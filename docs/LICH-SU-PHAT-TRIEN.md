# Lịch sử phát triển và nhật ký tương tác

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Nguồn: `git log --author=covuaduongsinh` (24 commit của fork trên tổng 428 commit của repo), thông điệp commit, các
> kế hoạch trong `docs/plans/`, và các phiên làm việc với trợ lý AI (mục 4).
> Chỉ ghi điều có bằng chứng trong git hoặc tài liệu; phần "vì sao" lấy từ chú thích mã và tài liệu, không suy đoán.

## 1. Bức tranh chung

Repo là fork của `microsoft/markitdown`. Lịch sử upstream bắt đầu từ 2024-11-13; **phần của fork bắt đầu 2026-06-10**.
Fork chưa bao giờ sửa lõi thư viện: mọi thay đổi của fork là **tệp mới ở thư mục gốc** cộng vài tài liệu, và hai lần merge từ upstream.

```mermaid
timeline
    title Các giai đoạn của bản fork
    2026-06-10 → 06-17 : Ứng dụng web đầu tiên
                        : OCR sách cờ vua bằng Claude Code
                        : Nhận diện bàn cờ FEN, dịch, Nga, Tây Ban Nha
                        : Giao diện Cờ vua Dương Sinh
    2026-09-12 → 09-13 : Đổi sang Google Antigravity làm mặc định
                        : Thử lại OCR ảnh lẻ
                        : Merge upstream lần 1
    2026-09-17 : Đưa lên web (Docker, Dokploy)
               : Trung tâm cài đặt hạ tầng
               : Token thuê bao, Gemini REST
               : Merge upstream lần 2
    2026-09-27 : Đồng bộ Dropbox
    2026-09-30 : Bộ tài liệu này
```

## 2. Dòng thời gian commit của fork

Sắp theo ngày. Thông điệp ngắn (tiếng Việt không dấu hoặc tiếng Anh) được chép nguyên; thông điệp dài được rút gọn
và có chỗ thêm dấu tiếng Việt — xem `git log` để có bản gốc.

| Ngày | Commit | Thông điệp | Ý nghĩa |
|---|---|---|---|
| 2026-06-10 | `bb16393` | web gui | Khởi tạo `markitdown_gui.py` (Gradio) |
| 2026-06-11 | `c772c50`, `f7b378a` | batch file, fix batch file | `run_gui.bat` |
| 2026-06-11 | `6ca19bc` | ocr chess board | Nhận diện bàn cờ (`chessboard_fen.py`) |
| 2026-06-11 | `1f3ad58` | ocr chess book | OCR sách cờ vua (`claude_ocr.py`) |
| 2026-06-11 | `0e2972d` | sonet + giảm effort low | Đổi model mặc định sang Sonnet, hạ effort xuống `low` (xem chú thích `_claude_fast_flags`) |
| 2026-06-11 | `f46c6ab` | translate chessbook | Dịch sách (`claude_translate.py`) |
| 2026-06-12 | `f583918` | bo header footer | Bỏ header/footer/số trang (`_PROMPT_CLEANUP`) |
| 2026-06-12 | `829a67e` | tiếng nga | Chế độ ký hiệu Nga |
| 2026-06-15 | `49d4059` | giao diện mới Cờ vua Dương Sinh + bàn cờ FEN | Giao diện navy/sun/teal; vẽ bàn cờ trong xem trước |
| 2026-06-17 | `2e264f9` | Tay ban nha | Chế độ ký hiệu Tây Ban Nha |
| 2026-09-12 | `3acbbee` | feat: tích hợp Google Antigravity làm AI engine mặc định và tối ưu tiết kiệm token | Tạo `ai_engine.py`; các preset Tiết kiệm/Cân bằng/Chính xác; gộp OCR+dịch |
| 2026-09-13 | `721a8ac` | fix(ocr): retry single-image OCR, refresh GUI docs/launcher | Thử lại ảnh lẻ; `GUI_README.md` |
| 2026-09-13 | `46d5350` | merge: cập nhật từ upstream | Merge upstream #1 |
| 2026-09-17 | `bf9b723` | feat(deploy): update Dockerfile and launcher for web production deployment | Docker + bind `0.0.0.0` |
| 2026-09-17 | `b86e92f` | feat(ui): Infrastructure & API Setup Center, live connection testing, instant conversion feedback | `infrastructure.py`, thẻ Cài đặt Hạ tầng |
| 2026-09-17 | `1109e87` | feat: monthly subscription connection support for Claude Code and Antigravity CLI | Ô dán token thuê bao |
| 2026-09-17 | `a3cf11d` | feat: full support for Google Antigravity CLI and OAuth on VPS and Web | Lưu token Antigravity phía máy chủ |
| 2026-09-17 | `5c4c748` | fix(docker): allow copying root Python scripts and assets into image | Sửa `.dockerignore`/COPY |
| 2026-09-17 | `9e6ba26` | fix(web): Direct Gemini REST API support, robust file handling, graceful fallback | `call_gemini_api_direct` |
| 2026-09-17 | `3000e93` | fix: remove root restriction flag for claude cli test | Sửa kiểm tra Claude trong container chạy root |
| 2026-09-17 | `f2ddf6f` | fix: `is_engine_available` accepts `claude_token`, `agy_token` | Sửa chữ ký hàm |
| 2026-09-17 | `ba0a8ad` | merge: cập nhật từ upstream | Merge upstream #2 |
| 2026-09-27 | `2c1df67` | feat(dropbox): automatic Dropbox sync … | Dropbox (`infrastructure.py`, GUI, `docs/DROPBOX_GUIDE.md`) |

