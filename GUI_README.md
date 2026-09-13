# MarkItDown GUI — Cờ vua Dương Sinh

App Gradio riêng của repo này (`markitdown_gui.py`), build trên nền thư viện
`markitdown` gốc, chuyên biệt cho việc chuyển sách/tài liệu (đặc biệt sách cờ
vua scan) sang Markdown, có OCR + dịch tiếng Việt qua AI Engine.

## Chạy app

```bat
.venv\Scripts\python.exe markitdown_gui.py
```

hoặc nhấp đúp `run_gui.bat`. Sau đó mở trình duyệt tại `http://127.0.0.1:7860`.

## Yêu cầu: 1 trong 2 AI Engine

Tính năng OCR/dịch cần **ít nhất một** CLI sau đã cài và **đăng nhập sẵn**
(không cần API key — dùng phiên đăng nhập subscription của CLI):

| Engine | CLI cần có trong PATH | Vai trò |
| --- | --- | --- |
| **Google Antigravity** (mặc định) | `agy` | Phương án 1 — khuyên dùng, rẻ hơn (Gemini Flash) |
| **Claude Code** | `claude` | Phương án 2 — dự phòng khi không có `agy` |

App tự dò CLI qua `ai_engine.find_agy()` / `find_claude()` (PATH, rồi
`%LOCALAPPDATA%\agy\bin\`, `~\.local\bin\`). Không có CLI nào cả thì app vẫn
chạy convert bình thường (dùng converter gốc của `markitdown`), chỉ mất tính
năng OCR AI.

Đổi engine ở radio **"Công cụ AI (Engine)"** trên giao diện — đổi xong toàn bộ
model/preset bên dưới tự tính lại theo engine mới.

## Model theo từng Engine

**Google Antigravity** (`ANTIGRAVITY_OCR_MODELS`/`ANTIGRAVITY_TRANSLATE_MODELS`
trong `ai_engine.py`, đã đối chiếu với `agy models` thực tế):

| Model | Dùng cho |
| --- | --- |
| `gemini-3.6-flash` | Siêu tiết kiệm token |
| `gemini-3.7-flash` | Cân bằng & nhanh (mặc định) |
| `gemini-3.8-flash` | Tốc độ cao |
| `gemini-3.1-pro` | Chính xác cao / văn phong cao cấp |
| `claude-sonnet-4-6` | Thinking, chỉ cho OCR/dịch chất lượng cao |
| `claude-opus-4-6-thinking` | Thinking, chỉ cho OCR |

> Lưu ý: `gemini-3.1-pro` trên `agy` chỉ có 2 mức effort thật là **high** và
> **low** (không có **medium**). Preset "Chính xác" hiện gán `tr_effort=medium`
> cho model này khi dịch — nếu thấy dịch không đúng effort mong muốn, thử đổi
> tay effort dịch sang "Cao" và báo lại để điều chỉnh preset.

**Claude Code**: `haiku` (tiết kiệm), `sonnet` (cân bằng, mặc định OCR),
`opus` (chính xác).

## Preset Tiết kiệm / Cân bằng / Chính xác

Giá trị thật lấy từ `_PRESET_OPTS_AGY` / `_PRESET_OPTS_CLAUDE`
(`markitdown_gui.py`):

| Preset | Antigravity: model OCR / dịch, effort, DPI, gộp trang | Claude Code: model OCR / dịch, effort, DPI, gộp trang |
| --- | --- | --- |
| **Tiết kiệm** | gemini-3.6-flash / gemini-3.6-flash, low, DPI 250, 2 trang/lần, gộp OCR+dịch | haiku / haiku, low, DPI 250, 2 trang/lần, gộp OCR+dịch |
| **Cân bằng** (mặc định) | gemini-3.7-flash / gemini-3.7-flash, auto, DPI 250, 1 trang/lần, gộp OCR+dịch | sonnet / haiku, auto, DPI 250, 1 trang/lần, gộp OCR+dịch |
| **Chính xác** | gemini-3.1-pro / gemini-3.1-pro, high/medium, DPI 400, 1 trang/lần, dịch riêng | opus / sonnet, high/medium, DPI 400, 1 trang/lần, dịch riêng |

"Gộp OCR+dịch" (`merge`) = OCR và dịch tiếng Việt trong cùng 1 lượt gọi AI,
tiết kiệm thêm ~30–40% lượt gọi so với dịch riêng một pass.

## 3 chế độ sách cờ vua

Chọn ở panel "CHẾ ĐỘ XỬ LÝ":

1. **Sách cờ vua — ký hiệu Anh**: figurine/K,Q,R,B,N → Vua/Hậu/Xe/Tượng/Mã (V/H/X/T/M).
2. **Sách cờ vua — ký hiệu Nga**: Кр/Ф/Л/С/К → V/H/X/T/M.
3. **Sách cờ vua — ký hiệu Tây Ban Nha**: R(Rey)/D(Dama)/T(Torre)/A(Alfil)/C(Caballo) → V/H/X/T/M.
   Lưu ý: nguồn `T` (Torre = Xe) → `X`, nguồn `A` (Alfil = Tượng) → `T` — **không**
   giữ nguyên chữ cái vì trùng với bảng ký hiệu tiếng Việt.
4. **Tài liệu thường**: convert gốc của `markitdown`, không có phần nhận diện
   bàn cờ / dịch theo quy tắc cờ vua.

Mỗi trang PDF được nhận diện bàn cờ → FEN cục bộ bằng model ONNX
(`chessboard_fen.py`, không tốn quota AI) trước khi gửi cho AI Engine OCR văn
bản xung quanh.
