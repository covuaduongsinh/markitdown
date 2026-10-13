# Tính năng 12 — Đăng nhập Claude Code CLI bền vững (OAuth token 1 năm)

> Tài liệu này mô tả mã nguồn thêm vào ngày 2026-10-13.
> Tệp chính: `claude_login_bridge.py` (file mới). Liên quan: `claude_ocr.py:_claude_env`, `infrastructure.py`,
> `markitdown_gui.py` (tab "⚙️ Cài đặt Hạ tầng & API").

---

# Phần A — Chức năng

## Bài toán

Trước đây, để dùng gói thuê bao Claude Pro/Max cho OCR, người dùng phải tự lấy cookie `sessionKey` từ
claude.ai (F12 → Application → Cookies) dán vào ô trên web — cookie này hết hạn nhanh, phải lặp lại
thường xuyên, và (như phát hiện ở [05](05-ha-tang-va-ket-noi.md)) mã nguồn cũ còn đặt nó vào biến môi
trường sai (`ANTHROPIC_API_KEY`) khiến CLI xác thực sai kiểu, gây lỗi OCR hàng loạt.

## Người dùng nhận được gì

- Một nút **"🔐 Đăng nhập Claude Code"** ngay trên tab "Cài đặt Hạ tầng & API": bấm vào, web hiện link
  đăng nhập, mở link đó trên trình duyệt của bạn (không phải trên server), đăng nhập bằng tài khoản
  Claude Pro/Max, dán mã xác nhận ngược lại ô trên web nếu được yêu cầu.
- Token sinh ra (từ lệnh chính thức `claude setup-token`) **sống khoảng 1 năm** — thay vì phải lấy lại
  cookie mỗi vài ngày, giờ chỉ cần làm lại việc này khoảng 1 lần/năm.
- Token tự điền vào ô "Claude Code OAuth Token" để dùng ngay trong phiên hiện tại; web cũng hiện rõ
  chuỗi token để người dùng tự copy dán vào biến môi trường `CLAUDE_CODE_OAUTH_TOKEN` trong cấu hình
  Dokploy, giúp token này **sống qua mọi lần deploy lại** mà không cần thao tác gì trên web nữa.
- Vẫn giữ cách cũ (SSH vào server chạy `claude setup-token` tay) làm phương án dự phòng nếu nút trên web
  gặp sự cố.

---

# Phần B — Kỹ thuật

## 1. Vì sao tách file riêng, không gộp vào `infrastructure.py`

`infrastructure.py` là tập hợp các hàm **chạy-xong-là-xong** (mỗi `test_*_connection` là một
`subprocess.run` chặn, không giữ trạng thái). Luồng đăng nhập cần một tiến trình `claude setup-token`
**sống xuyên nhiều HTTP request** của Gradio (mở link → chờ người dùng đăng nhập trên trình duyệt riêng
→ dán mã lại ở một request khác) — nên cần một singleton cấp module (khoá bằng `threading.Lock`), khác
hẳn bản chất với các hàm còn lại.

## 2. Luồng xử lý

```mermaid
flowchart TD
    A["Bấm Đăng nhập Claude Code"] --> B["start_claude_login()<br/>spawn: claude setup-token"]
    B --> C["thread nền đọc stdout<br/>regex bắt URL"]
    C --> D["Trả URL cho UI hiển thị"]
    D --> E["Người dùng mở URL TRÊN MÁY HỌ, đăng nhập"]
    E --> F{"Trình duyệt redirect<br/>được về CLI?"}
    F -- "Không (SSH/container — case này)" --> G["CLI hiện mã, chờ dán ngược vào stdin"]
    G --> H["Người dùng dán mã vào ô web"]
    H --> I["submit_claude_login_code(code)<br/>ghi vào stdin tiến trình"]
    I --> J["thread đọc tiếp, bắt dòng token + dấu hiệu success"]
    J --> K{"Tiến trình thoát mã 0?"}
    K -- "có" --> L["status=success<br/>(LUÔN coi thành công dù heuristic không khớp)"]
    K -- "khác 0" --> M["status=error hoặc unknown"]
```

## 3. Singleton trạng thái (`claude_login_bridge.py`)

Biến module `_STATE` (bảo vệ bởi `_LOCK`) giữ: `proc` (Popen đang chạy), `session_id` (uuid, phân biệt
phiên cũ/mới — thread đọc cũ tự rút lui ngay khi phát hiện `session_id` đã đổi), `status`
(`idle|starting|waiting_code|working|success|error|unknown`), `url`, `token`, `error`, `lines` (tối đa
200 dòng log gần nhất), và một `watchdog` (`threading.Timer`) tự dọn tiến trình bỏ dở sau
`IDLE_TIMEOUT_S = 300` giây không ai tương tác.

