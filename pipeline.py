# -*- coding: utf-8 -*-
"""
Lõi chuyển đổi của ứng dụng web (không phụ thuộc Gradio): ghi tệp kết quả, chuyển đổi
tệp/URL, OCR qua AI Engine, dịch sang tiếng Việt, tự lưu/đồng bộ Dropbox.

`markitdown_gui.py` chỉ còn giao diện và các handler; mọi thứ ở đây gọi được từ test
mà không cần dựng giao diện.
"""

import os
import re
import shutil
import tempfile
import traceback
import zipfile
import contextvars
from typing import NamedTuple

from markitdown import MarkItDown

from ai_engine import ENGINE_ANTIGRAVITY, is_engine_available
import infrastructure

# Thư mục tạm để chứa các tệp .md xuất ra (cho nút tải về)
_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "markitdown_gui_output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)

# Công việc nền (jobs.py) đặt thư mục xuất riêng cho từng tệp; không đặt thì dùng _OUTPUT_DIR như trước.
_OUT_DIR_OVERRIDE = contextvars.ContextVar("mid_out_dir", default=None)


def _out_dir():
    d = _OUT_DIR_OVERRIDE.get()
    if d:
        os.makedirs(d, exist_ok=True)
        return d
    return _OUTPUT_DIR


def _safe_filename(name: str) -> str:
    """Bỏ ký tự không hợp lệ trong tên tệp Windows."""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", name).strip().strip(".")
    return name or "ketqua"


def _write_md(markdown: str, base_name: str, used_paths=None) -> str:
    """Ghi nội dung Markdown ra tệp .md trong thư mục tạm, trả về đường dẫn.

    `used_paths`: các đường dẫn đã xuất trong cùng lô — nếu trùng thì
    thêm hậu tố _2, _3... để không ghi đè kết quả của tệp trước.
    """
    out_path = os.path.join(_out_dir(), _safe_filename(base_name) + ".md")
    if used_paths:
        root, ext = os.path.splitext(out_path)
        n = 2
        while out_path in used_paths:
            out_path = f"{root}_{n}{ext}"
            n += 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return out_path


def _write_fen_file(md, base_name, used_paths=None):
    """Trích FEN từ md, ghi tệp <base>_fen.txt (1 FEN mỗi dòng).

    Trả về (đường dẫn, số FEN) hoặc (None, 0) nếu md không có thế cờ nào.
    Dedup hậu tố _2, _3... như `_write_md` để không ghi đè kết quả tệp trước.
    """
    import claude_ocr

    fens = claude_ocr.extract_fens(md)
    if not fens:
        return None, 0
    out_path = os.path.join(_out_dir(), _safe_filename(base_name) + "_fen.txt")
    if used_paths:
        root, ext = os.path.splitext(out_path)
        n = 2
        while out_path in used_paths:
            out_path = f"{root}_{n}{ext}"
            n += 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(fens) + "\n")
    return out_path, len(fens)


def _zip_all(paths, zip_path=None, extra=()):
    """Gộp các tệp .md kết quả vào 1 zip cố định trong _OUTPUT_DIR, trả về đường dẫn.

    Dùng tên cố định để mỗi lần gọi ghi đè (không tích lũy zip cũ). Dedup tên
    trùng bên trong archive (a.md, a_2.md...) để không mất tệp khi nhiều nguồn
    cùng tên gốc.
    """
    zip_path = zip_path or os.path.join(_out_dir(), "markitdown_ketqua.zip")
    used = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if not os.path.exists(p):
                continue
            arc = os.path.basename(p)
            root, ext = os.path.splitext(arc)
            n = 2
            while arc in used:
                arc = f"{root}_{n}{ext}"
                n += 1
            used.add(arc)
            zf.write(p, arcname=arc)
        for p, arc in extra:  # tệp kèm theo có sẵn đường dẫn trong zip (vd thư mục chương cho Obsidian)
            if os.path.exists(p):
                zf.write(p, arcname=arc)
    return zip_path


