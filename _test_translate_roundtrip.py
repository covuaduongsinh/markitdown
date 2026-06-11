# -*- coding: utf-8 -*-
"""Test nhanh (không gọi Claude): tách/khôi phục block chessboard + chia chunk."""
import claude_translate as ct

MD = """## Trang 1

# Chapter 1

Some intro text about the King's Gambit.

```chessboard
fen: r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3
```

1.e4 e5 2.Nf3 Nc6

## Trang 2

More text here.

```chessboard
fen: 8/8/8/8/8/8/8/K6k w - - 0 1
strict: false
```

*[Cảnh báo: FEN ở trên có thể sai, hãy đối chiếu lại với hình cờ]*
"""

# 1. Round-trip extract/restore phải giữ nguyên byte-by-byte
text, blocks = ct._extract_boards(MD)
assert len(blocks) == 2, blocks
assert "```chessboard" not in text
assert "⟦CHESSBOARD_1⟧" in text and "⟦CHESSBOARD_2⟧" in text
restored = ct._restore_boards(text, blocks)
assert restored == MD, "round-trip khác bản gốc!"

# 2. Chia chunk tại ranh giới '## ' và ghép lại không mất nội dung
chunks = ct._split_chunks(text, max_chars=80)
assert len(chunks) >= 2, chunks
rejoined = "\n".join(chunks)
assert rejoined == text.strip(), "ghép chunk khác bản gốc!"

# 3. max_chars lớn -> 1 chunk duy nhất
assert len(ct._split_chunks(text, max_chars=10**6)) == 1

# 4. Kiểm tra placeholder bị mất -> phát hiện được
assert not (ct._placeholders_in("⟦CHESSBOARD_1⟧ x ⟦CHESSBOARD_2⟧")
            <= ct._placeholders_in("⟦CHESSBOARD_1⟧ only"))
assert ct._placeholders_in("⟦CHESSBOARD_1⟧") <= ct._placeholders_in(
    "dịch rồi ⟦CHESSBOARD_1⟧ xong")

# 5. Văn bản rỗng
assert ct._split_chunks("") == []

print("Tất cả test round-trip OK")
