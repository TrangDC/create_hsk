import sys
import os
import subprocess
import traceback
from dotenv import load_dotenv
import json
import random
from hsk_ppt.test_extract_json_bk import process_full_hsk_lesson
from hsk_ppt.test_extract_json_grammar import process_grammar_lesson
from hsk_ppt.prepare_images import prepare_images_for_json
from hsk_ppt.test_generate_ppt_bk import PPTGenerator
from hsk_ppt.test_generate_ppt_grammar import GrammarPPTGenerator

# ==========================================
# SUPPRESS SUBPROCESS WINDOWS GLOBALLY
# ==========================================
# Patch subprocess TRƯỚC khi import các module khác
if os.name == 'nt':  # Windows only
    old_popen = subprocess.Popen
    
    class _SuppressedPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            # Thiết lập startupinfo để suppress window
            if 'startupinfo' not in kwargs:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= 0x01  # STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                kwargs['startupinfo'] = startupinfo
            
            # Redirect stdout, stderr, stdin nếu không có
            if 'stdout' not in kwargs:
                kwargs['stdout'] = subprocess.DEVNULL
            if 'stderr' not in kwargs:
                kwargs['stderr'] = subprocess.DEVNULL
            if 'stdin' not in kwargs:
                kwargs['stdin'] = subprocess.DEVNULL
            
            # Thêm creationflags để không mở window
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            else:
                kwargs['creationflags'] |= 0x08000000
            
            super().__init__(*args, **kwargs)
    
    subprocess.Popen = _SuppressedPopen

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QPlainTextEdit, QFileDialog, QMessageBox,
    QTabWidget, QRadioButton, QButtonGroup, QGroupBox, QListWidget, QAbstractItemView, QSpinBox
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
    text_to_speech_google,
    generate_single_audio_narakeet
)
from services.media_merger import create_merged_gif
from services.input_handler import InputDataManager
from services.image_gen_service import ImageGenerationService
from services.image_gen_logger import ImageGenLogger
from services.gif_downloader import StrokeGifManager
from call_vertexai import generate_content
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

    def __init__(self, pdf_folder, hsk_level, preproc_mode=0):
        super().__init__()
        self.pdf_folder = pdf_folder
        self.hsk_level = hsk_level
        self.preproc_mode = preproc_mode

    def run(self):
        try:
            result_path = run_full_pipeline(self.pdf_folder, self.hsk_level, self.preproc_mode)
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

# Lớp Worker để tạo ảnh Flashcard tiếng Anh
class EngFlashcardWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, excel_path, sheet_names, prompt_path, error_only=False, gen_audio=True, audio_model="Narakeet"):
        super().__init__()
        self.excel_path   = excel_path
        self.sheet_names  = sheet_names if isinstance(sheet_names, list) else [sheet_names]
        self.prompt_path  = prompt_path
        self.error_only   = error_only
        self.gen_audio    = gen_audio
        self.audio_model  = audio_model
        self.output_base  = "output/eng_flashcards"
        self.template_img_dir = "resources/images/image_eng_template"
        self._is_running  = True

    def stop(self):
        self._is_running = False

    def _get_random_template_image(self):
        if not os.path.exists(self.template_img_dir):
            return None
        valid_ext = ('.png', '.jpg', '.jpeg', '.webp')
        images = [f for f in os.listdir(self.template_img_dir) if f.lower().endswith(valid_ext)]
        if not images:
            return None
        return os.path.join(self.template_img_dir, random.choice(images))

    def run(self):
        try:
            self.progress.emit("🚀 BẮT ĐẦU TẠO ẢNH FLASHCARD TIẾNG ANH...")
            result_folder = os.path.abspath(self.output_base)
            if not os.path.exists(self.template_img_dir):
                os.makedirs(self.template_img_dir, exist_ok=True)
            
            if not os.path.exists(self.excel_path):
                raise FileNotFoundError(f"Không tìm thấy file Excel tại: {self.excel_path}")

            self.progress.emit("⚙️ Khởi tạo Image Generation Service...")
            img_service = ImageGenerationService()

            # Khởi tạo Audio Service nếu được bật
            audio_service = None
            if self.gen_audio:
                from services.eng_audio_service import EngAudioService
                self.progress.emit(f"🔊 Khởi tạo English Audio Service ({self.audio_model})...")
                audio_service = EngAudioService(model_name=self.audio_model)
                if not audio_service.client:
                    self.progress.emit("⚠️ Không khởi tạo được Audio Service — bỏ qua sinh audio.")
                    audio_service = None
                else:
                    self.progress.emit("✅ Audio Service sẵn sàng.")
            
            self.progress.emit("�📄 Đang đọc file Prompt và Excel...")
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            xls = pd.ExcelFile(self.excel_path)
            
            total_generated = 0
            total_audio_generated = 0
            
            for sheet in self.sheet_names:
                if not self._is_running:
                    break
                self.progress.emit(f"\n📂 Đang xử lý sheet: {sheet}")

                # Khởi tạo logger cho từng sheet
                logger = ImageGenLogger(session_name=f"eng_flashcard_{sheet}")
                
                # Tạo thư mục theo tên sheet
                sheet_safe_name = "".join([c for c in sheet if c.isalnum() or c in (' ', '-', '_')]).strip()
                sheet_out_dir = os.path.join(self.output_base, sheet_safe_name)
                if len(self.sheet_names) == 1:
                    result_folder = os.path.abspath(sheet_out_dir)
                audio_out_dir = os.path.join(sheet_out_dir, "audio")
                os.makedirs(sheet_out_dir, exist_ok=True)
                if audio_service:
                    os.makedirs(audio_out_dir, exist_ok=True)

                try:
                    df = pd.read_excel(xls, sheet_name=sheet)
                except Exception as e:
                    self.progress.emit(f"⚠️ Lỗi đọc sheet '{sheet}': {e}")
                    continue
                
                if 'Từ' not in df.columns:
                    self.progress.emit(f"⚠️ Sheet '{sheet}' không có cột 'Từ'. Bỏ qua.")
                else:
                    # Đảm bảo các cột cần thiết tồn tại để tránh lỗi
                    if 'Nghĩa' not in df.columns:
                        df['Nghĩa'] = ''
                    if 'Câu ví dụ' not in df.columns:
                        df['Câu ví dụ'] = ''
                    if 'Note' not in df.columns:
                        df['Note'] = ''

                    words    = df['Từ'].astype(str).tolist()
                    meanings = df['Nghĩa'].fillna('').astype(str).tolist()
                    examples = df['Câu ví dụ'].fillna('').astype(str).tolist()
                    notes    = df['Note'].fillna('').astype(str).tolist()
                    
                    self.progress.emit(f"📋 Tìm thấy {len(words)} từ vựng trong sheet {sheet}.")

                    for idx, word in enumerate(words):
                        if not self._is_running:
                            self.progress.emit("\n🛑 NGƯỜI DÙNG ĐÃ YÊU CẦU DỪNG.")
                            break

                        word = word.strip()
                        if not word or word == 'nan': continue

                        note_val = notes[idx].strip()
                        if self.error_only and not note_val:
                            logger.log_request(word=word, status="skipped")
                            continue
                        force_regenerate = self.error_only and bool(note_val)

                        meaning = meanings[idx].strip()
                        example = examples[idx].strip()

                        safe_word = "".join([c for c in word if c.isalnum() or c in (' ', '-', '_')]).strip()
                        final_img_path = os.path.join(sheet_out_dir, f"{safe_word}.png")

                        # --- SINH ẢNH ---
                        if os.path.exists(final_img_path) and not force_regenerate:
                            self.progress.emit(f"   [{idx + 1}/{len(words)}] ⏭️ '{word}' đã có ảnh, bỏ qua.")
                            logger.log_request(word=word, status="skipped")
                        else:
                            action_label = "🎨 Đang ghi đè ảnh cho" if force_regenerate and os.path.exists(final_img_path) else "🎨 Đang tạo ảnh cho"
                            self.progress.emit(f"   [{idx + 1}/{len(words)}] {action_label}: '{word}'...")
                            
                            image_prompt = prompt_template.format(
                                word=word,
                                meaning=meaning,
                                example=example,
                                topic=sheet
                            )

                            template_img_path = self._get_random_template_image()
                            if not template_img_path:
                                self.progress.emit("      ⚠️ Không tìm thấy ảnh template mẫu.")

                            try:
                                img_bytes, usage = img_service.generate_image_with_image_ref(
                                    prompt=image_prompt,
                                    image_path=template_img_path,
                                    aspect_ratio="3:2"
                                )
                                
                                if img_bytes:
                                    with open(final_img_path, "wb") as f:
                                        f.write(img_bytes)
                                    total_generated += 1
                                    logger.log_request(
                                        word=word,
                                        status="success",
                                        tokens_in=usage.get("prompt_tokens", 0),
                                        tokens_out=usage.get("output_tokens", 0),
                                        total_tokens=usage.get("total_tokens", 0),
                                        attempts=usage.get("attempts", 1),
                                    )
                                    self.progress.emit(
                                        f"      ✅ Ảnh OK | tokens: {usage.get('total_tokens', 'N/A')} | attempts: {usage.get('attempts', 1)}"
                                    )
                                else:
                                    self.progress.emit(f"      ❌ Không sinh được ảnh cho '{word}'")
                                    logger.log_request(
                                        word=word,
                                        status="failed",
                                        attempts=usage.get("attempts", 1),
                                        error="No image data returned",
                                    )
                                    
                            except Exception as e:
                                self.progress.emit(f"      ❌ Lỗi AI (ảnh): {e}")
                                logger.log_request(word=word, status="failed", error=str(e))

                        # --- SINH AUDIO (nếu được bật) ---
                        if audio_service and self._is_running:
                            word_audio_path    = os.path.join(audio_out_dir, f"{safe_word}.mp3")
                            example_audio_path = os.path.join(audio_out_dir, f"{safe_word}_example.mp3")

                            # Audio từ đơn
                            if os.path.exists(word_audio_path) and not force_regenerate:
                                self.progress.emit(f"      🔊 Audio từ đã có, bỏ qua.")
                            else:
                                prefix = "ghi đè" if force_regenerate and os.path.exists(word_audio_path) else "sinh"
                                self.progress.emit(f"      🔊 Đang {prefix} audio từ: '{word}'...")
                                ok = audio_service.generate_word(word=word, out_path=word_audio_path, overwrite=force_regenerate)
                                if ok:
                                    total_audio_generated += 1
                                    self.progress.emit(f"      ✅ Audio từ OK")
                                else:
                                    self.progress.emit(f"      ❌ Lỗi sinh audio từ '{word}'")

                            # Audio câu ví dụ
                            if example and example != 'nan':
                                if os.path.exists(example_audio_path) and not force_regenerate:
                                    self.progress.emit(f"      🔊 Audio câu ví dụ đã có, bỏ qua.")
                                else:
                                    prefix = "ghi đè" if force_regenerate and os.path.exists(example_audio_path) else "sinh"
                                    self.progress.emit(f"      🔊 Đang {prefix} audio câu ví dụ...")
                                    ok = audio_service.generate_example(sentence=example, out_path=example_audio_path, overwrite=force_regenerate)
                                    if ok:
                                        total_audio_generated += 1
                                        self.progress.emit(f"      ✅ Audio câu ví dụ OK")
                                    else:
                                        self.progress.emit(f"      ❌ Lỗi sinh audio câu ví dụ")
                        
                        import time
                        time.sleep(1) # Tránh rate limit

                # --- Kết thúc sheet: upload log lên Drive ---
                self.progress.emit(f"\n📤 Đang upload log sheet '{sheet}' lên Drive...")
                logger.finish_and_upload()

            summary = f"Hoàn tất! Đã tạo thành công {total_generated} ảnh"
            if self.gen_audio:
                summary += f" và {total_audio_generated} file audio"
            summary += f" tại:\n{result_folder}"
            self.finished.emit(summary)

        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())

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

    def __init__(self, pdf_path, prompt_path, num_lessons):
        super().__init__()
        self.pdf_path = pdf_path
        self.prompt_path = prompt_path
        self.num_lessons = num_lessons
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
            return self.credentials
            
        except Exception as e:
            print(f"Lỗi khi tạo credentials từ service account: {e}")
            return None

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
            
            # Thay thế số lượng bài khóa trong prompt nếu có
            prompt_content = prompt_content.replace("{num_lessons}", str(self.num_lessons))

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

class FlashcardWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, excel_path, sheet_name, output_base):
        super().__init__()
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.output_base = output_base

        # Cấu hình đường dẫn nội bộ
        self.img_final_dir = os.path.join(self.output_base, "images")
        self.audio_dir = os.path.join(self.output_base, "audio")
        self.raw_img_dir = os.path.join(self.output_base, "raw_images")
        self.raw_gif_dir = os.path.join(self.output_base, "raw_gifs")

        # Cấu hình Resource
        self.schema_path = "resources/schema/flashcard_schema.json"
        self.prompt_path = "resources/prompts/enrich_vocab.txt"
        self.mascot_pdf = "resources/panda_mascot.pdf"
        
        # Khởi tạo Google TTS client
        self.tts_client = None
        try:
            self.tts_client = init_google_tts_client()
            print("✅ Google TTS Client đã khởi tạo thành công!")
        except Exception as e:
            print(f"⚠️ Lỗi khởi tạo Google TTS Client: {e}")
            print("   Audio sẽ không được tạo nếu không khởi tạo được client.")

    def _setup_folders(self):
        for d in [self.output_base, self.img_final_dir, self.audio_dir, 
                  self.raw_img_dir, self.raw_gif_dir]:
            if not os.path.exists(d): os.makedirs(d)

    def _setup_resources(self):
        """
        Chỉ kiểm tra sự tồn tại của các file cấu hình.
        Nếu chưa có thì tạo bản mẫu cơ bản.
        """
        # 1. Kiểm tra Schema
        if not os.path.exists(self.schema_path):
            os.makedirs(os.path.dirname(self.schema_path), exist_ok=True)
            default_schema = {
                "type": "OBJECT",
                "properties": {
                    "pinyin": {"type": "STRING", "description": "Phiên âm Pinyin"},
                    "part_of_speech": {"type": "STRING", "description": "Từ loại"},
                    "word_meaning_vn": {"type": "STRING", "description": "Nghĩa tiếng Việt"},
                    "example_sentence_cn": {"type": "STRING", "description": "Câu ví dụ tiếng Trung"},
                    "example_pinyin": {"type": "STRING", "description": "Pinyin ví dụ"},
                    "example_meaning_vn": {"type": "STRING", "description": "Nghĩa tiếng Việt ví dụ"},
                    "use_mascot": {"type": "BOOLEAN", "description": "True nếu dùng Mascot."},
                    "image_prompt_en": {"type": "STRING", "description": "Prompt vẽ ảnh."}
                },
                "required": ["pinyin", "part_of_speech", "word_meaning_vn", "example_sentence_cn", "example_pinyin", "example_meaning_vn", "use_mascot", "image_prompt_en"]
            }
            with open(self.schema_path, 'w', encoding='utf-8') as f:
                json.dump(default_schema, f, ensure_ascii=False, indent=2)
            self.progress.emit("📄 Đã tạo file Schema mẫu tại " + self.schema_path)

        # 2. Kiểm tra Prompt Template
        if not os.path.exists(self.prompt_path):
            os.makedirs(os.path.dirname(self.prompt_path), exist_ok=True)
            default_prompt = """
        Bạn là chuyên gia ngôn ngữ Trung-Việt và Art Director.
Input: Từ '{word}', Phiên âm '{pinyin}', Nghĩa '{meaning}', Ví dụ '{example}'.

Nhiệm vụ:
1. Xác định Pinyin chuẩn.
2. Xác định **DUY NHẤT 01** Từ loại (Part of Speech) dựa trên ngữ cảnh ví dụ.
3. Tạo Pinyin và dịch nghĩa cho câu ví dụ.
4. Quyết định 'use_mascot' (True/False):
   - TRUE khi: Từ chỉ hành động chung (ăn, chạy, học), cảm xúc (vui, buồn), nghề nghiệp chung mà gấu trúc đóng vai được.
   - FALSE khi: 
     + Từ chỉ đồ vật tĩnh, kiến trúc, phương tiện (tứ hợp viện, xe hơi, máy tính). -> Vẽ trực tiếp đối tượng.
     + Từ chỉ hành động/tính chất đặc thù giới tính hoặc nhân vật khác (trang điểm, mặc váy). -> Vẽ nhân vật phù hợp văn hóa Trung Quốc (ví dụ: cô gái Trung Quốc hoạt hình).

5. Viết Prompt vẽ ảnh (image_prompt_en):
    - Mục tiêu: Tạo ra một đối tượng đồ họa cô lập (isolated) để ghép vào thẻ học.
    - Yêu cầu bắt buộc: 
        + Phong cách: Flat illustration, 2D vector, hoạt hình, màu sắc tươi sáng, nét vẽ rõ ràng.
        + Nền: PHẢI LÀ NỀN TRẮNG TINH (Pure white background). 
        + Bối cảnh: KHÔNG vẽ bầu trời, KHÔNG vẽ mặt đất, KHÔNG vẽ cây cối hay nhà cửa xung quanh (trừ khi đối tượng chính là cái nhà). 
        + Hình ảnh phải được cô lập hoàn toàn (Isolated), giống như một tấm nhãn dán (Sticker style).
        + KHÔNG KÈM CHỮ VIẾT NÀO TRÊN ẢNH, chỉ có hình vẽ.
    - Nội dung:
        + Nếu use_mascot=TRUE: Mô tả hành động của chú gấu trúc (từ tài liệu PDF tham khảo) thực hiện hành động của từ '{word}' theo câu ví dụ '{example}'.
        + Nếu use_mascot=FALSE: Mô tả đối tượng hoặc nhân vật cụ thể thực hiện hành động.
    - Lưu ý vibes: Ưu tiên vibes Trung Quốc hiện đại hoặc truyền thống nhẹ nhàng tùy ngữ cảnh câu.

Trả về JSON chuẩn theo Schema.
        """
            with open(self.prompt_path, 'w', encoding='utf-8') as f:
                f.write(default_prompt)
            self.progress.emit("📄 Đã tạo file Prompt mẫu tại " + self.prompt_path)    

    def run(self):
        try:
            self.progress.emit("🚀 KHỞI ĐỘNG FLASHCARD GENERATOR...")
            self._setup_folders()
            self._setup_resources()

            # 1. XỬ LÝ INPUT
            self.progress.emit(f"📄 Đang đọc dữ liệu từ Excel...")
            input_manager = InputDataManager(self.excel_path)
            input_data_list = input_manager.process_specific_sheet(self.sheet_name)
            
            if not input_data_list:
                raise ValueError("Không tìm thấy dữ liệu hợp lệ trong sheet.")

            # 2. INIT SERVICES
            self.progress.emit("⚙️ Khởi tạo AI & Image Services...")
            gif_manager = StrokeGifManager(gif_folder=self.raw_gif_dir, png_folder=self.raw_gif_dir)
            img_service = ImageGenerationService()

            excel_results = []
            total_items = len(input_data_list)
            
            # 3. VÒNG LẶP XỬ LÝ (QUÉT QUA TOÀN BỘ CÁC DÒNG)
            for idx, item in enumerate(input_data_list):
                word = item['word']

                def get_updated_filename(exist_key, final_key):
                    val = item.get(exist_key)
                    if val and str(val).strip() and str(val) != 'nan':
                        return item.get(final_key)
                    return val

                # Khởi tạo row_data mặc định từ dữ liệu Excel hiện có
                row_data = {
                    "Title": item['final_title'],
                    "word": word,
                    "pronunciation": item['pinyin'],
                    "type": item['type'],
                    "word_translation": item['meaning'],
                    "phrace": item['example'],
                    "pronunciation_phrace": item['ex_pinyin'],
                    "phrace_translation": item['ex_meaning'],
                    "thumbnail": get_updated_filename('exist_thumb', 'filename_image'),
                    "audio1": get_updated_filename('exist_audio1', 'filename_audio_word'),
                    "audio2": get_updated_filename('exist_audio2', 'filename_audio_ex')
                }

                # KIỂM TRA XEM CÓ CẦN XỬ LÝ AI/MEDIA KHÔNG
                if item['needs_processing']:
                    self.progress.emit(f"\n[{idx+1}/{total_items}] 🔄 Đang bổ sung dữ liệu: {word}...")

                    # --- A. GỌI AI (Đọc prompt/schema từ file) ---
                    ai_data = {}
                    try:
                        with open(self.prompt_path, 'r', encoding='utf-8') as f:
                            prompt_template = f.read()
                        
                        prompt_input = prompt_template.format(
                            word=word, 
                            pinyin=item['pinyin'] or "",
                            meaning=item['meaning'] or "", 
                            example=item['example'] or ""
                        )
                        
                        temp_path = f"resources/prompts/temp_{idx}.txt"
                        with open(temp_path, 'w', encoding='utf-8') as f: f.write(prompt_input)

                        ai_data = generate_content(temp_path, self.schema_path, [self.mascot_pdf], None)
                        if os.path.exists(temp_path): os.remove(temp_path)
                    except Exception as e:
                        self.progress.emit(f"⚠️ Lỗi AI tại từ '{word}': {e}")

                    # --- B. ĐIỀN KHUYẾT THÔNG TIN TEXT (Nếu Excel trống mới lấy AI) ---
                    if not row_data['pronunciation']: row_data['pronunciation'] = ai_data.get('pinyin', '')
                    if not row_data['type']: row_data['type'] = ai_data.get('part_of_speech', '')
                    if not row_data['word_translation']: row_data['word_translation'] = ai_data.get('word_meaning_vn', '')
                    
                    if not row_data['phrace']: 
                        row_data['phrace'] = ai_data.get('example_sentence_cn', '')
                    
                    # Cập nhật pinyin/dịch câu dựa trên câu ví dụ cuối cùng (Excel hoặc AI)
                    if not row_data['pronunciation_phrace']: row_data['pronunciation_phrace'] = ai_data.get('example_pinyin', '')
                    if not row_data['phrace_translation']: row_data['phrace_translation'] = ai_data.get('example_meaning_vn', '')

                    # --- C. XỬ LÝ MEDIA (Chỉ sinh những cái còn thiếu) ---
                    
                    # 1. Ảnh minh họa (Thumbnail)
                    if not row_data['thumbnail']:
                        row_number = item.get('excel_row', idx + 2)
                        raw_img_path = os.path.join(self.raw_img_dir, f"{word}_{row_number}_ai.png")
                        has_img = False
                        
                        # Sinh ảnh AI nếu chưa có
                        if not os.path.exists(raw_img_path):
                            try:
                                use_mascot = ai_data.get('use_mascot', True)
                                prompt = ai_data.get('image_prompt_en', f"illustration of {word}")
                                pdf = self.mascot_pdf if use_mascot else None
                                img_bytes = img_service.generate_image_pdfs(prompt, pdf, aspect_ratio="3:2")
                                if img_bytes:
                                    # Nén và tối ưu hóa ảnh trước khi lưu (Giảm dung lượng từ vài MB xuống vài trăm KB)
                                    from PIL import Image
                                    import io
                                    
                                    img = Image.open(io.BytesIO(img_bytes))
                                    if img.mode in ("RGBA", "LA"):
                                        bg = Image.new("RGB", img.size, (255, 255, 255))
                                        bg.paste(img, mask=img.split()[-1])
                                        img = bg
                                    else:
                                        img = img.convert("RGB")
                                        
                                    img.save(raw_img_path, format="JPEG", quality=85, optimize=True)
                                    has_img = True
                            except Exception as e: self.progress.emit(f"⚠️ Lỗi Image Gen: {e}")
                        else: has_img = True

                        # Tải GIF nét viết
                        gifs = []
                        for char in word:
                            g = gif_manager.download_char(char) # Trả về (gif_path, png_path)
                            if g and os.path.exists(g): gifs.append(g)
                        
                        if len(gifs) != len(word): gifs = [] # Nếu thiếu nét thì coi như ko có gif

                        # Merge thành GIF cuối cùng
                        final_gif_path = os.path.join(self.img_final_dir, item['filename_image'])
                        if has_img:
                            if create_merged_gif(raw_img_path, gifs, final_gif_path):
                                row_data['thumbnail'] = item['filename_image']
                                self.progress.emit(f"   ✅ Đã tạo ảnh mới: {item['filename_image']}")
                        
                    # 2. Audio Từ (audio1) - Sử dụng Google TTS
                    if not row_data['audio1']:
                        w_path = os.path.join(self.audio_dir, item['filename_audio_word'])
                        if self.tts_client:
                            try:
                                if text_to_speech_google(self.tts_client, word, w_path):
                                    row_data['audio1'] = item['filename_audio_word']
                                    self.progress.emit(f"   🔊 Đã tạo audio từ (Google TTS).")
                            except Exception as e:
                                self.progress.emit(f"   ⚠️ Lỗi tạo audio từ: {e}")
                        else:
                            self.progress.emit(f"   ⚠️ Bỏ qua audio từ: Google TTS client chưa sẵn sàng")

                    # 3. Audio Câu (audio2) - Sử dụng Google TTS
                    if not row_data['audio2'] and row_data['phrace']:
                        ex_path = os.path.join(self.audio_dir, item['filename_audio_ex'])
                        if self.tts_client:
                            try:
                                if text_to_speech_google(self.tts_client, row_data['phrace'], ex_path):
                                    row_data['audio2'] = item['filename_audio_ex']
                                    self.progress.emit(f"   🔊 Đã tạo audio câu (Google TTS).")
                            except Exception as e:
                                self.progress.emit(f"   ⚠️ Lỗi tạo audio câu: {e}")
                        else:
                            self.progress.emit(f"   ⚠️ Bỏ qua audio câu: Google TTS client chưa sẵn sàng")

                else:
                    self.progress.emit(f"[{idx+1}/{total_items}] ✅ Bỏ qua (Đã hoàn thành): {word}")

                # Lưu vào danh sách tổng (85 dòng)
                excel_results.append(row_data)

            # 4. XUẤT EXCEL VỚI RICH TEXT (TÔ ĐẬM TỪ KHÓA)
            self.progress.emit("\n📦 Đang đóng gói file Excel và tô đậm từ khóa...")
            if excel_results:
                df = pd.DataFrame(excel_results)
                cols_order = ["Title", "word", "pronunciation", "type", 
                            "word_translation", "phrace", "pronunciation_phrace", 
                            "phrace_translation", "thumbnail", "audio1", "audio2"]
                final_cols = [c for c in cols_order if c in df.columns]
                df = df[final_cols]
                
                out_path = os.path.join(self.output_base, f"Result_{self.sheet_name}.xlsx")

                # --- SỬ DỤNG XLSXWRITER ĐỂ BOLD ---
                writer = pd.ExcelWriter(out_path, engine='xlsxwriter')
                df.to_excel(writer, index=False, sheet_name='Sheet1')

                workbook  = writer.book
                worksheet = writer.sheets['Sheet1']
                bold_format = workbook.add_format({'bold': True})

                try:
                    phrace_col_idx = df.columns.get_loc("phrace")
                except:
                    phrace_col_idx = 5

                # Chọn toàn bộ 85 dòng trong excel_results
                for row_num, row_data in enumerate(excel_results):
                    word_val = str(row_data.get('word', '')).strip()
                    phrase_val = str(row_data.get('phrace', '')).strip()

                    if word_val and phrase_val and word_val in phrase_val:
                        parts = phrase_val.split(word_val, 1)
                        rich_string = []
                        if parts[0]: rich_string.append(parts[0])
                        rich_string.append(bold_format)
                        rich_string.append(word_val)
                        if parts[1]: rich_string.append(parts[1])

                        # Ghi Rich String vào dòng (row_num + 1)
                        worksheet.write_rich_string(row_num + 1, phrace_col_idx, *rich_string)
                
                writer.close()
                self.finished.emit(f"🎉 HOÀN TẤT!\nFile: {out_path}")
            else:
                self.error.emit("Không có dữ liệu đầu ra.")

        except Exception as e:
            error_msg = traceback.format_exc()
            self.error.emit(f"Lỗi hệ thống:\n{error_msg}")