## 3. Các quyết định thiết kế và lý do (có bằng chứng)

| Quyết định | Vì sao | Bằng chứng |
|---|---|---|
| Dùng CLI thuê bao (`agy`, `claude`) thay khoá API | Không tốn tiền theo lượt; dùng phiên đăng nhập sẵn có | Docstring `claude_ocr.py`, `infrastructure.py`: *"KHÔNG cần API key"*, *"0đ phí API"* |
| Hạ `effort` xuống `low` | OCR chỉ là chép chữ; `effortLevel: xhigh` trong cài đặt người dùng khiến model "suy nghĩ hàng chục nghìn token mỗi trang" | Chú thích `_claude_fast_flags` (`claude_ocr.py:398`), commit `0e2972d` |
| Nhận diện bàn cờ bằng ONNX cục bộ | Không tốn quota AI, nhanh; AI chỉ chèn FEN đúng chỗ | Docstring `chessboard_fen.py`; prompt `_PROMPT_CHESS_GIVEN` |
| Vẽ trang ở DPI cao, thu nhỏ để gửi AI | Ảnh nét cho mô hình bàn cờ; ảnh nhỏ cho OCR | `_render_page_pair` |
| Gộp OCR + dịch trong một lần gọi | Tiết kiệm ~30–40% lượt gọi/hạn mức | Nhãn `Tùy chọn nâng cao` ở `markitdown_gui.py:1709`, `GUI_README.md` |
| Đặt banner "đầu ra = tiếng Việt" đầu prompt | Footer dịch ở cuối bị model bỏ qua khi nhiều trang/effort thấp | Chú thích `claude_ocr.py:161–164` |
| Tách placeholder `⟦CHESSBOARD_n⟧` khi dịch | Đảm bảo FEN không bao giờ bị dịch/sửa/mất | Docstring `claude_translate.py` |
| Chunk dịch cắt tại dòng trống | OCR không còn chèn `## Trang N`, cả sách dồn thành một chunk | Chú thích `_split_chunks` |
| Sách Nga giữ chữ Cyrillic đến bước dịch | Tránh đụng độ `K` Latin (Vua) với `К` Cyrillic (Mã) | Chú thích `claude_ocr.py:117–120` |
| Sách Tây Ban Nha: `T`→`X`, `A`→`T` | Bảng nguồn/đích dùng chung chữ cái | Chú thích `_CHESS_II_ES`, `GUI_README.md` |
| `pick_files.py` là tiến trình con | Tránh xung đột tkinter với luồng nền của Gradio | Docstring `pick_files.py` |
| `_stream_job` yield ≤ 5 s/lần | Kết nối SSE của Gradio không rớt khi tác vụ dài | Docstring `_stream_job` |
| Lưu tùy chọn ở `BrowserState` | Không phải nhập lại; không cần tài khoản/DB | `docs/DROPBOX_GUIDE.md`, `prefs` |
| Refresh Token cho Dropbox | Access Token chỉ sống vài giờ | `docs/plans/2026-09-27-dropbox-sync-integration.md` |

