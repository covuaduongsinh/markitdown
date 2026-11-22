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

Ngoài ra cần cài các gói của ứng dụng riêng bằng `pip install -r requirements-gui.txt` (đã ghim phiên bản: `gradio`,
`pypdfium2`, `pillow`, `numpy`, `chess`, `onnxruntime`, `opencv-python-headless`, `requests`). Thông điệp của
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
| Python | `pip install /app/packages/markitdown[all] /app/packages/markitdown-ocr -r /app/requirements-gui.txt` |
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

### Gắn volume dữ liệu công việc nền (G2.9 — **đã thực hiện trên production 2026-11-22**)

Mã G2 ghi dữ liệu vào `MID_DATA_DIR` (Dockerfile đặt `/data`, `VOLUME /data`). Để lịch sử/điểm lưu sống qua redeploy, gắn volume bền. Các bước (làm **sau khi chủ dự án duyệt nhánh và cho phép lên production**):

1. Trên VPS: `mkdir -p /root/markitdown-data` và ghi lại dung lượng trống bằng `df -h /root`.
2. Dokploy → ứng dụng markitdown → Mounts: thêm `bind` `/root/markitdown-data` → `/data` (cùng cách đã làm với `/root/.gemini`, xem `docs/plans/2026-11-21-cap-nhat-model-antigravity-va-mount-volume-vps.md`); Environment: `MID_DATA_DIR=/data`, `MID_KEEP_DAYS=60`.
3. Deploy (thủ công — auto deploy đang tắt); xác minh `docker inspect` thấy mount `/data`.
4. Tạo một công việc (PDF thật 2–3 trang khi được phép), deploy lần nữa, mở lại: công việc **vẫn còn** ở tab Lịch sử.
5. Ước lượng dung lượng bằng một cuốn mẫu (ảnh trang chưa lưu ở G2; chỉ văn bản + bản sao nguồn) rồi ghi con số vào đây. Nếu gần đầy đĩa: giảm `MID_KEEP_DAYS` trước.

**Kết quả thực tế (2026-11-22):** `/root/markitdown-data` trên host (đĩa `/` 193 GB, trống 41 GB trước khi gắn, dùng 79%); mount thêm bằng bản ghi `markitdown_data_mount` trong bảng `mount` của Postgres Dokploy + cột `env` của `application` (giống cách `gemini_oauth_mount_217`). Deploy bằng webhook: vì `autoDeploy=false` nên webhook trả 400 — đã bật `autoDeploy` **một lần**, gọi webhook, rồi tắt lại ngay (`false`). Build thật trên Dokploy mất ~35 phút do VPS tải cao (load average ~60 từ các ứng dụng khác); bước cài gói bằng `requirements-gui.txt` thành công. Kiểm chứng: `docker service inspect` thấy mount `/data` và env; trong container `gradio 6.32.0`, `agy`, `claude` đủ; tạo một công việc thử bằng **engine giả** (không gọi AI) → thư mục host có dữ liệu → `docker service update --force` (container đổi) → công việc **vẫn còn** → đã xóa công việc thử. Dung lượng: 3 trang giả = 76 KB; với sách thật dung lượng chủ yếu là **bản sao PDF nguồn** (có thể hàng chục MB mỗi cuốn) — theo dõi tab Lịch sử (hiện tổng dung lượng) và giảm `MID_KEEP_DAYS` trước khi đĩa gần đầy.

Bài học: lần deploy đầu thất bại vì Dockerfile chứa hai ký tự `\` và `n` thật (lỗi heredoc khi sửa tệp) thay cho xuống dòng — Docker báo `can't find = in "\\n"` và dịch vụ cũ vẫn chạy bình thường (rolling update chỉ thay khi build thành công).

Lưu ý: không có volume thì dữ liệu nằm trong một volume ẩn danh do `VOLUME /data` tạo và **mất khi container bị thay** (như trước).

Đối chiếu kế hoạch với repo: tệp của Dokploy (compose, biến môi trường, volume) **không có trong repo** — cấu
hình sống trên Dokploy. Khi nhân bản phải ghi lại: tên miền, biến môi trường đặt trên Dokploy, volume nếu có.

## 4. Biến môi trường

Bảng đầy đủ và nơi đọc: [`../../TECH.md`](../../TECH.md) mục "Biến môi trường".

### Đăng nhập web (G0.4, 2026-11-21)

Đặt **cả hai** biến `MID_AUTH_USER` và `MID_AUTH_PASS` trong cấu hình Dokploy rồi redeploy: Gradio hiện trang đăng nhập
(`launch(auth=(user, pass))`), mọi đường `/config`, `/gradio_api/...` đều trả 401 khi chưa đăng nhập. Không đặt biến nào = như cũ (không khóa).
Chỉ đặt một trong hai: ứng dụng **từ chối khởi động** (`❌ Chỉ đặt một trong hai biến…`) thay vì chạy không khóa.
Đã kiểm trên Gradio 6.32.0 (cục bộ, engine giả): chưa đăng nhập `/config` → 401; sai mật khẩu → 400; đúng → 200. **Chưa kiểm chứng** sau reverse proxy Traefik của Dokploy (cookie phiên qua HTTPS).
Đây là một tài khoản dùng chung, không tách phiên AI giữa người dùng (S2 vẫn mở).

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
- Gói `dropbox` đã bỏ khỏi Dockerfile (không được import, [07](07-dong-bo-dropbox.md)); gói `markitdown-ocr` cài nhưng
  không được bật ([09](09-plugin-ocr-mcp-mau.md)).
- Phiên bản gói GUI được **ghim** ở `requirements-gui.txt` (G0.1, 2026-11-21): `gradio==6.32.0` (bản production),
  `onnxruntime 1.20.1`, `chess 1.11.2`, `opencv-python-headless 4.13.0.92`…; dev và Docker cài cùng tệp. Gói
  `markitdown[all]`, `markitdown-ocr` và `claude-code` (npm) vẫn không ghim.
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
