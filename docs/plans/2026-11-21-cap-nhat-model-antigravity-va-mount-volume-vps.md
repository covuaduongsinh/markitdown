# Kế hoạch Cập nhật Model Antigravity Thế hệ mới & Cấu hình Bền vững Phiên đăng nhập VPS (2026-11-21)

> **Mục tiêu:** Cập nhật danh sách model Google Antigravity theo chuẩn mới nhất (Gemini 3.8 Flash, Gemini 4 Neon, Argon, Hydrogen, Claude 5.5), đổi model mặc định từ `gemini-3.7-flash` sang `gemini-3.8-flash`, đồng thời cấu hình mount volume bền vững cho `/root/.gemini` trên Dokploy VPS để không bị mất đăng nhập sau mỗi lần deploy.

---

## 1. Kết quả Rà soát & Bằng chứng Kỹ thuật Thực tế

Qua kiểm tra trực tiếp trên VPS `217.15.160.118`:

### 1.1. Về sự thay đổi Model của Google Antigravity
Khi chạy thử model cũ `gemini-3.7-flash` trên `agy 1.5.14`:
```text
error: invalid model selection (--model "gemini-3.7-flash" --effort ""): model gemini-3.7-flash is not recognized as a known model or custom model in settings
```
CLI `agy 1.5.14` đã chính thức loại bỏ các model cũ (`gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.1-pro`, `claude-sonnet-4-6`). Danh sách model mới hiện tại gồm:
- **`gemini-3.8-flash`** (hỗ trợ các mức effort: `low`, `medium`, `high`) — Khuyên dùng làm mặc định cho OCR và Dịch vì tốc độ cực nhanh và nhận diện cờ vua chính xác.
- **`gemini-4-neon`** (hỗ trợ `low`, `medium`, `high`, `xhigh`) — Thế hệ Gemini 4 mới nhất, cân bằng và thông minh.
- **`gemini-4-hydrogen`** (hỗ trợ `low`, `medium`, `high`, `xhigh`) — Model siêu nhẹ, tốc độ cao nhất.
- **`gemini-4-argon`** (hỗ trợ `low`, `medium`, `high`) — Phân tích cờ chuyên sâu.
- **`claude-sonnet-5-5`** (hỗ trợ `low`, `medium`, `high`) — Claude Sonnet 5.5 mới nhất.
- **`claude-opus-5-5`** (hỗ trợ `low`, `medium`, `high`) — Claude Opus 5.5 cao cấp.

### 1.2. Về phiên đăng nhập trên VPS Docker
- VPS Host (`217.15.160.118`) tại `/root/.gemini/` **đã có sẵn tài khoản Google hợp lệ** của chủ dự án (đã test `agy -p "1+1=?" --model gemini-3.8-flash --effort low` ra kết quả `2` thành công).
- Tuy nhiên, dịch vụ Dokploy chạy container Docker độc lập chưa mount `/root/.gemini` từ host, nên khi container mới deploy sẽ bị thiếu token OAuth và đòi `agy login`.
- Đã kiểm chứng: Khi copy `/root/.gemini` từ host vào container `app-copy-primary-feed-r4ikwl`, container thực thi ngay lập tức prompt `1+1=?` trả về `2` mượt mà.

---

## 2. Kế hoạch Triển khai Chi tiết

### Giai đoạn 1: Cập nhật Danh sách Model & Model Mặc định trong Codebase
1. **`ai_engine.py`**:
   - Cập nhật danh sách `ANTIGRAVITY_OCR_MODELS`:
     - Gemini 3.8 Flash (Mặc định)
     - Gemini 4 Neon
     - Gemini 4 Hydrogen
     - Gemini 4 Argon
     - Claude Sonnet 5.5
     - Claude Opus 5.5
   - Cập nhật danh sách `ANTIGRAVITY_TRANSLATE_MODELS`: tương tự như trên.
   - Cập nhật fallback model trong `call_gemini_api_direct` và `run_agy_prompt`.
2. **`claude_ocr.py` & `claude_translate.py`**:
   - Đổi giá trị mặc định `model="gemini-3.7-flash"` thành `model="gemini-3.8-flash"`.
3. **`markitdown_gui.py`**:
   - Cập nhật dropdown choices và default value của model OCR và Dịch.
4. **Kiểm thử cục bộ**:
   - Chạy test roundtrip tiếng Việt và FEN (`_test_translate_roundtrip.py`).
   - Smoke test import và khởi tạo giao diện Gradio.

### Giai đoạn 2: Cấu hình Bền vững Phiên Đăng nhập trên VPS Dokploy
1. **Cấu hình Volume Mount**:
   - Cập nhật Docker Swarm service `app-copy-primary-feed-r4ikwl` trên VPS để mount bind volume:
     `--mount-add type=bind,source=/root/.gemini,target=/root/.gemini`
   - Nhờ vậy, mọi lần deploy lại container sau này đều tự động thừa hưởng đăng nhập Google Antigravity của VPS host mà không bao giờ bị mất lại.
2. **Thêm Volume Mount cho Claude Code (nếu có)**:
   - Mount tương tự cho `/root/.claude.json` hoặc `/root/.claude` nếu có nhu cầu dùng song song Claude Code CLI.

### Giai đoạn 3: Triển khai & Xác minh Thực tế trên VPS
1. [x] Commit các thay đổi code lên GitHub (`origin main`) - Commit `d72cc40`.
2. [x] Trigger Dokploy redeploy ứng dụng `markitdown-web` thành công.
3. [x] Kiểm tra log khởi động container và xác minh mount volume bên trong container:
   - Mount: `[{"Type":"bind","Source":"/root/.gemini","Destination":"/root/.gemini"}]`
   - Test trong container: `agy -p '1+1=?' --model gemini-3.8-flash --effort low` -> Trả về `1 + 1 = 2` thành công không cần login lại.
   - Giao diện web `https://markitdown.dsc.edu.vn` hoạt động bình thường (`HTTP 200`).
4. [x] Cập nhật tài liệu `MEMORY.md` và `docs/LICH-SU-PHAT-TRIEN.md`.
