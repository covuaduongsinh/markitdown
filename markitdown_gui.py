# -*- coding: utf-8 -*-
"""
Màn hình (GUI web) chạy MarkItDown bằng Gradio.

Cách chạy:
    .venv\\Scripts\\python.exe markitdown_gui.py
hoặc nhấp đúp run_gui.bat

Sau khi chạy, mở trình duyệt tại http://127.0.0.1:7860
"""

import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from urllib.parse import quote

import gradio as gr
from markitdown import MarkItDown

# Thư mục tạm để chứa các tệp .md xuất ra (cho nút tải về)
_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "markitdown_gui_output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    """Bỏ ký tự không hợp lệ trong tên tệp Windows."""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", name).strip().strip(".")
    return name or "ketqua"


def _write_md(markdown: str, base_name: str, used_paths=None) -> str:
    """Ghi nội dung Markdown ra tệp .md trong thư mục tạm, trả về đường dẫn.

    `used_paths`: các đường dẫn đã xuất trong cùng lô — nếu trùng thì
    thêm hậu tố _2, _3... để không ghi đè kết quả của tệp trước.
    """
    out_path = os.path.join(_OUTPUT_DIR, _safe_filename(base_name) + ".md")
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
    out_path = os.path.join(_OUTPUT_DIR, _safe_filename(base_name) + "_fen.txt")
    if used_paths:
        root, ext = os.path.splitext(out_path)
        n = 2
        while out_path in used_paths:
            out_path = f"{root}_{n}{ext}"
            n += 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(fens) + "\n")
    return out_path, len(fens)


_DL_FILE_ICON = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#1FA98F" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/></svg>'
)
_DL_DOWN_ICON = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
)
_DL_ZIP_ICON = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>'
)


def _zip_all(paths):
    """Gộp các tệp .md kết quả vào 1 zip cố định trong _OUTPUT_DIR, trả về đường dẫn.

    Dùng tên cố định để mỗi lần gọi ghi đè (không tích lũy zip cũ). Dedup tên
    trùng bên trong archive (a.md, a_2.md...) để không mất tệp khi nhiều nguồn
    cùng tên gốc.
    """
    zip_path = os.path.join(_OUTPUT_DIR, "markitdown_ketqua.zip")
    used = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            arc = os.path.basename(p)
            root, ext = os.path.splitext(arc)
            n = 2
            while arc in used:
                arc = f"{root}_{n}{ext}"
                n += 1
            used.add(arc)
            zf.write(p, arcname=arc)
    return zip_path


def _download_panel(paths):
    """HTML danh sách tệp kết quả, mỗi tệp một nút tải riêng.

    Khi có ≥2 tệp, chèn thêm một dòng "Tải tất cả (.zip)" ở đầu danh sách.
    """
    if not paths:
        return ""
    rows = []
    if len(paths) >= 2:
        zip_path = _zip_all(paths)
        zip_name = os.path.basename(zip_path)
        zip_href = "/gradio_api/file=" + quote(zip_path.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row dl-all">'
            f'<span class="dl-fileicon">{_DL_ZIP_ICON}</span>'
            f'<span class="dl-name">Tải tất cả · {len(paths)} tệp</span>'
            f'<a class="dl-btn" href="{zip_href}" download="{zip_name}">'
            f'{_DL_DOWN_ICON}Tải .zip</a></div>'
        )
    for p in paths:
        name = os.path.basename(p)
        href = "/gradio_api/file=" + quote(p.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row"><span class="dl-fileicon">{_DL_FILE_ICON}</span>'
            f'<span class="dl-name">{name}</span>'
            f'<a class="dl-btn" href="{href}" download="{name}">{_DL_DOWN_ICON}Tải về</a></div>'
        )
    return (
        '<div class="dl-list"><div class="dl-title">Tệp kết quả · '
        f'{len(paths)} tệp</div>'
        + "".join(rows)
        + "</div>"
    )


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
    """'opus (chính xác nhất)' -> 'opus'."""
    return (label or "opus").strip().split()[0].lower()


_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _effort_from_label(label, default="low"):
    """'low (tiết kiệm nhất)' -> 'low'; 'auto …'/nhãn lạ -> default.

    Với OCR truyền default=None ('auto' -> giữ logic low/medium tự động trong
    claude_ocr); với Dịch default='low'.
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


