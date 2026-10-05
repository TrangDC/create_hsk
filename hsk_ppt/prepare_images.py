import json
import os
import sys
import hashlib

# Thêm đường dẫn để import được image_gen_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.image_gen_service import ImageGenerationService


HSK4_CARTOON_STYLE = (
    "2D cartoon illustration, clean educational animation style, simplified shapes, "
    "friendly expressive characters, soft colors, consistent hand-drawn look, "
    "not photorealistic, not a photograph, not 3D render."
    " No text, no letters, no Chinese characters, no numbers, no symbols, "
    "no labels, no subtitles, no speech bubbles, no logos, no watermark."
)

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
    image_bytes = image_service.generate_image(prompt=description, aspect_ratio="1:1")
    
    if image_bytes:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath
    return None


def generate_and_save_image_with_reference(
    image_service, description, reference_path, output_dir
):
    """Generate a scene while keeping the visual identity from a reference image."""
    if not description:
        return None

    cache_key = f"{reference_path or ''}\n{description}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".png"
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        print(f"   [Cache] Đã có ảnh theo reference: {description[:50]}...")
        return filepath

    print(f"   [API] Đang vẽ ảnh theo reference: {description[:50]}...")
    image_bytes, _usage = image_service.generate_image_with_image_ref(
        prompt=description,
        image_path=reference_path,
        aspect_ratio="1:1",
    )
    if image_bytes:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath
    return None


def _estimate_lines(text, font_size, width_cm):
    width_chars = max(1, int(width_cm / (font_size * 0.026)))
    return max(
        1,
        sum(max(1, (len(line) + width_chars - 1) // width_chars)
            for line in str(text or "").split("\n")),
    )


def _estimate_sentence_height(sentences, width_cm):
    total = 0.0
    for sentence in sentences:
        total += _estimate_lines(sentence.get("hz", ""), 42, width_cm) * 1.45
        total += _estimate_lines(sentence.get("pinyin", ""), 28, width_cm) * 0.95
        total += _estimate_lines(sentence.get("vi", ""), 28, width_cm) * 0.95
        total += 0.25
    return total


def _build_hsk4_sentence_groups(sentences):
    """Mirror the HSK4 renderer's 1/2-sentence slide grouping."""
    groups = []
    current = []
    for sentence in sentences:
        candidate = current + [sentence]
        if current and _estimate_sentence_height(candidate, 48.04) > 7.92:
            groups.append(current)
            current = [sentence]
        else:
            current = candidate
    if current:
        groups.append(current)
    return groups


def _prepare_hsk4_images(data, image_service, output_dir):
    """Create one visual reference and one consistent image per rendered slide chunk."""
    for unit_index, unit in enumerate(data.get("units", []), start=1):
        unit_description = unit.get("image_description", "")
        reference_description = unit.get("visual_reference_description") or unit_description
        reference_prompt = (
            "Create a clean visual identity reference for the same characters and setting "
            "used in a Chinese HSK4 lesson. Show the main people clearly and consistently. "
            f"{HSK4_CARTOON_STYLE} "
            f"Reference details: {reference_description}"
        )
        reference_path = generate_and_save_image(
            image_service, reference_prompt, output_dir
        )
        if reference_path:
            unit["visual_reference_path"] = reference_path

        if unit_description:
            full_prompt = (
                "Use the attached visual reference to keep exactly the same characters, "
                "faces, hairstyles, age, clothing style and illustration style. "
                "Create one clean text-free illustration for this lesson scene. "
                f"{HSK4_CARTOON_STYLE} "
                f"Scene: {unit_description}"
            )
            full_path = generate_and_save_image_with_reference(
                image_service, full_prompt, reference_path, output_dir
            ) if reference_path else generate_and_save_image(
                image_service, full_prompt, output_dir
            )
            if full_path:
                unit["local_image_path"] = full_path

        sentences = unit.get("sentences", [])
        groups = _build_hsk4_sentence_groups(sentences)
        image_groups = []
        sentence_offset = 0
        for group_index, group in enumerate(groups, start=1):
            descriptions = [
                sentence.get("image_description", "")
                for sentence in group
                if sentence.get("image_description")
            ]
            if not descriptions:
                sentence_offset += len(group)
                continue

            chunk_prompt = (
                "Use the attached visual reference and keep the exact same characters, "
                "faces, hairstyles, age, clothing style and visual style. "
                "Create one coherent text-free illustration representing this slide's "
                "consecutive moment(s). Do not create a collage or split panels. "
                f"{HSK4_CARTOON_STYLE} "
                "Scene description: " + " Then: ".join(descriptions)
            )
            chunk_path = generate_and_save_image_with_reference(
                image_service, chunk_prompt, reference_path, output_dir
            ) if reference_path else generate_and_save_image(
                image_service, chunk_prompt, output_dir
            )

            sentence_ids = []
            for sentence in group:
                sentence_ids.append(sentence.get("id", f"sentence_{sentence_offset + 1}"))
                if chunk_path:
                    sentence["image_group_local_path"] = chunk_path
                    sentence["local_image_path"] = chunk_path
                sentence_offset += 1
            image_groups.append({
                "group_id": f"unit_{unit_index:02d}_chunk_{group_index:02d}",
                "sentence_ids": sentence_ids,
                "local_image_path": chunk_path,
            })
        unit["image_groups"] = image_groups

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
        
    # Tạo thư mục chứa ảnh: resources/images/ppt/generated/
    base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "resources", "images", "ppt", "generated")
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
        
    # HSK4 dùng reference theo unit và ảnh theo đúng nhóm slide câu.
    if isinstance(data, dict) and "units" in data and "vocabulary_source" in data:
        _prepare_hsk4_images(data, img_service, output_dir)
    else:
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