## 4. Nhật ký tương tác với trợ lý AI

Mục này ghi **những gì được yêu cầu và làm**, để phiên sau (người hay AI) nối tiếp được. Quy ước:
mỗi phiên một mục, ngày tuyệt đối, chỉ nêu điều không suy ra được từ git.

### 2026-09-30 — Phiên lập tài liệu

**Yêu cầu của chủ dự án:** tạo hoặc cập nhật các tệp `.md` quan trọng (`AGENTS.md`, `CLAUDE.md`, `README.md`,
`SKILLS.md`, `TECH.md`, `MEMORY.md`…) để thống kê, giới thiệu, mô tả chi tiết thuật toán, lưu lịch sử tương tác,
của **tất cả** module/tính năng — làm cơ sở **rà soát, xây dựng module mới, nhân bản phần mềm**.

**Đã làm** (chỉ thêm tệp `.md` mới, và thêm một khối đầu vào `README.md`; **không sửa mã**):

- Gốc repo: `AGENTS.md`, `CLAUDE.md`, `TECH.md`, `SKILLS.md`, `MEMORY.md`; thêm khối "Bản fork Cờ vua Dương Sinh" vào đầu `README.md`.
- `docs/`: `README.md` (mục lục), `TONG-QUAN-KIEN-TRUC.md`, `LICH-SU-PHAT-TRIEN.md` (tệp này),
  `NHAN-BAN-VA-MO-RONG.md`, `RA-SOAT-RUI-RO.md`.
- `docs/tinh-nang/01…11`: mười một tài liệu tính năng theo mẫu hai tầng (Phần A chức năng / Phần B kỹ thuật).

**Cách kiểm chứng:** số dòng bằng script đếm ký tự xuống dòng (không lấy từ công cụ đọc tệp); mọi đường dẫn tương đối;
mọi "điều đáng ngờ" đánh dấu là suy ra từ mã, chưa chạy thử.

**Chưa làm / để ngỏ:**
- Chưa chạy ứng dụng, chưa gọi `agy`/`claude`/Gemini/Dropbox thật → hành vi thời gian chạy chưa được xác nhận.
- Các mục trong `RA-SOAT-RUI-RO.md` chưa được sửa, chỉ ghi nhận.

### 2026-10-13 — Sửa lỗi OCR thất bại toàn bộ + đăng nhập Claude Code bền vững

**Bối cảnh:** Chủ dự án báo OCR trên web production lỗi "thất bại ở toàn bộ 97 trang". Điều tra qua SSH
vào VPS production (Dokploy) xác định CLI `claude` hoạt động bình thường,
nhưng cơ chế xác thực của ứng dụng dùng sai: `_claude_env`/`infrastructure.py` đặt cookie `sessionKey`
người dùng tự lấy từ claude.ai vào ba biến môi trường không chính thức, trong đó `ANTHROPIC_API_KEY` có
độ ưu tiên xác thực **cao hơn** biến đúng `CLAUDE_CODE_OAUTH_TOKEN` — khiến CLI luôn thử xác thực sai
kiểu. Xác nhận qua tài liệu chính thức Claude Code CLI (code.claude.com/docs/en/authentication).

**Yêu cầu tiếp theo của chủ dự án:** không muốn tiếp tục lấy lại cookie `sessionKey` thủ công mỗi lần hết
hạn — muốn cơ chế đăng nhập bền vững hơn, cả giải pháp nhanh lẫn một nút đăng nhập ngay trên web.

**Đã làm:**
- Sửa `claude_ocr.py:_claude_env`, `infrastructure.py` (`test_claude_cli_connection`,
  `get_infrastructure_status`): bỏ 3 biến sai, chỉ set `CLAUDE_CODE_OAUTH_TOKEN`.
- Thêm `claude --version` vào `Dockerfile` sau dòng cài Claude Code CLI để build fail cứng nếu cài lỗi.
- Sửa nhãn/hướng dẫn ô token trên UI (`markitdown_gui.py`) từ "cookie sessionKey" sang "OAuth Token từ
  `claude setup-token`".
- Thêm file mới `claude_login_bridge.py`: cầu nối pipe+regex quanh `claude setup-token` (singleton
  xuyên request HTTP, kill-tree an toàn, ghi stdin an toàn ranh giới UTF-8, timeout ≠ thất bại) + nút
  "Đăng nhập Claude Code" trên tab "Cài đặt Hạ tầng & API".
