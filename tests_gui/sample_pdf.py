"""Tạo PDF mẫu dạng scan (chỉ ảnh, không có lớp văn bản) bằng Pillow để kiểm luồng OCR với engine giả."""

import os

from PIL import Image, ImageDraw


def make_sample_pdf(path, pages=6, size=(612, 792)):
    """Ghi PDF `pages` trang vào `path`; mỗi trang là một ảnh có số trang to ở giữa."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    imgs = []
    for n in range(1, pages + 1):
        im = Image.new("RGB", size, "white")
        d = ImageDraw.Draw(im)
        d.rectangle([40, 40, size[0] - 40, size[1] - 40], outline="black", width=3)
        d.text((size[0] // 2 - 20, size[1] // 2), f"TRANG {n}", fill="black")
        imgs.append(im)
    imgs[0].save(path, "PDF", save_all=True, append_images=imgs[1:], resolution=72.0)
    return path
