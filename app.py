z#!/usr/bin/env python3
"""TextureLab native desktop application."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
from time import perf_counter
import uuid
import zipfile
import numpy as np
from PySide6.QtCore import Qt, QRect, QRectF, QSize, Signal, QThread, QSettings
from PySide6.QtGui import QAction, QPixmap, QPainter, QPen, QColor, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QSplitter, QTabWidget, QScrollArea, QSpinBox, QDoubleSpinBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QProgressBar, QToolBar, QDialog, QDialogButtonBox,
    QFrame, QStackedWidget,
)
from desktop_ui import STYLE, EmptyState, OrangeCheckBox, ResultsTable, Section, brand_pixmap, icon
from texture.analysis import AnalysisConfig, analyze
from texture.io import load_image, png_bytes, SUPPORTED_EXTENSIONS
from texture.export import write_export
from texture.comparison import compare_histograms

VERSION = '2.0.0'
ROLE = Qt.ItemDataRole.UserRole
STATES = {
    'no_signal': 'Không có tín hiệu',
    'multimodal_or_mixed': 'Nhiều hướng',
    'diffuse_or_weakly_oriented': 'Hướng phân tán',
    'strong_single_axis_component': 'Một hướng trội',
    'mixed_or_moderately_oriented': 'Hướng hỗn hợp',
}


def fmt(value, decimals=4):
    return '—' if value is None else f'{value:.{decimals}f}'


def atomic_bytes(path, data):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def package_records(records, destination):
    """Atomic export with distinct directories for duplicate basenames."""
    destination = Path(destination)
    temporary = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            rows = []
            for index, record in enumerate(records, 1):
                prefix = f'{index:03d}_{Path(record["path"]).stem}' if len(records) > 1 else ''
                for file in sorted(Path(record['directory']).iterdir()):
                    if file.is_file():
                        z.write(file, str(Path(prefix) / file.name))
                row = {'file': Path(record['path']).name, 'elapsed_ms': record['elapsed_ms']}
                for method in ('spatial', 'fourier'):
                    for key in ('peak_angle_deg', 'resultant_length', 'entropy_normalized'):
                        row[f'{method}_{key}'] = record['summary'][method][key]
                rows.append(row)
            if len(rows) > 1:
                from io import StringIO
                buffer = StringIO(newline='')
                writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
                z.writestr('batch_summary.csv', buffer.getvalue().encode('utf-8-sig'))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


class ImageView(QWidget):
    roiChanged = Signal(object)

    def __init__(self, selectable=False):
        super().__init__()
        self.setMinimumSize(200, 160)
        self.pixmap = QPixmap()
        self.selectable = selectable
        self.roi = None
        self.origin = None
        self.drag = None
        self.empty = None

    def set_empty_state(self, title, description='', action=None):
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 24, 24, 24)
        self.empty = EmptyState(title, description, action)
        layout.addWidget(self.empty)

    def update_empty_state(self):
        if self.empty: self.empty.setVisible(self.pixmap.isNull())

    def image_rect(self):
        if self.pixmap.isNull():
            return QRect()
        size = self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width()-size.width())//2, (self.height()-size.height())//2, size.width(), size.height())

    def set_data(self, data):
        self.pixmap = QPixmap(); self.pixmap.loadFromData(data)
        self.roi = None; self.update_empty_state(); self.update()

    def set_file(self, path):
        self.pixmap = QPixmap(str(path)) if path else QPixmap()
        self.roi = None; self.update_empty_state(); self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#fafbfe'))
        if self.pixmap.isNull() and self.empty:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor('#d8deea'), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(14, 18, -14, -14), 10, 10)
        area = self.image_rect()
        if not self.pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(area, self.pixmap)
            selection = self.drag
            if self.roi and selection is None:
                x,y,w,h = self.roi
                sx,sy = area.width()/self.pixmap.width(), area.height()/self.pixmap.height()
                selection = QRectF(area.left()+x*sx, area.top()+y*sy, w*sx, h*sy)
            if selection is not None:
                painter.setPen(QPen(QColor('#c4510c'), 2)); painter.setBrush(QColor(196,81,12,35))
                painter.drawRect(selection)

    def mousePressEvent(self, event):
        if self.selectable and event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position().toPoint()):
            self.origin = event.position().toPoint(); self.drag = QRect(self.origin, self.origin)

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.drag = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.image_rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is None: return
        r, area = self.drag, self.image_rect()
        self.origin = None; self.drag = None
        if r and r.width() > 2 and r.height() > 2:
            sx,sy = self.pixmap.width()/area.width(), self.pixmap.height()/area.height()
            x = max(0, int((r.left()-area.left())*sx)); y = max(0, int((r.top()-area.top())*sy))
            w = min(self.pixmap.width()-x, int(r.width()*sx)); h = min(self.pixmap.height()-y, int(r.height()*sy))
            if w >= 32 and h >= 32:
                self.roi = (x,y,w,h); self.roiChanged.emit(self.roi)
        self.update()


class AnalysisWorker(QThread):
    completed = Signal(object)
    failed = Signal(str, str)
    progress = Signal(int, int)

    def __init__(self, jobs, config, directory, arrays=False):
        super().__init__()
        self.jobs, self.config = jobs, config
        self.directory, self.arrays = directory, arrays

    def run(self):
        for index, (path, roi) in enumerate(self.jobs):
            if self.isInterruptionRequested(): break
            try:
                start = perf_counter()
                image = load_image(path); result = analyze(image, self.config, roi)
                elapsed = (perf_counter()-start)*1000
                result.metadata.update({
                    'source_filename': Path(path).name,
                    'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'application_version': VERSION, 'elapsed_ms_read_and_analysis': elapsed,
                    'runtime': {'python': platform.python_version(), **{
                        name: importlib.metadata.version(name) for name in
                        ('numpy', 'scipy', 'opencv-python-headless', 'Pillow', 'PySide6-Essentials')
                    }},
                })
                folder = Path(self.directory)/uuid.uuid4().hex
                write_export(result, folder, Path(path).name, arrays=self.arrays)
                self.completed.emit({'path': path, 'directory': str(folder), 'summary': result.summary(),
                                     'elapsed_ms': elapsed, 'roi': roi})
                del image, result
            except Exception as exc:
                self.failed.emit(path, str(exc))
            self.progress.emit(index+1, len(self.jobs))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TextureLab · Phân tích hướng kết cấu'); self.resize(1600, 940)
        self.setMinimumSize(1180, 760); self.setWindowIcon(icon('layers', '#c4510c'))
        self.settings = QSettings('TextureLab', 'Desktop')
        self.session = tempfile.TemporaryDirectory(prefix='texturelab_')
        self.records = {}; self.rois = {}; self.worker = None; self.errors = []; self.inputs = {}
        self.setAcceptDrops(True); self.build_ui()
        geometry = self.settings.value('geometry')
        if geometry: self.restoreGeometry(geometry)

    def button(self, text, callback, glyph=None):
        button = QPushButton(text); button.clicked.connect(callback)
        if glyph: button.setIcon(icon(glyph))
        return button

    def build_ui(self):
        toolbar = QToolBar(); toolbar.setMovable(False); toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setIconSize(QSize(18,18)); self.addToolBar(toolbar)
        brand = QWidget(); brand_layout = QHBoxLayout(brand); brand_layout.setContentsMargins(0,0,0,0)
        logo = QLabel(); logo.setPixmap(brand_pixmap()); brand_layout.addWidget(logo)
        title = QLabel('TEXTURELAB'); title.setObjectName('brand'); brand_layout.addWidget(title)
        toolbar.addWidget(brand); toolbar.addSeparator()
        for name, callback, shortcut, glyph in [
            ('Mở ảnh', self.open_files, QKeySequence.StandardKey.Open, 'image'),
            ('Mở thư mục', self.open_folder, None, 'folder'),
            ('Lưu kết quả', self.export_current, QKeySequence.StandardKey.Save, 'save'),
            ('Lưu toàn bộ', self.export_all, None, 'layers'),
        ]:
            action = QAction(icon(glyph, '#ffffff' if name == 'Mở ảnh' else '#273044'), name, self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback); toolbar.addAction(action)
            if name == 'Mở ảnh':
                toolbar.widgetForAction(action).setObjectName('primary'); self.open_action = action
            if name == 'Mở thư mục': self.folder_action = action
            if name == 'Lưu kết quả': self.save_action = action
            if name == 'Lưu toàn bộ': self.save_all_action = action
        toolbar.addSeparator()
        action = QAction(icon('info'), 'Thông tin nhóm', self); action.triggered.connect(self.edit_group); toolbar.addAction(action)
        root = QWidget(); root_layout = QVBoxLayout(root); root_layout.setContentsMargins(12,14,12,8)
        main = QSplitter(); main.setChildrenCollapsible(False); main.setHandleWidth(16); root_layout.addWidget(main); self.setCentralWidget(root)
        left = QFrame(); left.setObjectName('card'); left.setMinimumWidth(220); lv = QVBoxLayout(left)
        lv.setContentsMargins(10,8,10,12); lv.setSpacing(12)
        heading = QLabel('  DANH SÁCH ẢNH'); heading.setObjectName('listHeading'); lv.addWidget(heading)
        self.group_label = QLabel(self.settings.value('group', '')); self.group_label.setObjectName('muted')
        self.group_label.setWordWrap(True); self.group_label.setVisible(bool(self.group_label.text())); lv.addWidget(self.group_label)
        self.file_list = QListWidget(); self.file_list.currentItemChanged.connect(self.select_file)
        self.file_stack = QStackedWidget(); self.file_stack.addWidget(self.file_list)
        self.list_empty = EmptyState('Chưa có ảnh nào', 'Mở ảnh hoặc thư mục để bắt đầu phân tích kết cấu.')
        self.file_stack.addWidget(self.list_empty); lv.addWidget(self.file_stack, 1)
        self.remove_button = self.button('Xóa ảnh', self.remove_current, 'trash')
        self.clear_button = self.button('Xóa tất cả', self.clear_files, 'layers')
        row = QHBoxLayout(); row.addWidget(self.remove_button); row.addWidget(self.clear_button); lv.addLayout(row)
        main.addWidget(left)
        center = QWidget(); cv = QVBoxLayout(center); cv.setContentsMargins(0,0,0,0); cv.setSpacing(14)
        viewer = QFrame(); viewer.setObjectName('card'); viewer_layout = QVBoxLayout(viewer)
        viewer_layout.setContentsMargins(12,10,12,10); viewer_layout.setSpacing(0)
        self.filename = QLabel(''); self.filename.setObjectName('filename'); self.filename.hide(); viewer_layout.addWidget(self.filename)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setIconSize(QSize(17,17))
        viewer_layout.addWidget(self.tabs, 1); cv.addWidget(viewer, 1); self.views = {}
        for name, label in [('source','Ảnh gốc'),('histogram','Histogram'),('orientation_map','Bản đồ hướng'),
                            ('gradient_magnitude','Gradient'),('fft_spectrum','Phổ Fourier'),('preprocessed','Tiền xử lý')]:
            view = ImageView(selectable=name == 'source'); self.views[name] = view
            if name == 'source':
                view.roiChanged.connect(self.set_roi)
                view.set_empty_state('Mở ảnh để xem và phân tích', 'Kéo thả ảnh vào đây hoặc sử dụng nút “Mở ảnh” ở thanh công cụ.', self.open_files)
            else: view.set_empty_state('Chưa có kết quả', 'Chạy phân tích để xem kết quả tại đây.')
            if name == 'orientation_map':
                panel=QWidget(); layout=QVBoxLayout(panel); layout.setContentsMargins(0,0,0,0)
                layout.addWidget(view,1); self.legend=ImageView(); self.legend.setMinimumHeight(70); self.legend.setMaximumHeight(85)
                layout.addWidget(self.legend); self.tabs.addTab(panel,label)
            else: self.tabs.addTab(view, label)
        self.table = QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['Góc (°)','Sobel gốc','Sobel trơn','Fourier gốc','Fourier trơn'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabs.addTab(self.table, 'Dữ liệu')
        self.fiji_panel = QWidget(); fv = QVBoxLayout(self.fiji_panel); controls = QHBoxLayout()
        self.compare_method = QComboBox(); self.compare_method.addItems(['Sobel','Fourier']); self.compare_method.currentIndexChanged.connect(self.clear_comparison)
        controls.addWidget(self.compare_method); self.import_fiji = self.button('Nhập CSV Fiji', self.compare_fiji)
        controls.addWidget(self.import_fiji); controls.addStretch(); fv.addLayout(controls)
        self.comparison_label = QLabel(''); self.comparison_label.setWordWrap(True); fv.addWidget(self.comparison_label)
        self.comparison_view = ImageView(); fv.addWidget(self.comparison_view, 1); self.tabs.addTab(self.fiji_panel, 'Đối chiếu Fiji')
        for index, glyph in enumerate(['image','histogram','compass','gradient','fourier','sliders','data','compare']):
            self.tabs.setTabIcon(index, icon(glyph))
        self.tabs.currentChanged.connect(self.update_tab_icons); self.update_tab_icons(0)
        self.stats = ResultsTable()
        self.stats.setHorizontalHeaderLabels(['Phương pháp','Góc đỉnh (°)','R','Entropy','Khối lượng ±10°','Phân bố'])
        self.stats.verticalHeader().hide(); self.stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats.horizontalHeader().setMinimumSectionSize(105)
        for column in range(self.stats.columnCount()):
            header = self.stats.horizontalHeaderItem(column); header.setToolTip(header.text())
        self.stats.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.stats.setShowGrid(False)
        self.stats.setAlternatingRowColors(True)
        results = QFrame(); results.setObjectName('card'); results.setFixedHeight(168)
        results_layout = QVBoxLayout(results); results_layout.setContentsMargins(12,10,12,10); results_layout.addWidget(self.stats)
        cv.addWidget(results)
        self.metadata = QLabel(''); self.metadata.setObjectName('muted'); self.metadata.setWordWrap(True); self.metadata.hide(); cv.addWidget(self.metadata); main.addWidget(center)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumWidth(310)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0,0,0,0); rv.setSpacing(10)
        params = Section('THAM SỐ', 'settings'); form = QFormLayout(params.body)
        form.setContentsMargins(0,6,0,0); form.setVerticalSpacing(5); form.setHorizontalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        specs = [('bins','Số bin',18,720,180,0),('gaussian_sigma','Gaussian σ (px)',0,5,1,2),
                 ('gradient_threshold','Ngưỡng gradient',0,.99,.05,2),('histogram_sigma_deg','Làm trơn góc (°)',0,15,2,2),
                 ('min_frequency','Tần số nhỏ nhất',0,.499,.02,3),('max_frequency','Tần số lớn nhất',.001,.5,.45,3),
                 ('max_size','Cạnh tối đa (px)',64,2048,1024,0)]
        for key,label,lo,hi,value,decimals in specs:
            widget = QDoubleSpinBox() if decimals else QSpinBox()
            if decimals: widget.setDecimals(decimals); widget.setSingleStep(.01 if decimals == 2 else .001)
            widget.setRange(lo,hi); widget.setValue(value); widget.valueChanged.connect(self.invalidate)
            self.inputs[key] = widget; form.addRow(label, widget)
        for key,label,items,default in [('sobel_size','Sobel',['3','5','7'],'5'),('gradient_weight','Trọng số',['1','2'],'2')]:
            box = QComboBox(); box.addItems(items); box.setCurrentText(default); box.currentIndexChanged.connect(self.invalidate)
            self.inputs[key] = box; form.addRow(label,box)
        self.hann = OrangeCheckBox('Cửa sổ Hann'); self.hann.setChecked(True); self.hann.toggled.connect(self.invalidate); form.addRow(self.hann)
        self.arrays = OrangeCheckBox('Lưu ma trận NPZ'); self.arrays.toggled.connect(self.invalidate); form.addRow(self.arrays); rv.addWidget(params)
        region = Section('VÙNG PHÂN TÍCH', 'roi'); rf = QFormLayout(region.body); self.roi_fields = []
        rf.setContentsMargins(0,6,0,0); rf.setVerticalSpacing(6)
        rf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for label in ['X','Y','Rộng','Cao']:
            spin=QSpinBox(); spin.setRange(0,24000000); self.roi_fields.append(spin); rf.addRow(label,spin)
        self.apply_roi = self.button('Áp dụng ROI',self.apply_roi_fields, 'roi'); rf.addRow(self.apply_roi)
        self.reset_roi = self.button('Toàn ảnh',self.clear_roi, 'roi'); rf.addRow(self.reset_roi); rv.addWidget(region)
        self.run_button = self.button('PHÂN TÍCH',self.analyze_current); self.run_button.setObjectName('primary'); self.run_button.setIcon(icon('play', '#ffffff'))
        self.batch_button = self.button('Phân tích toàn bộ', self.analyze_all, 'layers')
        self.cancel_button = self.button('Dừng',self.cancel, 'stop'); self.cancel_button.setEnabled(False)
        actions = QFrame(); actions.setObjectName('card'); av = QVBoxLayout(actions)
        av.setContentsMargins(10,10,10,10); av.setSpacing(7)
        av.addWidget(self.run_button); av.addWidget(self.batch_button); av.addWidget(self.cancel_button)
        rv.addStretch(); scroll.setWidget(right)
        sidebar = QWidget(); sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0,0,0,0); sidebar_layout.setSpacing(10)
        sidebar_layout.addWidget(scroll, 1); sidebar_layout.addWidget(actions)
        main.addWidget(sidebar); main.setSizes([250,960,330]); main.setStretchFactor(1,1)
        self.progress = QProgressBar(); self.progress.setFixedWidth(180); self.progress.hide(); self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage('Sẵn sàng'); self.refresh_actions()

    def update_tab_icons(self, selected):
        for index, glyph in enumerate(['image','histogram','compass','gradient','fourier','sliders','data','compare']):
            self.tabs.setTabIcon(index, icon(glyph, '#ffffff' if index == selected else '#454c5c'))

    def current_path(self):
        item = self.file_list.currentItem(); return item.data(ROLE) if item else None

    def config(self):
        values = {key: int(w.currentText()) if isinstance(w,QComboBox) else w.value() for key,w in self.inputs.items()}
        values['use_hann'] = self.hann.isChecked(); config = AnalysisConfig(**values); config.validate(); return config

    def notify_error(self, error): QMessageBox.warning(self, 'Không thể thực hiện', str(error))

    def refresh_actions(self):
        busy = self.worker is not None; has_file = self.current_path() is not None; has_result = self.current_path() in self.records
        self.file_stack.setCurrentWidget(self.file_list if self.file_list.count() else self.list_empty)
        self.remove_button.setEnabled(has_file and not busy); self.clear_button.setEnabled(bool(self.file_list.count()) and not busy)
        self.open_action.setEnabled(not busy); self.folder_action.setEnabled(not busy)
        self.views['source'].empty.open_button.setEnabled(not busy)
        self.run_button.setEnabled(has_file and not busy); self.batch_button.setEnabled(self.file_list.count() > 0 and not busy)
        self.save_action.setEnabled(has_result and not busy); self.save_all_action.setEnabled(bool(self.records) and not busy); self.import_fiji.setEnabled(has_result and not busy)
        for widget in [*self.inputs.values(), self.hann,self.arrays,self.apply_roi,self.reset_roi,*self.roi_fields,self.file_list]: widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy); self.views['source'].selectable = not busy

    def open_files(self):
        if self.worker: return
        paths,_ = QFileDialog.getOpenFileNames(self,'Mở ảnh',self.settings.value('last_folder',''),'Ảnh (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)'); self.add_files(paths)

    def open_folder(self):
        if self.worker: return
        folder = QFileDialog.getExistingDirectory(self,'Mở thư mục',self.settings.value('last_folder',''))
        if folder: self.add_files(sorted(str(p) for p in Path(folder).iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS))

    def add_files(self, paths):
        if self.worker: return
        known = {self.file_list.item(i).data(ROLE) for i in range(self.file_list.count())}; first = None
        for path in paths:
            path = str(Path(path).resolve())
            if path in known or Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS: continue
            item=QListWidgetItem(Path(path).name); item.setData(ROLE,path); item.setToolTip(path)
            self.file_list.addItem(item); known.add(path)
            if first is None: first=item
        if first:
            self.settings.setValue('last_folder',str(Path(first.data(ROLE)).parent)); self.file_list.setCurrentItem(first)
        self.refresh_actions()

    def remove_current(self):
        if self.worker: return
        path=self.current_path()
        if path:
            self.records.pop(path,None); self.rois.pop(path,None); self.file_list.takeItem(self.file_list.currentRow())
        self.refresh_actions()

    def clear_files(self):
        if self.worker: return
        self.file_list.clear(); self.records.clear(); self.rois.clear(); self.select_file(); self.refresh_actions()

    def select_file(self, *args):
        self.clear_results(); path=self.current_path(); self.filename.setText(Path(path).name if path else ''); self.views['source'].set_file(None)
        self.filename.setVisible(bool(path))
        if path:
            try:
                image=load_image(path)
                if image.dtype != np.uint8:
                    lo,hi=float(image.min()),float(image.max()); image=(image-lo)/(hi-lo) if hi>lo else np.zeros_like(image,dtype=float)
                self.views['source'].set_data(png_bytes(image)); self.views['source'].roi=self.rois.get(path)
                h,w=image.shape[:2]; roi=self.rois.get(path,(0,0,w,h))
                for spin,value in zip(self.roi_fields,roi): spin.setValue(value)
                self.statusBar().showMessage(f'{w} × {h} px')
            except Exception as exc: self.statusBar().showMessage(str(exc))
        if path in self.records: self.show_record(self.records[path])
        self.refresh_actions()

    def clear_comparison(self, *args): self.comparison_view.set_file(None); self.comparison_label.clear()

    def clear_results(self):
        for key,view in self.views.items():
            if key != 'source': view.set_file(None)
        self.legend.set_file(None); self.stats.clearContents(); self.table.setRowCount(0); self.metadata.clear(); self.clear_comparison()
        self.stats.show_empty(True); self.metadata.hide()

    def invalidate(self, *args):
        if not hasattr(self,'stats'): return
        self.records.clear(); self.clear_results()
        for i in range(self.file_list.count()):
            item=self.file_list.item(i); item.setText(Path(item.data(ROLE)).name)
        self.refresh_actions()

    def set_roi(self, roi):
        path=self.current_path()
        if not path or self.worker: return
        self.rois[path]=tuple(roi); self.records.pop(path,None); self.views['source'].roi=tuple(roi); self.views['source'].update()
        for spin,value in zip(self.roi_fields,roi): spin.setValue(value)
        self.clear_results(); self.refresh_actions(); self.statusBar().showMessage(f'ROI: {roi[0]}, {roi[1]}, {roi[2]} × {roi[3]} px')

    def apply_roi_fields(self):
        if not self.current_path(): return
        roi=tuple(spin.value() for spin in self.roi_fields); x,y,w,h=roi; p=self.views['source'].pixmap
        if p.isNull() or min(w,h)<32 or x+w>p.width() or y+h>p.height():
            self.notify_error('ROI phải nằm trong ảnh và có kích thước tối thiểu 32 × 32 px.'); return
        self.set_roi(roi)

    def clear_roi(self):
        path=self.current_path()
        if path: self.rois.pop(path,None); self.records.pop(path,None); self.select_file()

    def analyze_current(self):
        if self.current_path(): self.start_jobs([self.current_path()])

    def analyze_all(self): self.start_jobs([self.file_list.item(i).data(ROLE) for i in range(self.file_list.count())])

    def start_jobs(self, paths):
        if self.worker or not paths: return
        try: config=self.config()
        except ValueError as exc: self.notify_error(exc); return
        for path in paths: self.records.pop(path,None)
        self.clear_results(); self.errors=[]
        self.worker=AnalysisWorker([(p,self.rois.get(p)) for p in paths],config,self.session.name,self.arrays.isChecked())
        self.worker.completed.connect(self.accept_record); self.worker.failed.connect(lambda p,e:self.errors.append(f'{Path(p).name}: {e}'))
        self.worker.progress.connect(self.update_progress); self.worker.finished.connect(self.finished_jobs)
        self.progress.setRange(0,len(paths)); self.progress.setValue(0); self.progress.show()
        self.statusBar().showMessage('Đang phân tích…'); self.refresh_actions(); self.worker.start()

    def update_progress(self, current,total): self.progress.setValue(current); self.statusBar().showMessage(f'Đã xử lý {current}/{total} ảnh')

    def accept_record(self, record):
        record['summary']['submission'] = {'group': self.settings.value('group',''), 'members': self.settings.value('members','')}
        atomic_bytes(Path(record['directory'])/'summary.json',json.dumps(record['summary'],indent=2,ensure_ascii=False,allow_nan=False).encode())
        self.records[record['path']]=record
        for i in range(self.file_list.count()):
            item=self.file_list.item(i)
            if item.data(ROLE)==record['path']: item.setText('✓ '+Path(record['path']).name)
        if self.current_path()==record['path']: self.show_record(record); self.tabs.setCurrentIndex(1)

    def finished_jobs(self):
        worker=self.worker; self.worker=None; stopped=worker.isInterruptionRequested(); worker.deleteLater()
        self.progress.hide(); self.refresh_actions(); self.statusBar().showMessage('Đã dừng' if stopped else f'Hoàn tất · {len(self.records)} ảnh')
        if self.errors: self.notify_error('\n'.join(self.errors))

    def show_record(self, record):
        self.stats.show_empty(False); self.metadata.show()
        folder=Path(record['directory']); summary=record['summary']; self.legend.set_file(folder/'orientation_legend.png')
        for key,view in self.views.items():
            if key!='source': view.set_file(folder/(key+'.png'))
        for row,(label,method) in enumerate([('Sobel','spatial'),('Fourier','fourier')]):
            s=summary[method]; values=[label,fmt(s['peak_angle_deg']),fmt(s['resultant_length']),fmt(s['entropy_normalized']),fmt(s['peak_mass_pm10deg']),STATES.get(s['interpretation'],s['interpretation'])]
            for col,value in enumerate(values): self.stats.setItem(row,col,QTableWidgetItem(value))
        with (folder/'histograms.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.reader(f))[1:]
        self.table.setRowCount(len(rows))
        for row,values in enumerate(rows):
            for col,value in enumerate(values): self.table.setItem(row,col,QTableWidgetItem(f'{float(value):.6f}'))
        h,w=summary['metadata']['analysis_shape_hw']
        self.metadata.setText(f'{w} × {h} px · {summary["config"]["bins"]} bin · {record["elapsed_ms"]:.1f} ms · ROI: '+('toàn ảnh' if record['roi'] is None else ', '.join(map(str,record['roi']))))
        peaks=[]
        for label,method in [('Sobel','spatial'),('Fourier','fourier')]:
            peaks.append(label+': '+(', '.join(f'{x:.2f}°' for x in summary[method]['peaks_deg']) or '—'))
        self.metadata.setText(self.metadata.text()+'\nĐỉnh '+ ' · '.join(peaks))

    def cancel(self):
        if self.worker: self.worker.requestInterruption(); self.cancel_button.setEnabled(False); self.statusBar().showMessage('Đang dừng…')

    def export_current(self):
        path=self.current_path()
        if path in self.records: self.export_records([self.records[path]],Path(path).stem+'_ket_qua.zip')

    def export_all(self):
        records=[self.records[self.file_list.item(i).data(ROLE)] for i in range(self.file_list.count()) if self.file_list.item(i).data(ROLE) in self.records]
        if records: self.export_records(records,'TextureLab_ket_qua.zip')

    def export_records(self, records, name):
        path,_=QFileDialog.getSaveFileName(self,'Lưu kết quả',name,'ZIP (*.zip)')
        if path:
            if not path.lower().endswith('.zip'): path+='.zip'
            try: package_records(records,path); self.statusBar().showMessage('Đã lưu '+Path(path).name)
            except Exception as exc: self.notify_error(exc)

    def compare_fiji(self):
        record=self.records.get(self.current_path())
        if not record: return
        path,_=QFileDialog.getOpenFileName(self,'Nhập CSV Fiji','','CSV (*.csv)')
        if not path: return
        method=('spatial','fourier')[self.compare_method.currentIndex()]
        try:
            folder=Path(record['directory']); report,angles,hp,hf=compare_histograms(folder/'histograms.csv',path,method)
            import matplotlib.pyplot as plt
            from texture.export import _fig_bytes
            fig,ax=plt.subplots(figsize=(9,4.5)); ax.plot(angles,100*hp,label='Python',color='#0d9488'); ax.plot(angles,100*hf,label='Fiji',color='#ea580c')
            ax.set(xlim=(0,180),xlabel='Structure angle (degrees)',ylabel='Normalized weight (%)'); ax.grid(alpha=.2); ax.legend(); fig.tight_layout(); png=_fig_bytes(fig)
            atomic_bytes(folder/f'fiji_{method}.png',png); atomic_bytes(folder/f'fiji_{method}.json',json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False).encode())
            atomic_bytes(folder/f'fiji_{method}_source.csv',Path(path).read_bytes()); self.comparison_view.set_data(png)
            self.comparison_label.setText(f'{Path(path).name}\nΔ góc: {report["peak_difference_deg"]:.4f}° · JSD: {report["jensen_shannon_divergence_base2"]:.6f} · MAE histogram: {report["histogram_mae"]:.6f}')
        except Exception as exc: self.notify_error(exc)

    def edit_group(self):
        from PySide6.QtWidgets import QLineEdit, QPlainTextEdit
        dialog=QDialog(self); dialog.setWindowTitle('Thông tin nhóm'); form=QFormLayout(dialog)
        group=QLineEdit(self.settings.value('group','')); members=QPlainTextEdit(self.settings.value('members',''))
        form.addRow('Mã nhóm',group); form.addRow('Thành viên',members)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec():
            self.settings.setValue('group',group.text().strip()); self.settings.setValue('members',members.toPlainText().strip()); self.group_label.setText(group.text().strip()); self.group_label.setVisible(bool(group.text().strip()))
            for record in self.records.values():
                record['summary']['submission']={'group':group.text().strip(),'members':members.toPlainText().strip()}
                atomic_bytes(Path(record['directory'])/'summary.json',json.dumps(record['summary'],indent=2,ensure_ascii=False,allow_nan=False).encode())

    def dragEnterEvent(self,event):
        if not self.worker and event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self,event): self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])

    def closeEvent(self,event):
        if self.worker: self.cancel(); event.ignore(); return
        self.settings.setValue('geometry',self.saveGeometry()); self.session.cleanup(); event.accept()


def configure_appearance(app):
    """Use one complete light theme, including controls not covered by QSS."""
    app.setStyle('Fusion')
    # Older supported Qt versions rely on the explicit palette below.
    if hasattr(app.styleHints(), 'setColorScheme'):
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = QPalette()
    colors = {
        'Window': '#f6f8fb', 'WindowText': '#273044',
        'Base': '#ffffff', 'AlternateBase': '#eef4f8',
        'Text': '#273044', 'PlaceholderText': '#6a7284',
        'Button': '#ffffff', 'ButtonText': '#273044',
        'Light': '#ffffff', 'Midlight': '#edf2f7',
        'Mid': '#dde2ec', 'Dark': '#6a7284', 'Shadow': '#273044',
        'Highlight': '#f5e9df', 'HighlightedText': '#a64009',
        'ToolTipBase': '#ffffff', 'ToolTipText': '#273044',
        'Link': '#a64009', 'LinkVisited': '#913806',
        'BrightText': '#ffffff', 'Accent': '#c4510c',
    }
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive,
                  QPalette.ColorGroup.Disabled):
        for role, color in colors.items():
            palette.setColor(group, getattr(QPalette.ColorRole, role), QColor(color))
    for role in ('WindowText', 'Text', 'ButtonText', 'PlaceholderText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor('#9aa7b7'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor('#edf1f6'))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


def main():
    app=QApplication(sys.argv); app.setApplicationName('TextureLab'); app.setApplicationVersion(VERSION)
    configure_appearance(app); window=MainWindow(); window.show()
    paths=[p for p in sys.argv[1:] if Path(p).is_file()]
    if paths: window.add_files(paths)
    return app.exec()

if __name__ == '__main__': sys.exit(main())
