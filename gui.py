import sys
import os
import traceback
from dotenv import load_dotenv

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QPlainTextEdit, QFileDialog, QMessageBox,
    QTabWidget, QRadioButton, QButtonGroup, QGroupBox # <-- Thêm QRadioButton, QButtonGroup, QGroupBox

)
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QFont
from processor import run_full_pipeline
from image_generator import process_excel_file
from merge_image import ImageMerger
import pandas as pd # Cần cài: pip install pandas openpyxl
import requests     # Cần cài: pip install requests
from services.chinese_tts import (
    init_google_tts_client, 
    get_sheets_with_hsk, 
    processing_sheet, 
    text_to_speech_google
)
# Giả sử các module này đã có sẵn trong project của bạn
from services.CompressPDF import compress_pdf_ghostscript 
from services.response2docx import response2docx
from services.process import ProcessingThread
from google.oauth2 import service_account

# Lớp để chuyển hướng stdout sang GUI
class StreamRedirector(QObject):
    stringWritten = pyqtSignal(str)

    def write(self, text):
        self.stringWritten.emit(str(text))

    def flush(self):
        pass

# Lớp Worker để chạy pipeline trong một luồng riêng
class PipelineWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pdf_folder, hsk_level):
        super().__init__()
        self.pdf_folder = pdf_folder
        self.hsk_level = hsk_level

    def run(self):
        try:
            result_path = run_full_pipeline(self.pdf_folder, self.hsk_level)
            if result_path:
                self.finished.emit(result_path)
            else:
                self.error.emit("Pipeline đã chạy xong nhưng không trả về kết quả thành công. Vui lòng kiểm tra log.")
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

# Lớp Worker để tạo ảnh trong một luồng riêng
class ImageGeneratorWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, excel_path):
        super().__init__()
        self.excel_path = excel_path

    def run(self):
        try:
            result_path = process_excel_file(self.excel_path)
            if result_path:
                self.finished.emit(result_path)
            else:
                self.error.emit("Quá trình tạo ảnh không thành công. Vui lòng kiểm tra log.")
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

# Lớp Worker để ghép ảnh trong một luồng riêng
class ImageMergerWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, excel_path, images_folder, output_folder="IMAGES_MERGED"):
        super().__init__()
        self.excel_path = excel_path
        self.images_folder = images_folder
        self.output_folder = output_folder
        
    def run(self):
        try:
            merger = ImageMerger(self.excel_path, self.images_folder, self.output_folder)
            merger.process_all()
            result_path = os.path.abspath(self.output_folder)
            self.finished.emit(result_path)
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

class ChineseTTSWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str) # Tín hiệu để cập nhật log

    def __init__(self, excel_path, output_folder):
        super().__init__()
        self.excel_path = excel_path
        self.output_folder = output_folder

    def run(self):
        try:
            self.progress.emit("🔄 Đang khởi tạo Google TTS Client...")
            # Kiểm tra biến môi trường trước
            load_dotenv()
            if not os.getenv("PROJECT_ID"):
                raise ValueError("Thiếu cấu hình Google Cloud trong file .env")

            client = init_google_tts_client()
            self.progress.emit("✅ Client đã sẵn sàng.")
            
            # Lấy danh sách sheet
            hsk_sheets = get_sheets_with_hsk(self.excel_path)
            if isinstance(hsk_sheets, str): 
                raise ValueError(hsk_sheets)
            
            if not hsk_sheets:
                raise ValueError("Không tìm thấy sheet nào chứa từ 'HSK'.")

            total_files_created = 0
            
            for sheetname in hsk_sheets:
                self.progress.emit(f"\n📂 Đang xử lý sheet: {sheetname}...")
                
                # Tạo thư mục output riêng cho sheet
                sheet_out_dir = os.path.join(self.output_folder, sheetname)
                os.makedirs(sheet_out_dir, exist_ok=True)
                
                # Gọi hàm xử lý sheet từ service
                try:
                    stt_arr, vocab_arr, ex_arr, lesson_arr = processing_sheet(self.excel_path, sheetname)
                except Exception as e:
                    self.progress.emit(f"❌ Lỗi đọc sheet {sheetname}: {e}")
                    continue
                
                # Loop tạo audio Từ vựng
                for i, text in enumerate(vocab_arr):
                    if text:
                        filename = f"B{lesson_arr[i]}_{stt_arr[i]}.mp3"
                        out_path = os.path.join(sheet_out_dir, filename)
                        self.progress.emit(f"   -> Tạo audio từ: {text}")
                        text_to_speech_google(client, text, out_path)
                        total_files_created += 1

                # Loop tạo audio Ví dụ
                if ex_arr:
                    for i, text in enumerate(ex_arr):
                         if text and isinstance(text, str) and text.strip():
                            filename = f"B{lesson_arr[i]}_VD_{stt_arr[i]}.mp3"
                            out_path = os.path.join(sheet_out_dir, filename)
                            self.progress.emit(f"   -> Tạo audio ví dụ: {stt_arr[i]}")
                            text_to_speech_google(client, text, out_path)
                            total_files_created += 1

            self.finished.emit(f"Hoàn thành! Đã tạo {total_files_created} file tại:\n{self.output_folder}")

        except Exception as e:
            error_details = traceback.format_exc()
            self.error.emit(f"{str(e)}\n\nChi tiết:\n{error_details}")

# --- WORKER CHO KOREAN TTS ---