def _autosave(path, folder):
    """Copy tệp .md vào thư mục người dùng chọn ngay khi xong.

    Không ghi đè tệp có sẵn (thêm hậu tố _2, _3...).
    Trả về (đường dẫn đích, None) hoặc (None, thông báo lỗi).
    """
    folder = (folder or "").strip()
    if not folder:
        return None, "⚠️ Chưa nhập thư mục lưu kết quả."
    try:
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, os.path.basename(path))
        root, ext = os.path.splitext(dest)
        n = 2
        while os.path.exists(dest):
            dest = f"{root}_{n}{ext}"
            n += 1
        shutil.copy2(path, dest)
        return dest, None
    except OSError as exc:
        return None, f"⚠️ Không lưu được vào thư mục: {exc}"


def _resolve_save_dir(fp, target, custom_dir, sources_are_real):
    """Tính thư mục đích để tự động lưu tệp .md của một tệp nguồn `fp`.

    Trả về (thư mục đích, ghi chú). 'Cùng thư mục với file gốc' chỉ dùng được khi
    `fp` là đường dẫn thật (chọn bằng hộp thoại); tệp kéo-thả không có đường dẫn
    gốc nên lùi về `custom_dir` kèm ghi chú.
    """
    if target == AUTOSAVE_SRC and sources_are_real:
        return os.path.dirname(os.path.abspath(fp)), ""
    if target == AUTOSAVE_SRC:  # kéo-thả: không có đường dẫn gốc
        return custom_dir, " (kéo-thả → dùng thư mục tùy chọn)"
    return custom_dir, ""


def _publish_output(
    path, save_dir, *, autosave_on=False, dropbox_sync_on=False, auto_download_on=False,
    dropbox_cfg=None, save_note="", inline=False,
):
    """Đưa một tệp kết quả ra các đích: thư mục tự lưu, Dropbox, tải về máy.

    Trả về chuỗi ghi chú để nối vào dòng trạng thái của tệp nguồn. `inline=True` dùng cho tệp phụ
    (`_vn.md`, `_fen.txt`): ghi chú nối cùng dòng bằng " · " thay vì xuống dòng. `dropbox_cfg` là dict
    các khóa folder, token, refresh_token, app_key, app_secret. `save_note` chỉ dùng ở kiểu không inline.
    """
    cfg = dropbox_cfg or {}
    name = os.path.basename(path)
    note = ""
    sep = " · " if inline else "\n  "
    if autosave_on:
        saved, err = _autosave(path, save_dir)
        if saved:
            note += f"{sep}💾 [VPS] đã lưu: `{saved}`" + ("" if inline else save_note)
        else:
            note += f"\n  {err}"
    if dropbox_sync_on:
        dbx_path, dbx_err = infrastructure.upload_to_dropbox(
            path, target_folder=cfg.get("folder", "/MarkItDown"),
            token=cfg.get("token", ""), refresh_token=cfg.get("refresh_token", ""),
            app_key=cfg.get("app_key", ""), app_secret=cfg.get("app_secret", ""),
        )
        if dbx_path:
            note += f"{sep}☁️ [Dropbox] " + (f"`{dbx_path}`" if inline else f"đã lưu: `{dbx_path}`")
        elif dbx_err:
            note += f"\n  ⚠️ [Dropbox] {dbx_err}"
    if auto_download_on:
        note += f"{sep}⚡ [Máy tính] Đang tải `{name}`" + ("" if inline else " về máy...")
    return note


