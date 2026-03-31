import json
import os
import sys
import hashlib

# Thêm đường dẫn để import được image_gen_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.image_gen_service import ImageGenerationService

def generate_and_save_image(image_service, description, output_dir):
    """
    Generate image using AI and save it to output_dir. 
    Returns the absolute path to the saved image.
    Uses MD5 hash of description for filename to cache and avoid re-generation.
    """
    if not description:
        return None
        
    # Tạo tên file hash từ description để làm cache (Tránh gọi lại API nếu trùng mô tả)
    filename = hashlib.md5(description.encode('utf-8')).hexdigest() + ".png"
    filepath = os.path.join(output_dir, filename)
    
    # Nếu ảnh đã tồn tại, dùng lại luôn
    if os.path.exists(filepath):
        print(f"   [Cache] Đã có sẵn ảnh cho: {description[:50]}...")
        return filepath
        
    print(f"   [API] Đang gọi AI vẽ ảnh cho: {description[:50]}...")
    image_bytes = image_service.generate_image_legacy(prompt=description)
    
    if image_bytes:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath
    return None

def process_json_node(node, image_service, output_dir):
    """
    Đệ quy duyệt qua toàn bộ cấu trúc JSON. Nếu thấy key 'image_description', 
    gọi API sinh ảnh và thêm key 'local_image_path' chứa đường dẫn nội bộ.
    """
    if isinstance(node, dict):
        if "image_description" in node and isinstance(node["image_description"], str):
            desc = node["image_description"].strip()
            if desc:
                local_path = generate_and_save_image(image_service, desc, output_dir)
                if local_path:
                    node["local_image_path"] = local_path
                    
        # Tiếp tục duyệt sâu vào các value là dict/list
        for key, value in node.items():
            process_json_node(value, image_service, output_dir)
            
    elif isinstance(node, list):
        for item in node:
            process_json_node(item, image_service, output_dir)

def prepare_images_for_json(json_path, output_json_path=None):
    if not os.path.exists(json_path):
        print(f"Lỗi: Không tìm thấy file {json_path}")
        return
        
    if not output_json_path:
        output_json_path = json_path # Ghi đè file gốc nếu không chỉ định
        
    # Tạo thư mục chứa ảnh: hsk_ppt/images/generated/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "images", "generated")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n--- ĐANG TIỀN XỬ LÝ ẢNH CHO {os.path.basename(json_path)} ---")
    
    # Khởi tạo ImageGenerationService
    try:
        img_service = ImageGenerationService()
    except Exception as e:
        print(f"Lỗi khởi tạo ImageGenerationService: {e}")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Duyệt đệ quy để sinh ảnh
    process_json_node(data, img_service, output_dir)
    
    # Lưu JSON mới (cùng tên hoặc tên mới)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Đã hoàn tất tải ảnh và lưu JSON cập nhật tại: {output_json_path}")

if __name__ == "__main__":
    # Test chạy nội bộ (Thay đổi file json nếu cần)
    bk_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HSK2_BK_test_output.json")
    gr_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HSK2_Grammar_test_output.json")
    
    prepare_images_for_json(bk_json)
    prepare_images_for_json(gr_json)
