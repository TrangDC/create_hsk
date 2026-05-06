import os
import re
import io
import pandas as pd
from google.cloud import texttospeech
from google.oauth2 import service_account
from pydub import AudioSegment
from dotenv import load_dotenv
import openpyxl

load_dotenv()

# ==========================================
# PHẦN 1: XỬ LÝ VĂN BẢN (PROCESSOR)
# ==========================================
class HSKTextProcessor:
    def __init__(self):
        self.chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
        # Tăng range lên 100 để an toàn cho đề có số câu dài hơn
        self.question_numbers = {i: f"第{self._to_chinese_num(i)}题" for i in range(1, 101)}

    def _to_chinese_num(self, n):
        nums = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        if n <= 10: return nums[n]
        if n < 20: return "十" + nums[n%10]
        if n < 100:
            tens = n // 10
            ones = n % 10
            if ones == 0: return nums[tens] + "十"
            return nums[tens] + "十" + nums[ones]
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
        lines = str(text_block).split('\n')
        return [l.strip() for l in lines if self.is_contains_chinese(l) and "http" not in l.lower() and not self.is_option_line(l)]

    def build_script(self, row_data, is_first_in_group=False, is_merged_group=False, is_last_in_group=False):
        """
        Xây dựng kịch bản cho một câu hỏi.
        row_data: {q_idx, text_i, text_f, ...}
        """
        script = []
        q_idx = row_data['q_idx']
        text_i = row_data['text_i']
        text_f = row_data['text_f']

        # 1. Xử lý Intro/Ví dụ nếu là câu đầu tiên của nhóm
        if is_first_in_group:
            if is_merged_group:
                # Dạng gộp nhóm (như 9-12 cũ)
                is_dialogue = any(re.search(r'(男|女)[：:]', line) for line in text_i)
                intro_text = "一段对话" if is_dialogue else "一段话"
                # Sẽ replace "...题" bằng end_q ở lớp ngoài
                script.append({'v': 'Leda', 't': f"第{self._to_chinese_num(q_idx)}题到第...题是根据下面{intro_text}。", 'delay_after': 5000})
            elif text_f:
                # Dạng có ví dụ (như 13 cũ)
                if len(text_f) >= 1:
                    delay = 1200 if len(text_f) >= 2 else 15000
                    script.append({'v': 'Leda', 't': text_f[0], 'delay_after': delay})
                if len(text_f) >= 2:
                    script.append({'v': 'Zephyr', 't': self.clean_tags(text_f[1]), 'delay_after': 15000})

        # 2. Đọc số câu
        script.append({'v': 'Leda', 't': self.question_numbers.get(q_idx, f"第{q_idx}题"), 'delay_after': 1500})

        # 3. Đọc nội dung chính
        if len(text_i) == 1:
            # Dạng câu đơn
            content = self.clean_tags(text_i[0], remove_all=True)
            script.extend([
                {'v': 'Charon', 't': content, 'delay_after': 5000},
                {'v': 'Zephyr', 't': content, 'delay_after': 0}
            ])
        elif len(text_i) >= 2:
            # Dạng đối thoại / đoạn văn
            # Lượt 1
            for i, line in enumerate(text_i):
                if "女：" in line or "女:" in line: v = 'Zephyr'
                elif "男：" in line or "男:" in line: v = 'Charon'
                else: v = 'Charon' if i % 2 == 0 else 'Zephyr'
                delay = 1200 if i < len(text_i) - 1 else 5000
                script.append({'v': v, 't': self.clean_tags(line, remove_all=True), 'delay_after': delay})
            
            # Lượt 2
            for i, line in enumerate(text_i):
                if "女：" in line or "女:" in line: v = 'Zephyr'
                elif "男：" in line or "男:" in line: v = 'Charon'
                else: v = 'Charon' if i % 2 == 0 else 'Zephyr'
                # Nếu là trong nhóm gộp (merged) và chưa phải câu cuối -> nghỉ 15s để làm bài
                end_delay = 15000 if (is_merged_group and not is_last_in_group) else 0
                delay = 1200 if i < len(text_i) - 1 else end_delay
                script.append({'v': v, 't': self.clean_tags(line, remove_all=True), 'delay_after': delay})
        
        return script

