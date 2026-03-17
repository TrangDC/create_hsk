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
    def __init__(self, exam_type=1):
        self.chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
        # Tăng range lên 50 để an toàn cho đề có số câu dài hơn
        self.question_numbers = {i: f"第{self._to_chinese_num(i)}题" for i in range(1, 51)}
        self.exam_type = exam_type

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

        # 1. KIỂM TRA DẠNG CÂU ĐƠN (Nam đọc 1 dòng, Nữ đọc 1 dòng)
        is_single = False
        if self.exam_type == 1 and 1 <= q_idx <= 8: is_single = True
        elif self.exam_type == 2 and 13 <= q_idx <= 20: is_single = True
        elif self.exam_type == 3 and 16 <= q_idx <= 20: is_single = True

        if is_single:
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            if text_i:
                content = self.clean_tags(text_i[0], remove_all=True)
                script.extend([{'v': 'Charon', 't': content}, {'v': 'Zephyr', 't': content}])
            return script

        # 2. KIỂM TRA DẠNG GỘP NHÓM (Chỉ áp dụng cho Type 1: Câu 9-12)
        if self.exam_type == 1 and 9 <= q_idx <= 12:
            if q_idx == 9: script.append({'v': 'Leda', 't': "第九题到十二题是根据下面一段话。"})
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            block =[]
            for i, line in enumerate(text_i):
                if "女：" in line or "女:" in line: v = 'Zephyr'
                elif "男：" in line or "男:" in line: v = 'Charon'
                else: v = 'Charon' if i % 2 == 0 else 'Zephyr'
                block.append({'v': v, 't': self.clean_tags(line, remove_all=True)})
            script.extend(block * 2)
            return script

        # 3. KIỂM TRA DẠNG CÓ VÍ DỤ (Chỉ áp dụng cho Type 1: Câu 13)
        if self.exam_type == 1 and q_idx == 13:
            if len(text_f) >= 1: script.append({'v': 'Leda', 't': text_f[0]})
            if len(text_f) >= 2: script.append({'v': 'Zephyr', 't': self.clean_tags(text_f[1])})
            script.append({'v': 'Leda', 't': self.question_numbers[q_idx]})
            if len(text_i) >= 2:
                block =[{'v': 'Charon', 't': self.clean_tags(text_i[0], remove_all=True)},
                         {'v': 'Zephyr', 't': self.clean_tags(text_i[1], remove_all=True)}]
                script.extend(block * 2)
            return script

        # 4. CÁC CÂU CÒN LẠI (MẶC ĐỊNH LÀ ĐỐI THOẠI)
        script.append({'v': 'Leda', 't': self.question_numbers.get(q_idx, f"第{q_idx}题")})
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
def test_file(excel_path, output_dir, model_name='Chirp3-HD', male_voice='Charon', female_voice='Zephyr', log_fn=print, exam_type=1):
    """
    Xử lý file Excel và tạo audio tương ứng.

    Args:
        excel_path: Đường dẫn file Excel input
        output_dir: Root thư mục lưu audio output (ví dụ "output")
        model_name: Model TTS (gemini-2.5-pro-tts, gemini-2.5-flash-tts, Chirp3-HD)
        male_voice: Voice nam (Charon, Orus, Enceladus)
        female_voice: Voice nữ (Zephyr, Leda, Carrllihoe)
        log_fn: hàm để nhận thông điệp tiến độ (mặc định là print)
        exam_type: Dạng cấu trúc đề (1: Dạng cũ, 2: Câu 13-20 là câu đơn, 3: Câu 16-20 là câu đơn)
    """    # xác định tên folder con dựa trên tên file input
    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    audio_folder = os.path.join(output_dir, "audio", base_name)
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder, exist_ok=True)

    # dùng pandas đọc dữ liệu từ file để xử lý nội dung
    df = pd.read_excel(excel_path)

    # khởi tạo processor/generator
    processor = HSKTextProcessor(exam_type=exam_type)
    generator = VertexAudioGenerator(model_name=model_name, male_voice=male_voice, female_voice=female_voice)

    group_9_12_script = []
    group_9_12_filename = "Câu_9_12"
    log_fn("--- Bắt đầu xử lý file ---")
    log_fn(f"Model: {model_name} | Voice Nam: {male_voice} | Voice Nữ: {female_voice}")

    for idx, row in df.iterrows():
        q_idx = idx + 1  # Dòng 2 Excel là Câu 1
        col_b, col_f, col_i = row.iloc[1], row.iloc[5], row.iloc[8]
        if "Phụ đề:" not in str(col_i):
            continue

        # Lấy tên file từ cột F
        file_name = f"Câu_{q_idx}"
        if isinstance(col_f, str):
            url_match = re.search(r'URL:\s*([^\n\r]+)', col_f, re.IGNORECASE)
            if url_match:
                file_name = url_match.group(1).strip()
                if file_name.lower().endswith('.mp3'):
                    file_name = file_name[:-4].strip()

        script = processor.build_script(col_f, col_i, q_idx)
        if exam_type == 1 and 9 <= q_idx <= 12:
            group_9_12_script.extend(script)
            if q_idx == 9:
                if isinstance(col_b, str):
                    lines = [l.strip() for l in col_b.split('\n') if l.strip()]
                    for l in lines:
                        if "audio" not in l.lower():
                            group_9_12_filename = l
                            break
                    else:
                        if lines: group_9_12_filename = lines[-1]
                    
                    if group_9_12_filename.lower().endswith('.mp3'):
                        group_9_12_filename = group_9_12_filename[:-4].strip()
            if q_idx == 12:
                path = generator.create_audio(group_9_12_script, os.path.join(audio_folder, f"{group_9_12_filename}.mp3"))
                log_fn(f"Đã xong cụm Câu 9-12 (File: {group_9_12_filename}.mp3)")
        else:
            path = generator.create_audio(script, os.path.join(audio_folder, f"{file_name}.mp3"))
            log_fn(f"Đã xong Câu {q_idx} (File: {file_name}.mp3)")

    log_fn(f"\n--- HOÀN THÀNH ---")

    # trả về đường dẫn folder audio
    return audio_folder