def _convert(source, enable_plugins, base_name, used_paths=None):
    """Lõi chuyển đổi dùng chung cho cả tệp lẫn URL.

    Trả về (preview_md, raw_md, download_path, status_md).
    """
    try:
        md = MarkItDown(enable_plugins=enable_plugins)
        result = md.convert(source)
        text = result.markdown or ""

        if not text.strip():
            return (
                "",
                "",
                None,
                "⚠️ Chuyển đổi xong nhưng không trích được nội dung văn bản nào.",
            )

        title = getattr(result, "title", None)
        name = _safe_filename(title) if title else base_name
        download_path = _write_md(text, name, used_paths)

        status = f"✅ Thành công — {len(text):,} ký tự"
        if title:
            status += f" · Tiêu đề: {title}"
        return text, text, download_path, status
    except Exception as exc:  # hiển thị lỗi thân thiện thay vì để app sập
        detail = traceback.format_exc(limit=2)
        msg = (
            f"❌ Lỗi khi chuyển đổi: {type(exc).__name__}: {exc}\n\n"
            "Gợi ý: kiểm tra định dạng có được hỗ trợ không, "
            "hoặc thiếu phụ thuộc (vd: audio cần ffmpeg)."
        )
        return "", f"```\n{detail}\n```", None, msg


class ConvertResult(NamedTuple):
    """Kết quả chuyển đổi một tệp.

    `translated`: True khi `raw_md` đã là bản tiếng Việt do chế độ gộp OCR+dịch (một bước) —
    thay cho việc dò chuỗi "gộp 1 bước" trong dòng trạng thái (B9).
    """

    preview: str
    raw_md: str
    path: object  # đường dẫn tệp .md hoặc None
    status: str
    translated: bool = False


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

# Nhãn các chế độ xử lý trên giao diện.
MODE_CHESS = "📚 Sách cờ vua tiếng Anh (mặc định)"
MODE_CHESS_RU = "📚 Sách cờ vua tiếng Nga"
MODE_CHESS_ES = "📚 Sách cờ vua tiếng Tây Ban Nha"
MODE_GENERAL = "📄 Tài liệu thường (chế độ gốc)"

# Nhãn lựa chọn nơi tự động lưu tệp .md kết quả.
AUTOSAVE_SRC = "📂 Cùng thư mục với file gốc"
AUTOSAVE_CUSTOM = "📁 Thư mục tùy chọn (ô bên dưới)"


def _is_chess_mode(label):
    """Nhãn chế độ -> True nếu là chế độ sách cờ vua (mặc định khi nhãn lạ)."""
    return label != MODE_GENERAL


def _chess_lang_from_mode(label):
    """Nhãn chế độ -> ngôn ngữ ký hiệu nguồn: 'ru' sách Nga, 'es' sách Tây Ban
    Nha, 'en' còn lại."""
    if label == MODE_CHESS_RU:
        return "ru"
    if label == MODE_CHESS_ES:
        return "es"
    return "en"


def _model_from_label(label):
    """'gemini-3.8-flash (cân bằng)' -> 'gemini-3.8-flash', 'opus (chính xác)' -> 'opus'."""
    if not label:
        return "gemini-3.8-flash"
    tok = str(label).strip().split()
    return tok[0].lower() if tok else "gemini-3.8-flash"


_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _effort_from_label(label, default="low"):
    """'low (tiết kiệm nhất)' -> 'low'; 'auto …'/nhãn lạ -> default.

    Với OCR truyền default=None ('auto' -> giữ logic low/medium tự động);
    với Dịch default='low'.
    """
    tok = (label or "").strip().split()
    val = tok[0].lower() if tok else ""
    return val if val in _EFFORT_LEVELS else default


def _dpi_from_label(label):
    """'400 (nét nhất — mặc định)' -> 400; nhãn lạ -> 400."""
    try:
        return int((label or "").strip().split()[0])
    except (ValueError, IndexError):
        return 400


def _pages_from_label(label):
    """'2 trang/lần' -> 2; nhãn lạ -> 1 (an toàn). Giới hạn 1..3."""
    try:
        n = int((label or "").strip().split()[0])
    except (ValueError, IndexError):
        return 1
    return min(3, max(1, n))


