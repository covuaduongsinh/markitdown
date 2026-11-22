# Sổ rà soát: rủi ro, điều đáng ngờ và nợ kỹ thuật

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Tổng hợp từ mục "Điểm cần lưu ý và hạn chế" của từng tài liệu trong `docs/tinh-nang/`, gom lại một chỗ để rà soát.
> **S10 đã được sửa (2026-10-13)** — xem ghi chú tại dòng mục đó. Các mục còn lại chưa sửa.

## Cách đọc

| Cột | Nghĩa |
|---|---|
| **Mức** | 🔴 cao (mất dữ liệu/lộ bí mật/hỏng chức năng chính) · 🟠 vừa · 🟡 thấp (khó đọc, lệch tài liệu) |
| **Độ chắc** | ✅ *Xác nhận từ mã*: đọc thẳng được từ mã hoặc `grep` · ❓ *Suy ra*: hợp lý từ mã nhưng **chưa chạy thử** — nêu ra để người đọc tự xác minh |
| **Chi tiết** | tài liệu tính năng có phân tích đầy đủ |

---

## 1. Bảo mật

| ID | Mức | Độ chắc | Vấn đề | Nơi | Chi tiết |
|---|:-:|:-:|---|---|---|
| S1 | 🔴 | ✅ | **Web không có xác thực** (`launch()` không truyền `auth`). Ai vào được URL đều dùng được phiên AI thuê bao đã cấu hình — **mã đã sẵn sàng (G0.4)**: đặt `MID_AUTH_USER` + `MID_AUTH_PASS` để bật; mặc định vẫn tắt nên rủi ro còn cho tới khi chủ dự án đặt biến trên Dokploy | `markitdown_gui.py:1975` | [06](tinh-nang/06-giao-dien-gradio.md) |
| S2 | 🔴 | ✅ | **Token người dùng dán được ghi ra đĩa máy chủ và dùng chung**: `~/.gemini/antigravity-cli/antigravity-oauth-token` thuộc người dùng hệ điều hành, không thuộc người dùng web; người sau ghi đè người trước | `infrastructure.py:142` | [05](tinh-nang/05-ha-tang-va-ket-noi.md) |
| S3 | 🟠 | ✅ | **Khóa/token lưu thô trong `localStorage`** (Gemini key, token Claude/Antigravity, Dropbox token, App Secret) và đi qua websocket của Gradio — **đã xử lý (G4.2: máy chủ ưu tiên biến môi trường; công tắc "Nhớ khóa trên trình duyệt này" (tắt = lưu rỗng); hiện "Đã cấu hình trên máy chủ". Khóa đã lưu từ trước vẫn nằm trong trình duyệt tới khi người dùng tắt công tắc/xóa; `e2025fb`)** | `markitdown_gui.py:1812` | [06](tinh-nang/06-giao-dien-gradio.md), [07](tinh-nang/07-dong-bo-dropbox.md) |
| S4 | 🟠 | ❓ | **Prompt injection**: bước dịch (`_call_agy`) đưa nội dung tài liệu vào prompt của `agy` chạy với `--dangerously-skip-permissions` (agent không hỏi quyền khi dùng công cụ). Tài liệu do người lạ tải lên có thể chứa chỉ dẫn độc hại | `claude_translate.py:313`, `ai_engine.py:317` | [04](tinh-nang/04-ai-engine.md) |
| S5 | 🟠 | ❓ | **SSRF**: nhập URL nội bộ ở thẻ "Từ URL" khiến **máy chủ** truy cập địa chỉ đó (`MarkItDown.convert(url)`) | `markitdown_gui.py:469` | [08](tinh-nang/08-loi-markitdown.md) |
| S6 | 🟠 | ✅ | **`_autosave` ghi `.md` vào thư mục bất kỳ** do người dùng gõ ở ô "Thư mục tùy chọn trên VPS", không giới hạn — **đã xử lý (G4.1: `MID_SAVE_ROOT` (Docker mặc định `<data>/saved`), chặn `..`, so realpath; `e2025fb`)** | `markitdown_gui.py:182` | [06](tinh-nang/06-giao-dien-gradio.md) |
| S7 | 🟠 | ✅ | ~~**Thư mục kết quả dùng chung** mọi người dùng: `markitdown_ketqua.zip` là một tên cố định; tệp phục vụ qua `/gradio_api/file=<đường dẫn>` với `allowed_paths=[_OUTPUT_DIR, …]`~~ — **đã xử lý một phần (G2.7)**: công việc nền mỗi việc một thư mục `jobs/<id>/` (id ngẫu nhiên) và zip riêng, nên hết đè nhau; nhưng `allowed_paths` gồm cả `MID_DATA_DIR` nên ai đoán được id vẫn tải được (id 12 ký tự ngẫu nhiên) và chưa tách theo người dùng (S2) | `markitdown_gui.py:46, 123, 1982` | [06](tinh-nang/06-giao-dien-gradio.md) |
| S8 | 🟡 | ✅ | Container chạy bằng **root**; không có `USER` trong Dockerfile | `Dockerfile` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| S9 | 🟡 | ✅ | Kế hoạch trong `docs/plans/` ghi **địa chỉ IP VPS** và tên dịch vụ Swarm. Nếu repo công khai thì lộ thông tin hạ tầng | `docs/plans/2026-09-27-dropbox-sync-integration.md:79` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| S10 | 🟡 | ✅ | ~~`test_claude_cli_connection` đặt token phiên vào `ANTHROPIC_API_KEY`~~ — đã xác nhận qua tài liệu CLI chính thức và sửa: chỉ set `CLAUDE_CODE_OAUTH_TOKEN`, dùng token từ `claude setup-token` thay cookie `sessionKey` | `infrastructure.py`, `claude_ocr.py:_claude_env` | [05](tinh-nang/05-ha-tang-va-ket-noi.md), [12](tinh-nang/12-dang-nhap-claude-code.md) |

