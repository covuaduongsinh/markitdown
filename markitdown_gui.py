# -*- coding: utf-8 -*-
"""
Màn hình (GUI web) chạy MarkItDown bằng Gradio.

Cách chạy:
    .venv\\Scripts\\python.exe markitdown_gui.py
hoặc nhấp đúp run_gui.bat

Sau khi chạy, mở trình duyệt tại http://127.0.0.1:7860
"""

import os
import re
import shutil
import tempfile
import traceback
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


def _download_panel(paths):
    """HTML danh sách tệp kết quả, mỗi tệp một nút tải riêng."""
    if not paths:
        return ""
    rows = []
    for p in paths:
        name = os.path.basename(p)
        href = "/gradio_api/file=" + quote(p.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row"><span class="dl-name">📝 {name}</span>'
            f'<a class="dl-btn" href="{href}" download="{name}">⬇️ Tải về</a></div>'
        )
    return (
        '<div class="dl-list"><div class="dl-title">⬇️ Tệp .md kết quả</div>'
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


def _model_from_label(label):
    """'opus (chính xác nhất)' -> 'opus'."""
    return (label or "opus").strip().split()[0].lower()


def _dpi_from_label(label):
    """'400 (nét nhất — mặc định)' -> 400; nhãn lạ -> 400."""
    try:
        return int((label or "").strip().split()[0])
    except (ValueError, IndexError):
        return 400


def _ocr_to_outputs(file_path, base_name, model, board_dpi=400, used_paths=None):
    """Chạy OCR (PDF hoặc ảnh) qua Claude Code và trả về 4-tuple kết quả."""
    import claude_ocr

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = claude_ocr.ocr_pdf(file_path, model=model, board_dpi=board_dpi)
    else:
        text = claude_ocr.ocr_image_file(file_path, model=model)

    if not text.strip():
        return "", "", None, "⚠️ OCR xong nhưng không trích được nội dung."

    download_path = _write_md(text, base_name, used_paths)
    status = f"✅ Đã OCR bằng Claude Code (model: {model}) — {len(text):,} ký tự"
    return text, text, download_path, status


def convert_file(
    file_path, enable_plugins, use_ocr, model_label, force_ocr=False,
    board_dpi_label=None, used_paths=None,
):
    if not file_path:
        return "", "", None, "ℹ️ Hãy chọn hoặc kéo-thả một tệp trước."

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    ext = os.path.splitext(file_path)[1].lower()
    model = _model_from_label(model_label)
    board_dpi = _dpi_from_label(board_dpi_label)
    is_image = ext in IMAGE_EXTS
    is_pdf = ext == ".pdf"

    # Ảnh: built-in chỉ ra metadata/mô tả, nên OCR trực tiếp nếu được bật.
    if use_ocr and is_image:
        from claude_ocr import find_claude

        if not find_claude():
            # Không có Claude Code -> vẫn thử chuyển đổi thường (ra metadata).
            return _convert(file_path, enable_plugins, base_name, used_paths)
        try:
            return _ocr_to_outputs(file_path, base_name, model, board_dpi, used_paths)
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
            return _ocr_to_outputs(file_path, base_name, model, board_dpi, used_paths)
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
            return _ocr_to_outputs(file_path, base_name, model, board_dpi, used_paths)
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


THEME = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="violet",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
)

CSS = """
.gradio-container { max-width: 1280px !important; margin: 0 auto; }
#hero {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 60%, #9333ea 100%);
    color: #fff;
    border-radius: 14px;
    padding: 12px 20px;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 18px;
}
#hero h1 { margin: 0; font-size: 1.3rem; color: #fff; }
#hero p { margin: 0; font-size: .9rem; opacity: .9; flex: 1 1 auto; }
#hero .badges { display: flex; flex-wrap: wrap; gap: 5px; }
#hero .badges span {
    background: rgba(255, 255, 255, .16);
    border: 1px solid rgba(255, 255, 255, .25);
    border-radius: 999px;
    padding: 2px 10px;
    font-size: .72rem;
    white-space: nowrap;
}
#status-box {
    border: 1px solid var(--border-color-primary);
    background: var(--background-fill-secondary);
    border-radius: 12px;
    padding: 8px 14px;
}
.dl-list {
    border: 1px solid var(--border-color-primary);
    background: var(--background-fill-secondary);
    border-radius: 12px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.dl-title { font-weight: 600; margin-bottom: 2px; }
.dl-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    border: 1px solid var(--border-color-primary);
    background: var(--background-fill-primary);
    border-radius: 8px;
    padding: 5px 10px;
}
.dl-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.dl-btn {
    flex: 0 0 auto;
    background: #4f46e5;
    color: #fff !important;
    text-decoration: none !important;
    border-radius: 999px;
    padding: 4px 14px;
    font-size: .85rem;
    font-weight: 600;
    white-space: nowrap;
}
.dl-btn:hover { background: #4338ca; }
"""

