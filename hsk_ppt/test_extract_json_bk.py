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
            "image_description": {
                "type": "string", 
                "description": "Mô tả chi tiết bằng tiếng Anh (prompt) để AI vẽ ảnh minh họa cho nội dung bài khóa/hội thoại/đoạn văn này. Chú ý miêu tả rõ bối cảnh, nhân vật, hành động."
            },
            "full_dialogue": {
                "type": "object",
                "properties": {
                    "hz": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại Hán tự trong bài. Trường hợp là section Đoạn văn thì sẽ là một đoạn văn dài, không chia thành nhiều câu nhỏ."},
                    "py": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang Pinyin tương ứng, nếu là section Đoạn văn thì sẽ là Pinyin của cả đoạn văn đó."},
                    "vi": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang tiếng Việt tương ứng, nếu là section Đoạn văn thì sẽ là nghĩa tiếng Việt của cả đoạn văn đó."},
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
                "description": "Mảng các kiến thức mở rộng (Sinh từ 1 đến 2 kiến thức). Kiến thức mở rộng ở đây là những thông tin, hiểu biết thêm về ngữ pháp, từ vựng được tổng hợp ngoài phạm vi sách giáo khoa nhưng vẫn liên quan chặt chẽ đến nội dung bài học, giúp người học có cái nhìn sâu sắc và toàn diện hơn về ngôn ngữ.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Loại kiến thức: grammar_formula, grammar_advanced, vocab_list, word_derivatives, word_comparison"},
                        "grammar_formula": {
                            "type": "object",
                            "description": "Dữ liệu cho grammar_formula",
                            "properties": {
                                "title": {"type": "string"},
                                "formula": {"type": "string"},
                                "usage": {"type": "string"},
                                "examples": {
                                    "type": "array",
                                    "description": "Danh sách ví dụ, tối đa 2 ví dụ",
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
                                        }
                                    }
                                }
                            }
                        },
                        "grammar_advanced": {
                            "type": "object",
                            "description": "Dữ liệu cho grammar_advanced",
                            "properties": {
                                "title": {"type": "string"},
                                "explanation": {"type": "string"},
                                "comparison_table": {
                                    "type": "object",
                                    "properties": {
                                        "headers": {"type": "array", "items": {"type": "string"}},
                                        "rows": {
                                            "type": "array", 
                                            "description": "Các hàng trong bảng, tối đa 4 hàng",
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "important_notes": {"type": "array", "items": {"type": "string"}, "description": "Lưu ý quan trọng, tối đa 3 items"},
                                "examples": {
                                    "type": "array",
                                    "description": "Danh sách ví dụ, tối đa 2 ví dụ",
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
                                        }
                                    }
                                }
                            }
                        },
                        "vocab_list": {
                            "type": "object",
                            "description": "Dữ liệu cho vocab_list",
                            "properties": {
                                "title": {"type": "string"},
                                "category_desc": {"type": "string"},
                                "items": {
                                    "type": "array",
                                    "description": "Danh sách các mục, tối đa 4 mục",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "hz": {"type": "string"},
                                            "py": {"type": "string"},
                                            "vi": {"type": "string"},
                                            "image_description": {
                                                "type": "string",
                                                "description": "Mô tả chi tiết bằng tiếng Anh (prompt) để AI vẽ ảnh minh họa cho từ vựng này."
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "word_derivatives": {
                            "type": "object",
                            "description": "Dữ liệu cho word_derivatives",
                            "properties": {
                                "root_word": {"type": "string"},
                                "pinyin": {"type": "string"},
                                "meaning": {"type": "string"},
                                "derived_words": {
                                    "type": "array",
                                    "description": "Danh sách từ phái sinh, tối đa 4 từ",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "hz": {"type": "string"},
                                            "py": {"type": "string"},
                                            "vi": {"type": "string"},
                                            "image_description": {
                                                "type": "string",
                                                "description": "Mô tả chi tiết bằng tiếng Anh (prompt) để AI vẽ ảnh minh họa cho từ vựng này."
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "word_comparison": {
                            "type": "object",
                            "description": "Dữ liệu cho word_comparison. So sánh 2 đến 3 từ.",
                            "properties": {
                                "title": {"type": "string"},
                                "similarities": {
                                    "type": "object",
                                    "properties": {
                                        "explanation": {"type": "string", "description": "Giải thích sự giống nhau"},
                                        "examples": {
                                            "type": "array",
                                            "description": "Ví dụ minh họa sự giống nhau",
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
                                                }
                                            }
                                        }
                                    }
                                },
                                "differences_overview": {
                                    "type": "object",
                                    "description": "Khái quát sự khác nhau và ví dụ",
                                    "properties": {
                                        "explanations": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "word": {"type": "string"},
                                                    "explanation": {"type": "string"}
                                                }
                                            }
                                        },
                                        "examples": {
                                            "type": "array",
                                            "description": "Ví dụ minh họa sự khác nhau",
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
                                                }
                                            }
                                        }
                                    }
                                },
                                "differences": {
                                    "type": "array",
                                    "description": "Danh sách điểm khác biệt chi tiết, từ 2 đến 3 mục",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "word": {"type": "string"},
                                            "pinyin": {"type": "string"},
                                            "focus": {"type": "string"},
                                            "context": {"type": "string"},
                                            "word_type": {"type": "string"},
                                            "image_description": {"type": "string",
                                                                  "description": "Mô tả chi tiết bằng tiếng Anh (prompt) để AI vẽ ảnh minh họa cho điểm khác biệt này."
                                            }
                                        }
                                    }
                                },
                                "memory_tip": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "simple_dialogue": {
                "type": "object",
                "properties": {
                    "hz": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại Hán tự trong bài. Trường hợp là section Đoạn văn thì sẽ là một đoạn văn dài, không chia thành nhiều câu nhỏ. "},
                    "vi": {"type": "array", "items": {"type": "string"}, "description": "Danh sách các câu thoại được dịch sang tiếng Việt tương ứng, nếu là section Đoạn văn thì sẽ là nghĩa tiếng Việt của cả đoạn văn đó."},
                },
            },
            "exercise": {
                "type": "array",
                "description": "Mảng các bài tập. Tối đa 2 bài tập.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Loại bài tập: multiple_choice, true_false, fill_in_the_blanks"},
                        "multiple_choice": {
                            "type": "object",
                            "description": "Chỉ có dữ liệu nếu type = multiple_choice",
                            "properties": {
                                "question": {"type": "string", "description": "Câu hỏi trắc nghiệm. VD: 他说他很饿，但是为什么______米饭都不吃？ hoặc A: 我们怎么去学校？ B: 坐公交车人太多了，我们______去吧。"},
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
                                            "py": {"type": "string"},
                                        }
                                    }
                                }
                            }
                        },
                        "true_false": {
                            "type": "object",
                            "description": "Chỉ có dữ liệu nếu type = true_false",
                            "properties": {
                                "statement": {"type": "string", "description": "Câu nhận định. VD: “星期天” và “星期日” có ý nghĩa giống nhau"},
                                "answer": {"type": "boolean", "description": "Đáp án đúng sai (true hoặc false)"}
                            }
                        },
                        "fill_in_the_blanks": {
                            "type": "object",
                            "description": "Chỉ có dữ liệu nếu type = fill_in_the_blanks",
                            "properties": {
                                "instruction": {"type": "string", "description": "Yêu cầu làm bài. VD: Điền các từ sau vào chỗ trống:"},
                                "given_words": {
                                    "type": "array",
                                    "description": "Danh sách từ cho sẵn, tối đa 4 từ.",
                                    "items": {"type": "string"}
                                },
                                "sentences": {
                                    "type": "array",
                                    "description": "Danh sách câu hỏi, tối đa 4 câu. Dùng *...* để bọc chỗ trống.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "full_sentence": {"type": "string"}                                        }
                                    }
                                }
                            }
                        }
                    }
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
        temperature=0.6,
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

