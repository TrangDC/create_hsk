import json
from pathlib import Path
from typing import Dict, Any

class MatrixManager:
    """
    Quản lý việc đọc file JSON ma trận câu hỏi và file từ vựng HSK.
    Cung cấp hàm trích xuất dữ liệu động (rules, từ vựng) cho từng dạng bài.
    """
    def __init__(self, matrix_path: str, vocab_path: str):
        self.matrix_path = Path(matrix_path)
        self.vocab_path = Path(vocab_path)
        
        self.matrix_data = self._load_json(self.matrix_path)
        self.vocab_data = self._load_json(self.vocab_path)

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            print(f"❌ Lỗi: Không tìm thấy file {path}")
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Lỗi khi đọc JSON từ {path}: {e}")
            return {}

    def _get_vocab_for_topic(self, hsk_level: str, topic_name: str) -> list:
        """
        Tìm và trả về danh sách từ vựng thuộc về 1 topic_name (ví dụ: 'Số lượng').
        Duyệt qua tất cả các bài trong level đó.
        """
        result = []
        # Chắc chắn key level phải khớp (ví dụ: "HSK1")
        level_data = self.vocab_data.get(hsk_level.upper())
        if not level_data:
            return result
            
        # level_data là dict có key là số thứ tự bài: "1", "2", "3"...
        for lesson_id, lesson_topics in level_data.items():
            # lesson_topics là dict chứa các chủ đề của bài đó
            if topic_name in lesson_topics:
                # Tìm thấy chủ đề, lấy mảng danh sách từ vựng
                # Bổ sung thêm thông tin Chủ đề vào từng từ vựng
                words = lesson_topics[topic_name]
                for w in words:
                    w_copy = w.copy()
                    w_copy["Topic"] = topic_name
                    result.append(w_copy)
                
        return result

    def _format_vocab_list(self, vocab_list: list) -> str:
        """
        Format list từ vựng thành bảng Markdown để nhồi vào prompt.
        Tính toán độ rộng cột để bảng hiển thị đẹp mắt hơn và bổ sung cột Chủ đề.
        """
        if not vocab_list:
            return "Không có từ vựng cụ thể cho các chủ đề yêu cầu."
            
        # Tìm độ dài tối đa của từng cột để padding
        max_topic_len = len("Chủ đề")
        max_word_len = len("Từ vựng")
        max_pinyin_len = len("Phiên âm")
        max_meaning_len = len("Nghĩa")

        unique_vocab = []
        seen = set()
        for v in vocab_list:
            word = v.get("Từ vựng", "")
            if word not in seen:
                seen.add(word)
                topic = v.get("Topic", "")
                pinyin = v.get("Phiên âm", "")
                meaning = v.get("Nghĩa", "")
                
                max_topic_len = max(max_topic_len, len(topic))
                max_word_len = max(max_word_len, len(word))
                max_pinyin_len = max(max_pinyin_len, len(pinyin))
                max_meaning_len = max(max_meaning_len, len(meaning))
                
                unique_vocab.append({
                    "Topic": topic,
                    "Từ vựng": word,
                    "Phiên âm": pinyin,
                    "Nghĩa": meaning
                })

        # Tạo bảng Markdown có padding
        md = f"| {'Chủ đề'.ljust(max_topic_len)} | {'Từ vựng'.ljust(max_word_len)} | {'Phiên âm'.ljust(max_pinyin_len)} | {'Nghĩa'.ljust(max_meaning_len)} |\n"
        md += f"|-{'-' * max_topic_len}-|-{'-' * max_word_len}-|-{'-' * max_pinyin_len}-|-{'-' * max_meaning_len}-|\n"
        
        for v in unique_vocab:
            topic = v['Topic'].ljust(max_topic_len)
            word = v['Từ vựng'].ljust(max_word_len)
            pinyin = v['Phiên âm'].ljust(max_pinyin_len)
            meaning = v['Nghĩa'].ljust(max_meaning_len)
            md += f"| {topic} | {word} | {pinyin} | {meaning} |\n"
            
        return md

    def get_dynamic_data_for_form(self, hsk_level: str, matrix_name: str) -> Dict[str, Any]:
        """
        Hàm chính: Trả về Dictionary chứa các giá trị động cho một dạng bài cụ thể 
        để tiêm vào chuỗi `.format()` của file prompt .txt tĩnh.
        """
        # 1. Kiểm tra tính hợp lệ
        if self.matrix_data.get("Lever", "").upper() != hsk_level.upper():
            print(f"⚠️ Cảnh báo: File matrix không khớp với level {hsk_level}")
            return None

        if matrix_name not in self.matrix_data:
            print(f"⚠️ Cảnh báo: Dạng bài '{matrix_name}' không tồn tại trong matrix.")
            return None

        form_data = self.matrix_data[matrix_name]
        number_of_questions = form_data.get("SL_dang_bai", 0)
        questions = form_data.get("data", [])
        
        # 2. Build phần Rule cho từng câu
        rules_text = ""
        all_vocab_topics = set() # Dùng set để gom các chủ đề từ vựng cần tra cứu để loại bỏ trùng lặp
        
        for idx, q in enumerate(questions, start=1):
            topic = q.get("Nhom_tu_vung")
            if topic:
                # Thêm topic vào set để chút nữa quét file JSON
                all_vocab_topics.add(topic)
                
            rules_text += f"--- YÊU CẦU CÂU HỎI SỐ {idx} ---\n"
            rules_text += f"- Độ khó: {q.get('Do_kho', 'Không có')}\n"
            rules_text += f"- Trọng tâm kiểm tra: {q.get('Trong_tam', 'Không có')}\n"
            rules_text += f"- Chủ đề từ vựng / tình huống: {q.get('Chu-de_tinh-huong', 'Không có')}\n"
            # rules_text += f"- Từ trọng tâm bắt buộc: {q.get('Tu_trong_tam', 'Không có')}\n"
            
            grammar = q.get('Ngu-phap_mau-cau')
            if not grammar or grammar == "—":
                 rules_text += f"- Ngữ pháp / mẫu câu: Sử dụng ngữ pháp cốt lõi của {hsk_level.upper()}\n"
            else:
                 rules_text += f"- Ngữ pháp / mẫu câu: Bắt buộc dùng ngữ pháp '{grammar}'\n"
                 
            # rules_text += f"- Đặc tả tạo đề: {q.get('Dac_ta_tao_de_tt', 'Không có')}\n\n"

        # 3. Tra cứu và Build phần Danh sách từ vựng Markdown
        vocab_list = []
        for topic in all_vocab_topics:
            # Tra cứu trong hsk_vocab.json với level tương ứng (VD: "HSK1")
            vocab_list.extend(self._get_vocab_for_topic(hsk_level.upper(), topic))
            
        vocab_md = self._format_vocab_list(vocab_list)

        # 4. Trả về payload động
        return {
            "number": number_of_questions,
            "matrix_name": matrix_name,
            "rules_text": rules_text,
            "vocab_md": vocab_md
        }

if __name__ == "__main__":
    # Test script nhanh
    manager = MatrixManager(
        matrix_path=r"d:\Edmicro\Tools\create_hsk\hsk_core\resources\data\matrix_hsk1.json",
        vocab_path=r"d:\Edmicro\Tools\create_hsk\hsk_core\resources\data\hsk_vocab.json"
    )
    
    data = manager.get_dynamic_data_for_form("HSK1", "Nghe từ/cụm từ + tranh Đ/S")
    if data:
        print("====== SỐ CÂU ======")
        print(data["number"])
        print("\n====== QUY TẮC ======")
        print(data["rules_text"])
        print("\n====== TỪ VỰNG ======")
        print(data["vocab_md"])