def parse_page_ranges(text, n_pages):
    """'1-5, 20, 31-40' -> tập số trang (đếm từ 1), cắt theo n_pages. Trống -> None (= tất cả các trang).

    Chấp nhận dấu phẩy/chấm phẩy/khoảng trắng làm dấu ngăn và '-' hoặc '–' làm dấu khoảng; thứ tự và trùng lặp
    không quan trọng. Ném ValueError (thông báo tiếng Việt) khi sai cú pháp, số trang < 1, khoảng ngược hoặc
    không có trang nào nằm trong tệp.
    """
    text = (text or "").strip()
    if not text:
        return None
    pages = set()
    for tok in re.split(r"[,;\s]+", text):
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)(?:[-–](\d+))?", tok)
        if not m:
            raise ValueError(f"Khoảng trang không hợp lệ: '{tok}'. Ví dụ đúng: 1-5, 20, 31-40")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if a < 1 or b < 1:
            raise ValueError("Số trang phải từ 1 trở lên.")
        if b < a:
            raise ValueError(f"Khoảng '{tok}' bị ngược (trang đầu lớn hơn trang cuối).")
        pages.update(range(a, min(b, n_pages) + 1))
    if not pages:
        raise ValueError(f"Không có trang nào nằm trong tệp (tệp có {n_pages} trang).")
    return pages