Hai hàm chính:
- `start_claude_login()` — spawn `[claude_bin, "setup-token"]` (**không** `shell=True`), chờ có giới hạn
  thời gian (`URL_WAIT_TIMEOUT_S = 45s`) để lấy URL.
- `submit_claude_login_code(code, session_id)` — ghi mã vào stdin (an toàn ranh giới UTF-8, không cắt
  giữa ký tự nhiều byte), chờ kết quả (`CODE_RESULT_TIMEOUT_S = 60s`).

**Quy tắc cứng** (áp dụng từ kinh nghiệm các dự án cầu nối CLI thuê bao tương tự trước đây):
- Tiến trình thoát mã 0 → **luôn** coi là thành công, dù heuristic chuỗi ("success"/"logged in") không
  khớp dòng nào — khi đó `token` có thể là `None`, UI hiện 15 dòng log cuối để người dùng tự đọc/copy
  token bằng tay (đường thoát bắt buộc, không được âm thầm báo lỗi).
- Hết thời gian chờ → trạng thái `unknown`, **không** khẳng định thất bại (timeout khác đăng xuất/lỗi thật).
- Giết tiến trình luôn TERM trước rồi mới KILL, giết cả cây tiến trình con (`os.killpg` + `start_new_session=True`
  lúc spawn trên POSIX; `taskkill /F /T /PID` trên Windows — nhánh Windows chỉ để đọc code khi dev, chưa
  chạy thật được ở đó).

## 4. Nối vào UI (`markitdown_gui.py`)

Thêm vào `gr.Group()` của Claude Code (cạnh ô `claude_token_in`): nút "Đăng nhập Claude Code", một
`gr.Markdown` ẩn/hiện để chỉ URL, một `gr.Textbox` ẩn/hiện để dán mã, nút "Xác nhận mã", nút "Hủy". Khi
thành công, kết quả tự gán vào `claude_token_in.value` — tận dụng wiring `.change` đã có sẵn trước đó
(tự lưu `gr.BrowserState` localStorage + tự vẽ lại bảng trạng thái hạ tầng), không cần viết thêm logic lưu.

## 5. Điểm cần lưu ý và hạn chế

**Chưa kiểm chứng — cần thử thật trên VPS, đừng tin các giả định sau tới khi đã quan sát thật:**
- Định dạng chính xác dòng URL / dòng nhắc "dán mã" / dòng in token cuối cùng của `claude setup-token`
  (heuristic hiện tại: dòng không khoảng trắng, dài trên 20 ký tự, xuất hiện sau dấu hiệu "success").
- CLI có tự thoát (exit 0) ngay sau khi in token, hay treo thêm — module có timer phòng thủ tự kill sau
  3 giây kể từ khi bắt được token, nhưng đây là suy đoán, chưa xác nhận có cần thiết không.
- `claude setup-token` có ghi `~/.claude/.credentials.json` như side-effect không (ảnh hưởng đánh giá có
  nên lo ngại việc kill-tree làm hỏng file đó hay không, như từng xảy ra ở dự án cầu nối CLI khác).

**Vận hành**
- Chỉ một phiên đăng nhập được chạy cùng lúc trên toàn server (singleton cấp tiến trình Python, không
  phải cấp người dùng) — nếu nhiều tab cùng bấm "Đăng nhập", tab sau sẽ nhận lại đúng trạng thái của
  phiên đang chạy thay vì tạo tiến trình mới chồng lên.
- Test cục bộ (không gọi AI thật) đã kiểm chứng: bắt URL, ghi stdin, heuristic success/error, timeout,
  dọn tiến trình — bằng một CLI Python giả lập hành vi `claude setup-token`. Phần hành vi thật của CLI
  thật (mục "chưa kiểm chứng" ở trên) cần thử trên VPS khi triển khai.

## 6. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Singleton trạng thái + 2 hàm chính | `claude_login_bridge.py` `start_claude_login`, `submit_claude_login_code` |
| Giết tiến trình an toàn (TERM→KILL cả cây) | `claude_login_bridge.py` `_kill_tree` |
| Ghi stdin an toàn ranh giới UTF-8 | `claude_login_bridge.py` `_write_stdin_safe` |
| Nối UI, nút bấm | `markitdown_gui.py` quanh ô `claude_token_in` (tab "Cài đặt Hạ tầng & API") |
| Biến môi trường đúng cho subprocess `claude` | `claude_ocr.py:_claude_env`, `infrastructure.py:test_claude_cli_connection` |