def _ocr_to_outputs(
    file_path, base_name, model, board_dpi=400, used_paths=None, chess=True,
    progress=None, chess_lang="en", effort=None, merge_translate=False,
    pages_per_call=1,
):
    """Chạy OCR (PDF hoặc ảnh) qua Claude Code và trả về 4-tuple kết quả.

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
        )
    else:
        text = claude_ocr.ocr_image_file(
            file_path, model=model, chess=chess, chess_lang=chess_lang,
            effort=effort, translate_to=translate_to,
        )

    if not text.strip():
        return "", "", None, "⚠️ OCR xong nhưng không trích được nội dung."

    out_name = f"{base_name}_vn" if merge_translate else base_name
    download_path = _write_md(text, out_name, used_paths)
    label = "OCR+dịch (gộp 1 bước)" if merge_translate else "OCR"
    status = (
        f"✅ Đã {label} bằng Claude Code (model: {model}, "
        f"effort: {effort or 'auto'}) — {len(text):,} ký tự"
    )
    return text, text, download_path, status


def convert_file(
    file_path, enable_plugins, use_ocr, model_label, force_ocr=False,
    board_dpi_label=None, used_paths=None, chess=True, progress=None,
    chess_lang="en", ocr_effort_label=None, merge_translate=False,
    ocr_pages_label=None,
):
    if not file_path:
        return "", "", None, "ℹ️ Hãy chọn hoặc kéo-thả một tệp trước."

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    ext = os.path.splitext(file_path)[1].lower()
    model = _model_from_label(model_label)
    ocr_effort = _effort_from_label(ocr_effort_label, default=None)
    board_dpi = _dpi_from_label(board_dpi_label)
    pages_per_call = _pages_from_label(ocr_pages_label)
    is_image = ext in IMAGE_EXTS
    is_pdf = ext == ".pdf"

    # Ảnh: built-in chỉ ra metadata/mô tả, nên OCR trực tiếp nếu được bật.
    if use_ocr and is_image:
        from claude_ocr import find_claude

        if not find_claude():
            # Không có Claude Code -> vẫn thử chuyển đổi thường (ra metadata).
            return _convert(file_path, enable_plugins, base_name, used_paths)
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
            )
        except Exception as exc:
            return "", "", None, f"❌ Lỗi OCR: {exc}"

    # PDF + "Buộc OCR": bỏ qua lớp text có sẵn (thường là text rác từ OCR cũ
    # nhúng trong PDF scan), OCR lại toàn bộ bằng Claude Code.
    if use_ocr and is_pdf and force_ocr:
        from claude_ocr import find_claude

        if not find_claude():
            return (
                "",
                "",
                None,
                "⚠️ Cần Claude Code (lệnh 'claude') trong PATH để buộc OCR.",
            )
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
            )
        except Exception as exc:
            return "", "", None, f"❌ Lỗi OCR: {exc}"

    # Chuyển đổi thường trước.
    preview, raw_md, download, status = _convert(
        file_path, enable_plugins, base_name, used_paths
    )

    # PDF scan (không có lớp text) -> OCR fallback nếu được bật.
    if use_ocr and is_pdf and not (raw_md or "").strip():
        from claude_ocr import find_claude

        if not find_claude():
            return (
                preview,
                raw_md,
                download,
                "⚠️ PDF scan không có text. Cần Claude Code (lệnh 'claude') trong PATH để OCR.",
            )
        try:
            return _ocr_to_outputs(
                file_path, base_name, model, board_dpi, used_paths, chess=chess,
                progress=progress, chess_lang=chess_lang, effort=ocr_effort,
                merge_translate=merge_translate, pages_per_call=pages_per_call,
            )
        except Exception as exc:
            return "", "", None, f"❌ Lỗi OCR: {exc}"

    return preview, raw_md, download, status


def convert_url(url, enable_plugins):
    url = (url or "").strip()
    if not url:
        return "", "", None, "ℹ️ Hãy nhập một URL (YouTube, Wikipedia, trang web, RSS...)."
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return "", "", None, "⚠️ URL phải bắt đầu bằng http:// hoặc https://"
    return _convert(url, enable_plugins, "ketqua_url")


# ======================================================================
# Lớp giao diện — bộ nhận diện "Cờ vua Dương Sinh" (navy/sun/teal).
# Tái tạo từ design_handoff_markitdown_gui/ (Phương án A). Backend OCR/dịch
# ở phần trên giữ nguyên — đây chỉ là lớp trình bày.
# ======================================================================

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _svg_data_uri(rel_path):
    """Đọc 1 file SVG trong assets/ -> data URI base64 (nhúng thẳng vào HTML)."""
    try:
        with open(os.path.join(_ASSETS_DIR, rel_path), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return "data:image/svg+xml;base64," + b64
    except OSError:
        return ""


_PIECE_NAMES = ["wp", "wn", "wb", "wr", "wq", "wk", "bp", "bn", "bb", "br", "bq", "bk"]
_PIECES = {n: _svg_data_uri(f"pieces/{n}.svg") for n in _PIECE_NAMES}
_SYMBOL_WHITE = _svg_data_uri("symbol-white.svg")

THEME = gr.themes.Base(
    font=[gr.themes.GoogleFont("Roboto"), "Segoe UI", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("Roboto Mono"), "monospace"],
)

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;'
    "0,400;0,500;0,700;0,900;1,400&family=Roboto+Condensed:wght@400;500;600;700"
    '&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

# JS: chuyển theme sáng/tối, bắc cầu thẻ "chế độ" (HTML) -> gr.Radio ẩn, và
# render block ```chessboard``` / dòng `fen:` trong phần xem trước thành bàn cờ.
_SCRIPT = r"""
<script>
(function(){
  window.MID_PIECES = __MID_PIECES__;
  var MOON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  var SUN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F6B92B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.2" y1="4.2" x2="5.6" y2="5.6"/><line x1="18.4" y1="18.4" x2="19.8" y2="19.8"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.2" y1="19.8" x2="5.6" y2="18.4"/><line x1="18.4" y1="5.6" x2="19.8" y2="4.2"/></svg>';

  function setThemeBtn(){
    var dark = document.body.getAttribute('data-mid-theme') === 'dark';
    var want = dark ? 'sun' : 'moon';
    document.querySelectorAll('[data-mid-theme-icon]').forEach(function(el){
      if (el.getAttribute('data-mid-icon') !== want){ el.innerHTML = dark ? SUN : MOON; el.setAttribute('data-mid-icon', want); }
    });
    var label = dark ? 'Sáng' : 'Tối';
    document.querySelectorAll('[data-mid-theme-label]').forEach(function(el){ if (el.textContent !== label) el.textContent = label; });
  }
  window.midToggleTheme = function(){
    var b = document.body, dark = b.getAttribute('data-mid-theme') === 'dark';
    var next = dark ? 'light' : 'dark';
    b.setAttribute('data-mid-theme', next);
    try { localStorage.setItem('mid-theme', next); } catch(e){}
    setThemeBtn();
  };
  window.midSelectMode = function(idx){
    document.querySelectorAll('[data-mid-mode]').forEach(function(el){ el.classList.toggle('active', (+el.dataset.midMode) === idx); });
    var rs = document.querySelectorAll('#mid-mode-radio input[type=radio]');
    // .click() đi qua trọn vẹn luồng sự kiện của Svelte (gr.Radio) -> cập nhật
    // state + bắn .change cho backend; bỏ qua nếu ô đã được chọn sẵn.
    if (rs[idx] && !rs[idx].checked){ rs[idx].click(); }
  };
  // Đồng bộ class .active của các thẻ chế độ (HTML) theo radio ẩn — cần khi
  // giá trị radio được đặt bằng backend (vd khôi phục từ BrowserState) chứ
  // không qua midSelectMode.
  window.midSyncModeCards = function(){
    var rs = document.querySelectorAll('#mid-mode-radio input[type=radio]'), idx = 0;
    rs.forEach(function(r, i){ if (r.checked) idx = i; });
    document.querySelectorAll('[data-mid-mode]').forEach(function(el){
      el.classList.toggle('active', (+el.dataset.midMode) === idx); });
  };

  function boardHTML(fen, px){
    var map = {p:'bp',n:'bn',b:'bb',r:'br',q:'bq',k:'bk',P:'wp',N:'wn',B:'wb',R:'wr',Q:'wq',K:'wk'};
    var rows = fen.split(/\s+/)[0].split('/');
    var sq = px / 8;
    function cell(r, f, p){
      var light = ((r + f) % 2) === 0;
      var img = (p && window.MID_PIECES[p]) ? '<img src="' + window.MID_PIECES[p] + '" style="width:' + (sq*0.82) + 'px;height:' + (sq*0.82) + 'px;display:block;">' : '';
      return '<div style="width:' + sq + 'px;height:' + sq + 'px;background:' + (light ? '#F6F2E4' : '#46B49A') + ';display:flex;align-items:center;justify-content:center;">' + img + '</div>';
    }
    var html = '<div class="mid-board" style="box-sizing:content-box;width:' + px + 'px;height:' + px + 'px;display:grid;grid-template-columns:repeat(8,1fr);grid-template-rows:repeat(8,1fr);border:5px solid #2B3990;border-radius:8px;overflow:hidden;box-shadow:0 8px 22px rgba(43,57,144,.22);flex:0 0 auto;">';
    for (var r = 0; r < rows.length; r++){
      var f = 0;
      for (var i = 0; i < rows[r].length; i++){
        var ch = rows[r][i];
        if (/\d/.test(ch)){ var n = +ch; for (var k = 0; k < n; k++){ html += cell(r, f, null); f++; } }
        else { html += cell(r, f, map[ch]); f++; }
      }
    }
    return html + '</div>';
  }
  window.midRenderBoards = function(){
    var prev = document.getElementById('mid-preview');
    if (!prev) return;
    prev.querySelectorAll('pre code').forEach(function(code){
      var pre = code.parentElement;
      if (!pre || pre.dataset.midBoard) return;
      var cls = code.className || '', txt = code.textContent || '';
      var isBoard = cls.indexOf('chessboard') >= 0 || /^\s*fen:/i.test(txt);
      if (!isBoard) return;
      var m = txt.match(/fen:\s*([^\n]+)/i);
      var fen = (m ? m[1] : txt).trim();
      if (!fen || fen.indexOf('/') < 0) return;
      pre.dataset.midBoard = '1';
      var wrap = document.createElement('div');
      wrap.className = 'mid-board-wrap';
      wrap.innerHTML = boardHTML(fen, 256);
      pre.parentNode.insertBefore(wrap, pre);
      pre.style.display = 'none';
    });
  };

  document.addEventListener('click', function(e){
    if (!e.target || !e.target.closest) return;
    var card = e.target.closest('[data-mid-mode]');
    if (card){ window.midSelectMode(+card.dataset.midMode); return; }
    var t = e.target.closest('[data-mid-action="toggle-theme"]');
    if (t){ window.midToggleTheme(); return; }
  });

  function init(){
    if (!document.body.getAttribute('data-mid-theme')){
      var saved = '';
      try { saved = localStorage.getItem('mid-theme') || ''; } catch(e){}
      document.body.setAttribute('data-mid-theme', saved === 'dark' ? 'dark' : 'light');
    }
    setThemeBtn();
    window.midSyncModeCards();
    window.midRenderBoards();
  }
  function start(){
    init();
    new MutationObserver(function(){ setThemeBtn(); window.midSyncModeCards(); window.midRenderBoards(); }).observe(document.body, {childList:true, subtree:true});
  }
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();
</script>
"""

HEAD = _FONTS_LINK + _SCRIPT.replace("__MID_PIECES__", json.dumps(_PIECES))

CSS = r"""
/* ---------- design tokens (2 theme) ---------- */
body {
  --navy:#2B3990; --navy-deep:#1E2A6B; --navy-ink:#151D49;
  --sun:#F6B92B; --sun-deep:#D99A12; --teal:#1FA98F;
  --c-bg:#F1F3F9; --c-panel:#FFFFFF; --c-inset:#F5F6FB; --c-dropbg:#FCFCFE;
  --c-text:#16203A; --c-body:#3A4254; --c-subtext:#6E7486; --c-faint:#A2A7B6;
  --c-border:#E3E5EC; --c-border-strong:#D2D6E4; --c-navysoft:#E9EBF6; --c-sunsoft:#FDF1D2;
  --c-shadow:0 12px 32px rgba(21,29,73,0.10);
}
body[data-mid-theme="dark"] {
  --c-bg:#0E1430; --c-panel:#1A2356; --c-inset:#141C49; --c-dropbg:#141C49;
  --c-text:#F2F4FB; --c-body:#D4D9EE; --c-subtext:#A6AED2; --c-faint:#7C84AC;
  --c-border:rgba(255,255,255,0.10); --c-border-strong:rgba(255,255,255,0.20);
  --c-navysoft:rgba(99,120,214,0.20); --c-sunsoft:rgba(246,185,43,0.16);
  --c-shadow:0 16px 40px rgba(0,0,0,0.34);
}

/* ---------- base / container ---------- */
html, body, gradio-app { background:var(--c-bg) !important; }
.gradio-container { max-width:100% !important; padding:0 !important; background:var(--c-bg) !important;
  font-family:'Roboto','Segoe UI',system-ui,sans-serif; color:var(--c-text); }
.gradio-container .main, .gradio-container .wrap, .gradio-container .contain { padding:0 !important; }
footer { display:none !important; }
@keyframes mid-spin { to { transform: rotate(360deg); } }
@keyframes mid-pulse { 0%,100% { opacity:1; } 50% { opacity:.45; } }
@keyframes mid-rise { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background:rgba(110,116,134,.32); border-radius:999px; }

/* ---------- top bar ---------- */
#mid-topbar { position:sticky; top:0; z-index:30; display:flex; align-items:center; gap:14px;
  padding:13px 26px; background:var(--navy); color:#fff; box-shadow:0 2px 14px rgba(21,29,73,.28); }
#mid-topbar .mid-logo { width:24px; height:26px; display:block; }
#mid-topbar .mid-brand { font-weight:900; font-size:19px; letter-spacing:-0.01em; }
#mid-topbar .mid-tagline { font-weight:300; font-size:12.5px; opacity:.85; letter-spacing:.03em;
  border-left:1px solid rgba(255,255,255,.25); padding-left:14px; }
#mid-topbar .mid-topbar-right { margin-left:auto; display:flex; align-items:center; gap:14px; }
#mid-topbar .mid-badges { display:flex; gap:6px; }
#mid-topbar .mid-badge { font-size:11px; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.22);
  border-radius:999px; padding:3px 10px; white-space:nowrap; }