- Tài liệu mới `docs/tinh-nang/12-dang-nhap-claude-code.md`; cập nhật `05-ha-tang-va-ket-noi.md`,
  `RA-SOAT-RUI-RO.md` (đánh dấu S10 đã xử lý), `TONG-QUAN-KIEN-TRUC.md`, `docs/README.md`, `AGENTS.md`,
  `MEMORY.md`.

**Cách kiểm chứng:** hàm thuần `_claude_env`/`get_infrastructure_status` kiểm bằng `python -c` (không
gọi CLI thật); toàn bộ logic `claude_login_bridge.py` (bắt URL, ghi stdin, heuristic success/error,
timeout, dọn tiến trình) kiểm bằng một CLI Python giả lập hành vi `claude setup-token`, không gọi AI
thật; `markitdown_gui.py` import thành công (toàn bộ Blocks UI dựng được, xác nhận wiring đúng số
input/output).

**Chưa làm / để ngỏ:**
- Giai đoạn 0 của kế hoạch (chạy `claude setup-token` thật qua SSH, lấy token 1 năm, set vào biến môi
  trường Dokploy) cần chính chủ dự án tự thực hiện (đăng nhập bằng tài khoản cá nhân) — chưa xác nhận đã
  làm xong tại thời điểm ghi nhật ký này.
- Hành vi thật của `claude setup-token` (định dạng dòng output, có treo sau khi in token không) chưa
  được quan sát trên VPS thật — xem mục "chưa kiểm chứng" trong `docs/tinh-nang/12-dang-nhap-claude-code.md`.
- Chưa build lại Docker image / deploy lên Dokploy — thay đổi mới chỉ nằm trong working tree, chưa commit/push.

### 2026-11-21: Đồng bộ upstream microsoft/markitdown lên v0.1.9 (commit ed17895)

**Yêu cầu của chủ dự án:** Repo gốc có update, lên kế hoạch và triển khai update, đồng bộ vào repo ở local và GitHub. Từ giờ, các kế hoạch luôn để ở thư mục `/docs/plans`.

**Đã làm:**
- Tạo kế hoạch chi tiết tại [`plans/2026-11-21-dong-bo-upstream-markitdown.md`](plans/2026-11-21-dong-bo-upstream-markitdown.md).
- Commit toàn bộ bộ tài liệu kiến trúc, vận hành và kế hoạch vào nhánh `main` (`8d77815`).
- Merge thành công 23 commit mới từ `upstream/main` (`945314a..ed17895`) với merge commit `a722ceb`.
- Không phát sinh xung đột: git ort tự động gộp `README.md` (giữ nguyên banner fork Cờ vua Dương Sinh ở đầu và nhận nội dung mới về Azure Document Intelligence, hosted service của upstream). Toàn bộ 8 tệp mã nguồn riêng của fork ở thư mục gốc không bị ảnh hưởng.
- Cập nhật phiên bản các gói trong `TECH.md` (`markitdown` 0.1.9, `markitdown-ocr` 0.1.2, `markitdown-mcp` 0.0.1a8).
- Cập nhật bộ nhớ dự án trong `MEMORY.md`.

**Cách kiểm chứng:**
- Smoke test import upstream `MarkItDown()` và toàn bộ 7 module riêng của fork (`markitdown_gui`, `claude_ocr`, `claude_translate`, `chessboard_fen`, `ai_engine`, `infrastructure`, `claude_login_bridge`): đạt 100%.
- Kiểm tra toàn bộ test case roundtrip FEN và bảo vệ khối dịch tiếng Việt (`_test_translate_roundtrip.py`): đạt 100%.

- Đã deploy thành công lên VPS Dokploy (`217.15.160.118`), dịch vụ Docker Swarm `app-copy-primary-feed-r4ikwl` chuyển sang container mới, tên miền `https://markitdown.dsc.edu.vn` phản hồi `HTTP 200 OK`. Kế hoạch triển khai chi tiết tại [`plans/2026-11-21-trien-khai-cap-nhat-vps-dokploy.md`](plans/2026-11-21-trien-khai-cap-nhat-vps-dokploy.md).

