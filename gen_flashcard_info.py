import os
import json
import time
import pandas as pd
from PIL import Image

# Import services
from call_vertexai import generate_content
from services.image_gen_service import ImageGenerationService
from services.gif_downloader import StrokeGifManager
from services.chinese_tts import generate_single_audio_narakeet
from services.media_merger import create_merged_gif
from services.input_handler import InputDataManager

# --- CẤU HÌNH ---
# 1. Đường dẫn file Excel đầu vào (CẬP NHẬT ĐƯỜNG DẪN CỦA BẠN TẠI ĐÂY)
INPUT_EXCEL_PATH = r"D:\Edmicro\Tools\create_hsk\input\Flashcard input_Từ Vựng HSK 3.0.xlsx"

# 2. Cấu hình Output
OUTPUT_BASE = "output/flashcards"
IMG_FINAL_DIR = os.path.join(OUTPUT_BASE, "images")
AUDIO_DIR = os.path.join(OUTPUT_BASE, "audio")
RAW_IMG_DIR = os.path.join(OUTPUT_BASE, "raw_images")
RAW_GIF_DIR = os.path.join(OUTPUT_BASE, "raw_gifs")

# Cấu hình file Resource (Schema/Prompt)
SCHEMA_PATH = "resources/schema/flashcard_schema.json"
PROMPT_PATH = "resources/prompts/enrich_vocab.txt"
MASCOT_PDF_PATH = "resources/panda_mascot.pdf"

def setup_folders():
    """Tạo các thư mục cần thiết"""
    for d in [OUTPUT_BASE, IMG_FINAL_DIR, AUDIO_DIR, RAW_IMG_DIR, RAW_GIF_DIR, "resources/schema", "resources/prompts"]:
        if not os.path.exists(d): os.makedirs(d)

def setup_resources():
    """Thiết lập Schema và Prompt cho Vertex AI (Giữ nguyên logic cũ)"""
    # 1. Schema
    schema_data = {
        "type": "OBJECT",
        "properties": {
            "pinyin": {"type": "STRING", "description": "Phiên âm Pinyin của từ (có thanh điệu)"},
            "part_of_speech": {"type": "STRING", "description": "Từ loại (Danh từ/Động từ...)"},
            "word_meaning_vn": {"type": "STRING", "description": "Nghĩa tiếng Việt của từ"},
            "example_sentence_cn": {"type": "STRING", "description": "Câu ví dụ tiếng Trung (Nếu input thiếu thì tự đặt câu)"},
            "example_pinyin": {"type": "STRING", "description": "Pinyin của câu ví dụ"},
            "example_meaning_vn": {"type": "STRING", "description": "Nghĩa tiếng Việt của câu ví dụ"},
            "use_mascot": {"type": "BOOLEAN", "description": "True nếu dùng Mascot Gấu trúc, False nếu vẽ đồ vật/cảnh vật."},
            "image_prompt_en": {"type": "STRING", "description": "Prompt tiếng Anh để vẽ ảnh minh họa."}
        },
        "required": ["pinyin", "part_of_speech", "word_meaning_vn", "example_sentence_cn", "example_pinyin", "example_meaning_vn", "use_mascot", "image_prompt_en"]
    }
    with open(SCHEMA_PATH, 'w', encoding='utf-8') as f:
        json.dump(schema_data, f, ensure_ascii=False, indent=2)
            
    # 2. CẬP NHẬT PROMPT (Hướng dẫn AI ưu tiên context đầu vào)
    prompt_content = """
Bạn là chuyên gia giáo dục HSK.
Input Context:
- Từ vựng: '{word}'
- Nghĩa gốc (Có thể trống): '{meaning}'
- Ví dụ gốc (Có thể trống): '{example}'

Nhiệm vụ:
1. Hoàn thiện thông tin còn thiếu (Pinyin, Từ loại, Nghĩa, Ví dụ). 
   - QUAN TRỌNG: Nếu Nghĩa gốc hoặc Ví dụ gốc đã có trong Input, hãy DÙNG NÓ để tạo Pinyin/Dịch tương ứng. KHÔNG được đổi nghĩa khác.
   - Nếu Input trống, hãy tự đề xuất nội dung phù hợp trình độ HSK.
2. Quyết định hình ảnh:
   - 'use_mascot': True nếu là hành động/cảm xúc nhân hóa. False nếu là danh từ đồ vật cụ thể.
   - 'image_prompt_en': Viết prompt vẽ ảnh Flat illustration, nền trắng, nét vẽ đơn giản hiện đại.
"""
    with open(PROMPT_PATH, 'w', encoding='utf-8') as f:
        f.write(prompt_content.strip())

