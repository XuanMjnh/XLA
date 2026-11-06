# TextureLab Desktop 2.0

Phân tích hướng kết cấu ảnh bằng Sobel và Fourier. Giao diện desktop Qt/PySide6, xử lý ngoại tuyến.

Giao diện dùng bộ màu sáng cố định cho nền, chữ và các điều khiển, không phụ thuộc chế độ sáng/tối của hệ điều hành.

## Thành phần

- `app.py`: ứng dụng desktop.
- `texture/`: thuật toán, dữ liệu tổng hợp, xuất kết quả, thực nghiệm và đối chiếu histogram.
- `cli.py`: phân tích ảnh đơn, xử lý lô và benchmark.
- `fiji/`: script Directionality và đối chiếu CSV.
- `data/samples/`: ảnh có nhãn và manifest.
- `results/experiments/`: số liệu thực nghiệm, cấu hình và biểu đồ.
- `bao_cao/`: báo cáo học phần.
- `thuyet_trinh/`: presentation.
- `tests/`: kiểm thử thuật toán và desktop.

## Môi trường

Python 3.11–3.13. NumPy, SciPy, OpenCV headless, Pillow, Matplotlib, PySide6 Essentials.

## Điểm vào

| Tệp | Chức năng |
| --- | --- |
| `run_windows.bat` | Khởi chạy desktop trên Windows với Python đã cài |
| `run_unix.sh` | Khởi chạy desktop trên Linux/macOS với Python đã cài |
| `build_windows.bat` | Tạo ứng dụng Windows tại `dist/TextureLab/TextureLab.exe` trên máy Windows |
| `build.py` | Đóng gói trên hệ điều hành đang chạy |

## Quy ước dữ liệu

Góc cấu trúc ngược chiều kim đồng hồ, 0° nằm ngang, chu kỳ 180°. Histogram chuẩn hóa theo tổng trọng số. R là độ tập trung góc trục. Tần số tính trên pixel sau tiền xử lý.

CSV Fiji: `angle_deg,weight`. So sánh histogram thô theo nội suy tuần hoàn. Script Fiji nhận ảnh xám đơn khung; đầu vào `input.png` trong gói kết quả đã cắt ROI và giảm kích thước, chưa áp dụng Gaussian.

## Phạm vi thực nghiệm

Ảnh tổng hợp có góc đúng xác định từ bộ sinh. Đã chạy Directionality 2.3.0 chính thức trong runtime ImageJ 1.54p headless trên 15 ảnh mẫu. Histogram, góc khớp Gaussian, độ rộng, amount và goodness of fit nằm trong `results/fiji/`. Chưa có đánh giá ảnh tự nhiên có nhãn. Kiểm thử desktop thực hiện bằng Qt offscreen trên Linux. Gói nguồn có launcher Windows, chưa kèm tệp thực thi Windows đã biên dịch.
