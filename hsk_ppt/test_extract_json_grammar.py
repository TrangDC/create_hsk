import sys
import os
import json
import time
import re

# Đảm bảo có thể import được services từ thư mục cha
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.callAPI import VertexClient

def get_grammar_schema():
    """Định nghĩa JSON Schema cho điểm ngữ pháp (Linear Structure)"""
    return {
        "type": "object",
        "properties": {
            "lesson_info": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "Số bài (VD: 2)"},
                    "title_cn": {"type": "string", "description": "Tên bài pdf tiếng Trung (VD: 你穿红色的很好看)"},
                    "title_vn": {"type": "string", "description": "Tên bài ngữ pháp tiếng Việt (VD: Ngữ pháp - Bài 2)"}
                },
                "required": ["number","title_cn", "title_vn"]
            },
            "grammar_point": {
                "type": "object",
                "description": "Nội dung chi tiết của một chủ điểm ngữ pháp cụ thể.",
                "properties": {
                    "grammar_name": {
                        "type": "string", 
                        "description": "Tên điểm ngữ pháp chính được dịch sang Tiếng Việt. VD: Trật tự từ trong câu, Động từ lặp lại..."
                    },
                    "structures": {
                        "type": "array",
                        "description": "Danh sách các cấu trúc/dạng thức (VD: Dạng khẳng định, Phủ định, Động từ 1 âm tiết...)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sub_title": {"type": "string", "description": "Tên dạng cấu trúc. VD: Dạng khẳng định"},
                                "formula": {"type": "string", "description": "Công thức ngữ pháp cốt lõi (VD: Chủ ngữ + Động từ + Tân ngữ). Nếu không có, hãy để chuỗi rỗng ''"},
                                "usage": {"type": "string", "description": "Đoạn văn giải thích cách dùng, ý nghĩa, hoàn cảnh sử dụng. Bao gồm cả giải thích phân tích thành phần câu (nếu có)."},
                                "examples": {
                                    "type": "array",
                                    "description": "Danh sách ví dụ minh họa cho cấu trúc này",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "hz": {"type": "string"},
                                            "py": {"type": "string"},
                                            "vi": {"type": "string"},
                                            "image_description": {
                                                "type": "string",
                                                "description": "Mô tả chi tiết bằng tiếng Anh (prompt) để AI vẽ ảnh minh họa cho câu ví dụ này."
                                            }
                                        },
                                        "required": ["hz", "py", "vi"]
                                    }
                                }
                            },
                            "required": ["sub_title", "formula", "usage", "examples"]
                        }
                    },
                    "notes": {
                        "type": "array",
                        "description": "Danh sách các lưu ý quan trọng, quy tắc ngoại lệ, mẹo nhớ (dạng text thuần). Nếu không có thì là mảng rỗng []",
                        "items": {
                            "type": "string",
                            "description": "Nội dung lưu ý. VD: Khi động từ là ly hợp, không thể dùng ABAB."
                        }
                    },
                    "exercises": {
                        "type": "array",
                        "description": "Danh sách bài tập củng cố riêng cho điểm ngữ pháp này.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Loại bài tập: multiple_choice, true_false, fill_in_the_blanks"},
                                "multiple_choice": {
                                    "type": "object",
                                    "description": "Chỉ điền dữ liệu nếu type = multiple_choice",
                                    "properties": {
                                        "question": {"type": "string", "description": "Câu hỏi trắc nghiệm."},
                                        "pinyin": {"type": "string", "description": "Pinyin của câu hỏi trắc nghiệm."},
                                        "answer": {"type": "string", "description": "Đáp án A, B, C hoặc D."},
                                        "options": {
                                            "type": "array",
                                            "description": "Danh sách đáp án, đúng 4 đáp án.",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "label": {"type": "string"},
                                                    "hz": {"type": "string"},
                                                    "py": {"type": "string"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["question", "pinyin", "answer", "options"]
                                },
                                "true_false": {
                                    "type": "object",
                                    "description": "Chỉ điền dữ liệu nếu type = true_false",
                                    "properties": {
                                        "statement": {"type": "string", "description": "Câu nhận định đúng sai."},
                                        "answer": {"type": "boolean", "description": "Đáp án đúng sai (true hoặc false)"}
                                    },
                                    "required": ["statement", "answer"]
                                },
                                "fill_in_the_blanks": {
                                    "type": "object",
                                    "description": "Chỉ điền dữ liệu nếu type = fill_in_the_blanks",
                                    "properties": {
                                        "instruction": {"type": "string", "description": "Yêu cầu làm bài. VD: Điền các từ sau vào chỗ trống:"},
                                        "given_words": {
                                            "type": "array",
                                            "description": "Danh sách từ cho sẵn.",
                                            "items": {"type": "string"}
                                        },
                                        "sentences": {
                                            "type": "array",
                                            "description": "Danh sách câu hỏi. Dùng *...* để bọc chỗ trống chứa đáp án trong full_sentence.",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "full_sentence": {"type": "string"},
                                                    "blank_word": {"type": "string"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["instruction", "given_words", "sentences"]
                                }
                            },
                            "required": ["type"]
                        }
                    }
                },
                "required": ["grammar_name", "structures", "notes", "exercises"]
            }
        },
        "required": ["lesson_info", "grammar_point"]
    }

