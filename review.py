# -*- coding: utf-8 -*-
"""
Hiệu đính kết quả của một công việc đã xong (không phụ thuộc Gradio): bảng thế cờ (sửa FEN, ghi lại mọi tệp liên quan)
và đối chiếu từng trang gốc ↔ Markdown của đúng trang đó.

Quy ước dữ liệu (xem jobs.py): f<NN>/pages/NNNN.md|.err là kết quả OCR từng trang, f<NN>/raw.md là văn bản chính,
f<NN>/out/ chứa <tên>.md, <tên>_vn.md, <tên>_fen.txt. "Văn bản chính" = tệp `md` (OCR chưa dịch) nếu có, không thì `vn`.
"""

import os
import re

import fen_tools
import jobs

_PAGE_MD_RE = re.compile(r"^(\d{4,})\.md$")
_PAGE_ERR_RE = re.compile(r"^(\d{4,})\.err$")
THUMB_MAX_WIDTH = 900


class ReviewError(Exception):
    """Lỗi hiệu đính có thông báo tiếng Việt để hiện cho người dùng."""


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _file_entry(job, file_idx):
    for f in job["files"]:
        if f["idx"] == file_idx:
            return f
    raise ReviewError("Không tìm thấy tệp trong công việc.")


def md_outputs(f):
    """Các tệp kết quả dạng Markdown của một tệp nguồn (md và/hoặc vn), theo thứ tự."""
    return [o for o in f.get("outputs", []) if o.get("kind") in ("md", "vn")]


def main_output(f):
    """Tệp văn bản chính: `md` nếu có, không thì `vn` (chế độ gộp OCR+dịch chỉ ghi `_vn.md`)."""
    outs = md_outputs(f)
    for o in outs:
        if o["kind"] == "md":
            return o
    return outs[0] if outs else None


def _pages_dir(mgr, job_id, file_idx):
    return os.path.join(mgr.file_dir(job_id, file_idx), "pages")


def page_files(mgr, job_id, file_idx):
    """{số trang: ('ok'|'err', đường dẫn)} cho mọi trang đã có điểm lưu (.md thắng .err)."""
    pdir = _pages_dir(mgr, job_id, file_idx)
    out = {}
    try:
        names = os.listdir(pdir)
    except OSError:
        return out
    for n in names:
        m = _PAGE_ERR_RE.match(n)
        if m:
            out[int(m.group(1))] = ("err", os.path.join(pdir, n))
    for n in names:
        m = _PAGE_MD_RE.match(n)
        if m:
            out[int(m.group(1))] = ("ok", os.path.join(pdir, n))
    return out


def _board_pages(mgr, job_id, file_idx, total_boards):
    """Danh sách (trang, chỉ số thế cờ trong trang) theo thứ tự thế cờ toàn tệp; None nếu không khớp tổng số (không tin được)."""
    mapping = []
    for page, (kind, path) in sorted(page_files(mgr, job_id, file_idx).items()):
        if kind != "ok":
            continue
        for k in range(1, len(fen_tools.list_boards(_read(path))) + 1):
            mapping.append((page, k))
    return mapping if len(mapping) == total_boards else None


def load_boards(mgr, job, file_idx):
    """Bảng thế cờ của một tệp: [{'n', 'fen', 'valid', 'page'}]; page là None nếu không suy ra được."""
    f = _file_entry(job, file_idx)
    out = main_output(f)
    if not out:
        return []
    md = _read(mgr.abs_path(job["id"], out["rel"]))
    boards = fen_tools.list_boards(md)
    mapping = _board_pages(mgr, job["id"], file_idx, len(boards))
    for i, b in enumerate(boards):
        b["page"] = mapping[i][0] if mapping else None
    return boards


