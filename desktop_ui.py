"""Native Qt building blocks for TextureLab's fixed orange theme."""
from PySide6.QtCore import QByteArray, Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QTableWidget, QToolButton,
    QStyle, QStyleOptionButton, QVBoxLayout, QWidget,
)


PATHS = {
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="15.5" cy="8.5" r="1.5"/><path d="m3 17 5-5 5 5 3-3 5 5"/>',
    'folder': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    'save': '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    'layers': '<path d="m12 3 10 6-10 6L2 9Zm-10 11 10 6 10-6M2 18l10 6 10-6"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
    'histogram': '<path d="M4 20V12m5 8V7m5 13V4m5 16V9"/>',
    'compass': '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5Z"/>',
    'gradient': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18m4-18v18m4-18v18" opacity=".45"/>',
    'fourier': '<circle cx="12" cy="12" r="2"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>',
    'sliders': '<path d="M3 7h8m5 0h5M3 17h3m5 0h10"/><circle cx="13.5" cy="7" r="2.5"/><circle cx="8.5" cy="17" r="2.5"/>',
    'data': '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    'compare': '<path d="M9 3H3v15h6m6-12h6v15h-6M8 8h8v8H8Z"/>',
    'roi': '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m6 0h6v-6"/>',
    'play': '<path d="m7 3 14 9-14 9Z"/>',
    'stop': '<rect x="4" y="4" width="16" height="16" rx="3"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    'settings': '<path d="m9 3-1 3-3 1-2 4 2 2v4l4 2 3-1 3 1 4-2v-4l2-2-2-4-3-1-1-3Z"/><circle cx="12" cy="11" r="3"/>',
    'chevron': '<path d="m6 9 6 6 6-6"/>',
    'up': '<path d="m6 15 6-6 6 6"/>',
    'table': '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 9v12m6-12v12M3 15h18"/>',
}


def svg_pixmap(svg, size):
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon(name, color='#273044'):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.7" '
           f'stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>')
    result = QIcon()
    result.addPixmap(svg_pixmap(svg, 40))
    disabled = svg.replace(color, '#a4aabb')
    result.addPixmap(svg_pixmap(disabled, 40), QIcon.Mode.Disabled)
    return result


def illustration(size=150, plus=False):
    badge = ('<circle cx="119" cy="112" r="20" fill="#c4510c" stroke="white" stroke-width="4"/>'
             '<path d="M110 112h18m-9-9v18" stroke="white" stroke-width="3" stroke-linecap="round"/>') if plus else ''
    return svg_pixmap(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160">
      <g fill="none" stroke="#c4510c" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <rect x="40" y="44" width="78" height="68" rx="5"/>
        <circle cx="94" cy="64" r="6"/>
        <path d="m40 99 25-25 21 22 13-13 19 19"/>
      </g>{badge}
    </svg>''', size)


def brand_pixmap():
    return svg_pixmap('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
      <g fill="none" stroke="#c4510c" stroke-width="3" stroke-linejoin="round">
        <path d="m4 23 16 9 16-9M4 30l16 9 16-9"/>
        <path d="m20 2 16 9-16 9L4 11Z" fill="#c4510c"/>
      </g>
    </svg>''', 36)


class EmptyState(QFrame):
    def __init__(self, title, description='', action=None, compact=False, parent=None):
        super().__init__(parent)
        self.setObjectName('emptyState')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12 if not compact else 5)
        layout.addStretch()
        graphic = QLabel()
        graphic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graphic.setPixmap(icon('table', '#9ba1ad').pixmap(30, 30) if compact else illustration(150 if action else 116, bool(action)))
        layout.addWidget(graphic)
        heading = QLabel(title)
        heading.setObjectName('emptyHeadingSmall' if compact else 'emptyHeading')
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter); heading.setWordWrap(True)
        layout.addWidget(heading)
        if description:
            detail = QLabel(description); detail.setObjectName('muted')
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter); detail.setWordWrap(True)
            layout.addWidget(detail)
        if action:
            button = QPushButton('Mở ảnh'); button.setIcon(icon('image', '#ffffff'))
            button.setObjectName('primary'); button.setFixedWidth(154)
            button.clicked.connect(action); layout.addSpacing(10)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.open_button = button
        layout.addStretch()


class Section(QFrame):
    """A card with a collapsible body that preserves all parameter values."""
    def __init__(self, title, glyph):
        super().__init__()
        self.setObjectName('section')
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 12, 16, 14)
        heading = QHBoxLayout()
        symbol = QLabel(); symbol.setPixmap(icon(glyph, '#c4510c').pixmap(21, 21)); heading.addWidget(symbol)
        label = QLabel(title); label.setObjectName('sectionHeading'); heading.addWidget(label, 1)
        self.toggle = QToolButton(); self.toggle.setObjectName('collapse')
        self.toggle.setCheckable(True); self.toggle.setChecked(True)
        self.toggle.setIcon(icon('up')); self.toggle.setToolTip('Thu gọn / mở rộng ' + title.lower())
        self.toggle.setAccessibleName(title)
        heading.addWidget(self.toggle); layout.addLayout(heading)
        self.body = QWidget(); layout.addWidget(self.body)
        self.toggle.toggled.connect(self.set_expanded)

    def set_expanded(self, expanded):
        self.body.setVisible(expanded)
        self.toggle.setIcon(icon('up' if expanded else 'chevron'))


