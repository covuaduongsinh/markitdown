# -*- coding: utf-8 -*-
"""
Dịch Markdown (sách cờ vua) sang tiếng Việt bằng Claude Code headless.

Cùng cơ chế với claude_ocr.py: gọi CLI `claude -p` dùng phiên đăng nhập
Claude Code hiện có, KHÔNG cần API key. Nội dung cần dịch được đưa qua
stdin để tránh giới hạn độ dài command line trên Windows.

Hai chế độ dịch:
- chess=True (sách cờ vua): quy tắc ký hiệu cờ vua, block ```chessboard (FEN)
  được tách thành placeholder trước khi dịch và khôi phục nguyên văn sau —
  đảm bảo FEN không bao giờ bị dịch/sửa/mất.
- chess=False (tài liệu thường): dịch thông thường, MỌI fenced code block
  được bảo vệ theo cùng cơ chế placeholder.
"""

import json
import re
import subprocess

from claude_ocr import ClaudeOCRError, _claude_env, _claude_fast_flags, find_claude

# Regex block chessboard — giống _CHESSBOARD_BLOCK_RE trong claude_ocr.py.
_CHESSBOARD_BLOCK_RE = re.compile(r"```[ \t]*chessboard[^\n]*\n(.*?)```", re.DOTALL)
# Chế độ tài liệu thường: bảo vệ MỌI fenced code block (code/lệnh không được dịch).
_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

_PLACEHOLDER_FMT = "⟦CHESSBOARD_{n}⟧"
_PLACEHOLDER_RE = re.compile(r"⟦CHESSBOARD_(\d+)⟧")

TRANSLATE_INSTRUCTION_CHESS = (
    "Bạn nhận được (qua stdin) nội dung Markdown trích từ một cuốn sách cờ vua. "
    "Hãy DỊCH toàn bộ phần văn bản sang tiếng Việt, giữ nguyên cấu trúc Markdown.\n\n"
    "=====================\n"
    "I. PLACEHOLDER BÀN CỜ\n"
    "=====================\n"
    "- Các dòng dạng ⟦CHESSBOARD_1⟧, ⟦CHESSBOARD_2⟧... là placeholder cho hình bàn cờ.\n"
    "- BẮT BUỘC giữ NGUYÊN VĂN từng placeholder, đúng vị trí tương ứng, trên dòng riêng.\n"
    "- KHÔNG dịch, KHÔNG sửa, KHÔNG xóa, KHÔNG thêm placeholder.\n\n"
    "=====================\n"
    "II. KÝ HIỆU NƯỚC ĐI\n"
    "=====================\n"
    "A. Tên quân: King → Vua; Queen → Hậu; Rook → Xe; Bishop → Tượng; "
    "Knight → Mã; Pawn → Tốt.\n"
    "B. Notation: K → V; Q → H; R → X; B → T; N → M; Tốt không có ký hiệu.\n"
    "   Ví dụ: Nf3 → Mf3; Qxd5 → Hxd5; Bc4 → Tc4; exd5 → exd5; "
    "O-O → 0-0; O-O-O → 0-0-0.\n"
    "C. Icon quân cờ (figurine): ♔ → V; ♕ → H; ♖ → X; ♗ → T; ♘ → M; "
    "♙ → không ký hiệu.\n"
    "D. Giữ nguyên tọa độ a-h, 1-8.\n"
    "E. Thuật ngữ: check → chiếu; checkmate → chiếu hết; capture → ăn quân.\n"
    "F. Giữ nguyên các ký hiệu đánh giá: !, ?, !!, ??, !?, ?!, ±, =, +-, -+, +...\n\n"
    "=====================\n"
    "III. FORMAT NƯỚC ĐI (BẮT BUỘC)\n"
    "=====================\n"
    "1.e4 e5\n"
    "2.Mf3 Mc6\n"
    "3.Tc4 Mf6\n"
    "- Có dấu \".\" sau số thứ tự nước.\n"
    "- KHÔNG có khoảng trắng sau dấu \".\".\n"
    "- KHÔNG dư khoảng trắng.\n"
    "- Nếu chỉ có 1 bên đi: 1.e4\n"
    "- Nước của Đen đứng riêng: 1...e5\n\n"
    "=====================\n"
    "IV. CẤU TRÚC HEADING\n"
    "=====================\n"
    "- Chương → Heading 1; Biến / Mục → Heading 2; Ván cờ → Heading 3.\n"
    "- \"Chapter 1\" → \"# Chương 1\"; \"Game 1\" → \"### Ván 1\"; "
    "\"Example\" → \"### Ví dụ\".\n"
    "- Mỗi heading trên dòng riêng, không gộp với nội dung.\n"
    "- Giữ nguyên các heading đã có sẵn trong bản gốc (vd: \"## Trang 5\").\n\n"
    "=====================\n"
    "V. ĐỊNH DẠNG TRUNG THỰC\n"
    "=====================\n"
    "- KHÔNG tự ý in đậm, làm đẹp hay thay đổi format.\n"
    "- Chỗ nào bản gốc in đậm (**...**) thì bản dịch giữ in đậm; "
    "bản gốc không in đậm thì TUYỆT ĐỐI không thêm.\n"
    "- Không bỏ sót nội dung.\n\n"
    "=====================\n"
    "VI. OUTPUT\n"
    "=====================\n"
    "CHỈ trả về nội dung Markdown đã dịch, KHÔNG thêm lời mở đầu, "
    "giải thích hay nhận xét."
)

