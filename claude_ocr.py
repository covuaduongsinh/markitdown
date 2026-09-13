# -*- coding: utf-8 -*-
"""
OCR cho PDF / ảnh scan qua AI Engine ở chế độ headless (KHÔNG cần API key).

Ý tưởng: render từng trang PDF thành ảnh PNG, rồi gọi AI Engine đã chọn — Google
Antigravity (`agy -p`, mặc định) hoặc Claude Code (`claude -p`, phương án 2) —
để đọc ảnh và trích toàn bộ văn bản ra Markdown. Việc chọn engine + danh sách
model của từng engine nằm ở `ai_engine.py`. Xác thực bằng phiên đăng nhập CLI
hiện có của người dùng (không cần API key).

Phụ thuộc: pypdfium2 + Pillow (đã có sẵn trong venv qua markitdown[all]),
và CLI `agy` (Google Antigravity) hoặc `claude` (Claude Code) trong PATH.
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

# Quy tắc dọn các thành phần phụ trợ của trang in (header/footer/số trang).
# Dùng chung cho mọi chế độ -> nối vào cuối _PROMPT_HEADER.
_PROMPT_CLEANUP = (
    "Loại bỏ các thành phần phụ trợ của trang in, KHÔNG đưa vào Markdown:\n"
    "- Tiêu đề chạy đầu trang (header): tên sách, tên chương... in tách biệt phía trên thân trang.\n"
    "- Chân trang (footer) và số trang.\n"
    "- Phần cố định lặp lại ở mọi trang (vd: tên sách/chương ở mép trên hoặc mép dưới).\n"
    "Mỗi lần bạn chỉ thấy MỘT trang, nên nhận biết các thành phần này qua VỊ TRÍ "
    "(ở mép trên/dưới, tách rời phần thân) và nội dung (tên sách/chương, số trang), "
    "không cần so sánh giữa các trang.\n"
    "Nếu KHÔNG chắc một dòng có phải header/footer/số trang hay không thì GIỮ NGUYÊN "
    "dòng đó và ghi chú ngay sau: (cần kiểm tra).\n\n"
)

_PROMPT_HEADER = (
    "Hãy đọc ảnh tài liệu tại đường dẫn: {path}\n\n"
    "Đây có thể là tài liệu tiếng Việt được scan, có thể có watermark hoặc dấu mộc. "
    "Nhiệm vụ của bạn là OCR: trích xuất TOÀN BỘ nội dung văn bản nhìn thấy trong ảnh "
    "và trình bày lại dưới dạng Markdown, giữ đúng cấu trúc (tiêu đề, đoạn văn, bảng, "
    "danh sách). Bỏ qua hoa văn/watermark trang trí.\n\n"
) + _PROMPT_CLEANUP

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

# Footer dùng chung cho mọi chế độ.
_PROMPT_FOOTER_PLAIN = (
    "CHỈ trả về nội dung Markdown đã trích, KHÔNG thêm lời mở đầu, giải thích hay nhận xét."
)

_PROMPT_FOOTER = (
    "Về ký hiệu nước đi cờ vua trong văn bản: giữ NGUYÊN VĂN như sách in (số thứ tự nước "
    "'12.' hoặc '12...', các ký hiệu đánh giá !, ?, !!, ??, !?, ?!, ±, =, +-, -+...). "
    "Nếu sách in quân cờ bằng hình (figurine) thì chuyển về chữ cái SAN quốc tế tương ứng "
    "K, Q, R, B, N. KHÔNG diễn giải hay bình luận thêm về nước đi.\n\n"
) + _PROMPT_FOOTER_PLAIN

# Footer cho SÁCH TIẾNG NGA: giữ nguyên chữ quân cờ Nga; figurine -> chữ cái Nga
# (KHÔNG đổi sang Latin) để cả trang đồng nhất một bảng chữ cái, tránh đụng độ
# K (Vua, Latin từ figurine) với К (Mã, Cyrillic). Bước dịch sẽ đổi Кр/Ф/Л/С/К
# sang V/H/X/T/M.
_PROMPT_FOOTER_RU = (
    "Về ký hiệu nước đi cờ vua trong văn bản (sách tiếng Nga): giữ NGUYÊN VĂN như sách in "
    "— chữ cái quân cờ tiếng Nga (Кр, Ф, Л, С, К, п), số thứ tự nước '12.' hoặc '12...', "
    "các ký hiệu đánh giá !, ?, !!, ??, !?, ?!, ±, =, +-, -+... KHÔNG dịch và KHÔNG chuyển "
    "chữ Nga sang chữ Latin. Nếu sách in quân cờ bằng hình (figurine) thì chuyển về chữ "
    "cái quân cờ TIẾNG NGA tương ứng: ♔/♚→Кр, ♕/♛→Ф, ♖/♜→Л, ♗/♝→С, ♘/♞→К, ♙/♟→không có "
    "chữ. KHÔNG diễn giải hay bình luận thêm về nước đi.\n\n"
) + _PROMPT_FOOTER_PLAIN

# Footer cho SÁCH TIẾNG TÂY BAN NHA: giữ nguyên chữ quân cờ Tây Ban Nha (R, D,
# T, A, C); figurine -> chữ cái Tây Ban Nha (KHÔNG đổi sang SAN quốc tế) để cả
# trang đồng nhất một bảng chữ. Bước dịch sau sẽ đổi R/D/T/A/C sang V/H/X/T/M
# (lưu ý T = Torre/Xe -> X, A = Alfil/Tượng -> T, R = Rey/Vua -> V).
_PROMPT_FOOTER_ES = (
    "Về ký hiệu nước đi cờ vua trong văn bản (sách tiếng Tây Ban Nha): giữ NGUYÊN "
    "VĂN như sách in — chữ cái quân cờ tiếng Tây Ban Nha (R=Rey, D=Dama, T=Torre, "
    "A=Alfil, C=Caballo; tốt không có chữ), số thứ tự nước '12.' hoặc '12...', các "
    "ký hiệu đánh giá !, ?, !!, ??, !?, ?!, ±, =, +-, -+... KHÔNG dịch và KHÔNG đổi "
    "các chữ cái quân cờ này sang ký hiệu khác. Nếu sách in quân cờ bằng hình "
    "(figurine) thì chuyển về chữ cái quân cờ TIẾNG TÂY BAN NHA tương ứng: ♔/♚→R, "
    "♕/♛→D, ♖/♜→T, ♗/♝→A, ♘/♞→C, ♙/♟→không có chữ. KHÔNG diễn giải hay bình luận "
    "thêm về nước đi.\n\n"
) + _PROMPT_FOOTER_PLAIN


def _chess_footer(chess_lang):
    """Chọn footer giữ-nguyên-văn theo ngôn ngữ ký hiệu nguồn của sách cờ vua."""
    return {"ru": _PROMPT_FOOTER_RU, "es": _PROMPT_FOOTER_ES}.get(
        chess_lang, _PROMPT_FOOTER
    )


# Giữ tên cũ cho tương thích (prompt khi Claude phải tự nhận diện bàn cờ).
PROMPT_VI = _PROMPT_HEADER + _PROMPT_CHESS_SELF + _PROMPT_FOOTER

# === Chế độ GỘP OCR + DỊCH (translate_to="vi") =================================
# Thay vì OCR giữ nguyên văn rồi dịch ở bước riêng, yêu cầu Claude vừa OCR vừa
# dịch sang tiếng Việt trong CÙNG một lần gọi -> bỏ hẳn pass dịch (tiết kiệm
# hạn mức). Quy tắc ký hiệu nước đi tái dùng nguyên các hằng trong
# claude_translate.py (_CHESS_II_EN/_CHESS_II_RU/_CHESS_TAIL) để giữ MỘT nguồn
# chân lý duy nhất, tránh viết trùng và lệch quy tắc.
# Banner đặt ở ĐẦU prompt gộp để "ngôn ngữ đầu ra = tiếng Việt" là điều model
# đọc TRƯỚC TIÊN — footer dịch nằm cuối dễ bị bỏ qua ở chế độ nhiều trang hoặc
# effort thấp (model OCR xong rồi quên dịch).
_PROMPT_MERGE_BANNER = (
    "‼️ YÊU CẦU QUAN TRỌNG NHẤT — NGÔN NGỮ ĐẦU RA = TIẾNG VIỆT: Hãy OCR rồi DỊCH "
    "toàn bộ văn bản sang TIẾNG VIỆT. TUYỆT ĐỐI KHÔNG để nguyên văn bản tiếng "
    "Anh/Nga (chỉ giữ nguyên tên riêng, tọa độ a-h/1-8, ký hiệu nước đi và block "
    "```chessboard). Quy tắc chi tiết ở phần dưới.\n\n"
)

_PROMPT_MERGE_INTRO = (
    "NGÔN NGỮ ĐẦU RA — QUAN TRỌNG: Sau khi OCR, hãy DỊCH toàn bộ phần VĂN BẢN sang "
    "TIẾNG VIỆT ngay trong bước này. Đầu ra là Markdown tiếng Việt, giữ nguyên cấu "
    "trúc (tiêu đề, đoạn, bảng, danh sách). KHÔNG để lại văn bản tiếng Anh/Nga chưa "
    "dịch (trừ tên riêng, tọa độ a-h/1-8 và ký hiệu nước đi theo quy tắc dưới). "
    "Giữ NGUYÊN VĂN các block ```chessboard (FEN) — KHÔNG dịch, KHÔNG sửa.\n\n"
)

# Quy tắc dịch cho chế độ tài liệu thường (gộp). Ngắn gọn, không phụ thuộc
# claude_translate vì đây không phải phần dễ sai như ký hiệu cờ vua.
_PROMPT_MERGE_GENERAL = (
    "QUY TẮC DỊCH:\n"
    "- Dịch tự nhiên, chính xác, đúng thuật ngữ chuyên ngành của tài liệu.\n"
    "- KHÔNG dịch: tên riêng, tên thương hiệu, URL, đường dẫn tệp, mã/lệnh, "
    "ký hiệu toán học.\n"
    "- Thuật ngữ kỹ thuật không có từ tiếng Việt thông dụng thì giữ nguyên "
    "tiếng Anh.\n"
    "- Giữ format trung thực: bản gốc in đậm (**...**) thì giữ in đậm; bản gốc "
    "không in đậm thì TUYỆT ĐỐI không thêm.\n\n"
) + _PROMPT_FOOTER_PLAIN


def _merge_footer(chess, chess_lang):
    """Footer cho chế độ gộp OCR+dịch: dịch sang tiếng Việt thay vì giữ nguyên văn."""
    if not chess:
        return _PROMPT_MERGE_INTRO + _PROMPT_MERGE_GENERAL
    # Tái dùng quy tắc ký hiệu + format từ bước dịch để đồng nhất hoàn toàn.
    from claude_translate import (
        _CHESS_II_EN, _CHESS_II_ES, _CHESS_II_RU, _CHESS_TAIL,
    )

    notation = {"ru": _CHESS_II_RU, "es": _CHESS_II_ES}.get(chess_lang, _CHESS_II_EN)
    return _PROMPT_MERGE_INTRO + notation + _CHESS_TAIL


def _build_prompt(img_path, board_fens=None, chess=True, chess_lang="en",
                  translate_to=None):
    """Ghép prompt OCR: có FEN tính sẵn thì yêu cầu dùng nguyên văn.

    chess=False (chế độ tài liệu thường): bỏ toàn bộ phần bàn cờ vua.
    chess_lang="ru": footer giữ ký hiệu tiếng Nga và đổi figurine sang chữ Nga;
    "es": footer giữ ký hiệu Tây Ban Nha R/D/T/A/C (figurine -> chữ Tây Ban Nha);
    "en" (mặc định): footer chuẩn (figurine -> SAN quốc tế K/Q/R/B/N).
    translate_to="vi": chế độ gộp — vừa OCR vừa dịch sang tiếng Việt trong cùng
    một lần gọi (footer dịch thay cho footer giữ nguyên văn).
    """
    head = _PROMPT_HEADER.format(path=img_path)
    banner = _PROMPT_MERGE_BANNER if translate_to == "vi" else ""
    if translate_to == "vi":
        footer = _merge_footer(chess, chess_lang)
    elif chess:
        footer = _chess_footer(chess_lang)
    else:
        footer = _PROMPT_FOOTER_PLAIN
    if not chess:
        return banner + head + footer
    if board_fens:
        fen_list = "\n".join(f"{i}. {fen}" for i, fen in enumerate(board_fens, 1))
        chess_part = _PROMPT_CHESS_GIVEN.format(n=len(board_fens), fen_list=fen_list)
    else:
        chess_part = _PROMPT_CHESS_SELF
    return banner + head + chess_part + footer


# === Gộp nhiều trang vào 1 lần gọi (pages_per_call > 1) ========================
# Marker model phải in giữa hai trang liên tiếp để ta tách lại đúng từng trang.
_PAGE_BREAK = "<<<<<--- HET_TRANG --->>>>>"

_PROMPT_MULTI_HEADER = (
    "Hãy đọc (OCR) {n} trang tài liệu sau, MỖI trang là một ảnh riêng — đọc bằng "
    "công cụ Read theo đúng đường dẫn:\n"
    "{page_list}\n\n"
    "Xử lý LẦN LƯỢT từng trang theo đúng thứ tự trên (TRANG 1, TRANG 2, ...). "
    "Giữa hai trang liên tiếp, in ĐÚNG MỘT dòng marker dưới đây trên dòng riêng, "
    "KHÔNG thêm gì khác trên dòng đó, và KHÔNG in marker trước TRANG 1 hay sau "
    "trang cuối cùng:\n"
    "{marker}\n\n"
    "Với MỖI trang: trích TOÀN BỘ nội dung văn bản nhìn thấy và trình bày lại "
    "dưới dạng Markdown, giữ đúng cấu trúc (tiêu đề, đoạn văn, bảng, danh sách). "
    "Bỏ qua hoa văn/watermark trang trí.\n\n"
) + _PROMPT_CLEANUP

# Quy tắc bàn cờ tổng quát cho nhiều trang (FEN sẵn của từng trang nằm trong
# page_list). Diễn đạt theo "từng trang" thay vì một trang đơn lẻ.
_PROMPT_MULTI_CHESS = (
    "VỀ HÌNH BÀN CỜ VUA (áp dụng riêng cho TỪNG trang):\n"
    "- Nếu trang có dòng 'FEN đã nhận diện sẵn': khi gặp hình bàn cờ thứ i trên "
    "trang đó, chèn NGAY TẠI VỊ TRÍ hình (TRƯỚC phần nước đi liên quan) một block "
    "dùng NGUYÊN VĂN FEN thứ i của trang đó — KHÔNG tự nhận diện lại, KHÔNG sửa "
    "FEN. Riêng lượt đi: nếu chú thích/nước kế cho thấy Đen đi trước ('Đen đi', "
    "nước dạng '1...') thì đổi trường lượt đi của FEN từ w thành b.\n"
    "- Nếu trang KHÔNG có FEN sẵn mà lại có hình bàn cờ: tự quan sát từng ô a1..h8, "
    "sinh FEN đầy đủ 6 trường (lượt đi suy từ chú thích, không rõ dùng w; quyền "
    "nhập thành -; ô bắt tốt qua đường -; số nước nửa 0; số nước đầy đủ 1).\n"
    "- Thế cờ KHÔNG đủ 2 quân Vua (đúng 1 K trắng và 1 k đen) thì thêm dòng "
    "`strict: false` ngay dưới dòng fen.\n\n"
) + _PROMPT_BLOCK_RULES


def _build_prompt_multi(pages, chess=True, chess_lang="en", translate_to=None):
    """Ghép prompt OCR cho một NHÓM trang (pages = list (path, board_fens)).

    Model OCR lần lượt từng trang, phân tách bằng marker _PAGE_BREAK để caller
    tách lại đúng từng trang. Quy tắc bàn cờ / dịch dùng chung với chế độ 1 trang.
    """
    n = len(pages)
    lines = []
    for idx, (path, fens) in enumerate(pages, 1):
        lines.append(f"- TRANG {idx}: {path}")
        if chess and fens:
            fen_str = "; ".join(f"{i}) {f}" for i, f in enumerate(fens, 1))
            lines.append(
                f"    FEN đã nhận diện sẵn cho TRANG {idx} "
                f"(theo thứ tự xuất hiện): {fen_str}"
            )
    head = _PROMPT_MULTI_HEADER.format(
        n=n, page_list="\n".join(lines), marker=_PAGE_BREAK
    )
    banner = _PROMPT_MERGE_BANNER if translate_to == "vi" else ""
    if translate_to == "vi":
        footer = _merge_footer(chess, chess_lang)
    elif chess:
        footer = _chess_footer(chess_lang)
    else:
        footer = _PROMPT_FOOTER_PLAIN
    body = _PROMPT_MULTI_CHESS if chess else ""
    reminder = (
        f"\n\nNHẮC LẠI: in đúng dòng marker `{_PAGE_BREAK}` giữa các trang "
        f"(tổng cộng {n - 1} marker cho {n} trang); KHÔNG in ở đầu hoặc cuối."
    )
    return banner + head + body + footer + reminder

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


def extract_fens(md):
    """Trả về list FEN (chuỗi) từ mọi block ```chessboard trong md, đúng thứ tự.

    Khối đã qua _normalize_chessboard_blocks luôn có dòng `fen: <FEN>`; vẫn dự
    phòng cho khối không có tiền tố `fen:` (lấy dòng đầu trông giống FEN).
    """
    fens = []
    for m in _CHESSBOARD_BLOCK_RE.finditer(md):
        body = m.group(1)
        fm = _FEN_FIELD_RE.search(body)
        if fm:
            fen = fm.group(1).strip().strip("\"'").strip()
        else:
            fen = next((ln.strip() for ln in body.splitlines() if "/" in ln), "")
        if fen:
            fens.append(fen)
    return fens


class ClaudeOCRError(RuntimeError):
    """Lỗi trong quá trình OCR bằng Claude Code."""


def find_claude():
    """Trả về đường dẫn tới CLI `claude`, hoặc None nếu không có trong PATH."""
    return shutil.which("claude")


def _claude_fast_flags(effort="low"):
    """Flags thêm vào mọi lệnh `claude -p` để chạy nhanh nhất có thể.

    Quan trọng nhất là --effort: override effortLevel trong settings người
    dùng (nếu đặt xhigh, model sẽ "suy nghĩ" hàng chục nghìn token cho mỗi
    trang — OCR/dịch chỉ là chép chữ nên không cần). Các flag còn lại bỏ
    việc nạp user settings/plugin/MCP và ghi session log mỗi lần gọi.
    """
    return [
        "--effort", effort,
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--no-session-persistence",
    ]


def _claude_env():
    """Env cho tiến trình `claude`: tắt auto-update/telemetry khi khởi động."""
    env = os.environ.copy()
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env


# DPI cao để nhận diện bàn cờ (cắt hình nét); DPI thấp cho OCR cả trang.
# Model bàn cờ chỉ nhìn ảnh <=512px nên 250 DPI thường đủ và nhanh hơn ~2.5x.
BOARD_DPI = 400


def _render_page_pair(page, out_dir, page_no, ocr_dpi=200, board_dpi=BOARD_DPI):
    """Render 1 trang PDF: trả về (đường dẫn PNG ocr_dpi, ảnh PIL board_dpi)."""
    from PIL import Image

    hi = page.render(scale=board_dpi / 72.0).to_pil().convert("RGB")
    lo = hi.resize(
        (
            max(1, hi.width * ocr_dpi // board_dpi),
            max(1, hi.height * ocr_dpi // board_dpi),
        ),
        Image.LANCZOS,
    )
    out_path = os.path.join(out_dir, f"page_{page_no:03d}.png")
    lo.save(out_path, format="PNG")
    return out_path, hi


def _render_page(page, out_dir, page_no, dpi=200):
    """Render 1 trang PDF thẳng ở DPI cho OCR (chế độ thường, không cần ảnh nét
    cao để nhận diện bàn cờ). Trả về đường dẫn PNG."""
    lo = page.render(scale=dpi / 72.0).to_pil().convert("RGB")
    out_path = os.path.join(out_dir, f"page_{page_no:03d}.png")
    lo.save(out_path, format="PNG")
    return out_path


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


def _run_claude_ocr(prompt, img_dir, model, effort, timeout):
    """Gọi `claude -p` với prompt OCR (đọc ảnh qua tool Read). Trả về văn bản
    cuối (đã bóc khỏi JSON --output-format), trước bước hậu kiểm chessboard."""
    claude = find_claude()
    if not claude:
        raise ClaudeOCRError(
            "Không tìm thấy Claude Code (lệnh 'claude') trong PATH. "
            "Hãy đảm bảo Claude Code đã được cài và đăng nhập."
        )

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
    ] + _claude_fast_flags(effort)

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
            env=_claude_env(),
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


def _run_engine_ocr(prompt, img_dir, model, effort, timeout, engine="antigravity"):
    """Điều phối chạy OCR qua Antigravity (mặc định) hoặc Claude Code."""
    from ai_engine import ENGINE_ANTIGRAVITY, ENGINE_CLAUDE, run_agy_prompt, AIEngineError

    if engine == ENGINE_ANTIGRAVITY:
        try:
            return run_agy_prompt(
                prompt=prompt,
                model=model,
                effort=effort,
                img_dir=img_dir,
                timeout=timeout,
            )
        except AIEngineError as exc:
            raise ClaudeOCRError(str(exc)) from exc
    else:
        return _run_claude_ocr(prompt, img_dir, model, effort, timeout)


def _ensure_translated(text, chess, chess_lang, model, engine="antigravity"):
    """Chế độ gộp OCR+dịch: nếu đầu ra trông như CHƯA dịch (còn nguyên ngôn ngữ
    gốc) thì dịch lại bằng pass dịch chuyên dụng để bảo đảm ra tiếng Việt.

    Chỉ tốn thêm quota khi thực sự lỗi — trang dịch tốt ngay từ đầu sẽ bỏ qua.
    Lỗi khi dịch lại -> giữ nguyên text (không làm hỏng tiến trình).
    """
    if not text or not text.strip():
        return text
    # Lazy-import tránh import vòng (claude_translate import từ claude_ocr).
    from claude_translate import _looks_untranslated, translate_markdown_vn

    if not _looks_untranslated(text, chess_lang):
        return text
    try:
        return translate_markdown_vn(
            text, model=model, chess=chess, chess_lang=chess_lang, effort="low",
        )
    except Exception as exc:
        print(f"[merge] Lỗi dịch lại trang chưa dịch: {exc}", file=sys.stderr)
        return text


def ocr_image_path(
    img_path, model="gemini-3.7-flash", timeout=600, board_fens=None, chess=True,
    chess_lang="en", effort=None, translate_to=None, engine="antigravity",
):
    """Gọi AI Engine (Antigravity hoặc Claude Code) để OCR một ảnh. Trả về Markdown trích được.

    board_fens: danh sách FEN của các hình bàn cờ trên trang (đã nhận diện cục
    bộ bằng model ONNX, theo thứ tự đọc) — AI sẽ dùng nguyên văn thay vì tự
    nhận diện.
    chess=False (chế độ tài liệu thường): OCR bằng prompt thường, không có phần
    nhận diện bàn cờ / block chessboard.
    chess_lang="ru": dùng footer tiếng Nga (giữ ký hiệu Кр/Ф/Л/С/К).
    translate_to="vi": gộp OCR+dịch — xuất thẳng Markdown tiếng Việt.
    engine: 'antigravity' (mặc định) hoặc 'claude'.
    """
    img_path = os.path.abspath(img_path)
    img_dir = os.path.dirname(img_path)
    prompt = _build_prompt(
        img_path, board_fens, chess=chess, chess_lang=chess_lang,
        translate_to=translate_to,
    )

    if effort is None:
        effort = "medium" if (translate_to == "vi" or (chess and not board_fens)) else "low"
    raw = _run_engine_ocr(prompt, img_dir, model, effort, timeout, engine=engine)
    # Chế độ thường không sinh block chessboard nên không cần hậu kiểm.
    post = _normalize_chessboard_blocks if chess else (lambda s: s)
    out = post(raw)
    if translate_to == "vi":
        out = _ensure_translated(out, chess, chess_lang, model, engine=engine)
    return out


def ocr_image_group(
    items, model="gemini-3.7-flash", timeout=600, chess=True, chess_lang="en",
    effort=None, translate_to=None, engine="antigravity",
):
    """OCR một NHÓM trang trong 1 lần gọi AI Engine. Trả về list Markdown theo
    đúng thứ tự trang trong nhóm.
    """
    n = len(items)
    if n == 1:
        png, fens = items[0]
        return [ocr_image_path(
            png, model=model, timeout=timeout, board_fens=fens, chess=chess,
            chess_lang=chess_lang, effort=effort, translate_to=translate_to,
            engine=engine,
        )]

    pages = [(os.path.abspath(p), f) for p, f in items]
    img_dir = os.path.dirname(pages[0][0])
    prompt = _build_prompt_multi(
        pages, chess=chess, chess_lang=chess_lang, translate_to=translate_to,
    )
    if effort is None:
        need_detect = chess and any(not fens for _p, fens in pages)
        effort = "medium" if (translate_to == "vi" or need_detect) else "low"
    raw = _run_engine_ocr(prompt, img_dir, model, effort, timeout, engine=engine)

    post = _normalize_chessboard_blocks if chess else (lambda s: s)
    parts = [p.strip() for p in re.split(re.escape(_PAGE_BREAK), raw)]
    nonempty = [p for p in parts if p]
    if len(parts) == n:
        chosen = parts
    elif len(nonempty) == n:
        chosen = nonempty
    else:
        chosen = nonempty if nonempty else parts
    mismatched = len(chosen) != n
    if len(chosen) > n:
        chosen = chosen[: n - 1] + ["\n\n".join(chosen[n - 1:])]
    while len(chosen) < n:
        chosen.append("")

    out = []
    for k in range(n):
        seg = chosen[k]
        if not seg:
            out.append("")
            continue
        seg = post(seg)
        if translate_to == "vi":
            seg = _ensure_translated(seg, chess, chess_lang, model, engine=engine)
        out.append(seg)
    if mismatched and out:
        note = (
            f"\n\n*[Cảnh báo: model tách được số phần khác {n} trang trong nhóm — "
            "cần kiểm tra ranh giới trang]*"
        )
        out[0] = (out[0] + note) if out[0] else note.strip()
    return out


# Số lần gọi chạy song song
OCR_WORKERS = 8


def _ocr_page_group(items, model, page_timeout, chess, chess_lang="en",
                    effort=None, translate_to=None, engine="antigravity"):
    """OCR 1 nhóm trang với 1 lần thử lại. Trả về list Markdown; vẫn lỗi thì raise."""
    try:
        return ocr_image_group(
            items, model=model, timeout=page_timeout, chess=chess,
            chess_lang=chess_lang, effort=effort, translate_to=translate_to,
            engine=engine,
        )
    except ClaudeOCRError:
        return ocr_image_group(
            items, model=model, timeout=page_timeout, chess=chess,
            chess_lang=chess_lang, effort=effort, translate_to=translate_to,
            engine=engine,
        )


def ocr_pdf(
    pdf_path, model="gemini-3.7-flash", dpi=200, progress=None, page_timeout=600,
    board_dpi=BOARD_DPI, chess=True, workers=OCR_WORKERS, chess_lang="en",
    effort=None, translate_to=None, pages_per_call=1, engine="antigravity",
):
    """OCR toàn bộ PDF scan qua Antigravity hoặc Claude Code. Trả về Markdown ghép các trang.

    Mỗi trang: nhận diện hình bàn cờ -> FEN cục bộ bằng model ONNX (không tốn
    quota AI), rồi OCR văn bản bằng AI với FEN đã tính sẵn. Các lệnh gọi
    được chạy song song `workers` lệnh một lúc, kết quả ghép đúng thứ tự.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import pypdfium2 as pdfium

    pages_per_call = max(1, int(pages_per_call or 1))
    tmp_dir = tempfile.mkdtemp(prefix="mid_ocr_")
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            n_pages = len(pdf)
            if n_pages == 0:
                raise ClaudeOCRError("PDF không có trang nào.")
            parts = [None] * n_pages
            n_failed = 0
            n_done = 0
            if progress is not None:
                progress(0, n_pages)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = {}
                group = []

                def _submit(g):
                    items = [(png, fens) for _no, png, fens in g]
                    fut = pool.submit(
                        _ocr_page_group, items, model, page_timeout, chess,
                        chess_lang, effort, translate_to, engine=engine,
                    )
                    futures[fut] = [no for no, _png, _fens in g]

                for i in range(1, n_pages + 1):
                    if chess:
                        png, hi_res = _render_page_pair(
                            pdf[i - 1], tmp_dir, i, ocr_dpi=dpi, board_dpi=board_dpi
                        )
                        board_fens = _page_board_fens(hi_res)
                        del hi_res
                    else:
                        png = _render_page(pdf[i - 1], tmp_dir, i, dpi=dpi)
                        board_fens = None
                    group.append((i, png, board_fens))
                    if len(group) >= pages_per_call:
                        _submit(group)
                        group = []
                if group:
                    _submit(group)

                for fut in as_completed(futures):
                    idxs = futures[fut]
                    try:
                        results = fut.result()
                    except ClaudeOCRError as exc:
                        for pi in idxs:
                            n_failed += 1
                            parts[pi - 1] = f"*[Lỗi OCR trang {pi}: {exc}]*"
                            n_done += 1
                            if progress is not None:
                                progress(n_done, n_pages)
                        continue
                    for k, pi in enumerate(idxs):
                        text = results[k] if k < len(results) else ""
                        if text and text.strip():
                            parts[pi - 1] = text.strip()
                        else:
                            parts[pi - 1] = f"*[Trang {pi}: không trích được nội dung]*"
                        n_done += 1
                        if progress is not None:
                            progress(n_done, n_pages)
        finally:
            pdf.close()
        if n_failed == n_pages:
            engine_name = "Antigravity" if engine == "antigravity" else "Claude Code"
            raise ClaudeOCRError(
                f"OCR thất bại ở toàn bộ {n_failed} trang. "
                f"Hãy kiểm tra {engine_name} còn phiên đăng nhập/hạn mức không."
            )
        return "\n\n".join(parts).strip()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _ocr_image_with_retry(img_path, **kwargs):
    """OCR 1 ảnh với 1 lần thử lại, cùng pattern với _ocr_page_group (PDF)."""
    try:
        return ocr_image_path(img_path, **kwargs)
    except ClaudeOCRError:
        return ocr_image_path(img_path, **kwargs)


def ocr_image_file(
    img_path, model="gemini-3.7-flash", page_timeout=600, chess=True,
    chess_lang="en", effort=None, translate_to=None, engine="antigravity",
):
    """OCR một tệp ảnh đơn lẻ (jpg/png...), tự thử lại 1 lần nếu lỗi."""
    board_fens = None
    if chess:
        try:
            from PIL import Image

            with Image.open(img_path) as im:
                board_fens = _page_board_fens(im.convert("RGB"))
        except Exception:
            board_fens = None
    return _ocr_image_with_retry(
        img_path, model=model, timeout=page_timeout, board_fens=board_fens,
        chess=chess, chess_lang=chess_lang, effort=effort,
        translate_to=translate_to, engine=engine,
    )

