# -*- coding: utf-8 -*-
"""
Handler Gradio cho công việc nền: bấm Chuyển đổi tạo công việc (jobs.py), giao diện hỏi trạng thái định kỳ
(gr.Timer) thay vì giữ một generator dài, nên đóng/khóa trình duyệt không làm mất việc.

Thứ tự đầu ra chung của mọi handler vẽ công việc (JOB_OUTPUTS, ghép với components trong build_ui):
    status, preview, raw, downloads, sig_state, timer, btn_file, btn_stop, btn_resume, job_flag
"""

import functools
import os

import gradio as gr

import job_view
import jobs
import pipeline
from ui_render import _download_panel

STATUS_HINT = "👋 Chọn tệp hoặc dán URL rồi bấm **Chuyển đổi**."
TICK_SECONDS = 2


def _mgr():
    return jobs.get_manager()


def collect_sources(file_paths, picked_paths):
    """Chuẩn hóa danh sách tệp từ gr.File / hộp thoại Windows -> (list đường dẫn, có phải đường dẫn thật)."""
    raw_sources = picked_paths if picked_paths else file_paths
    out = []
    if raw_sources:
        items = [raw_sources] if isinstance(raw_sources, (str, bytes)) else raw_sources
        for item in items or []:
            if not item:
                continue
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict) and "path" in item:
                out.append(item["path"])
            elif hasattr(item, "path"):
                out.append(getattr(item, "path"))
            else:
                out.append(str(item))
    return out, bool(picked_paths)


# ---------------------------------------------------------------------- vẽ công việc ra các thành phần
def _idle(status=None):
    """Không có công việc: nút Chuyển đổi hiện, Dừng/Chạy tiếp ẩn, Timer tắt."""
    return (
        status if status is not None else gr.skip(), gr.skip(), gr.skip(), gr.skip(), "",
        gr.Timer(active=False), gr.update(visible=True), gr.update(visible=False),
        gr.update(visible=False), job_view.flag_html(None),
    )


def render_job(job_id, last_sig="", reattach=False):
    """Trạng thái hiện tại của công việc -> bộ giá trị cho JOB_OUTPUTS.

    last_sig: chữ ký lần vẽ trước; không đổi thì không gửi lại xem trước/tải về (giảm tải đường truyền).
    reattach=True: mở lại công việc cũ (tải lại trang, Lịch sử) -> không tự tải tệp về máy.
    """
    mgr = _mgr()
    job = mgr.get(job_id) if job_id else None
    if not job:
        return _idle()
    active = job["status"] in job_view.ACTIVE
    sig = job_view.signature(job)
    if sig == last_sig:
        preview = raw = downloads = gr.skip()
    else:
        preview, raw = job_view.collect_previews(job, job_view.read_raw_from_disk(mgr))
        paths = [mgr.abs_path(job["id"], rel) for rel in job_view.output_rels(job)]
        downloads = _download_panel(
            paths, auto_download=bool(job["options"].get("auto_download_on")) and not reattach,
            zip_path=os.path.join(mgr.job_dir(job["id"]), "ketqua.zip"),
        )
    resumable = mgr.is_resumable(job)
    return (
        job_view.render_status_md(job), preview, raw, downloads, sig,
        gr.Timer(TICK_SECONDS, active=active),
        gr.update(visible=not active), gr.update(visible=active),
        gr.update(visible=resumable, value=job_view.resume_label(job)),
        job_view.flag_html(job),
    )


def on_tick(job_id, last_sig):
    return render_job(job_id, last_sig)


def on_reattach(job_id):
    """Mở lại trang: gắn vào công việc đang chạy / hiện lại kết quả công việc gần nhất."""
    return render_job(job_id, "", reattach=True)


def on_start_job(
    file_paths, mode_label, enable_plugins, use_ocr,
    ocr_model, ocr_effort, translate_model, translate_effort,
    force_ocr, board_dpi, translate_vn, merge_ocr_translate, ocr_pages_per_call,
    autosave_on, auto_download_on, autosave_dir, picked_paths, autosave_target, engine,
    api_key="", claude_token="", agy_token="",
    dropbox_sync_on=True, dropbox_folder="/MarkItDown",
    dropbox_token="", dropbox_refresh_token="", dropbox_app_key="", dropbox_app_secret="",
    page_spec="",
):
    """Bấm Chuyển đổi -> tạo công việc nền. Trả về [job_id] + JOB_OUTPUTS."""
    sources, real = collect_sources(file_paths, picked_paths)
    if not sources:
        return ("",) + _idle(
            "⚠️ **Chưa có tệp nào được tải lên.**\n\nVui lòng kéo-thả tệp vào khung tải tệp ở trên trước khi bấm **Chuyển đổi**."
        )
    options = dict(
        mode_label=mode_label, use_ocr=bool(use_ocr), force_ocr=bool(force_ocr),
        ocr_model=ocr_model, ocr_effort=ocr_effort, board_dpi=str(board_dpi),
        ocr_pages_per_call=str(ocr_pages_per_call or "1"), translate_vn=bool(translate_vn),
        merge=bool(merge_ocr_translate and translate_vn), translate_model=translate_model,
        translate_effort=translate_effort, page_spec=page_spec or "", engine=engine,
        autosave_on=bool(autosave_on), autosave_dir=autosave_dir or "", autosave_target=autosave_target,
        sources_are_real=real, auto_download_on=bool(auto_download_on),
        dropbox_sync_on=bool(dropbox_sync_on), dropbox_folder=dropbox_folder or "/MarkItDown",
    )
    creds = dict(
        api_key=api_key, claude_token=claude_token, agy_token=agy_token, dropbox_token=dropbox_token,
        dropbox_refresh_token=dropbox_refresh_token, dropbox_app_key=dropbox_app_key,
        dropbox_app_secret=dropbox_app_secret,
    )
    files = [
        {"path": p, "name": os.path.basename(p), "orig_path": p if real else None}
        for p in sources
    ]
    job_id = _mgr().submit(files, options, creds)
    return (job_id,) + render_job(job_id, "")