# Giữ tên cũ cho tương thích.
TRANSLATE_INSTRUCTION = TRANSLATE_INSTRUCTION_CHESS

# Prompt dịch cho tài liệu thường (chế độ gốc, không quy tắc cờ vua).
TRANSLATE_INSTRUCTION_GENERAL = (
    "Bạn nhận được (qua stdin) nội dung Markdown trích từ một tài liệu. "
    "Hãy DỊCH toàn bộ phần văn bản sang tiếng Việt, giữ nguyên cấu trúc Markdown "
    "(heading, đoạn văn, bảng, danh sách, liên kết).\n\n"
    "=====================\n"
    "I. PLACEHOLDER\n"
    "=====================\n"
    "- Các dòng dạng ⟦CHESSBOARD_1⟧, ⟦CHESSBOARD_2⟧... là placeholder cho các khối "
    "nội dung phải giữ nguyên (code, lệnh...).\n"
    "- BẮT BUỘC giữ NGUYÊN VĂN từng placeholder, đúng vị trí tương ứng, trên dòng riêng.\n"
    "- KHÔNG dịch, KHÔNG sửa, KHÔNG xóa, KHÔNG thêm placeholder.\n\n"
    "=====================\n"
    "II. QUY TẮC DỊCH\n"
    "=====================\n"
    "- Dịch tự nhiên, chính xác, đúng thuật ngữ chuyên ngành của tài liệu.\n"
    "- KHÔNG dịch: tên riêng, tên thương hiệu, URL, đường dẫn tệp, mã/lệnh, "
    "ký hiệu toán học.\n"
    "- Thuật ngữ kỹ thuật không có từ tiếng Việt thông dụng thì giữ nguyên "
    "tiếng Anh.\n\n"
    "=====================\n"
    "III. ĐỊNH DẠNG TRUNG THỰC\n"
    "=====================\n"
    "- KHÔNG tự ý in đậm, làm đẹp hay thay đổi format.\n"
    "- Chỗ nào bản gốc in đậm (**...**) thì bản dịch giữ in đậm; "
    "bản gốc không in đậm thì TUYỆT ĐỐI không thêm.\n"
    "- Giữ nguyên các heading đã có sẵn trong bản gốc (vd: \"## Trang 5\").\n"
    "- Không bỏ sót nội dung.\n\n"
    "=====================\n"
    "IV. OUTPUT\n"
    "=====================\n"
    "CHỈ trả về nội dung Markdown đã dịch, KHÔNG thêm lời mở đầu, "
    "giải thích hay nhận xét."
)


def _extract_boards(md, chess=True):
    """Thay từng block cần giữ nguyên bằng placeholder, trả (md, list block gốc).

    chess=True: chỉ tách block ```chessboard. chess=False: tách MỌI fenced
    code block (tài liệu thường — code/lệnh không được dịch).
    """
    blocks = []

    def repl(match):
        blocks.append(match.group(0))
        return _PLACEHOLDER_FMT.format(n=len(blocks))

    pattern = _CHESSBOARD_BLOCK_RE if chess else _CODE_BLOCK_RE
    return pattern.sub(repl, md), blocks


def _restore_boards(md, blocks):
    """Khôi phục các placeholder về block ```chessboard nguyên văn."""

    def repl(match):
        i = int(match.group(1)) - 1
        if 0 <= i < len(blocks):
            return blocks[i]
        return match.group(0)

    return _PLACEHOLDER_RE.sub(repl, md)


