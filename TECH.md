# TECH — Ngăn xếp công nghệ, phiên bản, cấu hình

> Mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27). Phiên bản lấy từ `.venv` (`*.dist-info`), `pyproject.toml`
> và `__about__.py`; phần nào là "không ghim" nghĩa là repo không quy định phiên bản.

## 1. Ngôn ngữ và môi trường chạy

| Mục | Giá trị | Nguồn |
|---|---|---|
| Python (dev, venv) | 3.12 (`cpython-3.12-windows-x86_64`) | `.venv/pyvenv.cfg` |
| Python (Docker) | 3.12 (`python:3.12-slim`) | `Dockerfile` |
| Python (thư viện upstream hỗ trợ) | 3.10 – 3.14 | `packages/markitdown/pyproject.toml` |
| Hệ điều hành dev | Windows 10; production Linux (Docker) | |
| Lưu ý | `python` trên PATH của máy dev có thể là 3.8 — **luôn dùng `.venv\Scripts\python.exe`** | |

## 2. Thư viện của ứng dụng riêng (thư mục gốc)

| Thư viện | Phiên bản đã cài trong `.venv` | Dùng ở | Ghi chú |
|---|---|---|---|
| `gradio` | 6.17.3 (`gradio_client` 2.5.0) | `markitdown_gui.py` | Không ghim ở Dockerfile |
| `onnxruntime` | 1.20.1 | `chessboard_fen.py` | Chỉ `CPUExecutionProvider` |
| `opencv-python-headless` | 4.13.0.92 | `chessboard_fen.py` | |
| `chess` (python-chess) | 1.11.2 | `chessboard_fen.py` | Chỉ để `refine_fen` |
| `pypdfium2` | (đã cài, không ghim) | `claude_ocr.py` | Vẽ trang PDF |
| `Pillow`, `numpy` | (không ghim) | `chessboard_fen.py`, `claude_ocr.py` | |
| `dropbox` | (cài trong Dockerfile) | **không dùng** | Mã dùng `urllib` thuần |
| `requests` | (lõi cũng phụ thuộc) | — | |
| `tkinter` | thư viện chuẩn | `pick_files.py` | Chỉ Windows |

## 3. Gói upstream (thư mục `packages/`)

| Gói | Phiên bản | Ghi chú |
|---|---|---|
| `markitdown` | 0.1.9 | lõi; extras `[all]`, `[pdf]`, `[docx]`, `[pptx]`, `[xlsx]`, `[xls]`, `[outlook]`, `[audio-transcription]`, `[youtube-transcription]`, `[az-doc-intel]`, `[az-content-understanding]` |
| `markitdown-ocr` | 0.1.2 | phụ thuộc `markitdown>=0.1.9`, `PyMuPDF>=1.24.0`… |
| `markitdown-mcp` | 0.0.1a8 | MCP SDK 2.x |
| `markitdown-sample-plugin` | 0.1.0a1 | `striprtf` |

Build: `hatchling`; kiểm thử: `hatch test`, `pytest`; định dạng: `black 23.7.0` (pre-commit).

## 4. Công cụ ngoài (không phải gói Python)

| Công cụ | Vai trò | Cách có mặt |
|---|---|---|
| `agy` (Google Antigravity CLI) | Động cơ AI mặc định | Cài tay (Windows) / `curl … install.sh` trong Docker |
| `claude` (Claude Code CLI) | Động cơ AI phương án 2 | `npm install -g @anthropic-ai/claude-code` |
| `ffmpeg`, `exiftool`, `poppler-utils` | Âm thanh, metadata ảnh, PDF | `apt-get` trong Docker |
| Node.js 20 | Chạy `claude` | NodeSource, trong Docker |
| Mô hình ONNX (5 tệp: `existence`, `bbox`, `rotation`, `fen`, `orientation`) | Nhận diện bàn cờ | **Ngoài repo**: dự án `ocrchessboard` |

## 5. Dịch vụ bên ngoài mà mã gọi

| Dịch vụ | URL (từ mã) | Nơi gọi |
|---|---|---|
| Gemini REST | `https://generativelanguage.googleapis.com/v1beta/models…` | `ai_engine.py`, `infrastructure.py` |
| Dropbox OAuth | `https://api.dropboxapi.com/oauth2/token` | `infrastructure.py` |
| Dropbox API | `https://api.dropboxapi.com/2/users/get_current_account`, `…/get_space_usage` | `infrastructure.py` |
| Dropbox upload | `https://content.dropboxapi.com/2/files/upload` | `infrastructure.py` |
| Google Fonts | `fonts.googleapis.com`, `fonts.gstatic.com` | giao diện (trình duyệt) |
| Cài Antigravity | `https://antigravity.google/cli/install.sh` | `Dockerfile` |
| Web production | `https://markitdown.dsc.edu.vn` | tài liệu `docs/` |

