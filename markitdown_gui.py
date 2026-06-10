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
import tempfile
import traceback

import gradio as gr
from markitdown import MarkItDown

# Thư mục tạm để chứa các tệp .md xuất ra (cho nút tải về)
_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "markitdown_gui_output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    """Bỏ ký tự không hợp lệ trong tên tệp Windows."""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", name).strip().strip(".")
    return name or "ketqua"


def _write_md(markdown: str, base_name: str) -> str:
    """Ghi nội dung Markdown ra tệp .md trong thư mục tạm, trả về đường dẫn."""
    out_path = os.path.join(_OUTPUT_DIR, _safe_filename(base_name) + ".md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return out_path


def _convert(source, enable_plugins, base_name):
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
        download_path = _write_md(text, name)

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


def _ocr_to_outputs(file_path, base_name, model, board_dpi=400):
    """Chạy OCR (PDF hoặc ảnh) qua Claude Code và trả về 4-tuple kết quả."""
    import claude_ocr

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = claude_ocr.ocr_pdf(file_path, model=model, board_dpi=board_dpi)
    else:
        text = claude_ocr.ocr_image_file(file_path, model=model)

    if not text.strip():
        return "", "", None, "⚠️ OCR xong nhưng không trích được nội dung."

    download_path = _write_md(text, base_name)
    status = f"✅ Đã OCR bằng Claude Code (model: {model}) — {len(text):,} ký tự"
    return text, text, download_path, status


def convert_file(
    file_path, enable_plugins, use_ocr, model_label, force_ocr=False,
    board_dpi_label=None,
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
            return _convert(file_path, enable_plugins, base_name)
        try:
            return _ocr_to_outputs(file_path, base_name, model, board_dpi)
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
            return _ocr_to_outputs(file_path, base_name, model, board_dpi)
        except Exception as exc:
            return "", "", None, f"❌ Lỗi OCR: {exc}"

    # Chuyển đổi thường trước.
    preview, raw_md, download, status = _convert(file_path, enable_plugins, base_name)

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
            return _ocr_to_outputs(file_path, base_name, model, board_dpi)
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
    """Đổi đường dẫn tải về thành cập nhật ẩn/hiện cho DownloadButton."""
    preview_md, raw_md, path, status_md = result
    if path:
        dl = gr.DownloadButton(value=path, visible=True)
    else:
        dl = gr.DownloadButton(visible=False)
    return preview_md, raw_md, dl, status_md


def on_convert_file(
    file_path, enable_plugins, use_ocr, model_label, force_ocr, board_dpi_label
):
    return _with_download_update(
        convert_file(
            file_path, enable_plugins, use_ocr, model_label, force_ocr,
            board_dpi_label,
        )
    )


def on_convert_url(url, enable_plugins):
    return _with_download_update(convert_url(url, enable_plugins))


def on_clear():
    return "", "", gr.DownloadButton(visible=False), _STATUS_HINT


def build_ui():
    with gr.Blocks(title="MarkItDown") as demo:
        gr.HTML(HERO_HTML)

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=340):
                with gr.Tabs():
                    with gr.Tab("📁 Từ tệp"):
                        file_in = gr.File(
                            label="Kéo-thả tệp vào đây hoặc bấm để chọn",
                            type="filepath",
                            height=170,
                        )
                        btn_file = gr.Button(
                            "🚀 Chuyển đổi", variant="primary", size="lg"
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
                        value=False,
                        info=(
                            "Dùng khi PDF scan có sẵn lớp text rác (OCR cũ kém chất lượng) "
                            "khiến kết quả chuyển đổi thường bị lỗi — vd: sách cờ vua scan."
                        ),
                    )
                    ocr_model = gr.Dropdown(
                        choices=["opus (chính xác nhất)", "sonnet (nhanh/nhẹ hơn)"],
                        value="opus (chính xác nhất)",
                        label="Model Claude dùng để OCR",
                    )
                    board_dpi = gr.Dropdown(
                        choices=[
                            "400 (nét nhất — mặc định)",
                            "250 (nhanh hơn ~2.5×)",
                        ],
                        value="400 (nét nhất — mặc định)",
                        label="DPI render trang để nhận diện bàn cờ",
                        info=(
                            "Model nhận diện chỉ nhìn ảnh ≤512px nên 250 DPI "
                            "thường cho kết quả tương đương mà render nhanh hơn "
                            "hẳn; chọn 400 nếu sơ đồ in nhỏ/mờ."
                        ),
                    )

                status = gr.Markdown(_STATUS_HINT, elem_id="status-box")

                with gr.Row():
                    download = gr.DownloadButton("⬇️ Tải tệp .md", visible=False)
                    btn_clear = gr.Button("🗑️ Xóa kết quả", variant="secondary")

            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.Tab("👁️ Xem trước"):
                        preview = gr.Markdown(height=560)
                    with gr.Tab("📝 Mã Markdown"):
                        raw = gr.Code(
                            label="Markdown (.md)", language="markdown", max_lines=24
                        )

        outputs = [preview, raw, download, status]
        btn_file.click(
            on_convert_file,
            [file_in, enable_plugins, use_ocr, ocr_model, force_ocr, board_dpi],
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
    build_ui().launch(inbrowser=True, theme=THEME, css=CSS)