#mid-topbar .mid-badge-chess { background:rgba(246,185,43,.22); border-color:rgba(246,185,43,.5);
  color:#FCE29A; font-weight:600; }
#mid-topbar .mid-theme-btn { display:flex; align-items:center; gap:7px; cursor:pointer;
  background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22); color:#fff;
  border-radius:999px; padding:6px 13px; font-family:'Roboto'; font-size:12.5px; font-weight:600; }
#mid-topbar .mid-theme-btn [data-mid-theme-icon] { display:flex; }
@media (max-width:780px){ #mid-topbar .mid-tagline, #mid-topbar .mid-badges { display:none; } }

/* ---------- workspace 2-col grid ---------- */
#mid-workspace { display:grid !important; grid-template-columns:412px minmax(0,1fr); gap:22px;
  max-width:1340px; margin:0 auto !important; padding:24px 26px 60px; align-items:start; width:100%; }
@media (max-width:1040px){ #mid-workspace { grid-template-columns:1fr; } }
#mid-workspace > .column, .mid-col-left, .mid-col-right { min-width:0 !important; gap:16px !important; }

/* ---------- cards ---------- */
.mid-card { background:var(--c-panel) !important; border:1px solid var(--c-border) !important;
  border-radius:18px !important; box-shadow:var(--c-shadow) !important; padding:16px !important; }
/* chỉ làm trong suốt các lớp bố cục, KHÔNG đụng tới nút/ô nhập bên trong */
.mid-card > .form, .mid-card > .gap, .mid-card .gap > .form,
.mid-card .tabitem > .gap, .mid-card .tabitem > .form { background:transparent !important;
  border:none !important; box-shadow:none !important; }
.mid-card .gap, .mid-card .form { gap:12px !important; }
.mid-input-card { padding:0 !important; overflow:hidden; }
.mid-section-title { font-family:'Roboto Condensed'; font-weight:700; font-size:12px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--c-subtext); }

/* ---------- input tabs (segmented) ---------- */
.mid-input-tabs .tab-nav, .mid-input-tabs > div[role="tablist"] { background:var(--c-inset) !important;
  border:none !important; border-bottom:1px solid var(--c-border) !important; padding:6px !important;
  gap:4px !important; display:flex !important; }
.mid-input-tabs .tab-nav button { flex:1; border:none !important; background:transparent !important;
  color:var(--c-subtext) !important; font-weight:600; font-size:13px; padding:9px !important;
  border-radius:9px !important; }
.mid-input-tabs .tab-nav button.selected { background:var(--c-panel) !important; color:var(--navy) !important;
  box-shadow:0 2px 6px rgba(21,29,73,.10); }
.mid-input-tabs .tabitem { padding:16px !important; border:none !important; }

/* ---------- drop zone (gr.File) ---------- */
.mid-drop-caption { font-size:12px; color:var(--c-subtext); line-height:1.5; margin:0 0 9px; }
.mid-drop-caption b { color:var(--c-text); font-weight:700; }
#mid-file { border:2px dashed var(--c-border-strong) !important; background:var(--c-dropbg) !important;
  border-radius:14px !important; padding:6px !important; min-height:120px; }
#mid-file .block, #mid-file .wrap, #mid-file .center, #mid-file .file-preview,
#mid-file [class*="upload"], #mid-file [data-testid="block-label"] { border:none !important;
  background:transparent !important; box-shadow:none !important; color:var(--c-subtext) !important; }
#mid-file svg { color:var(--navy) !important; stroke:var(--navy) !important; }
.mid-pick-btn button { width:100% !important; background:var(--c-inset) !important;
  border:1px solid var(--c-border) !important; color:var(--c-subtext) !important; border-radius:11px !important;
  font-size:12.5px !important; font-weight:600 !important; box-shadow:none !important; }
.mid-pick-btn button:hover { background:var(--c-navysoft) !important; }
.mid-picked-view { font-size:11.5px; color:var(--c-subtext); }
.mid-picked-view p, .mid-picked-view li { color:var(--c-subtext) !important; font-size:11.5px; }

/* URL tab */
.mid-url-box textarea, .mid-url-box input { border:1px solid var(--c-border-strong) !important;
  background:var(--c-dropbg) !important; color:var(--c-text) !important; border-radius:12px !important;
  font-size:13.5px !important; }

/* ---------- mode cards ---------- */
.mid-hidden { position:absolute !important; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
  opacity:0; pointer-events:none; margin:0 !important; }
