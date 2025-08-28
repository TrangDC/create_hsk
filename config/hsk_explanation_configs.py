import os

# 1. Import các hàm renderer từ module formatters
from services.explanation_sheet_formatters import (
    render_individual_img_explanation,
    render_shared_image_comprehension_explanation,
    render_reading_comp_explanation,
    render_image_matching_explanation,
    render_sentence_matching_explanation,
    render_word_fill_explanation,
)

# 2. Import các hàm xây dựng prompt từ module explanation_prompt_builders
from services.explanation_prompt_builders import (
    build_individual_image_matching_prompt,
    build_shared_image_comprehension_prompt,
    build_reading_comprehension_choice_prompt,
    build_image_matching_questions_prompt,
    build_sentence_matching_questions_prompt,
    build_word_fill_in_questions_prompt,
    build_script_hinh_anh_prompt,
    build_tuvung_hinh_anh_prompt,
)

# --- CẤU HÌNH ĐƯỜNG DẪN PROMPT VÀ SCHEMA ---
# Xác định các đường dẫn gốc
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(ROOT_DIR, "..", "resources") # Đi ngược ra 1 cấp
EXPLANATION_PROMPTS_DIR = os.path.join(RESOURCES_DIR, "prompts", "explanation")
EXPLANATION_SCHEMAS_DIR = os.path.join(RESOURCES_DIR, "schema", "explanation")

# Cấu hình cho HSK1
HSK1_EXPLANATION_CONFIGS = {
    "individual_image_matching": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_individual_img_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_individual_img_explanation_schema.json"),
        "prompt_builder": build_individual_image_matching_prompt,
        "sheet_name": "TN PA đúng (img) (HSK1)",
        "renderer": render_individual_img_explanation
    },
    "shared_image_comprehension": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_shared_img_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_shared_img_explanation_schema.json"),
        "prompt_builder": build_shared_image_comprehension_prompt,
        "sheet_name": "TN PA đúng (img) (HL) (HSK1)",
        "renderer": render_shared_image_comprehension_explanation
    },
    "reading_comprehension_choice": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_reading_comp_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_reading_comp_explanation_schema.json"),
        "prompt_builder": build_reading_comprehension_choice_prompt,
        "sheet_name": "TN PA đúng (HSK1)",
        "renderer": render_reading_comp_explanation
    },
    "image_matching_questions": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_img_match_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_img_match_explanation_schema.json"),
        "prompt_builder": build_image_matching_questions_prompt,
        "sheet_name": "TN chọn ảnh (img) (HL) (HSK1)",
        "renderer": render_image_matching_explanation

    },
    "sentence_matching_questions": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_sentence_match_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_sentence_match_explanation_schema.json"),
        "prompt_builder": build_sentence_matching_questions_prompt,
        "sheet_name": "TN câu trả lời đúng (HL) (HSK1)",
        "renderer": render_sentence_matching_explanation
    },
    "word_fill_in_questions": {
        "prompt_path": os.path.join(EXPLANATION_PROMPTS_DIR, "hsk1", "hsk1_word_fill_explanation_prompt.txt"),
        "schema_path": os.path.join(EXPLANATION_SCHEMAS_DIR, "hsk1", "hsk1_word_fill_explanation_schema.json"),
        "prompt_builder": build_word_fill_in_questions_prompt,
        "sheet_name": "TN chọn từ đúng (HL) (HSK1)",
        "renderer": render_word_fill_explanation
    }
}

# --- CÁC HÀM "NHÀ MÁY" ĐỂ LẤY CẤU HÌNH ĐÚNG ---

def get_explanation_config(hsk_level: str):
    """Trả về dictionary cấu hình prompt cho cấp độ HSK được chỉ định."""
    if hsk_level == 'hsk1':
        return HSK1_EXPLANATION_CONFIGS
    # elif hsk_level == 'hsk2':
    #     return HSK2_EXPLANATION_PROMPTS
    print(f"Cảnh báo: Không tìm thấy cấu hình prompt lời giải cho '{hsk_level}'.")
    return None