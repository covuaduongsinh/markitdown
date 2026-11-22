# -*- coding: utf-8 -*-
"""
Chuyển trạng thái công việc (jobs.py) thành thứ hiển thị: dòng trạng thái, xem trước, danh sách tệp tải, lịch sử.
Không phụ thuộc Gradio. Mọi chuỗi đưa vào HTML đều đi qua html.escape.
"""

import html
import os
import time

ACTIVE = ("queued", "running")

_STAGE_TEXT = {
    "convert": "đang phân tích định dạng",
    "publish": "đang lưu kết quả",
}


def fmt_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _stage_text(f):
    stage = f.get("stage")
    if stage == "ocr":
        total = f.get("pages_total") or 0
        return f"OCR trang {f.get('pages_done', 0)}/{total}" if total else "đang OCR"
    if stage == "translate":
        total = f.get("chunks_total") or 0
        return f"dịch đoạn {f.get('chunks_done', 0)}/{total}" if total else "đang dịch"
    return _STAGE_TEXT.get(stage, "đang xử lý")


def failed_pages_total(job):
    return sum(f.get("pages_failed", 0) for f in job["files"])


def resume_label(job):
    """Nhãn nút chạy tiếp: «OCR lại N trang lỗi» khi chỉ còn trang lỗi, «Chạy tiếp» khi còn tệp dang dở."""
    unfinished = any(f["status"] != "done" for f in job["files"])
    k = failed_pages_total(job)
    if not unfinished and k:
        return f"🔁 OCR lại {k} trang lỗi"
    return "▶ Chạy tiếp"


def signature(job):
    """Chuỗi thay đổi khi có tệp mới xong/đổi trạng thái -> lúc đó mới gửi lại phần xem trước và danh sách tải."""
    parts = [job["id"], job["status"]]
    for f in job["files"]:
        parts.append(f"{f['status']}:{len(f.get('outputs', []))}:{f.get('pages_failed', 0)}")
    return "|".join(parts)


def collect_previews(job, read_raw, only=None):
    """(preview_md, raw_md) ghép từ các tệp đã xong (hoặc chỉ tệp có idx == only). read_raw(job, file_entry) -> văn bản."""
    previews, raws = [], []
    for f in job["files"]:
        if f["status"] != "done" or (only is not None and f["idx"] != only):
            continue
        text = read_raw(job, f)
        if not text.strip():
            continue
        previews.append(f"## 📄 {f['name']}\n\n{text}")
        raws.append(text)
    return "\n\n---\n\n".join(previews), "\n\n".join(raws)


def pick_selected(job, selected):
    """Tệp đang xem: `selected` nếu là một tệp đã xong, không thì tệp xong đầu tiên (None nếu chưa có tệp nào xong)."""
    done = [f["idx"] for f in job["files"] if f["status"] == "done"]
    if selected in done:
        return selected
    return done[0] if done else None


def output_meta(job, read_path):
    """{rel: 'N ký tự · M thế cờ'} cho từng tệp kết quả. read_path(rel) -> văn bản."""
    meta = {}
    for f in job["files"]:
        for o in f.get("outputs", []):
            text = read_path(o["rel"])
            if not text:
                continue
            if o.get("kind") == "fen":
                n = len([ln for ln in text.splitlines() if ln.strip()])
                meta[o["rel"]] = f"{n} thế cờ"
            else:
                chars = f"{len(text):,}".replace(",", ".")
                boards = text.count("```chessboard")
                meta[o["rel"]] = f"{chars} ký tự" + (f" · {boards} thế cờ" if boards else "")
    return meta


def output_rels(job):
    """Đường dẫn tương đối (từ thư mục công việc) của mọi tệp kết quả, theo thứ tự tệp nguồn."""
    return [o["rel"] for f in job["files"] for o in f.get("outputs", [])]


def flag_html(job):
    """Thẻ ẩn để JS (đổi tiêu đề tab, thông báo trình duyệt) biết trạng thái công việc."""
    if not job:
        return '<div id="mid-job-flag" data-state="none" data-id="" data-failed="0"></div>'
    return (
        f'<div id="mid-job-flag" data-state="{html.escape(job["status"])}" '
        f'data-id="{html.escape(job["id"])}" data-failed="{failed_pages_total(job)}"></div>'
    )