def apply_fen(mgr, job_id, file_idx, n, new_fen):
    """Ghi FEN mới cho thế cờ thứ n vào MỌI nơi liên quan: các tệp .md/_vn.md, raw.md, điểm lưu trang tương ứng
    (để "Chạy tiếp" không làm mất sửa đổi), tệp _fen.txt và zip. Trả {'files': [...], 'page': trang hoặc None}.

    Tính trước toàn bộ nội dung mới rồi mới ghi, nên lỗi (n ngoài khoảng, FEN sai) không để lại tệp ghi dở.
    """
    job = mgr.get(job_id)
    if not job:
        raise ReviewError("Công việc không còn tồn tại.")
    if job["status"] in jobs.ACTIVE:
        raise ReviewError("Công việc đang chạy — hãy chờ xong rồi hiệu đính.")
    f = _file_entry(job, file_idx)
    if f["status"] != "done":
        raise ReviewError("Tệp này chưa xong.")
    main = main_output(f)
    if not main:
        raise ReviewError("Tệp này không có kết quả Markdown.")
    main_text = _read(mgr.abs_path(job_id, main["rel"]))
    total = len(fen_tools.list_boards(main_text))
    mapping = _board_pages(mgr, job_id, file_idx, total)

    writes = {}  # đường dẫn -> nội dung mới
    try:
        for o in md_outputs(f):
            p = mgr.abs_path(job_id, o["rel"])
            writes[p] = fen_tools.replace_nth_fen(_read(p), n, new_fen)
        raw_path = os.path.join(mgr.file_dir(job_id, file_idx), "raw.md")
        if os.path.exists(raw_path):
            writes[raw_path] = fen_tools.replace_nth_fen(_read(raw_path), n, new_fen)
        page = None
        if mapping and 1 <= n <= len(mapping):
            page, local = mapping[n - 1]
            ppath = page_files(mgr, job_id, file_idx)[page][1]
            writes[ppath] = fen_tools.replace_nth_fen(_read(ppath), local, new_fen)
    except ValueError as exc:
        raise ReviewError(str(exc)) from exc

    for p, text in writes.items():
        jobs._atomic_write(p, text)
    new_main = writes[mgr.abs_path(job_id, main["rel"])]
    for o in f.get("outputs", []):
        if o.get("kind") == "fen":
            jobs._atomic_write(mgr.abs_path(job_id, o["rel"]), fen_tools.fens_text(new_main))
    mgr.rebuild_obsidian(job_id, file_idx)  # làm lại frontmatter/chương Obsidian (nếu bật) và zip theo văn bản mới
    return {"files": [os.path.basename(p) for p in writes], "page": page}


# ---------------------------------------------------------------------- đối chiếu trang gốc ↔ kết quả (G3.2)
def page_list(mgr, job, file_idx, only="all"):
    """Danh sách trang có điểm lưu: [{'page', 'ok', 'text', 'error', 'boards'}]. only: 'all' | 'errors' | 'boards'."""
    rows = []
    for page, (kind, path) in sorted(page_files(mgr, job["id"], file_idx).items()):
        text = _read(path)
        row = {
            "page": page, "ok": kind == "ok", "text": text if kind == "ok" else "",
            "error": text if kind == "err" else "", "boards": len(fen_tools.list_boards(text)) if kind == "ok" else 0,
        }
        if only == "errors" and row["ok"]:
            continue
        if only == "boards" and not row["boards"]:
            continue
        rows.append(row)
    return rows


def page_thumb(mgr, job, file_idx, page):
    """Đường dẫn ảnh JPEG thu nhỏ của một trang PDF nguồn (tạo lần đầu từ tệp nguồn, rồi lưu pages/NNNN.jpg). None nếu không tạo được."""
    f = _file_entry(job, file_idx)
    pdir = _pages_dir(mgr, job["id"], file_idx)
    out = os.path.join(pdir, f"{page:04d}.jpg")
    if os.path.exists(out):
        return out
    src = os.path.join(mgr.job_dir(job["id"]), f["src"])
    if os.path.splitext(src)[1].lower() != ".pdf" or not os.path.exists(src):
        return None
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(src)
        try:
            if not 1 <= page <= len(pdf):
                return None
            img = pdf[page - 1].render(scale=1.5).to_pil().convert("RGB")
        finally:
            pdf.close()
        if img.width > THUMB_MAX_WIDTH:
            img = img.resize((THUMB_MAX_WIDTH, max(1, img.height * THUMB_MAX_WIDTH // img.width)))
        os.makedirs(pdir, exist_ok=True)
        tmp = out + ".tmp"
        img.save(tmp, format="JPEG", quality=72)
        os.replace(tmp, out)
        return out
    except Exception:
        return None
