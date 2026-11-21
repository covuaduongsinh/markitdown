# Mục lục tài liệu

> Mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27). Bộ tài liệu này được lập ngày 2026-09-30.
> Mọi tài liệu tính năng theo mẫu hai tầng: **Phần A — Chức năng** (cho mọi người) và **Phần B — Kỹ thuật** (cho người bảo trì),
> kết bằng "Điểm cần lưu ý và hạn chế" và "Đường dẫn tham chiếu nhanh".

## Đọc theo mục đích

| Bạn là… / muốn… | Đọc theo thứ tự |
|---|---|
| Người mới, muốn hiểu dự án | [`../README.md`](../README.md) (khối đầu) → [`TONG-QUAN-KIEN-TRUC.md`](TONG-QUAN-KIEN-TRUC.md) Phần A |
| Lập trình viên sắp sửa mã | [`../AGENTS.md`](../AGENTS.md) → [`TONG-QUAN-KIEN-TRUC.md`](TONG-QUAN-KIEN-TRUC.md) → tài liệu tính năng liên quan |
| Người rà soát chất lượng/bảo mật | [`RA-SOAT-RUI-RO.md`](RA-SOAT-RUI-RO.md) → tài liệu tính năng tương ứng |
| Người muốn **nhân bản** phần mềm | [`NHAN-BAN-VA-MO-RONG.md`](NHAN-BAN-VA-MO-RONG.md) → [`../TECH.md`](../TECH.md) |
| Người muốn **thêm module/tính năng** | [`../SKILLS.md`](../SKILLS.md) mục A (đã có gì, thiếu gì) → [`NHAN-BAN-VA-MO-RONG.md`](NHAN-BAN-VA-MO-RONG.md) mục 3 |
| Trợ lý AI mở phiên mới | [`../CLAUDE.md`](../CLAUDE.md)/[`../AGENTS.md`](../AGENTS.md) → [`../MEMORY.md`](../MEMORY.md) |

## Tệp ở thư mục gốc

| Tệp | Nội dung |
|---|---|
| [`../README.md`](../README.md) | README của upstream + khối giới thiệu bản fork ở đầu |
| [`../GUI_README.md`](../GUI_README.md) | Cách chạy ứng dụng, engine, model, preset, ba chế độ sách, Dropbox (có từ trước) |
| [`../AGENTS.md`](../AGENTS.md) | Quy ước, ranh giới, quy trình cho mọi trợ lý AI/lập trình viên |
| [`../CLAUDE.md`](../CLAUDE.md) | Nhập `AGENTS.md` + ghi chú riêng cho Claude Code |
| [`../TECH.md`](../TECH.md) | Ngăn xếp, phiên bản, biến môi trường, dịch vụ ngoài, lệnh |
| [`../SKILLS.md`](../SKILLS.md) | Danh mục năng lực (đã có/thiếu) và bài làm mẫu |
| [`../MEMORY.md`](../MEMORY.md) | Bộ nhớ dự án: bẫy đã gặp, quyết định, việc dang dở |

## Tài liệu trong `docs/`

| Tệp | Nội dung |
|---|---|
| [`TONG-QUAN-KIEN-TRUC.md`](TONG-QUAN-KIEN-TRUC.md) | Kiến trúc tầng, bản đồ module, sơ đồ, điểm vào, dữ liệu, quy ước mã |
| [`NHAN-BAN-VA-MO-RONG.md`](NHAN-BAN-VA-MO-RONG.md) | Danh sách việc khi nhân bản; bài mẫu thêm ngôn ngữ ký hiệu/engine/nơi đồng bộ |
| [`RA-SOAT-RUI-RO.md`](RA-SOAT-RUI-RO.md) | Sổ rủi ro (bảo mật, lỗi, vận hành, nợ kỹ thuật), có mức độ và độ chắc |
| [`LICH-SU-PHAT-TRIEN.md`](LICH-SU-PHAT-TRIEN.md) | Dòng thời gian commit, quyết định + lý do, nhật ký tương tác |
| [`DROPBOX_GUIDE.md`](DROPBOX_GUIDE.md) | Hướng dẫn người dùng tạo Dropbox App (có từ trước) |
| [`plans/`](plans/) | Hai kế hoạch triển khai (2026-09-17 hạ tầng; 2026-09-27 Dropbox) — có từ trước |