def on_stop_job(job_id):
    """Bấm Dừng: diệt tiến trình AI đang chạy; trạng thái cuối cùng đến qua Timer."""
    if job_id and _mgr().cancel(job_id):
        return "⏹ **Đang dừng…** diệt các tiến trình AI đang chạy; các trang đã xong được giữ lại."
    return gr.skip()


def on_resume_job(
    job_id, api_key="", claude_token="", agy_token="",
    dropbox_token="", dropbox_refresh_token="", dropbox_app_key="", dropbox_app_secret="",
):
    """Chạy tiếp / OCR lại trang lỗi: chỉ gọi AI cho các trang còn thiếu."""
    creds = dict(
        api_key=api_key, claude_token=claude_token, agy_token=agy_token, dropbox_token=dropbox_token,
        dropbox_refresh_token=dropbox_refresh_token, dropbox_app_key=dropbox_app_key,
        dropbox_app_secret=dropbox_app_secret,
    )
    if not job_id or not _mgr().resume(job_id, creds):
        return render_job(job_id, "", reattach=True)
    return render_job(job_id, "")


# ---------------------------------------------------------------------- lịch sử
def history_refresh():
    mgr = _mgr()
    rows = mgr.list_jobs()
    return (
        gr.update(choices=job_view.history_choices(rows), value=None),
        job_view.usage_md(mgr.disk_usage(), mgr.keep_days, len(rows)),
    )


def history_open(job_id):
    """Mở lại kết quả một công việc cũ. Trả về [job_id] + JOB_OUTPUTS."""
    if not job_id or not _mgr().get(job_id):
        return ("",) + _idle("ℹ️ Chọn một công việc trong danh sách rồi bấm **Mở**.")
    return (job_id,) + render_job(job_id, "", reattach=True)


def history_delete(job_id, current_job_id):
    """Xóa một công việc (không xóa được khi đang chạy). Trả về (dropdown, usage, thông báo, job_id hiện tại)."""
    mgr = _mgr()
    note = ""
    if job_id:
        if mgr.delete(job_id):
            note = "🗑 Đã xóa công việc."
            if job_id == current_job_id:
                current_job_id = ""
        else:
            note = "⚠️ Không xóa được (công việc đang chạy hoặc đã bị xóa)."
    dd, usage = history_refresh()
    return dd, usage + ("  \n" + note if note else ""), current_job_id


# ---------------------------------------------------------------------- ước lượng khoảng trang
@functools.lru_cache(maxsize=64)
def _pages_cached(path, mtime):
    return pipeline.count_pdf_pages(path)


def on_estimate(file_paths, picked_paths, page_spec, pages_per_call):
    """Dòng ước lượng 'N trang → M lượt gọi OCR' cho từng PDF đã chọn (trống nếu chưa chọn tệp)."""
    sources, _real = collect_sources(file_paths, picked_paths)
    ppc = int(pages_per_call or 1) if str(pages_per_call or "1").isdigit() else 1
    items = []
    for p in sources:
        name = os.path.basename(p)
        if os.path.splitext(p)[1].lower() != ".pdf":
            items.append((name, None, None, None))
            continue
        try:
            total = _pages_cached(p, os.path.getmtime(p))
        except OSError:
            total = None
        if total is None:
            items.append((name, None, None, None))
            continue
        try:
            sel = pipeline.parse_page_ranges(page_spec, total)
            items.append((name, total, len(sel) if sel is not None else None, None))
        except ValueError as exc:
            items.append((name, total, None, str(exc)))
    return job_view.estimate_md(items, ppc)


# ---------------------------------------------------------------------- hàng đợi tệp
def on_queue(file_paths, picked_paths):
    """Vẽ hàng đợi tệp từ các tệp đã chọn (kéo-thả hoặc hộp thoại Windows). Rỗng khi chưa có tệp."""
    sources, real = collect_sources(file_paths, picked_paths)
    items = []
    for p in sources:
        try:
            size = os.path.getsize(p)
        except OSError:
            size = None
        pages = None
        if os.path.splitext(p)[1].lower() == ".pdf":
            try:
                pages = _pages_cached(p, os.path.getmtime(p))
            except OSError:
                pages = None
        items.append((os.path.basename(p), size, pages))
    # Tệp chọn bằng hộp thoại không nằm trong gr.File nên không xóa từng tệp được -> chỉ liệt kê.
    return job_view.queue_html(items, removable=not real)