def _split_chunks(md, max_chars=6000):
    """Chia Markdown thành các chunk <= max_chars, cắt tại ranh giới '\\n## '.

    Đầu ra của ocr_pdf có header '## Trang N' cho mỗi trang nên thường mỗi
    chunk gộp được vài trang. Đoạn nào tự nó dài hơn max_chars thì giữ
    nguyên thành 1 chunk (không cắt giữa chừng).
    """
    md = md.strip()
    if not md:
        return []
    # Tách giữ nguyên nội dung: mỗi phần tử bắt đầu bằng '## ' (trừ phần đầu).
    parts = re.split(r"\n(?=## )", md)
    chunks = []
    cur = ""
    for part in parts:
        if not cur:
            cur = part
        elif len(cur) + 1 + len(part) <= max_chars:
            cur = cur + "\n" + part
        else:
            chunks.append(cur)
            cur = part
    if cur:
        chunks.append(cur)
    return chunks


def _call_claude(chunk, model="opus", timeout=600, instruction=None):
    """Gọi `claude -p` dịch một chunk (đưa qua stdin). Trả về text đã dịch."""
    claude = find_claude()
    if not claude:
        raise ClaudeOCRError(
            "Không tìm thấy Claude Code (lệnh 'claude') trong PATH. "
            "Hãy đảm bảo Claude Code đã được cài và đăng nhập."
        )

    # Dịch không cần extended thinking -> effort low (override settings).
    cmd = [
        claude,
        "-p",
        instruction or TRANSLATE_INSTRUCTION_CHESS,
        "--output-format",
        "json",
        "--model",
        model,
    ] + _claude_fast_flags("low")

    try:
        proc = subprocess.run(
            cmd,
            input=chunk,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_claude_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeOCRError(
            f"Claude Code quá thời gian ({timeout}s) khi dịch."
        ) from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        raise ClaudeOCRError(f"Claude Code lỗi (exit {proc.returncode}): {detail}")

    out = (proc.stdout or "").strip()
    if not out:
        raise ClaudeOCRError("Claude Code không trả về dữ liệu.")

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            return result.strip()
    return out


def _placeholders_in(text):
    """Tập số thứ tự placeholder xuất hiện trong text."""
    return set(_PLACEHOLDER_RE.findall(text))


# Số chunk dịch song song (mỗi chunk là một tiến trình `claude` riêng).
TRANSLATE_WORKERS = 8


def _translate_chunk(chunk, model, timeout, instruction):
    """Dịch 1 chunk với 1 lần thử lại + hậu kiểm placeholder.

    Chunk lỗi hoặc bị mất placeholder -> trả về nguyên văn chunk kèm ghi chú,
    không raise (để không hủy cả bản dịch).
    """
    translated = None
    err = None
    for _attempt in range(2):  # thử lại 1 lần nếu lỗi
        try:
            translated = _call_claude(
                chunk, model=model, timeout=timeout, instruction=instruction
            )
            break
        except ClaudeOCRError as exc:
            err = exc
    if translated is None:
        return f"{chunk}\n\n*[Lỗi dịch đoạn này: {err}]*"
    # An toàn: bản dịch phải giữ đủ placeholder của chunk gốc,
    # nếu thiếu thì dùng lại nguyên văn để không mất bàn cờ/code nào.
    if not _placeholders_in(chunk) <= _placeholders_in(translated):
        return f"{chunk}\n\n*[Đoạn này dịch bị mất khối bàn cờ/code nên giữ nguyên văn]*"
    return translated


def translate_markdown_vn(
    md, model="opus", progress=None, timeout=600, chess=True,
    workers=TRANSLATE_WORKERS,
):
    """Dịch Markdown sang tiếng Việt.

    chess=True (sách cờ vua): dịch theo quy tắc ký hiệu cờ vua (V/H/X/T/M...),
    giữ nguyên các block ```chessboard.
    chess=False (tài liệu thường): dịch thông thường, giữ nguyên mọi code block.

    Các chunk được dịch song song `workers` chunk một lúc, ghép đúng thứ tự.
    progress: callable(i, n) — gọi mỗi khi xong thêm một chunk (i = số đã xong).
    Chunk lỗi (sau 1 lần thử lại) hoặc bị mất placeholder -> giữ nguyên văn
    chunk gốc kèm ghi chú, không hủy cả bản dịch.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    instruction = TRANSLATE_INSTRUCTION_CHESS if chess else TRANSLATE_INSTRUCTION_GENERAL
    text, blocks = _extract_boards(md, chess=chess)
    chunks = _split_chunks(text)
    if not chunks:
        return md

    out_parts = [None] * len(chunks)
    n_done = 0
    if progress is not None:
        progress(0, len(chunks))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_translate_chunk, chunk, model, timeout, instruction): idx
            for idx, chunk in enumerate(chunks)
        }
        for fut in as_completed(futures):
            out_parts[futures[fut]] = fut.result()
            n_done += 1
            if progress is not None:
                progress(n_done, len(chunks))

    return _restore_boards("\n\n".join(out_parts).strip(), blocks)
