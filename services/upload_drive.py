import base64
import requests
import mimetypes
import os

# ================= CẤU HÌNH =================
# 1. Dán cái Web app URL của bạn vào đây
WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbxLIxvKSHtLY57wPss-K6LrKnV5s-abX166HEXs-cPY7DSivfZnw0-ct2luvV-wzQk9Xg/exec'

# 2. Đường dẫn file muốn upload
FILE_PATH = r'D:\Edmicro\Tools\create_hsk\draft\list.txt'
# ============================================

def upload_file_ngam():
    if not os.path.exists(FILE_PATH):
        print(f"❌ File không tồn tại: {FILE_PATH}")
        return

    # Lấy tên và định dạng file
    file_name = os.path.basename(FILE_PATH)
    mime_type, _ = mimetypes.guess_type(FILE_PATH)
    mime_type = mime_type or 'application/octet-stream'

    print(f"⚙️ Đang đọc và mã hóa file: {file_name} ...")

    # Đọc file ra chuỗi Base64
    with open(FILE_PATH, 'rb') as f:
        file_bytes = f.read()
        base64_data = base64.b64encode(file_bytes).decode('utf-8')

    # Đóng gói dữ liệu thành JSON (Chuẩn Backend API)
    payload = {
        "fileName": file_name,
        "mimeType": mime_type,
        "fileData": base64_data
    }

    print("🚀 Đang gọi API chạy ngầm để đẩy lên Drive...")
    try:
        # Bắn POST request chứa file JSON
        response = requests.post(WEB_APP_URL, json=payload)
        
        # Google Apps Script mặc định sẽ redirect (302) và requests của Python sẽ tự động handle việc đó.
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print("✅ UPLOAD THÀNH CÔNG!")
                print(f"📦 Tên file: {result.get('name')}")
                print(f"🔗 Link Drive: {result.get('url')}")
            else:
                print("❌ Lỗi từ Apps Script:", result.get('message'))
        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print("❌ Lỗi gọi API:", e)

if __name__ == '__main__':
    upload_file_ngam()