_STATUS_ICON = {"done": "✅", "error": "❌", "cancelled": "⏹", "running": "⏳", "queued": "⌛"}


def history_label(row):
    """Nhãn một dòng lịch sử (chuỗi thuần, dùng cho Dropdown)."""
    when = time.strftime("%d/%m %H:%M", time.localtime(row["created"]))
    names = ", ".join(row["names"][:2]) + (f" +{len(row['names']) - 2}" if len(row["names"]) > 2 else "")
    bad = f" · {row['failed_pages']} trang lỗi" if row["failed_pages"] else ""
    icon = _STATUS_ICON.get(row["status"], "•")
    return f"{when} · {names} · {icon} {row['n_done']}/{row['n_files']} tệp{bad}"


def history_choices(rows):
    return [(history_label(r), r["id"]) for r in rows]


def usage_md(total_bytes, keep_days, n_jobs):
    keep = f"giữ {keep_days} ngày" if keep_days > 0 else "không tự xóa"
    return f"💾 {n_jobs} công việc · đang dùng **{fmt_bytes(total_bytes)}** ({keep})."


def estimate_md(items, pages_per_call):
    """items: list (tên, tổng_trang | None, số_trang_chọn | None, lỗi | None) -> dòng ước lượng số lượt gọi OCR."""
    import pipeline

    lines = []
    total_calls = 0
    for name, total, chosen, err in items:
        safe = html.escape(name)
        if err:
            lines.append(f"- {safe}: ⚠️ {html.escape(err)}")
        elif total is None:
            lines.append(f"- {safe}: không phải PDF hoặc không đọc được số trang")
        else:
            n = chosen if chosen is not None else total
            calls = pipeline.estimate_ocr_calls(n, pages_per_call)
            total_calls += calls
            sel = f"{n}/{total} trang" if n != total else f"{total} trang"
            lines.append(f"- {safe}: {sel} → **{calls} lượt gọi OCR**")
    if not lines:
        return ""
    head = f"📊 Ước lượng: **{total_calls} lượt gọi OCR** (mỗi lượt {pages_per_call} trang)"
    return head + "\n" + "\n".join(lines)


def read_raw_from_disk(manager):
    """Trả hàm read_raw(job, file_entry) đọc f<NN>/raw.md trong thư mục công việc."""

    def _read(job, f):
        path = os.path.join(manager.file_dir(job["id"], f["idx"]), "raw.md")
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    return _read


# ---------------------------------------------------------------------- hàng đợi tệp (G1.3)
_Q_TYPES = {
    ".pdf": ("PDF", "#EE5A52"), ".doc": ("Word", "#3DA0E3"), ".docx": ("Word", "#3DA0E3"), ".rtf": ("Văn bản", "#3DA0E3"),
    ".xls": ("Excel", "#1FA98F"), ".xlsx": ("Excel", "#1FA98F"), ".csv": ("CSV", "#1FA98F"),
    ".ppt": ("PowerPoint", "#D99A12"), ".pptx": ("PowerPoint", "#D99A12"),
    ".jpg": ("Ảnh", "#8B5CF6"), ".jpeg": ("Ảnh", "#8B5CF6"), ".png": ("Ảnh", "#8B5CF6"), ".gif": ("Ảnh", "#8B5CF6"),
    ".webp": ("Ảnh", "#8B5CF6"), ".bmp": ("Ảnh", "#8B5CF6"), ".tif": ("Ảnh", "#8B5CF6"), ".tiff": ("Ảnh", "#8B5CF6"),
}
_Q_FILE_ICON = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/></svg>'
)


