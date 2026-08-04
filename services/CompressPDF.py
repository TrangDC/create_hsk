import os
import shutil
import subprocess
from pathlib import Path


def _find_ghostscript_executable():
    """Tìm executable Ghostscript trên Windows theo PATH hoặc thư mục cài đặt phổ biến."""
    candidates = ["gswin64c", "gswin32c", "gs"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    common_roots = [
        Path("C:/Program Files/gs"),
        Path("C:/Program Files (x86)/gs"),
    ]
    executable_names = ["gswin64c.exe", "gswin32c.exe"]

    for root in common_roots:
        if not root.exists():
            continue
        for version_dir in sorted(root.iterdir(), reverse=True):
            if not version_dir.is_dir():
                continue
            bin_dir = version_dir / "bin"
            for executable_name in executable_names:
                executable_path = bin_dir / executable_name
                if executable_path.exists():
                    return str(executable_path)

    return None

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

    if quality not in {"screen", "ebook", "printer", "prepress"}:
        raise ValueError(f"Chất lượng PDF không hợp lệ: {quality}")

    ghostscript_executable = _find_ghostscript_executable()
    if not ghostscript_executable:
        raise FileNotFoundError(
            "Không tìm thấy Ghostscript. Hãy cài Ghostscript và đảm bảo 'gswin64c' có trong PATH, "
            "hoặc cài vào thư mục mặc định C:/Program Files/gs/."
        )

    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if input_path == output_path:
        temp_output_path = str(Path(output_path).with_name(f"{Path(output_path).stem}_compressed{Path(output_path).suffix}"))
    else:
        temp_output_path = output_path

    gs_command = [
        ghostscript_executable,
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS=/{quality}',
        '-dNOPAUSE',
        '-dQUIET',
        '-dBATCH',
        f'-sOutputFile={temp_output_path}',
        input_path,
    ]

    try:
        subprocess.run(gs_command, check=True, capture_output=True, text=True)
        if temp_output_path != output_path:
            shutil.move(temp_output_path, output_path)
        print(f"Nén thành công: {output_path}")
    except subprocess.CalledProcessError as e:
        print("Lỗi khi nén PDF:")
        print(e)
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)
        raise


path = r"D:\Edmicro\Tools\create_hsk\input\tóm tắt HSK\hsk5\TT_H5_B3.pdf"

if __name__ == "__main__":
    compress_pdf_ghostscript(path, r"D:\Edmicro\Tools\create_hsk\input\tóm tắt HSK\hsk5\TT_H5_B3.pdf", 'ebook')