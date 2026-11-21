# Tính năng 10 — Triển khai: Windows cục bộ, Docker và VPS (Dokploy)

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Tệp: `run_gui.bat` (45 dòng), `Dockerfile` (51 dòng), `.dockerignore`, `.github/workflows/`.
> Kế hoạch triển khai: `docs/plans/2026-09-27-dropbox-sync-integration.md` (hạng mục 6).

---

# Phần A — Chức năng

Phần mềm chạy được ở **hai nơi** với cùng một mã nguồn:

| Nơi chạy | Ai dùng | Cách chạy | Đặc điểm |
|---|---|---|---|
| **Máy Windows cá nhân** | Người biên tập tại chỗ | nhấp đúp `run_gui.bat` | CLI `agy`/`claude` đã đăng nhập sẵn; có hộp thoại chọn tệp; trình duyệt tự mở |
| **Web trên VPS** | Cả đội, từ xa | Docker qua Dokploy tại `https://markitdown.dsc.edu.vn` | CLI cài trong container; người dùng dán token thuê bao trên giao diện; không có hộp thoại hệ thống |

Nhánh code tự nhận biết môi trường bằng biến `DOCKER` (Dockerfile đặt `DOCKER=1`) và `sys.platform`.

---

# Phần B — Kỹ thuật

## 1. Windows: `run_gui.bat`

```
chcp 65001                                   # console UTF-8
cd /d "%~dp0"                                # về thư mục repo
nếu thiếu .venv\Scripts\python.exe           → hướng dẫn tạo venv, thoát 1
dò agy:    where agy  |  %LOCALAPPDATA%\agy\bin\agy.EXE
dò claude: where claude  |  %USERPROFILE%\.local\bin\claude.exe
nếu thiếu cả hai                             → cảnh báo "vẫn chạy được, chỉ mất OCR/dịch"
chạy .venv\Scripts\python.exe markitdown_gui.py   → http://127.0.0.1:7860
```

Tạo môi trường mới (từ thông điệp lỗi của chính script):

```bat
python -m venv .venv
.venv\Scripts\pip.exe install -e "packages/markitdown[all]"
```

Ngoài ra cần cài các gói của ứng dụng riêng (xem danh sách trong Dockerfile bên dưới): `gradio`, `pypdfium2`,
`pillow`, `numpy`, `chess`, `onnxruntime`, `opencv-python-headless`, `dropbox`, `requests`. Thông điệp của
`run_gui.bat` **không** nhắc tới chúng — người mới dễ thiếu.

## 2. Docker: `Dockerfile`

| Lớp | Nội dung |
|---|---|
| Nền | `python:3.12-slim` |
| `ENV` | `DEBIAN_FRONTEND=noninteractive`, `PYTHONUNBUFFERED=1`, `EXIFTOOL_PATH=/usr/bin/exiftool`, `FFMPEG_PATH=/usr/bin/ffmpeg`, `ORT_DISABLE_TELEMETRY=1`, `GRADIO_SERVER_NAME=0.0.0.0`, `GRADIO_SERVER_PORT=7860`, `PATH=/root/.local/bin:$PATH`, `DOCKER=1` |
| Gói hệ thống | `ffmpeg`, `libimage-exiftool-perl`, `poppler-utils`, `git`, `curl`, `ca-certificates`, `gnupg` |
| Node.js 20 | qua `deb.nodesource.com/setup_20.x`, rồi `npm install -g @anthropic-ai/claude-code` |
| Antigravity | `curl -fsSL https://antigravity.google/cli/install.sh \| bash \|\| true` rồi `ln -sf /root/.local/bin/agy /usr/local/bin/agy \|\| true` |
| Mã | `WORKDIR /app`, `COPY . /app` |
| Python | `pip install /app/packages/markitdown[all] /app/packages/markitdown-ocr gradio pypdfium2 pillow numpy chess onnxruntime opencv-python-headless dropbox requests` |
| Chạy | `EXPOSE 7860`; `CMD ["python", "markitdown_gui.py"]` |

`.dockerignore` loại `.git`, `.venv`, `.omc`, `__pycache__`, cache kiểm thử, `dist`, `build`, `*.egg-info`, tệp hệ điều hành.

**Điểm khác nhau giữa Docker và Windows** (do biến `DOCKER` và nền tảng):

| Việc | Windows | Docker |
|---|---|---|
| `server_name` mặc định | `127.0.0.1` | `0.0.0.0` |
| Tự mở trình duyệt | có | không |
| Nút chọn tệp từ máy | dùng được | vô hiệu, trả hướng dẫn |
| `claude.ready` trong bảng trạng thái | chỉ cần có CLI | cần cả token |
| Nhãn môi trường trong bảng trạng thái | `Desktop / Native (win32)` | `Docker Container (Linux VPS)` |

## 3. Triển khai VPS (từ kế hoạch 2026-09-27)

