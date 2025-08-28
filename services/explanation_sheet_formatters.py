import re
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

# --- CÁC HÀM TIỆN ÍCH CHO AUTO-SIZING ---
def calculate_cell_dimensions(text: str, font_size=11):
    """
    Tính toán chiều rộng và chiều cao cần thiết cho ô dựa trên nội dung text.
    
    Args:
        text (str): Nội dung text cần tính toán
        font_size (int): Kích thước font (mặc định 11)
    
    Returns:
        tuple: (width, height) - chiều rộng và số dòng cần thiết
    """
    if not text:
        return 15, 1
    
    # Xử lý text từ CellRichText hoặc string thông thường
    if hasattr(text, '__iter__') and not isinstance(text, str):
        # Nếu là CellRichText, chuyển về string để tính toán
        plain_text = ""
        for part in text:
            if isinstance(part, TextBlock):
                plain_text += part.text
            else:
                plain_text += str(part)
        text = plain_text
    
    lines = str(text).split('\n')
    max_line_length = max(len(line) for line in lines) if lines else 0
    num_lines = len(lines)
    
    # Tính chiều rộng: khoảng 1.2 đơn vị Excel cho mỗi ký tự (tùy chỉnh theo font)
    # Đối với tiếng Việt và tiếng Trung, cần thêm không gian
    char_width = 1.3
    estimated_width = max_line_length * char_width
    
    # Đặt giới hạn tối thiểu và tối đa
    min_width = 20
    max_width = 100
    final_width = max(min_width, min(estimated_width, max_width))
    
    # Tính số dòng thực tế cần thiết (không tăng quá nhiều)
    actual_lines = num_lines
    if estimated_width > max_width:
        # Chỉ tăng nhẹ số dòng khi text quá dài
        wrap_factor = estimated_width / max_width
        additional_lines = max(0, int((wrap_factor - 1) * 0.5))  # Giảm hệ số wrap
        actual_lines = num_lines + additional_lines
    
    return final_width, actual_lines

def auto_size_cell(worksheet, cell, content):
    """
    Tự động điều chỉnh kích thước ô theo nội dung.
    
    Args:
        worksheet: Worksheet object của openpyxl
        cell: Cell object cần điều chỉnh
        content: Nội dung đã được ghi vào cell
    """
    try:
        # Tính toán kích thước cần thiết
        width, num_lines = calculate_cell_dimensions(content)
        
        # Lấy chỉ số cột
        col_letter = get_column_letter(cell.column)
        
        # Điều chỉnh chiều rộng cột (chỉ tăng, không giảm)
        current_width = worksheet.column_dimensions[col_letter].width or 15
        if width > current_width:
            worksheet.column_dimensions[col_letter].width = width
        
        # Điều chỉnh chiều cao hàng
        row_height = max(15, num_lines * 15)  # 15 points per line
        current_height = worksheet.row_dimensions[cell.row].height or 15
        if row_height > current_height:
            worksheet.row_dimensions[cell.row].height = row_height
            
    except Exception as e:
        print(f"Cảnh báo: Không thể auto-size cell {cell.coordinate}: {e}")

# --- CÁC HÀM XÂY DỰNG RICH TEXT CHUYÊN BIỆT ---
def format_simple_context_rich_text(explanation_json: dict) -> CellRichText:
    """Xây dựng CellRichText cho các dạng câu hỏi có ngữ cảnh đơn giản."""
    bold_font = InlineFont(b=True)
    italic_font = InlineFont(i=True)
    rich_text = CellRichText()

    # 1. Phân tích
    rich_text.append(explanation_json.get('analysis_paragraph', '') + '\n\n')

    # 2. Phụ đề
    context = explanation_json.get('context_block', {})
    rich_text.append(TextBlock(bold_font, "Phụ đề:\n"))
    rich_text.append(f"{context.get('chinese_text', '')}\n")
    rich_text.append(f"{context.get('pinyin', '')}\n\n")

    # 3. Tạm dịch
    translation = explanation_json.get('translation_block', {})
    rich_text.append(TextBlock(bold_font, "Tạm dịch: "))
    rich_text.append(TextBlock(italic_font, translation.get('vietnamese_text', '')))
    
    return rich_text