KOREAN_VOICES_DATA = {
    "In-Guk (Nam)": {
        "id": "in-guk", 
        "sample_path": "resources/samples/in-guk.mp3"
    },
    "Ji-Yeon (Nữ)": {
        "id": "ji-yeon", 
        "sample_path": "resources/samples/ji-yeon.mp3"
    },
    "Jae-Hyun (Nam)": {
        "id": "jae-hyun", 
        "sample_path": "resources/samples/jae-hyun.mp3"
    },
    "Yoo-Jung (Nữ)": {
        "id": "yoo-jung", 
        "sample_path": "resources/samples/yoo-jung.mp3"
    }
}
class KoreanTTSWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, excel_path, output_folder, voice_id):
        super().__init__()
        self.excel_path = excel_path
        self.output_folder = output_folder
        # Key từ code của bạn
        self.apikey = 'QXGh0KOTHI7CaR9Vdh61M77FPRV98ZBMdNALHcsd' 
        self.voice = voice_id
        self.url = f'https://api.narakeet.com/text-to-speech/mp3?voice={self.voice}'

    def run(self):
        try:
            self.progress.emit(f"🔄 Khởi tạo với giọng đọc: {self.voice}...")
            self.progress.emit("🔄 Đang đọc file Excel...")
            xl = pd.ExcelFile(self.excel_path)
            # Logic lọc sheet có dấu gạch ngang từ code gốc
            target_sheets = [s for s in xl.sheet_names if '-' in s]
            
            if not target_sheets:
                self.progress.emit("⚠️ Không tìm thấy sheet nào có chứa dấu gạch ngang '-' trong tên.")
                # Nếu không tìm thấy sheet có dấu gạch ngang, thử lấy tất cả sheet
                target_sheets = xl.sheet_names

            self.progress.emit(f"Tìm thấy {len(target_sheets)} sheet cần xử lý.")
            total_files = 0
            
            for sheet_name in target_sheets:
                self.progress.emit(f"\n📂 Đang xử lý sheet: {sheet_name}")
                
                # Logic đọc data
                df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=0)
                
                # Check cột bắt buộc
                required = ["STT", "Ví dụ", "Tên chủ đề"]
                missing = [col for col in required if col not in df.columns]
                if missing:
                    self.progress.emit(f"⚠️ Bỏ qua sheet {sheet_name} do thiếu cột: {missing}")
                    continue

                # Tạo folder output
                sheet_out_dir = os.path.join(self.output_folder, sheet_name)
                os.makedirs(sheet_out_dir, exist_ok=True)

                # Loop và gọi API
                for idx, row in df.iterrows():
                    if pd.isna(row["Ví dụ"]): continue
                    
                    text = str(row["Ví dụ"])
                    stt = row["STT"]
                    topic = str(row["Tên chủ đề"]).strip()
                    
                    filename = f"{stt}_{topic}.mp3"
                    # Xử lý ký tự đặc biệt trong tên file
                    filename = "".join([c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
                    filepath = os.path.join(sheet_out_dir, filename)
                    
                    self.progress.emit(f"   -> Tải audio: {filename}")
                    
                    # Gọi API Narakeet
                    options = {
                        'headers': {
                            'Accept': 'application/octet-stream',
                            'Content-Type': 'text/plain',
                            'x-api-key': self.apikey,
                        },
                        'data': text.encode('utf8')
                    }
                    response = requests.post(self.url, **options)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        total_files += 1
                    else:
                        self.progress.emit(f"❌ Lỗi API (Code {response.status_code}) với text: {text[:20]}...")

            self.finished.emit(f"Hoàn thành! Đã tạo {total_files} file audio tiếng Hàn tại:\n{self.output_folder}")

        except Exception as e:
            error_details = traceback.format_exc()
            self.error.emit(f"{str(e)}\n\nChi tiết:\n{error_details}")

class SummaryWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, pdf_path, prompt_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.prompt_path = prompt_path
        self.project_id = "onluyen-media" # Hardcode từ code cũ
        # Credentials từ code cũ
        self.creds = self._setup_credentials()

    def _setup_credentials(self):
        """Thiết lập credentials từ service account"""
        try:
            service_account_data = {
                "type": os.getenv("TYPE"),
                "project_id": os.getenv("PROJECT_ID"),
                "private_key_id": os.getenv("PRIVATE_KEY_ID"),
                "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n') if os.getenv("PRIVATE_KEY") else None,
                "client_email": os.getenv("CLIENT_EMAIL"),
                "client_id": os.getenv("CLIENT_ID", ""),
                "auth_uri": os.getenv("AUTH_URI"),
                "token_uri": os.getenv("TOKEN_URI"),
                "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
                "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
                "universe_domain": os.getenv("UNIVERSE_DOMAIN")
            }
            
            self.credentials = service_account.Credentials.from_service_account_info(
                service_account_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
        except Exception as e:
            print(f"Lỗi khi tạo credentials từ service account: {e}")
            self.credentials = None

    def run(self):
        try:
            os.makedirs("output", exist_ok=True)
            
            # Đọc prompt
            if not os.path.exists(self.prompt_path):
                raise FileNotFoundError("Không tìm thấy file prompt.")
                
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()

            file_name = os.path.splitext(os.path.basename(self.pdf_path))[0]

            # Bước 1: Nén PDF
            self.progress.emit(f"🔄 Đang nén PDF: {file_name}...")
            # tạo thư mục summary trong output nếu chưa có
            os.makedirs("output/summary", exist_ok=True)
            compressed_pdf_path = f"output/summary/{file_name}_compressed.pdf"
            
            # Gọi hàm nén từ module CompressPDF
            compress_pdf_ghostscript(self.pdf_path, compressed_pdf_path, 'ebook')
            
            if not os.path.exists(compressed_pdf_path):
                raise Exception("Nén PDF thất bại.")

            # Bước 2: Gọi AI tạo DOCX
            self.progress.emit(f"🤖 Đang gửi yêu cầu tóm tắt tới Gemini...")
            docx_path = f"output/summary/{file_name}.docx"
            
            # Gọi hàm response2docx
            response2docx(
                compressed_pdf_path, 
                prompt_content, 
                file_name, 
                self.project_id, 
                self.creds, 
                "gemini-2.5-pro"
            )
            
            self.finished.emit(f"Hoàn tất! File lưu tại:\n{os.path.abspath(docx_path)}")

        except Exception as e:
            self.error.emit(str(e))        

# Lớp Giao diện chính với Tab
class HSKGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()

        # Khởi tạo Media Player
        self.media_player = QMediaPlayer()

        self.initUI()
        self.redirect_stdout()
        self.setup_styles()

    def initUI(self):
        self.setWindowTitle('Tool sinh câu hỏi và ảnh AI cho HSK/TOPIK')
        self.setGeometry(200, 200, 900, 700)

        # Layout chính
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Tạo TabWidget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Pipeline HSK
        self.pipeline_tab = self.create_pipeline_tab()
        self.tab_widget.addTab(self.pipeline_tab, "HSK/TOPIK")
        
        # Tab 2: Tạo ảnh
        self.image_tab = self.create_image_tab()
        self.tab_widget.addTab(self.image_tab, "Tạo ảnh AI")

        # Tab 3: Ghép ảnh
        self.merge_tab = self.create_merge_tab()
        self.tab_widget.addTab(self.merge_tab, "Ghép ảnh AI")

        # --- THÊM TAB TTS MỚI Ở ĐÂY ---
        self.tts_tab = self.create_tts_tab()
        self.tab_widget.addTab(self.tts_tab, "TTS")

        self.summary_tab = self.create_summary_tab()
        self.tab_widget.addTab(self.summary_tab, "Tóm tắt HSK")

        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)

    def setup_styles(self):
        """Thiết lập style chung cho ứng dụng"""
        # Font chính cho toàn bộ ứng dụng
        font = QFont("Arial", 11)
        self.setFont(font)
        
        # Style cho toàn bộ ứng dụng
        app_style = """
        QWidget {
            background-color: #f5f5f5;
            color: #333333;
            font-size: 11pt;
        }
        
        QTabWidget::pane {
            border: 2px solid #c0c0c0;
            border-radius: 10px;
            background-color: white;
        }
        
        QTabWidget::tab-bar {
            left: 5px;
        }
        
        QTabBar::tab {
            background-color: #e1e1e1;
            color: #333333;
            border: 2px solid #c0c0c0;
            border-bottom-color: #C2C7CB;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            min-width: 120px;
            padding: 10px 20px;
            font-size: 12pt;
            font-weight: bold;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-color: #0078d4;
            border-bottom-color: white;
            color: #0078d4;
        }
        
        QTabBar::tab:hover {
            background-color: #f0f0f0;
        }
        
        QLabel {
            color: #333333;
            font-size: 12pt;
            font-weight: bold;
        }
        
        QLineEdit {
            padding: 8px 12px;
            border: 2px solid #cccccc;
            border-radius: 8px;
            background-color: white;
            font-size: 11pt;
            min-height: 20px;
        }
        
        QLineEdit:focus {
            border-color: #0078d4;
        }
        
        QComboBox {
            padding: 8px 12px;
            border: 2px solid #cccccc;
            border-radius: 8px;
            background-color: white;
            font-size: 11pt;
            min-height: 20px;
        }
        
        QComboBox:focus {
            border-color: #0078d4;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 1px;
            border-left-color: #cccccc;
            border-left-style: solid;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }
        
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 12pt;
            font-weight: bold;
            min-height: 25px;
        }
        
        QPushButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton:pressed {
            background-color: #005a9e;
        }
        
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        
        QPlainTextEdit {
            background-color: #fafafa;
            color: #333333;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10pt;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 10px;
        }
        """
        
        self.setStyleSheet(app_style)

    def create_pipeline_tab(self):
        """Tạo tab cho HSK Pipeline (chức năng cũ)."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn thư mục
        path_layout = QHBoxLayout()
        path_layout.setSpacing(15)
        self.path_label = QLabel('Thư mục PDF:')
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Chọn thư mục chứa các file PDF bài khóa...")
        self.browse_button = QPushButton('Duyệt...')
        self.browse_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_button.clicked.connect(self._browse_folder)
        path_layout.addWidget(self.path_label, 0)
        path_layout.addWidget(self.path_input, 1)
        path_layout.addWidget(self.browse_button, 0)
        layout.addLayout(path_layout)

        # 2. Phần chọn HSK Level
        hsk_layout = QHBoxLayout()
        hsk_layout.setSpacing(15)
        self.hsk_label = QLabel('Cấp độ HSK/TOPIK:')
        self.hsk_combo = QComboBox()
        self.hsk_combo.addItems([f'hsk{i}' for i in range(1, 6)] + [f'topik{i}' for i in range(1, 4)])
        self.hsk_combo.setMinimumWidth(150)
        hsk_layout.addWidget(self.hsk_label, 0)
        hsk_layout.addWidget(self.hsk_combo, 0)
        hsk_layout.addStretch(1)
        layout.addLayout(hsk_layout)
        
        # 3. Nút chạy
        self.run_button = QPushButton('🚀 Bắt đầu chạy')
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.run_button.clicked.connect(self._start_pipeline)
        layout.addWidget(self.run_button)

        # 4. Khung hiển thị log
        log_label = QLabel('📋 Nhật ký hoạt động:')
        layout.addWidget(log_label)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        tab.setLayout(layout)
        return tab

    def create_image_tab(self):
        """Tạo tab cho chức năng tạo ảnh AI."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn file Excel
        excel_layout = QHBoxLayout()
        excel_layout.setSpacing(15)
        self.excel_label = QLabel('File Excel:')
        self.excel_input = QLineEdit()
        self.excel_input.setPlaceholderText("Chọn file Excel chứa dữ liệu...")
        self.browse_excel_button = QPushButton('Duyệt...')
        self.browse_excel_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_excel_button.clicked.connect(self._browse_excel_file)
        excel_layout.addWidget(self.excel_label, 0)
        excel_layout.addWidget(self.excel_input, 1)
        excel_layout.addWidget(self.browse_excel_button, 0)
        layout.addLayout(excel_layout)

        # 2. Nút tạo ảnh
        self.generate_button = QPushButton('🎨 Bắt đầu tạo ảnh AI')
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.generate_button.clicked.connect(self._start_image_generation)
        layout.addWidget(self.generate_button)

        # 3. Khung hiển thị log cho tab ảnh
        image_log_label = QLabel('📋 Nhật ký tạo ảnh:')
        layout.addWidget(image_log_label)
        
        self.image_log_display = QPlainTextEdit()
        self.image_log_display.setReadOnly(True)
        layout.addWidget(self.image_log_display)

        tab.setLayout(layout)
        return tab

    def create_merge_tab(self):
        """Tạo tab cho chức năng ghép ảnh AI."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn file Excel
        excel_merge_layout = QHBoxLayout()
        excel_merge_layout.setSpacing(15)
        self.excel_merge_label = QLabel('File Excel:')
        self.excel_merge_input = QLineEdit()
        self.excel_merge_input.setPlaceholderText("Chọn file Excel chứa thông tin ghép...")
        self.browse_excel_merge_button = QPushButton('Duyệt...')
        self.browse_excel_merge_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_excel_merge_button.clicked.connect(self._browse_excel_merge_file)
        excel_merge_layout.addWidget(self.excel_merge_label, 0)
        excel_merge_layout.addWidget(self.excel_merge_input, 1)
        excel_merge_layout.addWidget(self.browse_excel_merge_button, 0)
        layout.addLayout(excel_merge_layout)

        # 2. Phần chọn thư mục ảnh
        images_layout = QHBoxLayout()
        images_layout.setSpacing(15)
        self.images_label = QLabel('Thư mục ảnh:')
        self.images_input = QLineEdit()
        self.images_input.setPlaceholderText("Chọn thư mục chứa ảnh cần ghép...")
        self.browse_images_button = QPushButton('Duyệt...')
        self.browse_images_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_images_button.clicked.connect(self._browse_images_folder)
        images_layout.addWidget(self.images_label, 0)
        images_layout.addWidget(self.images_input, 1)
        images_layout.addWidget(self.browse_images_button, 0)
        layout.addLayout(images_layout)

        # 3. Nút ghép ảnh
        self.merge_button = QPushButton('🔄 Bắt đầu ghép ảnh AI')
        self.merge_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.merge_button.clicked.connect(self._start_image_merge)
        layout.addWidget(self.merge_button)

        # 4. Khung hiển thị log cho tab ghép ảnh
        merge_log_label = QLabel('📋 Nhật ký ghép ảnh:')
        layout.addWidget(merge_log_label)
        
        self.merge_log_display = QPlainTextEdit()
        self.merge_log_display.setReadOnly(True)
        layout.addWidget(self.merge_log_display)

        tab.setLayout(layout)
        return tab

    def create_tts_tab(self):
        """Tạo tab cho chức năng Text to Speech (Chinese/Korean)."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Chọn File Excel
        excel_layout = QHBoxLayout()
        self.tts_excel_label = QLabel('File Excel:')
        self.tts_excel_input = QLineEdit()
        self.tts_excel_input.setPlaceholderText("Chọn file Excel chứa từ vựng/câu...")
        self.tts_browse_excel_btn = QPushButton('Duyệt...')
        self.tts_browse_excel_btn.setStyleSheet("background-color: #28a745;")
        self.tts_browse_excel_btn.clicked.connect(self._browse_tts_excel)
        
        excel_layout.addWidget(self.tts_excel_label)
        excel_layout.addWidget(self.tts_excel_input)
        excel_layout.addWidget(self.tts_browse_excel_btn)
        layout.addLayout(excel_layout)

        # 2. Chọn Folder Output
        output_layout = QHBoxLayout()
        self.tts_output_label = QLabel('Thư mục Output:')
        self.tts_output_input = QLineEdit()
        self.tts_output_input.setText(os.path.join(os.getcwd(), "output", "audio")) 
        self.tts_browse_output_btn = QPushButton('Duyệt...')
        self.tts_browse_output_btn.setStyleSheet("background-color: #28a745;")
        self.tts_browse_output_btn.clicked.connect(self._browse_tts_output)

        output_layout.addWidget(self.tts_output_label)
        output_layout.addWidget(self.tts_output_input)
        output_layout.addWidget(self.tts_browse_output_btn)
        layout.addLayout(output_layout)

        # 3. Chọn Ngôn ngữ & Cấu hình giọng đọc
        lang_group_box = QGroupBox("Cấu hình Ngôn ngữ")
        lang_main_layout = QVBoxLayout() # Đổi thành QVBoxLayout để xếp dọc các tùy chọn

        # --- Dòng chọn ngôn ngữ ---
        radio_layout = QHBoxLayout()
        self.rb_chinese = QRadioButton("Tiếng Trung (Google TTS)")
        self.rb_chinese.setChecked(True)
        self.rb_korean = QRadioButton("Tiếng Hàn (Narakeet)")
        
        self.rb_chinese.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self.rb_korean.setStyleSheet("font-size: 11pt; font-weight: bold;")

        self.lang_btn_group = QButtonGroup()
        self.lang_btn_group.addButton(self.rb_chinese)
        self.lang_btn_group.addButton(self.rb_korean)

        radio_layout.addWidget(self.rb_chinese)
        radio_layout.addWidget(self.rb_korean)
        radio_layout.addStretch()
        lang_main_layout.addLayout(radio_layout)

        # --- Dòng chọn giọng đọc Tiếng Hàn (Mặc định ẩn) ---
        self.korean_options_widget = QWidget()
        korean_opts_layout = QHBoxLayout(self.korean_options_widget)
        korean_opts_layout.setContentsMargins(20, 0, 0, 0) # Thụt vào một chút

        lbl_voice = QLabel("Chọn giọng đọc:")
        self.combo_korean_voice = QComboBox()
        self.combo_korean_voice.addItems(list(KOREAN_VOICES_DATA.keys()))
        self.combo_korean_voice.setMinimumWidth(200)

        self.btn_preview_voice = QPushButton("▶ Nghe thử")
        self.btn_preview_voice.setStyleSheet("background-color: #17a2b8; padding: 5px 15px;")
        self.btn_preview_voice.clicked.connect(self._play_voice_sample)

        korean_opts_layout.addWidget(lbl_voice)
        korean_opts_layout.addWidget(self.combo_korean_voice)
        korean_opts_layout.addWidget(self.btn_preview_voice)
        korean_opts_layout.addStretch()

        lang_main_layout.addWidget(self.korean_options_widget)
        lang_group_box.setLayout(lang_main_layout)
        layout.addWidget(lang_group_box)

        # Logic ẩn hiện vùng chọn giọng đọc
        self.korean_options_widget.setVisible(False) # Mặc định ẩn vì Tiếng Trung được chọn
        self.rb_chinese.toggled.connect(self._toggle_korean_options)
        self.rb_korean.toggled.connect(self._toggle_korean_options)

        # 4. Nút chạy
        self.tts_run_button = QPushButton('🔊 Bắt đầu tạo Audio')
        self.tts_run_button.setStyleSheet("""
            QPushButton {
                background-color: #673AB7;
                color: white;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #5E35B1;
            }
        """)
        self.tts_run_button.clicked.connect(self._start_tts)
        layout.addWidget(self.tts_run_button)

        # 5. Log area
        log_label = QLabel('📋 Nhật ký TTS:')
        layout.addWidget(log_label)
        
        self.tts_log_display = QPlainTextEdit()
        self.tts_log_display.setReadOnly(True)
        layout.addWidget(self.tts_log_display)

        tab.setLayout(layout)
        return tab

    def create_summary_tab(self):
        """Tạo tab cho chức năng Tóm tắt Tiếng Trung."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Chọn PDF
        pdf_layout = QHBoxLayout()
        self.sum_pdf_label = QLabel('File PDF:')
        self.sum_pdf_input = QLineEdit()
        self.sum_pdf_input.setPlaceholderText("Chọn file bài khóa PDF...")
        self.sum_browse_pdf_btn = QPushButton('Duyệt...')
        self.sum_browse_pdf_btn.setStyleSheet("background-color: #28a745;")
        self.sum_browse_pdf_btn.clicked.connect(self._browse_sum_pdf)
        
        pdf_layout.addWidget(self.sum_pdf_label)
        pdf_layout.addWidget(self.sum_pdf_input)
        pdf_layout.addWidget(self.sum_browse_pdf_btn)
        layout.addLayout(pdf_layout)

        # 2. Chọn Prompt
        prompt_layout = QHBoxLayout()
        self.sum_prompt_label = QLabel('File Prompt:')
        self.sum_prompt_input = QLineEdit()
        # đặt file prompt mặc định là prompt_summary.txt trong thư mục resources
        default_prompt_path = os.path.join(os.getcwd(), "resources", "prompts", "prompt_summary.txt")
        self.sum_prompt_input.setText(default_prompt_path)
        self.sum_browse_prompt_btn = QPushButton('Duyệt...')
        self.sum_browse_prompt_btn.setStyleSheet("background-color: #17a2b8;")
        self.sum_browse_prompt_btn.clicked.connect(self._browse_sum_prompt)

        prompt_layout.addWidget(self.sum_prompt_label)
        prompt_layout.addWidget(self.sum_prompt_input)
        prompt_layout.addWidget(self.sum_browse_prompt_btn)
        layout.addLayout(prompt_layout)

        # 3. Nút chạy
        self.sum_run_button = QPushButton('📝 Bắt đầu Tóm tắt')
        self.sum_run_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.sum_run_button.clicked.connect(self._start_summary)
        layout.addWidget(self.sum_run_button)

        # 4. Log area
        log_label = QLabel('📋 Nhật ký Tóm tắt:')
        layout.addWidget(log_label)
        
        self.sum_log_display = QPlainTextEdit()
        self.sum_log_display.setReadOnly(True)
        layout.addWidget(self.sum_log_display)

        tab.setLayout(layout)
        return tab


    def redirect_stdout(self):
        """Chuyển hướng tất cả output từ print() vào khung log."""
        self.stream_redirector = StreamRedirector()
        self.stream_redirector.stringWritten.connect(self._update_log)
        sys.stdout = self.stream_redirector

    def _update_log(self, text):
        """Cập nhật văn bản vào khung log hiện tại và tự động cuộn xuống."""
        current_tab_index = self.tab_widget.currentIndex()
        idx = self.tab_widget.currentIndex()
        if current_tab_index == 0:  # Tab Pipeline
            self.log_display.insertPlainText(text)
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        elif current_tab_index == 1:  # Tab Image
            self.image_log_display.insertPlainText(text)
            self.image_log_display.verticalScrollBar().setValue(self.image_log_display.verticalScrollBar().maximum())
        elif current_tab_index == 2:  # Tab Merge
            self.merge_log_display.insertPlainText(text)
            self.merge_log_display.verticalScrollBar().setValue(self.merge_log_display.verticalScrollBar().maximum())
        elif current_tab_index == 3:  # Tab TTS (Index là 3 vì thêm sau cùng)
            self.tts_log_display.insertPlainText(text)
            self.tts_log_display.verticalScrollBar().setValue(self.tts_log_display.verticalScrollBar().maximum())
        if idx == 4: # Tab Summary (Index 4)
             self.sum_log_display.insertPlainText(text)       

    def _browse_folder(self):
        """Mở dialog để chọn thư mục."""
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa file PDF')
        if folder_path:
            self.path_input.setText(folder_path)

    def _browse_excel_file(self):
        """Mở dialog để chọn file Excel."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Chọn file Excel', 
            '', 
            'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.excel_input.setText(file_path)

    def _browse_excel_merge_file(self):
        """Mở dialog để chọn file Excel cho ghép ảnh."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Chọn file Excel cho ghép ảnh', 
            '', 
            'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.excel_merge_input.setText(file_path)

    def _browse_images_folder(self):
        """Mở dialog để chọn thư mục ảnh."""
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa ảnh cần ghép')
        if folder_path:
            self.images_input.setText(folder_path)

    def _start_pipeline(self):
        """Bắt đầu chạy pipeline trong một luồng riêng."""
        pdf_folder = self.path_input.text()
        hsk_level = self.hsk_combo.currentText()

        if not pdf_folder or not os.path.isdir(pdf_folder):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một thư mục PDF hợp lệ.')
            return

        # Vô hiệu hóa nút chạy và xóa log cũ
        self.run_button.setEnabled(False)
        self.run_button.setText('⏳ Đang xử lý...')
        self.log_display.clear()
        
        # Tạo và khởi chạy thread
        self.thread = QThread()
        self.worker = PipelineWorker(pdf_folder, hsk_level)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._pipeline_finished)
        self.worker.error.connect(self._pipeline_error)

        # Dọn dẹp sau khi thread kết thúc
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)

        # 2. Dọn dẹp khi CÓ LỖI (Quan trọng - Thêm đoạn này)
        self.worker.error.connect(self.thread.quit)     # <--- Dừng luồng ngay cả khi lỗi
        self.worker.error.connect(self.worker.deleteLater) # <--- Xóa worker khi lỗi

        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _start_image_generation(self):
        """Bắt đầu tạo ảnh trong một luồng riêng."""
        excel_path = self.excel_input.text()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một file Excel hợp lệ.')
            return

        # Load .env file
        load_dotenv()

        # Kiểm tra credentials
        if not os.getenv("PROJECT_ID"):
            QMessageBox.warning(self, 'Lỗi cấu hình', 'Không tìm thấy thông tin credentials trong file .env.')
            return

        # Vô hiệu hóa nút tạo ảnh và xóa log cũ
        self.generate_button.setEnabled(False)
        self.generate_button.setText('⏳ Đang tạo ảnh...')
        self.image_log_display.clear()
        
        # Tạo và khởi chạy thread
        self.image_thread = QThread()
        self.image_worker = ImageGeneratorWorker(excel_path)
        self.image_worker.moveToThread(self.image_thread)

        self.image_thread.started.connect(self.image_worker.run)
        self.image_worker.finished.connect(self._image_generation_finished)
        self.image_worker.error.connect(self._image_generation_error)

        # Dọn dẹp sau khi thread kết thúc
        self.image_worker.error.connect(self.image_thread.quit)      # Thêm
        self.image_worker.error.connect(self.image_worker.deleteLater) # Thêm
        self.image_worker.finished.connect(self.image_thread.quit)
        self.image_worker.finished.connect(self.image_worker.deleteLater)
        self.image_thread.finished.connect(self.image_thread.deleteLater)

        self.image_thread.start()

    def _start_image_merge(self):
        """Bắt đầu ghép ảnh trong một luồng riêng."""
        excel_path = self.excel_merge_input.text()
        images_folder = self.images_input.text()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một file Excel hợp lệ.')
            return

        if not images_folder or not os.path.isdir(images_folder):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một thư mục ảnh hợp lệ.')
            return

        # Vô hiệu hóa nút ghép ảnh và xóa log cũ
        self.merge_button.setEnabled(False)
        self.merge_button.setText('⏳ Đang ghép ảnh...')
        self.merge_log_display.clear()
        
        # Tạo và khởi chạy thread
        self.merge_thread = QThread()
        self.merge_worker = ImageMergerWorker(excel_path, images_folder)
        self.merge_worker.moveToThread(self.merge_thread)

        self.merge_thread.started.connect(self.merge_worker.run)
        self.merge_worker.finished.connect(self._image_merge_finished)
        self.merge_worker.error.connect(self._image_merge_error)

        # Dọn dẹp sau khi thread kết thúc
        self.merge_worker.error.connect(self.merge_thread.quit)      # Thêm
        self.merge_worker.error.connect(self.merge_worker.deleteLater) # Thêm
        self.merge_worker.finished.connect(self.merge_thread.quit)
        self.merge_worker.finished.connect(self.merge_worker.deleteLater)
        self.merge_thread.finished.connect(self.merge_thread.deleteLater)

        self.merge_thread.start()

    def _browse_tts_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Chọn file Excel từ vựng', '', 'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.tts_excel_input.setText(file_path)

    def _browse_tts_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu Audio')
        if folder_path:
            self.tts_output_input.setText(folder_path)

    def _toggle_korean_options(self):
        """Ẩn/Hiện phần chọn giọng đọc tiếng Hàn."""
        is_korean = self.rb_korean.isChecked()
        self.korean_options_widget.setVisible(is_korean)

    def _play_voice_sample(self):
        """Phát file mẫu của giọng đang chọn."""
        # 1. Lấy tên hiển thị đang chọn trong ComboBox
        selected_display_name = self.combo_korean_voice.currentText()
        
        # 2. Lấy đường dẫn file từ Dictionary
        voice_data = KOREAN_VOICES_DATA.get(selected_display_name)
        if not voice_data:
            return

        sample_path = voice_data["sample_path"]
        
        # 3. Kiểm tra file có tồn tại không
        if not os.path.exists(sample_path):
            QMessageBox.warning(self, "Lỗi file", f"Không tìm thấy file mẫu tại:\n{sample_path}")
            return

        # 4. Phát âm thanh
        try:
            full_path = os.path.abspath(sample_path)
            content = QMediaContent(QUrl.fromLocalFile(full_path))
            self.media_player.setMedia(content)
            self.media_player.play()
            self.tts_log_display.appendPlainText(f"🎵 Đang phát mẫu giọng: {selected_display_name}")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi Audio", f"Không thể phát file: {e}")

    def _start_tts(self):
        excel_path = self.tts_excel_input.text()
        output_folder = self.tts_output_input.text()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi', 'Vui lòng chọn file Excel hợp lệ.')
            return
        
        if not output_folder:
            QMessageBox.warning(self, 'Lỗi', 'Vui lòng chọn thư mục Output.')
            return

        # Disable nút
        self.tts_run_button.setEnabled(False)
        self.tts_run_button.setText('⏳ Đang xử lý...')
        self.tts_log_display.clear()

        # Tạo Thread
        self.tts_thread = QThread()
        
        # Chọn Worker
        if self.rb_chinese.isChecked():
            self.tts_log_display.appendPlainText(">> Đã chọn chế độ: Tiếng Trung (Google TTS)")
            self.tts_worker = ChineseTTSWorker(excel_path, output_folder)
        else:
            # Lấy voice ID từ ComboBox
            selected_display_name = self.combo_korean_voice.currentText()
            voice_id = KOREAN_VOICES_DATA[selected_display_name]["id"]
            
            self.tts_log_display.appendPlainText(f">> Đã chọn chế độ: Tiếng Hàn (Narakeet) - Giọng: {selected_display_name}")
            
            # Truyền voice_id vào Worker
            self.tts_worker = KoreanTTSWorker(excel_path, output_folder, voice_id=voice_id)

        self.tts_worker.moveToThread(self.tts_thread)

        # Kết nối tín hiệu (Giữ nguyên)
        self.tts_thread.started.connect(self.tts_worker.run)
        self.tts_worker.finished.connect(self._tts_finished)
        self.tts_worker.error.connect(self._tts_error)
        self.tts_worker.progress.connect(self._tts_progress)

        # Dọn dẹp (Giữ nguyên)
        self.tts_worker.error.connect(self.tts_thread.quit)
        self.tts_worker.error.connect(self.tts_worker.deleteLater)
        self.tts_worker.finished.connect(self.tts_thread.quit)
        self.tts_worker.finished.connect(self.tts_worker.deleteLater)
        self.tts_thread.finished.connect(self.tts_thread.deleteLater)

        self.tts_thread.start()


    def _tts_progress(self, message):
        """Hàm nhận signal progress từ worker và ghi vào log"""
        self.tts_log_display.appendPlainText(message)
        self.tts_log_display.verticalScrollBar().setValue(self.tts_log_display.verticalScrollBar().maximum())

    def _tts_finished(self, result_msg):
        self.tts_run_button.setEnabled(True)
        self.tts_run_button.setText('🔊 Bắt đầu tạo Audio')
        QMessageBox.information(self, 'Hoàn thành', result_msg)

    def _tts_error(self, error_msg):
        self.tts_run_button.setEnabled(True)
        self.tts_run_button.setText('🔊 Bắt đầu tạo Audio')
        QMessageBox.critical(self, 'Lỗi', f"Đã xảy ra lỗi:\n{error_msg}")    

    # --- SLOT CHO SUMMARY TAB ---
    def _browse_sum_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Chọn file PDF', '', 'PDF Files (*.pdf)')
        if file_path:
            self.sum_pdf_input.setText(file_path)

    def _browse_sum_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Chọn file Prompt', '', 'Text Files (*.txt)')
        if file_path:
            self.sum_prompt_input.setText(file_path)

    def _start_summary(self):
        pdf_path = self.sum_pdf_input.text()
        prompt_path = self.sum_prompt_input.text()

        if not os.path.exists(pdf_path):
            QMessageBox.warning(self, 'Lỗi', 'File PDF không tồn tại.')
            return
        if not os.path.exists(prompt_path):
            QMessageBox.warning(self, 'Lỗi', 'File Prompt không tồn tại.')
            return

        self.sum_run_button.setEnabled(False)
        self.sum_run_button.setText('⏳ Đang xử lý...')
        self.sum_log_display.clear()

        self.sum_thread = QThread()
        self.sum_worker = SummaryWorker(pdf_path, prompt_path)
        self.sum_worker.moveToThread(self.sum_thread)

        self.sum_thread.started.connect(self.sum_worker.run)
        self.sum_worker.finished.connect(self._sum_finished)
        self.sum_worker.error.connect(self._sum_error)
        self.sum_worker.progress.connect(self._sum_progress)

        self.sum_worker.error.connect(self.sum_thread.quit)      # Thêm
        self.sum_worker.error.connect(self.sum_worker.deleteLater) # Thêm
        self.sum_worker.finished.connect(self.sum_thread.quit)
        self.sum_worker.finished.connect(self.sum_worker.deleteLater)
        self.sum_thread.finished.connect(self.sum_thread.deleteLater)

        self.sum_thread.start()

    def _sum_progress(self, msg):
        self.sum_log_display.appendPlainText(msg)
        self.sum_log_display.verticalScrollBar().setValue(self.sum_log_display.verticalScrollBar().maximum())

    def _sum_finished(self, result):
        self.sum_run_button.setEnabled(True)
        self.sum_run_button.setText('📝 Bắt đầu Tóm tắt')
        QMessageBox.information(self, 'Hoàn thành', result)

    def _sum_error(self, err):
        self.sum_run_button.setEnabled(True)
        self.sum_run_button.setText('📝 Bắt đầu Tóm tắt')
        QMessageBox.critical(self, 'Lỗi', f"Lỗi: {err}")


    def _pipeline_finished(self, result_path):
        """Xử lý khi pipeline chạy thành công."""
        self.run_button.setEnabled(True)
        self.run_button.setText('🚀 Bắt đầu chạy Pipeline')
        QMessageBox.information(self, '✅ Hoàn thành', f'Pipeline đã chạy thành công!\n\nKết quả được lưu tại:\n{os.path.abspath(result_path)}')

    def _pipeline_error(self, error_message):
        """Xử lý khi pipeline gặp lỗi."""
        self.run_button.setEnabled(True)
        self.run_button.setText('🚀 Bắt đầu chạy Pipeline')
        QMessageBox.critical(self, '❌ Lỗi Pipeline', f'Đã xảy ra lỗi trong quá trình chạy:\n\n{error_message}')

    def _image_generation_finished(self, result_path):
        """Xử lý khi tạo ảnh thành công."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText('🎨 Bắt đầu tạo ảnh AI')
        QMessageBox.information(self, '✅ Hoàn thành', f'Tạo ảnh đã hoàn thành!\n\nCác ảnh được lưu tại:\n{os.path.abspath(result_path)}')

    def _image_generation_error(self, error_message):
        """Xử lý khi tạo ảnh gặp lỗi."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText('🎨 Bắt đầu tạo ảnh AI')
        QMessageBox.critical(self, '❌ Lỗi tạo ảnh', f'Đã xảy ra lỗi trong quá trình tạo ảnh:\n\n{error_message}')

    def _image_merge_finished(self, result_path):
        """Xử lý khi ghép ảnh thành công."""
        self.merge_button.setEnabled(True)
        self.merge_button.setText('🔄 Bắt đầu ghép ảnh AI')
        QMessageBox.information(self, '✅ Hoàn thành', f'Ghép ảnh đã hoàn thành!\n\nCác ảnh đã ghép được lưu tại:\n{result_path}')

    def _image_merge_error(self, error_message):
        """Xử lý khi ghép ảnh gặp lỗi."""
        self.merge_button.setEnabled(True)
        self.merge_button.setText('🔄 Bắt đầu ghép ảnh AI')
        QMessageBox.critical(self, '❌ Lỗi ghép ảnh', f'Đã xảy ra lỗi trong quá trình ghép ảnh:\n\n{error_message}')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Thiết lập font mặc định cho toàn bộ ứng dụng
    font = QFont("Arial", 10)
    app.setFont(font)
    
    ex = HSKGeneratorApp()
    ex.show()
    sys.exit(app.exec_())