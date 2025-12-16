import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import sys

# Quyền truy cập: drive.file để upload, quản lý file do app tạo
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_resource_path(relative_path):
    """Lấy đường dẫn tài nguyên, tương thích với PyInstaller"""
    try:
        # PyInstaller tạo thư mục tạm _MEIPASS
        base_path = os.path.dirname(sys.executable)
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_working_directory():
    """Lấy thư mục làm việc hiện tại (nơi lưu token.json)"""
    if getattr(sys, 'frozen', False):
        # Nếu chạy từ .exe, lấy thư mục chứa .exe
        return os.path.dirname(sys.executable)
    else:
        # Nếu chạy Python script bình thường
        return os.path.abspath(".")

# File credentials nằm trong resources (đóng gói với app)
CLIENT_SECRET_FILE = get_resource_path(os.path.join('resources', 'client_secret.json'))

# Token lưu ở thư mục làm việc (bên ngoài app)
TOKEN_FILE = os.path.join(get_working_directory(), 'token.json')

def authenticate_google_drive():
    """Xử lý xác thực và tạo token."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"❌ Lỗi: Không tìm thấy file credentials tại {CLIENT_SECRET_FILE}")
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    return creds

def create_subfolder(folder_name, parent_id):
    """
    Tạo một thư mục con trên Drive.
    Returns: folder_id hoặc None nếu lỗi
    """
    creds = authenticate_google_drive()
    if not creds: return None

    try:
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        
        file = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = file.get('id')
        print(f"📂 Đã tạo folder mới: '{folder_name}' (ID: {folder_id})")
        return folder_id
    except Exception as e:
        print(f"❌ Lỗi tạo folder Drive: {e}")
        return None

def upload_image_and_get_link(file_path, folder_id=None):
    """
    Upload ảnh lên Drive, set quyền công khai và trả về Link xem ảnh.
    Returns: tuple (webViewLink, fileName) hoặc (None, None) nếu lỗi.
    """
    creds = authenticate_google_drive()
    if not creds: return None, None

    try:
        service = build('drive', 'v3', credentials=creds)
        file_name = os.path.basename(file_path)
        
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype='image/png', resumable=True)

        # 1. Upload File
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()
        
        file_id = file.get('id')
        web_view_link = file.get('webViewLink')

        # 2. Set quyền truy cập (Permission) -> Anyone with link can view
        permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        service.permissions().create(
            fileId=file_id,
            body=permission,
            fields='id',
        ).execute()

        print(f"✅ Upload thành công: {file_name} -> ID: {file_id}")
        return web_view_link

    except HttpError as error:
        print(f"❌ Lỗi Drive API: {error}")
        return None
    except Exception as e:
        print(f"❌ Lỗi Upload: {e}")
        return None

if __name__ == '__main__':
    # Test upload
    TEST_FILE = r'test_image.png'
    TEST_FOLDER_ID = '15nuXv7cUkWLnyUp3TpVOIQSg3qvBGjo8' 
    
    # Tạo file giả nếu chưa có
    if not os.path.exists(TEST_FILE):
        with open(TEST_FILE, 'w') as f: f.write("dummy image content")

    link, name = upload_image_and_get_link(TEST_FILE, TEST_FOLDER_ID)
    print(f"Link ảnh: {link}")
    print(f"Tên file: {name}")
    
    # Xóa file test
    if os.path.exists(TEST_FILE): os.remove(TEST_FILE)