def format_dialogue_rich_text(explanation_json: dict) -> CellRichText:
    """Xây dựng CellRichText cho các dạng câu hỏi có hội thoại."""
    bold_font = InlineFont(b=True)
    italic_font = InlineFont(i=True)
    rich_text = CellRichText()

    # 1. Phân tích
    rich_text.append(explanation_json.get('analysis_paragraph', '') + '\n\n')
    
    # 2. Phụ đề (hội thoại)
    context = explanation_json.get('context_block', {})
    dialogue = context.get('dialogue', [])
    rich_text.append(TextBlock(bold_font, "Phụ đề:\n"))
    for turn in dialogue:
        speaker = turn.get('speaker', '')
        speaker_prefix = f"**{speaker}：**" if speaker else ""
        rich_text.append(f"{speaker_prefix}{turn.get('chinese_text', '')}\n")
        rich_text.append(f"{' ' * len(speaker_prefix)}{turn.get('pinyin', '')}\n")
    rich_text.append('\n')

    # 3. Tạm dịch
    translation = explanation_json.get('translation_block', {})
    rich_text.append(TextBlock(bold_font, "Tạm dịch:\n"))
    rich_text.append(TextBlock(italic_font, translation.get('vietnamese_text', '')))

    return rich_text

def format_word_fill_rich_text(explanation_json: dict) -> CellRichText:
    """Xây dựng CellRichText cho dạng Điền từ, có xử lý highlight chữ Hán."""
    bold_font = InlineFont(b=True)
    italic_font = InlineFont(i=True)
    blue_font = InlineFont(color="0000FF") # Màu xanh dương cho dễ nhìn
    rich_text = CellRichText()
    
    # 1. Phân tích
    rich_text.append(explanation_json.get('analysis_paragraph', '') + '\n\n')

    # 2. Phụ đề (với highlight)
    context = explanation_json.get('context_block', {})
    script_lines = context.get('script_lines', [])
    rich_text.append(TextBlock(bold_font, "Phụ đề:\n"))
    
    chinese_pattern = r'(__[^_]+__)' # Pattern để tìm __text__
    for line in script_lines:
        speaker = line.get('speaker', '')
        prefix = f"**{speaker}：**" if speaker else ""
        chinese_text = line.get('chinese_text', '')
        pinyin = line.get('pinyin', '')
        
        rich_text.append(prefix)
        # Tách chuỗi để highlight
        parts = re.split(chinese_pattern, chinese_text)
        for i, part in enumerate(parts):
            if i % 2 == 1: # Phần nằm giữa cặp __
                rich_text.append(TextBlock(blue_font, part[2:-2])) # Bỏ đi 2 dấu __
            else:
                rich_text.append(part)
        rich_text.append('\n')
        rich_text.append(f"{' ' * len(prefix)}{pinyin}\n")
    rich_text.append('\n')

    # 3. Tạm dịch
    translation = explanation_json.get('translation_block', {})
    vietnamese_text = translation.get('vietnamese_text', '')
    if vietnamese_text.startswith("**Nam:**") or vietnamese_text.startswith("**Nữ:**"):
        rich_text.append(TextBlock(bold_font, "Tạm dịch:\n"))
    else:
        rich_text.append(TextBlock(bold_font, "Tạm dịch: "))
    rich_text.append(TextBlock(italic_font, vietnamese_text))
    
    return rich_text

def apply_ds_vocab_rich_text_formatting(text: str) -> CellRichText:
    """
    Áp dụng định dạng rich text cho dạng DS vocab với các quy tắc:
    - Bôi đậm: "Phụ đề:", "Tạm dịch:"
    - In nghiêng: Text sau "Tạm dịch:"
    """
    # Define fonts
    bold_font = InlineFont(b=True)
    italic_font = InlineFont(i=True)
    
    rich_text = CellRichText()
    
    # Define keywords để bôi đậm
    bold_keywords = ["Phụ đề:", "Tạm dịch:"]
    
    # Tạo pattern regex
    escaped_keywords = [re.escape(kw) for kw in bold_keywords]
    pattern = '(' + '|'.join(escaped_keywords) + ')'
    
    # Split text theo keywords, giữ lại các keywords
    parts = re.split(pattern, text)
    
    in_tam_dich_section = False
    
    for part in parts:
        if not part:  # Skip empty parts
            continue
            
        if part in bold_keywords:
            rich_text.append(TextBlock(bold_font, part))
            if part == "Tạm dịch:":
                in_tam_dich_section = True
        else:
            # Normal text
            if in_tam_dich_section:
                rich_text.append(TextBlock(italic_font, part))
            else:
                rich_text.append(part)
    
    return rich_text

