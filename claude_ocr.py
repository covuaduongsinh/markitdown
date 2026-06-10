# -*- coding: utf-8 -*-
"""
OCR cho PDF / ảnh scan bằng Claude Code ở chế độ headless (KHÔNG cần API key).

Ý tưởng: render từng trang PDF thành ảnh PNG, rồi gọi `claude -p` (Claude Code)
để đọc ảnh (qua tool Read) và trích toàn bộ văn bản ra Markdown. Xác thực bằng
phiên đăng nhập Claude Code hiện có của người dùng.

Phụ thuộc: pypdfium2 + Pillow (đã có sẵn trong venv qua markitdown[all]),
và CLI `claude` (Claude Code) trong PATH.
"""

import json
import os
import shutil
import subprocess
import tempfile

# Ánh xạ nhãn model trên giao diện -> alias dùng cho `--model`
MODEL_ALIASES = {"opus", "sonnet", "haiku"}

PROMPT_VI = (
    "Hãy đọc ảnh tài liệu tại đường dẫn: {path}\n\n"
    "Đây có thể là tài liệu tiếng Việt được scan, có thể có watermark hoặc dấu mộc. "
    "Nhiệm vụ của bạn là OCR: trích xuất TOÀN BỘ nội dung văn bản nhìn thấy trong ảnh "
    "và trình bày lại dưới dạng Markdown, giữ đúng cấu trúc (tiêu đề, đoạn văn, bảng, "
    "danh sách). Bỏ qua hoa văn/watermark trang trí. "
    "CHỈ trả về nội dung Markdown đã trích, KHÔNG thêm lời mở đầu, giải thích hay nhận xét."
)


class ClaudeOCRError(RuntimeError):
    """Lỗi trong quá trình OCR bằng Claude Code."""


def find_claude():
    """Trả về đường dẫn tới CLI `claude`, hoặc None nếu không có trong PATH."""
    return shutil.which("claude")


def render_pdf_to_pngs(pdf_path, out_dir, dpi=200):
    """Render từng trang PDF thành PNG trong out_dir. Trả về danh sách đường dẫn PNG."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    scale = dpi / 72.0
    paths = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            pil = page.render(scale=scale).to_pil().convert("RGB")
            out_path = os.path.join(out_dir, f"page_{i + 1:03d}.png")
            pil.save(out_path, format="PNG")
            paths.append(out_path)
    finally:
        pdf.close()
    return paths


def ocr_image_path(img_path, model="opus", timeout=300):
    """Gọi Claude Code headless để OCR một ảnh. Trả về Markdown trích được."""
    claude = find_claude()
    if not claude:
        raise ClaudeOCRError(
            "Không tìm thấy Claude Code (lệnh 'claude') trong PATH. "
            "Hãy đảm bảo Claude Code đã được cài và đăng nhập."
        )

    img_path = os.path.abspath(img_path)
    img_dir = os.path.dirname(img_path)
    prompt = PROMPT_VI.format(path=img_path)

    cmd = [
        claude,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--add-dir",
        img_dir,
        "--model",
        model,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=img_dir,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeOCRError(f"Claude Code quá thời gian ({timeout}s) khi OCR.") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        raise ClaudeOCRError(f"Claude Code lỗi (exit {proc.returncode}): {detail}")

    out = (proc.stdout or "").strip()
    if not out:
        raise ClaudeOCRError("Claude Code không trả về dữ liệu.")

    # --output-format json: stdout là một object có trường 'result' chứa văn bản cuối.
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # Phòng khi đầu ra không phải JSON thuần (lẫn log) -> dùng nguyên văn.
        return out

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            return result.strip()
    return out


def ocr_pdf(pdf_path, model="opus", dpi=200, progress=None, page_timeout=300):
    """OCR toàn bộ PDF scan. Trả về Markdown ghép các trang."""
    tmp_dir = tempfile.mkdtemp(prefix="mid_ocr_")
    try:
        pngs = render_pdf_to_pngs(pdf_path, tmp_dir, dpi=dpi)
        if not pngs:
            raise ClaudeOCRError("Không render được trang nào từ PDF.")
        parts = []
        for i, png in enumerate(pngs, 1):
            if progress is not None:
                progress(i, len(pngs))
            text = ocr_image_path(png, model=model, timeout=page_timeout)
            if text.strip():
                parts.append(f"## Trang {i}\n\n{text.strip()}")
            else:
                parts.append(f"## Trang {i}\n\n*[Không trích được nội dung]*")
        return "\n\n".join(parts).strip()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ocr_image_file(img_path, model="opus", page_timeout=300):
    """OCR một tệp ảnh đơn lẻ (jpg/png...)."""
    return ocr_image_path(img_path, model=model, timeout=page_timeout)