.mid-modes { display:flex; flex-direction:column; gap:9px; margin-top:11px; }
.mid-mode { display:flex; align-items:center; gap:12px; padding:12px 13px; border-radius:12px; cursor:pointer;
  background:var(--c-inset); border:1px solid var(--c-border); transition:all .16s cubic-bezier(.22,1,.36,1); }
.mid-mode.active { background:var(--c-sunsoft); border:1.5px solid var(--sun); box-shadow:0 4px 14px rgba(246,185,43,.18); }
.mid-mode .mid-mode-icon { width:30px; height:30px; flex:0 0 auto; display:flex; align-items:center; justify-content:center; }
.mid-mode .mid-mode-title { font-weight:700; font-size:14px; color:var(--c-text); }
.mid-mode .mid-mode-desc { font-size:11.5px; color:var(--c-subtext); margin-top:1px; }
.mid-mode .mid-mode-text { flex:1; min-width:0; }
.mid-mode .mid-check { width:18px; height:18px; flex:0 0 auto; border-radius:999px;
  border:2px solid var(--c-border-strong); background-position:center; background-repeat:no-repeat; }
.mid-mode.active .mid-check { width:20px; height:20px; border:none; background-color:var(--sun);
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%232B2207' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E"); }

/* ---------- quality / preset ---------- */
.mid-quality-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:11px; }
#mid-preset-hint { font-size:11.5px; color:var(--c-subtext); }
#mid-preset .wrap { display:flex !important; gap:4px; background:var(--c-inset); border:1px solid var(--c-border);
  border-radius:12px; padding:4px; }
#mid-preset label { flex:1; justify-content:center; display:flex; align-items:center; border:none !important;
  background:transparent !important; border-radius:9px !important; padding:10px 4px !important; font-weight:700;
  font-size:13px; color:var(--c-subtext) !important; cursor:pointer; box-shadow:none !important; margin:0 !important;
  white-space:nowrap; }
#mid-preset label.selected, #mid-preset label:has(input:checked) { background:var(--navy) !important;
  color:#fff !important; box-shadow:0 4px 12px rgba(43,57,144,.30) !important; }
#mid-preset label.selected span, #mid-preset label:has(input:checked) span { color:#fff !important; }
#mid-preset input { display:none !important; }

/* convert button */
#mid-convert { margin-top:13px !important; }
#mid-convert button, #mid-convert-url button { width:100%; border:none !important; border-radius:12px !important;
  padding:14px !important; font-family:'Roboto'; font-weight:700 !important; font-size:15px !important;
  background:var(--navy) !important; background-image:none !important; color:#fff !important;
  box-shadow:0 10px 26px rgba(43,57,144,.28); }
#mid-convert button:hover, #mid-convert-url button:hover { background:var(--navy-deep) !important; }
#mid-stop { margin-top:13px !important; }
#mid-stop button { width:100%; border:none !important; border-radius:12px !important;
  padding:14px !important; font-family:'Roboto'; font-weight:700 !important; font-size:15px !important;
  background:#D64545 !important; background-image:none !important; color:#fff !important;
  box-shadow:0 10px 26px rgba(214,69,69,.28); }
#mid-stop button:hover { background:#B83434 !important; }

/* advanced accordion */
.mid-adv { margin-top:11px !important; background:transparent !important; border:1px solid var(--c-border) !important;
  border-radius:11px !important; }
.mid-adv > button, .mid-adv .label-wrap { color:var(--c-subtext) !important; font-weight:600 !important;
  font-size:13px !important; }
.mid-adv .label-wrap { padding:11px 13px !important; }

/* toggles as switches */
.mid-toggle { padding:0 !important; }
.mid-toggle label { display:flex !important; align-items:center !important; gap:11px; font-size:13px !important;
  font-weight:600 !important; color:var(--c-text) !important; cursor:pointer; }
.mid-toggle input[type=checkbox] { appearance:none; -webkit-appearance:none; width:38px !important;
  height:22px !important; min-width:38px; border-radius:999px !important; background:var(--c-border-strong) !important;
  position:relative; cursor:pointer; flex:0 0 auto; transition:background .18s ease; border:none !important; margin:0 !important; }
.mid-toggle input[type=checkbox]::before { content:""; position:absolute; top:2px; left:2px; width:18px; height:18px;
  border-radius:999px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.25); transition:left .18s ease; }
.mid-toggle input[type=checkbox]:checked { background:var(--navy) !important; }
.mid-toggle input[type=checkbox]:checked::before { left:18px; }
.mid-toggle .info, .mid-toggle [data-testid="block-info"] { font-size:11px !important; color:var(--c-subtext) !important;
  margin:1px 0 0 49px !important; line-height:1.4; }

/* selects: 3 hàng × 2 cột (dùng layout sẵn của gr.Row) */
.mid-selects { gap:11px !important; }
.mid-select { min-width:0 !important; }
.mid-select span[data-testid="block-info"] { display:none !important; }
.mid-select label > span:first-child, .mid-select .gr-form > span,
.mid-select [data-testid="block-label"] { font-size:11px !important; font-weight:600 !important;
  color:var(--c-subtext) !important; margin-bottom:5px !important; }
.mid-select .wrap, .mid-select .wrap-inner, .mid-select .secondary-wrap,
.mid-select input { background:var(--c-inset) !important; color:var(--c-text) !important;
  font-size:12.5px !important; }
.mid-select .container > .wrap, .mid-select .wrap { border:1px solid var(--c-border) !important;
  border-radius:9px !important; }

/* hidden plumbing controls */
.mid-plumbing { display:none !important; }
.mid-autosave-target .wrap, .mid-autosave-dir textarea, .mid-autosave-dir input { background:var(--c-inset) !important;
  border:1px solid var(--c-border) !important; color:var(--c-text) !important; border-radius:9px !important; }

/* ---------- right preview card ---------- */
.mid-preview-card { padding:0 !important; overflow:hidden; min-height:640px; }
.mid-preview-card > .gap, .mid-preview-card > .form { gap:0 !important; }
#mid-status { padding:10px 18px !important; border-bottom:1px solid var(--c-border); background:var(--c-inset); }
#mid-status p { margin:0; font-size:12.5px; color:var(--c-body); }
.mid-preview-card .tabs > .tab-nav { padding:10px 18px 0 !important; border-bottom:1px solid var(--c-border) !important;
  background:var(--c-inset); gap:6px; }
.mid-preview-card .tab-nav button { border:none !important; background:none !important; color:var(--c-subtext) !important;
  font-size:13px; font-weight:500; padding:7px 13px !important; border-radius:8px 8px 0 0 !important; }
.mid-preview-card .tab-nav button.selected { background:var(--navy) !important; color:#fff !important; font-weight:700; }
.mid-preview-card .tabitem { padding:0 !important; }
#mid-preview { padding:30px 36px !important; color:var(--c-body); animation:mid-rise .3s ease; min-height:480px; }
#mid-preview:empty::before { content:"Kết quả Markdown sẽ hiện ở đây — chọn tệp hoặc dán URL bên trái, chọn chế độ rồi bấm Chuyển đổi.";
  display:block; color:var(--c-faint); font-size:14px; text-align:center; padding:80px 20px; }
#mid-preview h1 { font-weight:900; font-size:28px; line-height:1.15; color:var(--c-text); margin:0 0 14px; }
#mid-preview h2 { font-weight:800; font-size:19px; color:var(--c-text); margin:18px 0 12px; }
#mid-preview p, #mid-preview li { font-size:15px; line-height:1.7; color:var(--c-body); }
#mid-preview table { width:100%; border-collapse:collapse; font-size:13.5px; }
#mid-preview th { text-align:left; padding:9px 12px; border-bottom:2px solid var(--c-border-strong); color:var(--c-text); font-weight:700; }
#mid-preview td { padding:9px 12px; border-bottom:1px solid var(--c-border); color:var(--c-body); }
#mid-preview pre, #mid-preview code { font-family:'Roboto Mono',monospace; }
#mid-preview pre { background:var(--c-inset); border:1px solid var(--c-border); border-radius:10px; padding:13px 15px; }
.mid-board-wrap { margin:0 0 18px; }
#mid-raw { padding:0 !important; }
#mid-raw .cm-editor, #mid-raw .cm-scroller { background:var(--c-panel) !important; font-family:'Roboto Mono',monospace !important;
  font-size:12.5px !important; }

