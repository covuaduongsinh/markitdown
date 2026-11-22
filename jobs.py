# -*- coding: utf-8 -*-
"""
Công việc nền lưu đĩa cho chuyển đổi sách dài: chạy tiếp được, dừng thật, không mất kết quả khi rớt kết nối.

Bố cục thư mục (MID_DATA_DIR, mặc định <tmp>/markitdown_gui_data):

    jobs/<job_id>/
        job.json                 trạng thái, tùy chọn, tiến độ từng tệp (ghi nguyên tử: ghi tệp tạm rồi os.replace)
        src/f01/<tên gốc>        bản sao tệp nguồn (để chạy tiếp được)
        f01/pages/0007.md        kết quả OCR từng trang (0007.err nếu lỗi)
        f01/tr/<sha1>.md         kết quả dịch từng đoạn (điểm lưu khi dịch riêng)
        f01/out/                 <tên>.md, <tên>_vn.md, <tên>_fen.txt
        f01/raw.md               văn bản kết quả (cho xem trước / mở lại từ lịch sử)
        ketqua.zip               gộp mọi tệp kết quả

`job_id` là chuỗi ngẫu nhiên (không lấy từ tên tệp người dùng). `job.json` KHÔNG lưu khóa/token: chúng chỉ nằm trong RAM
lúc công việc chạy; "Chạy tiếp" phải truyền lại.

Trạng thái công việc: queued -> running -> done | error | cancelled. Tệp trong công việc: pending -> running -> done | error | cancelled.
"""

import copy
import json
import os
import queue
import re
import secrets as _secrets
import shutil
import tempfile
import threading
import time
import traceback

import obsidian
import pipeline
from proc_control import CancelToken, OperationCancelled, use_token

QUEUED, RUNNING, DONE, ERROR, CANCELLED = "queued", "running", "done", "error", "cancelled"
ACTIVE = (QUEUED, RUNNING)

_PAGE_FILE_RE = re.compile(r"^(\d{4,})\.md$")


def _now():
    return time.time()


def _atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{_secrets.token_hex(4)}.tmp"
    # newline="\n": cùng một nội dung trên mọi hệ điều hành (Windows không đổi \n thành \r\n trong tệp kết quả/điểm lưu)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


class DiskChunkCache:
    """Điểm lưu bản dịch theo đoạn: mỗi đoạn một tệp <sha1>.md (dùng cho translate_markdown_vn(chunk_cache=...))."""

    def __init__(self, directory):
        self.dir = directory

    def get(self, key):
        text = _read(os.path.join(self.dir, f"{key}.md"))
        return text or None

    def put(self, key, text):
        _atomic_write(os.path.join(self.dir, f"{key}.md"), text)


def default_options():
    """Tùy chọn mặc định của một công việc (UI ghi đè từng khóa). Không chứa khóa/token."""
    return dict(
        mode_label=pipeline.MODE_CHESS, use_ocr=True, force_ocr=True,
        ocr_model="gemini-3.8-flash", ocr_effort="auto", board_dpi="250", ocr_pages_per_call="1",
        translate_vn=True, merge=False, translate_model="gemini-3.8-flash", translate_effort="low",
        page_spec="", engine="antigravity",
        autosave_on=False, autosave_dir="", autosave_target=pipeline.AUTOSAVE_CUSTOM, sources_are_real=False,
        auto_download_on=False, dropbox_sync_on=False, dropbox_folder="/MarkItDown",
        obsidian_frontmatter=False, obsidian_split=False,
    )