class ResultsTable(QTableWidget):
    def __init__(self):
        super().__init__(2, 6)
        self.empty = EmptyState('Chưa có kết quả phân tích', 'Chạy phân tích để xem kết quả tại đây.', compact=True, parent=self.viewport())
        self.empty.setObjectName('resultsEmpty')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.empty.setGeometry(self.viewport().rect())

    def show_empty(self, visible):
        self.empty.setVisible(visible)
        self.empty.raise_()


class OrangeCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton(); self.initStyleOption(option)
        rect = QRectF(self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)).adjusted(.5,.5,-.5,-.5)
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = '#c4510c' if self.isEnabled() else '#b6bdc9'
        painter.setPen(QPen(QColor(color if self.isChecked() else '#cdd3df'), 1))
        painter.setBrush(QColor(color if self.isChecked() else '#ffffff'))
        painter.drawRoundedRect(rect, 3, 3)
        if self.isChecked():
            painter.setPen(QPen(QColor('white'), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline([QPointF(rect.left()+rect.width()*.22, rect.top()+rect.height()*.5),
                                  QPointF(rect.left()+rect.width()*.43, rect.top()+rect.height()*.72),
                                  QPointF(rect.left()+rect.width()*.8, rect.top()+rect.height()*.27)])


STYLE = '''
QWidget { font-family: "Segoe UI", "DejaVu Sans", sans-serif; font-size: 13px; color: #273044; }
QMainWindow, QDialog { background: #f6f8fb; }
QToolBar { background: #ffffff; border: 0; border-bottom: 1px solid #e6e9f0; spacing: 10px; padding: 14px 18px; }
QToolBar::separator { background: #dde1eb; width: 1px; margin: 3px 12px; }
QLabel#brand { font-size: 21px; font-weight: 800; color: #172033; padding-right: 22px; }
QToolButton, QPushButton { background: #ffffff; border: 1px solid #e0e4ed; border-radius: 5px; padding: 8px 12px; }
QToolButton { padding: 9px 15px; }
QToolButton:hover, QPushButton:hover { background: #f8f3ef; border-color: #c4510c; }
QToolButton:pressed, QPushButton:pressed { background: #f1dfd2; }
QPushButton#primary, QToolButton#primary { background: #c4510c; color: white; border: 1px solid #c4510c; font-weight: 600; }
QPushButton#primary { padding: 11px 16px; }
QPushButton#primary:hover, QToolButton#primary:hover { background: #ad4308; border-color: #ad4308; }
QPushButton#primary:pressed, QToolButton#primary:pressed { background: #913806; }
QPushButton:disabled, QToolButton:disabled, QPushButton#primary:disabled { color: #9aa7b7; background: #edf1f6; border-color: #edf1f6; }
QPushButton:focus, QToolButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #c4510c; }
QFrame#card, QFrame#section { background: white; border: 1px solid #e8ebf2; border-radius: 8px; }
QFrame#resultsEmpty { background: white; }
QLabel#listHeading { background: #f2f3f5; border-radius: 8px; padding: 12px; font-weight: 700; color: #202735; }
QLabel#filename { font-size: 14px; font-weight: 600; padding: 2px 4px 6px; }
QLabel#sectionHeading { font-size: 13px; font-weight: 700; color: #202735; }
QLabel#emptyHeading { font-size: 19px; font-weight: 700; color: #202735; }
QLabel#emptyHeadingSmall { font-size: 13px; font-weight: 600; color: #202735; }
QLabel#muted { color: #6a7284; font-size: 12px; }
QToolButton#collapse { border: 0; background: transparent; padding: 3px; }
QListWidget { background: white; border: 0; outline: 0; }
QListWidget::item { padding: 12px 8px; margin: 2px 0; border-radius: 4px; }
QListWidget::item:selected { background: #f5e9df; color: #a64009; }
QListWidget::item:hover { background: #f8f3ef; }
QTabWidget::pane { border: 0; background: white; }
QTabBar { background: #f5f6f9; border-radius: 5px; }
QTabBar::tab { padding: 10px 9px; margin: 3px 1px; border-radius: 4px; color: #454c5c; }
QTabBar::tab:selected { background: #c4510c; color: white; }
QTabBar::tab:!selected:hover { background: #f5e9df; }
QTabBar QToolButton { padding: 0; width: 22px; border: 0; border-radius: 4px; background: #edf1f6; }
QTableWidget { background: white; alternate-background-color: #fafafa; border: 0; gridline-color: #eef0f5; selection-background-color: #f5e9df; selection-color: #a64009; }
QHeaderView { background: #f2f3f5; }
QHeaderView::section { background: #f2f3f5; color: #303441; padding: 10px 3px; border: 0; border-right: 1px solid #fafafa; font-weight: 600; }
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { background: white; padding: 2px 7px; border: 1px solid #dde2ec; border-radius: 6px; min-height: 16px; selection-background-color: #eed7c7; selection-color: #273044; }
QPlainTextEdit { background: white; border: 1px solid #dde2ec; border-radius: 6px; padding: 7px; }
QComboBox QAbstractItemView { background: white; color: #273044; selection-background-color: #f5e9df; selection-color: #a64009; border: 1px solid #dde2ec; }
QCheckBox { spacing: 7px; padding: 2px 0; }
QCheckBox::indicator { width: 16px; height: 16px; }
QStatusBar { background: #f6f8fb; border: 0; padding: 5px 10px; }
QStatusBar::item { border: 0; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #f6f8fb; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #d7dce6; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: transparent; width: 12px; }
QProgressBar { border: 1px solid #d8bba8; background: #f8f3ef; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: #c4510c; border-radius: 4px; }
QToolTip { background: white; color: #273044; border: 1px solid #e0e4ed; padding: 5px; }
'''
