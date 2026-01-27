import subprocess
import os

def compress_pdf_ghostscript(input_path, output_path, quality='screen'):
    """
    quality options:
    - screen: 72dpi, nhỏ nhất
    - ebook: 150dpi, vừa phải 
    - printer: 300dpi, chất lượng cao
    - prepress: 300dpi, chất lượng tốt nhất
    """
    if not os.path.isfile(input_path):
        print(f"File nguồn không tồn tại: {input_path}")
        return

    # Đặt đường dẫn trong dấu ngoặc kép để tránh lỗi với tên file có dấu cách/ký tự đặc biệt
    gs_command = [
        'gswin64c',
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS=/{quality}',
        '-dNOPAUSE',
        '-dQUIET',
        '-dBATCH',
        f'-sOutputFile="{output_path}"',
        f'"{input_path}"'
    ]

    try:
        # shell=True để xử lý dấu ngoặc kép trên Windows
        result = subprocess.run(" ".join(gs_command), shell=True, check=True, capture_output=True, text=True)
        print(f"Nén thành công: {output_path}")
    except subprocess.CalledProcessError as e:
        print("Lỗi khi nén PDF:")
        print(e)
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)


# path = r"D:\Tools\sumaryContent\HSK5 课文 第五课 .pdf"

# compress_pdf_ghostscript(path, "output/HSK5_课文_第五课_compressed.pdf", 'ebook')