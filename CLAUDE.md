# CLAUDE.md

@AGENTS.md

## Ghi chú riêng cho Claude Code

- Toàn bộ quy ước, ranh giới, bản đồ tệp và quy trình nằm ở `AGENTS.md` (được nhập ở trên). Đọc nó trước.
- Dùng `.venv\Scripts\python.exe`, không dùng `python` trần.
- **Đừng chạy** `agy`, `claude -p`, hay gọi Gemini/Dropbox thật để kiểm thử — tốn hạn mức và ghi lên tài khoản của chủ dự án.
  Hàm thuần (`_split_chunks`, `_normalize_chessboard_blocks`, `_looks_untranslated`, `extract_fens`…) có thể gọi trực tiếp bằng
  `python -c` để kiểm chứng.
- Hai tệp `_test_*.py` không được `pytest` tự nhặt; chạy bằng `python <tệp>` hoặc `python -m unittest`.
- Trước khi khẳng định hành vi của `agy`/`claude`/Gemini, kiểm lại trong mã hoặc ghi rõ "chưa kiểm chứng" (xem `docs/RA-SOAT-RUI-RO.md`).
- Bộ nhớ dự án (quyết định, bẫy, việc dang dở): `MEMORY.md`. Nhật ký các phiên: `docs/LICH-SU-PHAT-TRIEN.md` mục 4 — cập nhật cả hai khi kết thúc
  một phiên có thay đổi đáng kể.
- Tài liệu dự án được viết bằng skill `document-repo` (hai tầng: Phần A chức năng / Phần B kỹ thuật; kết bằng "Điểm cần lưu ý và hạn chế" +
  "Đường dẫn tham chiếu nhanh"). Khi thêm tài liệu tính năng mới, theo cùng mẫu.
- Skill `ai-subscription-bridge` (trong `~/.claude/skills`) mô tả đúng bài toán của `ai_engine.py`/`infrastructure.py` (dùng CLI thuê bao thay
  khoá API, đăng nhập trên giao diện, chạy trên VPS) — tham khảo khi sửa hai tệp đó hoặc thêm engine.
