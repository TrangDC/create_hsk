# config/hsk_question_configs.py

# 1. Import tất cả các hàm xử lý sheet từ services
from services.question_sheet_processors import (
    populate_individual_image_matching,       # HSK1 only
    populate_shared_image_comprehension,      # Reused in HSK2, HSK3
    populate_reading_comprehension_choice,    # HSK1 only
    populate_image_matching_shared,           # Reused in HSK2
    populate_sentence_matching_shared,        # HSK1 only
    populate_word_fill_in_shared,             # Reused in HSK2
    populate_true_false_from_array,           # HSK1 only
    populate_true_false_image,                # Dạng 1 - HSK2
    populate_reading_comprehension_dialogue,  # Dạng 3 & 4 - HSK2
    populate_true_false_statement,            # Dạng 6 - HSK2
    populate_sentence_matching_inverted,     # Dạng 8 - HSK2
    populate_true_false_listening_choice, # Dạng 2 - HSK3
    populate_reading_comprehension_v3, # Dạng 7 - HSK3
    populate_sentence_reordering, # Dạng 8 - HSK3
    populate_word_fill_in_display_answer # Dạng 9 - HSK3
)

# 2. Định nghĩa cấu hình cho các HSK
HSK1_PROMPT_CONFIGS = {
    "hsk1_prompt_2_3_4": {
        "type": "keyed",
        "processors": [
            ("individual_image_matching", "TN PA đúng (img) (HSK1)", populate_individual_image_matching),
            ("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK1)", populate_shared_image_comprehension),
            ("reading_comprehension_choice", "TN PA đúng (HSK1)", populate_reading_comprehension_choice),
        ]
    },
    "hsk1_prompt_6_7_8": {
        "type": "keyed",
        "processors": [
            ("image_matching_questions", "TN chọn ảnh (img) (HL) (HSK1)", populate_image_matching_shared),
            ("sentence_matching_questions", "TN câu trả lời đúng (HL) (HSK1)", populate_sentence_matching_shared),
            ("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK1)", populate_word_fill_in_shared),
        ]
    },
    "hsk1_prompt_ĐS": {
        "type": "array",
        "processor": populate_true_false_from_array
    }
}

HSK2_PROMPT_CONFIGS = {
    # Dạng 1: Đúng sai (img) (HSK2)
    "hsk2_1_prompt_ds_img": {
        "type": "keyed",
        "processors": [
            ("true_false_image_questions", "Đúng sai (img) (HSK2)", populate_true_false_image),
        ]
    },
    # Dạng 2: TN PA đúng (img) (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_2_prompt_tn_pa_dung_hl": {
        "type": "keyed",
        "processors": [
            ("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK2)", populate_shared_image_comprehension),
        ]
    },
    # Dạng 3: TN PA đúng (HSK2)
    "hsk2_3_prompt_tn_pa_dung": {
        "type": "keyed",
        "processors": [
            ("reading_comprehension_dialogue_2_lines", "TN PA đúng (HSK2)", populate_reading_comprehension_dialogue),
        ]
    },
    # Dạng 4: TN PA đúng_v2 (HSK2) - Có thể tái sử dụng hàm của Dạng 3
    "hsk2_4_prompt_tn_pa_dung_v2": {
        "type": "keyed",
        "processors": [
            ("reading_comprehension_dialogue_4_lines", "TN PA đúng_v2 (HSK2)", populate_reading_comprehension_dialogue),
        ]
    },
    # Dạng 5: TN chọn ảnh (img) (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_5_prompt_tn_chon_anh_hl": {
        "type": "keyed",
        "processors": [
            ("image_matching_questions", "TN chọn ảnh (img) (HL) (HSK2)", populate_image_matching_shared),
        ]
    },
    # Dạng 6: TN chọn từ đúng (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_6_prompt_tn_chon_tu_dung_hl": {
        "type": "keyed",
        "processors": [
            ("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK2)", populate_word_fill_in_shared),
        ]
    },
    # Dạng 7: ĐS lựa chọn (HSK2)
    "hsk2_7_prompt_ds_lua_chon": {
        "type": "keyed",
        "processors": [
            ("true_false_statement_questions", "ĐS lựa chọn (HSK2)", populate_true_false_statement),
        ]
    },
    # Dạng 8: TN câu trả lời đúng (HL) (HSK2)
    "hsk2_8_prompt_tn_cau_tra_loi_dung_hl": {
        "type": "keyed",
        "processors": [
            ("sentence_matching_inverted_questions", "TN câu trả lời đúng (HL) (HSK2)", populate_sentence_matching_inverted),
        ]
    },
}

