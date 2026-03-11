import os
import re
import io
import pandas as pd
from google.cloud import texttospeech
from google.oauth2 import service_account
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# PHẦN 1: XỬ LÝ VĂN BẢN (PROCESSOR)
# ==========================================
class HSKTextProcessor:
    def __init__(self):
        self.chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
        self.question_numbers = {i: f"第{self._to_chinese_num(i)}题" for i in range(1, 21)}

    def _to_chinese_num(self, n):
        nums =["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        if n <= 10: return nums[n]
        if n < 20: return "十" + nums[n%10]
        if n == 20: return "二十"
        return str(n)

    def is_contains_chinese(self, text):
        if not text or not isinstance(text, str): return False
        return bool(self.chinese_char_pattern.search(text))

    def is_option_line(self, text):
        if "√" in text: return True
        if re.match(r'^[A-C][\s\.]', text.strip()): return True
        return False

    def clean_tags(self, text, remove_all=False):
        if not text: return ""
        text = text.replace("问：", "").replace("问:", "").strip()
        if remove_all:
            tags = ["女：", "女:", "男：", "男:"]
            for tag in tags:
                text = text.replace(tag, "")
        return text.strip()

    def extract_clean_chinese(self, text_block):
        if not text_block or not isinstance(text_block, str): return []
        lines = text_block.split('\n')
        return[l.strip() for l in lines if self.is_contains_chinese(l) and "http" not in l.lower() and not self.is_option_line(l)]

    def build_script(self, col_f, col_i, q_idx):
        script =[]
        text_i_raw = str(col_i).split("Phụ đề:")[1].split("Tạm dịch:")[0] if "Phụ đề:" in str(col_i) else ""
        text_i = self.extract_clean_chinese(text_i_raw)
        text_f = self.extract_clean_chinese(col_f)

        # LƯU Ý MỚI: Zephyr = Nữ, Charon = Nam, Leda = Dẫn chuyện

        # CÂU 1 - 8 (Câu đơn: Nam đọc 1 dòng, Nữ đọc 1 dòng)
        if 1 <= q_idx <= 8:
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            if text_i:
                content = self.clean_tags(text_i[0], remove_all=True)
                script.extend([{'v': 'Charon', 't': content}, {'v': 'Zephyr', 't': content}])

        # CÂU 9 - 12 (Cặp thoại)
        elif 9 <= q_idx <= 12:
            if q_idx == 9: script.append({'v': 'Leda', 't': "第九题到十二题是根据下面一段话。"})
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            block =[]
            for i, line in enumerate(text_i):
                # Bắt chính xác tag để không bị nhầm khi trong câu có chữ "Nữ" hoặc "Nam"
                if "女：" in line or "女:" in line:
                    v = 'Zephyr' # Nữ
                elif "男：" in line or "男:" in line:
                    v = 'Charon' # Nam
                else:
                    # Nếu file Excel vô tình thiếu Tag, tự động gán luân phiên để chống lỗi
                    v = 'Charon' if i % 2 == 0 else 'Zephyr'
                
                block.append({'v': v, 't': self.clean_tags(line, remove_all=True)})
            script.extend(block * 2)

        # CÂU 13 (Cột F có ví dụ)
        elif q_idx == 13:
            if len(text_f) >= 1: script.append({'v': 'Leda', 't': text_f[0]}) # Dòng ví dụ
            if len(text_f) >= 2: script.append({'v': 'Zephyr', 't': self.clean_tags(text_f[1])}) # Câu hỏi -> Nữ
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            
            # Cột I: Dòng 1 Nội dung (Nam), Dòng 2 Câu hỏi (Nữ)
            if len(text_i) >= 2:
                block =[{'v': 'Charon', 't': self.clean_tags(text_i[0], remove_all=True)},
                         {'v': 'Zephyr', 't': self.clean_tags(text_i[1], remove_all=True)}]
                script.extend(block * 2)

        # CÂU 14 TRỞ ĐI
        elif q_idx >= 14:
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            # Cột I: Dòng 1 Nội dung (Nam), Dòng 2 Câu hỏi (Nữ)
            if len(text_i) >= 2:
                block =[{'v': 'Charon', 't': self.clean_tags(text_i[0], remove_all=True)},
                         {'v': 'Zephyr', 't': self.clean_tags(text_i[1], remove_all=True)}]
                script.extend(block * 2)
            elif text_i:
                content = self.clean_tags(text_i[0], remove_all=True)
                script.extend([{'v': 'Charon', 't': content}, {'v': 'Zephyr', 't': content}])
        return script

# ==========================================
# PHẦN 2: TẠO ÂM THANH (AUDIO GENERATOR)
# ==========================================
class VertexAudioGenerator:
    # Danh sách các model name hỗ trợ
    SUPPORTED_MODELS = ['gemini-2.5-pro-tts', 'gemini-2.5-flash-tts', 'Chirp3-HD']
    
    # Danh sách voice nam và nữ
    MALE_VOICES = ['Charon', 'Orus', 'Enceladus']
    FEMALE_VOICES = ['Zephyr', 'Leda', 'Carrllihoe']
    NARRATOR_VOICE = 'Leda'  # Voice dùng cho dẫn chuyện, câu số, ví dụ
    
    def __init__(self, model_name='Chirp3-HD', male_voice='Charon', female_voice='Zephyr'):
        """
        Args:
            model_name: Một trong SUPPORTED_MODELS
            male_voice: Voice nam từ MALE_VOICES
            female_voice: Voice nữ từ FEMALE_VOICES
        """
        self.model_name = model_name if model_name in self.SUPPORTED_MODELS else 'Chirp3-HD'
        self.male_voice = male_voice if male_voice in self.MALE_VOICES else 'Charon'
        self.female_voice = female_voice if female_voice in self.FEMALE_VOICES else 'Zephyr'
        self.narrator_voice = self.NARRATOR_VOICE
        
        self.client = self._init_client()
        self.silence = AudioSegment.silent(duration=1000)
        self.language_code = "cmn-CN"

    def _init_client(self):
        creds = service_account.Credentials.from_service_account_info({
            "type": os.getenv("TYPE"),
            "project_id": os.getenv("PROJECT_ID"),
            "private_key_id": os.getenv("PRIVATE_KEY_ID"),
            "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n'),
            "client_email": os.getenv("CLIENT_EMAIL"),
            "client_id": os.getenv("CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        return texttospeech.TextToSpeechClient(credentials=creds)

    def _get_voice_name(self, voice_key):
        """
        Lấy tên voice dựa vào model_name được chọn.
        
        Nếu Chirp3-HD: trả về {language_code}-{model_name}-{voice} (e.g., cmn-CN-Chirp3-HD-Charon)
        Nếu gemini: trả về {voice} (e.g., Charon)
        """
        if self.model_name == 'Chirp3-HD':
            return f"{self.language_code}-{self.model_name}-{voice_key}"
        else:
            # Cho các model gemini, chỉ dùng tên voice
            return voice_key

    def _build_voice_params(self, voice_key):
        """
        Xây dựng VoiceSelectionParams dựa trên model_name.
        
        Nếu model là gemini: 3 tham số (language_code, name, model_name)
        Nếu model là Chirp3-HD: 2 tham số (language_code, name)
        """
        voice_name = self._get_voice_name(voice_key)
        
        if self.model_name in ['gemini-2.5-pro-tts', 'gemini-2.5-flash-tts']:
            # API Gemini yêu cầu model_name trong VoiceSelectionParams
            return texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=voice_name,
                model_name=self.model_name
            )
        else:
            # Chirp3-HD chỉ dùng language_code và name
            return texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=voice_name
            )

    def _map_voice_key(self, voice_role):
        """
        Map voice role ('Leda', 'Charon', 'Zephyr') thành voice thực tế được chọn.
        """
        voice_map = {
            'Leda': self.narrator_voice,
            'Charon': self.male_voice,
            'Zephyr': self.female_voice
        }
        return voice_map.get(voice_role, self.male_voice)

    def generate_single(self, text, v_role):
        """
        Tạo audio cho một đoạn text với voice role nhất định.
        
        Args:
            text: Nội dung cần phát âm
            v_role: Role voice ('Leda' cho dẫn chuyện, 'Charon' cho nam, 'Zephyr' cho nữ)
        """
        input_text = texttospeech.SynthesisInput(text=text)
        
        # Map role thành voice thực tế
        actual_voice = self._map_voice_key(v_role)
        
        # Xây dựng VoiceSelectionParams dựa trên model
        voice = self._build_voice_params(actual_voice)
        
        config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        res = self.client.synthesize_speech(input=input_text, voice=voice, audio_config=config)
        return AudioSegment.from_file(io.BytesIO(res.audio_content), format="mp3")

    def create_audio(self, script, out_path):
        """
        Tạo audio file từ script.
        
        Args:
            script: List of {'v': role, 't': text}
            out_path: Đường dẫn lưu file MP3
        """
        combined = AudioSegment.empty()
        for i, item in enumerate(script):
            seg = self.generate_single(item['t'], item['v'])
            combined += seg
            if i < len(script) - 1: 
                combined += self.silence
        combined.export(out_path, format="mp3")
        return os.path.abspath(out_path)

# ==========================================
# PHẦN 3: HÀM CHẠY TEST (MAIN RUNNER)
# ==========================================
def test_file(excel_path, output_dir, model_name='Chirp3-HD', male_voice='Charon', female_voice='Zephyr', log_fn=print):
    """
    Xử lý file Excel và tạo audio tương ứng.

    Args:
        excel_path: Đường dẫn file Excel input
        output_dir: Root thư mục lưu audio output (ví dụ "output")
        model_name: Model TTS (gemini-2.5-pro-tts, gemini-2.5-flash-tts, Chirp3-HD)
        male_voice: Voice nam (Charon, Orus, Enceladus)
        female_voice: Voice nữ (Zephyr, Leda, Carrllihoe)
        log_fn: hàm để nhận thông điệp tiến độ (mặc định là print)
    """    # xác định tên folder con dựa trên tên file input
    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    audio_folder = os.path.join(output_dir, "audio", base_name)
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder, exist_ok=True)

    # tạo bản sao Excel bằng pywin32 để không làm mất định dạng
    dest_excel = os.path.join(audio_folder, f"{base_name}_Result_Final.xlsx")
    try:
        import win32com.client as win32
        excel_app = win32.gencache.EnsureDispatch('Excel.Application')
        excel_app.DisplayAlerts = False
        wb_copy = excel_app.Workbooks.Open(os.path.abspath(excel_path))
        wb_copy.SaveAs(os.path.abspath(dest_excel))
        wb_copy.Close(False)
        excel_app.Quit()
    except Exception as e:
        # nếu pywin32 không tồn tại, fallback về sao chép file bình thường
        import shutil
        shutil.copy2(excel_path, dest_excel)

    # dùng pandas đọc dữ liệu từ bản sao để xử lý nội dung
    df = pd.read_excel(dest_excel)

    # khởi tạo processor/generator giống như trước
    processor = HSKTextProcessor()
    generator = VertexAudioGenerator(model_name=model_name, male_voice=male_voice, female_voice=female_voice)

    group_9_12_script = []
    log_fn("--- Bắt đầu xử lý file ---")
    log_fn(f"Model: {model_name} | Voice Nam: {male_voice} | Voice Nữ: {female_voice}")

    # nếu pywin32 thành công ở trên, mở file để cập nhật đường dẫn trực tiếp
    excel_updater = None
    try:
        import win32com.client as win32
        excel_app = win32.gencache.EnsureDispatch('Excel.Application')
        excel_app.DisplayAlerts = False
        workbook = excel_app.Workbooks.Open(os.path.abspath(dest_excel))
        worksheet = workbook.Worksheets(1)
        excel_updater = (excel_app, workbook, worksheet)
    except Exception:
        excel_updater = None

    for idx, row in df.iterrows():
        q_idx = idx + 1  # Dòng 2 Excel là Câu 1
        col_f, col_i = row.iloc[5], row.iloc[8]
        if "Phụ đề:" not in str(col_i):
            continue

        script = processor.build_script(col_f, col_i, q_idx)
        if 9 <= q_idx <= 12:
            group_9_12_script.extend(script)
            if q_idx == 12:
                path = generator.create_audio(group_9_12_script, os.path.join(audio_folder, "Câu_9_12.mp3"))
                for r in range(idx - 3, idx + 1):
                    if r < len(df):
                        # cập nhật dataframe để giữ track
                        df.iloc[r, 10] = path
                        # viết vào file Excel qua COM nếu có
                        if excel_updater:
                            excel_row = r + 2
                            excel_updater[2].Cells(excel_row, 11).Value = path
                log_fn("Đã xong cụm Câu 9-12")
        else:
            path = generator.create_audio(script, os.path.join(audio_folder, f"Câu_{q_idx}.mp3"))
            if idx < len(df):
                df.iloc[idx, 10] = path
                if excel_updater:
                    excel_updater[2].Cells(idx + 2, 11).Value = path
            log_fn(f"Đã xong Câu {q_idx}")

    # lưu kết quả nếu không dùng COM, otherwise COM đã lưu trực tiếp
    if not excel_updater:
        df.to_excel(dest_excel, index=False)
    else:
        workbook.Save()
        workbook.Close(False)
        excel_app.Quit()

    log_fn(f"\n--- HOÀN THÀNH ---")
    log_fn(f"File kết quả: {dest_excel}")

    # trả về đường dẫn folder audio và file excel kết quả
    return audio_folder, dest_excel

if __name__ == "__main__":
    # Thay đổi đường dẫn file test tại đây
    EXCEL_INPUT = r"D:\Edmicro\Tools\create_hsk\input\Bài 13.xlsx" 
    # folder gốc 'output'; hàm sẽ tạo subfolder audio/<basename>
    FOLDER_AUDIO = os.path.join(".", "output")
    
    test_file(EXCEL_INPUT, FOLDER_AUDIO)