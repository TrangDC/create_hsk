# services/gif_downloader.py
import requests
from bs4 import BeautifulSoup
import time
import random
import re
import os
import urllib.parse
from PIL import Image

# --- CẤU HÌNH TỪ CODE CỦA BẠN ---
MAX_RETRIES_PER_TEMPLATE = 4  
RETRY_DELAY = 10               
SEARCH_TEMPLATES = [
    "{}- 生字笔顺展示",           # Ưu tiên 1
    "{}生字笔顺展示",              # Ưu tiên 2
    "{}- 生字笔顺展示- 淘知"       # Ưu tiên 3
]

class StrokeGifManager:
    def __init__(self, gif_folder="output/flashcards/raw_gifs", png_folder="output/flashcards/pngs_static"):
        self.gif_folder = gif_folder
        self.png_folder = png_folder
        
        # Tạo folder nếu chưa có
        if not os.path.exists(self.gif_folder): os.makedirs(self.gif_folder)
        if not os.path.exists(self.png_folder): os.makedirs(self.png_folder)
        
        self.session = requests.Session()
        self.setup_session()

    def setup_session(self):
        """Thiết lập header giả lập trình duyệt"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.session.headers.update(headers)

    def get_real_url_from_baidu(self, baidu_link):
        """Lấy link thật từ link redirect của Baidu"""
        try:
            resp = self.session.get(baidu_link, allow_redirects=False, timeout=10)
            if resp.status_code == 302:
                return resp.headers.get('Location')
            return baidu_link 
        except Exception:
            return None

    def extract_static_png(self, gif_path, char):
        """Trích xuất frame cuối cùng của gif làm ảnh tĩnh (Phục vụ Flashcard mặt sau)"""
        try:
            png_path = os.path.join(self.png_folder, f"{char}.png")
            # Nếu đã có png thì trả về luôn
            if os.path.exists(png_path): return png_path

            with Image.open(gif_path) as im:
                im.seek(im.n_frames - 1) # Lấy frame cuối
                im.convert("RGBA").save(png_path)
            return png_path
        except Exception as e:
            print(f"    [!] Lỗi tạo PNG cho {char}: {e}")
            return None

    def _download_attempt(self, char, search_template):
        """
        Thử tải với 1 mẫu tìm kiếm cụ thể.
        Trả về: (Success: bool, Content: bytes hoặc None)
        """
        query_text = search_template.format(char)
        
        # Retry mạng cho template này
        for attempt in range(1, MAX_RETRIES_PER_TEMPLATE + 1):
            try:
                # --- BƯỚC 1: SEARCH BAIDU ---
                self.session.headers.update({'Referer': 'https://www.baidu.com/'})
                base_url = "https://www.baidu.com/s"
                params = {'wd': query_text, 'ie': 'utf-8', 'rn': 10}
                
                resp = self.session.get(base_url, params=params, timeout=10)
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')

                # --- BƯỚC 2: TÌM LINK TAOZHI ---
                results = soup.find_all('div', class_=re.compile(r'result'))
                found_taozhi_url = None

                for res in results:
                    h3 = res.find('h3')
                    if not h3: continue
                    a_tag = h3.find('a')
                    if not a_tag: continue
                    
                    baidu_link = a_tag.get('href')
                    real_url = self.get_real_url_from_baidu(baidu_link)
                    
                    if real_url and "taozhi.cn" in real_url:
                        # print(f"    [+] Tìm thấy link: {real_url}")
                        found_taozhi_url = real_url
                        break
                    time.sleep(0.1)

                if not found_taozhi_url:
                    # Nếu không thấy link Taozhi, coi như template này fail ở lần thử này
                    raise Exception("Không tìm thấy kết quả taozhi.cn trên Baidu")

                # --- BƯỚC 3: VÀO TAOZHI LẤY GIF ---
                time.sleep(random.uniform(1, 1.5))
                tz_resp = self.session.get(found_taozhi_url, timeout=10)
                
                # [QUAN TRỌNG 1] Fix lỗi font chữ (Encoding) để Python đọc được tiếng Trung
                tz_resp.encoding = tz_resp.apparent_encoding 
                tz_soup = BeautifulSoup(tz_resp.text, 'html.parser')

                # ================================================================
                # [QUAN TRỌNG 2] KIỂM TRA TITLE NGHIÊM NGẶT
                # ================================================================
                page_title = tz_soup.title.string.strip() if tz_soup.title else ""
                
                # Cấu trúc mong đợi: "雪 - 生字笔顺演示..." hoặc "雪 - 生字..."
                # Ta dùng dấu phân cách " - " (khoảng trắng + gạch ngang + khoảng trắng)
                separator = " - "
                
                if separator in page_title:
                    # Lấy phần chữ nằm trước dấu gạch ngang
                    extracted_char = page_title.split(separator)[0].strip()
                    
                    if extracted_char != char:
                        # Log lỗi để biết tại sao fail
                        # print(f"      [Mismatch] Title là '{extracted_char}', cần tìm '{char}'")
                        raise Exception(f"Sai trang đích! Web là chữ [{extracted_char}], đang tìm [{char}]")
                else:
                    # Fallback: Nếu title không có dấu " - ", kiểm tra xem có bắt đầu bằng char không
                    if not page_title.startswith(char):
                         raise Exception(f"Title '{page_title}' không đúng với chữ '{char}'")

                target_img_src = None
                sx_box = tz_soup.find('div', id='sxBox')
                if sx_box:
                    img = sx_box.find('img', class_='img_shuxie')
                    if img: target_img_src = img.get('src')
                
                # Fallback tìm gif
                if not target_img_src:
                    gifs = tz_soup.find_all('img', src=re.compile(r'\.gif$', re.IGNORECASE))
                    for g in gifs:
                        src = g.get('src')
                        if src and ('taozhi.cn' in src or 'Upload' in src):
                            target_img_src = src
                            break

                if not target_img_src:
                    raise Exception("Không tìm thấy URL GIF trong trang web")

                if not target_img_src.startswith('http'):
                    target_img_src = urllib.parse.urljoin("https://www.taozhi.cn", target_img_src)

                # --- BƯỚC 4: TẢI FILE ---
                # Quan trọng: Anti-hotlink referer
                img_headers = {
                    'User-Agent': self.session.headers['User-Agent'],
                    'Referer': found_taozhi_url 
                }
                
                img_resp = self.session.get(target_img_src, headers=img_headers, timeout=15, stream=True)
                
                content_type = img_resp.headers.get('Content-Type', '')
                if 'image' not in content_type and 'application/octet-stream' not in content_type:
                    raise Exception(f"Server trả về định dạng lạ ({content_type})")
                
                # Tải toàn bộ content vào biến
                content = b""
                for chunk in img_resp.iter_content(chunk_size=8192):
                    content += chunk
                
                return True, content

            except Exception as e:
                if attempt < MAX_RETRIES_PER_TEMPLATE:
                    # print(f"      -> Lỗi thử lại ({attempt}): {e}")
                    time.sleep(RETRY_DELAY)
                else:
                    # print(f"      -> Thất bại template này: {e}")
                    pass
        
        return False, None

    def download_char(self, char):
        """
        Hàm chính được gọi từ bên ngoài.
        Áp dụng chiến thuật Waterfall: Thử từng template một.
        """
        gif_path = os.path.join(self.gif_folder, f"{char}.gif")
        
        # 1. Check file tồn tại và hợp lệ
        if os.path.exists(gif_path):
            if os.path.getsize(gif_path) > 1000:
                print(f"    [-] Đã có file: {char}")
                return gif_path
            else:
                try: os.remove(gif_path)
                except: pass

        print(f"    [Processing] Đang xử lý chữ: '{char}'")

        # 2. Chạy vòng lặp Template (Chiến thuật)
        for idx, template in enumerate(SEARCH_TEMPLATES):
            # print(f"    ... Thử chiến thuật {idx+1}: {template.format(char)}")
            success, content = self._download_attempt(char, template)
            
            if success and content:
                # Lưu file
                with open(gif_path, 'wb') as f:
                    f.write(content)
                
                # Kiểm tra size lần cuối
                if os.path.getsize(gif_path) > 1000:
                    print(f"    [OK] Tải thành công: {char} (Chiến thuật {idx+1})")
                    # png_path = self.extract_static_png(gif_path, char)
                    return gif_path
                else:
                    print(f"    [!] File tải về quá nhẹ, xóa và thử tiếp.")
                    os.remove(gif_path)
            
            # Nếu thất bại template này, vòng lặp for sẽ tự nhảy sang template tiếp theo
            time.sleep(1)

        print(f"    [X] Thất bại toàn tập với chữ: '{char}'")
        return None
    
def main():

    # --- DỮ LIỆU INPUT ---
    input_vocab = [
  { "word": "可以", "meaning": "Có thể", "example": "我可以去吗？" },
  { "word": "再", "meaning": "Lại / Nữa", "example": "再见。" },
  { "word": "问题", "meaning": "Vấn đề / Câu hỏi", "example": "没问题。" },
  { "word": "卖", "meaning": "Bán", "example": "卖书。" },
  { "word": "打电话", "meaning": "Gọi điện thoại", "example": "我在打电话。" },
  { "word": "一下", "meaning": "Một lát / Thử xem", "example": "看一下。" },
  { "word": "服务员", "meaning": "Người phục vụ", "example": "服务员，点菜。" },
  { "word": "女士", "meaning": "Quý cô / Bà", "example": "女士们，先生们。" },
  { "word": "请", "meaning": "Mời / Xin", "example": "请进。" },
  { "word": "坐", "meaning": "Ngồi", "example": "请坐。" },
  { "word": "给", "meaning": "Đưa cho / Cho", "example": "给我那本书。" },
  { "word": "杯", "meaning": "Cốc / Ly (lượng từ)", "example": "一杯茶。" },
  { "word": "要", "meaning": "Muốn / Cần", "example": "我要咖啡。" },
  { "word": "早饭", "meaning": "Bữa sáng", "example": "吃早饭。" },
  { "word": "这个", "meaning": "Cái này", "example": "我要这个。" },
  { "word": "面包", "meaning": "Bánh mì", "example": "买面包。" },
  { "word": "鸡蛋", "meaning": "Trứng gà", "example": "吃鸡蛋。" },
  { "word": "先生", "meaning": "Ông / Ngài", "example": "王先生。" },
  { "word": "一半", "meaning": "Một nửa", "example": "给我一半。" },
  { "word": "茶", "meaning": "Trà", "example": "喝茶。" },
  { "word": "上", "meaning": "Trên / Lên", "example": "上车。" },
  { "word": "火车", "meaning": "Tàu hỏa", "example": "坐火车。" },
  { "word": "中午", "meaning": "Buổi trưa", "example": "中午好。" },
  { "word": "开", "meaning": "Mở / Lái (xe)", "example": "开门。" },
  { "word": "有些", "meaning": "Có một số / Có vài", "example": "有些人。" },
  { "word": "有的", "meaning": "Có cái / Có người", "example": "有的书很有趣。" },
  { "word": "了", "meaning": "Rồi (trợ từ)", "example": "太好了。" },
  { "word": "写", "meaning": "Viết", "example": "写汉字。" },
  { "word": "都", "meaning": "Đều", "example": "我们都去。" },
  { "word": "听见", "meaning": "Nghe thấy", "example": "我听见了。" },
  { "word": "不要", "meaning": "Đừng / Không muốn", "example": "不要说话。" },
  { "word": "说话", "meaning": "Nói chuyện", "example": "他在说话。" },
  { "word": "听", "meaning": "Nghe", "example": "听音乐。" },
  { "word": "哪些", "meaning": "Những cái nào", "example": "哪些书？" },
  { "word": "字", "meaning": "Chữ", "example": "写字。" },
  { "word": "汉语", "meaning": "Tiếng Trung", "example": "学汉语。" },
  { "word": "汉字", "meaning": "Chữ Hán", "example": "汉字很难。" },
  { "word": "明年", "meaning": "Năm sau", "example": "明年见。" },
  { "word": "上", "meaning": "Đi học / Lên (lớp)", "example": "上学。" },
  { "word": "中学", "meaning": "Trường trung học", "example": "他在中学。" },
  { "word": "小学", "meaning": "Trường tiểu học", "example": "去小学。" },
  { "word": "中学生", "meaning": "Học sinh trung học", "example": "我是中学生。" },
  { "word": "小学生", "meaning": "Học sinh tiểu học", "example": "他是小学生。" },
  { "word": "上学", "meaning": "Đi học", "example": "每天上学。" },
  { "word": "他们", "meaning": "Họ / Các anh ấy", "example": "他们来了。" },
  { "word": "她们", "meaning": "Họ / Các cô ấy", "example": "她们很漂亮。" },
  { "word": "它们", "meaning": "Chúng nó (vật/động vật)", "example": "它们是猫。" },
  { "word": "晚", "meaning": "Muộn / Tối", "example": "太晚了。" },
  { "word": "爱", "meaning": "Yêu", "example": "我爱你。" },
  { "word": "哪个", "meaning": "Cái nào", "example": "哪个好？" },
  { "word": "去年", "meaning": "Năm ngoái", "example": "去年我去过。" },
  { "word": "男朋友", "meaning": "Bạn trai", "example": "我的男朋友。" },
  { "word": "几", "meaning": "Mấy / Vài", "example": "几个人？" },
  { "word": "年", "meaning": "Năm", "example": "一年。" },
  { "word": "好玩儿", "meaning": "Vui / Thú vị", "example": "真好玩儿。" },
  { "word": "飞机", "meaning": "Máy bay", "example": "坐飞机。" },
  { "word": "要", "meaning": "Sắp / Phải", "example": "要下雨了。" },
  { "word": "小时", "meaning": "Tiếng / Giờ (đồng hồ)", "example": "两个小时。" },
  { "word": "家人", "meaning": "Người nhà", "example": "我的家人。" },
  { "word": "时间", "meaning": "Thời gian", "example": "没时间。" },
  { "word": "机场", "meaning": "Sân bay", "example": "去机场。" },
  { "word": "接", "meaning": "Đón / Nhận", "example": "接电话。" },
  { "word": "住", "meaning": "Sống / Ở", "example": "你住哪儿？" },
  { "word": "早", "meaning": "Sớm", "example": "很早。" },
  { "word": "那", "meaning": "Kia / Đó", "example": "那是什么？" }
]

    # Cấu hình thư mục output theo yêu cầu
    GIF_OUTPUT = "output/flashcards/raw_gifs"
    PNG_OUTPUT = "output/flashcards/pngs_static" # Mặc dù chỉ cần GIF, nhưng class thường tạo cả PNG
    
    print("="*60)
    print("🚀 BẮT ĐẦU TOOL DOWNLOAD GIF (TEST MODE)")
    print(f"📁 Thư mục lưu GIF: {GIF_OUTPUT}")
    print("="*60)

    try:
        downloader = StrokeGifManager(
            gif_folder=GIF_OUTPUT,
            png_folder=PNG_OUTPUT
        )
    except Exception as e:
        print(f"❌ Lỗi khởi tạo Downloader: {e}")
        return

    # Thống kê sơ bộ
    total_chars = 0
    unique_chars = set()
    for item in input_vocab:
        for char in item['word']:
            unique_chars.add(char)
            total_chars += 1
            
    print(f"📊 Tổng số từ: {len(input_vocab)}")
    print(f"🔣 Tổng số chữ cái (unique): {len(unique_chars)}")
    print("-" * 60)

    success_count = 0
    fail_count = 0
    
    # Bắt đầu vòng lặp
    for idx, item in enumerate(input_vocab):
        word = item['word']
        meaning = item['meaning']
        
        print(f"\n🔹 [{idx+1}/{len(input_vocab)}] Đang xử lý từ: {word} ({meaning})")
        
        for char in word:
            # Chỉ xử lý chữ Hán (UTF-8 range cơ bản)
            if not ('\u4e00' <= char <= '\u9fff'):
                print(f"    ⚠️ Bỏ qua '{char}': Không phải chữ Hán.")
                continue

            try:
                # Gọi hàm download
                # Lưu ý: Code của bạn đã có logic check file tồn tại bên trong download_char rồi
                gif_path = downloader.download_char(char)
                
                if gif_path and os.path.exists(gif_path):
                    # print(f"    ✅ '{char}': OK") # Comment bớt cho đỡ rối nếu muốn
                    success_count += 1
                else:
                    print(f"    ❌ '{char}': THẤT BẠI (Không tìm thấy hoặc lỗi)")
                    fail_count += 1
            
            except Exception as e:
                print(f"    ❌ '{char}': Lỗi ngoại lệ - {e}")
                fail_count += 1
            
            # Delay nhẹ giữa các chữ để tránh spam request quá gắt
            time.sleep(5) 
        
        # Delay giữa các từ
        time.sleep(6)

    print("\n" + "="*60)
    print("🎉 HOÀN TẤT QUÁ TRÌNH TEST")
    print(f"✅ Thành công (bao gồm file cũ): {success_count} chữ")
    print(f"❌ Thất bại: {fail_count} chữ")
    print("="*60)

if __name__ == "__main__":
    main()    