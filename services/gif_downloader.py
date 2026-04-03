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
  {"word": "主要","meaning": "chủ yếu, chính","example": "他的主要工作是帮助经理准备会议。" },
  {"word": "得分","meaning": "ghi điểm, số điểm","example": "在这次比赛中，我们队的得分最高。" },
  {"word": "体育","meaning": "thể dục, thể thao","example": "我不仅喜欢体育，也对音乐感兴趣。" },
  {"word": "运动员","meaning": "vận động viên","example": "他是一名优秀的篮球运动员。" },
  {"word": "奥运会","meaning": "Thế vận hội Olympic","example": "奥运会每四年举行一次。" },
  {"word": "刘长春","meaning": "Lưu Trường Xuân (tên riêng)","example": "刘长春是中国第一位参加奥运会的运动员。" },
  {"word": "数学","meaning": "Toán học","example": "这道数学题太难了，我还没做出来。" },
  {"word": "认真","meaning": "nghiêm túc, chăm chỉ","example": "他做作业总是非常认真，很少出错。" },
  {"word": "笔记","meaning": "ghi chép, vở ghi","example": "老师讲的内容，我都记在笔记里了。" },
  {"word": "历史","meaning": "lịch sử","example": "读历史书可以让我们了解过去的事情。" },
  {"word": "难","meaning": "khó","example": "学好外语虽然很难，但是很有用。" },
  {"word": "外语","meaning": "ngoại ngữ","example": "他除了英语以外，还会说一点儿日语。" },
  {"word": "句","meaning": "câu (lượng từ)","example": "请你把课文里的第一句话读一遍。" },
  {"word": "年级","meaning": "năm học, khối lớp","example": "我弟弟现在已经是小学三年级的学生了。" },
  {"word": "后年","meaning": "năm sau nữa","example": "他打算明年结婚，后年回国。" },
  {"word": "努力","meaning": "nỗ lực, cố gắng","example": "只有努力学习，才能考上好的大学。" },
  {"word": "开会","meaning": "họp, mở cuộc họp","example": "经理正在开会，请您在外面等一会儿。" },
  {"word": "后天","meaning": "ngày mốt (ngày kia)","example": "明天我有事，我们后天再去爬山吧。" },
  {"word": "室","meaning": "phòng (hậu tố)","example": "我们的会议室在三楼，请跟我来。" },
  {"word": "看来","meaning": "xem ra, có vẻ như","example": "天阴了，看来一会儿就要下雨了。" },
  {"word": "只能","meaning": "chỉ có thể","example": "电梯坏了，我们只能走楼梯上去了。" },
  {"word": "休假","meaning": "nghỉ phép, nghỉ lễ","example": "我打算下个月请几天假去南方旅游。" },
  {"word": "怕","meaning": "sợ, lo lắng","example": "我最怕在很多人面前说话。" },
  {"word": "邮箱","meaning": "hòm thư (vật lý hoặc email)","example": "记得经常检查你的电子邮箱。" },
  {"word": "老张","meaning": "Ông Trương (cách gọi thân mật)","example": "老张是我们的邻居，他为人很热情。" },
  {"word": "或","meaning": "hoặc","example": "周末我喜欢在家里看书或听音乐。" },
  {"word": "开花","meaning": "nở hoa","example": "春天到了，公园里的花都开花了。" },
  {"word": "工作日","meaning": "ngày làm việc","example": "银行在工作日八点半开始上班。" },
  {"word": "地方","meaning": "địa điểm, chỗ","example": "这个地方的环境非常安静，适合学习。" },
  {"word": "刮","meaning": "thổi (gió)","example": "外面刮风了，你出门多穿点儿衣服。" },
  {"word": "风","meaning": "gió","example": "今天的风很大，雨伞都没法用。" },
  {"word": "雨衣","meaning": "áo mưa","example": "骑自行车的时候穿雨衣比打伞方便。" },
  {"word": "冬天","meaning": "mùa đông","example": "北方的冬天非常冷，经常下雪。" },
  {"word": "常常","meaning": "thường xuyên","example": "我常常去图书馆借书。" },
  {"word": "关注","meaning": "quan tâm, theo dõi","example": "我们要多关注天气变化，预防感冒。" },
  {"word": "四季","meaning": "bốn mùa","example": "这个城市的四季都不太一样。" },
  {"word": "春天","meaning": "mùa xuân","example": "春天是爬山的好季节。" },
  {"word": "夏天","meaning": "mùa hè","example": "夏天的时候，大家都喜欢去海边玩。" },
  {"word": "秋天","meaning": "mùa thu","example": "秋天的天气很舒服，一点儿也不热。" },
  {"word": "变成","meaning": "trở thành, biến thành","example": "几年不见，他已经变成了一个大人。" },
  {"word": "请客","meaning": "mời khách, đãi tiệc","example": "今天是我生日，我请客大家去吃烤鸭。" },
  {"word": "南方","meaning": "miền Nam","example": "南方人比北方人更喜欢吃米饭。" },
  {"word": "北方","meaning": "miền Bắc","example": "冬天的时候，北方家里都有暖气。" },
  {"word": "做法","meaning": "cách làm","example": "这个菜的做法很简单，你可以试一下。" },
  {"word": "的话","meaning": "nếu (đứng sau một vế câu)","example": "如果明天下大雨的话，我们就别去了。" },
  {"word": "酒","meaning": "rượu","example": "为了身体健康，你应该少喝点儿酒。" },
  {"word": "客人","meaning": "khách","example": "今天家里要来客人，我去买些水果。" },
  {"word": "晚会","meaning": "buổi tiệc tối, dạ hội","example": "元旦晚会上有好多精彩的节目。" },
  {"word": "画家","meaning": "họa sĩ","example": "他从小就想成为一名有名的画家。" },
  {"word": "聊天儿","meaning": "nói chuyện phiếm","example": "老人们喜欢在树下坐着聊天儿。" }
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