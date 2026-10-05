# 📚 HƯỚNG DẪN SỬ DỤNG ENGLISH FLASHCARD GENERATOR

## 🎯 Tổng quan
Công cụ **English Flashcard Generator** giúp tự động tạo ảnh minh họa flashcard tiếng Anh và file audio phát âm cho từ vựng, sử dụng AI (Vertex AI - Imagen 3) để sinh ảnh và các dịch vụ TTS để tạo audio.

---

## 📋 Yêu cầu chuẩn bị

### 1. File Excel đầu vào
File Excel cần có cấu trúc với các cột sau:

| Cột | Bắt buộc | Mô tả |
|-----|----------|-------|
| **Từ** | ✅ Có | Từ vựng tiếng Anh cần tạo flashcard |
| **Nghĩa** | ⚠️ Nên có | Nghĩa tiếng Việt của từ |
| **Câu ví dụ** | ⚠️ Nên có | Câu ví dụ sử dụng từ vựng |
| **Note** | ❌ Không | Cột ghi chú (dùng để đánh dấu từ bị lỗi cần chạy lại) |

**Ví dụ:**
```
| Từ        | Nghĩa              | Câu ví dụ                                    | Note |
|-----------|-------------------|----------------------------------------------|------|
| apple     | quả táo           | I eat an apple every day.                    |      |
| beautiful | đẹp               | She is a beautiful girl.                     |      |
| computer  | máy tính          | I use my computer for work.                  | lỗi  |
```

### 2. File Prompt
- Đường dẫn mặc định: `resources/prompts/image_eng_gen_flashcard.txt`
- File này chứa hướng dẫn cho AI về cách vẽ ảnh minh họa
- **Không nên chỉnh sửa** trừ khi bạn muốn thay đổi phong cách ảnh

### 3. Ảnh Template (Reference)
- Thư mục: `resources/images/image_eng_template/`
- Chứa các ảnh mẫu để AI tham khảo phong cách vẽ
- Tool sẽ **chọn ngẫu nhiên** 1 ảnh từ thư mục này làm reference cho mỗi từ
- Định dạng hỗ trợ: `.png`, `.jpg`, `.jpeg`, `.webp`

### 4. Cấu hình API
Đảm bảo file `.env` đã được cấu hình đầy đủ:
```env
PROJECT_ID=your-google-cloud-project-id
PRIVATE_KEY=your-service-account-private-key
CLIENT_EMAIL=your-service-account-email
# ... các biến khác
```

---

## 🚀 Hướng dẫn sử dụng

### Bước 1: Chọn File Excel
1. Click nút **"Chọn..."** để duyệt và chọn file Excel chứa từ vựng
2. Hoặc click **"Mở File Mẫu"** để xem cấu trúc file Excel mẫu

### Bước 2: Tải danh sách Sheet
1. Click nút **"🔄 Tải danh sách Sheet"** 
2. Dropdown sẽ hiển thị tất cả các sheet trong file Excel
3. Chọn sheet cần xử lý, hoặc chọn **"Tất cả các sheet"** để chạy toàn bộ

### Bước 3: Chọn File Prompt (Tùy chọn)
- Đường dẫn mặc định đã được điền sẵn
- Nếu muốn dùng prompt khác:
  - Click **"Chọn..."** để chọn file prompt mới
  - Click **"Mở File"** để xem/chỉnh sửa nội dung prompt

### Bước 4: Cấu hình tùy chọn

#### ✅ Chỉ chạy các từ bị lỗi
- Tick vào checkbox này nếu bạn chỉ muốn tạo lại ảnh cho các từ có dữ liệu trong cột **"Note"**
- Hữu ích khi cần chạy lại các từ bị lỗi mà không tốn thời gian cho các từ đã OK

#### 🔊 Chọn Model sinh audio
Tool hỗ trợ 3 model TTS:

| Model | Đặc điểm | Giọng đọc |
|-------|----------|-----------|
| **Narakeet** | Ổn định, nhanh | Nữ: Lisa, Nam: Jeff (cố định) |
| **Chirp3-HD** | Ổn định, nhanh, chất lượng tốt | Google TTS |
| **gemini-3.1-flash-tts-preview** | Tự nhiên nhất, ngữ điệu tốt | Gemini TTS |

**Khuyến nghị:** 
- Dùng **Narakeet** cho tốc độ nhanh
- Dùng **gemini-3.1-flash-tts-preview** cho chất lượng tốt nhất

### Bước 5: Bắt đầu tạo
1. Click nút **"🚀 Bắt đầu tạo ảnh English Flashcard"**
2. Theo dõi tiến trình trong khung **"📋 Nhật ký"**
3. Nếu muốn dừng giữa chừng, click nút **"🛑 Dừng"**

---

## 📂 Kết quả đầu ra

### Cấu trúc thư mục
```
output/
└── eng_flashcards/
    └── [Tên Sheet]/
        ├── apple.png              # Ảnh minh họa từ "apple"
        ├── beautiful.png          # Ảnh minh họa từ "beautiful"
        ├── computer.png           # Ảnh minh họa từ "computer"
        └── audio/
            ├── apple.mp3          # Audio phát âm từ "apple"
            ├── apple_example.mp3  # Audio câu ví dụ của "apple"
            ├── beautiful.mp3
            ├── beautiful_example.mp3
            ├── computer.mp3
            └── computer_example.mp3
```

### Nội dung file
- **Ảnh PNG**: Ảnh minh họa từ vựng theo phong cách flat illustration, tỷ lệ 3:2
- **Audio MP3**: 
  - `[từ].mp3`: Phát âm từ đơn
  - `[từ]_example.mp3`: Phát âm câu ví dụ

