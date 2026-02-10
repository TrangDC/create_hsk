# services/chinese_tts.py
"""
HSK Vocabulary Text-to-Speech Generator using Google Cloud TTS
"""

import pandas as pd
import os
import re
from google.cloud import texttospeech
from google.oauth2 import service_account
from dotenv import load_dotenv
load_dotenv()
import requests


def get_sheets_with_hsk(filepath):
    try:
        xl = pd.ExcelFile(filepath)
        sheets = xl.sheet_names
        hsk_sheets = [sheet for sheet in sheets if "HSK" in sheet]
        return hsk_sheets
    except FileNotFoundError:
        return "Error: File not found."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def clean_vocabulary(vocabulary_array):
    cleaned_vocabulary = []
    for item in vocabulary_array:
        if isinstance(item, str):  # Check if the item is a string
            cleaned_item = re.sub(r'\s*\(\s*.*?\s*\)\s*', '', item)
            cleaned_vocabulary.append(cleaned_item)
        else:
            cleaned_vocabulary.append(item)  # Append as is if it's not a string
    return cleaned_vocabulary

def processing_sheet(filepath, sheetname):
    """Process a single sheet from the Excel file"""
    # Đọc file Excel, với tiêu đề ở dòng đầu tiên (header=0)
    df = pd.read_excel(filepath, sheet_name=sheetname, header=0)
    
    # In ra tất cả các cột để debug
    print(f"Available columns in {sheetname}: {df.columns.tolist()}")
    
    # Hàm chuẩn hóa tên cột (bỏ dấu cách thừa, chuyển chữ thường)
    def normalize_column_name(col_name):
        if isinstance(col_name, str):
            return col_name.strip().lower()
        return str(col_name).strip().lower()
    
    # Tạo dict mapping từ tên cột chuẩn hóa sang tên cột gốc
    normalized_columns = {normalize_column_name(col): col for col in df.columns}
    
    # Tìm cột tương ứng với các tên khác nhau
    column_mapping = {
        'stt': None,
        'vocabulary': None,
        'example': None,
        'lesson': None
    }
    
    # Các tên cột có thể cho STT
    stt_variants = ['stt', 'no', 'number', 'số']
    for variant in stt_variants:
        if variant in normalized_columns:
            column_mapping['stt'] = normalized_columns[variant]
            break
    
    # Các tên cột có thể cho Từ vựng
    vocab_variants = ['từ vựng', 'vocabulary', 'word', 'từ', 'chinese']
    for variant in vocab_variants:
        if variant in normalized_columns:
            column_mapping['vocabulary'] = normalized_columns[variant]
            break
    # Thử tìm cột có chứa "vựng" hoặc "vocab"
    if not column_mapping['vocabulary']:
        for norm_name, orig_name in normalized_columns.items():
            if 'vựng' in norm_name or 'vocab' in norm_name:
                column_mapping['vocabulary'] = orig_name
                break
    
    # Các tên cột có thể cho Ví dụ
    example_variants = ['ví dụ làm file nghe', 'ví dụ', 'example', 'sentence']
    for variant in example_variants:
        if variant in normalized_columns:
            column_mapping['example'] = normalized_columns[variant]
            break
    # Thử tìm cột có chứa "ví dụ" hoặc "example"
    if not column_mapping['example']:
        for norm_name, orig_name in normalized_columns.items():
            if 'ví dụ' in norm_name or 'example' in norm_name:
                column_mapping['example'] = orig_name
                break
    
    # Các tên cột có thể cho STT Bài
    lesson_variants = ['stt bài', 'lesson', 'unit', 'bài']
    for variant in lesson_variants:
        if variant in normalized_columns:
            column_mapping['lesson'] = normalized_columns[variant]
            break
    # Thử tìm cột có chứa "bài" hoặc "lesson"
    if not column_mapping['lesson']:
        for norm_name, orig_name in normalized_columns.items():
            if 'bài' in norm_name or 'lesson' in norm_name:
                column_mapping['lesson'] = orig_name
                break
    
    print(f"Column mapping: {column_mapping}")
    
    # Kiểm tra cột bắt buộc
    if not column_mapping['vocabulary']:
        raise ValueError(f"Cannot find vocabulary column in sheet {sheetname}")
    if not column_mapping['stt']:
        raise ValueError(f"Cannot find STT column in sheet {sheetname}")
    
    # Tìm dòng cuối có dữ liệu trong cột từ vựng
    last_row_read = df[df[column_mapping['vocabulary']].notna()].index[-1] + 1
    data = pd.read_excel(filepath, sheet_name=sheetname, header=0, nrows=last_row_read)
    
    # Chọn các cột cần thiết (chỉ chọn các cột tồn tại)
    columns_to_extract = [column_mapping['stt'], column_mapping['vocabulary']]
    if column_mapping['example']:
        columns_to_extract.append(column_mapping['example'])
    if column_mapping['lesson']:
        columns_to_extract.append(column_mapping['lesson'])
    
    data = data[columns_to_extract]

    # Loại bỏ các hàng trống hoàn toàn trong các cột đã chọn
    data = data.dropna(how="all", subset=columns_to_extract)
    data = data.where(pd.notnull(data), None)

    # Xử lý cột "STT" để đảm bảo không bị đọc thành số thập phân
    if data[column_mapping['stt']].dtype == 'float64':
        if data[column_mapping['stt']].isna().sum() == 0:
            data[column_mapping['stt']] = data[column_mapping['stt']].astype(int)
        else:
            data[column_mapping['stt']] = data[column_mapping['stt']].astype(str)

    # Chuẩn hóa cột "STT bài" nếu tồn tại
    def propagate_numbers(series):
        last_valid_number = None
        result = []
        for value in series:
            if isinstance(value, int) or (isinstance(value, float) and not pd.isna(value)):
                last_valid_number = int(value)
            result.append(last_valid_number if last_valid_number is not None else 1)
        return result

    # Áp dụng hàm chuẩn hóa cho cột "STT bài" nếu có
    if column_mapping['lesson']:
        data[column_mapping['lesson']] = propagate_numbers(data[column_mapping['lesson']])
        sttbai_array = data[column_mapping['lesson']].tolist()
    else:
        # Nếu không có cột STT Bài, tạo mảng với giá trị 1 cho tất cả
        sttbai_array = [1] * len(data)
    
    stt_array = data[column_mapping['stt']].tolist()
    cleaned_vocabulary_array = clean_vocabulary(data[column_mapping['vocabulary']].tolist())
    
    # Xử lý cột ví dụ nếu có
    if column_mapping['example']:
        examples_array = data[column_mapping['example']].tolist()
    else:
        # Nếu không có cột ví dụ, tạo mảng None
        examples_array = [None] * len(data)
    
    # Hiển thị dữ liệu đã chuẩn hóa
    print(f"Processed {len(stt_array)} rows")
    print(data.head())
    
    return stt_array, cleaned_vocabulary_array, examples_array, sttbai_array