# apply rich text formatting cho sheet "TN PA đúng (img) (HL) (HSK1)"
def build_plain_text_with_markers(explanation_json: dict) -> str:
    text_parts = []

    # 1) analysis...
    analysis = explanation_json.get('analysis_paragraph', '')
    if analysis:
        text_parts.append(analysis)
        text_parts.append('\n\n')

    # 2) phụ đề...
    context = explanation_json.get('context_block', {}) or {}
    dialogue = context.get('dialogue', []) or []
    if dialogue:
        text_parts.append('**Phụ đề**:\n')
        for i, turn in enumerate(dialogue):
            speaker = turn.get('speaker', '') or ''
            chinese = turn.get('chinese_text', '') or ''
            pinyin  = turn.get('pinyin', '') or ''
            if speaker:
                text_parts.append(f'**{speaker}**：')
            if chinese:
                text_parts.append(chinese)
            text_parts.append('\n')
            if pinyin:
                pinyin_indent = ' ' * len(f"{speaker}：") if speaker else ''
                text_parts.append(f"{pinyin_indent}{pinyin}")
            if i < len(dialogue) - 1:
                text_parts.append('\n')
        text_parts.append('\n\n')

    # 3) Tạm dịch (sửa tại đây)
    translation = explanation_json.get('translation_block', {}) or {}
    vi_turns = translation.get('vietnamese_dialogue', []) or []
    if vi_turns:
        text_parts.append('**Tạm dịch**:\n')
        for i, tvi in enumerate(vi_turns):
            sp = tvi.get('speaker_vi', '') or ''
            dv = tvi.get('dialogue_vi', '') or ''
            if sp:
                # speaker Việt: đậm + nghiêng
                text_parts.append(f'<<bi>>{sp}<</bi>>: ')
            if dv:
                # NHÉT \n VÀO BÊN TRONG marker italic (trừ dòng cuối)
                if i < len(vi_turns) - 1:
                    text_parts.append(f'<<i>>{dv}\n<</i>>')
                else:
                    text_parts.append(f'<<i>>{dv}<</i>>')

    return ''.join(text_parts)

# Áp dụng regex để build CellRichText từ plain text với markers
def apply_regex_formatting(plain_text: str) -> CellRichText:
    """
    Parse các marker và build CellRichText.
    Thứ tự ưu tiên: <<bi>>...<</bi>> -> <<i>>...<</i>> -> **...**
    """
    bold_font        = InlineFont(b=True)
    italic_font      = InlineFont(i=True)
    bold_italic_font = InlineFont(b=True, i=True)

    rich = CellRichText()

    # Combined token regex (non-greedy, cho phép xuống dòng)
    token_re = re.compile(r'(?s)(<<bi>>.*?<<\/bi>>|<<i>>.*?<<\/i>>|\*\*[^*]+\*\*)')

    pos = 0
    for m in token_re.finditer(plain_text):
        # 1) text thường trước token
        if m.start() > pos:
            rich.append(plain_text[pos:m.start()])

        tok = m.group(0)

        if tok.startswith('<<bi>>'):
            content = tok[len('<<bi>>'):-len('<</bi>>')]
            rich.append(TextBlock(bold_italic_font, content))
        elif tok.startswith('<<i>>'):
            content = tok[len('<<i>>'):-len('<</i>>')]
            rich.append(TextBlock(italic_font, content))
        else:
            # **...**
            content = tok[2:-2]
            rich.append(TextBlock(bold_font, content))

        pos = m.end()

    # 2) phần còn lại sau token cuối
    if pos < len(plain_text):
        rich.append(plain_text[pos:])

    return rich

# render rich text cho sheet "TN PA đúng (img) (HL) (HSK1)"
def format_shared_image_comprehension_rich_text(explanation_json: dict) -> CellRichText:
    """
    Xây dựng CellRichText cho sheet "TN PA đúng (img) (HL) (HSK1)".
    Sử dụng phương pháp tạo plain text với markers rồi áp dụng regex formatting.
    """
    
    # 1. Tạo plain text với markers
    plain_text_with_markers = build_plain_text_with_markers(explanation_json)
    
    # 2. Áp dụng định dạng bằng regex
    rich_text = apply_regex_formatting(plain_text_with_markers)
    
    return rich_text

