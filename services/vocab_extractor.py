"""
vocab_extractor.py
------------------
Đọc file Excel, cho phép chọn sheet → bài → chủ đề (nếu có),
rồi lọc ra danh sách từ vựng theo đúng logic của AppScript gốc.

Yêu cầu: pip install openpyxl
"""

import re
import sys
from openpyxl import load_workbook


# ---------------------------------------------------------------------------
# Helpers (dịch 1:1 từ normalizeString_ và normalizeSttBai_ trong .gs)
# ---------------------------------------------------------------------------

def normalize_string(value) -> str:
    """Lowercase, trim, collapse mọi loại khoảng trắng (kể cả non-breaking space)."""
    if value is None:
        return ""
    # \s bao gồm space, tab, newline; \u00a0 là non-breaking space
    return re.sub(r"[\s\u00a0]+", " ", str(value)).strip().lower()


def normalize_stt_bai(value) -> str:
    """Chuyển số bài về dạng chuỗi nguyên, bỏ đuôi '.0' nếu có."""
    if value is None or str(value).strip() == "":
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


# ---------------------------------------------------------------------------
# Bước 1 – Quét sheet để xây dựng map: bài → {start_row, end_row, topics}
# (dịch từ populateBaiComboboxData)
# ---------------------------------------------------------------------------

SPECIAL_TOPICS = {"no hsk topic", "tất cả chủ đề", "all topics"}


def build_lesson_map(ws) -> dict:
    """
    Trả về dict:
      {
        "1": {"start_row": 3, "end_row": 10, "topics": ["1 - Ẩm thực", ...]},
        "2": {...},
        ...
      }
    start_row / end_row là chỉ số dòng Excel (1-based).
    """
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {}

    header = [normalize_string(h) for h in rows[0]]

    try:
        topic_col   = header.index("tên chủ đề")
        lesson_col  = header.index("stt bài")
    except ValueError as e:
        raise ValueError(f"Không tìm thấy cột bắt buộc: {e}") from e

    lesson_map = {}
    current_lesson = None
    prev_lesson = None

    for row_idx in range(1, len(rows)):          # row_idx: 0-based trong list
        excel_row = row_idx + 1                   # Excel row number (1-based, bỏ header)

        lesson_raw = rows[row_idx][lesson_col]
        topic_raw  = rows[row_idx][topic_col]

        # --- Xác định số bài ---
        try:
            lesson_float = float(lesson_raw) if lesson_raw not in (None, "") else None
            if (
                lesson_float is not None
                and lesson_float == int(lesson_float)
                and lesson_float >= 1
            ):
                current_lesson = int(lesson_float)
                if current_lesson != prev_lesson:
                    # Đóng bài trước
                    if prev_lesson is not None:
                        lesson_map[str(prev_lesson)]["end_row"] = row_idx  # row_idx là Excel row của dòng hiện tại (0-based + 1 = excel-1-based nhưng chưa +1 header... xem giải thích bên dưới)
                    # Mở bài mới
                    if str(current_lesson) not in lesson_map:
                        lesson_map[str(current_lesson)] = {
                            "start_row": excel_row + 1,  # dòng dữ liệu đầu tiên (bỏ dòng header số bài)
                            "end_row": None,
                            "topics": [],
                        }
                    prev_lesson = current_lesson
        except (ValueError, TypeError):
            pass

        # --- Thu thập chủ đề ---
        if current_lesson is not None and topic_raw and str(topic_raw).strip():
            full_topic = f"{current_lesson} - {str(topic_raw).strip()}"
            key = str(current_lesson)
            if full_topic not in lesson_map[key]["topics"]:
                lesson_map[key]["topics"].append(full_topic)

    # Đóng bài cuối cùng
    if current_lesson is not None:
        lesson_map[str(current_lesson)]["end_row"] = len(rows)  # Excel row cuối (1-based)

    # Bài không có chủ đề → gán "No HSK topic" (giống AppScript)
    for key, data in lesson_map.items():
        if not data["topics"]:
            data["topics"].append(f"{key} - No HSK topic")

    return lesson_map


# ---------------------------------------------------------------------------
# Bước 2 – Lọc từ vựng theo bài + chủ đề
# (dịch từ processSelections)
# ---------------------------------------------------------------------------

