import os
from PIL import Image, ImageSequence

# --- CẤU HÌNH KÍCH THƯỚC (LANDSCAPE 1920x1080) ---
CANVAS_W, CANVAS_H = 1920, 1080

# 1. Khu vực ảnh AI (Phần trên)
# Dành khoảng 700px chiều cao cho ảnh minh họa
AI_AREA_H = 750 

# 2. Khu vực chữ viết (Phần dưới)
# Vị trí Y bắt đầu vẽ chữ (ngay bên dưới vùng ảnh AI)
GIF_START_Y = 750 
CHAR_SIZE = 280      # Kích thước ô chữ (Vuông 280x280)
CHAR_GAP = 40        # Khoảng cách giữa các chữ

def process_ai_image(img_path, target_w, target_h):
    """
    Xử lý ảnh AI để đặt vào vùng trên của khổ ngang.
    Chiến thuật: Resize theo chiều cao (Fit Height) rồi căn giữa.
    """
    try:
        # Tạo nền trắng mặc định cho vùng chứa ảnh
        container = Image.new("RGB", (target_w, target_h), "white")

        if not os.path.exists(img_path):
            return container

        img = Image.open(img_path)

        # 1. Xử lý màu (Giữ nguyên logic cũ)
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGBA", img.size, (255, 255, 255))
            img = Image.alpha_composite(background, img.convert("RGBA"))
        img = img.convert("RGB")

        # 2. Tính toán Resize (Fit theo chiều cao target_h)
        # Vì ảnh AI thường là 1:1 hoặc 3:2, ta ưu tiên giữ full chiều cao
        scale = target_h / img.height
        new_w = int(img.width * scale)
        new_h = int(img.height * scale) # Chính là target_h
        
        img_resized = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

        # 3. Paste căn giữa (Center)
        # Tính tọa độ X để ảnh nằm giữa khung 1920
        paste_x = (target_w - new_w) // 2
        paste_y = 0 
        
        container.paste(img_resized, (paste_x, paste_y))
        
        return container

    except Exception as e:
        print(f"❌ Lỗi xử lý ảnh AI: {e}")
        return Image.new("RGB", (target_w, target_h), (240, 240, 240))

def create_merged_gif(ai_image_path, list_char_gif_paths, output_path):
    # 1. Chuẩn bị Ảnh AI (Vùng trên) - Giữ nguyên RGB
    ai_img_processed = process_ai_image(ai_image_path, CANVAS_W, AI_AREA_H)

    # 2. Lọc GIF hợp lệ
    valid_gifs = []
    if list_char_gif_paths:
        for p in list_char_gif_paths:
            if p and os.path.exists(p):
                valid_gifs.append(p)

    # --- TRƯỜNG HỢP 1: KHÔNG CÓ GIF CHỮ (Ảnh tĩnh PNG) ---
    if not valid_gifs:
        try:
            frame = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
            frame.paste(ai_img_processed, (0, 0))
            base, _ = os.path.splitext(output_path)
            png_output_path = base + ".png"
            frame.save(png_output_path)
            return png_output_path
        except Exception as e:
            print(f"❌ Lỗi tạo ảnh tĩnh: {e}")
            return False

    # --- TRƯỜNG HỢP 2: CÓ GIF CHỮ (Tạo GIF động) ---
    try:
        char_assets = []
        total_frames_needed = 0
        for path in valid_gifs:
            img = Image.open(path)
            n_frames = getattr(img, 'n_frames', 1)
            char_assets.append({'img': img, 'n_frames': n_frames})
            total_frames_needed += n_frames

        PAUSE_FRAMES = 35
        total_loop_frames = total_frames_needed + PAUSE_FRAMES
        total_width_chars = (len(char_assets) * CHAR_SIZE) + ((len(char_assets) - 1) * CHAR_GAP)
        start_x = (CANVAS_W - total_width_chars) // 2

        # CHỈNH SỬA Ở ĐÂY: Lưu các frame ở dạng RGB gốc, chưa quantize
        rgb_frames = []
        
        for i in range(total_loop_frames):
            frame = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
            frame.paste(ai_img_processed, (0, 0))

            curr_x = start_x
            cumulative_f = 0

            for asset in char_assets:
                c_img = asset['img']
                n_f = asset['n_frames']
                
                if i < cumulative_f: fr_idx = 0 
                elif i < cumulative_f + n_f: fr_idx = i - cumulative_f
                else: fr_idx = n_f - 1

                c_img.seek(fr_idx)
                char_frame = c_img.copy().convert("RGBA").resize((CHAR_SIZE, CHAR_SIZE))
                frame.paste(char_frame, (curr_x, GIF_START_Y), mask=char_frame)
                
                curr_x += CHAR_SIZE + CHAR_GAP
                cumulative_f += n_f
            
            rgb_frames.append(frame)

        # --- TỐI ƯU BẢNG MÀU (FIX LỖI ĐỔI MÀU) ---
        if rgb_frames:
            # Bước 1: Lấy frame cuối cùng (thường là frame đầy đủ màu nhất) làm mẫu để tạo bảng màu
            # Nếu dùng MEDIANCUT cho frame cuối, các màu của ảnh AI sẽ được giữ cố định
            sample_frame = rgb_frames[-1].quantize(colors=256, method=Image.MEDIANCUT)
            
            final_frames = []
            for f in rgb_frames:
                # Ép tất cả các frame khác dùng chung bảng màu của sample_frame
                final_frames.append(f.quantize(palette=sample_frame))

            durations = [60] * total_loop_frames
            final_frames[0].save(
                output_path,
                save_all=True,
                append_images=final_frames[1:],
                duration=durations,
                loop=0,
                disposal=2,
                optimize=True
            )
            return output_path
            
    except Exception as e:
        print(f"❌ Lỗi tạo GIF động: {e}")
        return False

    return False