# apply rich text formatting cho sheet "TN PA đúng (HSK1)"
def apply_rich_text_formatting(text: str) -> CellRichText:
    bold_font = InlineFont(b=True)
    italic_font = InlineFont(i=True)
    bold_italic_font = InlineFont(b=True, i=True)

    rich_text = CellRichText()

    bold_keywords = ["Tạm dịch:", "Phụ đề:"]
    bold_italic_keywords = ["Câu hỏi:"]
    all_keywords = bold_keywords + bold_italic_keywords

    # Tách theo heading (giữ lại heading)
    escaped_keywords = [re.escape(kw) for kw in sorted(all_keywords, key=len, reverse=True)]
    pattern = '(' + '|'.join(escaped_keywords) + ')'
    parts = re.split(pattern, text)
    
    # DEBUG: In ra các parts để kiểm tra
    print("DEBUG - Parts:")
    for i, part in enumerate(parts):
        print(f"Part {i}: '{part}'")
    print("---")

    # NEW: bắt token **...** và <<i>>...<<\/i>> (non-greedy, đa dòng)
    bold_token_re = re.compile(r'(?s)(<<bi>>.*?<<\/bi>>|<<i>>.*?<<\/i>>|\*\*[^*]+\*\*)')

    def emit_with_bold_tokens(chunk: str, italic_ctx: bool):
        pos = 0
        for m in bold_token_re.finditer(chunk):
            if m.start() > pos:
                normal = chunk[pos:m.start()]
                if italic_ctx:
                    rich_text.append(TextBlock(italic_font, normal))
                else:
                    rich_text.append(normal)
            
            # Xử lý các token
            token = m.group(0)
            if token.startswith('<<i>>') and token.endswith('<</i>>'):
                # Token italic đơn thuần
                content = token[5:-6]  # Bỏ <<i>> và <</i>>
                rich_text.append(TextBlock(italic_font, content))
            elif token.startswith('<<bi>>') and token.endswith('<</bi>>'):
                # Token bold italic
                content = token[6:-7]  # Bỏ <<bi>> và <</bi>>
                rich_text.append(TextBlock(bold_italic_font, content))
            elif token.startswith('**') and token.endswith('**'):
                # Token bold (ví dụ **问：**)
                content = token[2:-2]
                rich_text.append(TextBlock(bold_font, content))
            
            pos = m.end()
        
        if pos < len(chunk):
            tail = chunk[pos:]
            if italic_ctx:
                rich_text.append(TextBlock(italic_font, tail))
            else:
                rich_text.append(tail)

    in_tam_dich_section = False

    for part in parts:
        if not part:
            continue
        if part in bold_keywords:
            rich_text.append(TextBlock(bold_font, part))
            in_tam_dich_section = (part == "Tạm dịch:")
        elif part in bold_italic_keywords:
            rich_text.append(TextBlock(bold_italic_font, part))
            # KHÔNG reset in_tam_dich_section - giữ nguyên để phần sau "Câu hỏi:" vẫn italic
        else:
            # Không phải heading -> xử lý **...** và <<i>>...<<\/i>> tokens
            emit_with_bold_tokens(part, italic_ctx=in_tam_dich_section)

    return rich_text

# render lời giải cho sheet "TN PA đúng (HSK1)"
def render_reading_comp_explanation(cell, explanation_json: dict):
    """
    Ghi lời giải cho dạng Đọc hiểu (TN PA đúng) vào ô Excel với rich text formatting.
    """
    # Initialize cell value as a string
    cell_value = ""
    
    # 1. Đoạn phân tích
    analysis = explanation_json.get('analysis_paragraph', '')
    cell_value += analysis + '\n\n'
    
    # 2. Danh sách lựa chọn
    options = explanation_json.get('options_list', [])
    for opt in options:
        letter = opt.get('letter', '')
        chinese = opt.get('chinese_text', '')
        translation = opt.get('translation', '')
        pinyin = opt.get('pinyin', '')
        cell_value += f"{letter}. {chinese} <<i>>({translation})<</i>>\n"
        cell_value += f"{pinyin}\n"
    cell_value += '\n'

    # 3. Khối Phụ đề
    context = explanation_json.get('context_block', {})
    script_lines = context.get('script_lines', [])
    cell_value += "Phụ đề:\n"
    for line in script_lines:
        label = line.get('line_label', '')
        prefix = f"**{label}**：" if label else ""
        cell_value += f"{prefix}{line.get('chinese_text', '')}\n"
        cell_value += f"{' ' * len(prefix)}{line.get('pinyin', '')}\n"
    cell_value += '\n'

    # 4. Khối Tạm dịch
    translation = explanation_json.get('translation_block', {})
    cell_value += "Tạm dịch:\n"
    cell_value += f"{translation.get('context_vietnamese', '')}\n"
    cell_value += "Câu hỏi: "
    cell_value += f"{translation.get('query_vietnamese', '')}"

    print(cell_value)

    # Apply rich text formatting
    cell.value = apply_rich_text_formatting(cell_value)
    cell.alignment = Alignment(wrap_text=True, vertical='top')

    # Auto-size the cell
    auto_size_cell(cell.parent, cell, cell_value)