def queue_html(items, removable=True):
    """HTML hàng đợi tệp. items: list (tên, dung_lượng_byte | None, số_trang | None). Rỗng -> chuỗi rỗng."""
    if not items:
        return ""
    n = len(items)
    head = (
        f'<div class="mid-q-head"><span class="mid-q-title">{n} tệp trong hàng đợi</span>'
        + (
            '<span><button type="button" class="mid-q-link" data-mid-queue-add>+ Thêm tệp</button>'
            '<button type="button" class="mid-q-link" data-mid-queue-clear>Xóa hết</button></span>'
            if removable else ""
        )
        + "</div>"
    )
    rows = []
    for i, (name, size, pages) in enumerate(items):
        ext = os.path.splitext(name)[1].lower()
        kind, color = _Q_TYPES.get(ext, (ext.lstrip(".").upper() or "Tệp", "#2B3990"))
        meta = [kind]
        if size is not None:
            meta.append(fmt_bytes(size))
        if pages:
            meta.append(f"{pages} trang")
        x = (
            f'<button type="button" class="mid-q-x" data-mid-queue-remove="{i}" aria-label="Xóa khỏi hàng đợi">×</button>'
            if removable else ""
        )
        rows.append(
            f'<div class="mid-q-item" style="--tc:{color}"><span class="mid-q-ico">{_Q_FILE_ICON}</span>'
            f'<div class="mid-q-main"><div class="mid-q-name" title="{html.escape(name, quote=True)}">{html.escape(name)}</div>'
            f'<div class="mid-q-meta">{html.escape(" · ".join(meta))}</div></div>{x}</div>'
        )
    return f'<div class="mid-queue">{head}{"".join(rows)}</div>'


# ---------------------------------------------------------------------- bảng trạng thái có cấu trúc (G1.4)
_IDLE_ICON = (
    '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
)
_CHECK_ICON = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" '
    'stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
)

_CHIP = {
    "queued": ("running", "Đang chờ"),
    "running": ("running", "Đang xử lý…"),
    "error": ("error", "Có lỗi"),
    "cancelled": ("stopped", "Đã dừng"),
}


def idle_html(message=None):
    """Trạng thái rỗng: biểu tượng + hướng dẫn. `message` (tùy chọn) hiện thêm một dòng thông báo."""
    note = f'<div class="mid-st-msg">{html.escape(message)}</div>' if message else ""
    return (
        '<div class="mid-st mid-st-idle">'
        '<div class="mid-st-head"><span class="mid-chip mid-chip-idle"><i class="mid-dot"></i>Chưa chạy</span></div>'
        f'<div class="mid-idle-ico">{_IDLE_ICON}</div>'
        '<div class="mid-idle-title">Kết quả Markdown sẽ hiện ở đây</div>'
        '<div class="mid-idle-text">Chọn tệp hoặc dán URL bên trái, chọn chế độ xử lý rồi bấm <b>Chuyển đổi</b>.</div>'
        f"{note}</div>"
    )


def message_html(text, kind="info"):
    """Một thông báo ngắn (văn bản thuần, đã escape; xuống dòng giữ nguyên)."""
    body = html.escape(text or "").replace("`", "").replace("\n", "<br>")
    return f'<div class="mid-st mid-st-note mid-st-{html.escape(kind)}"><div class="mid-st-msg">{body}</div></div>'


def _file_fraction(f, opts):
    """Phần hoàn thành (0..1) của một tệp đang chạy. Có dịch riêng -> OCR chiếm 70%, dịch 30%."""
    separate_tr = bool(opts.get("translate_vn")) and not opts.get("merge")
    ocr_w = 0.7 if separate_tr else 1.0
    pt, ct = f.get("pages_total") or 0, f.get("chunks_total") or 0
    ocr = (f.get("pages_done", 0) / pt) if pt else 0.0
    if f.get("stage") == "translate":
        tr = (f.get("chunks_done", 0) / ct) if ct else 0.0
        return ocr_w + (1 - ocr_w) * tr
    if f.get("stage") == "publish":
        return 0.97
    return ocr_w * ocr


def progress_percent(job):
    files = job["files"]
    if not files:
        return 0
    total = 0.0
    for f in files:
        if f["status"] == "done":
            total += 1
        elif f["status"] == "running":
            total += _file_fraction(f, job.get("options", {}))
    return int(round(100 * total / len(files)))


def _elapsed(job, now):
    start = job.get("started")
    if not start:
        return ""
    end = now if job["status"] in ACTIVE else (job.get("finished") or now)
    return f"{int(max(0, end - start))}s"