class AudioTTSWorker(QObject):
    """Worker để chạy Audio TTS (Vertex AI) trong một luồng riêng."""
    finished = pyqtSignal(str)  # Trả về đường dẫn folder chứa audio
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, excel_path, output_folder, model_name='Chirp3-HD', male_voice='Charon', female_voice='Zephyr'):
        super().__init__()
        self.excel_path = excel_path
        self.output_folder = output_folder
        self.model_name = model_name
        self.male_voice = male_voice
        self.female_voice = female_voice

    def run(self):
        try:
            self.progress.emit("🔄 Khởi tạo Audio TTS (Vertex AI)...")
            self.progress.emit(f"   Model: {self.model_name} | Voice Nam: {self.male_voice} | Voice Nữ: {self.female_voice}")

            # delegate toàn bộ logic sang helper ở services/audio_tts
            from services.audio_tts import test_file
            audio_folder = test_file(
                self.excel_path,
                self.output_folder,
                model_name=self.model_name,
                male_voice=self.male_voice,
                female_voice=self.female_voice,
                log_fn=self.progress.emit
            )

            self.progress.emit(f"\n🎉 HOÀN THÀNH! Audio thư mục: {os.path.abspath(audio_folder)}")
            self.finished.emit(f"✅ Thành công!\nFolder audio: {os.path.abspath(audio_folder)}")

        except Exception as e:
            error_details = traceback.format_exc()
            self.progress.emit(f"❌ Lỗi: {str(e)}")
            self.error.emit(f"{str(e)}\n\nChi tiết:\n{error_details}")

class PPTGeneratorWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, pdf_path, output_folder, hsk_level, ppt_type):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_folder = output_folder
        self.hsk_level = hsk_level
        self.ppt_type = ppt_type

    def run(self):
        try:
            # Lấy đường dẫn thư mục linh hoạt giữa file thực thi (exe) và python script
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Đảm bảo import được module trong hsk_ppt
            if base_dir not in sys.path:
                sys.path.append(base_dir)

            base_name = os.path.basename(self.pdf_path).replace('.pdf', '')
            bk_json_path = os.path.join(self.output_folder, f"{base_name}_bk.json")
            gr_json_path = os.path.join(self.output_folder, f"{base_name}_grammar.json")
            bk_ppt_path = os.path.join(self.output_folder, f"{base_name}_{self.hsk_level}_Bai_Khoa.pptx")
            gr_ppt_path = os.path.join(self.output_folder, f"{base_name}_{self.hsk_level}_Ngu_Phap.pptx")

            index_file = os.path.join(base_dir, "resources", "ppt_templates", "hsk_index.json")
            bk_template = os.path.join(base_dir, "resources", "ppt_templates", "HSK Bài Khóa template.pptx")
            gr_template = os.path.join(base_dir, "resources", "ppt_templates", "HSK Ngữ pháp template.pptx")
            bk_prompt = os.path.join(base_dir, "resources", "prompts", "ppt_generation", "Prompt_Bai_Khoa.txt")
            gr_prompt = os.path.join(base_dir, "resources", "prompts", "ppt_generation", "Prompt_Ngu_Phap.txt")
            
            with open(bk_prompt, 'r', encoding='utf-8') as f:
                bk_prompt_text = f.read()
            with open(gr_prompt, 'r', encoding='utf-8') as f:
                gr_prompt_text = f.read()

            if self.ppt_type in ["Cả hai", "Bài khóa"]:
                self.progress.emit(f"Đang trích xuất JSON Bài Khóa ({self.hsk_level})...")
                process_full_hsk_lesson(self.pdf_path, bk_prompt_text, self.hsk_level, bk_json_path)

            if self.ppt_type in ["Cả hai", "Ngữ pháp"]:
                self.progress.emit(f"Đang trích xuất JSON Ngữ Pháp ({self.hsk_level})...")
                process_grammar_lesson(self.pdf_path, gr_prompt_text, self.hsk_level, index_file, gr_json_path)

            # Step 2: Prepare Images
            if self.ppt_type in ["Cả hai", "Bài khóa"]:
                self.progress.emit("Đang sinh ảnh minh họa AI (Bài Khóa)...")
                prepare_images_for_json(bk_json_path)

            if self.ppt_type in ["Cả hai", "Ngữ pháp"]:
                self.progress.emit("Đang sinh ảnh minh họa AI (Ngữ Pháp)...")
                prepare_images_for_json(gr_json_path)

            # Step 3: Render PPT
            if self.ppt_type in ["Cả hai", "Bài khóa"]:
                self.progress.emit("Đang render PPT Bài Khóa...")
                if os.path.exists(bk_json_path):
                    gen_bk = PPTGenerator(bk_template, bk_json_path)
                    gen_bk.build()
                    gen_bk.save(bk_ppt_path)
                
            if self.ppt_type in ["Cả hai", "Ngữ pháp"]:
                self.progress.emit("Đang render PPT Ngữ Pháp...")
                if os.path.exists(gr_json_path):
                    gen_gr = GrammarPPTGenerator(gr_template, gr_json_path)
                    gen_gr.build()
                    gen_gr.save(gr_ppt_path)

            self.finished.emit(self.output_folder)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())

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
        self.setGeometry(200, 200, 1600, 900)

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

        # --- TAB AUDIO TTS (VERTEX AI) ---
        self.audio_tts_tab = self.create_audio_tts_tab()
        self.tab_widget.addTab(self.audio_tts_tab, "🎙️ Audio TTS")

        self.ppt_tab = self.create_ppt_gen_tab()
        self.tab_widget.addTab(self.ppt_tab, "Tạo PPT HSK")

        self.summary_tab = self.create_summary_tab()
        self.tab_widget.addTab(self.summary_tab, "Tóm tắt HSK")

        self.flashcard_tab = self.create_flashcard_tab()
        self.tab_widget.addTab(self.flashcard_tab, "Flashcard Gen")

        # --- THÊM TAB ENGLISH FLASHCARD ---
        self.eng_flashcard_tab = self.create_eng_flashcard_tab()
        self.tab_widget.addTab(self.eng_flashcard_tab, "English Flashcard")

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
            min-width: 180px;
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
        self.browse_button = QPushButton('Chọn...')
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

        # --- THÊM MỚI: Phần chọn Chế độ phân tích PDF ---
        preproc_layout = QHBoxLayout()
        preproc_layout.setSpacing(15)
        self.preproc_label = QLabel('Tùy chọn phân tích PDF:')
        self.preproc_combo = QComboBox()
        self.preproc_combo.addItems([
            "Minitest",
            "Chỉ Từ vựng & Bài khóa",
            "Chỉ Từ vựng & Ngữ pháp"
        ])
        self.preproc_combo.setMinimumWidth(300)
        preproc_layout.addWidget(self.preproc_label, 0)
        preproc_layout.addWidget(self.preproc_combo, 0)
        preproc_layout.addStretch(1)
        layout.addLayout(preproc_layout)

        
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
        self.browse_excel_button = QPushButton('Chọn...')
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
        self.browse_excel_merge_button = QPushButton('Chọn...')
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
        self.browse_images_button = QPushButton('Chọn...')
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
        self.tts_browse_excel_btn = QPushButton('Chọn...')
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
        self.tts_browse_output_btn = QPushButton('Chọn...')
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

    def create_audio_tts_tab(self):
        """Tạo tab cho chức năng Audio TTS (Vertex AI)."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Chọn File Excel
        excel_layout = QHBoxLayout()
        self.audio_tts_excel_label = QLabel('File Excel:')
        self.audio_tts_excel_input = QLineEdit()
        self.audio_tts_excel_input.setPlaceholderText("Chọn file Excel chứa câu hỏi...")
        self.audio_tts_browse_excel_btn = QPushButton('Chọn...')
        self.audio_tts_browse_excel_btn.setStyleSheet("background-color: #28a745;")
        self.audio_tts_browse_excel_btn.clicked.connect(self._browse_audio_tts_excel)
        
        excel_layout.addWidget(self.audio_tts_excel_label)
        excel_layout.addWidget(self.audio_tts_excel_input)
        excel_layout.addWidget(self.audio_tts_browse_excel_btn)
        layout.addLayout(excel_layout)

        # 2. Chọn Folder Output
        output_layout = QHBoxLayout()
        self.audio_tts_output_label = QLabel('Thư mục Output:')
        self.audio_tts_output_input = QLineEdit()
        # default points to root 'output' folder - audio subfolder will be created automatically
        self.audio_tts_output_input.setText(os.path.join(os.getcwd(), "output"))
        self.audio_tts_browse_output_btn = QPushButton('Chọn...')
        self.audio_tts_browse_output_btn.setStyleSheet("background-color: #28a745;")
        self.audio_tts_browse_output_btn.clicked.connect(self._browse_audio_tts_output)

        output_layout.addWidget(self.audio_tts_output_label)
        output_layout.addWidget(self.audio_tts_output_input)
        output_layout.addWidget(self.audio_tts_browse_output_btn)
        layout.addLayout(output_layout)

        # 3. Cấu hình Model và Voice
        config_group_box = QGroupBox("Cấu hình Model & Voice")
        config_layout = QVBoxLayout()
        
        # Dòng 1: Model Name Selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Model TTS:")
        self.audio_tts_model_combo = QComboBox()
        self.audio_tts_model_combo.addItems(['Chirp3-HD', 'gemini-2.5-pro-tts', 'gemini-2.5-flash-tts'])
        self.audio_tts_model_combo.setCurrentText('Chirp3-HD')
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.audio_tts_model_combo)
        model_layout.addStretch()
        config_layout.addLayout(model_layout)
        
        # Dòng 2: Voice Nam Selection
        male_layout = QHBoxLayout()
        male_label = QLabel("Voice Nam:")
        self.audio_tts_male_voice_combo = QComboBox()
        self.audio_tts_male_voice_combo.addItems(['Charon', 'Orus', 'Enceladus'])
        self.audio_tts_male_voice_combo.setCurrentText('Charon')
        male_layout.addWidget(male_label)
        male_layout.addWidget(self.audio_tts_male_voice_combo)
        male_layout.addStretch()
        config_layout.addLayout(male_layout)
        
        # Dòng 3: Voice Nữ Selection
        female_layout = QHBoxLayout()
        female_label = QLabel("Voice Nữ:")
        self.audio_tts_female_voice_combo = QComboBox()
        self.audio_tts_female_voice_combo.addItems(['Zephyr', 'Leda', 'Carrllihoe'])
        self.audio_tts_female_voice_combo.setCurrentText('Zephyr')
        female_layout.addWidget(female_label)
        female_layout.addWidget(self.audio_tts_female_voice_combo)
        female_layout.addStretch()
        config_layout.addLayout(female_layout)
        
        config_group_box.setLayout(config_layout)
        layout.addWidget(config_group_box)

        # 4. Nút chạy
        self.audio_tts_run_button = QPushButton('🎙️ Tạo Audio TTS (Vertex AI)')
        self.audio_tts_run_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B6B;
                color: white;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF5252;
            }
            QPushButton:pressed {
                background-color: #E63946;
            }
        """)
        self.audio_tts_run_button.clicked.connect(self._start_audio_tts)
        layout.addWidget(self.audio_tts_run_button)

        # 5. Log area
        log_label = QLabel('📋 Nhật ký Audio TTS:')
        layout.addWidget(log_label)
        
        self.audio_tts_log_display = QPlainTextEdit()
        self.audio_tts_log_display.setReadOnly(True)
        layout.addWidget(self.audio_tts_log_display)

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
        self.sum_browse_pdf_btn = QPushButton('Chọn...')
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
        self.sum_browse_prompt_btn = QPushButton('Chọn...')
        self.sum_browse_prompt_btn.setStyleSheet("background-color: #17a2b8;")
        self.sum_browse_prompt_btn.clicked.connect(self._browse_sum_prompt)

        prompt_layout.addWidget(self.sum_prompt_label)
        prompt_layout.addWidget(self.sum_prompt_input)
        prompt_layout.addWidget(self.sum_browse_prompt_btn)
        layout.addLayout(prompt_layout)

        # 2.5 Nhập số lượng bài khóa
        num_lessons_layout = QHBoxLayout()
        self.sum_num_lessons_label = QLabel('Số lượng bài khóa:')
        self.sum_num_lessons_input = QSpinBox()
        self.sum_num_lessons_input.setMinimum(1)
        self.sum_num_lessons_input.setMaximum(20)
        self.sum_num_lessons_input.setValue(1) # Mặc định là 1

        num_lessons_layout.addWidget(self.sum_num_lessons_label)
        num_lessons_layout.addWidget(self.sum_num_lessons_input)
        num_lessons_layout.addStretch()
        layout.addLayout(num_lessons_layout)

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

    def create_flashcard_tab(self):
        """Tạo tab Flashcard Generator (Tính năng mới)."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Chọn Excel Input
        excel_layout = QHBoxLayout()
        self.fc_excel_label = QLabel('File Excel Đầu vào:')
        self.fc_excel_input = QLineEdit()
        self.fc_browse_btn = QPushButton('Chọn...')
        self.fc_browse_btn.setStyleSheet("background-color: #28a745;")
        self.fc_browse_btn.clicked.connect(self._browse_flashcard_excel)
        excel_layout.addWidget(self.fc_excel_label)
        excel_layout.addWidget(self.fc_excel_input)
        excel_layout.addWidget(self.fc_browse_btn)
        layout.addLayout(excel_layout)

        # 2. Chọn Sheet (Dropdown)
        sheet_layout = QHBoxLayout()
        self.fc_sheet_label = QLabel('Chọn Sheet HSK:')
        self.fc_sheet_combo = QComboBox()
        self.fc_sheet_combo.setMinimumWidth(200)
        self.fc_load_sheet_btn = QPushButton('🔄 Tải danh sách Sheet')
        self.fc_load_sheet_btn.clicked.connect(self._load_sheets)
        sheet_layout.addWidget(self.fc_sheet_label)
        sheet_layout.addWidget(self.fc_sheet_combo)
        sheet_layout.addWidget(self.fc_load_sheet_btn)
        sheet_layout.addStretch()
        layout.addLayout(sheet_layout)

        # 3. Chọn Output Folder
        out_layout = QHBoxLayout()
        self.fc_out_label = QLabel('Thư mục Output:')
        self.fc_out_input = QLineEdit()
        self.fc_out_input.setText(os.path.join(os.getcwd(), "output", "flashcards"))
        self.fc_out_browse = QPushButton('Chọn...')
        self.fc_out_browse.clicked.connect(lambda: self.fc_out_input.setText(QFileDialog.getExistingDirectory(self, "Chọn Output")))
        out_layout.addWidget(self.fc_out_label)
        out_layout.addWidget(self.fc_out_input)
        out_layout.addWidget(self.fc_out_browse)
        layout.addLayout(out_layout)

        # 4. Nút Chạy
        self.fc_run_btn = QPushButton('🚀 TẠO FLASHCARD HSK')
        self.fc_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63; 
                color: white; 
                font-size: 14pt; padding: 15px; font-weight: bold;
            }
            QPushButton:hover { background-color: #C2185B; }
        """)
        self.fc_run_btn.clicked.connect(self._start_flashcard_gen)
        layout.addWidget(self.fc_run_btn)

        # 5. Log
        self.fc_log = QPlainTextEdit()
        self.fc_log.setReadOnly(True)
        layout.addWidget(QLabel('📋 Nhật ký xử lý:'))
        layout.addWidget(self.fc_log)

        tab.setLayout(layout)
        return tab

    def create_eng_flashcard_tab(self):
        """Tạo tab cho chức năng tạo ảnh English Flashcard."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Chọn file Excel
        excel_layout = QHBoxLayout()
        excel_layout.setSpacing(15)
        excel_layout.addWidget(QLabel('File Excel:'))
        self.eng_excel_input = QLineEdit()
        self.eng_excel_input.setPlaceholderText("Chọn file Excel flashcard tiếng Anh...")
        excel_layout.addWidget(self.eng_excel_input, 1)
        
        self.browse_eng_excel_btn = QPushButton('Chọn...')
        self.browse_eng_excel_btn.setStyleSheet("background-color: #28a745; min-width: 80px;")
        self.browse_eng_excel_btn.clicked.connect(self._browse_eng_excel_file)
        
        self.eng_template_btn = QPushButton('Mở File Mẫu')
        self.eng_template_btn.setStyleSheet("background-color: #17a2b8; min-width: 80px;")
        self.eng_template_btn.clicked.connect(self._open_eng_template)
        
        excel_layout.addWidget(self.browse_eng_excel_btn, 0)
        excel_layout.addWidget(self.eng_template_btn, 0)
        layout.addLayout(excel_layout)

        # 2. Chọn Sheet (Dropdown)
        sheet_layout = QHBoxLayout()
        self.eng_sheet_label = QLabel('Chọn Sheet:')
        self.eng_sheet_combo = QComboBox()
        self.eng_sheet_combo.setMinimumWidth(350) # Tăng độ rộng tối thiểu
        # Cho phép combobox hiển thị tên dài hơn nếu cần, thêm tooltip
        self.eng_sheet_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        
        self.eng_load_sheet_btn = QPushButton('🔄 Tải danh sách Sheet')
        self.eng_load_sheet_btn.clicked.connect(self._load_eng_sheets)
        sheet_layout.addWidget(self.eng_sheet_label)
        sheet_layout.addWidget(self.eng_sheet_combo, 1) # Cho phép combobox giãn ra
        sheet_layout.addWidget(self.eng_load_sheet_btn)
        layout.addLayout(sheet_layout)

        # 3. Chọn file Prompt
        prompt_layout = QHBoxLayout()
        prompt_layout.setSpacing(15)
        self.eng_prompt_label = QLabel('File Prompt:')
        self.eng_prompt_input = QLineEdit()
        default_prompt_path = os.path.join(os.getcwd(), "resources", "prompts", "image_eng_gen_flashcard.txt")
        self.eng_prompt_input.setText(default_prompt_path)
        
        self.eng_browse_prompt_btn = QPushButton('Chọn...')
        self.eng_browse_prompt_btn.setStyleSheet("background-color: #ffc107; color: black; min-width: 80px;")
        self.eng_browse_prompt_btn.clicked.connect(self._browse_eng_prompt)
        
        self.eng_open_prompt_btn = QPushButton('Mở File')
        self.eng_open_prompt_btn.setStyleSheet("background-color: #17a2b8; min-width: 80px;")
        self.eng_open_prompt_btn.clicked.connect(self._open_eng_prompt)

        prompt_layout.addWidget(self.eng_prompt_label)
        prompt_layout.addWidget(self.eng_prompt_input, 1)
        prompt_layout.addWidget(self.eng_browse_prompt_btn, 0)
        prompt_layout.addWidget(self.eng_open_prompt_btn, 0)
        layout.addLayout(prompt_layout)

        # 3.5 Checkbox options + chọn model audio
        from PyQt5.QtWidgets import QCheckBox
        cb_layout = QHBoxLayout()
        self.eng_error_only_cb = QCheckBox("Chỉ chạy các từ bị lỗi (có dữ liệu ở cột 'Note')")
        self.eng_error_only_cb.setStyleSheet("font-size: 11pt; font-weight: bold; color: #dc3545;")
        cb_layout.addWidget(self.eng_error_only_cb)

        # Combo chọn model TTS
        cb_layout.addWidget(QLabel("Model sinh audio:"))
        self.eng_audio_model_combo = QComboBox()
        self.eng_audio_model_combo.addItems(["Narakeet", "Chirp3-HD", "gemini-3.1-flash-tts-preview"])
        self.eng_audio_model_combo.setCurrentText("Narakeet")
        self.eng_audio_model_combo.setMinimumWidth(220)
        self.eng_audio_model_combo.setToolTip(
            "Chirp3-HD: ổn định, nhanh\n"
            "gemini-3.1-flash-tts-preview: tự nhiên hơn, hỗ trợ ngữ điệu tốt hơn\n"
            "Narakeet: dùng voice cố định Nữ Lisa, Nam Jeff"
        )
        cb_layout.addWidget(self.eng_audio_model_combo)

        cb_layout.addStretch()
        layout.addLayout(cb_layout)

        # 4. Nút chạy và dừng
        btn_layout = QHBoxLayout()
        self.eng_run_button = QPushButton('🚀 Bắt đầu tạo ảnh English Flashcard')
        self.eng_run_button.setStyleSheet("""
            QPushButton {
                background-color: #673AB7;
                color: white;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #5E35B1;
            }
        """)
        self.eng_run_button.clicked.connect(self._start_eng_flashcard_generation)
        
        self.eng_stop_button = QPushButton('🛑 Dừng')
        self.eng_stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.eng_stop_button.clicked.connect(self._stop_eng_flashcard_generation)
        self.eng_stop_button.setEnabled(False)

        btn_layout.addWidget(self.eng_run_button)
        btn_layout.addWidget(self.eng_stop_button)
        layout.addLayout(btn_layout)

        # 5. Log
        layout.addWidget(QLabel('📋 Nhật ký:'))
        self.eng_log_display = QPlainTextEdit()
        self.eng_log_display.setReadOnly(True)
        layout.addWidget(self.eng_log_display)

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
        # Lấy index: 0, 1 hoặc 2
        preproc_mode = self.preproc_combo.currentIndex()

        if not pdf_folder or not os.path.isdir(pdf_folder):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một thư mục PDF hợp lệ.')
            return

        # Vô hiệu hóa nút chạy và xóa log cũ
        self.run_button.setEnabled(False)
        self.run_button.setText('⏳ Đang xử lý...')
        self.log_display.clear()
        
        # Tạo và khởi chạy thread
        self.thread = QThread()
        self.worker = PipelineWorker(pdf_folder, hsk_level, preproc_mode)
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

        excel_dir = os.path.dirname(os.path.abspath(excel_path))
        excel_name = os.path.splitext(os.path.basename(excel_path))[0]
        output_folder = os.path.join(excel_dir, f"IMAGE_MERGED_{excel_name}")

        # Vô hiệu hóa nút ghép ảnh và xóa log cũ
        self.merge_button.setEnabled(False)
        self.merge_button.setText('⏳ Đang ghép ảnh...')
        self.merge_log_display.clear()
        
        # Tạo và khởi chạy thread
        self.merge_thread = QThread()
        self.merge_worker = ImageMergerWorker(excel_path, images_folder, output_folder)
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

    # --- SLOT CHO AUDIO TTS TAB ---
    def _browse_audio_tts_excel(self):
        """Chọn file Excel cho Audio TTS."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Chọn file Excel câu hỏi', '', 'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.audio_tts_excel_input.setText(file_path)

    def _browse_audio_tts_output(self):
        """Chọn folder output cho Audio TTS."""
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu Audio')
        if folder_path:
            self.audio_tts_output_input.setText(folder_path)

    def _start_audio_tts(self):
        """Bắt đầu chạy Audio TTS trong một luồng riêng."""
        excel_path = self.audio_tts_excel_input.text()
        output_folder = self.audio_tts_output_input.text()
        model_name = self.audio_tts_model_combo.currentText()
        male_voice = self.audio_tts_male_voice_combo.currentText()
        female_voice = self.audio_tts_female_voice_combo.currentText()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi', 'Vui lòng chọn file Excel hợp lệ.')
            return
        
        if not output_folder:
            QMessageBox.warning(self, 'Lỗi', 'Vui lòng chọn thư mục Output.')
            return

        # Disable nút và xóa log cũ
        self.audio_tts_run_button.setEnabled(False)
        self.audio_tts_run_button.setText('⏳ Đang xử lý...')
        self.audio_tts_log_display.clear()
        self.audio_tts_log_display.appendPlainText(">> Khởi động Audio TTS (Vertex AI)...")

        # Tạo Thread
        self.audio_tts_thread = QThread()
        self.audio_tts_worker = AudioTTSWorker(
            excel_path, 
            output_folder, 
            model_name=model_name,
            male_voice=male_voice,
            female_voice=female_voice
        )
        self.audio_tts_worker.moveToThread(self.audio_tts_thread)

        # Kết nối tín hiệu
        self.audio_tts_thread.started.connect(self.audio_tts_worker.run)
        self.audio_tts_worker.finished.connect(self._audio_tts_finished)
        self.audio_tts_worker.error.connect(self._audio_tts_error)
        self.audio_tts_worker.progress.connect(self._audio_tts_progress)

        # Dọn dẹp
        self.audio_tts_worker.error.connect(self.audio_tts_thread.quit)
        self.audio_tts_worker.error.connect(self.audio_tts_worker.deleteLater)
        self.audio_tts_worker.finished.connect(self.audio_tts_thread.quit)
        self.audio_tts_worker.finished.connect(self.audio_tts_worker.deleteLater)
        self.audio_tts_thread.finished.connect(self.audio_tts_thread.deleteLater)

        self.audio_tts_thread.start()

    def _audio_tts_progress(self, message):
        """Hàm nhận signal progress từ worker và ghi vào log."""
        self.audio_tts_log_display.appendPlainText(message)
        self.audio_tts_log_display.verticalScrollBar().setValue(
            self.audio_tts_log_display.verticalScrollBar().maximum()
        )

    def _audio_tts_finished(self, result_msg):
        """Xử lý khi Audio TTS chạy thành công."""
        self.audio_tts_run_button.setEnabled(True)
        self.audio_tts_run_button.setText('🎙️ Tạo Audio TTS (Vertex AI)')
        
        # trích thư mục audio từ thông điệp trả về (nếu có)
        audio_folder = None
        try:
            import re
            m = re.search(r"Folder audio:\s*(.+)", result_msg)
            if m:
                audio_folder = m.group(1).strip()
        except Exception:
            audio_folder = None

        # Hiển thị thông báo với nút mở folder
        reply = QMessageBox.information(
            self, 
            '✅ Hoàn thành', 
            f'{result_msg}\n\nBạn có muốn mở thư mục audio không?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            target = audio_folder or self.audio_tts_output_input.text()
            if os.path.exists(target):
                import subprocess
                import platform
                if platform.system() == 'Windows':
                    os.startfile(target)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', target])
                else:  # Linux
                    subprocess.Popen(['xdg-open', target])

    def _audio_tts_error(self, error_msg):
        """Xử lý khi Audio TTS gặp lỗi."""
        self.audio_tts_run_button.setEnabled(True)
        self.audio_tts_run_button.setText('🎙️ Tạo Audio TTS (Vertex AI)')
        QMessageBox.critical(self, 'Lỗi Audio TTS', f"Đã xảy ra lỗi:\n{error_msg}")    

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
        num_lessons = self.sum_num_lessons_input.value()

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
        self.sum_worker = SummaryWorker(pdf_path, prompt_path, num_lessons)
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

    def _browse_flashcard_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Excel", "", "Excel Files (*.xlsx *.xls)")
        if path:
            self.fc_excel_input.setText(path)
            self._load_sheets() # Tự động load sheet khi chọn file

    def _load_sheets(self):
        path = self.fc_excel_input.text()
        if not path or not os.path.exists(path): return
        
        try:
            input_mgr = InputDataManager(path)
            sheets = input_mgr.get_hsk_sheets()
            self.fc_sheet_combo.clear()
            if sheets:
                self.fc_sheet_combo.addItems(sheets)
                QMessageBox.information(self, "Thành công", f"Tìm thấy {len(sheets)} sheet HSK.")
            else:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy sheet nào có chữ 'HSK'.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _start_flashcard_gen(self):
        excel = self.fc_excel_input.text()
        sheet = self.fc_sheet_combo.currentText()
        out_dir = self.fc_out_input.text()

        if not excel or not sheet:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn File Excel và Sheet.")
            return

        self.fc_run_btn.setEnabled(False)
        self.fc_run_btn.setText("⏳ Đang chạy...")
        self.fc_log.clear()

        # Thread Setup
        self.fc_thread = QThread()
        self.fc_worker = FlashcardWorker(excel, sheet, out_dir)
        self.fc_worker.moveToThread(self.fc_thread)

        self.fc_thread.started.connect(self.fc_worker.run)
        self.fc_worker.progress.connect(lambda text: self.fc_log.appendPlainText(text)) # Update Log trực tiếp
        self.fc_worker.finished.connect(self._finish_flashcard)
        self.fc_worker.error.connect(lambda err: self.fc_log.appendPlainText(f"❌ {err}"))
        
        # Cleanup
        self.fc_worker.finished.connect(self.fc_thread.quit)
        self.fc_worker.error.connect(self.fc_thread.quit)
        self.fc_thread.finished.connect(self.fc_thread.deleteLater)

        self.fc_thread.start()

    def _finish_flashcard(self, msg):
        self.fc_run_btn.setEnabled(True)
        self.fc_run_btn.setText("🚀 TẠO FLASHCARD HSK")
        QMessageBox.information(self, "Hoàn tất", msg)

    def _browse_eng_excel_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.eng_excel_input.setText(file_path)
            self._load_eng_sheets()

    def _open_local_path(self, target_path, missing_message, open_error_title="Không thể mở file"):
        if not os.path.exists(target_path):
            QMessageBox.warning(self, "Lỗi", missing_message)
            return

        try:
            if os.name == 'nt':
                os.startfile(target_path)
                return

            import shutil
            import subprocess

            opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
            if not shutil.which(opener):
                raise FileNotFoundError(f"Không tìm thấy công cụ '{opener}' để mở file.")

            subprocess.Popen([opener, target_path])
        except Exception as e:
            QMessageBox.warning(
                self,
                open_error_title,
                f"Không thể mở file:\n{target_path}\n\nChi tiết: {e}"
            )

    def _open_eng_template(self):
        template_path = os.path.join(os.getcwd(), "resources", "sheet", "eng_flashcard_gen_template.xlsx")
        self._open_local_path(
            template_path,
            "Không tìm thấy file mẫu tại resources/sheet!",
            "Không thể mở file mẫu Excel"
        )

    def _browse_eng_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file Prompt", "", "Text Files (*.txt)")
        if file_path:
            self.eng_prompt_input.setText(file_path)

    def _open_eng_prompt(self):
        prompt_path = self.eng_prompt_input.text().strip()
        self._open_local_path(
            prompt_path,
            "Không tìm thấy file prompt! Vui lòng chọn đường dẫn hợp lệ.",
            "Không thể mở file prompt"
        )

    def _load_eng_sheets(self):
        path = self.eng_excel_input.text().strip()
        if not path or not os.path.exists(path): return
        
        try:
            xls = pd.ExcelFile(path)
            sheets = [s for s in xls.sheet_names if s.strip().lower() != "yêu cầu"]
            self.eng_sheet_combo.clear()
            if sheets:
                self.eng_sheet_combo.addItem("Tất cả các sheet")
                self.eng_sheet_combo.setItemData(0, "Chạy tạo ảnh cho tất cả các sheet", Qt.ToolTipRole)
                for sheet in sheets:
                    self.eng_sheet_combo.addItem(sheet)
                    # Gắn tooltip cho từng item trong dropdown để khi hover hiện full tên
                    self.eng_sheet_combo.setItemData(self.eng_sheet_combo.count() - 1, sheet, Qt.ToolTipRole)
                self.eng_log_display.appendPlainText(f">> Đã tự động tìm thấy {len(sheets)} sheet.")
            else:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy sheet hợp lệ.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi đọc sheet: {e}")

    def _start_eng_flashcard_generation(self):
        excel_path = self.eng_excel_input.text().strip()
        sheet_name = self.eng_sheet_combo.currentText()
        prompt_path = self.eng_prompt_input.text().strip()

        if not excel_path or not sheet_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file Excel và Sheet đầu vào!")
            return
            
        if not prompt_path or not os.path.exists(prompt_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file Prompt hợp lệ!")
            return

        self.eng_log_display.clear()
        self.eng_run_button.setEnabled(False)
        self.eng_stop_button.setEnabled(True)

        # Chuẩn bị danh sách sheet cần chạy
        sheets_to_run = []
        if sheet_name == "Tất cả các sheet":
            for i in range(1, self.eng_sheet_combo.count()):
                sheets_to_run.append(self.eng_sheet_combo.itemText(i))
        else:
            sheets_to_run = [sheet_name]

        error_only = self.eng_error_only_cb.isChecked()
        gen_audio = True
        audio_model = self.eng_audio_model_combo.currentText()

        # Cập nhật label nút chạy
        self.eng_run_button.setText('⏳ Đang tạo ảnh & audio...')

        # Khởi tạo thread và worker
        self.eng_thread = QThread()
        self.eng_worker = EngFlashcardWorker(excel_path, sheets_to_run, prompt_path, error_only, gen_audio, audio_model)
        self.eng_worker.moveToThread(self.eng_thread)

        # Kết nối tín hiệu
        self.eng_thread.started.connect(self.eng_worker.run)
        self.eng_worker.progress.connect(lambda msg: self.eng_log_display.appendPlainText(msg))
        self.eng_worker.finished.connect(self._on_eng_flashcard_finished)
        self.eng_worker.error.connect(self._on_eng_flashcard_error)
        
        # Dọn dẹp
        self.eng_worker.error.connect(self.eng_thread.quit)
        self.eng_worker.error.connect(self.eng_worker.deleteLater)
        self.eng_worker.finished.connect(self.eng_thread.quit)
        self.eng_worker.finished.connect(self.eng_worker.deleteLater)
        self.eng_thread.finished.connect(self.eng_thread.deleteLater)

        self.eng_thread.start()

    def _stop_eng_flashcard_generation(self):
        reply = QMessageBox.question(
            self, 'Xác nhận Dừng', 
            'Bạn có chắc chắn muốn dừng tạo ảnh?\nQuá trình sẽ dừng lại sau khi hoàn thành ảnh hiện tại.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if hasattr(self, 'eng_worker') and self.eng_worker:
                self.eng_worker.stop()
                self.eng_log_display.appendPlainText(">> Đang gửi lệnh dừng tới hệ thống, vui lòng chờ ảnh cuối cùng...")
                self.eng_stop_button.setEnabled(False)

    def _on_eng_flashcard_finished(self, message):
        self.eng_run_button.setEnabled(True)
        self.eng_run_button.setText('🚀 Bắt đầu tạo ảnh English Flashcard')
        self.eng_stop_button.setEnabled(False)
        QMessageBox.information(self, "Thành công", message)

        # Mở thư mục chứa kết quả
        try:
            import re
            # Trích xuất đường dẫn từ message "Hoàn tất! Đã tạo thành công X ảnh tại:\n[Đường_dẫn]"
            match = re.search(r"tại:\n(.*)", message)
            if match:
                folder_path = match.group(1).strip()
                if os.path.exists(folder_path):
                    if os.name == 'nt':
                        os.startfile(folder_path)
                    elif sys.platform == 'darwin':
                        import subprocess
                        subprocess.Popen(['open', folder_path])
                    else:
                        import subprocess
                        subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            self.eng_log_display.appendPlainText(f">> Không thể tự động mở thư mục: {e}")

    def _on_eng_flashcard_error(self, error_msg):
        self.eng_run_button.setEnabled(True)
        self.eng_run_button.setText('🚀 Bắt đầu tạo ảnh English Flashcard')
        self.eng_stop_button.setEnabled(False)
        self.eng_log_display.appendPlainText(f"\n❌ LỖI HỆ THỐNG:\n{error_msg}")
        QMessageBox.critical(self, "Lỗi", "Đã xảy ra lỗi trong quá trình thực hiện!")

    def create_ppt_gen_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Input PDF
        pdf_layout = QHBoxLayout()
        self.ppt_pdf_label = QLabel('File PDF Bài học:')
        self.ppt_pdf_input = QLineEdit()
        self.ppt_pdf_browse_btn = QPushButton('Chọn...')
        self.ppt_pdf_browse_btn.setStyleSheet("background-color: #28a745;")
        self.ppt_pdf_browse_btn.clicked.connect(self._browse_ppt_pdf)
        pdf_layout.addWidget(self.ppt_pdf_label)
        pdf_layout.addWidget(self.ppt_pdf_input)
        pdf_layout.addWidget(self.ppt_pdf_browse_btn)
        layout.addLayout(pdf_layout)

        # 2. HSK Level & PPT Type
        level_layout = QHBoxLayout()
        self.ppt_level_label = QLabel('Cấp độ HSK:')
        self.ppt_level_combo = QComboBox()
        self.ppt_level_combo.addItems(["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"])
        
        self.ppt_type_label = QLabel('Loại PPT:')
        self.ppt_type_combo = QComboBox()
        self.ppt_type_combo.addItems(["Cả hai", "Bài khóa", "Ngữ pháp"])

        level_layout.addWidget(self.ppt_level_label)
        level_layout.addWidget(self.ppt_level_combo)
        level_layout.addSpacing(20)
        level_layout.addWidget(self.ppt_type_label)
        level_layout.addWidget(self.ppt_type_combo)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 3. Output Folder
        out_layout = QHBoxLayout()
        self.ppt_out_label = QLabel('Thư mục Output:')
        self.ppt_out_input = QLineEdit()
        self.ppt_out_input.setText(os.path.join(os.getcwd(), "output", "ppt_hsk"))
        self.ppt_out_browse = QPushButton('Chọn...')
        self.ppt_out_browse.clicked.connect(self._browse_ppt_out)
        out_layout.addWidget(self.ppt_out_label)
        out_layout.addWidget(self.ppt_out_input)
        out_layout.addWidget(self.ppt_out_browse)
        layout.addLayout(out_layout)

        # 4. Nút Chạy và Nút Mở thư mục
        btn_layout = QHBoxLayout()
        self.ppt_run_btn = QPushButton('🚀 TẠO PPT HSK')
        self.ppt_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                font-size: 14pt; padding: 15px; font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #C2185B; }
        """)
        self.ppt_run_btn.clicked.connect(self._start_ppt_gen)
        
        self.ppt_open_btn = QPushButton('📂 Mở thư mục')
        self.ppt_open_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-size: 14pt; padding: 15px; font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        self.ppt_open_btn.clicked.connect(self._open_ppt_out)
        self.ppt_open_btn.setEnabled(False) # Chỉ bật khi làm xong

        btn_layout.addWidget(self.ppt_run_btn)
        btn_layout.addWidget(self.ppt_open_btn)
        layout.addLayout(btn_layout)

        # 5. Text Log
        self.ppt_log = QPlainTextEdit()
        self.ppt_log.setReadOnly(True)
        self.ppt_log.setStyleSheet("background-color: #f8f9fa; font-family: Consolas; font-size: 11pt;")
        layout.addWidget(self.ppt_log)

        tab.setLayout(layout)
        return tab

    def _browse_ppt_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Chọn file PDF Bài học', '', 'PDF Files (*.pdf)')
        if file_path:
            self.ppt_pdf_input.setText(file_path)

    def _browse_ppt_out(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Output")
        if folder_path:
            self.ppt_out_input.setText(folder_path)

    def _open_ppt_out(self):
        out_dir = self.ppt_out_input.text()
        if os.path.exists(out_dir):
            if os.name == 'nt':
                os.startfile(out_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', out_dir])
            else:
                subprocess.Popen(['xdg-open', out_dir])
        else:
            QMessageBox.warning(self, "Lỗi", "Thư mục không tồn tại!")

    def _start_ppt_gen(self):
        pdf_path = self.ppt_pdf_input.text().strip()
        out_dir = self.ppt_out_input.text().strip()
        hsk_level = self.ppt_level_combo.currentText()
        ppt_type = self.ppt_type_combo.currentText()

        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file PDF hợp lệ.")
            return

        os.makedirs(out_dir, exist_ok=True)

        self.ppt_run_btn.setEnabled(False)
        self.ppt_open_btn.setEnabled(False)
        self.ppt_run_btn.setText("⏳ Đang chạy...")
        self.ppt_log.clear()

        # Thread Setup
        self.ppt_thread = QThread()
        self.ppt_worker = PPTGeneratorWorker(pdf_path, out_dir, hsk_level, ppt_type)
        self.ppt_worker.moveToThread(self.ppt_thread)

        self.ppt_thread.started.connect(self.ppt_worker.run)
        self.ppt_worker.progress.connect(lambda text: self.ppt_log.appendPlainText(text)) 
        self.ppt_worker.finished.connect(self._finish_ppt_gen)
        self.ppt_worker.error.connect(lambda err: self.ppt_log.appendPlainText(f"❌ {err}"))
        self.ppt_worker.error.connect(self._finish_ppt_error)

        # Cleanup
        self.ppt_worker.finished.connect(self.ppt_thread.quit)
        self.ppt_worker.error.connect(self.ppt_thread.quit)
        self.ppt_thread.finished.connect(self.ppt_thread.deleteLater)

        self.ppt_thread.start()

    def _finish_ppt_error(self):
        self.ppt_run_btn.setEnabled(True)
        self.ppt_run_btn.setText("🚀 TẠO PPT HSK")

    def _finish_ppt_gen(self, msg):
        self.ppt_run_btn.setEnabled(True)
        self.ppt_open_btn.setEnabled(True)
        self.ppt_run_btn.setText("🚀 TẠO PPT HSK")
        self.ppt_log.appendPlainText("✅ HOÀN TẤT TẠO PPT!")
        QMessageBox.information(self, "Hoàn tất", f"Đã tạo xong PPT.\nThư mục: {msg}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Thiết lập font mặc định cho toàn bộ ứng dụng
    font = QFont("Arial", 10)
    app.setFont(font)
    
    ex = HSKGeneratorApp()
    ex.show()
    sys.exit(app.exec_())