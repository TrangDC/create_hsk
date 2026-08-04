# services/input_handler.py

import pandas as pd
import re
import os

class InputDataManager:
    def __init__(self, file_path):
        self.file_path = file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    def get_hsk_sheets(self):
        try:
            xl = pd.ExcelFile(self.file_path)
            return [sheet for sheet in xl.sheet_names if "HSK" in sheet.upper()]
        except Exception as e:
            return []

    def extract_hsk_number(self, sheet_name):
        match = re.search(r'HSK(\d+)', sheet_name, re.IGNORECASE)
        return match.group(1) if match else "1"

    def normalize_column_name(self, col_name):
        return str(col_name).strip().lower()

    def process_specific_sheet(self, sheet_name):
        xl = pd.ExcelFile(self.file_path)
        hsk_num = self.extract_hsk_number(sheet_name)
        df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=0)
        
        col_map = {}
        possible_cols = {
            'stt': ['stt', 'số thứ tự', 'no'],
            'word': ['từ vựng', 'từ', 'vocabulary', 'word'],
            'pinyin': ['phiên âm', 'pinyin'],
            'type': ['loại từ', 'từ loại', 'type', 'pos'],
            'meaning': ['nghĩa', 'ý nghĩa', 'meaning', 'vietnamese'],
            'example': ['ví dụ', 'câu ví dụ', 'example', 'sentence'],
            'ex_pinyin': ['phiên âm ví dụ', 'phiên âm câu'],
            'ex_meaning': ['nghĩa ví dụ', 'dịch câu', 'dịch ví dụ'],
            'topic': ['tên chủ đề', 'chủ đề', 'topic'],
            'lesson': ['stt bài', 'bài', 'lesson', 'unit'],
            'thumbnail': ['tên ảnh/gif flashcard', 'thumbnail', 'ảnh minh họa'],
            'audio1': ['tên audio từ vựng', 'audio1', 'audio từ'],
            'audio2': ['tên audio ví dụ', 'audio2', 'audio câu']
        }

        excel_cols_norm = {self.normalize_column_name(c): c for c in df.columns}
        for key, variants in possible_cols.items():
            for v in variants:
                if v in excel_cols_norm:
                    col_map[key] = excel_cols_norm[v]
                    break
            if key not in col_map: col_map[key] = None

        if not col_map['word']: return []

        if col_map['lesson']: df[col_map['lesson']] = df[col_map['lesson']].ffill()
        if col_map['topic']: df[col_map['topic']] = df[col_map['topic']].ffill()

        processed_data = []

        for idx, row in df.iterrows():
            word = row[col_map['word']] if col_map['word'] else None
            if pd.isna(word) or str(word).strip() == "": continue

            def get_val(key):
                if col_map[key] and not pd.isna(row[col_map[key]]):
                    return str(row[col_map[key]]).strip()
                return None 

            exist_thumb = get_val('thumbnail')
            exist_audio1 = get_val('audio1')
            exist_audio2 = get_val('audio2')

            # Đánh dấu dòng này có cần xử lý AI/Media hay không
            needs_processing = not (exist_thumb and exist_audio1 and exist_audio2)

            stt = get_val('stt') or str(idx + 1)
            if stt.endswith('.0'): stt = stt[:-2]
            lesson = get_val('lesson') or "1"
            if lesson.endswith('.0'): lesson = lesson[:-2]
            topic = get_val('topic') or "General"

            item = {
                "excel_row": idx + 2,
                "needs_processing": needs_processing, # Biến quan trọng
                "raw_stt": stt,
                "word": str(word).strip(),
                "pinyin": get_val('pinyin'),
                "type": get_val('type'),
                "meaning": get_val('meaning'),
                "example": get_val('example'),
                "ex_pinyin": get_val('ex_pinyin'),
                "ex_meaning": get_val('ex_meaning'),
                # Trả về dữ liệu cũ nếu có
                "exist_thumb": exist_thumb,
                "exist_audio1": exist_audio1,
                "exist_audio2": exist_audio2,
                # Thông tin đặt tên
                "final_title": f"H{hsk_num}_B{lesson}_{topic}",
                "filename_audio_word": f"H{hsk_num}_B{lesson}_{stt}.mp3",
                "filename_audio_ex": f"H{hsk_num}_B{lesson}_VD_{stt}.mp3",
                "filename_image": f"H{hsk_num}_B{lesson}_BG_{stt}.gif"
            }
            processed_data.append(item)
            
        return processed_data