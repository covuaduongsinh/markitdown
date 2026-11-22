# -*- coding: utf-8 -*-
"""
Handler Gradio cho hai tab hiệu đính: "Thế cờ" (bảng FEN sửa được) và "Đối chiếu trang" (ảnh trang gốc ↔ Markdown của đúng trang).

Mọi handler nhận (job_id, file_pick): `job_id` là công việc đang xem (BrowserState), `file_pick` là tệp đang chọn (chip) hoặc None.
"""

import os
from urllib.parse import quote

import gradio as gr

import fen_tools
import job_view
import jobs
import review

CMP_FILTERS = ["Tất cả trang", "Chỉ trang lỗi", "Chỉ trang có bàn cờ"]
_FILTER_KEY = {CMP_FILTERS[0]: "all", CMP_FILTERS[1]: "errors", CMP_FILTERS[2]: "boards"}


def _mgr():
    return jobs.get_manager()


def _context(job_id, selected):
    """(job, file_idx) hiện hành; (None, None) nếu chưa có công việc/tệp xong."""
    mgr = _mgr()
    job = mgr.get(job_id) if job_id else None
    if not job:
        return None, None
    idx = job_view.pick_selected(job, selected)
    return (job, idx) if idx is not None else (job, None)


def _msg(text, kind="info"):
    return job_view.message_html(text, kind) if text else ""


# ---------------------------------------------------------------------- tab "Thế cờ" (G3.1)
FEN_OUTPUTS_N = 7  # info, table, idx, fen_text, preview, link, msg


def _fen_view(boards, idx, msg=""):
    """Bộ giá trị cho [fen_info, fen_table, fen_idx, fen_text, fen_preview, fen_link, fen_msg] tại thế cờ idx (1-based)."""
    if not boards:
        info = job_view.message_html("Chưa có thế cờ nào (tệp không phải sách cờ vua hoặc OCR chưa tìm thấy sơ đồ).", "info")
        return info, [], 1, "", "", "", msg
    idx = min(max(1, int(idx or 1)), len(boards))
    bad = sum(1 for b in boards if not b["valid"])
    info = (
        f'<div class="mid-fen-info"><b>{len(boards)}</b> thế cờ'
        + (f' · <span class="mid-fen-bad">{bad} cần xem</span>' if bad else " · tất cả hợp lệ")
        + "</div>"
    )
    rows = [
        [b["n"], b["page"] if b["page"] is not None else "—", b["fen"], "✅" if b["valid"] else "⚠️ cần xem"]
        for b in boards
    ]
    cur = boards[idx - 1]
    return info, rows, idx, cur["fen"], _preview_html(cur["fen"]), _link_html(cur["fen"]), msg


def _preview_html(fen):
    status = (
        '<span class="mid-fen-ok">✅ Hợp lệ</span>' if fen_tools.fen_is_valid(fen)
        else '<span class="mid-fen-bad">⚠️ Cần xem: sai cú pháp hoặc không đủ hai Vua</span>'
    )
    return f'<div class="mid-fen-prev">{fen_tools.board_html(fen, 240)}<div class="mid-fen-status">{status}</div></div>'


def _link_html(fen):
    if not fen_tools.fen_is_valid(fen) and not (fen or "").strip():
        return ""
    return (
        f'<a class="mid-fen-lichess" href="{fen_tools.escape(fen_tools.lichess_url(fen))}" target="_blank" rel="noopener">'
        "Mở trong Lichess ↗</a>"
    )


def fen_refresh(job_id, selected):
    """Nạp bảng thế cờ của tệp đang xem (gọi khi mở tab, đổi tệp/công việc)."""
    job, idx = _context(job_id, selected)
    if not job or idx is None:
        return _fen_view([], 1)
    return _fen_view(review.load_boards(_mgr(), job, idx), 1)


def fen_goto(job_id, selected, n):
    job, idx = _context(job_id, selected)
    if not job or idx is None:
        return _fen_view([], 1)
    return _fen_view(review.load_boards(_mgr(), job, idx), n)


def fen_step(job_id, selected, n, delta):
    return fen_goto(job_id, selected, int(n or 1) + delta)


def fen_select(job_id, selected, evt: gr.SelectData):
    """Bấm một dòng của bảng -> chuyển tới thế cờ đó."""
    row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    return fen_goto(job_id, selected, int(row) + 1)


