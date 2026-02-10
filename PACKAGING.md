# PACKAGING.md — Đóng gói bằng PyInstaller

Hướng dẫn đóng gói `HSK_TOPIK_Creator` thành executable Windows bằng `PyInstaller`

1) Chuẩn bị môi trường

```powershell
# Từ thư mục gốc project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

2) Kiểm tra `HSK_TOPIK_Creator.spec`
- File spec hiện dùng `gui.py` là entrypoint và đã thêm `datas=[('resources','resources')]`.
- `hiddenimports` liệt kê một số module (openpyxl, google.*, bs4). Nếu khi chạy exe gặp lỗi ModuleNotFoundError, thêm tên module đó vào `hiddenimports`.

3) Thêm dữ liệu/tài nguyên vào spec (nếu cần)
- Nếu project dùng các thư mục data khác (ví dụ: `resources/schema`, `resources/prompts`, `input/`), thêm chúng vào `datas` dạng tuple `(src, dest)`:

```python
datas = [
    ('resources', 'resources'),
    ('config', 'config'),
    ('input', 'input'),
]
```

4) Các tùy chọn build phổ biến
- Dùng spec (giữ config trong file):

```powershell
pyinstaller --clean HSK_TOPIK_Creator.spec
```

- One-file executable (không dùng spec):

```powershell
pyinstaller --onefile --noconsole --add-data "resources;resources" gui.py
```

Lưu ý: trên Windows, `--add-data` dùng định dạng `src;dest`.

5) Kiểm tra kết quả
- Sau build, kiểm tra thư mục `dist/HSK_TOPIK_Creator/` (khi dùng spec) hoặc `dist/gui.exe` (onefile).
- Chạy exe, kiểm tra các chức năng chính: mở GUI, chọn folder input, tạo file output, gọi dịch vụ TTS/API.

6) Xử lý lỗi thường gặp
- Missing module at runtime: thêm module vào `hiddenimports` trong spec.
- Thiếu file dữ liệu: đảm bảo thư mục data được liệt kê trong `datas`.
- Lỗi credential/API: đặt `.env`, `resources/client_secret.json`, hoặc `token.json` cạnh exe hoặc cấu hình đúng theo RUNNING.md.


7) Lệnh build mẫu (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt pyinstaller
pyinstaller --clean HSK_TOPIK_Creator.spec
```
