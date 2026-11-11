# TextureLab Desktop

Bài tập lớn Xử lý ảnh — Nhóm 2, nhóm lớp 7. Ứng dụng phân tích hướng kết cấu
ảnh bằng Sobel và Fourier
## Chạy ứng dụng

Cần Python 3.11 trở lên. Trên Windows, mở **`run_windows.bat`** để tự tạo môi
trường, cài thư viện và chạy app. Có thể chạy thủ công:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```


## Chức năng

- Phân tích ảnh đơn hoặc thư mục; chọn ROI bằng chuột hoặc tọa độ.
- Hiển thị histogram, bản đồ hướng, gradient, phổ Fourier và thống kê.
- Đối chiếu CSV Fiji Directionality; xuất CSV, JSON, PNG, HTML, NPZ và ZIP.

Góc hướng thuộc [0°, 180°), đo ngược chiều kim đồng hồ: 0° nằm ngang,
90° thẳng đứng. Đầu vào là ảnh đơn khung, tối đa 20 MiB và 24 triệu pixel.

## Dòng lệnh và kiểm thử

```powershell
.venv\Scripts\python.exe cli.py analyze data/samples/stripes_030.png --out results/single
.venv\Scripts\python.exe cli.py batch data/samples --out results/batch
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

Bộ kiểm thử gồm 63 trường hợp. Xem thêm lệnh bằng `python cli.py --help`.
Đóng gói Windows bằng `build_windows.bat`; đầu ra: `dist/TextureLab/`.

## Cấu trúc và tài liệu

- `app.py`, `desktop_ui.py`, `desktop_worker.py`: giao diện và xử lý nền.
- `texture/`, `cli.py`: thuật toán, đọc/xuất dữ liệu và dòng lệnh.
- `tests/`, `data/`, `results/`: kiểm thử, ảnh mẫu và kết quả thực nghiệm.
- `fiji/`, `tools/`: chạy đối chứng Fiji, so sánh và đo hiệu năng.

[Báo cáo](bao_cao/BAOCAO_BTL_XLA_NHOM_2.docx) ·
[Slide PowerPoint](thuyet_trinh/TextureLab_Desktop.pptx) ·

Số liệu kiểm chứng nằm trong `results/windows/`; kết luận độ chính xác giới hạn
ở ảnh tổng hợp có nhãn. Mã nguồn dự án theo [MIT License](LICENSE.txt).