---

## 📊 Log và Tracking

### Log trong giao diện
Khung "📋 Nhật ký" hiển thị:
- ✅ Trạng thái tạo ảnh thành công
- ❌ Lỗi khi tạo ảnh/audio
- ⏭️ Các từ đã có ảnh (bỏ qua)
- 🔊 Trạng thái tạo audio
- 📊 Thống kê tokens sử dụng

### Log trên Google Drive
Sau khi xử lý xong mỗi sheet, tool tự động upload file log lên Google Drive với thông tin:
- Từ vựng đã xử lý
- Trạng thái (success/failed/skipped)
- Số tokens sử dụng
- Số lần thử (attempts)
- Thông báo lỗi (nếu có)

---

## ⚙️ Cơ chế hoạt động

### 1. Sinh ảnh minh họa
```
Đầu vào: Từ + Nghĩa + Câu ví dụ + Topic (tên sheet)
         ↓
AI Prompt: Kết hợp thông tin + Hướng dẫn vẽ từ file prompt
         ↓
Vertex AI Imagen 3: Sinh ảnh theo phong cách reference
         ↓
Đầu ra: File PNG (3:2 ratio)
```

**Đặc điểm ảnh:**
- ✅ Không có chữ trong ảnh
- ✅ Một cảnh duy nhất (không có grid/collage)
- ✅ Phong cách flat illustration
- ✅ Bảng màu hài hòa (Pink, Yellow, Blue, Green)

### 2. Sinh audio
```
Từ vựng → TTS Model → [từ].mp3
Câu ví dụ → TTS Model → [từ]_example.mp3
```

### 3. Xử lý lỗi và retry
- Nếu từ đã có ảnh → **Bỏ qua** (không tạo lại)
- Nếu API lỗi → **Ghi log** và tiếp tục từ tiếp theo
- Nếu tick "Chỉ chạy từ bị lỗi" → Chỉ xử lý từ có dữ liệu ở cột "Note"

---

## 💡 Tips và Lưu ý

### ✅ Nên làm
- Chuẩn bị đầy đủ cột "Nghĩa" và "Câu ví dụ" để AI vẽ ảnh chính xác hơn
- Đặt tên sheet theo chủ đề (ví dụ: "Animals", "Food", "Daily Activities")
- Thêm nhiều ảnh template đa dạng vào thư mục `resources/images/image_eng_template/`
- Kiểm tra file `.env` trước khi chạy

### ❌ Tránh làm
- Không để trống cột "Từ"
- Không đặt tên sheet quá dài hoặc có ký tự đặc biệt
- Không chạy quá nhiều từ cùng lúc (tránh rate limit API)
- Không xóa file prompt mặc định nếu chưa hiểu rõ cách hoạt động

### ⚡ Tối ưu hiệu suất
- Chạy từng sheet nhỏ (20-50 từ) thay vì chạy "Tất cả các sheet"
- Sử dụng chế độ "Chỉ chạy từ bị lỗi" khi cần chạy lại
- Delay 1 giây giữa các request để tránh rate limit

---

## 🐛 Xử lý lỗi thường gặp

### Lỗi: "Không tìm thấy file Excel"
**Nguyên nhân:** Đường dẫn file không đúng  
**Giải pháp:** Chọn lại file Excel bằng nút "Chọn..."

### Lỗi: "Thiếu cấu hình Google Cloud"
**Nguyên nhân:** File `.env` chưa được cấu hình  
**Giải pháp:** Kiểm tra và điền đầy đủ thông tin trong file `.env`

### Lỗi: "Không sinh được ảnh"
**Nguyên nhân:** 
- API Vertex AI lỗi
- Prompt không hợp lệ
- Từ vựng quá trừu tượng

**Giải pháp:**
- Kiểm tra log chi tiết trong khung "Nhật ký"
- Thử chạy lại với từ khác
- Kiểm tra quota API

### Lỗi: "Không sinh được audio"
**Nguyên nhân:** 
- TTS service không khởi tạo được
- API key không hợp lệ (với Narakeet)

**Giải pháp:**
- Thử đổi sang model TTS khác
- Kiểm tra cấu hình API trong code

### Ảnh không mở được sau khi tạo xong
**Nguyên nhân:** Thư mục output bị khóa hoặc không có quyền  
**Giải pháp:** Mở thủ công thư mục `output/eng_flashcards/[Tên Sheet]/`

---

## 📞 Hỗ trợ

Nếu gặp vấn đề không giải quyết được:
1. Kiểm tra log chi tiết trong khung "📋 Nhật ký"
2. Kiểm tra file log trên Google Drive
3. Liên hệ team phát triển với thông tin lỗi cụ thể

---

## 🔄 Cập nhật và Phát triển

### Phiên bản hiện tại
- ✅ Hỗ trợ sinh ảnh với Vertex AI Imagen 3
- ✅ Hỗ trợ 3 model TTS (Narakeet, Chirp3-HD, Gemini)
- ✅ Tự động upload log lên Drive
- ✅ Chế độ "Chỉ chạy từ bị lỗi"
- ✅ Xử lý đa sheet

### Tính năng sắp tới (có thể)
- ⏳ Hỗ trợ thêm model AI vẽ ảnh
- ⏳ Tùy chỉnh bảng màu trong giao diện
- ⏳ Batch processing với queue
- ⏳ Preview ảnh trước khi lưu

---

**Chúc bạn sử dụng tool hiệu quả! 🎉**