HSK3_PROMPT_CONFIGS = {
    "hsk3_1_prompt_tn_pa_dung_hl": {
        "type": "keyed",
        "processors": [
            ("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK3)", populate_shared_image_comprehension),
        ]
    },
    "hsk3_2_prompt_ds_nghe_chon": {
        "type": "keyed",
        "processors": [
            ("true_false_listening_choice", "ĐS nghe chọn (HSK3)", populate_true_false_listening_choice)
        ]
    },
    "hsk3_3_prompt_tn_pa_dung_no_pinyin": {
        "type": "keyed",
        "processors": [
            ("reading_comprehension_dialogue_2_lines", "TN PA đúng ko pinyin (HSK3)", populate_reading_comprehension_dialogue),
        ]
    },
    "hsk3_4_prompt_tn_pa_dung_no_pinyin_v2": {
        "type": "keyed",
        "processors": [
            ("reading_comprehension_dialogue_4_lines", "TN PA đúng ko pinyin_v2 (HSK3)", populate_reading_comprehension_dialogue),
        ]
    },
    "hsk3_5_prompt_tn_cau_tra_loi_dung_hl": {
        "type": "keyed",
        "processors": [
            ("sentence_matching_inverted_questions", "TN câu trả lời đúng (HL) (HSK3)", populate_sentence_matching_inverted),
        ]
    },
    "hsk3_6_prompt_tn_chon_tu_dung_hl": {
        "type": "keyed",
        "processors": [
            ("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK3)", populate_word_fill_in_shared),
        ]
    },
    "hsk3_7_prompt_tn_pa_dung_v3": {
        "type": "keyed",
        "processors": [
            ("reading_comprehension_no_pinyin_v3", "TN PA đúng ko pinyin_v3 (HSK3)", populate_reading_comprehension_v3)
        ]
    },
    "hsk3_8_prompt_sap_xep_cau": {
        "type": "keyed",
        "processors" : [("sentence_reordering", "Sắp xếp câu (HSK3)", populate_sentence_reordering)]
    },
    "hsk3_9_prompt_dien_tu_dung": {
        "type": "keyed",
        "processors" : [("word_fill_in_display_answer", "Điền từ đúng (HSK3)", populate_word_fill_in_display_answer)]
    }
}

HSK4_PROMPT_CONFIGS = {}

HSK5_PROMPT_CONFIGS = {}

# 3. Hàm "nhà máy" để lấy cấu hình đúng
def get_prompt_config(hsk_level: str):
    """
    Trả về dictionary cấu hình PROMPT_CONFIGS tương ứng với cấp độ HSK.
    """
    if hsk_level == 'hsk1':
        return HSK1_PROMPT_CONFIGS
    elif hsk_level == 'hsk2':
        return HSK2_PROMPT_CONFIGS
    elif hsk_level == 'hsk3':
        return HSK3_PROMPT_CONFIGS
    elif hsk_level == 'hsk4':
        return HSK4_PROMPT_CONFIGS
    elif hsk_level == 'hsk5':
        return HSK5_PROMPT_CONFIGS
    # Thêm các hsk level khác ở đây
    
    # Trả về None nếu không tìm thấy
    print(f"Cảnh báo: Không tìm thấy cấu hình cho cấp độ '{hsk_level}'.")
    return None