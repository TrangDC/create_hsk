import sys
import os
import json
import re
import time

# Đảm bảo có thể import được call_vertexai từ thư mục cha
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from call_vertexai import VertexClient, get_credentials

def get_section_schema():
    """Định nghĩa JSON Schema dưới dạng Dict để tránh lỗi Import"""
    return {
        "type": "object",
        "properties": {
            "lesson_info": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "Số bài (VD: 8)"},
                    "title_cn": {"type": "string"},
                    "title_vn": {"type": "string"},
                },
                "required": ["number", "title_cn", "title_vn"]
            },
            "section_title": {"type": "string", "description": "Hội thoại 1, Hội thoại 2, hoặc Đoạn văn"},
            "full_dialogue": {
                "type": "object",
                "properties": {
                    "hz": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại Hán tự trong bài"},
                    "py": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang Pinyin tương ứng"},
                    "vi": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang tiếng Việt tương ứng"},
                },
                "required": ["hz", "py", "vi"]
            },
            "vocabulary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hz": {"type": "string"},
                        "pinyin": {"type": "string"},
                        "type": {"type": "string"},
                        "vi": {"type": "string"},
                        "measure_word_usage": {"type": "string"},
                        "example": {
                            "type": "object",
                            "properties": {
                                "hz": {
                                    "type": "string", 
                                    "description": "Câu ví dụ Hán tự. BẮT BUỘC bọc từ vựng chính trong cặp thẻ <hl> và </hl>. VD: <hl>今天</hl>我去学校。"
                                },
                                "py": {
                                    "type": "string", 
                                    "description": "Pinyin câu ví dụ. BẮT BUỘC bọc pinyin của từ chính trong cặp thẻ <hl> và </hl>. VD: <hl>Jīntiān</hl> wǒ qù xuéxiào."
                                },
                                "vi": {
                                    "type": "string", 
                                    "description": "Dịch tiếng Việt câu ví dụ. BẮT BUỘC bọc nghĩa tiếng Việt của từ chính trong cặp thẻ <hl> và </hl>. VD: <hl>Hôm nay</hl> tôi đi học."
                                }
                            },
                        }
                    },
                    "required": ["hz", "pinyin", "vi"]
                }
            },
            "extra_knowledge": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "examples": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "hz": {"type": "string"},
                                    "py": {"type": "string"},
                                    "vi": {"type": "string"},
                                }
                            }
                        }
                    }
                }
            },
            "simple_dialogue": {
                "type": "object",
                "properties": {
                    "hz": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại Hán tự trong bài"},
                    "vi": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang tiếng Việt tương ứng"},
                },
            },
            "exercise": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hz": {"type": "string"},
                                "py": {"type": "string"},
                            }
                        }
                    },
                    "answer": {"type": "string"},
                }
            }
        },
        "required": ["lesson_info", "section_title", "full_dialogue", "vocabulary", "extra_knowledge", "simple_dialogue", "exercise"]
    }

def extract_single_section(client: VertexClient, pdf_path: str, prompt_text: str) -> dict:
    """Hàm gọi AI để xử lý 1 section duy nhất"""
    
    # Lấy schema đã định nghĩa
    schema = get_section_schema()
    
    # Gọi VertexClient với các tham số mới thêm
    resp = client.send_data_to_AI(
        prompt=prompt_text, 
        file_paths=[pdf_path], 
        temperature=0.6, # Nên để 0.2 cho các task trích xuất dữ liệu để AI bớt "sáng tạo"
        response_mime_type="application/json",
        response_schema=schema
    )
    
    # Parse chuỗi JSON trả về
    try:
        data = json.loads(resp)
        return data
    except json.JSONDecodeError as e:
        print(f"Lỗi parse JSON từ AI: {resp}")
        raise ValueError(f"AI trả về JSON lỗi: {e}")

def process_full_hsk_lesson(pdf_path: str, base_prompt: str, level: str, output_json_path: str):
    """Hàm điều phối: Gọi AI nhiều lần và gom data lại"""
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")

    # Xác định số lần lặp dựa trên Level
    level = level.upper()
    print(f"Đang xử lý cấp độ: {level}")
    total_iterations = 4 if level in ["HSK2", "HSK3"] else 3
    
    print(f"Bắt đầu xử lý file PDF cho cấp độ {level}. Tổng số section cần quét: {total_iterations}...")
    
    creds, project_id = get_credentials()
    client = VertexClient(project_id, creds, "gemini-2.5-pro", "us-central1") # Đã sửa tên model chuẩn
    
    # Khởi tạo object JSON tổng
    final_json = {
        "lesson_info": {},
        "sections":[]
    }
    
    for i in range(1, total_iterations + 1):
        # Xác định tên section
        if i <= 3:
            section_name = f"Hội thoại {i}"
        else:
            section_name = "Đoạn văn"
            
        print(f"\n[{i}/{total_iterations}] Đang trích xuất: {section_name}...")
        
        try:
            # Format prompt (Thay thế placeholder {level}, {number}, {section_name})
            formatted_prompt = base_prompt.format(level=level, number=i, section_name=section_name)
        
        except Exception as e:
            print(f"❌ Lỗi khi định dạng prompt cho section {section_name}: {e}")
            raise

        try:
            # Gọi AI cho 1 section
            section_data = extract_single_section(client, pdf_path, formatted_prompt)
            
            # Nếu là vòng lặp đầu tiên, lấy thông tin bài học (lesson_info)
            if i == 1 and "lesson_info" in section_data:
                final_json["lesson_info"] = section_data["lesson_info"]
                
            # Xóa lesson_info khỏi section_data để tránh trùng lặp khi gom vào mảng sections
            if "lesson_info" in section_data:
                del section_data["lesson_info"]
                
            # Đẩy dữ liệu section vào mảng tổng
            final_json["sections"].append(section_data)
            
            # Tạm nghỉ 3 giây giữa các lần gọi để tránh chạm limit Quota của API Google
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Lỗi khi trích xuất {section_name}: {e}")
            print("Dừng quá trình để kiểm tra.")
            raise

    # Lưu kết quả tổng ra file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ THÀNH CÔNG! Đã gộp và lưu {len(final_json['sections'])} sections vào: {output_json_path}")
    return final_json

if __name__ == "__main__":
    # Thay đổi đường dẫn tương ứng với môi trường của bạn để test
    PDF_FILE_PATH = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\input\8. 我爸爸也在医院工作 My father also works at a hospital.pdf"
    PROMPT_FILE_PATH = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\prompts\Prompt_Bai_Khoa_1_bai.txt"
    OUTPUT_JSON_FILE = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\test_output_json.json"

    # Định nghĩa cấp độ muốn chạy (HSK1, HSK2, HSK3)
    LEVEL = 'HSK1' 

    try:
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
            base_prompt_text = f.read()
            
        result = process_full_hsk_lesson(
            pdf_path=PDF_FILE_PATH, 
            base_prompt=base_prompt_text, 
            level=LEVEL,
            output_json_path=OUTPUT_JSON_FILE
        )
        
    except Exception as e:
        print(f"\n❌ LỖI CHUNG: {e}")