## 6. Biến môi trường

Quét bằng script trên các tệp chạy thật; cột "Đọc ở" là `tệp:dòng` đầu tiên.

| Biến | Tác dụng | Đọc ở |
|---|---|---|
| `GRADIO_SERVER_NAME` | địa chỉ bind (mặc định `127.0.0.1` Windows, `0.0.0.0` Docker) | `markitdown_gui.py:1972` |
| `PORT` / `GRADIO_SERVER_PORT` | cổng (mặc định `7860`); `PORT` ưu tiên | `markitdown_gui.py:1973` |
| `GRADIO_INBROWSER` | tự mở trình duyệt | `markitdown_gui.py:1974` |
| `DOCKER` | nhận biết container (Dockerfile đặt `1`) | `markitdown_gui.py:1084`, `infrastructure.py:289` |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | khoá Gemini REST | `ai_engine.py:123`, `infrastructure.py:28` |
| `CLAUDE_CODE_SESSION_ACCESS_TOKEN`, `ANTHROPIC_SESSION_KEY` | token phiên Claude | `claude_ocr.py:419`, `infrastructure.py:267` |
| `DROPBOX_ACCESS_TOKEN`, `DROPBOX_REFRESH_TOKEN`, `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` | xác thực Dropbox | `infrastructure.py:368–371` |
| `OCRCHESS_MODELS_DIR` | thư mục mô hình ONNX | `chessboard_fen.py:38` |
| `LOCALAPPDATA` | tìm `agy.exe` | `ai_engine.py:85` |
| `MARKITDOWN_ENABLE_PLUGINS` | bật plugin trong MCP | `markitdown_mcp/__main__.py:51` |
| `EXIFTOOL_PATH` | đường dẫn exiftool (lõi) | `_markitdown.py:203` |
| `FFMPEG_PATH`, `ORT_DISABLE_TELEMETRY`, `PYTHONUNBUFFERED`, `DEBIAN_FRONTEND` | đặt trong `Dockerfile`; **mã Python của repo không đọc trực tiếp `FFMPEG_PATH` và `ORT_DISABLE_TELEMETRY`** (thư viện bên thứ ba có thể đọc) | `Dockerfile` |

Biến được **đặt cho tiến trình con** `claude`: `DISABLE_AUTOUPDATER=1`,
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, và khi có token: `CLAUDE_CODE_SESSION_ACCESS_TOKEN`,
`ANTHROPIC_SESSION_KEY`, `ANTHROPIC_API_KEY` (`claude_ocr.py:414`).

> **Không tồn tại trong mã:** `DROPBOX_TARGET_FOLDER` (được nhắc trong `docs/DROPBOX_GUIDE.md` nhưng chưa cài đặt).

## 7. Tệp và thư mục mà ứng dụng tạo ra lúc chạy

| Đường dẫn | Nội dung | Dọn? |
|---|---|---|
| `<tmp>/markitdown_gui_output/*.md, *_fen.txt, markitdown_ketqua.zip` | kết quả chuyển đổi | không |
| `<tmp>/mid_ocr_*/page_NNN.png` | ảnh trang PDF khi OCR | có (`finally`) |
| Thư mục tùy chọn hoặc cạnh tệp gốc | bản sao `.md` (luồng "Lưu bản sao trên máy chủ") | không |
| `~/.gemini/antigravity-cli/antigravity-oauth-token`, `settings.json` | token Antigravity người dùng dán | không |
| `.omc/` | trạng thái công cụ OMC của Claude Code | đã trong `.gitignore` |

## 8. Cổng và lệnh thường dùng

```bat
:: Chạy ứng dụng web (Windows) — http://127.0.0.1:7860
.venv\Scripts\python.exe markitdown_gui.py
run_gui.bat

:: Chuyển tệp bằng CLI thư viện
.venv\Scripts\python.exe -m markitdown tệp.pdf -o tệp.md

:: Kiểm thử của fork (chạy từ thư mục gốc repo)
.venv\Scripts\python.exe _test_translate_roundtrip.py
.venv\Scripts\python.exe -m unittest _test_dropbox_sync -v

:: Kiểm thử upstream
cd packages\markitdown && hatch test
```

```bash
# Docker
docker build -t markitdown-gui .
docker run -p 7860:7860 markitdown-gui
```

## 9. Nhánh Git

`main` (một nhánh). Remote: `origin` = `github.com/covuaduongsinh/markitdown`, `upstream` = `microsoft/markitdown`.
Cập nhật từ upstream bằng `git merge upstream/main` (đã làm ở `46d5350`, `ba0a8ad`). Xem
[`docs/LICH-SU-PHAT-TRIEN.md`](docs/LICH-SU-PHAT-TRIEN.md).