class JobManager:
    def __init__(self, root, max_jobs=1, keep_days=60):
        self.root = root
        self.jobs_dir = os.path.join(root, "jobs")
        os.makedirs(self.jobs_dir, exist_ok=True)
        self.max_jobs = max(1, int(max_jobs))
        self.keep_days = int(keep_days)
        self._lock = threading.RLock()
        self._jobs = {}
        self._creds = {}    # job_id -> khóa/token (chỉ trong RAM)
        self._tokens = {}   # job_id -> CancelToken
        self._queue = queue.Queue()
        self._workers = []
        self._last_save = {}
        self._load_all()

    # ------------------------------------------------------------------ đường dẫn / lưu trữ
    def job_dir(self, job_id):
        return os.path.join(self.jobs_dir, job_id)

    def file_dir(self, job_id, idx):
        return os.path.join(self.job_dir(job_id), f"f{idx + 1:02d}")

    def abs_path(self, job_id, rel):
        """Đường dẫn tuyệt đối của một tệp kết quả (rel tính từ thư mục công việc); chặn thoát khỏi thư mục đó."""
        base = os.path.realpath(self.job_dir(job_id))
        path = os.path.realpath(os.path.join(base, rel))
        if os.path.commonpath([base, path]) != base:
            raise ValueError("Đường dẫn ngoài thư mục công việc.")
        return path

    def _save(self, job, force=True):
        """Ghi job.json. force=False: chỉ ghi nếu đã ≥1 giây từ lần trước (cập nhật tiến độ dày)."""
        now = _now()
        if not force and now - self._last_save.get(job["id"], 0) < 1.0:
            return
        self._last_save[job["id"]] = now
        job["updated"] = now
        _atomic_write(os.path.join(self.job_dir(job["id"]), "job.json"), json.dumps(job, ensure_ascii=False, indent=1))

    def _load_all(self):
        for name in os.listdir(self.jobs_dir):
            raw = _read(os.path.join(self.jobs_dir, name, "job.json"))
            if not raw:
                continue
            try:
                job = json.loads(raw)
            except ValueError:
                continue
            if job.get("status") in ACTIVE:  # app khởi động lại giữa chừng
                job["status"] = ERROR
                job["message"] = "Ứng dụng khởi động lại giữa chừng — bấm «Chạy tiếp» để làm nốt phần còn lại."
                for f in job.get("files", []):
                    if f.get("status") in ("running", "pending"):
                        f["status"] = "cancelled"
                _atomic_write(os.path.join(self.job_dir(name), "job.json"), json.dumps(job, ensure_ascii=False, indent=1))
            self._jobs[job["id"]] = job

    # ------------------------------------------------------------------ tạo / hỏi
    def submit(self, files, options=None, creds=None):
        """Tạo công việc và xếp hàng. files: list {"path": nguồn, "name": tên hiển thị, "orig_path": đường dẫn thật hoặc None}.

        Trả job_id. Tệp nguồn được sao vào thư mục công việc để chạy tiếp được dù tệp tạm của Gradio bị dọn.
        """
        job_id = _secrets.token_urlsafe(9)
        opts = default_options()
        opts.update(options or {})
        entries = []
        for i, f in enumerate(files):
            name = pipeline._safe_filename(f.get("name") or os.path.basename(f["path"]))
            if os.path.splitext(name)[1] == "" and os.path.splitext(f["path"])[1]:
                name += os.path.splitext(f["path"])[1]
            src_rel = os.path.join("src", f"f{i + 1:02d}", name)
            dest = os.path.join(self.job_dir(job_id), src_rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(f["path"], dest)
            entries.append(dict(
                idx=i, name=name, src=src_rel, orig_path=f.get("orig_path"), size=os.path.getsize(dest),
                status="pending", stage="", pages_total=0, pages_done=0, pages_failed=0,
                chunks_total=0, chunks_done=0, started=None, finished=None, error=None,
                outputs=[], notes=[],
            ))
        job = dict(
            id=job_id, created=_now(), updated=_now(), started=None, finished=None,
            status=QUEUED, message="", options=opts, files=entries,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._creds[job_id] = dict(creds or {})
            self._save(job)
        self._enqueue(job_id)
        return job_id

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list_jobs(self):
        """Tóm tắt mọi công việc, mới nhất trước."""
        with self._lock:
            rows = []
            for job in self._jobs.values():
                files = job["files"]
                rows.append(dict(
                    id=job["id"], created=job["created"], status=job["status"], message=job.get("message", ""),
                    names=[f["name"] for f in files],
                    n_files=len(files), n_done=sum(1 for f in files if f["status"] == "done"),
                    failed_pages=sum(f.get("pages_failed", 0) for f in files),
                ))
        rows.sort(key=lambda r: r["created"], reverse=True)
        return rows

    def active_job_ids(self):
        with self._lock:
            return [j for j, job in self._jobs.items() if job["status"] in ACTIVE]

    def is_resumable(self, job):
        """Có việc còn dang dở hoặc trang lỗi để làm lại không."""
        if not job or job["status"] in ACTIVE:
            return False
        return any(f["status"] != "done" or f.get("pages_failed", 0) for f in job["files"])

    # ------------------------------------------------------------------ điều khiển
    def cancel(self, job_id):
        """Dừng công việc: đang chạy -> diệt tiến trình AI; đang chờ -> hủy luôn. Trả True nếu có tác dụng."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] not in ACTIVE:
                return False
            token = self._tokens.get(job_id)
            if job["status"] == QUEUED:
                job["status"] = CANCELLED
                job["message"] = "Đã hủy khi đang chờ."
                job["finished"] = _now()
                for f in job["files"]:
                    if f["status"] == "pending":
                        f["status"] = "cancelled"
                self._save(job)
                return True
        if token is not None:
            token.cancel()
        return True

    def resume(self, job_id, creds=None):
        """Chạy tiếp: làm các tệp chưa xong, và làm lại các trang lỗi. Trang đã có điểm lưu không gọi AI lại."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not self.is_resumable(job):
                return False
            for f in job["files"]:
                if f["status"] != "done" or f.get("pages_failed", 0):
                    f["status"] = "pending"
                    f["error"] = None
            job["status"] = QUEUED
            job["message"] = ""
            job["finished"] = None
            self._creds[job_id] = dict(creds or {})
            self._save(job)
        self._enqueue(job_id)
        return True

    def clone(self, job_id, creds=None):
        """Tạo công việc MỚI từ cùng tệp nguồn và tùy chọn của một công việc cũ ("Chạy lại"). Trả job_id mới hoặc None."""
        job = self.get(job_id)
        if not job:
            return None
        files = [
            {"path": os.path.join(self.job_dir(job_id), f["src"]), "name": f["name"], "orig_path": f.get("orig_path")}
            for f in job["files"]
        ]
        return self.submit(files, job["options"], creds)

    def delete(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] in ACTIVE:
                return False
            del self._jobs[job_id]
            self._last_save.pop(job_id, None)
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
        return True

    def cleanup_old(self, now=None):
        """Xóa công việc không còn chạy và cũ hơn keep_days ngày. Trả số công việc đã xóa."""
        if self.keep_days <= 0:
            return 0
        limit = (now or _now()) - self.keep_days * 86400
        with self._lock:
            old = [j for j, job in self._jobs.items() if job["status"] not in ACTIVE and job["updated"] < limit]
        return sum(1 for j in old if self.delete(j))

    def disk_usage(self):
        """Tổng dung lượng (byte) các công việc."""
        total = 0
        for base, _dirs, names in os.walk(self.jobs_dir):
            for n in names:
                try:
                    total += os.path.getsize(os.path.join(base, n))
                except OSError:
                    pass
        return total

    def start_background_cleanup(self, interval_s=86400):
        """Dọn ngay một lần rồi lặp lại mỗi interval_s giây (luồng nền, daemon)."""
        def loop():
            while True:
                try:
                    self.cleanup_old()
                except Exception:
                    traceback.print_exc()
                time.sleep(interval_s)

        t = threading.Thread(target=loop, name="mid-cleanup", daemon=True)
        t.start()
        return t

    def wait(self, job_id, timeout=60):
        """Chờ công việc xong (dùng cho test)."""
        end = time.time() + timeout
        while time.time() < end:
            job = self.get(job_id)
            if job and job["status"] not in ACTIVE:
                return job
            time.sleep(0.05)
        return self.get(job_id)

    # ------------------------------------------------------------------ hàng đợi / luồng chạy
    def _enqueue(self, job_id):
        self._queue.put(job_id)
        with self._lock:
            self._workers = [w for w in self._workers if w.is_alive()]
            while len(self._workers) < self.max_jobs:
                w = threading.Thread(target=self._worker, name="mid-job-worker", daemon=True)
                w.start()
                self._workers.append(w)

    def _worker(self):
        while True:
            try:
                job_id = self._queue.get(timeout=30)
            except queue.Empty:
                return  # luồng nghỉ; _enqueue tự mở lại khi có việc
            try:
                self._run(job_id)
            except Exception:
                traceback.print_exc()

    def _upd(self, job, entry=None, force=False, **kw):
        with self._lock:
            (entry if entry is not None else job).update(kw)
            self._save(job, force=force)

    def _run(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != QUEUED:
                return
            token = CancelToken()
            self._tokens[job_id] = token
            creds = self._creds.get(job_id, {})
            job["status"] = RUNNING
            job["started"] = job["started"] or _now()
            job["message"] = ""
            self._save(job)
        status, message = DONE, ""
        try:
            with use_token(token):
                for entry in job["files"]:
                    if entry["status"] == "done":
                        continue
                    token.raise_if_cancelled()
                    self._process_file(job, entry, creds, token)
            if job["files"] and all(f["status"] == "error" for f in job["files"]):
                status = ERROR
        except OperationCancelled:
            status, message = CANCELLED, "Đã dừng. Các trang đã xong được giữ lại — bấm «Chạy tiếp» để làm nốt."
            for f in job["files"]:
                if f["status"] in ("running", "pending"):
                    f["status"] = "cancelled"
        except Exception as exc:
            traceback.print_exc()
            status, message = ERROR, f"Lỗi không mong muốn: {type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                self._tokens.pop(job_id, None)
                self._creds.pop(job_id, None)  # khóa/token không nằm lại trong RAM sau khi xong
                job["status"], job["message"], job["finished"] = status, message, _now()
                self._save(job)

    # ------------------------------------------------------------------ xử lý một tệp
    def _write_zip(self, job):
        paths = []
        for f in job["files"]:
            for o in f["outputs"]:
                p = os.path.join(self.job_dir(job["id"]), o["rel"])
                if os.path.exists(p):
                    paths.append(p)
        extra = self._chapter_files(job)
        if len(paths) >= 2 or extra:
            pipeline._zip_all(paths, zip_path=os.path.join(self.job_dir(job["id"]), "ketqua.zip"), extra=extra)

    def _chapter_files(self, job):
        """[(đường dẫn, tên trong zip)] của các tệp chương Obsidian: <tên sách>/<NN-chương>.md."""
        extra = []
        for f in job["files"]:
            cdir = os.path.join(self.file_dir(job["id"], f["idx"]), "out", "chapters")
            if not os.path.isdir(cdir):
                continue
            stem = os.path.splitext(f["name"])[0]
            for name in sorted(os.listdir(cdir)):
                extra.append((os.path.join(cdir, name), f"{stem}/{name}"))
        return extra

    def apply_obsidian(self, job, entry, outputs):
        """Xuất cho Obsidian theo tùy chọn của công việc: thêm frontmatter YAML vào các tệp .md/_vn.md và/hoặc tách tệp văn bản
        cuối (vn nếu có, không thì md) theo tiêu đề `#` thành các tệp chương trong out/chapters/ (chỉ đi vào zip).
        outputs: [(đường dẫn, loại)]. Chạy lại nhiều lần được (frontmatter cũ bị thay, thư mục chương được tạo lại).
        Trả số chương đã ghi."""
        opts = job["options"]
        want_fm, want_split = bool(opts.get("obsidian_frontmatter")), bool(opts.get("obsidian_split"))
        fdir = self.file_dir(job["id"], entry["idx"])
        cdir = os.path.join(fdir, "out", "chapters")
        shutil.rmtree(cdir, ignore_errors=True)
        if not (want_fm or want_split):
            return 0
        texts = [(p, k) for p, k in outputs if k in ("md", "vn")]
        if not texts:
            return 0
        final_path = next((p for p, k in texts if k == "vn"), texts[0][0])
        final_body = obsidian.strip_frontmatter(_read(final_path))
        book = obsidian.first_title(final_body, os.path.splitext(entry["name"])[0])
        meta = dict(
            source=entry["name"], date=time.strftime("%Y-%m-%d"), engine=opts.get("engine"),
            model=opts.get("ocr_model"), pages=entry.get("pages_total") or None,
        )
        if want_fm:
            for path, kind in texts:
                m = {"title": book, **meta}
                if kind == "vn":
                    m["translated"] = True
                    if opts.get("translate_model") and not opts.get("merge"):
                        m["translate_model"] = opts["translate_model"]
                _atomic_write(path, obsidian.with_frontmatter(_read(path), m))
        n = 0
        if want_split:
            book_meta = ({"book": book, **meta} if want_fm else None)
            for name, body in obsidian.chapters(final_body, book_meta):
                _atomic_write(os.path.join(cdir, name), body)
                n += 1
        return n

    def rebuild_obsidian(self, job_id, file_idx):
        """Làm lại frontmatter/chương sau khi văn bản kết quả đổi (vd hiệu đính FEN). Không làm gì nếu tùy chọn Obsidian tắt."""
        job = self.get(job_id)
        if not job:
            return 0
        entry = next((f for f in job["files"] if f["idx"] == file_idx), None)
        if not entry:
            return 0
        outputs = [(os.path.join(self.job_dir(job_id), o["rel"]), o["kind"]) for o in entry.get("outputs", [])]
        n = self.apply_obsidian(job, entry, outputs)
        self._write_zip(job)
        return n

    @staticmethod
    def _load_done_pages(pages_dir, target):
        done = {}
        try:
            names = os.listdir(pages_dir)
        except OSError:
            return done
        for n in names:
            m = _PAGE_FILE_RE.match(n)
            if not m:
                continue
            p = int(m.group(1))
            if target is None or p in target:
                text = _read(os.path.join(pages_dir, n))
                if text.strip():
                    done[p] = text
        return done

    @staticmethod
    def _count_failed_pages(pages_dir, target):
        try:
            names = os.listdir(pages_dir)
        except OSError:
            return 0
        n = 0
        for name in names:
            if name.endswith(".err"):
                p = int(name[:-4])
                if (target is None or p in target) and not os.path.exists(os.path.join(pages_dir, f"{p:04d}.md")):
                    n += 1
        return n

    def _process_file(self, job, entry, creds, token):
        job_id, opts = job["id"], job["options"]
        fdir = self.file_dir(job_id, entry["idx"])
        out_dir, pages_dir, tr_dir = (os.path.join(fdir, d) for d in ("out", "pages", "tr"))
        src = os.path.join(self.job_dir(job_id), entry["src"])
        ext = os.path.splitext(src)[1].lower()
        chess = pipeline._is_chess_mode(opts["mode_label"])
        chess_lang = pipeline._chess_lang_from_mode(opts["mode_label"])
        merge = bool(opts["merge"] and opts["translate_vn"])
        self._upd(
            job, entry, force=True, status="running", stage="convert", error=None, notes=[], outputs=[],
            started=_now(), finished=None, pages_done=0, pages_failed=0, chunks_done=0, chunks_total=0,
        )

        ocr_kwargs, target = None, None
        if ext == ".pdf" and opts["use_ocr"]:
            n_pages = pipeline.count_pdf_pages(src)
            try:
                target = pipeline.parse_page_ranges(opts["page_spec"], n_pages) if n_pages else None
            except ValueError as exc:
                self._upd(job, entry, force=True, status="error", stage="", error=f"⚠️ {exc}", finished=_now())
                return

            def on_page(page_no, text, err):
                base = os.path.join(pages_dir, f"{page_no:04d}")
                if text is not None:
                    _atomic_write(base + ".md", text)
                    if os.path.exists(base + ".err"):
                        os.remove(base + ".err")
                else:
                    _atomic_write(base + ".err", err or "lỗi")
                    if os.path.exists(base + ".md"):
                        os.remove(base + ".md")

            ocr_kwargs = dict(
                pages=target, done_pages=self._load_done_pages(pages_dir, target), on_page=on_page, cancel=token,
            )

        def on_ocr_progress(i, n):
            self._upd(job, entry, stage="ocr", pages_done=i, pages_total=n)

        def on_tr_progress(i, n):
            self._upd(job, entry, stage="translate", chunks_done=i, chunks_total=n)

        reset = pipeline._OUT_DIR_OVERRIDE.set(out_dir)
        try:
            res = pipeline.convert_file(
                src, False, opts["use_ocr"], opts["ocr_model"], force_ocr=opts["force_ocr"],
                board_dpi_label=str(opts["board_dpi"]), used_paths=[], chess=chess, progress=on_ocr_progress,
                chess_lang=chess_lang, ocr_effort_label=opts["ocr_effort"], merge_translate=merge,
                ocr_pages_label=f"{opts['ocr_pages_per_call']} trang/lần", engine=opts["engine"],
                api_key=creds.get("api_key") or None, claude_token=creds.get("claude_token") or None,
                agy_token=creds.get("agy_token") or None, ocr_pdf_kwargs=ocr_kwargs,
            )
            outputs = []  # (đường dẫn, loại)
            notes = [res.status] if res.status else []
            if not res.path:
                self._upd(
                    job, entry, force=True, status="error", stage="", error=res.status or "Không có kết quả.",
                    notes=notes, finished=_now(), pages_failed=self._count_failed_pages(pages_dir, target),
                )
                return
            outputs.append((res.path, "vn" if res.translated else "md"))
            _atomic_write(os.path.join(fdir, "raw.md"), res.raw_md or "")

            if opts["translate_vn"] and not res.translated and (res.raw_md or "").strip():
                self._upd(job, entry, force=True, stage="translate")
                vn_path, vn_status = pipeline._translate_to_vn(
                    res.raw_md, entry["name"], pipeline._model_from_label(opts["translate_model"]), [res.path],
                    chess=chess, progress=on_tr_progress, chess_lang=chess_lang,
                    effort=pipeline._effort_from_label(opts["translate_effort"], default="low"),
                    engine=opts["engine"], api_key=creds.get("api_key") or None,
                    claude_token=creds.get("claude_token") or None, agy_token=creds.get("agy_token") or None,
                    translate_kwargs=dict(chunk_cache=DiskChunkCache(tr_dir), cancel=token),
                )
                notes.append(vn_status)
                if vn_path:
                    outputs.append((vn_path, "vn"))

            if chess and (res.raw_md or "").strip():
                fen_path, n_fen = pipeline._write_fen_file(
                    res.raw_md, os.path.splitext(entry["name"])[0], [p for p, _k in outputs],
                )
                if fen_path:
                    notes.append(f"♟️ Đã gom {n_fen} thế cờ → `{os.path.basename(fen_path)}`")
                    outputs.append((fen_path, "fen"))

            n_chapters = self.apply_obsidian(job, entry, outputs)
            if opts.get("obsidian_frontmatter"):
                notes.append("📚 Obsidian: đã thêm frontmatter YAML vào các tệp .md")
            if opts.get("obsidian_split"):
                notes.append(
                    f"📚 Obsidian: tách {n_chapters} chương vào .zip (thư mục `{os.path.splitext(entry['name'])[0]}/`)"
                    if n_chapters else "📚 Obsidian: không có tiêu đề `#` nào để tách chương"
                )
            self._upd(job, entry, force=True, stage="publish")
            save_dir, save_note = pipeline._resolve_save_dir(
                entry.get("orig_path") or src, opts["autosave_target"], opts["autosave_dir"], opts["sources_are_real"],
            )
            cfg = dict(
                folder=opts["dropbox_folder"], token=creds.get("dropbox_token", ""),
                refresh_token=creds.get("dropbox_refresh_token", ""),
                app_key=creds.get("dropbox_app_key", ""), app_secret=creds.get("dropbox_app_secret", ""),
            )
            out_entries = []
            for k, (path, kind) in enumerate(outputs):
                notes.append(f"`{os.path.basename(path)}`" + pipeline._publish_output(
                    path, save_dir, save_note=save_note if k == 0 else "", dropbox_cfg=cfg, inline=k > 0,
                    autosave_on=opts["autosave_on"], dropbox_sync_on=opts["dropbox_sync_on"],
                    auto_download_on=opts["auto_download_on"],
                ))
                out_entries.append(dict(name=os.path.basename(path), rel=os.path.relpath(path, self.job_dir(job_id)), kind=kind))
            self._upd(
                job, entry, force=True, status="done", stage="", outputs=out_entries, notes=notes, finished=_now(),
                pages_failed=self._count_failed_pages(pages_dir, target),
            )
            self._write_zip(job)
        except OperationCancelled:
            self._upd(job, entry, force=True, status="cancelled", stage="")
            raise
        except Exception as exc:
            traceback.print_exc()
            self._upd(job, entry, force=True, status="error", stage="", error=f"❌ Lỗi xử lý {entry['name']}: {type(exc).__name__}: {exc}", finished=_now())
        finally:
            pipeline._OUT_DIR_OVERRIDE.reset(reset)


# ---------------------------------------------------------------------- bản dùng chung của ứng dụng
_MANAGER = None
_MANAGER_LOCK = threading.Lock()


def data_dir():
    return os.environ.get("MID_DATA_DIR") or os.path.join(tempfile.gettempdir(), "markitdown_gui_data")


def get_manager():
    """JobManager dùng chung (tạo ở lần gọi đầu; đọc MID_DATA_DIR, MID_MAX_JOBS, MID_KEEP_DAYS)."""
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = JobManager(
                data_dir(),
                max_jobs=int(os.environ.get("MID_MAX_JOBS", "1") or 1),
                keep_days=int(os.environ.get("MID_KEEP_DAYS", "60") or 60),
            )
            _MANAGER.start_background_cleanup()
        return _MANAGER