HERO_HTML = """
<div id="hero">
    <h1>📄 ➜ 📝 MarkItDown</h1>
    <p>Chuyển tài liệu hoặc đường link sang <b>Markdown</b> — chạy cục bộ trên máy bạn.</p>
    <div class="badges">
        <span>PDF</span><span>Word</span><span>Excel</span><span>PowerPoint</span>
        <span>Ảnh</span><span>URL / YouTube</span><span>+ nhiều nữa</span>
    </div>
</div>
"""

_STATUS_HINT = "👋 Chọn tệp hoặc dán URL rồi bấm **Chuyển đổi**."


def _with_download_update(result):
    """Đổi đường dẫn tải về thành bảng HTML chứa nút tải."""
    preview_md, raw_md, path, status_md = result
    return preview_md, raw_md, _download_panel([path] if path else []), status_md


def _translate_to_vn(raw_md, orig_path, model, done_paths):
    """Dịch raw_md sang tiếng Việt, ghi tệp `<tên gốc>_vn.md`.

    Trả về (đường dẫn tệp _vn hoặc None, dòng status).
    """
    import claude_translate
    from claude_ocr import find_claude

    if not find_claude():
        return None, "⚠️ Bỏ qua dịch: cần Claude Code (lệnh 'claude') trong PATH."
    try:
        vn_text = claude_translate.translate_markdown_vn(raw_md, model=model)
        vn_name = os.path.splitext(os.path.basename(orig_path))[0] + "_vn"
        vn_path = _write_md(vn_text, vn_name, done_paths)
        return vn_path, f"🇻🇳 Đã dịch sang tiếng Việt — {len(vn_text):,} ký tự"
    except Exception as exc:
        return None, f"⚠️ Lỗi dịch sang tiếng Việt: {exc}"


def on_convert_files(
    file_paths, enable_plugins, use_ocr, model_label, force_ocr, board_dpi_label,
    translate_vn, autosave_on, autosave_dir,
):
    if not file_paths:
        yield "", "", "", "ℹ️ Hãy chọn hoặc kéo-thả ít nhất một tệp trước."
        return

    total = len(file_paths)
    n_ok = 0  # số tệp nguồn chuyển đổi thành công (không tính tệp _vn)
    done_paths, previews, raws, lines = [], [], [], []

    for i, fp in enumerate(file_paths, 1):
        name = os.path.basename(fp)
        # Báo tiến độ trước khi xử lý, giữ nguyên kết quả các tệp đã xong.
        progress = "\n\n".join(lines + [f"⏳ Đang xử lý {i}/{total}: **{name}**…"])
        yield (
            "\n\n---\n\n".join(previews),
            "\n\n".join(raws),
            _download_panel(done_paths),
            progress,
        )

        preview, raw_md, path, st = convert_file(
            fp, enable_plugins, use_ocr, model_label, force_ocr, board_dpi_label,
            used_paths=done_paths,
        )
        if path and autosave_on:
            saved, err = _autosave(path, autosave_dir)
            st += f"\n  💾 đã lưu: `{saved}`" if saved else f"\n  {err}"
        if path:
            n_ok += 1
            done_paths.append(path)

        # Dịch sang tiếng Việt -> tạo thêm tệp _vn.md (nếu được bật).
        if translate_vn and path and (raw_md or "").strip():
            progress = "\n\n".join(
                lines + [f"**{name}** — {st}",
                         f"⏳ Đang dịch sang tiếng Việt {i}/{total}: **{name}**…"]
            )
            yield (
                "\n\n---\n\n".join(previews),
                "\n\n".join(raws),
                _download_panel(done_paths),
                progress,
            )
            model = _model_from_label(model_label)
            vn_path, vn_st = _translate_to_vn(raw_md, path, model, done_paths)
            st += f"\n  {vn_st}"
            if vn_path:
                if autosave_on:
                    saved, err = _autosave(vn_path, autosave_dir)
                    st += f" · 💾 đã lưu: `{saved}`" if saved else f"\n  {err}"
                done_paths.append(vn_path)
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
    return "", "", "", _STATUS_HINT


