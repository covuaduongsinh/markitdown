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
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import chessboard_fen  # nhận diện bàn cờ -> FEN cục bộ bằng model ONNX
except Exception:
    chessboard_fen = None

# Ánh xạ nhãn model trên giao diện -> alias dùng cho `--model`
MODEL_ALIASES = {"opus", "sonnet", "haiku"}

_PROMPT_HEADER = (
    "Hãy đọc ảnh tài liệu tại đường dẫn: {path}\n\n"
    "Đây có thể là tài liệu tiếng Việt được scan, có thể có watermark hoặc dấu mộc. "
    "Nhiệm vụ của bạn là OCR: trích xuất TOÀN BỘ nội dung văn bản nhìn thấy trong ảnh "
    "và trình bày lại dưới dạng Markdown, giữ đúng cấu trúc (tiêu đề, đoạn văn, bảng, "
    "danh sách). Bỏ qua hoa văn/watermark trang trí.\n\n"
)

_PROMPT_BLOCK_RULES = (
    "Quy tắc BẮT BUỘC cho block: không dùng dấu nháy kép; FEN nằm trên đúng 1 dòng; "
    "có đúng 1 dấu cách sau 'fen:'; không thêm bất kỳ chữ nào khác trong block.\n"
    "Ví dụ block đúng:\n"
    "```chessboard\n"
    "fen: r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3\n"
    "```\n\n"
)

# Trang chưa có FEN tính sẵn -> Claude tự nhận diện hình cờ (fallback).
_PROMPT_CHESS_SELF = (
    "NẾU trong ảnh có hình bàn cờ vua (diagram), với MỖI hình hãy làm như sau:\n"
    "1. Quan sát kỹ TỪNG Ô từ a1 đến h8 để xác định chính xác vị trí từng quân cờ. "
    "Nếu hình có in tọa độ (a-h, 1-8) thì dựa vào đó để xác định hướng bàn cờ; "
    "nếu không có tọa độ, mặc định Trắng ở phía dưới.\n"
    "2. Sinh chuỗi FEN ĐẦY ĐỦ 6 trường. Lượt đi: suy ra từ chú thích quanh hình "
    "('Trắng đi', 'Đen đi trước', hoặc nước tiếp theo trong văn bản dạng '1...' nghĩa là "
    "Đen đi) — nếu không rõ thì dùng w. Quyền nhập thành: ghi - trừ khi suy ra được chắc "
    "chắn. Ô bắt tốt qua đường: -. Số nước nửa: 0. Số nước đầy đủ: lấy theo số nước đi "
    "trong văn bản nếu rõ, nếu không thì 1.\n"
    "3. Ngay tại vị trí hình cờ trong trang (TRƯỚC phần nước đi liên quan), xuất một code "
    "block như sau.\n\n"
    "Nếu thế cờ có đủ 2 quân Vua (đúng 1 Vua trắng và 1 Vua đen):\n"
    "```chessboard\n"
    "fen: <giá trị FEN>\n"
    "```\n\n"
    "Nếu thế cờ KHÔNG có đủ 2 quân Vua:\n"
    "```chessboard\n"
    "fen: <giá trị FEN>\n"
    "strict: false\n"
    "```\n\n"
) + _PROMPT_BLOCK_RULES

# Trang đã có FEN nhận diện sẵn bằng model ONNX -> Claude chỉ chèn đúng chỗ.
_PROMPT_CHESS_GIVEN = (
    "Trang này có {n} hình bàn cờ vua. FEN của từng hình ĐÃ ĐƯỢC nhận diện sẵn bằng "
    "công cụ chuyên dụng, liệt kê theo thứ tự xuất hiện trên trang (trên xuống dưới, "
    "cùng hàng thì trái sang phải):\n"
    "{fen_list}\n\n"
    "Khi gặp hình bàn cờ thứ i trong trang, hãy chèn NGAY TẠI VỊ TRÍ hình đó (TRƯỚC "
    "phần nước đi liên quan) một code block dùng NGUYÊN VĂN FEN tương ứng — KHÔNG tự "
    "nhận diện lại bàn cờ, KHÔNG sửa FEN đã cho:\n\n"
    "```chessboard\n"
    "fen: <FEN thứ i>\n"
    "```\n\n"
    "Riêng lượt đi trong FEN: nếu chú thích quanh hình hoặc nước đi tiếp theo cho thấy "
    "Đen đi trước ('Đen đi', nước kế tiếp dạng '1...') thì đổi trường lượt đi của FEN "
    "từ w thành b; ngoài ra giữ nguyên.\n"
    "Nếu thế cờ KHÔNG có đủ 2 quân Vua (đúng 1 Vua trắng và 1 Vua đen) thì thêm dòng "
    "`strict: false` ngay dưới dòng fen.\n\n"
) + _PROMPT_BLOCK_RULES + (
    "Nếu trong trang có NHIỀU hình bàn cờ hơn danh sách trên, các hình thừa hãy tự "
    "nhận diện từng ô theo khả năng tốt nhất, cùng định dạng block.\n\n"
)