### 2026-11-21: Cập nhật model Antigravity (Gemini 3.8/4) & Cấu hình Mount Volume bền vững trên VPS

**Yêu cầu của chủ dự án:** Người dùng gặp lỗi OCR thất bại ở toàn bộ các trang trên web production, nghi vấn model AI thay đổi. Rà soát, lên kế hoạch và khắc phục hoàn thiện.

**Đã làm:**
- Rà soát `agy 1.5.14` trên VPS phát hiện model `gemini-3.7-flash` đã bị khai tử; CLI báo lỗi `model gemini-3.7-flash is not recognized`. Các model mới: `gemini-3.8-flash`, `gemini-4-neon`, `gemini-4-hydrogen`, `gemini-4-argon`, `claude-sonnet-5-5`, `claude-opus-5-5`.
- Đồng thời phát hiện container Docker trên Dokploy bị thiếu bind mount thư mục `/root/.gemini` chứa token OAuth từ VPS host.
- Cập nhật danh sách model trong `ai_engine.py`, `claude_ocr.py`, `claude_translate.py`, `markitdown_gui.py`, đổi model mặc định thành `gemini-3.8-flash`.
- Thêm bind mount record vào cơ sở dữ liệu Dokploy (`mount` table: `/root/.gemini` -> `/root/.gemini`).
- Commit (`d72cc40`), kích hoạt Dokploy build và deploy service `app-copy-primary-feed-r4ikwl` mới.
- Container mới khởi động thành công với bind mount `/root/.gemini`, test trực tiếp lệnh `agy -p "1+1=?" --model gemini-3.8-flash --effort low` bên trong container trả về `2` chính xác. Web `https://markitdown.dsc.edu.vn` phản hồi HTTP 200.
- Chi tiết kế hoạch tại [`plans/2026-11-21-cap-nhat-model-antigravity-va-mount-volume-vps.md`](plans/2026-11-21-cap-nhat-model-antigravity-va-mount-volume-vps.md).

### 2026-11-21: Nâng cấp giao diện và tính năng — Giai đoạn 0 (chốt nền)

**Yêu cầu của chủ dự án:** thực hiện Giai đoạn 0 của `plans/2026-11-21-nang-cap-giao-dien-va-tinh-nang.md` (prompt: `…-prompt-trien-khai.md`).

**Đã làm** (nhánh `feat/nang-cap-giao-dien`, không push, không đụng production):
- G0.1 `3930dd8`: `requirements-gui.txt` ghim `gradio==6.32.0` (bản production) + các gói GUI theo `.venv`; `Dockerfile` cài từ tệp đó, bỏ `dropbox`; `.venv` nâng 6.17.3 → 6.32.0 (`gradio_client` 2.7.2).
- G0.2 `f491108`: engine giả `fake_engine.py` (`MID_FAKE_ENGINE=1`, `MID_FAKE_DELAY`, `MID_FAKE_FAIL_PAGES`) cắm vào `_run_engine_ocr`, `_call_engine_translate`, `is_engine_available`; không có khi thiếu biến.
- G0.3 `af6ee35`: tách `markitdown_gui.py` (2.104 → 1.043 dòng) thành `pipeline.py` (lõi, 477), `ui_theme.py`, `presets.py`, `ui_render.py`, `assets/ui/app.{css,js}`; gom ba khối lặp thành `_publish_output`; thay việc dò chuỗi `"gộp 1 bước"` (B9) bằng `ConvertResult.translated`.
- G0.4 `d0d819e`: `MID_AUTH_USER`+`MID_AUTH_PASS` → `launch(auth=…)`; chỉ đặt một biến thì từ chối khởi động.
- G0.5 `23d6812`: `tests_gui/` 29 test dùng engine giả.

**Quyết định + lý do:** chỉ đặt một trong hai biến auth → thoát lỗi (fail closed) thay vì chạy không khóa; engine giả là engine mặc định khi bật để kiểm thử không cần thao tác chọn; `_publish_output` giữ y nguyên chuỗi trạng thái cũ (kiểu chính/inline) để không đổi hành vi.