# ==========================================
# PHẦN 2: TẠO ÂM THANH (AUDIO GENERATOR)
# ==========================================
class VertexAudioGenerator:
    # Danh sách các model name hỗ trợ
    SUPPORTED_MODELS = ['gemini-3.1-flash-tts-preview', 'gemini-2.5-pro-preview-tts', 'Chirp3-HD']
    
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
        
        if self.model_name in ['gemini-3.1-flash-tts-preview', 'gemini-2.5-pro-preview-tts']:
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
            script: List of {'v': role, 't': text, 'delay_after': int}
            out_path: Đường dẫn lưu file MP3
        """
        combined = AudioSegment.empty()
        for i, item in enumerate(script):
            seg = self.generate_single(item['t'], item['v'])
            combined += seg
            
            delay = item.get('delay_after', 1000)
            if i < len(script) - 1 and delay > 0:
                combined += AudioSegment.silent(duration=delay)
                
        combined.export(out_path, format="mp3")
        return os.path.abspath(out_path)

# ==========================================
# PHẦN 3: HÀM CHẠY TEST (MAIN RUNNER)
# ==========================================
def clean_filename(text):
    """
    Làm sạch tên file: bỏ các prefix như 'Ảnh:', 'Audio:', 'Audio, image:', 
    lấy dòng cuối cùng nếu có nhiều dòng, và bỏ đuôi file .mp3/.png...
    """
    if pd.isna(text) or not str(text).strip():
        return None
    
    # Tách dòng và lấy dòng chứa thông tin mã file (thường là dòng có dấu ( ) hoặc mã H1, H2...)
    lines = [l.strip() for l in str(text).split('\n') if l.strip()]
    if not lines: return None
    
    # Ưu tiên dòng có chứa định dạng mã (ví dụ: H1, H2, T1, C...)
    target = lines[-1]
    for line in lines:
        if re.search(r'H[1-6]\(.*\)', line, re.IGNORECASE):
            target = line
            break
    
    # Xóa prefix (chấp nhận cả dấu : của VN và Trung Quốc, thêm URL)
    prefix_pattern = r'^(Ảnh|Audio|Image|Illustration|Audio,\s*image|Audio,\s*hình\s*ảnh|URL)\s*[:：]\s*'
    target = re.sub(prefix_pattern, '', target, flags=re.IGNORECASE)
    
    # Xóa đuôi file nếu có
    target = re.sub(r'\.(mp3|png|jpg|jpeg|gif)$', '', target, flags=re.IGNORECASE)
    
    # Xử lý các ký tự cấm trong tên file Windows: \ / : * ? " < > |
    target = re.sub(r'[\\/:*?"<>|]', '_', target)
    
    return target.strip()

def get_range_from_filename(filename):
    """
    Phân tích tên file để tìm dải câu hỏi (ví dụ: C9_12 -> 9, 12)
    """
    if not filename: return None
    # Tìm mẫu _C[số]_[số] ở cuối tên file
    match = re.search(r'_C(\d+)_(\d+)$', filename)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None

def get_merged_ranges_b(excel_path):
    """
    Lấy danh sách các khoảng merge ở cột B (cột 2).
    Trả về list các tuple (start_row, end_row). Lưu ý: row của openpyxl bắt đầu từ 1.
    """
    try:
        wb = openpyxl.load_workbook(excel_path, read_only=True)
        ws = wb.active # pd.read_excel mặc định đọc sheet đầu tiên
        ranges = []
        if hasattr(ws, 'merged_cells'):
            for m_range in ws.merged_cells.ranges:
                if m_range.min_col <= 2 <= m_range.max_col:
                    ranges.append((m_range.min_row, m_range.max_row))
        wb.close()
        return ranges
    except Exception as e:
        print(f"Lỗi khi đọc merge cells: {e}")
        return []

def test_file(excel_path, output_dir, model_name='Chirp3-HD', male_voice='Charon', female_voice='Zephyr', log_fn=print):
    """
    Xử lý file Excel và tạo audio tương ứng.
    """
    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    audio_folder = os.path.join(output_dir, "audio", base_name)
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder, exist_ok=True)

    # Đọc dữ liệu
    df = pd.read_excel(excel_path)
    # Lấy thông tin merge thực tế từ Excel
    merged_ranges = get_merged_ranges_b(excel_path)
    
    processor = HSKTextProcessor()
    generator = VertexAudioGenerator(model_name=model_name, male_voice=male_voice, female_voice=female_voice)

    # BƯỚC 1: Parse data và map với thông tin merge + thông tin từ tên file
    parsed_rows = []
    for idx, row in df.iterrows():
        excel_row_idx = idx + 2 # pd.read_excel header=0 -> dòng data đầu là 2
        col_b, col_f, col_i = row.iloc[1], row.iloc[5], row.iloc[8]
        if "Phụ đề:" not in str(col_i):
            continue
        
        # 1. Tìm merge range từ Excel
        my_range = None
        for r_start, r_end in merged_ranges:
            if r_start <= excel_row_idx <= r_end:
                my_range = (r_start, r_end)
                break
        
        # 2. Tìm merge range từ tên file (Cột B)
        filename_b = clean_filename(col_b)
        file_range = get_range_from_filename(filename_b)
        
        text_i_raw = str(col_i).split("Phụ đề:")[1].split("Tạm dịch:")[0]
        parsed_rows.append({
            'q_idx': idx + 1,
            'excel_row': excel_row_idx,
            'merge_range': my_range,
            'file_range': file_range,
            'col_b': col_b,
            'col_f': col_f,
            'text_i': processor.extract_clean_chinese(text_i_raw),
            'text_f': processor.extract_clean_chinese(col_f)
        })

    if not parsed_rows:
        log_fn("❌ Không tìm thấy dữ liệu hợp lệ trong file Excel.")
        return audio_folder

    # BƯỚC 2: Gom nhóm dựa trên merge_range HOẶC file_range
    groups = []
    i = 0
    while i < len(parsed_rows):
        row = parsed_rows[i]
        
        # Ưu tiên gom theo merge range của Excel
        if row['merge_range']:
            group = []
            range_end = row['merge_range'][1]
            while i < len(parsed_rows) and parsed_rows[i]['excel_row'] <= range_end:
                group.append(parsed_rows[i])
                i += 1
            groups.append(group)
        
        # Nếu ko có merge Excel, check xem tên file có chứa dải câu hỏi (C9_12)
        elif row['file_range']:
            start_q, end_q = row['file_range']
            # Chỉ gom nếu start_q khớp với câu hiện tại
            if start_q == row['q_idx']:
                group = []
                while i < len(parsed_rows) and parsed_rows[i]['q_idx'] <= end_q:
                    group.append(parsed_rows[i])
                    i += 1
                groups.append(group)
            else:
                groups.append([row])
                i += 1
        else:
            # Dòng đơn (không merge)
            groups.append([row])
            i += 1

    # BƯỚC 3: Xử lý từng nhóm tạo audio
    generated_audio_paths = []
    log_fn("--- Bắt đầu tạo audio ---")

    for group in groups:
        is_merged = (len(group) > 1)
        
        if is_merged:
            # TẠO 1 FILE CHUNG CHO NHÓM MERGE
            group_script = []
            first_row = group[0]
            start_q = group[0]['q_idx']
            end_q = group[-1]['q_idx']
            
            # Làm sạch tên file từ cột B
            filename = clean_filename(first_row['col_b'])
            if not filename:
                filename = f"Câu_{start_q}_{end_q}"
            
            for j, row in enumerate(group):
                is_first = (j == 0)
                is_last = (j == len(group) - 1)
                s = processor.build_script(row, is_first_in_group=is_first, is_merged_group=True, is_last_in_group=is_last)
                
                # Cập nhật text dẫn nếu là câu đầu
                if is_first:
                    for item in s:
                        if "题到第...题" in item['t']:
                            item['t'] = item['t'].replace("题到第...题", f"题到第{processor._to_chinese_num(end_q)}题")
                group_script.extend(s)
            
            path = generator.create_audio(group_script, os.path.join(audio_folder, f"{filename}.mp3"))
            generated_audio_paths.append(path)
            log_fn(f"✅ Đã xong nhóm Câu {start_q}-{end_q} -> {filename}.mp3")
        
        else:
            # TẠO FILE RIÊNG LẺ
            row = group[0]
            q_idx = row['q_idx']
            # Làm sạch tên file từ cột F (hoặc B nếu F trống)
            filename = clean_filename(row['col_f'])
            if not filename:
                filename = clean_filename(row['col_b'])
            if not filename:
                filename = f"Câu_{q_idx}"
            
            # check_first_in_group=True để luôn add Ví dụ nếu có col_f (tiếng Trung)
            script = processor.build_script(row, is_first_in_group=True, is_merged_group=False)
            
            path = generator.create_audio(script, os.path.join(audio_folder, f"{filename}.mp3"))
            generated_audio_paths.append(path)
            log_fn(f"✅ Đã xong Câu {q_idx} -> {filename}.mp3")

    # BƯỚC 4: Gộp file tổng
    if generated_audio_paths:
        log_fn("\n--- Đang tạo file tổng Full.mp3 ---")
        try:
            combined = AudioSegment.empty()
            delay_segment = AudioSegment.silent(duration=15000)
            for i, path in enumerate(generated_audio_paths):
                if os.path.exists(path):
                    audio = AudioSegment.from_file(path, format="mp3")
                    combined += audio
                    if i < len(generated_audio_paths) - 1:
                        combined += delay_segment
            
            merged_path = os.path.join(audio_folder, f"{base_name}_Full.mp3")
            combined.export(merged_path, format="mp3")
            log_fn(f"🎉 HOÀN THÀNH! File tổng: {os.path.basename(merged_path)}")
        except Exception as e:
            log_fn(f"⚠️ Lỗi gộp file: {e}")

    return audio_folder