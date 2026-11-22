# -*- coding: utf-8 -*-
"""
Công cụ thuần (không gọi AI, không cần mô hình ONNX) để hiệu đính thế cờ trong Markdown kết quả:
liệt kê các khối ```chessboard, kiểm tra/sửa/xoay FEN, vẽ bàn cờ HTML, liên kết Lichess.

Định dạng khối giữ nguyên như plugin Chessboard Viewer của Obsidian yêu cầu (một dòng `fen:`, xem AGENTS.md 4b).
"""

import html
from urllib.parse import quote

from claude_ocr import _CHESSBOARD_BLOCK_RE, _FEN_FIELD_RE, _board_field_valid, _normalize_chessboard_blocks

_PIECE_CLASS = {
    "p": "bp", "n": "bn", "b": "bb", "r": "br", "q": "bq", "k": "bk",
    "P": "wp", "N": "wn", "B": "wb", "R": "wr", "Q": "wq", "K": "wk",
}


def _block_fen(body):
    """FEN (chuỗi) trong thân một khối chessboard; '' nếu không có."""
    m = _FEN_FIELD_RE.search(body)
    if m:
        return m.group(1).strip().strip("\"'").strip()
    return next((ln.strip() for ln in body.splitlines() if "/" in ln), "")


def list_boards(md):
    """Danh sách thế cờ trong md, đúng thứ tự: [{'n': 1.., 'fen': str, 'valid': bool}]."""
    out = []
    for i, m in enumerate(_CHESSBOARD_BLOCK_RE.finditer(md or ""), 1):
        fen = _block_fen(m.group(1))
        out.append({"n": i, "fen": fen, "valid": fen_is_valid(fen)})
    return out


def fen_is_valid(fen):
    """True nếu trường vị trí quân đủ 8 hàng × 8 ô, ký tự hợp lệ và có đúng một Vua mỗi bên."""
    board = (fen or "").strip().split(" ")[0]
    return bool(board) and _board_field_valid(board) and board.count("K") == 1 and board.count("k") == 1


def replace_nth_fen(md, n, new_fen):
    """Thay FEN của khối ```chessboard thứ n (đếm từ 1); trả md mới. Các khối khác không đổi.

    Khối mới được chuẩn hóa như đầu ra OCR (`_normalize_chessboard_blocks`): đủ 6 trường FEN, một dòng `fen:`,
    thêm `strict: false` nếu không đúng một Vua mỗi bên. Ném ValueError nếu n ngoài khoảng hoặc FEN sai cú pháp
    (trường vị trí quân phải là 8 hàng, mỗi hàng đủ 8 ô).
    """
    new_fen = " ".join((new_fen or "").split())
    if not new_fen or not _board_field_valid(new_fen.split(" ")[0]):
        raise ValueError("FEN không hợp lệ: cần 8 hàng ngăn bởi '/', mỗi hàng đủ 8 ô (vd 8/8/8/8/8/8/8/4K2k).")
    count = 0

    def repl(m):
        nonlocal count
        count += 1
        if count != n:
            return m.group(0)
        return _normalize_chessboard_blocks("```chessboard\nfen: " + new_fen + "\n```")

    out = _CHESSBOARD_BLOCK_RE.sub(repl, md or "")
    if not 1 <= n <= count:
        raise ValueError(f"Không có thế cờ số {n} (văn bản có {count} thế cờ).")
    return out


def flip_fen(fen):
    """Xoay bàn cờ 180° (đảo thứ tự hàng và thứ tự ô trong hàng), giữ nguyên các trường còn lại của FEN."""
    parts = (fen or "").strip().split(" ")
    if not parts or not parts[0]:
        return fen
    parts[0] = parts[0][::-1]  # đảo cả chuỗi = đảo thứ tự hàng và đảo từng hàng
    return " ".join(parts)


def lichess_url(fen):
    """Liên kết mở thế cờ trong trình soạn thảo bàn cờ của Lichess."""
    fen = " ".join((fen or "").split())
    return "https://lichess.org/editor/" + quote(fen.replace(" ", "_"), safe="/_-")


def board_html(fen, px=240):
    """Bàn cờ HTML (lưới 8×8). Quân vẽ bằng lớp `.mid-pc.<màu><quân>` (ảnh nền sinh trong ui_theme); ô sáng #F6F2E4, tối #46B49A."""
    board = (fen or "").strip().split(" ")[0]
    if not board or not _board_field_valid(board):
        return f'<div class="mid-fenboard mid-fenboard-bad" style="--px:{int(px)}px">FEN chưa hợp lệ</div>'
    cells = []
    for r, rank in enumerate(board.split("/")):
        f = 0
        for ch in rank:
            if ch.isdigit():
                for _ in range(int(ch)):
                    cells.append(_cell(r, f, None))
                    f += 1
            else:
                cells.append(_cell(r, f, _PIECE_CLASS[ch]))
                f += 1
    return f'<div class="mid-fenboard" style="--px:{int(px)}px">{"".join(cells)}</div>'


def _cell(r, f, piece):
    light = "l" if (r + f) % 2 == 0 else "d"
    inner = f'<i class="mid-pc {piece}"></i>' if piece else ""
    return f'<div class="mid-sq {light}">{inner}</div>'


def fens_text(md):
    """Nội dung tệp _fen.txt: mỗi FEN một dòng (chuỗi rỗng nếu không có thế cờ)."""
    fens = [b["fen"] for b in list_boards(md) if b["fen"]]
    return "\n".join(fens) + "\n" if fens else ""


def escape(text):
    return html.escape(text or "", quote=True)