1. Commit và `git push origin main` lên `github.com/covuaduongsinh/markitdown` (remote `origin`).
2. **Dokploy** tự build và cập nhật dịch vụ Docker Swarm (tên dịch vụ và địa chỉ VPS ghi trong kế hoạch).
3. Kiểm tra `https://markitdown.dsc.edu.vn`.

Repo có hai remote: `origin` (fork của Cờ vua Dương Sinh) và `upstream` (`microsoft/markitdown`). Fork đã merge từ
upstream hai lần (`46d5350`, `ba0a8ad`).

Đối chiếu kế hoạch với repo: tệp của Dokploy (compose, biến môi trường, volume) **không có trong repo** — cấu
hình sống trên Dokploy. Khi nhân bản phải ghi lại: tên miền, biến môi trường đặt trên Dokploy, volume nếu có.

## 4. Biến môi trường

Bảng đầy đủ và nơi đọc: [`../../TECH.md`](../../TECH.md) mục "Biến môi trường".

## 5. CI

`.github/workflows/tests.yml` (chạy khi `pull_request`) chạy ba job kiểm thử của **các gói upstream**
(`packages/markitdown`, `markitdown-ocr`, `markitdown-mcp`) — **không** có job nào cho mã riêng ở thư mục gốc
(`markitdown_gui.py`…). `.github/workflows/pre-commit.yml` + `.pre-commit-config.yaml` chạy **black 23.7.0**.
`.github/dependabot.yml`, `.github/constraints.txt` (ghim phiên bản cho CI).

## 6. Điểm cần lưu ý và hạn chế

**Thiết kế**
- **Mô hình ONNX không vào image.** `COPY . /app` không mang theo thư mục mô hình (nó nằm ngoài repo, xem
  [03](03-nhan-dien-ban-co-fen.md)), và Dockerfile không đặt `OCRCHESS_MODELS_DIR`. Trong container,
  `chessboard_fen.available()` trả `False` → OCR lùi về để AI tự đoán bàn cờ. Nếu muốn có FEN cục bộ trên VPS phải mount
  hoặc COPY mô hình và đặt biến này.
- Gói `dropbox` cài nhưng không được import ([07](07-dong-bo-dropbox.md)); gói `markitdown-ocr` cài nhưng
  không được bật ([09](09-plugin-ocr-mcp-mau.md)).
- Phiên bản gói Python trong Dockerfile **không ghim** (`gradio`, `onnxruntime`…): mỗi lần build có thể ra
  bản khác. venv cục bộ hiện dùng `gradio 6.17.3`, `onnxruntime 1.20.1`, `chess 1.11.2`,
  `opencv-python-headless 4.13.0.92`, `gradio_client 2.5.0` — nên ghim khớp.
- Không có `HEALTHCHECK`, không có người dùng không phải root: container chạy bằng **root** (đường dẫn
  `/root/.local/bin`, `~/.gemini`, `~/.claude.json` đều trong `/root`).

**Vận hành**
- **Đăng nhập thuê bao không bền qua lần deploy.** `~/.gemini/antigravity-cli/` và `~/.claude.json` nằm trong
  hệ thống tệp của container, không có volume trong repo → mỗi lần Dokploy dựng lại container thì mất, người dùng
  phải dán token lại (trừ khi cấu hình volume trên Dokploy — không thấy trong repo).
- Cài `agy` bằng `curl | bash` với `|| true`: nếu URL cài đặt đổi hoặc lỗi thì **build vẫn thành công nhưng
  không có `agy`**; lỗi chỉ lộ khi chạy. Tương tự `ln -sf … || true`.
- Node.js cài từ `deb.nodesource.com`, `claude-code` cài không ghim phiên bản.
- Ảnh `python:3.12-slim` nhưng các gói con hỗ trợ 3.10–3.13; `markitdown-mcp/Dockerfile` dùng `python:3.13-slim-trixie` — hai image dùng Python khác nhau.
- `run_gui.bat` giả định `.venv` cạnh tệp; `.venv` không nằm trong git.

**Điều đáng ngờ**
- `COPY . /app` sao chép cả `markitdown giao diện.zip` (63.023 byte) và `design_handoff_markitdown_gui/` vào image — vô ích ở production; `.dockerignore` chưa loại chúng.
- Các tệp thử nghiệm `_test_*.py` cũng vào image.

## 7. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Khởi động Windows | **`run_gui.bat`** |
| Đóng gói web | **`Dockerfile`** |
| Chọn bind/cổng/tự mở | `markitdown_gui.py` dòng 1971–1983 |
| Nhận biết Docker | `infrastructure.py` `get_infrastructure_status` (`is_docker`), `markitdown_gui.py` `on_pick_files` (1084) |
| Kế hoạch deploy | `docs/plans/2026-09-27-dropbox-sync-integration.md` |
| CI | `.github/workflows/tests.yml`, `pre-commit.yml` |