# Khởi tạo Google Cloud TTS client
def init_google_tts_client():
    """Initialize Google Cloud TTS client using service account from environment variables"""
    
    credentials_dict = {
        "type": os.getenv("TYPE"),
        "project_id": os.getenv("PROJECT_ID"),
        "private_key_id": os.getenv("PRIVATE_KEY_ID"),
        "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n') if os.getenv("PRIVATE_KEY") else None,
        "client_email": os.getenv("CLIENT_EMAIL"),
        "client_id": os.getenv("CLIENT_ID", ""),
        "auth_uri": os.getenv("AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("TOKEN_URI", "https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
        "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL", ""),
        "universe_domain": os.getenv("UNIVERSE_DOMAIN", "googleapis.com")
    }
    
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    return client

def text_to_speech_google(client, text, output_file):
    """Convert text to speech using Google Cloud TTS and save to file"""
    try:
        # Thiết lập input text
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Cấu hình giọng nói (Tiếng Trung)
        voice = texttospeech.VoiceSelectionParams(
            language_code="cmn-CN",  # Mandarin Chinese
            name="cmn-CN-Wavenet-A",  # Giọng nữ Wavenet chất lượng cao
            # Có thể thay đổi thành:
            # "cmn-CN-Wavenet-B" (nam)
            # "cmn-CN-Wavenet-C" (nam)
            # "cmn-CN-Wavenet-D" (nữ)
            # "cmn-CN-Standard-A", "cmn-CN-Standard-B", etc. (giọng standard)
        )

        # Cấu hình audio output
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,  # Tốc độ nói (0.25 đến 4.0)
            pitch=0.0,  # Cao độ giọng nói (-20.0 đến 20.0)
        )

        # Thực hiện text-to-speech request
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Lưu audio vào file
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
        
        print(f"Audio saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"Error generating speech for '{text}': {e}")
        return False

def generate_chinese_tts():
    """Main function to process HSK vocabulary and generate audio files"""
    # Đường dẫn file Excel (CẬP NHẬT ĐƯỜNG DẪN NÀY)
    file_path = r"D:\Edmicro\Tools\create_hsk\input\Từ vựng tiếng Trung - Flashcard.xlsx"
    if not file_path:
        file_path = 'Bản sao của Từ vựng HSK 5.xlsx'  # Đường dẫn mặc định
    
    # Kiểm tra file tồn tại
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        print(f"Current directory: {os.getcwd()}")
        return
    
    # Lấy danh sách các sheet có chứa "HSK"
    hsk_sheets = get_sheets_with_hsk(file_path)
    if isinstance(hsk_sheets, str):  # Nếu có lỗi
        print(hsk_sheets)
        return
    print(f"Found HSK sheets: {hsk_sheets}")
    
    # Khởi tạo Google TTS client
    print("\nInitializing Google Cloud TTS client...")
    try:
        tts_client = init_google_tts_client()
        print("Client initialized successfully!")
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease set the required environment variables:")
        print("  - TYPE")
        print("  - PROJECT_ID")
        print("  - PRIVATE_KEY")
        print("  - CLIENT_EMAIL")
        return
    except Exception as e:
        print(f"Failed to initialize Google TTS client: {e}")
        return
    
    # Hỏi thư mục output
    output_base = input("Enter output directory (or press Enter for './Output'): ").strip()
    if not output_base:
        output_base = './Output'
    
    # Xử lý từng sheet
    for sheetname in hsk_sheets:
        print(f"\n{'='*60}")
        print(f"Processing sheet: {sheetname}")
        print(f"{'='*60}")
        
        try:
            stt_array, cleaned_vocabulary_array, examples_array, sttbai_array = processing_sheet(file_path, sheetname)
        except Exception as e:
            print(f"Error processing sheet {sheetname}: {e}")
            continue
        
        output_dir = os.path.join(output_base, sheetname)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        # Tạo file audio cho từ vựng
        vocab_count = len([x for x in cleaned_vocabulary_array if x is not None])
        print(f"\nGenerating audio for vocabulary ({vocab_count} items)...")
        for i, text in enumerate(cleaned_vocabulary_array):
            if text is not None:
                output_file = f'{output_dir}/B{sttbai_array[i]}_{stt_array[i]}.mp3'
                if os.path.exists(output_file):
                    os.remove(output_file)
                print(f"  [{i+1}/{vocab_count}] Generating: {text}")
                text_to_speech_google(tts_client, text, output_file)
        
        # Tạo file audio cho ví dụ
        example_count = len([x for x in examples_array if x is not None])
        print(f"\nGenerating audio for examples ({example_count} items)...")
        for i, text in enumerate(examples_array):
            if text is not None and isinstance(text, str) and text.strip():  # Kiểm tra text hợp lệ
                output_file = f'{output_dir}/B{sttbai_array[i]}_VD_{stt_array[i]}.mp3'
                if os.path.exists(output_file):
                    os.remove(output_file)
                # Truncate text hiển thị an toàn
                display_text = text[:50] + "..." if len(text) > 50 else text
                print(f"  [{i+1}/{example_count}] Generating example: {display_text}")
                text_to_speech_google(tts_client, text, output_file)
    
    print(f"\n{'='*60}")
    print("All done!")
    print(f"{'='*60}")

def generate_single_audio(client, text, output_path):
    """
    Hàm hỗ trợ sinh audio lẻ từ bên ngoài (không qua Excel input).
    Args:
        client: Google TTS Client object
        text: Nội dung cần đọc
        output_path: Đường dẫn file mp3 đầu ra
    Returns:
        bool: True nếu thành công, False nếu lỗi
    """
    if not text:
        return False
    
    # 1. Đảm bảo thư mục cha tồn tại
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    # 2. Gọi hàm sinh audio cốt lõi
    # Lưu ý: Hàm text_to_speech_google đã được định nghĩa ở trên trong file cũ
    return text_to_speech_google(client, text, output_path)


# --- CẤU HÌNH NARAKEET ---
# API Key từ đoạn code của bạn
NARAKEET_API_KEY = 'QXGh0KOTHI7CaR9Vdh61M77FPRV98ZBMdNALHcsd'

# Giọng đọc Tiếng Trung (Mandarin)
# Các lựa chọn: 'Luli' (Nữ), 'Wang-Shu' (Nam), 'Chow' (Nam), 'Bao' (Nam)
VOICE_NAME = 'yifei'

def generate_single_audio_narakeet(text, output_path):
    """
    Sinh file MP3 từ text sử dụng Narakeet API.
    Args:
        text: Nội dung cần đọc (Tiếng Trung)
        output_path: Đường dẫn lưu file
    """
    if not text:
        return False
        
    # 1. Đảm bảo thư mục tồn tại
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        
    # 2. Cấu hình Request
    url = f'https://api.narakeet.com/text-to-speech/mp3?voice={VOICE_NAME}'
    
    options = {
        'headers': {
            'Accept': 'application/octet-stream',
            'Content-Type': 'text/plain',
            'x-api-key': NARAKEET_API_KEY,
        },
        'data': text.encode('utf8')
    }

    # 3. Gọi API
    try:
        response = requests.post(url, **options)
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            # print(f"   🔊 Đã sinh audio: {os.path.basename(output_path)}")
            return True
        else:
            print(f"   ❌ Lỗi Narakeet ({response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Lỗi kết nối Narakeet: {e}")
        return False

if __name__ == "__main__":
    generate_chinese_tts()