def build_ui():
    with gr.Blocks(title="MarkItDown") as demo:
        gr.HTML(HERO_HTML)

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=340):
                with gr.Tabs():
                    with gr.Tab("📁 Từ tệp"):
                        file_in = gr.File(
                            label="Kéo-thả một hoặc nhiều tệp vào đây, hoặc bấm để chọn",
                            type="filepath",
                            file_count="multiple",
                            height=170,
                        )
                        btn_file = gr.Button(
                            "🚀 Chuyển đổi", variant="primary", size="lg"
                        )
                        autosave_on = gr.Checkbox(
                            label="💾 Tự động lưu .md vào thư mục bên dưới khi mỗi tệp xong",
                            value=True,
                        )
                        autosave_dir = gr.Textbox(
                            label="Thư mục lưu kết quả",
                            value=os.path.join(
                                os.path.expanduser("~"), "Downloads"
                            ),
                        )
                    with gr.Tab("🔗 Từ URL"):
                        url_in = gr.Textbox(
                            label="URL",
                            placeholder="https://en.wikipedia.org/wiki/... hoặc link YouTube",
                            info="Hỗ trợ YouTube, Wikipedia, RSS và trang web bất kỳ. Nhấn Enter để chuyển đổi ngay.",
                        )
                        btn_url = gr.Button(
                            "🚀 Chuyển đổi", variant="primary", size="lg"
                        )

                with gr.Accordion("⚙️ Tùy chọn", open=False):
                    enable_plugins = gr.Checkbox(
                        label="Bật plugin của bên thứ ba (3rd-party plugins)",
                        value=False,
                        info="Cho phép MarkItDown nạp các plugin chuyển đổi được cài thêm.",
                    )
                    use_ocr = gr.Checkbox(
                        label="Tự động OCR PDF/ảnh scan bằng Claude Code",
                        value=True,
                        info=(
                            "Khi PDF/ảnh không có lớp text, dùng phiên đăng nhập Claude Code "
                            "hiện tại để OCR — không cần API key. Mỗi trang là một lần gọi "
                            "`claude`, có thể mất vài chục giây và tiêu tốn hạn mức subscription. "
                            "Hình bàn cờ vua sẽ tự động chuyển thành block `chessboard` (FEN) "
                            "dùng được với plugin Chessboard Viewer trong Obsidian."
                        ),
                    )
                    force_ocr = gr.Checkbox(
                        label="Buộc OCR toàn bộ (bỏ qua lớp text có sẵn trong PDF)",
                        value=True,
                        info=(
                            "Dùng khi PDF scan có sẵn lớp text rác (OCR cũ kém chất lượng) "
                            "khiến kết quả chuyển đổi thường bị lỗi — vd: sách cờ vua scan."
                        ),
                    )
                    translate_vn = gr.Checkbox(
                        label="🇻🇳 Dịch kết quả sang tiếng Việt (tạo thêm tệp _vn.md)",
                        value=True,
                        info=(
                            "Sau khi tạo tệp .md gốc, dịch sang tiếng Việt bằng Claude "
                            "Code và ghi thêm tệp cùng tên có hậu tố _vn. Ký hiệu nước "
                            "đi chuyển sang tiếng Việt (V/H/X/T/M), block FEN bàn cờ "
                            "giữ nguyên không dịch. Bỏ tích nếu không cần dịch."
                        ),
                    )
                    ocr_model = gr.Dropdown(
                        choices=["opus (chính xác nhất)", "sonnet (nhanh/nhẹ hơn)"],
                        value="opus (chính xác nhất)",
                        label="Model Claude dùng để OCR",
                    )
                    board_dpi = gr.Dropdown(
                        choices=[
                            "400 (nét nhất)",
                            "250 (nhanh hơn ~2.5× — mặc định)",
                        ],
                        value="250 (nhanh hơn ~2.5× — mặc định)",
                        label="DPI render trang để nhận diện bàn cờ",
                        info=(
                            "Model nhận diện chỉ nhìn ảnh ≤512px nên 250 DPI "
                            "thường cho kết quả tương đương mà render nhanh hơn "
                            "hẳn; chọn 400 nếu sơ đồ in nhỏ/mờ."
                        ),
                    )

                status = gr.Markdown(_STATUS_HINT, elem_id="status-box")

                downloads = gr.HTML()
                btn_clear = gr.Button("🗑️ Xóa kết quả", variant="secondary")

            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.Tab("👁️ Xem trước"):
                        preview = gr.Markdown(height=560)
                    with gr.Tab("📝 Mã Markdown"):
                        raw = gr.Code(
                            label="Markdown (.md)", language="markdown", max_lines=24
                        )

        outputs = [preview, raw, downloads, status]
        btn_file.click(
            on_convert_files,
            [
                file_in, enable_plugins, use_ocr, ocr_model, force_ocr,
                board_dpi, translate_vn, autosave_on, autosave_dir,
            ],
            outputs,
            show_progress="full",
        )
        btn_url.click(
            on_convert_url, [url_in, enable_plugins], outputs, show_progress="full"
        )
        url_in.submit(
            on_convert_url, [url_in, enable_plugins], outputs, show_progress="full"
        )
        btn_clear.click(on_clear, None, outputs)

    return demo


if __name__ == "__main__":
    build_ui().launch(
        inbrowser=True, theme=THEME, css=CSS, allowed_paths=[_OUTPUT_DIR]
    )
