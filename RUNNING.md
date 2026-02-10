# Hướng dẫn chạy dự án HSK_TOPIK_Creator

## 1) Yêu cầu
- Python 3.9+ (khuyến nghị 3.10/3.11)
- Git (tùy chọn)

## 2) Thiết lập môi trường
Mở PowerShell tại thư mục project (`d:\Edmicro\Tools\create_hsk`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu bạn muốn đóng gói exe: cài thêm `pyinstaller`:

```powershell
pip install pyinstaller
```

## 3) Cấu hình (Google credentials / API keys)
- File `resources/client_secret.json` chưa có sẵn trong repo; nếu bạn dùng OAuth token, đảm bảo `token.json` được tạo và đặt đúng chỗ.
- Một số tính năng (TTS, Gemini, Sheets) cần biến môi trường service account. Tạo file `.env` hoặc export các biến sau khi cần:

## 4) Chạy GUI
Giao diện chính là `gui.py`. Sau khi cài xong dependencies:

```powershell
python gui.py
```

Ứng dụng sẽ mở cửa sổ PyQt5 để bạn chọn thư mục PDF input, cấp độ HSK/TOPIK và thực thi pipeline.

## 5) Kiểm tra & khắc phục lỗi phổ biến
- Thiếu module khi chạy exe: kiểm tra thông báo lỗi và thêm vào `hiddenimports` trong `HSK_TOPIK_Creator.spec`.
- Thiếu tài nguyên (images, prompts, schema): đảm bảo các thư mục trong `resources/` đã có và được liệt kê trong `datas` của spec.
- Lỗi Google credential: kiểm tra `.env`, `client_secret.json` và `token.json`.

## 6) Nơi tìm code chính
- GUI: [gui.py](gui.py)
- Pipeline/CLI: [processor.py](processor.py)
- Tạo câu hỏi: [question_generator.py](question_generator.py)
- Tạo lời giải: [explanation_generator.py](explanation_generator.py)

---