/* ---------- downloads footer ---------- */
#mid-downloads:empty { display:none; }
.dl-list { border-top:1px solid var(--c-border); background:var(--c-inset); padding:14px 18px;
  display:flex; flex-direction:column; gap:7px; }
.dl-title { font-family:'Roboto Condensed'; font-weight:700; font-size:12px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--c-subtext); margin-bottom:3px; }
.dl-row { display:flex; align-items:center; gap:10px; padding:9px 12px; background:var(--c-panel);
  border:1px solid var(--c-border); border-radius:10px; }
.dl-fileicon { display:flex; flex:0 0 auto; }
.dl-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  font-weight:600; font-size:13px; color:var(--c-text); }
.dl-btn { flex:0 0 auto; display:flex; align-items:center; gap:5px; background:var(--navy); color:#fff !important;
  text-decoration:none !important; border-radius:999px; padding:6px 14px; font-size:11.5px; font-weight:700; }
.dl-btn:hover { background:var(--navy-deep); }
.dl-row.dl-all { background:var(--navy); border-color:var(--navy); }
.dl-row.dl-all .dl-name { color:#fff; }
.dl-row.dl-all .dl-btn { background:var(--sun); color:var(--navy-ink) !important; }
.dl-row.dl-all .dl-btn:hover { background:var(--sun-deep); }
.dl-row.dl-all .dl-btn svg { stroke:var(--navy-ink); }
.mid-clear-btn button { background:var(--c-inset) !important; border:1px solid var(--c-border) !important;
  color:var(--c-subtext) !important; border-radius:11px !important; font-size:12.5px !important; }
"""

# Doc-mode icon (lucide file-text) cho thẻ "Tài liệu thường".
_DOC_ICON_SVG = (
    '<svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="color:var(--c-subtext)">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/></svg>'
)

TOPBAR_HTML = f"""
<div id="mid-topbar">
  <img class="mid-logo" src="{_SYMBOL_WHITE}" alt="">
  <span class="mid-brand">MarkItDown</span>
  <span class="mid-tagline">Cờ vua Dương Sinh — tài liệu &amp; sách cờ → Markdown</span>
  <div class="mid-topbar-right">
    <div class="mid-badges">
      <span class="mid-badge">PDF</span>
      <span class="mid-badge">Word · Excel</span>
      <span class="mid-badge">Ảnh · URL</span>
      <span class="mid-badge mid-badge-chess">Sách cờ vua</span>
    </div>
    <button class="mid-theme-btn" data-mid-action="toggle-theme" type="button">
      <span data-mid-theme-icon></span><span data-mid-theme-label>Tối</span>
    </button>
  </div>
</div>
"""

MODE_CARDS_HTML = f"""
<div class="mid-modes">
  <div class="mid-mode active" data-mid-mode="0">
    <img class="mid-mode-icon" src="{_PIECES['wn']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Anh</div>
      <div class="mid-mode-desc">Nhận diện bàn cờ → FEN · K/Q/R/B/N → V/H/X/T/M</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="1">
    <img class="mid-mode-icon" src="{_PIECES['bn']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Nga</div>
      <div class="mid-mode-desc">Кр/Ф/Л/С/К → V/H/X/T/M · xử lý figurine</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="2">
    <img class="mid-mode-icon" src="{_PIECES['wb']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Tây Ban Nha</div>
      <div class="mid-mode-desc">R/D/T/A/C → V/H/X/T/M · ký hiệu Tây Ban Nha</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="3">
    <span class="mid-mode-icon">{_DOC_ICON_SVG}</span>
    <div class="mid-mode-text">
      <div class="mid-mode-title">Tài liệu thường</div>
      <div class="mid-mode-desc">Chuyển đổi gốc của MarkItDown + dịch thông thường</div>
    </div>
    <span class="mid-check"></span>
  </div>
</div>
"""

# Preset -> gợi ý ngắn hiển thị cạnh "MỨC CHẤT LƯỢNG".
PRESET_SAVER = "Tiết kiệm"
PRESET_BALANCED = "Cân bằng"
PRESET_ACCURATE = "Chính xác"
_PRESET_HINTS = {
    PRESET_SAVER: "haiku · effort thấp · gộp OCR+dịch",
    PRESET_BALANCED: "sonnet · auto · dịch riêng",
    PRESET_ACCURATE: "opus · effort cao · 400 DPI",
}

_STATUS_HINT = "👋 Chọn tệp hoặc dán URL rồi bấm **Chuyển đổi**."


def _with_download_update(result):
    """Đổi đường dẫn tải về thành bảng HTML chứa nút tải."""
    preview_md, raw_md, path, status_md = result
    return preview_md, raw_md, _download_panel([path] if path else []), status_md


def _translate_to_vn(
    raw_md, orig_path, model, done_paths, chess=True, progress=None,
    chess_lang="en", effort="low",
):
    """Dịch raw_md sang tiếng Việt, ghi tệp `<tên gốc>_vn.md`.

    chess: True -> dịch theo quy tắc cờ vua; False -> dịch tài liệu thường.
    chess_lang: 'en' (ký hiệu Anh) hoặc 'ru' (ký hiệu Nga) khi chess=True.
    Trả về (đường dẫn tệp _vn hoặc None, dòng status).
    """
    import claude_translate
    from claude_ocr import find_claude

    if not find_claude():
        return None, "⚠️ Bỏ qua dịch: cần Claude Code (lệnh 'claude') trong PATH."
    try:
        vn_text = claude_translate.translate_markdown_vn(
            raw_md, model=model, chess=chess, progress=progress,
            chess_lang=chess_lang, effort=effort,
        )
        vn_name = os.path.splitext(os.path.basename(orig_path))[0] + "_vn"
        vn_path = _write_md(vn_text, vn_name, done_paths)
        return vn_path, (
            f"🇻🇳 Đã dịch sang tiếng Việt (effort: {effort}) "
            f"— {len(vn_text):,} ký tự"
        )
    except Exception as exc:
        return None, f"⚠️ Lỗi dịch sang tiếng Việt: {exc}"


def _stream_job(func, kwargs, label, unit):
    """Chạy func(**kwargs, progress=...) trong thread nền, generator yield
    dòng tiến độ đều đặn (≤5s/lần) để kết nối SSE của Gradio không bị rớt
    khi tác vụ kéo dài. Kết thúc trả về kết quả của func (qua StopIteration).

    unit: tên đơn vị tiến độ hiển thị ("trang", "đoạn"...).
    """
    q = queue.Queue()
    out = {}

    def run():
        try:
            out["result"] = func(progress=lambda i, n: q.put((i, n)), **kwargs)
        except BaseException as exc:
            out["error"] = exc
        finally:
            q.put(None)  # báo hiệu kết thúc

    threading.Thread(target=run, daemon=True).start()
    start = time.monotonic()
    suffix = ""
    finished = False
    while not finished:
        try:
            msgs = [q.get(timeout=5)]
        except queue.Empty:
            msgs = []  # không có tiến độ mới -> vẫn yield keep-alive
        while True:  # gộp các message dồn lại, chỉ giữ cái mới nhất
            try:
                msgs.append(q.get_nowait())
            except queue.Empty:
                break
        for m in msgs:
            if m is None:
                finished = True
            else:
                suffix = f" — {unit} {m[0]}/{m[1]}"
        if finished:
            break
        yield f"{label}{suffix} · {int(time.monotonic() - start)}s…"
    if "error" in out:
        raise out["error"]
    return out.get("result")


def _picked_display(paths):
    """Markdown liệt kê các tệp đã chọn bằng hộp thoại (giữ đường dẫn gốc)."""
    if not paths:
        return ""
    rows = "\n".join(f"- `{p}`" for p in paths)
    return f"**📂 Đã chọn {len(paths)} tệp (giữ đường dẫn gốc):**\n{rows}"


def on_pick_files():
    """Mở hộp thoại chọn tệp gốc của Windows (qua tiến trình con pick_files.py).

    Trả về (danh sách đường dẫn THẬT, Markdown hiển thị) để cập nhật State + view.
    """
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pick_files.py")
    # Ẩn cửa sổ console của tiến trình con (hộp thoại tkinter vẫn hiện bình thường).
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        res = subprocess.run(
            [sys.executable, helper],
            capture_output=True, text=True, encoding="utf-8", timeout=300,
            creationflags=flags,
        )
        paths = [ln for ln in res.stdout.splitlines() if ln.strip()]
    except Exception as exc:
        return [], f"⚠️ Không mở được hộp thoại chọn tệp: {exc}"
    return paths, _picked_display(paths)


def on_convert_files(
    file_paths, mode_label, enable_plugins, use_ocr,
    model_label, ocr_effort_label, translate_model_label, translate_effort_label,
    force_ocr, board_dpi_label, translate_vn, merge_ocr_translate, ocr_pages_label,
    autosave_on, autosave_dir, picked_paths, autosave_target,
):
    # Ưu tiên tệp chọn bằng hộp thoại (có đường dẫn thật) — mới lưu được cạnh
    # file gốc; nếu không có thì dùng tệp kéo-thả (đường dẫn tạm).
    sources = picked_paths if picked_paths else file_paths
    sources_are_real = bool(picked_paths)
    if not sources:
        yield "", "", "", "ℹ️ Hãy chọn hoặc kéo-thả ít nhất một tệp trước."
        return

    chess = _is_chess_mode(mode_label)
    chess_lang = _chess_lang_from_mode(mode_label)
    # Gộp OCR+dịch chỉ có nghĩa khi người dùng cũng bật dịch tiếng Việt.
    merge = bool(merge_ocr_translate and translate_vn)
    total = len(sources)
    n_ok = 0  # số tệp nguồn chuyển đổi thành công (không tính tệp _vn)
    done_paths, previews, raws, lines = [], [], [], []

    for i, fp in enumerate(sources, 1):
        name = os.path.basename(fp)
        # Báo tiến độ trước khi xử lý, giữ nguyên kết quả các tệp đã xong.
        progress = "\n\n".join(lines + [f"⏳ Đang xử lý {i}/{total}: **{name}**…"])
        yield (
            "\n\n---\n\n".join(previews),
            "\n\n".join(raws),
            _download_panel(done_paths),
            progress,
        )

        # Chạy trong thread nền, yield tiến độ từng trang để giữ kết nối.
        job = _stream_job(
            convert_file,
            dict(
                file_path=fp, enable_plugins=enable_plugins, use_ocr=use_ocr,
                model_label=model_label, force_ocr=force_ocr,
                board_dpi_label=board_dpi_label, used_paths=done_paths,
                chess=chess, chess_lang=chess_lang,
                ocr_effort_label=ocr_effort_label,
                merge_translate=merge, ocr_pages_label=ocr_pages_label,
            ),
            label=f"⏳ Đang xử lý {i}/{total}: **{name}**",
            unit="trang",
        )
        while True:
            try:
                st_line = next(job)
            except StopIteration as stop:
                preview, raw_md, path, st = stop.value
                break
            # Yield tiến độ chỉ cập nhật status (gr.skip các ô còn lại
            # để giảm payload gửi về trình duyệt).
            yield gr.skip(), gr.skip(), gr.skip(), "\n\n".join(lines + [st_line])

        # Thư mục đích tính một lần cho mỗi tệp nguồn, dùng chung cho tệp gốc
        # lẫn tệp _vn.md.
        save_dir, save_note = _resolve_save_dir(
            fp, autosave_target, autosave_dir, sources_are_real
        )
        if path and autosave_on:
            saved, err = _autosave(path, save_dir)
            st += f"\n  💾 đã lưu: `{saved}`{save_note}" if saved else f"\n  {err}"
        if path:
            n_ok += 1
            done_paths.append(path)

        # Dịch sang tiếng Việt -> tạo thêm tệp _vn.md (nếu được bật).
        # Bỏ qua nếu nhánh OCR đã gộp dịch (chỉ khi đó status có "gộp 1 bước").
        # Dựa vào status thay vì cờ `merge` để tệp KHÔNG qua OCR (docx, PDF có
        # lớp text...) vẫn được dịch bình thường dù người dùng có tích merge.
        already_translated = bool(merge) and "gộp 1 bước" in (st or "")
        if translate_vn and not already_translated and path and (raw_md or "").strip():
            yield (
                "\n\n---\n\n".join(previews),
                "\n\n".join(raws),
                _download_panel(done_paths),
                "\n\n".join(
                    lines + [f"**{name}** — {st}",
                             f"⏳ Đang dịch sang tiếng Việt {i}/{total}: **{name}**…"]
                ),
            )
            model = _model_from_label(translate_model_label)
            translate_effort = _effort_from_label(
                translate_effort_label, default="low"
            )
            job = _stream_job(
                _translate_to_vn,
                dict(
                    raw_md=raw_md, orig_path=path, model=model,
                    done_paths=done_paths, chess=chess, chess_lang=chess_lang,
                    effort=translate_effort,
                ),
                label=f"⏳ Đang dịch sang tiếng Việt {i}/{total}: **{name}**",
                unit="đoạn",
            )
            while True:
                try:
                    st_line = next(job)
                except StopIteration as stop:
                    vn_path, vn_st = stop.value
                    break
                yield (
                    gr.skip(), gr.skip(), gr.skip(),
                    "\n\n".join(lines + [f"**{name}** — {st}", st_line]),
                )
            st += f"\n  {vn_st}"
            if vn_path:
                if autosave_on:
                    saved, err = _autosave(vn_path, save_dir)
                    st += f" · 💾 đã lưu: `{saved}`" if saved else f"\n  {err}"
                done_paths.append(vn_path)

        # Sách cờ vua (mặc định): gom FEN các thế cờ -> tệp <tên gốc>_fen.txt,
        # tải về + tự lưu cùng lúc với .md. FEN trong raw_md giữ nguyên văn nên
        # giống hệt bản dịch — chỉ cần trích một lần từ raw_md.
        if chess and path and (raw_md or "").strip():
            fen_base = os.path.splitext(os.path.basename(fp))[0]
            fen_path, n_fen = _write_fen_file(raw_md, fen_base, done_paths)
            if fen_path:
                st += f"\n  ♟️ Đã gom {n_fen} thế cờ → `{os.path.basename(fen_path)}`"
                if autosave_on:
                    saved, err = _autosave(fen_path, save_dir)
                    st += f" · 💾 đã lưu: `{saved}`" if saved else f"\n  {err}"
                done_paths.append(fen_path)
        lines.append(f"**{name}** — {st}")
        if preview:
            previews.append(f"## 📄 {name}\n\n{preview}")
        if raw_md:
            raws.append(raw_md)

        # Tệp xong tới đâu hiện kết quả và cho tải về ngay tới đó.
        summary = "\n\n".join(lines)
        if i == total:
            summary = f"🏁 Xong {n_ok}/{total} tệp.\n\n" + summary
        yield (
            "\n\n---\n\n".join(previews),
            "\n\n".join(raws),
            _download_panel(done_paths),
            summary,
        )


def on_convert_url(url, enable_plugins):
    return _with_download_update(convert_url(url, enable_plugins))


def on_clear():
    # Xoá kết quả + danh sách tệp đã chọn bằng hộp thoại.
    return "", "", "", _STATUS_HINT, [], ""


# Preset -> tham số (ánh xạ thẳng các giá trị mà backend label-parser hiểu).
# Trùng với presetOpts() trong bản thiết kế. forceOcr bật cho sách cờ, tắt cho
# tài liệu thường; translateVn & autosave luôn bật.
_PRESET_OPTS = {
    PRESET_SAVER: dict(merge=True, ocr_model="haiku", ocr_effort="low",
                       tr_model="haiku", tr_effort="low", dpi="250", pages="2"),
    PRESET_BALANCED: dict(merge=True, ocr_model="sonnet", ocr_effort="auto",
                          tr_model="haiku", tr_effort="low", dpi="250", pages="1"),
    PRESET_ACCURATE: dict(merge=False, ocr_model="opus", ocr_effort="high",
                          tr_model="sonnet", tr_effort="medium", dpi="400", pages="1"),
}


def _apply_preset(preset, mode_label):
    """Chọn preset/đổi chế độ -> tính lại toàn bộ tùy chọn nâng cao.

    Trả về update cho 4 công tắc + 6 dropdown + dòng gợi ý (đúng thứ tự khai
    báo `preset_outputs` trong build_ui).
    """
    opt = _PRESET_OPTS.get(preset, _PRESET_OPTS[PRESET_BALANCED])
    chess = _is_chess_mode(mode_label)
    return (
        gr.update(value=chess),            # force_ocr
        gr.update(value=True),             # translate_vn
        gr.update(value=opt["merge"]),     # merge_ocr_translate
        gr.update(value=True),             # autosave_on
        gr.update(value=opt["ocr_model"]),
        gr.update(value=opt["ocr_effort"]),
        gr.update(value=opt["tr_model"]),
        gr.update(value=opt["tr_effort"]),
        gr.update(value=opt["dpi"]),
        gr.update(value=opt["pages"]),
        gr.update(value=_PRESET_HINTS.get(preset, "")),  # preset_hint
    )


def _convert_btn_label(n):
    return f"Chuyển đổi {n} tệp" if n else "Chuyển đổi"


def _set_running(running):
    """Đang chạy -> ẩn nút Chuyển đổi, hiện nút Dừng (và ngược lại khi xong)."""
    return gr.update(visible=not running), gr.update(visible=running)


def _load_prefs(p):
    """BrowserState -> đặt lại preset/chế độ/thư mục lưu khi tải trang."""
    p = p or {}
    return (
        gr.update(value=p.get("preset", PRESET_BALANCED)),
        gr.update(value=p.get("mode", MODE_CHESS)),
        gr.update(value=p.get("dir") or os.path.join(os.path.expanduser("~"), "Downloads")),
    )


def _save_prefs(preset_v, mode_v, dir_v):
    """Gói lựa chọn hiện tại để lưu vào BrowserState (localStorage)."""
    return {"preset": preset_v, "mode": mode_v, "dir": dir_v}


def _on_files_change(files):
    """Kéo-thả tệp mới -> xoá lựa chọn từ hộp thoại + cập nhật nhãn nút."""
    n = len(files) if files else 0
    return [], "", gr.update(value=_convert_btn_label(n))


def build_ui():
    with gr.Blocks(title="MarkItDown") as demo:
        # ---- thanh tiêu đề navy (sticky) ----
        gr.HTML(TOPBAR_HTML)

        with gr.Row(elem_id="mid-workspace"):
            # ============ CỘT TRÁI — nhập liệu & điều khiển ============
            with gr.Column(elem_classes="mid-col-left"):

                # --- panel nhập liệu ---
                with gr.Group(elem_classes=["mid-card", "mid-input-card"]):
                    with gr.Tabs(elem_classes="mid-input-tabs"):
                        with gr.Tab("Từ tệp"):
                            gr.HTML(
                                '<div class="mid-drop-caption"><b>Kéo-thả tệp vào đây</b> '
                                "— hoặc bấm để chọn (PDF, Word, Excel, PPT, ảnh)</div>"
                            )
                            file_in = gr.File(
                                show_label=False,
                                type="filepath",
                                file_count="multiple",
                                height=130,
                                elem_id="mid-file",
                            )
                            picked_state = gr.State([])  # đường dẫn THẬT từ hộp thoại
                            btn_pick = gr.Button(
                                "Chọn tệp từ máy (giữ đường dẫn gốc để lưu cạnh file)",
                                elem_classes="mid-pick-btn",
                            )
                            picked_view = gr.Markdown(elem_classes="mid-picked-view")
                        with gr.Tab("Từ URL"):
                            url_in = gr.Textbox(
                                label="",
                                show_label=False,
                                placeholder="https://… hoặc link YouTube / Wikipedia",
                                info="Hỗ trợ YouTube, Wikipedia, RSS và trang web bất kỳ. Nội dung được tải về và chuyển thành Markdown.",
                                elem_classes="mid-url-box",
                            )
                            btn_url = gr.Button(
                                "Chuyển đổi URL", variant="primary", elem_id="mid-convert-url"
                            )

                # --- panel chế độ xử lý (thẻ HTML + radio ẩn để giữ backend) ---
                with gr.Group(elem_classes=["mid-card", "mid-mode-card"]):
                    gr.HTML('<div class="mid-section-title">Chế độ xử lý</div>')
                    gr.HTML(MODE_CARDS_HTML)
                    mode = gr.Radio(
                        choices=[MODE_CHESS, MODE_CHESS_RU, MODE_CHESS_ES, MODE_GENERAL],
                        value=MODE_CHESS,
                        show_label=False,
                        elem_id="mid-mode-radio",
                        elem_classes="mid-hidden",
                    )

                # --- panel chất lượng + chuyển đổi ---
                with gr.Group(elem_classes=["mid-card", "mid-quality-card"]):
                    with gr.Row(elem_classes="mid-quality-head"):
                        gr.HTML('<div class="mid-section-title">Mức chất lượng</div>')
                        preset_hint = gr.HTML(
                            _PRESET_HINTS[PRESET_BALANCED], elem_id="mid-preset-hint"
                        )
                    preset = gr.Radio(
                        choices=[PRESET_SAVER, PRESET_BALANCED, PRESET_ACCURATE],
                        value=PRESET_BALANCED,
                        show_label=False,
                        elem_id="mid-preset",
                        elem_classes="mid-preset",
                    )
                    btn_file = gr.Button(
                        "Chuyển đổi", variant="primary", elem_id="mid-convert"
                    )
                    btn_stop = gr.Button(
                        "⏹ Dừng", variant="stop", visible=False, elem_id="mid-stop"
                    )

                    with gr.Accordion(
                        "Tùy chọn nâng cao", open=False, elem_classes="mid-adv"
                    ):
                        force_ocr = gr.Checkbox(
                            label="Buộc OCR toàn bộ", value=True,
                            info="Bỏ lớp text rác trong PDF scan, OCR lại bằng Claude Code.",
                            elem_classes="mid-toggle", container=False,
                        )
                        translate_vn = gr.Checkbox(
                            label="Dịch sang tiếng Việt", value=True,
                            info="Tạo thêm tệp _vn.md. Ký hiệu cờ → V/H/X/T/M.",
                            elem_classes="mid-toggle", container=False,
                        )
                        merge_ocr_translate = gr.Checkbox(
                            label="OCR + dịch gộp 1 bước", value=True,
                            info="Mỗi trang vừa OCR vừa dịch — tiết kiệm ~30–40% hạn mức.",
                            elem_classes="mid-toggle", container=False,
                        )
                        autosave_on = gr.Checkbox(
                            label="Tự động lưu .md ra đĩa", value=True,
                            info="Lưu cạnh file gốc ngay khi mỗi tệp xong.",
                            elem_classes="mid-toggle", container=False,
                        )

                        gr.HTML('<div style="height:1px;background:var(--c-border);"></div>')

                        with gr.Row(elem_classes="mid-selects"):
                            ocr_model = gr.Dropdown(
                                choices=[("Haiku — nhanh", "haiku"),
                                         ("Sonnet — cân bằng", "sonnet"),
                                         ("Opus — chính xác", "opus")],
                                value="sonnet", label="Model OCR",
                                filterable=False, elem_classes="mid-select",
                            )
                            ocr_effort = gr.Dropdown(
                                choices=[("Thấp", "low"), ("Auto", "auto"),
                                         ("Trung bình", "medium"), ("Cao", "high")],
                                value="auto", label="Effort OCR",
                                filterable=False, elem_classes="mid-select",
                            )
                        with gr.Row(elem_classes="mid-selects"):
                            translate_model = gr.Dropdown(
                                choices=[("Haiku — tiết kiệm", "haiku"),
                                         ("Sonnet", "sonnet"), ("Opus", "opus")],
                                value="haiku", label="Model dịch",
                                filterable=False, elem_classes="mid-select",
                            )
                            translate_effort = gr.Dropdown(
                                choices=[("Thấp", "low"), ("Trung bình", "medium"),
                                         ("Cao", "high")],
                                value="low", label="Effort dịch",
                                filterable=False, elem_classes="mid-select",
                            )
                        with gr.Row(elem_classes="mid-selects"):
                            board_dpi = gr.Dropdown(
                                choices=[("250 — nhanh", "250"),
                                         ("400 — nét nhất", "400")],
                                value="250", label="DPI bàn cờ",
                                filterable=False, elem_classes="mid-select",
                            )
                            ocr_pages_per_call = gr.Dropdown(
                                choices=[("1 trang", "1"), ("2 trang", "2"),
                                         ("3 trang", "3")],
                                value="1", label="Trang / lần OCR",
                                filterable=False, elem_classes="mid-select",
                            )

                        gr.HTML('<div style="height:1px;background:var(--c-border);"></div>')

                        autosave_target = gr.Radio(
                            choices=[AUTOSAVE_SRC, AUTOSAVE_CUSTOM],
                            value=AUTOSAVE_SRC,
                            label="Nơi lưu .md",
                            elem_classes="mid-autosave-target",
                            info=(
                                "'Cùng thư mục với file gốc' chỉ áp dụng cho tệp chọn "
                                "bằng nút 'Chọn tệp từ máy'; tệp kéo-thả lùi về thư mục "
                                "tùy chọn bên dưới."
                            ),
                        )
                        autosave_dir = gr.Textbox(
                            label="Thư mục tùy chọn",
                            value=os.path.join(os.path.expanduser("~"), "Downloads"),
                            elem_classes="mid-autosave-dir",
                        )
                        # Plumbing ẩn — backend vẫn cần các giá trị này.
                        enable_plugins = gr.Checkbox(value=False, visible=False)
                        use_ocr = gr.Checkbox(value=True, visible=False)

            # ============ CỘT PHẢI — xem trước / kết quả ============
            with gr.Column(elem_classes="mid-col-right"):
                with gr.Group(elem_classes=["mid-card", "mid-preview-card"]):
                    status = gr.Markdown(_STATUS_HINT, elem_id="mid-status")
                    with gr.Tabs():
                        with gr.Tab("Xem trước"):
                            preview = gr.Markdown(elem_id="mid-preview")
                        with gr.Tab("Mã .md"):
                            raw = gr.Code(
                                language="markdown", show_label=False,
                                elem_id="mid-raw",
                            )
                    downloads = gr.HTML(elem_id="mid-downloads")
                btn_clear = gr.Button(
                    "Xóa kết quả", variant="secondary", elem_classes="mid-clear-btn"
                )

        # Ghi nhớ lựa chọn giữa các lần mở (lưu vào localStorage trình duyệt).
        prefs = gr.BrowserState(
            {
                "preset": PRESET_BALANCED,
                "mode": MODE_CHESS,
                "dir": os.path.join(os.path.expanduser("~"), "Downloads"),
            }
        )

        # ---------------- wiring sự kiện ----------------
        outputs = [preview, raw, downloads, status]
        preset_outputs = [
            force_ocr, translate_vn, merge_ocr_translate, autosave_on,
            ocr_model, ocr_effort, translate_model, translate_effort,
            board_dpi, ocr_pages_per_call, preset_hint,
        ]
        # Chọn preset / đổi chế độ -> tính lại tham số nâng cao.
        preset.change(_apply_preset, [preset, mode], preset_outputs)
        mode.change(_apply_preset, [preset, mode], preset_outputs)

        # Khôi phục lựa chọn đã lưu khi tải trang -> đặt component -> tính lại
        # tùy chọn nâng cao theo preset -> đồng bộ thẻ chế độ (HTML).
        demo.load(_load_prefs, prefs, [preset, mode, autosave_dir]).then(
            _apply_preset, [preset, mode], preset_outputs
        ).then(
            None, None, None,
            js="() => window.midSyncModeCards && window.midSyncModeCards()",
        )
        # Lưu lại mỗi khi đổi preset / chế độ / thư mục lưu.
        for _comp in (preset, mode, autosave_dir):
            _comp.change(_save_prefs, [preset, mode, autosave_dir], prefs)

        # Mở hộp thoại Windows -> nạp đường dẫn thật vào State + hiển thị.
        btn_pick.click(on_pick_files, None, [picked_state, picked_view]).then(
            lambda p: gr.update(value=_convert_btn_label(len(p) if p else 0)),
            picked_state, btn_file,
        )
        # Kéo-thả tệp mới -> xoá lựa chọn từ hộp thoại + cập nhật nhãn nút.
        file_in.change(_on_files_change, file_in, [picked_state, picked_view, btn_file])

        # Chuyển đổi tệp: bật chế độ "đang chạy" (hiện nút Dừng) -> chạy -> tắt.
        # `proc` là event generator cần nhắm tới khi Dừng (cancels), không phải
        # bước .then khôi phục nút ở cuối.
        proc = btn_file.click(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(
            on_convert_files,
            [
                file_in, mode, enable_plugins, use_ocr,
                ocr_model, ocr_effort, translate_model, translate_effort,
                force_ocr, board_dpi, translate_vn, merge_ocr_translate,
                ocr_pages_per_call, autosave_on, autosave_dir,
                picked_state, autosave_target,
            ],
            outputs,
            show_progress="full",
        )
        proc.then(lambda: _set_running(False), None, [btn_file, btn_stop])
        # Chuyển đổi URL cũng hiện nút Dừng (URL như YouTube có thể chậm).
        ev_url = btn_url.click(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(on_convert_url, [url_in, enable_plugins], outputs, show_progress="full")
        ev_url.then(lambda: _set_running(False), None, [btn_file, btn_stop])
        ev_urls = url_in.submit(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(on_convert_url, [url_in, enable_plugins], outputs, show_progress="full")
        ev_urls.then(lambda: _set_running(False), None, [btn_file, btn_stop])
        # Bấm Dừng -> hủy các tác vụ đang chạy + khôi phục nút Chuyển đổi.
        btn_stop.click(
            lambda: _set_running(False), None, [btn_file, btn_stop],
            cancels=[proc, ev_url, ev_urls],
        )
        btn_clear.click(on_clear, None, outputs + [picked_state, picked_view])

    return demo


if __name__ == "__main__":
    build_ui().launch(
        inbrowser=True, theme=THEME, css=CSS, head=HEAD,
        allowed_paths=[_OUTPUT_DIR, _ASSETS_DIR],
    )