def _get_grammar_blacklist(level: str, pdf_filename: str) -> list:
    """Đọc file hsk_index.json và trả về danh sách ngữ pháp của bài học hiện tại."""
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "resources", "ppt_templates", "hsk_index.json")
        
        if not os.path.exists(index_path):
            print("⚠️ Không tìm thấy hsk_index.json, bỏ qua blacklist ngữ pháp.")
            return []
            
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
            
        # Tìm số bài (lesson number) từ tên file PDF (VD: Bài 4_...pdf -> 4)
        match = re.search(r'Bài\s*(\d+)', pdf_filename, re.IGNORECASE)
        if not match:
            print(f"⚠️ Không trích xuất được số bài từ tên file PDF: {pdf_filename}. Bỏ qua blacklist ngữ pháp.")
            return []
            
        lesson_num = int(match.group(1))
        
        level_upper = level.upper()
        hsk_data = index_data.get("hsk_full_curriculum", {}).get(level_upper, [])
        
        # Tìm danh sách ngữ pháp của bài học tương ứng
        grammar_list = []
        for lesson in hsk_data:
            if lesson.get("lesson") == lesson_num:
                for grammar_item in lesson.get("grammar", []):
                    grammar_list.append(grammar_item.get("hz", ""))
                break                
                
        return grammar_list
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy blacklist ngữ pháp: {e}")
        return []