_CJK_SPEAKER_SET = {"男", "女", "问", "答"}
_CJK_LABEL_RE    = re.compile(r'^[\u3400-\u4DBF\u4E00-\u9FFF]{1,3}$')  # 1–3 ký tự CJK
_VI_SPEAKER_RE   = re.compile(r'^\*{0,2}(Nam|Nữ)\*{0,2}\s*:\s*')

def is_dialogue_style_word_fill(expl: dict) -> bool:
    ctx = expl.get("context_block", {}) or {}
    sl  = ctx.get("script_lines", []) or []
    if sl:
        speakers = [(line.get("speaker") or "").strip() for line in sl]
        if any((s in _CJK_SPEAKER_SET) or _CJK_LABEL_RE.match(s) for s in speakers if s):
            return True

    vt = ((expl.get("translation_block") or {}).get("vietnamese_text") or "")
    if any(_VI_SPEAKER_RE.match(line.strip()) for line in vt.splitlines()):
        return True

    return False

def normalize_word_fill_to_dialogue_schema(expl: dict) -> dict:
    sl = (expl.get("context_block") or {}).get("script_lines", []) or []
    dialogue = []
    for line in sl:
        dialogue.append({
            "speaker":      (line.get("speaker") or "").strip(),
            "chinese_text": (line.get("chinese_text") or ""),
            "pinyin":       (line.get("pinyin") or "")
        })

    vt = ((expl.get("translation_block") or {}).get("vietnamese_text") or "").strip()
    vi_dialogue = []
    if vt:
        for raw in [s.strip() for s in vt.splitlines() if s.strip()]:
            m = re.match(r'^\*{0,2}(Nam|Nữ)\*{0,2}\s*:\s*(.+)$', raw)
            if m:
                vi_dialogue.append({"speaker_vi": m.group(1), "dialogue_vi": m.group(2)})
        if not vi_dialogue:
            vi_dialogue.append({"speaker_vi": "", "dialogue_vi": vt})

    return {
        "analysis_paragraph": expl.get("analysis_paragraph", ""),
        "context_block": {"dialogue": dialogue},
        "translation_block": {"vietnamese_dialogue": vi_dialogue}
    }

def apply_chinese_highlight_over_markers(plain_text: str) -> CellRichText:
    green_font = InlineFont(color="FF00AA00")  # ARGB 8 ký tự
    rich = CellRichText()
    token_re = re.compile(r'__([\u3400-\u4DBF\u4E00-\u9FFF]+?)__')

    pos = 0
    for m in token_re.finditer(plain_text):
        if m.start() > pos:
            for run in apply_regex_formatting(plain_text[pos:m.start()]):
                rich.append(run)
        rich.append(TextBlock(green_font, m.group(1)))
        pos = m.end()
    if pos < len(plain_text):
        for run in apply_regex_formatting(plain_text[pos:]):
            rich.append(run)
    return rich

def apply_rich_text_formatting_with_chinese(text: str) -> CellRichText:
    green_font = InlineFont(color="FF00AA00")  # ARGB
    rich = CellRichText()
    token_re = re.compile(r'__([\u3400-\u4DBF\u4E00-\u9FFF]+?)__')

    pos = 0
    for m in token_re.finditer(text):
        if m.start() > pos:
            for run in apply_rich_text_formatting(text[pos:m.start()]):  # hàm bạn đã patch để hiểu **…**
                rich.append(run)
        rich.append(TextBlock(green_font, m.group(1)))
        pos = m.end()

    if pos < len(text):
        for run in apply_rich_text_formatting(text[pos:]):
            rich.append(run)
    return rich

