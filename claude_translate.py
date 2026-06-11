# -*- coding: utf-8 -*-
"""
Dịch Markdown (sách cờ vua) sang tiếng Việt bằng Claude Code headless.

Cùng cơ chế với claude_ocr.py: gọi CLI `claude -p` dùng phiên đăng nhập
Claude Code hiện có, KHÔNG cần API key. Nội dung cần dịch được đưa qua
stdin để tránh giới hạn độ dài command line trên Windows.

Các block ```chessboard (FEN bàn cờ) được tách ra thành placeholder trước
khi dịch và khôi phục nguyên văn sau khi dịch — đảm bảo FEN không bao giờ
bị dịch/sửa/mất.
"""

import json
import re
import subprocess

from claude_ocr import ClaudeOCRError, find_claude

# Regex block chessboard — giống _CHESSBOARD_BLOCK_RE trong claude_ocr.py.
_CHESSBOARD_BLOCK_RE = re.compile(r"```[ \t]*chessboard[^\n]*\n(.*?)```", re.DOTALL)

_PLACEHOLDER_FMT = "⟦CHESSBOARD_{n}⟧"
_PLACEHOLDER_RE = re.compile(r"⟦CHESSBOARD_(\d+)⟧")

TRANSLATE_INSTRUCTION = (
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


def _extract_boards(md):
    """Thay từng block ```chessboard bằng placeholder, trả (md, list block gốc)."""
    blocks = []

    def repl(match):
        blocks.append(match.group(0))
        return _PLACEHOLDER_FMT.format(n=len(blocks))

    return _CHESSBOARD_BLOCK_RE.sub(repl, md), blocks


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


def _call_claude(chunk, model="opus", timeout=600):
    """Gọi `claude -p` dịch một chunk (đưa qua stdin). Trả về text đã dịch."""
    claude = find_claude()
    if not claude:
        raise ClaudeOCRError(
            "Không tìm thấy Claude Code (lệnh 'claude') trong PATH. "
            "Hãy đảm bảo Claude Code đã được cài và đăng nhập."
        )

    cmd = [
        claude,
        "-p",
        TRANSLATE_INSTRUCTION,
        "--output-format",
        "json",
        "--model",
        model,
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=chunk,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
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


def translate_markdown_vn(md, model="opus", progress=None, timeout=600):
    """Dịch Markdown sang tiếng Việt, giữ nguyên các block ```chessboard.

    progress: callable(i, n) báo tiến độ theo chunk (tùy chọn).
    Chunk lỗi (sau 1 lần thử lại) hoặc bị mất placeholder bàn cờ -> giữ
    nguyên văn chunk gốc kèm ghi chú, không hủy cả bản dịch.
    """
    text, blocks = _extract_boards(md)
    chunks = _split_chunks(text)
    if not chunks:
        return md

    out_parts = []
    for i, chunk in enumerate(chunks, 1):
        if progress is not None:
            progress(i, len(chunks))
        translated = None
        err = None
        for _attempt in range(2):  # thử lại 1 lần nếu lỗi
            try:
                translated = _call_claude(chunk, model=model, timeout=timeout)
                break
            except ClaudeOCRError as exc:
                err = exc
        if translated is None:
            out_parts.append(f"{chunk}\n\n*[Lỗi dịch đoạn này: {err}]*")
            continue
        # An toàn: bản dịch phải giữ đủ placeholder bàn cờ của chunk gốc,
        # nếu thiếu thì dùng lại nguyên văn để không mất bàn cờ nào.
        if not _placeholders_in(chunk) <= _placeholders_in(translated):
            out_parts.append(
                f"{chunk}\n\n*[Đoạn này dịch bị mất hình bàn cờ nên giữ nguyên văn]*"
            )
            continue
        out_parts.append(translated)

    return _restore_boards("\n\n".join(out_parts).strip(), blocks)
