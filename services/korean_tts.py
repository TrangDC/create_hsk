# services/korean_tts.py
import pandas as pd
import requests
import os

def generate_korean_tts():
    """
    Đọc file Excel và tạo file MP3 từ các ví dụ tiếng Hàn
    sử dụng Narakeet API
    """
    # Cấu hình API
    apikey = 'QXGh0KOTHI7CaR9Vdh61M77FPRV98ZBMdNALHcsd'
    voice = 'in-guk'
    url = f'https://api.narakeet.com/text-to-speech/mp3?voice={voice}'
    
    # Đường dẫn file Excel (cập nhật đường dẫn phù hợp với máy của bạn)
    file_path = r'D:\Edmicro\Tools\create_hsk\input\Từ vựng tiếng Hàn - Flashcard.xlsx'
    
    # Thư mục output
    output_base_dir = 'output'
    
    # Kiểm tra file có tồn tại không
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file '{file_path}'")
        print("Vui lòng cập nhật đường dẫn file trong script")
        return
    
    # Đọc tất cả sheet names
    xl = pd.ExcelFile(file_path)
    all_sheet_names = xl.sheet_names
    
    # Lọc các sheet name chứa ký tự '-'
    sheet_names_with_hyphen = [sheet_name for sheet_name in all_sheet_names if '-' in sheet_name]
    
    print(f"Tìm thấy {len(sheet_names_with_hyphen)} sheet cần xử lý")
    
    # Xử lý từng sheet
    for sheet_name in sheet_names_with_hyphen:
        print(f"\nĐang xử lý sheet: {sheet_name}")
        
        stt_list = []
        example_list = []
        topic_list = []
        
        # Đọc dữ liệu từ sheet
        data = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
        
        # Kiểm tra xem các cột cần thiết có tồn tại không
        required_cols = ["STT", "Ví dụ", "Tên chủ đề"]
        if not all(col in data.columns for col in required_cols):
            print(f"  Sheet '{sheet_name}' thiếu các cột cần thiết. Bỏ qua...")
            continue
        
        # Duyệt qua từng hàng trong DataFrame
        for index, row in data.iterrows():
            # Kiểm tra xem có ô dữ liệu nào bị trống không
            if pd.isna(row["Ví dụ"]):
                continue
            stt_list.append(row["STT"])
            example_list.append(row["Ví dụ"])
            topic_list.append(row["Tên chủ đề"])
        
        print(f"  Tìm thấy {len(example_list)} ví dụ cần chuyển thành audio")
        
        # Tạo thư mục output cho sheet này
        output_dir = os.path.join(output_base_dir, sheet_name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Tạo file MP3 cho từng ví dụ
        for i, text in enumerate(example_list):
            try:
                options = {
                    'headers': {
                        'Accept': 'application/octet-stream',
                        'Content-Type': 'text/plain',
                        'x-api-key': apikey,
                    },
                    'data': text.encode('utf8')
                }
                
                # Gọi API và lưu file
                response = requests.post(url, **options)
                
                if response.status_code == 200:
                    filename = f'{stt_list[i]}_{topic_list[i]}.mp3'
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"  ✓ Đã tạo: {filename}")
                else:
                    print(f"  ✗ Lỗi tạo file cho STT {stt_list[i]}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"  ✗ Lỗi xử lý STT {stt_list[i]}: {str(e)}")
    
    print("\n=== Hoàn thành ===")

if __name__ == "__main__":
    generate_korean_tts()