**Cách kiểm chứng:** `HEAD`, `CSS`, `TOPBAR_HTML`, `MODE_CARDS_HTML` sau khi tách **bằng từng byte** với trước khi tách; luồng PDF 6 trang × 3 chế độ cho cùng số ký tự trước/sau tách (2.006/2.036/1.492); chạy app thật ở cổng riêng: có auth → `/config` 401, sai mật khẩu 400, đúng 200; không auth → 200; một biến → thoát mã 1; không có tiến trình `agy`/`claude` nào bị gọi (chặn `subprocess` trong test). `_test_translate_roundtrip.py` và `unittest discover tests_gui` đạt.

**Chưa làm / chưa kiểm chứng:** `markitdown_gui.py` còn >900 dòng (xem bảng Tiến độ); chưa mở bằng trình duyệt (G0 không đổi giao diện, nhưng nâng Gradio có thể đổi vẻ ngoài dev — kiểm ở G1); đăng nhập chưa thử sau Traefik/HTTPS; chưa push/merge/deploy. Phát hiện thêm P1–P5 ở cuối kế hoạch.

### 2026-11-22: Giai đoạn 2 — công việc nền (G2.1–G2.8), đẩy G0 lên `main`

**Yêu cầu của chủ dự án:** (sau khi tắt auto deploy) làm theo đề xuất: push nhánh → build thử → merge G0 vào `main` → làm công việc nền (G2).

**Đã làm:**
- Push nhánh `feat/nang-cap-giao-dien`; không có Docker trên máy dev nên **không build image được** — thay bằng giải phụ thuộc Linux/Python 3.12 (`uv pip compile`) với đúng bộ gói của Dockerfile: thành công, giữ đúng các bản ghim. Merge fast-forward G0 vào `main` và push (`9faa7e9..985e82b`).
- G2.1–G2.3 `183696d`: `proc_control.py` (CancelToken, `run_cli`, diệt cây tiến trình), `jobs.py` (công việc lưu đĩa, hàng đợi, chạy tiếp, dọn dẹp), `ocr_pdf` nhận `pages/done_pages/on_page/cancel`, dịch có `chunk_cache`, engine giả hủy được.
- G2.4–G2.8 (commit kế tiếp): `job_handlers.py`/`job_view.py`, `gr.Timer` + `BrowserState` thay `_stream_job`, nút Dừng/Chạy tiếp/OCR lại trang lỗi, ô "Trang cần làm" + ước lượng lượt gọi, tab Lịch sử, tiêu đề tab/thông báo khi xong. Xóa `_stream_job`, `on_convert_files`, `_with_download_update`.
- `Dockerfile`: `ENV MID_DATA_DIR=/data MID_KEEP_DAYS=60`, `VOLUME /data` (phần mã của G2.9).

**Quyết định + lý do:** `OperationCancelled` là `BaseException` (không bị `except Exception` nuốt); token hủy đi qua `contextvars` thay vì thêm tham số vào ~10 chữ ký hàm; "Chạy tiếp" và "OCR lại trang lỗi" là một thao tác (chỉ gọi AI cho trang chưa có `.md`); `job_state` dùng `secret` cố định để sống qua redeploy; khóa/token không bao giờ ghi vào `job.json`.

**Cách kiểm chứng:** 56 test `unittest discover tests_gui` + `_test_translate_roundtrip.py` đạt (kể cả Dừng ≤3 s, diệt tiến trình thật, chạy tiếp đúng 2 trang lỗi, khoảng trang `2-4` = 3 lượt). Mở app thật bằng Chrome với engine giả: chạy 12 trang, tải lại trang giữa chừng (gắn lại), khởi động lại server rồi tải lại (gắn lại), Dừng (≤1,5 s) → Chạy tiếp từ trang đã giữ, Lịch sử, liên kết tải (bắt được lỗi 403 do thiếu `allowed_paths` — đã sửa).

