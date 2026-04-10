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
  {
    "word": "丢",
    "meaning": "mất, quăng, ném",
    "example": "我不小心把护照丢了，心里急极了。"
  },
  {
    "word": "号码",
    "meaning": "số, số điện thoại",
    "example": "请问你的电话号码是多少？我想联系你。"
  },
  {
    "word": "好像",
    "meaning": "hình như, dường như",
    "example": "天阴了，好像马上就要下大雨了。"
  },
  {
    "word": "尝",
    "meaning": "nếm",
    "example": "这是我第一次做中国菜，你快来尝尝味道怎么样。"
  },
  {
    "word": "咱们",
    "meaning": "chúng ta (bao gồm cả người nghe)",
    "example": "既然大家都到齐了，咱们就出发吧。"
  },
  {
    "word": "挺",
    "meaning": "rất, khá",
    "example": "这家书店的环境挺安静的，适合看书。"
  },
  {
    "word": "卫生间",
    "meaning": "nhà vệ sinh",
    "example": "请问，这层楼的卫生间在哪里？"
  },
  {
    "word": "纸",
    "meaning": "giấy",
    "example": "请给我一张纸，我要把老师说的话记下来。"
  },
  {
    "word": "主意",
    "meaning": "ý kiến, chủ ý",
    "example": "这是一个好主意，咱们就按你说的办吧。"
  },
  {
    "word": "总之",
    "meaning": "tóm lại",
    "example": "总之，只有努力学习，才能取得好成绩。"
  },
  {
    "word": "沙发",
    "meaning": "ghế sô pha",
    "example": "下班回到家，坐在沙发上听音乐最舒服了。"
  },
  {
    "word": "合适",
    "meaning": "phù hợp, thích hợp",
    "example": "这件衣服的大小很合适，我非常喜欢。"
  },
  {
    "word": "毛",
    "meaning": "lông, hào (đơn vị tiền)",
    "example": "在那家超市，一斤苹果只要三块五毛钱。"
  },
  {
    "word": "体育馆",
    "meaning": "nhà thi đấu thể thao",
    "example": "学校的体育馆在那座大楼的后面。"
  },
  {
    "word": "羽毛球",
    "meaning": "cầu lông",
    "example": "除了足球，他最喜欢的体育运动是羽毛球。"
  },
  {
    "word": "低",
    "meaning": "thấp",
    "example": "由于感冒了，他说话的声音非常低。"
  },
  {
    "word": "差不多",
    "meaning": "xấp xỉ, gần như nhau",
    "example": "这两双鞋的质量差不多，但是价格不同。"
  },
  {
    "word": "开心",
    "meaning": "vui vẻ",
    "example": "听到朋友要来北京看我，我开心极了。"
  },
  {
    "word": "方法",
    "meaning": "phương pháp",
    "example": "我们需要找到一个更好的方法来解决这个难题。"
  },
  {
    "word": "校园",
    "meaning": "khuôn viên trường",
    "example": "春天的校园到处都是绿色的树和美丽的花。"
  },
  {
    "word": "网球",
    "meaning": "quần vợt (tennis)",
    "example": "他网球打得很好，经常参加学校的比赛。"
  },
  {
    "word": "联系",
    "meaning": "liên hệ",
    "example": "回国以后，记得经常跟我联系啊。"
  },
  {
    "word": "紧张",
    "meaning": "căng thẳng, hồi hộp",
    "example": "第一次在这么多人面前说话，他感到很紧张。"
  },
  {
    "word": "受到",
    "meaning": "nhận được (tác động, tình cảm)",
    "example": "这位画家受到了很多读者的喜爱。"
  },
  {
    "word": "得到",
    "meaning": "đạt được, có được",
    "example": "经过努力，他终于得到了这个工作的机会。"
  },
  {
    "word": "遍",
    "meaning": "lần (lượt - từ đầu đến cuối)",
    "example": "这个电影太有意思了，我已经看过三遍了。"
  },
  {
    "word": "页",
    "meaning": "trang (sách)",
    "example": "请大家打开书，翻到第六十二页。"
  },
  {
    "word": "对话",
    "meaning": "đối thoại",
    "example": "请两人一组，练习课文里的对话。"
  },
  {
    "word": "地点",
    "meaning": "địa điểm",
    "example": "晚会的地点定在学校附近的那个大饭馆。"
  },
  {
    "word": "街",
    "meaning": "phố, đường phố",
    "example": "周末街上到处都是出来旅游的客人。"
  },
  {
    "word": "变",
    "meaning": "thay đổi, biến đổi",
    "example": "几年没见，这个城市的变化非常大。"
  },
  {
    "word": "凉快",
    "meaning": "mát mẻ",
    "example": "下过雨以后，天气比昨天凉快多了。"
  },
  {
    "word": "叶子",
    "meaning": "lá cây",
    "example": "秋天到了，树上的叶子都变黄了。"
  },
  {
    "word": "不同",
    "meaning": "khác nhau",
    "example": "每个人对这个问题的看法都是不同的。"
  },
  {
    "word": "加",
    "meaning": "thêm vào, cộng",
    "example": "这杯咖啡有点儿苦，我想加点儿糖。"
  },
  {
    "word": "做客",
    "meaning": "làm khách, đến chơi nhà",
    "example": "明天我想请你去我家做客，欢迎吗？"
  },
  {
    "word": "来自",
    "meaning": "đến từ",
    "example": "我们班的学生来自世界不同的国家。"
  },
  {
    "word": "感到",
    "meaning": "cảm thấy",
    "example": "听到这个好消息，大家都感到非常高兴。"
  },
  {
    "word": "最好",
    "meaning": "tốt nhất, nên",
    "example": "感冒了最好多喝点儿热开水，多休息。"
  },
  {
    "word": "节",
    "meaning": "tiết (lượng từ môn học), lễ hội",
    "example": "今天上午我一共有四节课。"
  },
  {
    "word": "表演",
    "meaning": "biểu diễn",
    "example": "晚会上的节目表演得精彩极了。"
  },
  {
    "word": "网站",
    "meaning": "trang web",
    "example": "你可以上网查查，那个网站上有你需要的信息。"
  },
  {
    "word": "平时",
    "meaning": "bình thường, lúc bình thường",
    "example": "他平时很努力，所以考试成绩总是很好。"
  },
  {
    "word": "可是",
    "meaning": "nhưng",
    "example": "我想去爬山，可是今天的天气不太好。"
  },
  {
    "word": "养",
    "meaning": "nuôi, trồng",
    "example": "我奶奶在家里养了很多漂亮的花。"
  },
  {
    "word": "脏",
    "meaning": "bẩn",
    "example": "你的衣服弄脏了，快去换一件吧。"
  },
  {
    "word": "好像",
    "meaning": "giống như, dường như",
    "example": "他长得好像他的爸爸。"
  },
  {
    "word": "竹子",
    "meaning": "tre, trúc",
    "example": "大熊猫最喜欢吃的食物就是竹子。"
  },
  {
    "word": "身边",
    "meaning": "bên cạnh",
    "example": "虽然父母不在身边，但我会照顾好自己。"
  },
  {
    "word": "到处",
    "meaning": "khắp nơi",
    "example": "在北方，冬天到处都能看到白色的雪。"
  },
  {
    "word": "继续",
    "meaning": "tiếp tục",
    "example": "休息了十分钟以后，咱们继续练习吧。"
  },
  {
    "word": "有关",
    "meaning": "có liên quan đến",
    "example": "我想借几本有关中国历史的电子书。"
  },
  {
    "word": "比如",
    "meaning": "ví dụ như",
    "example": "我喜欢很多体育运动，比如足球和网球。"
  },
  {
    "word": "方向",
    "meaning": "phương hướng",
    "example": "由于没有带地图，他走错了方向。"
  },
  {
    "word": "大概",
    "meaning": "khoảng, có lẽ",
    "example": "从这里到火车站，打车大概需要二十分钟。"
  },
  {
    "word": "收",
    "meaning": "nhận, thu dọn",
    "example": "你要去超市吗？帮我收一下外面的衣服吧。"
  },
  {
    "word": "起",
    "meaning": "vụ, kiện (lượng từ), bắt đầu",
    "example": "从明天起，我们要开始准备运动会了。"
  },
  {
    "word": "矿泉水",
    "meaning": "nước khoáng",
    "example": "服务员，请给我拿一瓶矿泉水。"
  },
  {
    "word": "出发",
    "meaning": "xuất phát",
    "example": "为了不迟到，咱们明天早上六点就出发。"
  },
  {
    "word": "发生",
    "meaning": "xảy ra",
    "example": "马路上发生了一起交通事故，车很多。"
  },
  {
    "word": "刚",
    "meaning": "vừa, vừa mới",
    "example": "我刚收到他的邮件，他说后天过来。"
  },
  {
    "word": "只要",
    "meaning": "chỉ cần",
    "example": "只要你坚持努力，目标就一定能实现。"
  },
  {
    "word": "学期",
    "meaning": "học kỳ",
    "example": "这个学期快要结束了，同学们都非常忙。"
  },
  {
    "word": "毕业",
    "meaning": "tốt nghiệp",
    "example": "高中毕业以后，他打算去英国留学。"
  },
  {
    "word": "出生",
    "meaning": "sinh ra",
    "example": "他出生在一个非常美丽的小城市。"
  },
  {
    "word": "坚持",
    "meaning": "kiên trì",
    "example": "他每天都坚持跑步，所以身体很健康。"
  },
  {
    "word": "目标",
    "meaning": "mục tiêu",
    "example": "我的目标是今年能通过HSK三级考试。"
  },
  {
    "word": "发展",
    "meaning": "phát triển",
    "example": "随着社会的发展，人们的生活越来越方便。"
  }
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