def count_pdf_pages(path):
    """Số trang của PDF, hoặc None nếu không đọc được."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(path)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


def estimate_ocr_calls(n_target, pages_per_call):
    """Số lượt gọi AI cần để OCR n_target trang khi mỗi lượt gồm pages_per_call trang."""
    ppc = max(1, int(pages_per_call or 1))
    return (max(0, int(n_target)) + ppc - 1) // ppc


def _ocr_to_outputs(
    file_path, base_name, model, board_dpi=400, used_paths=None, chess=True,
    progress=None, chess_lang="en", effort=None, merge_translate=False,
    pages_per_call=1, engine="antigravity", api_key=None, claude_token=None,
    agy_token=None, ocr_pdf_kwargs=None,
):
    """Chạy OCR (PDF hoặc ảnh) qua AI Engine (Antigravity hoặc Claude Code) và trả về ConvertResult.

    ocr_pdf_kwargs: tham số tùy chọn chuyển thẳng cho `claude_ocr.ocr_pdf` (pages, done_pages, on_page, cancel).

    merge_translate=True: gộp OCR + dịch sang tiếng Việt trong cùng lệnh gọi
    (bỏ pass dịch riêng) — ghi tệp `<tên>_vn.md`.
    pages_per_call>1: gộp nhiều trang PDF vào 1 lệnh gọi (giảm số lệnh).
    """
    import claude_ocr

    translate_to = "vi" if merge_translate else None
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = claude_ocr.ocr_pdf(
            file_path, model=model, board_dpi=board_dpi, chess=chess,
            progress=progress, chess_lang=chess_lang, effort=effort,
            translate_to=translate_to, pages_per_call=pages_per_call,
            engine=engine, api_key=api_key, claude_token=claude_token,
            agy_token=agy_token, **(ocr_pdf_kwargs or {}),
        )
    else:
        text = claude_ocr.ocr_image_file(
            file_path, model=model, chess=chess, chess_lang=chess_lang,
            effort=effort, translate_to=translate_to, engine=engine,
            api_key=api_key, claude_token=claude_token,
            agy_token=agy_token,
        )

    if not text.strip():
        return ConvertResult("", "", None, "⚠️ OCR xong nhưng không trích được nội dung.")

    out_name = f"{base_name}_vn" if merge_translate else base_name
    download_path = _write_md(text, out_name, used_paths)
    label = "OCR+dịch (gộp 1 bước)" if merge_translate else "OCR"
    engine_name = "Google Antigravity / Gemini" if engine == "antigravity" else "Claude Code"
    status = (
        f"✅ Đã {label} bằng {engine_name} (model: {model}, "
        f"effort: {effort or 'auto'}) — {len(text):,} ký tự"
    )
    return ConvertResult(text, text, download_path, status, translated=bool(merge_translate))


def convert_file(
    file_path, enable_plugins, use_ocr, model_label, force_ocr=False,
    board_dpi_label=None, used_paths=None, chess=True, progress=None,
    chess_lang="en", ocr_effort_label=None, merge_translate=False,
    ocr_pages_label=None, engine="antigravity", api_key=None,
    claude_token=None, agy_token=None, ocr_pdf_kwargs=None,
):
    if not file_path:
        return ConvertResult("", "", None, "ℹ️ Hãy chọn hoặc kéo-thả một tệp trước.")

    from ai_engine import is_engine_available

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    ext = os.path.splitext(file_path)[1].lower()
    model = _model_from_label(model_label)
    ocr_effort = _effort_from_label(ocr_effort_label, default=None)
    board_dpi = _dpi_from_label(board_dpi_label)
    pages_per_call = _pages_from_label(ocr_pages_label)
    is_image = ext in IMAGE_EXTS
    is_pdf = ext == ".pdf"
    engine_name = "Google Antigravity / Gemini" if engine == "antigravity" else "Claude Code"

    # Ảnh: built-in chỉ ra metadata/mô tả, nên OCR trực tiếp nếu được bật.
    if use_ocr and is_image:
        if not is_engine_available(engine, api_key=api_key, claude_token=claude_token, agy_token=agy_token):
            # Không có CLI hoặc API Key -> thử chuyển đổi thường.
            preview, raw_md, download, st = _convert(file_path, enable_plugins, base_name, used_paths)
            if not (raw_md or "").strip():
                st = (
                    "⚠️ **Tệp ảnh**: Cần phiên thuê bao tháng hoặc API Key để nhận diện văn bản & hình cờ.\n\n"
                    "👉 Vui lòng mở tab **⚙️ Cài đặt Hạ tầng & API** để kết nối gói thuê bao hoặc nhập API Key!"
                )
            return ConvertResult(preview, raw_md, download, st)
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
                engine=engine, api_key=api_key, claude_token=claude_token,
                agy_token=agy_token, ocr_pdf_kwargs=ocr_pdf_kwargs,
            )
        except Exception as exc:
            return ConvertResult("", "", None, f"❌ Lỗi OCR: {exc}")

    # PDF + "Buộc OCR": bỏ qua lớp text có sẵn, OCR lại toàn bộ bằng AI Engine.
    if use_ocr and is_pdf and force_ocr:
        if not is_engine_available(engine, api_key=api_key, claude_token=claude_token, agy_token=agy_token):
            # Fallback sang chuyển đổi chuẩn của MarkItDown kèm ghi chú
            preview, raw_md, download, st = _convert(
                file_path, enable_plugins, base_name, used_paths
            )
            if (raw_md or "").strip():
                warning = "ℹ️ Đã chuyển đổi văn bản chuẩn MarkItDown. (Để nhận diện thế cờ & dịch tiếng Việt, hãy kết nối gói thuê bao hoặc nhập API Key tại tab **⚙️ Cài đặt Hạ tầng & API**)."
                st = f"{warning}\n\n{st}" if st else warning
            else:
                st = (
                    "⚠️ **PDF Scan (Dạng ảnh)**: Không tìm thấy lớp văn bản thô để trích xuất trực tiếp.\n\n"
                    "👉 **Cách xử lý**: Vui lòng chuyển sang tab **⚙️ Cài đặt Hạ tầng & API** để kết nối **Gói Thuê bao tháng (0đ phí API)** hoặc nhập **Gemini API Key**!"
                )
            return ConvertResult(preview, raw_md, download, st)
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
                engine=engine, api_key=api_key, claude_token=claude_token,
                agy_token=agy_token, ocr_pdf_kwargs=ocr_pdf_kwargs,
            )
        except Exception as exc:
            return ConvertResult("", "", None, f"❌ Lỗi OCR: {exc}")

    # Chuyển đổi thường trước.
    preview, raw_md, download, status = _convert(
        file_path, enable_plugins, base_name, used_paths
    )

    # PDF scan (không có lớp text) -> OCR fallback nếu được bật.
    if use_ocr and is_pdf and not (raw_md or "").strip():
        if not is_engine_available(engine, api_key=api_key, claude_token=claude_token, agy_token=agy_token):
            return (
                preview,
                raw_md,
                download,
                "⚠️ **PDF Scan (Dạng ảnh)**: Không có lớp văn bản.\n\n"
                "👉 Vui lòng mở tab **⚙️ Cài đặt Hạ tầng & API** để kết nối gói thuê bao tháng hoặc nhập API Key miễn phí.",
            )
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
                engine=engine, api_key=api_key, claude_token=claude_token,
                agy_token=agy_token, ocr_pdf_kwargs=ocr_pdf_kwargs,
            )
        except Exception as exc:
            return ConvertResult("", "", None, f"❌ Lỗi OCR: {exc}")

    return ConvertResult(preview, raw_md, download, status)



def convert_url(url, enable_plugins):
    url = (url or "").strip()
    if not url:
        return "", "", None, "ℹ️ Hãy nhập một URL (YouTube, Wikipedia, trang web, RSS...)."
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return "", "", None, "⚠️ URL phải bắt đầu bằng http:// hoặc https://"
    return _convert(url, enable_plugins, "ketqua_url")



def _translate_to_vn(
    raw_md, orig_path, model, done_paths, chess=True, progress=None,
    chess_lang="en", effort="low", engine=ENGINE_ANTIGRAVITY, api_key=None,
    claude_token=None, agy_token=None, translate_kwargs=None,
):
    """Dịch raw_md sang tiếng Việt, ghi tệp `<tên gốc>_vn.md`.

    translate_kwargs: tham số tùy chọn cho `translate_markdown_vn` (chunk_cache, cancel).

    chess: True -> dịch theo quy tắc cờ vua; False -> dịch tài liệu thường.
    chess_lang: 'en' (ký hiệu Anh) hoặc 'ru' (ký hiệu Nga) khi chess=True.
    engine: 'antigravity' (mặc định) hoặc 'claude'.
    Trả về (đường dẫn tệp _vn hoặc None, dòng status).
    """
    import claude_translate

    engine_name = "Google Antigravity / Gemini" if engine == ENGINE_ANTIGRAVITY else "Claude Code"
    if not is_engine_available(engine, api_key=api_key, claude_token=claude_token, agy_token=agy_token):
        cmd_name = "lệnh 'agy' hoặc Gemini API Key" if engine == ENGINE_ANTIGRAVITY else "lệnh 'claude' hoặc Token thuê bao"
        return None, f"⚠️ Bỏ qua dịch: cần {engine_name} ({cmd_name})."
    try:
        vn_text = claude_translate.translate_markdown_vn(
            raw_md, model=model, chess=chess, progress=progress,
            chess_lang=chess_lang, effort=effort, engine=engine, api_key=api_key,
            claude_token=claude_token, agy_token=agy_token, **(translate_kwargs or {}),
        )
        vn_name = os.path.splitext(os.path.basename(orig_path))[0] + "_vn"
        vn_path = _write_md(vn_text, vn_name, done_paths)
        return vn_path, (
            f"🇻🇳 Đã dịch bằng {engine_name} (model: {model}, effort: {effort}) "
            f"— {len(vn_text):,} ký tự"
        )
    except Exception as exc:
        return None, f"⚠️ Lỗi dịch sang tiếng Việt: {exc}"

