# -*- coding: utf-8 -*-
"""
Bảng thuật ngữ dịch: tệp `glossary.md` trong MID_DATA_DIR, mỗi dòng một cặp "nguồn → đích".

Khối chỉ thị sinh ở `prompt_block()` là NƠI DUY NHẤT định nghĩa quy tắc thuật ngữ; nó được chèn vào cả prompt OCR-gộp-dịch
(`claude_ocr._build_prompt*`) lẫn prompt dịch riêng (`claude_translate.translate_markdown_vn`), theo quy ước "một quy tắc chỉ
nằm ở một hằng" (AGENTS.md mục 4). Không có thuật ngữ nào thì khối rỗng và prompt giữ nguyên như trước.

Định dạng dòng: `nguồn → đích` (cũng nhận `->` hoặc `=>`); dòng trống và dòng bắt đầu bằng `#` bị bỏ qua.
Giới hạn để không làm phình prompt: tối đa MAX_ENTRIES cặp, mỗi vế tối đa MAX_TERM_LEN ký tự, cả khối tối đa MAX_BLOCK_CHARS.
"""

import hashlib
import os
import re

MAX_ENTRIES = 60
MAX_TERM_LEN = 60
MAX_BLOCK_CHARS = 2500
MAX_TEXT_CHARS = 20000   # kích thước tối đa của tệp glossary.md (phần thừa bị cắt khi lưu)

_SEP_RE = re.compile(r"\s*(?:→|=>|->)\s*")

GLOSSARY_HEADER = (
    "BẢNG THUẬT NGỮ (BẮT BUỘC): khi gặp thuật ngữ ở vế trái dưới đây, KHÔNG tự chọn cách dịch khác — "
    "LUÔN dịch đúng như vế phải (chỉ đổi hoa/thường cho hợp văn cảnh). "
    "KHÔNG áp dụng bên trong khối ```chessboard và khối code.\n"
)


def glossary_path():
    import jobs

    return os.path.join(jobs.data_dir(), "glossary.md")


def parse(text):
    """Phân tích văn bản -> (danh sách (nguồn, đích), danh sách cảnh báo tiếng Việt). Trùng nguồn: dòng sau thắng."""
    entries, warnings, seen = [], [], {}
    for lineno, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = _SEP_RE.split(line, maxsplit=1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            warnings.append(f"Dòng {lineno} bỏ qua (cần dạng «nguồn → đích»).")
            continue
        src, dst = parts[0].strip(), parts[1].strip()
        if len(src) > MAX_TERM_LEN or len(dst) > MAX_TERM_LEN:
            warnings.append(f"Dòng {lineno} bỏ qua (mỗi vế tối đa {MAX_TERM_LEN} ký tự).")
            continue
        key = src.casefold()
        if key in seen:
            entries[seen[key]] = (src, dst)
            continue
        if len(entries) >= MAX_ENTRIES:
            warnings.append(f"Dòng {lineno} bỏ qua (tối đa {MAX_ENTRIES} thuật ngữ).")
            continue
        seen[key] = len(entries)
        entries.append((src, dst))
    return entries, warnings


def load_text():
    """Nội dung tệp glossary.md ('' nếu chưa có)."""
    try:
        with open(glossary_path(), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def save_text(text):
    """Ghi glossary.md (nguyên tử). Trả (số thuật ngữ hợp lệ, cảnh báo)."""
    text = text or ""
    extra = []
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        extra.append(f"Văn bản dài quá {MAX_TEXT_CHARS} ký tự nên đã bị cắt.")
    entries, warnings = parse(text)
    warnings = warnings + extra
    path = glossary_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return len(entries), warnings


def prompt_block(entries=None):
    """Khối chỉ thị thuật ngữ để nối vào prompt ('' nếu chưa có thuật ngữ nào). Cắt bớt cho vừa MAX_BLOCK_CHARS."""
    if entries is None:
        entries, _w = parse(load_text())
    if not entries:
        return ""
    lines, used = [], len(GLOSSARY_HEADER)
    for src, dst in entries:
        line = f"- {src} → {dst}\n"
        if used + len(line) > MAX_BLOCK_CHARS:
            break
        lines.append(line)
        used += len(line)
    return GLOSSARY_HEADER + "".join(lines) + "\n"


def fingerprint(block):
    """Dấu vân tay ngắn của khối thuật ngữ (đưa vào khóa điểm lưu dịch: đổi thuật ngữ thì không dùng lại bản dịch cũ)."""
    return hashlib.sha1((block or "").encode("utf-8")).hexdigest()[:10] if block else ""
