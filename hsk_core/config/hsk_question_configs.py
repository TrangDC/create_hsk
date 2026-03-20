# hsk_core/config/hsk_question_configs.py

# Import các hàm xử lý từ Phase 4 (tạm thời đặt tên theo formatters)
# Khi bạn tạo file formatters/question_excel_formatter.py, các hàm này sẽ nằm ở đó
from formatters.question_excel_formatter import (
    populate_individual_image_matching, 
    populate_shared_image_comprehension,      
    populate_reading_comprehension_choice,    
    populate_image_matching_shared,           
    populate_sentence_matching_shared,        
    populate_word_fill_in_shared,             
    populate_true_false_from_array,           
    populate_true_false_image,                
    populate_reading_comprehension_dialogue,  
    populate_true_false_statement,            
    populate_sentence_matching_inverted,     
    populate_true_false_listening_choice, 
    populate_reading_comprehension_v3, 
    populate_sentence_reordering, 
    populate_word_fill_in_display_answer, 
    populate_passage_with_multiple_questions, 
    populate_sentence_sequence_reordering, 
    populate_passage_cloze,
    populate_main_idea_comprehension,
    populate_long_passage_comprehension,
    populate_image_with_word_sentence_creation,
    populate_writing_from_keywords,
    populate_writing_from_image
)

# Cấu hình HSK1: Đã tách thành 8 prompt riêng biệt
HSK1_PROMPT_CONFIGS = {
    "hsk1_1_ds_img": {
        "processors": [("ds_img_data", "ĐS (img) HSK1", populate_true_false_from_array)],
        "matrix_name": "Nghe từ/cụm từ + tranh Đ/S" 
    },
    "hsk1_2_tn_pa_dung_img": {
        "processors": [("individual_image_matching", "TN PA đúng (img) (HSK1)", populate_individual_image_matching)],
        "matrix_name": "Nghe câu đơn + chọn tranh" 
    },
    "hsk1_3_tn_pa_dung_img_hl": {
        "matrix_name": "Nghe hội thoại + nối tranh",
        "processors": [("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK1)", populate_shared_image_comprehension)]
    },
    "hsk1_4_tn_pa_dung": {
        "processors": [("reading_comprehension_choice", "TN PA đúng (HSK1)", populate_reading_comprehension_choice)],
        "matrix_name": "Nghe câu / đoạn ngắn + trả lời"
    },
    "hsk1_5_ds_no_sub": {
        "matrix_name": "Đọc từ + tranh Đ/S",
        "processors": [("ds_no_sub_data", "ĐS Ko phụ đề (img) HSK1", populate_true_false_from_array)]
    },
    "hsk1_6_tn_chon_anh_img_hl": {
        "matrix_name": "Đọc câu + nối tranh",
        "processors": [("image_matching_questions", "TN chọn ảnh (img) (HL) (HSK1)", populate_image_matching_shared)]
    },
    "hsk1_7_tn_cau_tra_loi_dung_hl": {
        "matrix_name": "Ghép câu hỏi với đáp án",
        "processors": [("sentence_matching_questions", "TN câu trả lời đúng (HL) (HSK1)", populate_sentence_matching_shared)]
    },
    "hsk1_8_tn_chon_tu_dung_hl": {
        "matrix_name": "Điền từ vào chỗ trống",
        "processors": [("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK1)", populate_word_fill_in_shared)]
    }
}