**Cập nhật cùng ngày — G2.9 đã làm trên production (chủ dự án cho phép):** merge `main` (`a4ccbe3`), thêm mount `/root/markitdown-data`→`/data` + env vào Dokploy, deploy tay (bật `autoDeploy` một lần rồi tắt lại). Lần deploy đầu lỗi do Dockerfile chứa hai ký tự `\` và `n` thật thay cho xuống dòng (đã sửa ở `83fe754`); lần hai build thật thành công (~35 phút, VPS tải cao), site HTTP 200; công việc thử bằng engine giả còn nguyên sau khi thay container; đã xóa công việc thử.

**Chưa làm / chưa kiểm chứng (tại thời điểm viết mục G2 trước đó):** G2.9 (đã xong như trên); Docker build thật (đã xong); thử với AI thật; `Notification` của trình duyệt; ảnh trang thu nhỏ (G3.2); `prefs` còn mã hóa bằng khóa ngẫu nhiên (P6).

### 2026-11-22: Giai đoạn 1 — giao diện đúng thiết kế, dùng tốt trên điện thoại

**Yêu cầu của chủ dự án:** thực hiện Giai đoạn 1 của kế hoạch nâng cấp giao diện (prompt `…-prompt-trien-khai.md`, `GIAI_DOAN = 1`).

**Đã làm** (nhánh `feat/nang-cap-giao-dien`; không merge `main`, không đụng production):
- G1.1–G1.2: `ui_theme.THEME` bằng `.set()` (có `*_dark`), CSS viết lại bám id/lớp của ta; 40 tệp phông woff2 tự lưu trữ + `font_face_css()`; thẻ đổi từ `gr.Group` sang `gr.Column` (hết viền kép); bỏ Google Fonts.
- G1.3: vùng thả tiếng Việt, hàng đợi tệp tự vẽ (loại/dung lượng/số trang/×/Xóa hết/Thêm tệp), nút "Chuyển đổi N tệp" vô hiệu khi chưa có tệp.
- G1.4 + G1.9: `render_status_html` (chip, thanh tiến độ gradient, danh sách tệp, trạng thái rỗng); `on_convert_url` dùng `_publish_output` và có tùy chọn dịch.
- G1.5: chip chọn xem từng tệp, nút Sao chép Markdown, meta mỗi tệp, "Chạy lại" (`JobManager.clone`).
- G1.6: trang Cài đặt riêng (lưới thẻ 2 cột, hướng dẫn thu vào accordion), nút ⚙ + huy hiệu AI trên thanh tiêu đề.
- G1.7: di động (<780 px): nút hành động dính đáy, thẻ chế độ/chất lượng thu gọn, cuộn tới kết quả, vùng bấm ≥ 44 px.
- G1.8: preset không ghi đè công tắc; gợi ý sinh từ bảng; công tắc được lưu vào prefs.

**Quyết định + lý do:** bật/tắt trang Cài đặt bằng lớp trên chính phần tử và dùng biến CSS thay quy tắc `body…` (Gradio nhân quy tắc CSS có tiền tố nên `body…` vô hiệu); Việt hóa vùng thả bằng CSS thay vì gói i18n (Gradio không có `vi`); "Chạy lại" tạo công việc mới khi không còn gì để chạy tiếp.

**Cách kiểm chứng:** 77 test `unittest discover tests_gui` + `_test_translate_roundtrip.py` đạt. Chạy app thật (engine giả) và nhìn bằng Chrome: chạy 12 trang, tải lại giữa chừng, chip/preview/meta/sao chép/Chạy lại, trang Cài đặt, preset giữ công tắc và nhớ sau khi tải lại; mạng không còn yêu cầu nào ra `fonts.googleapis.com`/`fonts.gstatic.com` (13 woff2 nạp từ máy chủ); 375 px (iframe): nút dính đáy, thẻ chế độ thu gọn, tự cuộn tới kết quả, 0 vùng bấm < 40 px, không tràn ngang; theme tối ở 375/768 px.

**Chưa làm / chưa kiểm chứng:** thiết bị di động thật, Safari/Firefox, hộp thoại chọn tệp Windows (`pick_files.py`) và đường tệp chọn bằng hộp thoại trên giao diện mới; thử với AI thật; so sánh từng pixel với `MarkItDown.dc.html` (so bằng mắt: bố cục/màu/chip/thanh tiến độ khớp; icon và vài khoảng cách khác nhỏ); ảnh trang thu nhỏ (G3.2). Phát hiện thêm P8–P10 ở cuối kế hoạch.

## 5. Cách nối tiếp lịch sử này

Khi làm một thay đổi có ý nghĩa, thêm một mục vào mục 4 với: ngày, yêu cầu, những gì đã làm, quyết định + lý do,
việc dang dở. Nếu quyết định mới thay đổi một dòng ở mục 3, sửa dòng đó thay vì thêm bản trùng. Sự kiện
chỉ có ích cho phiên sau (ví dụ "đã thử X, không chạy") nên đưa vào [`../MEMORY.md`](../MEMORY.md).
