"""Engine giả để kiểm thử luồng giao diện/công việc mà KHÔNG gọi AI thật.

Bật bằng biến môi trường ``MID_FAKE_ENGINE=1`` (xem ``ai_engine.is_engine_available``).
Không có tiến trình ``agy``/``claude`` nào được chạy, không có yêu cầu mạng.

Biến môi trường:
- ``MID_FAKE_DELAY``      giây ngủ mỗi lần "gọi AI" (mặc định 0.3).
- ``MID_FAKE_H1`` ``1`` = tiêu đề mỗi trang là cấp ``#`` (mặc định ``##``) — để thử tách chương theo tiêu đề cấp 1.
- ``MID_FAKE_DELAY_SCALE`` ``1`` = trễ nhân với số trang lớn nhất trong lượt (trang sau xong muộn hơn) — để thử Dừng giữa chừng.
- ``MID_FAKE_FAIL_PAGES`` danh sách số trang (ví dụ ``3,5``) mà lần OCR sẽ ném ``ClaudeOCRError``
  — để thử luồng "OCR lại trang lỗi". Số trang lấy từ tên tệp ảnh ``page_NNN.png`` trong prompt.

Đi qua đúng hai hàm điều phối thật (``claude_ocr._run_engine_ocr`` và
``claude_translate._call_engine_translate``), nên mọi bước phía trên (chia nhóm trang,
tách marker ``HET_TRANG``, hậu kiểm khối bàn cờ, bảo vệ placeholder khi dịch) chạy như thật.
"""

import os
import re
import threading

import proc_control

ENV_FLAG = "MID_FAKE_ENGINE"

# Nội dung mỗi trang: (tiếng Anh, tiếng Việt). Bản dịch giả ánh xạ đúng từng câu này nên
# phần dịch riêng cho kết quả có dấu tiếng Việt như dịch thật.
_SENTENCES = [
    ("Chapter {n}: The Italian Game",
     "Chương {n}: Khai cuộc Ý"),
    ("White develops the knight and the bishop toward the centre of the board.",
     "Trắng phát triển Mã và Tượng về phía trung tâm bàn cờ, chuẩn bị nhập thành sớm."),
    ("1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6 5.d4 exd4 6.cxd4 Bb4+",
     "1.e4 e5 2.Mf3 Mc6 3.Tc4 Tc5 4.c3 Mf6 5.d4 exd4 6.cxd4 Tb4+"),
    ("Black must find an accurate reply here, otherwise the initiative passes to White.",
     "Đen phải tìm được nước đáp chính xác ở đây, nếu không thế chủ động sẽ thuộc về Trắng."),
]

# Các thế cờ hợp lệ (đủ hai Vua) xoay vòng theo số trang.
_FENS = [
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
]

_PAGE_FILE_RE = re.compile(r"page_(\d+)\.png")
_MULTI_PAGE_RE = re.compile(r"^- TRANG \d+:", re.MULTILINE)


# Nhật ký lượt "gọi AI" của tiến trình này, dùng cho test đếm số lượt:
# ("ocr", [số trang trong lượt]) hoặc ("translate", None).
CALLS = []
_CALLS_LOCK = threading.Lock()


def reset_calls():
    with _CALLS_LOCK:
        CALLS.clear()


def _log(kind, pages=None):
    with _CALLS_LOCK:
        CALLS.append((kind, pages))


def is_enabled():
    return os.environ.get(ENV_FLAG, "").strip() in ("1", "true", "True", "yes")


def _delay():
    try:
        return max(0.0, float(os.environ.get("MID_FAKE_DELAY", "0.3")))
    except ValueError:
        return 0.3


def _fail_pages():
    out = set()
    for tok in os.environ.get("MID_FAKE_FAIL_PAGES", "").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.add(int(tok))
    return out


def _page_text(n, vietnamese, chess):
    idx = 1 if vietnamese else 0
    lines = [s[idx].format(n=n) for s in _SENTENCES]
    heading = "#" if os.environ.get("MID_FAKE_H1", "").strip() == "1" else "##"
    parts = [f"{heading} {lines[0]}", lines[1]]
    if chess:
        parts.append("```chessboard\nfen: " + _FENS[(n - 1) % len(_FENS)] + "\n```")
    parts.append(lines[2])
    parts.append(lines[3])
    return "\n\n".join(parts)


def fake_ocr(prompt):
    """Trả Markdown cho prompt OCR (một trang hoặc một nhóm trang)."""
    # Import muộn để cắt vòng phụ thuộc (claude_ocr import fake_engine).
    from claude_ocr import _PAGE_BREAK, _PROMPT_MERGE_BANNER, ClaudeOCRError

    numbers = [int(m) for m in _PAGE_FILE_RE.findall(prompt)]
    n_group = max(1, len(_MULTI_PAGE_RE.findall(prompt)))
    numbers = (numbers + [1] * n_group)[:n_group]
    _log("ocr", list(numbers))
    scale = max(numbers) if os.environ.get("MID_FAKE_DELAY_SCALE", "").strip() == "1" else 1
    proc_control.sleep(_delay() * scale)  # thức dậy ngay khi bấm Dừng (ném OperationCancelled)
    bad = sorted(set(numbers) & _fail_pages())
    if bad:
        raise ClaudeOCRError("Engine giả: giả lập lỗi OCR ở trang " + ", ".join(map(str, bad)))
    vietnamese = prompt.startswith(_PROMPT_MERGE_BANNER)
    chess = "```chessboard" in prompt
    pages = [_page_text(no, vietnamese, chess) for no in numbers]
    return ("\n" + _PAGE_BREAK + "\n").join(pages)


def fake_translate(chunk):
    """Dịch giả: thay từng câu Anh đã biết bằng câu Việt; giữ nguyên phần còn lại (placeholder, FEN…)."""
    _log("translate")
    proc_control.sleep(_delay())
    out = chunk
    for en, vi in _SENTENCES:
        if "{n}" in en:
            pat = re.compile(re.escape(en).replace(re.escape("{n}"), r"(\d+)"))
            out = pat.sub(lambda m, vi=vi: vi.format(n=m.group(1)), out)
        else:
            out = out.replace(en, vi)
    return out