## 2. Lỗi có khả năng xảy ra và điều đáng ngờ

| ID | Mức | Độ chắc | Vấn đề | Nơi | Chi tiết |
|---|:-:|:-:|---|---|---|
| B1 | 🟠 | ❓ | **Gemini REST đính mọi ảnh trong `img_dir`** vào mỗi lần gọi; với `ocr_pdf` đó là thư mục tạm chứa PNG các trang đã vẽ → gửi thừa, có thể ra nội dung sai trang | `ai_engine.py:220–238` | [04](tinh-nang/04-ai-engine.md) |
| B2 | 🟠 | ✅ | **Ánh xạ model REST sai**: `gemini-3.1-pro` → `gemini-1.5-pro`; `gemini-3.x-flash` → `gemini-2.5-flash` (không chạy đúng model đã chọn) | `ai_engine.py:183–200` | [04](tinh-nang/04-ai-engine.md) |
| B3 | 🟡 | ✅ | `maxOutputTokens: 8192` ở đường REST có thể cắt cụt trang dày chữ hoặc nhóm 2–3 trang | `ai_engine.py:244` | [04](tinh-nang/04-ai-engine.md) |
| B4 | 🟠 | ❓ | **Hai hàm `find_claude`** khác nhau: `claude_ocr` chỉ `shutil.which`; `ai_engine` dò thêm `~/.local/bin/claude.exe`. Máy chỉ có `claude` ở đó: kiểm tra kết nối báo có, OCR/dịch báo không tìm thấy — **đã xử lý (G4.3: `claude_ocr.find_claude` ủy quyền cho `ai_engine.find_claude`; `e2025fb`)** | `claude_ocr.py:393`, `ai_engine.py:102` | [01](tinh-nang/01-ocr-pdf-anh.md) |
| B5 | 🟠 | ✅ | `is_engine_available` trả `True` chỉ vì tồn tại `~/.claude.json` / tệp token Antigravity dù **không có CLI** → giao diện tưởng sẵn sàng, lỗi lúc chạy — **đã xử lý (G4.3: `is_engine_available` chỉ true khi có CLI (Antigravity: hoặc có Gemini API Key); `e2025fb`)** | `ai_engine.py:139–152` | [04](tinh-nang/04-ai-engine.md) |
| B6 | 🟠 | ❓ | **Bảng trạng thái báo ONNX "Sẵn sàng" chỉ vì `import chessboard_fen` thành công**, không gọi `available()` → có thể sai khi thiếu mô hình — **đã xử lý (G4.3: trạng thái ONNX gọi `chessboard_fen.available()`; `e2025fb`)** | `infrastructure.py:278–286` | [05](tinh-nang/05-ha-tang-va-ket-noi.md) |
| B7 | 🟠 | ✅ | ~~**Nút Dừng không dừng thật**: chỉ hủy sự kiện Gradio; thread nền và tiến trình `agy`/`claude` con vẫn chạy~~ — **đã xử lý (G2.3)**: `proc_control.run_cli` đăng ký tiến trình, Dừng diệt cả cây tiến trình, ≤3 s (kiểm bằng engine giả và tiến trình thật); đường Gemini REST (`urllib`) không ngắt được giữa lượt gọi | `markitdown_gui.py:1026, 1962` | [06](tinh-nang/06-giao-dien-gradio.md) |
| B8 | 🟡 | ❓ | `claude_ocr.py:600` có điều kiện `'seg' in dir()` vô nghĩa (luôn rơi vào `else`); trông như mảnh vá sót lại | `claude_ocr.py:600` | [01](tinh-nang/01-ocr-pdf-anh.md) |
| B9 | 🟡 | ✅ | ~~**Nhận biết "đã gộp OCR+dịch" bằng chuỗi `"gộp 1 bước"`** trong dòng trạng thái: sửa nhãn ở `_ocr_to_outputs` sẽ khiến dịch chạy lần thứ hai âm thầm~~ — **đã xử lý (G0.3)**: cờ `ConvertResult.translated` | `markitdown_gui.py:359, 1219` | [02](tinh-nang/02-dich-tieng-viet.md) |
| B10 | 🟡 | ✅ | ~~`_apply_preset` **đặt lại** `translate_vn`, `autosave_on`, `auto_download_on`, `dropbox_sync_on` = `True` mỗi khi đổi preset/chế độ/engine → ghi đè lựa chọn tay~~ — **đã xử lý (G1.8)**: preset chỉ đặt model/effort/DPI/trang/gộp; các công tắc được lưu vào trình duyệt | `markitdown_gui.py:1379–1393` | [06](tinh-nang/06-giao-dien-gradio.md) |
| B11 | 🟡 | ✅ | ~~`_PRESET_HINTS` còn nội dung thời chỉ có Claude; preset Cân bằng ghi "dịch riêng" nhưng thực tế `merge=True`~~ — **đã xử lý (G1.8)**: gợi ý sinh từ bảng preset (`preset_hint_text`) | `markitdown_gui.py:977–981` | [06](tinh-nang/06-giao-dien-gradio.md) |
| B12 | 🟡 | ✅ | **`DROPBOX_TARGET_FOLDER` chỉ có trong tài liệu**, không có trong mã | `docs/DROPBOX_GUIDE.md:81` | [07](tinh-nang/07-dong-bo-dropbox.md) |
| B13 | 🟡 | ✅ | Token Antigravity được **ghi lại ra đĩa** mỗi lần render bảng trạng thái/gọi AI (khi `agy_token` không rỗng); `expiry` là giá trị bịa `2030-01-01` khi chỉ dán access token | `infrastructure.py:142–186` | [05](tinh-nang/05-ha-tang-va-ket-noi.md) |
| B14 | 🟡 | ❓ | `test_antigravity_cli_connection` coi mọi exit 0 là thành công, không kiểm nội dung phản hồi | `infrastructure.py:235` | [05](tinh-nang/05-ha-tang-va-ket-noi.md) |
| B15 | 🟡 | ❓ | README của plugin OCR ghi `--llm-client/--llm-model` nhưng `__main__.py` của lõi không khai báo hai cờ này (chỉ có `--use-plugins`) | `packages/markitdown-ocr/README.md` | [09](tinh-nang/09-plugin-ocr-mcp-mau.md) |
| B16 | 🟡 | ❓ | Chunk dịch dài hơn 6000 ký tự (một đoạn không cắt được) đưa thẳng vào dòng lệnh `agy` → có thể chạm giới hạn độ dài dòng lệnh Windows | `claude_translate.py:313, 225` | [02](tinh-nang/02-dich-tieng-viet.md) |

