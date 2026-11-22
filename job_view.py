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


def render_status_md(job, now=None):
    """Khối Markdown trạng thái của công việc (cùng phong cách dòng trạng thái cũ)."""
    now = now or time.time()
    files = job["files"]
    n = len(files)
    n_ok = sum(1 for f in files if f["status"] == "done")
    status = job["status"]
    lines = []
    if status == "done":
        lines.append(f"🏁 Xong {n_ok}/{n} tệp.")
    elif status == "cancelled":
        lines.append(f"⏹ {job.get('message') or 'Đã dừng.'}")
    elif status == "error":
        lines.append(f"❌ {job.get('message') or 'Không có tệp nào chuyển đổi được.'}")
    elif status == "queued":
        lines.append("⌛ Đang chờ tới lượt chạy…")
    for i, f in enumerate(files, 1):
        name = f["name"]
        st = f["status"]
        if st == "done":
            body = "\n  ".join(x for x in f.get("notes", []) if x)
            lines.append(f"**{name}** — {body}" if body else f"**{name}** — ✅ xong")
        elif st == "running":
            started = f.get("started") or now
            lines.append(f"⏳ Đang xử lý {i}/{n}: **{name}** — {_stage_text(f)} · {int(now - started)}s…")
        elif st == "error":
            lines.append(f"**{name}** — {f.get('error') or '❌ lỗi'}")
        elif st == "cancelled":
            kept = f.get("pages_done", 0)
            tail = f" ({kept}/{f.get('pages_total')} trang đã được giữ lại)" if f.get("pages_total") else ""
            lines.append(f"⏹ **{name}** — đã dừng{tail}")
        else:
            lines.append(f"⌛ Chờ: **{name}**")
    k = failed_pages_total(job)
    if k and status not in ACTIVE:
        lines.append(
            f"⚠️ {k} trang OCR bị lỗi (đã đánh dấu `*[Lỗi OCR trang N…]*` trong kết quả). "
            f"Bấm «{resume_label(job)}» để chỉ làm lại các trang đó."
        )
    return "\n\n".join(lines)


def signature(job):
    """Chuỗi thay đổi khi có tệp mới xong/đổi trạng thái -> lúc đó mới gửi lại phần xem trước và danh sách tải."""
    parts = [job["id"], job["status"]]
    for f in job["files"]:
        parts.append(f"{f['status']}:{len(f.get('outputs', []))}:{f.get('pages_failed', 0)}")
    return "|".join(parts)


def collect_previews(job, read_raw):
    """(preview_md, raw_md) ghép từ các tệp đã xong. read_raw(job, file_entry) -> văn bản."""
    previews, raws = [], []
    for f in job["files"]:
        if f["status"] != "done":
            continue
        text = read_raw(job, f)
        if not text.strip():
            continue
        previews.append(f"## 📄 {f['name']}\n\n{text}")
        raws.append(text)
    return "\n\n---\n\n".join(previews), "\n\n".join(raws)


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