def fen_preview(fen):
    """Gõ vào ô FEN -> vẽ lại bàn cờ ngay (chưa ghi)."""
    return _preview_html(fen), _link_html(fen)


def fen_flip(fen):
    """Lật bàn 180° (chưa ghi)."""
    flipped = fen_tools.flip_fen(fen)
    return flipped, _preview_html(flipped), _link_html(flipped)


def fen_apply(job_id, selected, n, fen):
    """Ghi FEN đã sửa vào .md, _vn.md, điểm lưu trang, _fen.txt, zip; nạp lại bảng và dừng ở thế cờ đó."""
    job, idx = _context(job_id, selected)
    if not job or idx is None:
        return _fen_view([], 1, _msg("Chưa có tệp nào xong để hiệu đính.", "warn"))
    try:
        out = review.apply_fen(_mgr(), job_id, idx, int(n or 1), fen)
    except review.ReviewError as exc:
        view = _fen_view(review.load_boards(_mgr(), job, idx), n)
        return view[:-1] + (_msg(f"⚠️ {exc}", "warn"),)
    job = _mgr().get(job_id)
    where = f"trang {out['page']}" if out["page"] else "văn bản"
    note = f"✅ Đã ghi thế cờ số {int(n)} ({where}) vào: " + ", ".join(out["files"]) + ". Tải lại tệp kết quả để lấy bản mới."
    return _fen_view(review.load_boards(_mgr(), job, idx), n, _msg(note, "ok"))


# ---------------------------------------------------------------------- tab "Đối chiếu trang" (G3.2)
def _file_url(path):
    return "/gradio_api/file=" + quote(path.replace("\\", "/"))


def _cmp_view(job, idx, flt, page):
    """(page, ảnh HTML, Markdown, thông tin) cho trang `page` thuộc bộ lọc flt; page sai -> trang gần nhất hợp lệ."""
    rows = review.page_list(_mgr(), job, idx, _FILTER_KEY.get(flt, "all"))
    if not rows:
        empty = "Không có trang nào khớp bộ lọc." if _FILTER_KEY.get(flt) != "all" else "Tệp này chưa có điểm lưu theo trang (không phải PDF OCR)."
        return None, "", "", _msg(empty, "info")
    pages = [r["page"] for r in rows]
    cur = next((p for p in pages if p >= int(page or 0)), pages[-1])
    row = rows[pages.index(cur)]
    thumb = review.page_thumb(_mgr(), job, idx, cur)
    if thumb:
        img = f'<img class="mid-cmp-img" src="{fen_tools.escape(_file_url(thumb))}" alt="Trang {cur} của tệp gốc">'
    else:
        img = '<div class="mid-cmp-noimg">Không có ảnh trang (tệp nguồn không phải PDF hoặc không đọc được).</div>'
    if row["ok"]:
        md = row["text"]
        extra = f" · {row['boards']} thế cờ" if row["boards"] else ""
    else:
        md = "⚠️ **Trang này OCR lỗi.** " + (row["error"] or "")
        extra = " · lỗi"
    pos = pages.index(cur) + 1
    info = f'<div class="mid-fen-info">Trang <b>{cur}</b> ({pos}/{len(pages)}{extra})</div>'
    return cur, img, md, info


def cmp_load(job_id, selected, flt, page):
    job, idx = _context(job_id, selected)
    if not job or idx is None:
        return None, "", "", _msg("Chưa có tệp nào xong để đối chiếu.", "info")
    return _cmp_view(job, idx, flt, page)


def cmp_step(job_id, selected, flt, page, delta):
    """Trang trước/sau trong bộ lọc hiện hành."""
    job, idx = _context(job_id, selected)
    if not job or idx is None:
        return None, "", "", _msg("Chưa có tệp nào xong để đối chiếu.", "info")
    rows = review.page_list(_mgr(), job, idx, _FILTER_KEY.get(flt, "all"))
    pages = [r["page"] for r in rows]
    if not pages:
        return _cmp_view(job, idx, flt, page)
    cur = int(page or pages[0])
    if delta > 0:
        target = next((p for p in pages if p > cur), pages[-1])
    else:
        target = next((p for p in reversed(pages) if p < cur), pages[0])
    return _cmp_view(job, idx, flt, target)