_PROMPT_FOOTER = (
    "Về ký hiệu nước đi cờ vua trong văn bản: giữ NGUYÊN VĂN như sách in (số thứ tự nước "
    "'12.' hoặc '12...', các ký hiệu đánh giá !, ?, !!, ??, !?, ?!, ±, =, +-, -+...). "
    "Nếu sách in quân cờ bằng hình (figurine) thì chuyển về chữ cái SAN quốc tế tương ứng "
    "K, Q, R, B, N. KHÔNG diễn giải hay bình luận thêm về nước đi.\n\n"
    "CHỈ trả về nội dung Markdown đã trích, KHÔNG thêm lời mở đầu, giải thích hay nhận xét."
)

# Giữ tên cũ cho tương thích (prompt khi Claude phải tự nhận diện bàn cờ).
PROMPT_VI = _PROMPT_HEADER + _PROMPT_CHESS_SELF + _PROMPT_FOOTER


def _build_prompt(img_path, board_fens=None):
    """Ghép prompt OCR: có FEN tính sẵn thì yêu cầu dùng nguyên văn."""
    if board_fens:
        fen_list = "\n".join(f"{i}. {fen}" for i, fen in enumerate(board_fens, 1))
        chess_part = _PROMPT_CHESS_GIVEN.format(n=len(board_fens), fen_list=fen_list)
    else:
        chess_part = _PROMPT_CHESS_SELF
    return _PROMPT_HEADER.format(path=img_path) + chess_part + _PROMPT_FOOTER

# --- Hậu kiểm block ```chessboard --------------------------------------------

_CHESSBOARD_BLOCK_RE = re.compile(r"```[ \t]*chessboard[^\n]*\n(.*?)```", re.DOTALL)
_FEN_FIELD_RE = re.compile(r"fen\s*:\s*(.+)", re.IGNORECASE)
_FEN_DEFAULT_TAIL = ["w", "-", "-", "0", "1"]


def _board_field_valid(board):
    """Kiểm tra trường vị trí quân của FEN: 8 hàng, mỗi hàng đủ 8 ô, ký tự hợp lệ."""
    ranks = board.split("/")
    if len(ranks) != 8:
        return False
    for rank in ranks:
        total = 0
        for ch in rank:
            if ch in "12345678":
                total += int(ch)
            elif ch in "pnbrqkPNBRQK":
                total += 1
            else:
                return False
        if total != 8:
            return False
    return True


def _normalize_chessboard_blocks(md):
    """Ép các block ```chessboard về đúng định dạng plugin Chessboard Viewer (Obsidian).

    - Bỏ dấu nháy kép/khoảng trắng thừa quanh FEN, gộp FEN về 1 dòng.
    - Bổ sung các trường còn thiếu cho đủ 6 trường FEN.
    - Đủ đúng 2 Vua (1 K + 1 k) -> block thường; ngược lại -> thêm `strict: false`.
    - FEN hỏng -> giữ nguyên block, chèn cảnh báo ngay sau để người dùng kiểm tra.
    """

    def fix(match):
        body = match.group(1)
        m = _FEN_FIELD_RE.search(body)
        if not m:
            return match.group(0)

        fen = m.group(1).strip().strip("\"'").strip()
        fen = " ".join(fen.split())
        fields = fen.split(" ")
        board = fields[0]

        if not _board_field_valid(board):
            return (
                match.group(0)
                + "\n\n*[Cảnh báo: FEN ở trên có thể sai, hãy đối chiếu lại với hình cờ]*"
            )

        # Trường lượt đi không phải w/b -> phần đuôi là rác, thay bằng mặc định.
        if len(fields) >= 2 and fields[1] not in ("w", "b"):
            fields = [board]
        if len(fields) < 6:
            fields = fields + _FEN_DEFAULT_TAIL[len(fields) - 1 :]
        fen = " ".join(fields[:6])

        if board.count("K") == 1 and board.count("k") == 1:
            return "```chessboard\nfen: " + fen + "\n```"
        return "```chessboard\nfen: " + fen + "\nstrict: false\n```"

    return _CHESSBOARD_BLOCK_RE.sub(fix, md)


class ClaudeOCRError(RuntimeError):
    """Lỗi trong quá trình OCR bằng Claude Code."""


def find_claude():
    """Trả về đường dẫn tới CLI `claude`, hoặc None nếu không có trong PATH."""
    return shutil.which("claude")


# DPI cao để nhận diện bàn cờ (cắt hình nét); DPI thấp cho OCR cả trang.
BOARD_DPI = 400