HSK2_PROMPT_CONFIGS = {
    # Dạng 1: Đúng sai (img) (HSK2)
    "hsk2_1_prompt_ds_img": {
        "processors": [
            ("true_false_image_questions", "Đúng sai (img) (HSK2)", populate_true_false_image),
        ]
    },
    # Dạng 2: TN PA đúng (img) (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_2_prompt_tn_pa_dung_hl": {
        "processors": [
            ("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK2)", populate_shared_image_comprehension),
        ]
    },
    # Dạng 3: TN PA đúng (HSK2)
    "hsk2_3_prompt_tn_pa_dung": {
        "processors": [
            ("reading_comprehension_dialogue_2_lines", "TN PA đúng (HSK2)", populate_reading_comprehension_dialogue),
        ]
    },
    # Dạng 4: TN PA đúng_v2 (HSK2) - Có thể tái sử dụng hàm của Dạng 3
    "hsk2_4_prompt_tn_pa_dung_v2": {
        "processors": [
            ("reading_comprehension_dialogue_4_lines", "TN PA đúng_v2 (HSK2)", populate_reading_comprehension_dialogue),
        ]
    },
    # Dạng 5: TN chọn ảnh (img) (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_5_prompt_tn_chon_anh_hl": {
        "processors": [
            ("image_matching_questions", "TN chọn ảnh (img) (HL) (HSK2)", populate_image_matching_shared),
        ]
    },
    # Dạng 7: TN chọn từ đúng (HL) (HSK2) - Tái sử dụng hàm của HSK1
    "hsk2_7_prompt_tn_chon_tu_dung_hl": {
        "processors": [
            ("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK2)", populate_word_fill_in_shared),
        ]
    },
    # Dạng 6: ĐS lựa chọn (HSK2)
    "hsk2_6_prompt_ds_lua_chon": {
        "processors": [
            ("true_false_statement_questions", "ĐS lựa chọn (HSK2)", populate_true_false_statement),
        ]
    },
    # Dạng 8: TN câu trả lời đúng (HL) (HSK2)
    "hsk2_8_prompt_tn_cau_tra_loi_dung_hl": {
        "processors": [
            ("sentence_matching_inverted_questions", "TN câu trả lời đúng (HL) (HSK2)", populate_sentence_matching_inverted),
        ]
    },
}

HSK3_PROMPT_CONFIGS = {
    "hsk3_1_prompt_tn_pa_dung_hl": {
        "processors": [
            ("shared_image_comprehension", "TN PA đúng (img) (HL) (HSK3)", populate_shared_image_comprehension),
        ]
    },
    "hsk3_2_prompt_ds_nghe_chon": {
        "processors": [
            ("true_false_listening_choice", "ĐS nghe chọn (HSK3)", populate_true_false_listening_choice)
        ]
    },
    "hsk3_3_prompt_tn_pa_dung_no_pinyin": {
        "processors": [
            ("reading_comprehension_dialogue_2_lines", "TN PA đúng ko pinyin (HSK3)", populate_reading_comprehension_dialogue),
        ]
    },
    "hsk3_4_prompt_tn_pa_dung_no_pinyin_v2": {
        "processors": [
            ("reading_comprehension_dialogue_4_lines", "TN PA đúng ko pinyin_v2 (HSK3)", populate_reading_comprehension_dialogue),
        ]
    },
    "hsk3_5_prompt_tn_cau_tra_loi_dung_hl": {
        "processors": [
            ("sentence_matching_inverted_questions", "TN câu trả lời đúng (HL) (HSK3)", populate_sentence_matching_inverted),
        ]
    },
    "hsk3_6_prompt_tn_chon_tu_dung_hl": {
        "processors": [
            ("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK3)", populate_word_fill_in_shared),
        ]
    },
    "hsk3_7_prompt_tn_pa_dung_no_pinyin_v3": {
        "processors": [
            ("reading_comprehension_no_pinyin_v3", "TN PA đúng ko pinyin_v3 (HSK3)", populate_reading_comprehension_v3)
        ]
    },
    "hsk3_8_prompt_sap_xep_cau": {
        "processors" : [("sentence_reordering", "Sắp xếp câu (HSK3)", populate_sentence_reordering)]
    },
    "hsk3_9_prompt_dien_tu_dung": {
        "processors" : [("word_fill_in_display_answer", "Điền từ đúng (HSK3)", populate_word_fill_in_display_answer)]
    }
}

