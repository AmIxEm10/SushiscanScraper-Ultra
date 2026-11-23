import os
import re
import zipfile
from io import BytesIO
from PIL import Image

ALLOWED_WEBSITES = ["sushiscan.net", "sushiscan.fr"]
DEFAULT_WEBSITE = "sushiscan.net"

def sanitize_filename(name: str) -> str:
    """Removes invalid characters for Windows / Linux filenames."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r'\s+', " ", cleaned).strip()
    return cleaned or "unnamed"

def parse_chapter_selection(input_str: str, total_count: int) -> list[int]:
    """
    Parses user input for chapter selection and returns 0-based sorted indices.
    Supports:
      - 'all', 'tout', '*'
      - 'latest', 'dernier', 'last'
      - single numbers: '5'
      - ranges: '1-10', '1:10', '5-', ':8'
      - comma-separated: '1, 3, 5-8'
    """
    s = input_str.strip().lower()
    if not s:
        return []
    if s in ["all", "tout", "*"]:
        return list(range(total_count))
    if s in ["latest", "dernier", "last", "recent"]:
        return [total_count - 1] if total_count > 0 else []

    indices = set()
    parts = [p.strip() for p in s.split(",") if p.strip()]

    for part in parts:
        if "-" in part or ":" in part:
            sep = "-" if "-" in part else ":"
            start_str, end_str = part.split(sep, 1)
            start_val = int(start_str.strip()) if start_str.strip() else 1
            end_val = int(end_str.strip()) if end_str.strip() else total_count

            # Convert 1-based human range to 0-based indices
            start_idx = max(0, start_val - 1)
            end_idx = min(total_count, end_val)
            for i in range(start_idx, end_idx):
                indices.add(i)
        elif part.isdigit():
            val = int(part)
            if 1 <= val <= total_count:
                indices.add(val - 1)

    return sorted(list(indices))

def save_images_as_pdf(images_data: list[tuple[str, bytes]], output_pdf_path: str) -> bool:
    """
    Converts list of (filename, image_bytes) to a single PDF.
    Handles RGB, RGBA, transparency, and WebP.
    """
    if not images_data:
        return False

    pil_images = []
    for filename, raw_bytes in images_data:
        try:
            img = Image.open(BytesIO(raw_bytes))
            if img.mode in ("RGBA", "LA", "P"):
                # Paste on white background
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                mask = img.split()[-1] if "A" in img.mode else None
                bg.paste(img, mask=mask)
                pil_images.append(bg)
            elif img.mode != "RGB":
                pil_images.append(img.convert("RGB"))
            else:
                pil_images.append(img)
        except Exception as e:
            # Skip invalid images
            continue

    if not pil_images:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    pil_images[0].save(
        output_pdf_path,
        "PDF",
        resolution=100.0,
        save_all=True,
        append_images=pil_images[1:]
    )
    return True

def save_images_as_cbz(images_data: list[tuple[str, bytes]], output_cbz_path: str) -> bool:
    """Saves images into a .cbz archive (comic book zip)."""
    if not images_data:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_cbz_path)), exist_ok=True)
    with zipfile.ZipFile(output_cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, (filename, raw_bytes) in enumerate(images_data):
            ext = os.path.splitext(filename)[1] or ".jpg"
            arcname = f"page_{idx+1:03d}{ext}"
            zf.writestr(arcname, raw_bytes)
    return True

def save_raw_images(images_data: list[tuple[str, bytes]], output_folder: str) -> bool:
    """Saves images in a folder as individual files."""
    if not images_data:
        return False

    os.makedirs(output_folder, exist_ok=True)
    for idx, (filename, raw_bytes) in enumerate(images_data):
        ext = os.path.splitext(filename)[1] or ".jpg"
        filepath = os.path.join(output_folder, f"page_{idx+1:03d}{ext}")
        with open(filepath, "wb") as f:
            f.write(raw_bytes)
    return True