def main():
    print("🚀 BẮT ĐẦU CHƯƠNG TRÌNH...")
    setup_folders()
    setup_resources()
    
    # --- 1. XỬ LÝ INPUT TỪ EXCEL ---
    try:
        input_manager = InputDataManager(INPUT_EXCEL_PATH)
        
        # Chọn sheet
        # hsk_sheets = input_manager.get_hsk_sheets()
        # print(f"📄 Tìm thấy các sheet: {hsk_sheets}")
        target_sheet = "HSK1 test"  # Thay đổi theo nhu cầu của bạn
        
        # Lấy dữ liệu từ Class InputHandler
        input_data_list = input_manager.process_specific_sheet(target_sheet)
        
        if not input_data_list:
            print("❌ Không tìm thấy dữ liệu hoặc tên sheet sai.")
            return

    except Exception as e:
        print(f"❌ Lỗi Input Handler: {e}")
        return

    # --- 2. KHỞI TẠO SERVICES ---
    try:
        gif_manager = StrokeGifManager(gif_folder=RAW_GIF_DIR, png_folder=RAW_GIF_DIR)
        img_service = ImageGenerationService()
        # TTS không cần init client object vì dùng Narakeet REST API
        print("✅ Services initialized.")
    except Exception as e:
        print(f"❌ Init Service failed: {e}")
        return

    excel_results = []
    print(f"--- BẮT ĐẦU XỬ LÝ {len(input_data_list)} TỪ ---")

    for idx, item in enumerate(input_data_list):
        word = item['word']
        print(f"\n======== ĐANG XỬ LÝ: {word} ({item['final_title']}) ========")
        
        # --- KIỂM TRA FILE ĐÃ TỒN TẠI TRONG THƯ MỤC CHƯA ---
        expected_thumb_path = os.path.join(IMG_FINAL_DIR, item['filename_image'])
        expected_audio1_path = os.path.join(AUDIO_DIR, item['filename_audio_word'])
        expected_audio2_path = os.path.join(AUDIO_DIR, item['filename_audio_ex'])
        
        thumb_exists = os.path.exists(expected_thumb_path)
        audio1_exists = os.path.exists(expected_audio1_path)
        audio2_exists = os.path.exists(expected_audio2_path)
        
        # Kiểm tra xem text đã đầy đủ trong Excel chưa
        text_completed = bool(item['pinyin'] and item['type'] and item['meaning'] and item['example'])
        
        # Chỉ gọi Vertex AI nếu thiếu thông tin text HOẶC thiếu ảnh (vì AI sinh prompt vẽ ảnh)
        need_ai = not text_completed or not thumb_exists

        # Khởi tạo row_data với các thông tin cơ bản và điền sẵn media nếu có
        row_data = {
            "Title": item['final_title'],
            "word": word,
            "thumbnail": item['filename_image'] if thumb_exists else "",
            "audio1": item['filename_audio_word'] if audio1_exists else "",
            "audio2": item['filename_audio_ex'] if audio2_exists else ""
        }

        # NẾU ĐÃ ĐỦ HẾT FILE VÀ TEXT -> BỎ QUA CHẠY SANG TỪ KHÁC LUÔN
        if not need_ai and audio1_exists and (audio2_exists or not item['example']):
            print(f"   ✅ BỎ QUA - Đã có đủ Text và Media cho từ: {word}")
            row_data['pronunciation'] = item['pinyin']
            row_data['type'] = item['type']
            row_data['word_translation'] = item['meaning']
            row_data['phrace'] = item['example']
            row_data['pronunciation_phrace'] = item['ex_pinyin']
            row_data['phrace_translation'] = item['ex_meaning']
            excel_results.append(row_data)
            continue

        # --- A. GỌI VERTEX AI (Data Enrichment) ---
        ai_data = {}
        if need_ai:
            try:
                with open(PROMPT_PATH, 'r', encoding='utf-8') as f: prompt_temp = f.read()
                
                # Truyền dữ liệu từ Excel vào Prompt để AI hiểu ngữ cảnh
                prompt_input = prompt_temp.format(
                    word=word, 
                    meaning=item['meaning'] if item['meaning'] else "",
                    example=item['example'] if item['example'] else ""
                )
                
                temp_path = f"prompts/temp_{word}.txt"
                with open(temp_path, 'w', encoding='utf-8') as f: f.write(prompt_input)

                ai_data = generate_content(
                    prompt_file_path=temp_path,
                    schema_file_path=SCHEMA_PATH,
                    pdf_file_paths=[MASCOT_PDF_PATH], 
                    text_content=None,
                    service_tier="flex"
                )
                if os.path.exists(temp_path): os.remove(temp_path)
                
            except Exception as e:
                print(f"⚠️ Lỗi gọi AI: {e}. Sẽ sử dụng dữ liệu Excel tối đa.")

        # --- B. LOGIC MATCH THÔNG TIN (Excel ưu tiên -> rồi đến AI) ---
        
        # 1. Pinyin
        if item['pinyin']: 
            row_data['pronunciation'] = item['pinyin']
        else: 
            row_data['pronunciation'] = ai_data.get('pinyin', '')
            
        # 2. Từ loại (Type)
        if item['type']: 
            row_data['type'] = item['type']
        else: 
            row_data['type'] = ai_data.get('part_of_speech', '')
            
        # 3. Nghĩa từ (Word Translation)
        if item['meaning']: 
            row_data['word_translation'] = item['meaning']
        else: 
            # Schema mới đã có field này, AI sẽ trả về
            row_data['word_translation'] = ai_data.get('word_meaning_vn', '')

        # 4. Câu ví dụ (Phrase) & 5. Dịch ví dụ
        # Xác định câu ví dụ cuối cùng để dùng cho TTS và Excel
        final_phrase_cn = ""
        
        # Check Excel trước
        if item['example']:
            final_phrase_cn = item['example']
            row_data['phrace'] = item['example']
            
            # Nếu có câu ví dụ gốc, check xem có pinyin/dịch chưa
            if item['ex_pinyin']: row_data['pronunciation_phrace'] = item['ex_pinyin']
            else: row_data['pronunciation_phrace'] = ai_data.get('example_pinyin', '')
                
            if item['ex_meaning']: row_data['phrace_translation'] = item['ex_meaning']
            else: row_data['phrace_translation'] = ai_data.get('example_meaning_vn', '')
            
        else:
            # Nếu Excel không có ví dụ -> Lấy hoàn toàn từ AI
            final_phrase_cn = ai_data.get('example_sentence_cn', '') # Key mới trong Schema
            row_data['phrace'] = final_phrase_cn
            row_data['pronunciation_phrace'] = ai_data.get('example_pinyin', '')
            row_data['phrace_translation'] = ai_data.get('example_meaning_vn', '')

        # --- C. MEDIA GENERATION ---
        
        use_mascot = ai_data.get('use_mascot', True)
        
        # 1. Sinh ảnh AI và Gộp GIF (Chỉ làm khi chưa có file thumbnail)
        if not thumb_exists:
            row_number = item.get('excel_row', idx + 2)
            raw_img_path = os.path.join(RAW_IMG_DIR, f"{word}_{row_number}_ai.png")
            has_ai_img = False
            
            # Kiểm tra nếu ảnh chưa tồn tại thì mới sinh
            if not os.path.exists(raw_img_path):
                try:
                    prompt_img = ai_data.get('image_prompt_en', f"illustration of {word}")
                    pdf_send = MASCOT_PDF_PATH if use_mascot else None
                    # Aspect ratio 3:2 cho khổ ngang
                    img_bytes = img_service.generate_image_pdfs(prompt_img, pdf_send, aspect_ratio="3:2")
                    if img_bytes:
                        with open(raw_img_path, "wb") as f: f.write(img_bytes)
                        has_ai_img = True
                except Exception as e:
                    print(f"   ⚠️ Lỗi sinh ảnh AI: {e}")
            else:
                has_ai_img = True

            # 2. Tải GIF nét viết
            char_gif_paths = []
            for char in word:
                # download_char trả về (gif_path, png_path), ta chỉ lấy gif_path
                g, _ = gif_manager.download_char(char)
                if g and os.path.exists(g): char_gif_paths.append(g)

            # 3. Gộp ảnh (Thumbnail)
            final_gif_path = os.path.join(IMG_FINAL_DIR, item['filename_image'])
            
            if has_ai_img and char_gif_paths:
                success = create_merged_gif(raw_img_path, char_gif_paths, final_gif_path)
                if success:
                    print(f"   ✅ Ảnh gộp: {item['filename_image']}")
                    row_data['thumbnail'] = item['filename_image']
                else:
                    row_data['thumbnail'] = ""
            else:
                print("   ⚠️ Thiếu ảnh AI hoặc GIF nét viết -> Không tạo được Thumbnail")
                row_data['thumbnail'] = ""

        # 4. Sinh Audio (TTS - Narakeet)
        # a. Audio Từ (filename_audio_word từ InputHandler)
        if not audio1_exists:
            final_word_audio_path = os.path.join(AUDIO_DIR, item['filename_audio_word'])
            if generate_single_audio_narakeet(word, final_word_audio_path):
                row_data['audio1'] = item['filename_audio_word']
            else:
                row_data['audio1'] = ""

        # b. Audio Câu (filename_audio_ex từ InputHandler)
        if not audio2_exists and final_phrase_cn:
            final_ex_audio_path = os.path.join(AUDIO_DIR, item['filename_audio_ex'])
            if generate_single_audio_narakeet(final_phrase_cn, final_ex_audio_path):
                row_data['audio2'] = item['filename_audio_ex']
            else:
                row_data['audio2'] = ""

        # Lưu vào list kết quả
        excel_results.append(row_data)
        time.sleep(1) # Nghỉ nhẹ giữa các từ

    # --- 3. XUẤT FILE EXCEL CUỐI CÙNG ---
    print("\n📦 ĐANG XUẤT FILE EXCEL...")
    if excel_results:
        df = pd.DataFrame(excel_results)
        
        # Danh sách cột chuẩn Output
        cols_order = [
            "Title", "word", "pronunciation", "type", 
            "word_translation", "phrace", "pronunciation_phrace", 
            "phrace_translation", "thumbnail", "audio1", "audio2"
        ]
        
        # Lọc cột (để tránh lỗi nếu code logic trên có sai sót key)
        final_cols = [c for c in cols_order if c in df.columns]
        df = df[final_cols]
        
        # Tên file output dựa trên tên sheet input
        output_filename = f"Result_{target_sheet}.xlsx"
        excel_path = os.path.join(OUTPUT_BASE, output_filename)
        
        df.to_excel(excel_path, index=False)
        print(f"🎉 HOÀN TẤT! File kết quả: {excel_path}")
        print(f"📁 Folder Ảnh: {IMG_FINAL_DIR}")
        print(f"📁 Folder Audio: {AUDIO_DIR}")
    else:
        print("⚠️ Không có dữ liệu nào được xử lý thành công.")


if __name__ == "__main__":
    main()