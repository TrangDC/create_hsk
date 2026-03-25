import sys
import os
import json
import re

# Đảm bảo có thể import được call_vertexai từ thư mục cha
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from call_vertexai import VertexClient, get_credentials

def extract_hsk_json_from_pdf(pdf_path: str, prompt_text: str, output_json_path: str = None) -> dict:
    """
    Hàm gọi Vertex AI để phân tích PDF dựa trên prompt và trả về đối tượng JSON.
    Nếu output_json_path được truyền vào, kết quả sẽ được lưu ra file.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
        
    if not prompt_text or not prompt_text.strip():
        raise ValueError("Prompt không được để trống.")

    print(f"Đang phân tích file PDF: {os.path.basename(pdf_path)}...")
    
    try:
        # Lấy thông tin xác thực
        creds, project_id = get_credentials()
        client = VertexClient(project_id, creds, "gemini-2.5-pro")
        
        # Gửi dữ liệu lên AI
        print("Đang gửi dữ liệu lên Vertex AI (Vui lòng đợi, có thể mất vài chục giây)...")
        resp = client.send_data_to_AI(prompt_text, file_paths=[pdf_path])
        
        # Tiền xử lý chuỗi trả về (Giống logic trong WorkerThread của powperpoint_generate_hsk 1.py)
        cleaned = re.sub(r'```json|```', '', resp).strip()
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        
        if not match:
            print("--- PHẢN HỒI GỐC TỪ AI ---")
            print(resp)
            raise ValueError("Không tìm thấy JSON hợp lệ trong phản hồi AI.")
            
        json_str = match.group(0)
        json_str = json_str.replace('\r', '')
        json_str = re.sub(r',\s*}', '}', json_str) # Xóa dấu phẩy thừa ở cuối object
        json_str = re.sub(r',\s*]', ']', json_str) # Xóa dấu phẩy thừa ở cuối array
        
        # Parse chuỗi thành Dictionary
        data = json.loads(json_str)
        
        # (Tùy chọn) Lưu ra file nếu được yêu cầu
        if output_json_path:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Đã lưu kết quả JSON vào: {output_json_path}")
            
        return data

    except json.JSONDecodeError as e:
        print("--- LỖI PARSE JSON ---")
        print("Chuỗi JSON lỗi:")
        print(json_str)
        raise ValueError(f"AI trả về JSON không đúng định dạng: {e}")
    except Exception as e:
        print(f"Gặp lỗi trong quá trình xử lý: {e}")
        raise

if __name__ == "__main__":
    # Thay đổi đường dẫn tương ứng với môi trường của bạn để test
    PDF_FILE_PATH = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\input\8. 我爸爸也在医院工作 My father also works at a hospital.pdf"
    PROMPT_FILE_PATH = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\prompts\Prompt_Bai_Khoa.txt"
    OUTPUT_JSON_FILE = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\test_output_json.json"

    try:
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
            prompt = f.read()
            
        result_json = extract_hsk_json_from_pdf(
            pdf_path=PDF_FILE_PATH, 
            prompt_text=prompt, 
            output_json_path=OUTPUT_JSON_FILE
        )
        
        print("\n✅ THÀNH CÔNG! Đã lấy được JSON hợp lệ.")
        # In ra cấu trúc cơ bản để xác nhận
        print(f"Tiêu đề: {result_json.get('lesson_info', {}).get('title_vn')}")
        print(f"Số lượng sections: {len(result_json.get('sections', []))}")
        
    except Exception as e:
        print(f"\n❌ THẤT BẠI: {e}")