def render_word_fill_explanation(cell, explanation_json: dict):
    # Nếu là thoại -> dùng pipeline giống sheet ảnh (và vẫn highlight __漢字__)
    if is_dialogue_style_word_fill(explanation_json):
        normalized = normalize_word_fill_to_dialogue_schema(explanation_json)
        plain      = build_plain_text_with_markers(normalized)     # tạo **Phụ đề**/**Tạm dịch**, <<bi>> label
        rich       = apply_chinese_highlight_over_markers(plain)   # parse markers + overlay __漢字__
        cell.value = rich
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        auto_size_cell(cell.parent, cell, plain_text_from_rich_text(rich))
        return

    # Không phải thoại -> luồng cũ (nhưng dùng ASCII ":" và thụt pinyin cố định)
    cell_value = ""

    analysis = explanation_json.get('analysis_paragraph', '')
    cell_value += analysis + '\n\n'

    context = explanation_json.get('context_block', {})
    script_lines = context.get('script_lines', [])
    cell_value += "Phụ đề:\n"
    for line in script_lines:
        speaker = line.get('speaker', '')
        prefix  = f"**{speaker}:** " if speaker else ""   # dùng ":" ASCII
        chinese = line.get('chinese_text', '')
        pinyin  = line.get('pinyin', '')
        cell_value += f"{prefix}{chinese}\n"
        cell_value += f"  {pinyin}\n"                     # thụt cố định 2 space
    cell_value += '\n'

    tr = explanation_json.get('translation_block', {})
    vt = tr.get('vietnamese_text', '') or ''
    if vt.startswith("**Nam:**") or vt.startswith("**Nữ:**"):
        cell_value += "Tạm dịch:\n"
    else:
        cell_value += "Tạm dịch: "
    cell_value += vt

    cell.value = apply_rich_text_formatting_with_chinese(cell_value)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    auto_size_cell(cell.parent, cell, cell_value)

# Render lời giải cho sheet ĐS (img) HSK1 và ĐS Ko phụ đề (img) HSK1
def render_ds_vocab_explanation(worksheet, sheet_name):
    """
    Định dạng lại nội dung có sẵn trong cột I của sheet (bỏ qua hàng tiêu đề).
    Bôi đậm: "Phụ đề:", "Tạm dịch:"
    In nghiêng: phần sau "Tạm dịch:"
    """
    print(f"   - Đang định dạng sheet: {sheet_name}")
    
    try:
        # Lấy số hàng có dữ liệu trong cột I
        max_row = worksheet.max_row
        
        # Duyệt từ hàng 2 (bỏ qua tiêu đề) đến hàng cuối
        for row_num in range(2, max_row + 1):
            cell = worksheet[f'I{row_num}']
            
            # Chỉ xử lý nếu ô có nội dung
            if cell.value:
                # Lấy nội dung text gốc
                original_text = str(cell.value)
                
                # Áp dụng định dạng rich text
                formatted_content = apply_ds_vocab_rich_text_formatting(original_text)
                cell.value = formatted_content
                cell.alignment = Alignment(wrap_text=True, vertical='top')
                
                # Auto-size the cell
                auto_size_cell(worksheet, cell, original_text)
                
        print(f"   - ✅ Đã định dạng xong sheet: {sheet_name}")
        
    except Exception as e:
        print(f"   - ❌ Lỗi khi định dạng sheet {sheet_name}: {e}")

def plain_text_from_rich_text(rt: CellRichText) -> str:
    """Lấy chuỗi văn bản thô từ đối tượng CellRichText để tính toán kích thước."""
    return "".join(str(part.text if hasattr(part, 'text') else part) for part in rt)

def render_simple_context_explanation(cell, explanation_json: dict):
    """Render lời giải dạng ngữ cảnh đơn giản."""
    formatted_content = format_simple_context_rich_text(explanation_json)
    cell.value = formatted_content
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    auto_size_cell(cell.parent, cell, plain_text_from_rich_text(formatted_content))

def render_shared_image_comprehension_explanation(cell, explanation_json: dict):
    """Render lời giải cho sheet 'TN PA đúng (img) (HL) (HSK1)'."""
    formatted_content = format_shared_image_comprehension_rich_text(explanation_json)
    cell.value = formatted_content
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    auto_size_cell(cell.parent, cell, plain_text_from_rich_text(formatted_content))

render_individual_img_explanation = render_simple_context_explanation
render_image_matching_explanation = render_simple_context_explanation
render_sentence_matching_explanation = render_simple_context_explanation  