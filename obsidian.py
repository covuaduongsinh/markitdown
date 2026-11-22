# -*- coding: utf-8 -*-
"""
Xuất cho Obsidian (thuần, không phụ thuộc Gradio/AI): thêm frontmatter YAML, tách Markdown theo tiêu đề cấp `#` thành các tệp chương.

Tiêu đề cấp `#` nằm trong khối code/chessboard (``` hoặc ~~~) không được tính là ranh giới chương.
"""

import re

_H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
_BAD_FILE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n+", re.DOTALL)


def yaml_quote(value):
    """Chuỗi YAML an toàn: luôn đặt trong nháy kép, thoát `\\` và `"`, bỏ ký tự xuống dòng."""
    text = " ".join(str(value).split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def frontmatter(meta):
    """Khối frontmatter YAML từ dict có thứ tự. Giá trị bool/số in thẳng, None bị bỏ, chuỗi được quote."""
    lines = ["---"]
    for key, val in meta.items():
        if val is None or val == "":
            continue
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {yaml_quote(val)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def strip_frontmatter(md):
    """Bỏ khối frontmatter ở đầu văn bản (nếu có) — để thêm lại không bị lặp."""
    return _FRONTMATTER_RE.sub("", md or "", count=1)


def with_frontmatter(md, meta):
    """frontmatter + thân văn bản (đã bỏ frontmatter cũ)."""
    return frontmatter(meta) + strip_frontmatter(md).lstrip("\n")


def first_title(md, fallback=""):
    """Nội dung tiêu đề `#` đầu tiên (ngoài khối code), hoặc fallback."""
    for _i, title, _body in _scan(md):
        if title:
            return title
    return fallback


def _scan(md):
    """Duyệt các đoạn: [(chỉ số, tiêu đề hoặc None, nội dung)]; đoạn đầu có tiêu đề None là phần trước tiêu đề đầu tiên."""
    parts = []
    title, buf, in_fence = None, [], False
    for line in (md or "").split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _H1_RE.match(line)
        if m:
            parts.append((title, "\n".join(buf)))
            title, buf = m.group(1).strip(), [line]
        else:
            buf.append(line)
    parts.append((title, "\n".join(buf)))
    return [(i, t, b) for i, (t, b) in enumerate(parts)]


def split_by_h1(md):
    """Tách theo tiêu đề `#` -> [(tiêu đề, văn bản chương gồm cả dòng tiêu đề)]. Phần trước tiêu đề đầu tiên (nếu không rỗng)
    thành mục có tiêu đề ''. Không có tiêu đề `#` nào -> danh sách rỗng (không có gì để tách)."""
    parts = _scan(md)
    if not any(t for _i, t, _b in parts):
        return []
    out = []
    for _i, title, body in parts:
        if title is None:
            if body.strip():
                out.append(("", body.strip("\n") + "\n"))
        else:
            out.append((title, body.strip("\n") + "\n"))
    return out


def safe_name(text, max_len=60):
    """Tên tệp an toàn (giữ chữ có dấu), không ký tự cấm, độ dài giới hạn."""
    name = _BAD_FILE_CHARS.sub(" ", text or "")
    name = " ".join(name.split()).strip(" .")
    return name[:max_len].rstrip(" .") or "chuong"


def chapter_filename(i, title, total):
    """`01-Tiêu đề.md` (đánh số có đệm 0 theo tổng số chương); mục trước tiêu đề đầu tiên là `00-Mở đầu.md`."""
    width = max(2, len(str(total)))
    return f"{i:0{width}d}-{safe_name(title) if title else 'Mở đầu'}.md"


def chapters(md, book_meta=None):
    """Danh sách (tên tệp, nội dung) của các chương, sẵn sàng ghi ra đĩa. `book_meta` (dict) được thêm vào frontmatter của
    từng chương cùng `title` (tên chương) và `chapter` (số thứ tự); None thì không thêm frontmatter."""
    parts = split_by_h1(strip_frontmatter(md))
    total = sum(1 for t, _b in parts if t)
    out, n = [], 0
    for title, body in parts:
        if title:
            n += 1
            idx = n
        else:
            idx = 0
        name = chapter_filename(idx, title, total)
        if book_meta is not None:
            meta = {"title": title or "Mở đầu", "chapter": idx, **book_meta}
            body = with_frontmatter(body, meta)
        out.append((name, body))  # hai chương cùng tiêu đề vẫn khác tên nhờ số thứ tự đứng đầu
    return out