def extract_vocabulary(ws, lesson_map: dict, selected_bai: str, selected_chu_de: str) -> list[str]:
    """
    Trả về danh sách từ vựng (list[str]) theo bài và chủ đề đã chọn.

    selected_bai     : chuỗi số bài, vd "19"
    selected_chu_de  : chuỗi đầy đủ từ dropdown, vd "19 - Ẩm thực"
                       hoặc "19 - No HSK topic" nếu không có chủ đề
    """
    bai_key = normalize_stt_bai(selected_bai)

    if bai_key not in lesson_map:
        raise ValueError(f"Không tìm thấy bài '{selected_bai}' trong sheet.")

    lesson_data = lesson_map[bai_key]
    start_row   = lesson_data["start_row"]
    end_row     = lesson_data["end_row"]

    if not start_row or not end_row:
        raise ValueError(f"Bài '{bai_key}' thiếu thông tin start_row / end_row.")

    # Normalize chủ đề được chọn: bỏ phần "số - " ở đầu
    parts = selected_chu_de.split(" - ", 1)
    topic_normalized = normalize_string(parts[1] if len(parts) > 1 else selected_chu_de)
    is_special = topic_normalized in SPECIAL_TOPICS

    # Tìm cột header
    rows = list(ws.iter_rows(values_only=True))
    header = [normalize_string(h) for h in rows[0]]

    try:
        topic_col  = header.index("tên chủ đề")
        vocab_col  = header.index(normalize_string("Từ vựng"))
    except ValueError as e:
        raise ValueError(f"Không tìm thấy cột bắt buộc: {e}") from e

    vocabulary = []

    # start_row / end_row là Excel row (1-based) → array index = excel_row - 1
    for excel_row in range(start_row, end_row + 1):
        arr_idx = excel_row - 1
        if arr_idx < 0 or arr_idx >= len(rows):
            continue

        row = rows[arr_idx]

        sheet_topic_normalized = normalize_string(row[topic_col])

        if is_special or sheet_topic_normalized == topic_normalized:
            vocab_val = row[vocab_col]
            if vocab_val and str(vocab_val).strip():
                vocabulary.append(str(vocab_val).strip())

    return vocabulary


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def pick(options: list, prompt: str) -> str:
    """Hiển thị danh sách và trả về giá trị người dùng chọn."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            choice = int(input("Nhập số thứ tự: ").strip())
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except (ValueError, KeyboardInterrupt):
            pass
        print("  Lựa chọn không hợp lệ, thử lại.")


def main():
    # 1. Nhận đường dẫn file Excel
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("Nhập đường dẫn file Excel (.xlsx): ").strip().strip('"')

    print(f"\nĐang mở file: {file_path}")
    wb = load_workbook(file_path, read_only=True, data_only=True)

    # 2. Chọn sheet
    sheet_names = wb.sheetnames
    selected_sheet = pick(sheet_names, "Chọn sheet:")
    ws = wb[selected_sheet]
    print(f"→ Đang xử lý sheet: {selected_sheet}")

    # 3. Xây dựng map bài
    lesson_map = build_lesson_map(ws)
    if not lesson_map:
        print("Không tìm thấy dữ liệu bài nào trong sheet này.")
        return

    # 4. Chọn bài
    bai_list = sorted(lesson_map.keys(), key=lambda x: int(x))
    selected_bai = pick([f"Bài {b}" for b in bai_list], "Chọn bài:")
    bai_key = selected_bai.replace("Bài ", "")

    # 5. Chọn chủ đề
    topics = lesson_map[bai_key]["topics"]
    unique_topics = list(dict.fromkeys(topics))  # giữ thứ tự, loại trùng

    if len(unique_topics) == 1:
        # Chỉ có 1 chủ đề (thường là "No HSK topic") → tự động chọn
        selected_topic = unique_topics[0]
        print(f"\n→ Chủ đề duy nhất, tự động chọn: {selected_topic}")
    else:
        selected_topic = pick(unique_topics, "Chọn chủ đề:")

    # 6. Lọc từ vựng
    vocab_list = extract_vocabulary(ws, lesson_map, bai_key, selected_topic)

    # 7. In kết quả
    print(f"\n{'='*50}")
    print(f"Sheet : {selected_sheet}")
    print(f"Bài   : {bai_key}")
    print(f"Chủ đề: {selected_topic}")
    print(f"Số từ : {len(vocab_list)}")
    print(f"{'='*50}")
    for i, word in enumerate(vocab_list, 1):
        print(f"  {i:3}. {word}")
    print(f"{'='*50}")

    wb.close()
    return vocab_list


if __name__ == "__main__":
    main()