def _render_page_pair(page, out_dir, page_no, ocr_dpi=200):
    """Render 1 trang PDF: trả về (đường dẫn PNG ocr_dpi, ảnh PIL BOARD_DPI)."""
    from PIL import Image

    hi = page.render(scale=BOARD_DPI / 72.0).to_pil().convert("RGB")
    lo = hi.resize(
        (
            max(1, hi.width * ocr_dpi // BOARD_DPI),
            max(1, hi.height * ocr_dpi // BOARD_DPI),
        ),
        Image.LANCZOS,
    )
    out_path = os.path.join(out_dir, f"page_{page_no:03d}.png")
    lo.save(out_path, format="PNG")
    return out_path, hi


def _page_board_fens(pil_page):
    """Nhận diện FEN các hình bàn cờ trên trang bằng model ONNX cục bộ.

    Trả về list FEN theo thứ tự đọc, hoặc None nếu không có công cụ/lỗi
    (caller sẽ để Claude tự nhận diện như cũ).
    """
    if chessboard_fen is None or not chessboard_fen.available():
        return None
    try:
        return [fen for _box, fen in chessboard_fen.fens_for_page(pil_page)]
    except Exception as exc:
        print(f"[chessboard_fen] Lỗi nhận diện bàn cờ: {exc}", file=sys.stderr)
        return None


def ocr_image_path(img_path, model="opus", timeout=600, board_fens=None):
    """Gọi Claude Code headless để OCR một ảnh. Trả về Markdown trích được.

    board_fens: danh sách FEN của các hình bàn cờ trên trang (đã nhận diện cục
    bộ bằng model ONNX, theo thứ tự đọc) — Claude sẽ dùng nguyên văn thay vì tự
    nhận diện.
    """
    claude = find_claude()
    if not claude:
        raise ClaudeOCRError(
            "Không tìm thấy Claude Code (lệnh 'claude') trong PATH. "
            "Hãy đảm bảo Claude Code đã được cài và đăng nhập."
        )

    img_path = os.path.abspath(img_path)
    img_dir = os.path.dirname(img_path)
    prompt = _build_prompt(img_path, board_fens)

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
            stdin=subprocess.DEVNULL,
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
        return _normalize_chessboard_blocks(out)

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            return _normalize_chessboard_blocks(result.strip())
    return _normalize_chessboard_blocks(out)


def ocr_pdf(pdf_path, model="opus", dpi=200, progress=None, page_timeout=600):
    """OCR toàn bộ PDF scan. Trả về Markdown ghép các trang.

    Mỗi trang: nhận diện hình bàn cờ -> FEN cục bộ bằng model ONNX (không tốn
    quota Claude), rồi OCR văn bản bằng Claude với FEN đã tính sẵn.
    Trang nào lỗi (quá thời gian, claude trục trặc...) sẽ được thử lại 1 lần;
    vẫn lỗi thì ghi chú vào kết quả và TIẾP TỤC các trang sau, không hủy cả file.
    """
    import pypdfium2 as pdfium

    tmp_dir = tempfile.mkdtemp(prefix="mid_ocr_")
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            n_pages = len(pdf)
            if n_pages == 0:
                raise ClaudeOCRError("PDF không có trang nào.")
            parts = []
            n_failed = 0
            for i in range(1, n_pages + 1):
                if progress is not None:
                    progress(i, n_pages)
                png, hi_res = _render_page_pair(pdf[i - 1], tmp_dir, i, ocr_dpi=dpi)
                board_fens = _page_board_fens(hi_res)
                del hi_res  # giải phóng ảnh 400 DPI trước khi gọi Claude
                try:
                    text = ocr_image_path(
                        png, model=model, timeout=page_timeout, board_fens=board_fens
                    )
                except ClaudeOCRError:
                    try:  # thử lại 1 lần rồi mới bỏ qua trang
                        text = ocr_image_path(
                            png, model=model, timeout=page_timeout, board_fens=board_fens
                        )
                    except ClaudeOCRError as exc:
                        n_failed += 1
                        parts.append(f"## Trang {i}\n\n*[Lỗi OCR trang này: {exc}]*")
                        continue
                if text.strip():
                    parts.append(f"## Trang {i}\n\n{text.strip()}")
                else:
                    parts.append(f"## Trang {i}\n\n*[Không trích được nội dung]*")
            if n_failed == n_pages:
                raise ClaudeOCRError(
                    f"OCR thất bại ở toàn bộ {n_failed} trang. "
                    "Hãy kiểm tra Claude Code còn đăng nhập/hạn mức không."
                )
            return "\n\n".join(parts).strip()
        finally:
            pdf.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ocr_image_file(img_path, model="opus", page_timeout=600):
    """OCR một tệp ảnh đơn lẻ (jpg/png...)."""
    board_fens = None
    try:
        from PIL import Image

        with Image.open(img_path) as im:
            board_fens = _page_board_fens(im.convert("RGB"))
    except Exception:
        board_fens = None
    return ocr_image_path(
        img_path, model=model, timeout=page_timeout, board_fens=board_fens
    )