## Tài liệu tính năng (`tinh-nang/`)

| # | Tài liệu | Module chính | Dòng mã | Nội dung chính |
|---|---|---|---:|---|
| 01 | [OCR PDF và ảnh](tinh-nang/01-ocr-pdf-anh.md) | `claude_ocr.py` | 806 | Vòng OCR theo trang, ghép prompt, gộp trang, hậu kiểm khối bàn cờ |
| 02 | [Dịch tiếng Việt](tinh-nang/02-dich-tieng-viet.md) | `claude_translate.py` | 474 | Placeholder, chia đoạn, bảng ký hiệu Anh/Nga/Tây Ban Nha, phát hiện "chưa dịch" |
| 03 | [Nhận diện bàn cờ → FEN](tinh-nang/03-nhan-dien-ban-co-fen.md) | `chessboard_fen.py` | 511 | Pipeline 5 mô hình ONNX, ensemble, tìm bàn cờ trong trang |
| 04 | [Động cơ AI](tinh-nang/04-ai-engine.md) | `ai_engine.py` | 362 | Antigravity, Claude Code, Gemini REST; chọn engine; danh sách model |
| 05 | [Hạ tầng và kiểm tra kết nối](tinh-nang/05-ha-tang-va-ket-noi.md) | `infrastructure.py` (phần AI) | 576 (cả tệp) | Bảng trạng thái, token Antigravity, kiểm tra kết nối |
| 06 | [Giao diện Gradio](tinh-nang/06-giao-dien-gradio.md) | `markitdown_gui.py`, `pick_files.py` | 1.985 + 24 | Luồng bấm nút, `_stream_job`, preset, `BrowserState`, JavaScript |
| 07 | [Đồng bộ Dropbox](tinh-nang/07-dong-bo-dropbox.md) | `infrastructure.py` (phần Dropbox) | — | Xác thực, tải lên, ba luồng song song |
| 08 | [Lõi MarkItDown](tinh-nang/08-loi-markitdown.md) | `packages/markitdown` | 7.554 | Registry converter, ưu tiên, danh sách converter, CLI (upstream) |
| 09 | [Plugin OCR, MCP, plugin mẫu](tinh-nang/09-plugin-ocr-mcp-mau.md) | `packages/markitdown-ocr`, `-mcp`, `-sample-plugin` | 863 + 152 + 88 | Ba gói con upstream (không dùng trong app web) |
| 10 | [Triển khai](tinh-nang/10-trien-khai-docker-vps.md) | `run_gui.bat`, `Dockerfile` | 45 + 52 | Windows, Docker, VPS/Dokploy, CI |
| 11 | [Kiểm thử](tinh-nang/11-kiem-thu.md) | `_test_*.py`, `packages/*/tests` | 72 + 90 (+ upstream) | Kiểm thử của fork, upstream, khoảng trống |
| 12 | [Đăng nhập Claude Code](tinh-nang/12-dang-nhap-claude-code.md) | `claude_login_bridge.py` | 392 | OAuth token 1 năm qua `claude setup-token`, không cần SSH |

## Về độ tin cậy

- Số dòng: đếm bằng script (đếm ký tự `\n`), tổng đã cộng lại (4.738 dòng mã riêng của fork).
- **Chưa chạy** ứng dụng, chưa gọi `agy`/`claude`/Gemini/Dropbox thật. Mọi mục ❓ trong `RA-SOAT-RUI-RO.md` là suy ra từ mã.
- Dòng số trong bảng "Đường dẫn tham chiếu nhanh" đúng với commit ghim ở đầu mỗi tài liệu; sau khi sửa mã, tìm theo **tên hàm**.
- Đường dẫn trong tài liệu đều **tương đối** so với gốc repo.