## 3. Vận hành và triển khai

| ID | Mức | Độ chắc | Vấn đề | Nơi | Chi tiết |
|---|:-:|:-:|---|---|---|
| O1 | 🔴 | ✅ | **Mô hình ONNX không có trong repo và không vào Docker image**; mặc định trỏ vào đường dẫn cá nhân → trên VPS mặc định tắt FEN cục bộ | `chessboard_fen.py:37`, `Dockerfile` | [03](tinh-nang/03-nhan-dien-ban-co-fen.md), [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O2 | 🟠 | ❓ | **Đăng nhập thuê bao mất mỗi lần deploy** vì `~/.gemini`, `~/.claude.json` nằm trong container, repo không có volume | `Dockerfile` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O3 | 🟠 | ✅ | `curl … \| bash \|\| true` và `ln -sf … \|\| true` che lỗi cài `agy` → build xanh nhưng thiếu CLI — **đã xử lý (G4.4: bỏ `|| true`, thêm `agy --version` (build thất bại nếu cài lỗi); `e2025fb`)** | `Dockerfile:25–26` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O4 | 🟠 | ✅ | ~~**Phụ thuộc không ghim** trong Dockerfile (`gradio`, `onnxruntime`, `chess`…) và `claude-code` cài không ghim~~ — đã ghim các gói GUI ở `requirements-gui.txt` (G0.1, kế hoạch 2026-11-21); `claude-code` (npm) vẫn không ghim | `Dockerfile`, `requirements-gui.txt` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O5 | 🟡 | ✅ | ~~`dropbox` được cài nhưng không import~~ (đã bỏ khỏi Dockerfile, G0.1); `markitdown-ocr` được cài nhưng `enable_plugins=False` | `Dockerfile`, `markitdown_gui.py:1791` | [07](tinh-nang/07-dong-bo-dropbox.md), [09](tinh-nang/09-plugin-ocr-mcp-mau.md) |
| O6 | 🟡 | ✅ | ~~Thư mục kết quả tạm không bao giờ được dọn;~~ **đã xử lý (G2.7)** cho công việc nền (dọn theo `MID_KEEP_DAYS`); còn lại: thư mục `mid_ocr_*` không dọn nếu tiến trình chết | `markitdown_gui.py:46` | [06](tinh-nang/06-giao-dien-gradio.md) |
| O7 | 🟡 | ✅ | `run_gui.bat` không nhắc cài `gradio`, `pypdfium2`, `onnxruntime`… (chỉ nhắc `markitdown[all]`) — **đã xử lý (G4.5: `run_gui.bat` nhắc cài từ `requirements-gui.txt`; `e2025fb`)** | `run_gui.bat:14–15` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O8 | 🟡 | ✅ | Image chứa cả `markitdown giao diện.zip`, `design_handoff_markitdown_gui/`, `_test_*.py`; `.dockerignore` chưa loại — **đã xử lý (G4.4: `.dockerignore` loại `*.zip`, `design_handoff_markitdown_gui/`, `_test_*.py`, `tests_gui/`, `docs/`; `e2025fb`)** | `.dockerignore` | [10](tinh-nang/10-trien-khai-docker-vps.md) |
| O9 | 🟡 | ✅ | Dropbox: mỗi upload đổi refresh token một lần; không thử lại; upload một phát đọc cả tệp vào RAM; ghi đè cùng tên | `infrastructure.py:363, 466` | [07](tinh-nang/07-dong-bo-dropbox.md) |
| O10 | 🟡 | ❓ | Mặc định Gradio cho mỗi sự kiện chạy một lượt một lúc; mã không đặt `concurrency_limit` → nhiều người phải xếp hàng (chưa xác minh trên 6.17.3) | `markitdown_gui.py` | [01](tinh-nang/01-ocr-pdf-anh.md) |

## 4. Nợ kỹ thuật (khó đọc / khó bảo trì)

| ID | Vấn đề | Gợi ý |
|---|---|---|
| T1 | `markitdown_gui.py` 1.985 dòng lẫn nghiệp vụ, CSS/JS trong chuỗi Python và bố cục | Tách `ui_theme.py` (CSS/JS/HTML), `pipeline.py` (`convert_file`, `on_convert_files`), `ui.py` (`build_ui`) |
| T2 | Khối "lưu VPS + Dropbox + tải về" lặp ba lần trong `on_convert_files` | Rút thành một hàm (xem [`NHAN-BAN-VA-MO-RONG.md`](NHAN-BAN-VA-MO-RONG.md) mục 3.3) |
| T3 | Tên `claude_ocr.py`, `claude_translate.py`, `ClaudeOCRError` sai nghĩa (phục vụ cả Antigravity) | Đổi thành `ocr_engine.py`, `translate.py`, `OCRError`, giữ bí danh tương thích |
| T4 | Đường gọi Claude Code nằm rải trong `claude_ocr`/`claude_translate`, không nằm trong `ai_engine.py` | Chuyển vào `ai_engine.run_claude_prompt` |
| T5 | Bốn nơi tính `engine_name` bằng `"Google Antigravity / Gemini" if … else "Claude Code"` | Một hàm/dict duy nhất | ← **đã xử lý (G4.3, `engine_display_name`)**
| T6 | Vòng phụ thuộc `claude_ocr ↔ claude_translate`, `ai_engine ↔ infrastructure` được cắt bằng import trễ | Tách phần dùng chung (`_CHESS_II_*`, `find_*`) ra module thứ ba |
| T7 | Tham số `engine, api_key, claude_token, agy_token` lan qua mọi hàm | Một đối tượng `EngineConfig` |
| T8 | Kiểm thử tự động gần như không phủ mã riêng; hai tệp `_test_*.py` không nằm trong CI và không được `pytest` phát hiện | Xem [11](tinh-nang/11-kiem-thu.md) mục 3 |
| T9 | Thông báo lỗi/hướng dẫn cứng đường dẫn `C:\Users\duongsinh\…` | Dùng `expanduser` | ← G4.5: rà lại, không còn đường dẫn cứng trong mã; chỉ còn chuỗi ví dụ trong tài liệu

## 5. Ưu tiên gợi ý khi bắt đầu sửa

1. **Trước khi mở web ra ngoài:** S1, S2, S3, S6, S7 (xác thực, tách phiên người dùng, thư mục tạm riêng từng phiên).
2. **Trước khi giao bản sao:** O1, O2, O3, O4 (mô hình ONNX vào image, volume đăng nhập, ghim phiên bản).
3. **Sửa nhanh, ít rủi ro:** B5, B6, B10, B11, B12, T9 và các dòng lệch tài liệu.
4. **Cần thử với dịch vụ thật trước khi kết luận:** mọi mục "❓ Suy ra" — đặc biệt B1, B4, S4, S10.