HSK4_PROMPT_CONFIGS = {
    "hsk4_1_prompt_ds_nghe_chon": {
        "processors": [("true_false_listening_choice", "ĐS nghe chọn (HSK4)", populate_true_false_listening_choice)]
    },
    "hsk4_2_prompt_tn_pa_dung": {
        "processors": [("reading_comprehension_dialogue_2_lines", "TN PA đúng (HSK4)", populate_reading_comprehension_dialogue)]
    },
    "hsk4_3_prompt_tn_pa_dung_v2": {
        "processors": [("reading_comprehension_dialogue_4_lines", "TN PA đúng_v2 (HSK4)", populate_reading_comprehension_dialogue)]
    },
    "hsk4_4_prompt_tn_nghe_hieu": {
        "processors": [("listening_comprehension", "TN Nghe hiểu (HSK4)", populate_passage_with_multiple_questions)]
    },
    "hsk4_5_prompt_tn_chon_tu_dung_hl": {
        "processors": [("word_fill_in_questions", "TN chọn từ đúng (HL) (HSK4)", populate_word_fill_in_shared)]
    },
    "hsk4_6_prompt_sap_xep_cac_cau": {
        "processors": [("sentence_sequence_reordering", "Sắp xếp các câu (HSK4)", populate_sentence_sequence_reordering)]
    },
    "hsk4_7_prompt_tn_pa_dung_no_pinyin_v3": {
        "processors": [("reading_comprehension_no_pinyin_v3", "TN PA đúng ko pinyin_v3 (HSK4)", populate_reading_comprehension_v3)]
    },
    "hsk4_8_prompt_tn_doc_hieu_ngan": {
        "processors": [("reading_comprehension_short_passage", "TN Đọc hiểu ngắn (HSK4)", populate_passage_with_multiple_questions)]
    },
    "hsk4_9_prompt_sap_xep_cau": {
        "processors": [("sentence_reordering", "Sắp xếp câu (HSK4)", populate_sentence_reordering)]
    },
    "hsk4_10_prompt_anh_voi_tu": {
        "processors": [("image_with_word_sentence_creation", "Ảnh với từ (img) (HSK4)", populate_image_with_word_sentence_creation)]
    }
}

HSK5_PROMPT_CONFIGS = {
    "hsk5_1_prompt_tn_pa_dung": {
        "processors": [("reading_comprehension_dialogue_2_lines","TN PA đúng (HSK5)",populate_reading_comprehension_dialogue)]
    },
    "hsk5_2_prompt_tn_pa_dung_v2": {
        "processors": [("reading_comprehension_dialogue_4_lines","TN PA đúng_v2 (HSK5)",populate_reading_comprehension_dialogue)]
    },
    "hsk5_3_prompt_tn_nghe_hieu": {
        "processors": [("listening_comprehension","TN Nghe hiểu (HSK5)",populate_passage_with_multiple_questions)]
    },
    "hsk5_4_prompt_dien_tu_doan_van": {
        "processors": [("passage_cloze","Điền từ đoạn văn (HSK5)", populate_passage_cloze)]
    },
    "hsk5_5_prompt_chon_chu_de": {
        "processors": [("main_idea_comprehension","Chọn chủ đề đoạn văn (HSK5)", populate_main_idea_comprehension)]
    },
    "hsk5_6_prompt_tn_doc_hieu_img": {
        "processors": [("long_passage_comprehension","TN Đọc hiểu (img) (HSK5)", populate_long_passage_comprehension)]
    },
    "hsk5_7_prompt_sap_xep_cau": {
        "processors": [("sentence_reordering","Sắp xếp câu (HSK5)",populate_sentence_reordering)]
    },
    "hsk5_8_prompt_viet_dua_vao_tu": {
        "processors": [("writing_from_keywords","Viết dựa vào từ (HSK5)",populate_writing_from_keywords)]
    },
    "hsk5_9_prompt_viet_dua_vao_anh": {
        "processors": [("writing_from_image","Viết dựa vào ảnh (img) (HSK5)",populate_writing_from_image)]
    }
}


# Hàm nhà máy để lấy config
def get_prompt_config(level: str):
    configs = {
        "hsk1": HSK1_PROMPT_CONFIGS,
        "hsk2": HSK2_PROMPT_CONFIGS,
        "hsk3": HSK3_PROMPT_CONFIGS,
        "hsk4": HSK4_PROMPT_CONFIGS,
        "hsk5": HSK5_PROMPT_CONFIGS
    }
    return configs.get(level.lower())