def _file_li(f, now):
    st = f["status"]
    name = html.escape(f["name"])
    tag = ""
    if st == "done":
        cls, ico = "is-done", _CHECK_ICON
        tag = "Xong"
        total = f.get("pages_total")
        detail = f"{total} trang" if total else "Hoàn tất"
        if f.get("pages_failed"):
            cls, tag, detail = "is-warn", f"{f['pages_failed']} trang lỗi", "Hoàn tất, có trang OCR lỗi"
    elif st == "running":
        cls, ico = "is-run", ""
        started = f.get("started") or now
        detail = f"{_stage_text(f)} · {int(now - started)}s"
        if f.get("stage") == "ocr" and f.get("pages_total"):
            tag = f"trang {f.get('pages_done', 0)}/{f['pages_total']}"
        elif f.get("stage") == "translate" and f.get("chunks_total"):
            tag = f"đoạn {f.get('chunks_done', 0)}/{f['chunks_total']}"
    elif st == "error":
        cls, ico, tag = "is-err", "!", "Lỗi"
        detail = html.escape(str(f.get("error") or "Lỗi không rõ"))
    elif st == "cancelled":
        cls, ico, tag = "is-stop", "■", "Đã dừng"
        detail = f"{f.get('pages_done', 0)}/{f.get('pages_total')} trang được giữ lại" if f.get("pages_total") else "đã dừng"
    else:
        cls, ico, tag, detail = "is-wait", "", "Chờ", "Đang chờ tới lượt"
    tag_html = f'<span class="mid-st-tag">{html.escape(tag)}</span>' if tag else ""
    return (
        f'<li class="mid-st-file {cls}"><span class="mid-st-ico">{ico}</span>'
        f'<div class="mid-st-main"><div class="mid-st-name">{name}</div><div class="mid-st-detail">{detail}</div></div>'
        f"{tag_html}</li>"
    )


def _is_chess(opts):
    import pipeline

    return pipeline._is_chess_mode(opts.get("mode_label", pipeline.MODE_CHESS))


def render_status_html(job, now=None):
    """Bảng trạng thái của công việc: chip, tiêu đề, thanh tiến độ, danh sách từng tệp, ghi chú xử lý."""
    now = now or time.time()
    files = job["files"]
    n = len(files)
    n_ok = sum(1 for f in files if f["status"] == "done")
    status = job["status"]
    opts = job.get("options", {})
    if status == "done":
        chip_cls, chip = "done", f"Xong {n_ok}/{n} tệp"
    else:
        chip_cls, chip = _CHIP.get(status, ("idle", status))
    running = status in ACTIVE
    pct = 100 if status == "done" else progress_percent(job)
    elapsed = _elapsed(job, now)
    parts = [f'<div class="mid-st" data-state="{html.escape(status)}">']
    parts.append(
        '<div class="mid-st-head">'
        f'<span class="mid-chip mid-chip-{chip_cls}"><i class="mid-dot"></i>{html.escape(chip)}</span>'
        + (f'<span class="mid-st-time">{elapsed}</span>' if elapsed else "")
        + "</div>"
    )
    if running:
        sub = "OCR bằng AI"
        if _is_chess(opts):
            sub += " · nhận diện sơ đồ cờ → FEN"
        if opts.get("translate_vn"):
            sub += " · dịch sang tiếng Việt"
        title = "Đang chờ tới lượt chạy…" if status == "queued" else f"Đang chuyển đổi {n} tệp"
        parts.append(f'<div class="mid-st-title">{title}</div><div class="mid-st-sub">{html.escape(sub)}</div>')
    elif status in ("cancelled", "error") and job.get("message"):
        parts.append(f'<div class="mid-st-sub">{html.escape(job["message"])}</div>')
    if running or pct:
        parts.append(
            f'<div class="mid-progress" role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100">'
            f'<span style="width:{pct}%"></span></div>'
        )
    parts.append('<ul class="mid-st-files">' + "".join(_file_li(f, now) for f in files) + "</ul>")
    k = failed_pages_total(job)
    if k and not running:
        parts.append(
            f'<div class="mid-st-warn">⚠️ {k} trang OCR bị lỗi (đã đánh dấu <code>*[Lỗi OCR trang N…]*</code> trong kết quả). '
            f"Bấm «{html.escape(resume_label(job))}» để chỉ làm lại các trang đó.</div>"
        )
    notes = []
    for f in files:
        lines = [x for x in f.get("notes", []) if x]
        if lines:
            notes.append(f["name"] + "\n  " + "\n  ".join(lines))
    if notes:
        body = html.escape("\n\n".join(notes))
        parts.append(f'<details class="mid-st-notes"><summary>Chi tiết xử lý</summary><pre>{body}</pre></details>')
    parts.append("</div>")
    return "".join(parts)