def extract_single_grammar_point(client: VertexClient, pdf_path: str, prompt_text: str) -> dict:
    """Hàm gọi AI để xử lý 1 điểm ngữ pháp duy nhất"""
    
    schema = get_grammar_schema()
    
    resp = client.send_data_to_AI(
        prompt=prompt_text, 
        file_paths=[pdf_path], 
        temperature=0.6,
        response_mime_type="application/json",
        response_schema=schema
    )
    
    try:
        data = json.loads(resp)
        return data
    except json.JSONDecodeError as e:
        print(f"Lỗi parse JSON từ AI: {resp}")
        raise ValueError(f"AI trả về JSON lỗi: {e}")

def process_grammar_lesson(pdf_path: str, base_prompt: str, level: str, index_file_path: str, output_json_path: str):
    """
    Hàm điều phối: Gọi AI nhiều lần, mỗi lần quét 1 chủ điểm ngữ pháp trong danh sách grammar của bài học tương ứng,
    sau đó gom tất cả lại thành 1 file JSON tổng.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
    
    if not os.path.exists(index_file_path):
        raise FileNotFoundError(f"Không tìm thấy file index tại: {index_file_path}")

    # Trích xuất số bài (lesson number) từ tên file PDF bằng regex
    file_name = os.path.basename(pdf_path)
    match = re.search(r'Bài\s+(\d+)', file_name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Không thể trích xuất số bài từ tên file PDF: {file_name}. Tên file cần có định dạng 'Bài <số>'")
    
    lesson_number = int(match.group(1))
    level = level.upper()
    
    # Đọc file index.json để lấy danh sách grammar
    with open(index_file_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
        
    curriculum = index_data.get("hsk_full_curriculum", {}).get(level, [])
    lesson_data = next((lesson for lesson in curriculum if lesson.get("lesson") == lesson_number), None)
    
    if not lesson_data:
        raise ValueError(f"Không tìm thấy thông tin bài {lesson_number} của level {level} trong file index.")
        
    grammar_topics = [f"{g.get('hz')} - {g.get('vi')}" for g in lesson_data.get("grammar", [])]
    total_topics = len(grammar_topics)
    
    if total_topics == 0:
        raise ValueError(f"Bài {lesson_number} không có điểm ngữ pháp nào cần trích xuất.")

    print(f"Bắt đầu xử lý file PDF Ngữ Pháp cấp độ {level} - Bài {lesson_number}. Tổng số chủ điểm: {total_topics}...")
    
    client = VertexClient(None, None, "gpt-5.4", "us-central1")  # Dùng OpenAI backend
    
    final_json = {
        "lesson_info": {},
        "grammar_points": []
    }
    
    for i, topic in enumerate(grammar_topics, 1):
        print(f"\n[{i}/{total_topics}] Đang trích xuất chủ điểm: {topic}...")
        
        try:
            # Format prompt thay thế {level} và {section_name} bằng tên chủ điểm hiện tại
            formatted_prompt = base_prompt.format(level=level, section_name=topic)
        except Exception as e:
            print(f"❌ Lỗi khi định dạng prompt cho chủ điểm {topic}: {e}")
            continue

        try:
            # Gọi AI
            point_data = extract_single_grammar_point(client, pdf_path, formatted_prompt)
            
            # Lấy lesson_info từ lần chạy đầu tiên thành công
            if i == 1 and "lesson_info" in point_data:
                final_json["lesson_info"] = point_data["lesson_info"]
                
            # Đẩy dữ liệu ngữ pháp vào mảng tổng
            if "grammar_point" in point_data:
                final_json["grammar_points"].append(point_data["grammar_point"])
            
            # Tạm nghỉ để tránh Rate Limit API
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Lỗi khi trích xuất {topic}: {e}")
            print("Chuyển sang chủ điểm tiếp theo...")

    # Lưu kết quả
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ THÀNH CÔNG! Đã gộp và lưu {len(final_json['grammar_points'])} điểm ngữ pháp vào: {output_json_path}")
    return final_json

if __name__ == "__main__":
    # Các tham số file cần thiết
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PDF_FILE_PATH = os.path.join(base_dir, "hsk_ppt", "input", "HSK2", "Bài 4_你穿红色的很好看.pdf")
    PROMPT_FILE_PATH = os.path.join(base_dir, "resources", "prompts", "ppt_generation", "Prompt_Ngu_Phap_New.txt")
    INDEX_FILE_PATH = os.path.join(base_dir, "resources", "ppt_templates", "hsk_index.json")
    OUTPUT_JSON_FILE = os.path.join(base_dir, "hsk_ppt", "HSK2_Grammar_test_output.json")
    HSK_LEVEL = "HSK2"

    try:
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
            base_prompt_text = f.read()
            
        result = process_grammar_lesson(
            pdf_path=PDF_FILE_PATH, 
            base_prompt=base_prompt_text, 
            level=HSK_LEVEL,
            index_file_path=INDEX_FILE_PATH,
            output_json_path=OUTPUT_JSON_FILE
        )
        
    except Exception as e:
        print(f"\n❌ LỖI CHUNG: {e}")