def process_full_hsk_lesson(pdf_path: str, base_prompt: str, level: str, output_json_path: str):
    """Hàm điều phối: Gọi AI nhiều lần và gom data lại"""
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")

    # Lấy danh sách ngữ pháp cấm sinh (từ hsk_index.json)
    pdf_filename = os.path.basename(pdf_path)
    grammar_blacklist = _get_grammar_blacklist(level, pdf_filename)
    grammar_blacklist_str = "\n- ".join(grammar_blacklist) if grammar_blacklist else "Không có"
    print(f"📋 Blacklist ngữ pháp (lấy từ hsk_index): \n- {grammar_blacklist_str}")

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
    
    used_extra_knowledge = []
    
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
            
            # Thêm constraints chống trùng lặp vào cuối prompt
            used_knowledge_str = "\n- ".join(used_extra_knowledge) if used_extra_knowledge else "Chưa có"
            constraints_text = f"""

--- RÀNG BUỘC ĐẶC BIỆT KHI SINH 'extra_knowledge' (KIẾN THỨC LIÊN QUAN) ---
1. TUYỆT ĐỐI KHÔNG sinh các kiến thức liên quan chính đến chủ điểm ngữ pháp sau đây (vì chúng đã có sẵn trong sách và sẽ được học riêng):
- {grammar_blacklist_str}

2. TUYỆT ĐỐI KHÔNG sinh lại các chủ điểm kiến thức sau đây (vì chúng đã được sinh ở các hội thoại trước):
- {used_knowledge_str}

Mục tiêu của 'extra_knowledge' là:
 + Sinh kiến thức MỚI được rút ra từ thực tiễn ứng dụng ngoài đời sống.
 + Có nội dung liên quan tới chủ đề từ vựng, hội thoại của section hiện tại nhưng KHÔNG TRÙNG LẶP với nội dung trong sách giáo khoa.
 + Mở rộng từ vựng hoặc nâng cao kiến thức KHÁC với nội dung chính của bài học.
"""
            formatted_prompt += constraints_text
        
        except Exception as e:
            print(f"❌ Lỗi khi định dạng prompt cho section {section_name}: {e}")
            raise

        try:
            # Gọi AI cho 1 section
            section_data = extract_single_section(client, pdf_path, formatted_prompt)
            
            # Cập nhật danh sách kiến thức đã sử dụng
            if "extra_knowledge" in section_data:
                for knowledge_item in section_data["extra_knowledge"]:
                    # Tìm title tuỳ theo loại kiến thức
                    k_type = knowledge_item.get("type", "")
                    title = ""
                    if k_type and k_type in knowledge_item:
                        title = knowledge_item[k_type].get("title", "")
                    elif "root_word" in knowledge_item.get("word_derivatives", {}):
                        title = "Phái sinh từ " + knowledge_item["word_derivatives"]["root_word"]
                    
                    if title:
                        used_extra_knowledge.append(title)
            
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
    # Tham số
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PDF_FILE_PATH = os.path.join(base_dir, "hsk_ppt", "input", "HSK2", "Bài 4_你穿红色的很好看.pdf")
    PROMPT_FILE_PATH = os.path.join(base_dir, "resources", "prompts", "ppt_generation", "Prompt_Bai_Khoa.txt")
    OUTPUT_JSON_FILE = os.path.join(base_dir, "hsk_ppt", "HSK2_BK_test_output.json")
    HSK_LEVEL = "HSK2"
    
    with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
        base_prompt_text = f.read()
            
    result = process_full_hsk_lesson(
        pdf_path=PDF_FILE_PATH, 
        base_prompt=base_prompt_text, 
        level=HSK_LEVEL,
        output_json_path=OUTPUT_JSON_FILE
    )
        
    print(f"\n✅ THÀNH CÔNG! Đã xử lý xong file PDF: {PDF_FILE_PATH}")