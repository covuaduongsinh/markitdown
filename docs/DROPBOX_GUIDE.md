# Hướng dẫn Đồng bộ Tự động với Dropbox (Dropbox Sync Guide)

MarkItDown hỗ trợ tính năng **tự động đồng bộ các tệp tài liệu Markdown (`.md`), bản dịch tiếng Việt (`_vn.md`) và tệp thế cờ FEN (`_fen.txt`) lên tài khoản Dropbox** của bạn ngay khi chuyển đổi xong.

---

## 🎯 Mục đích & Lợi ích
1. **Liên kết Pipeline tự động**: Các phần mềm, bot AI hoặc hệ sinh thái xử lý tài liệu khác có thể tự động đọc và tiêu thụ các tệp Markdown ngay từ Dropbox theo thời gian thực.
2. **Lưu trữ đám mây an toàn & Đa thiết bị**: Truy cập tài liệu đã dịch và OCR ở bất kỳ đâu (Điện thoại, Máy tính bảng, Laptop).
3. **Song song 3 luồng dữ liệu độc lập**:
   - ⚡ **Tự động tải về máy tính cá nhân** qua trình duyệt web.
   - 💾 **Lưu bản sao trên máy chủ (VPS)**.
   - ☁️ **Đồng bộ tự động lên Dropbox**.

---

## 🚀 Hướng dẫn lấy Token Dropbox (Chỉ mất 1–2 phút)

Để ứng dụng có quyền tải file lên Dropbox của bạn, hãy làm theo các bước đơn giản sau:

### Bước 1: Tạo Dropbox App
1. Đăng nhập vào [Dropbox App Console](https://www.dropbox.com/developers/apps).
2. Bấm nút **Create App** (Tạo ứng dụng).
3. Chọn các tùy chọn:
   - **1. Choose an API**: Chọn `Scoped access`.
   - **2. Choose the type of access**:
     - Chọn `Full Dropbox` (để lưu vào thư mục bất kỳ như `/MarkItDown`), hoặc:
     - Chọn `App folder` (chỉ lưu trong thư mục riêng của app: `Apps/<TênApp>`).
   - **3. Name your app**: Đặt tên ứng dụng (ví dụ: `MarkItDown-Sync-CuaBan`).
4. Bấm **Create app**.

### Bước 2: Cấp quyền (Permissions) cho App
1. Chuyển sang tab **Permissions** trong trang quản lý App vừa tạo.
2. Tick chọn các quyền sau:
   - ✅ `files.content.write` *(Quyền ghi/tải file lên)*
   - ✅ `files.content.read` *(Quyền đọc file)*
   - ✅ `account_info.read` *(Quyền kiểm tra thông tin tài khoản & dung lượng)*
3. Kéo xuống dưới cùng và bấm nút **Submit** để lưu quyền.

### Bước 3: Lấy Token hoặc App Key / Secret

#### 👉 Cách 1: Lấy Access Token trực tiếp (Dễ nhất - Dùng thử nhanh)
1. Chuyển sang tab **Settings**.
2. Tìm mục **OAuth 2** -> bấm nút **Generate** tại phần **Generated access token**.
3. Copy chuỗi Token (bắt đầu bằng `sl.u...`) và dán vào ô **Dropbox Access Token** trên MarkItDown Web.

#### 👉 Cách 2: Dùng Refresh Token + App Key + App Secret (Khuyên dùng - Vĩnh viễn không hết hạn)
1. Tại tab **Settings**, copy 2 thông tin:
   - **App key**
   - **App secret** (bấm *Show*)
2. Dán **App Key** và **App Secret** vào ô tương ứng trên MarkItDown Web.
3. Dán Refresh Token hoặc Access Token vào ô Token. Hệ thống sẽ tự động làm mới token vĩnh viễn mỗi khi chạy.

---

## ⚙️ Cách sử dụng trên Giao diện Web MarkItDown

1. Truy cập Web MarkItDown: `https://markitdown.dsc.edu.vn` (hoặc `http://localhost:7860`).
2. Vào tab **⚙️ Cài đặt Hạ tầng & API** -> mục **☁️ 4. Cấu hình Đồng bộ Đám mây Dropbox**.
3. Dán Token / App Key / App Secret vào các ô tương ứng.
4. Nhập thư mục lưu trữ mong muốn (mặc định: `/MarkItDown`).
5. Bấm **🔍 Kiểm tra kết nối Dropbox**:
   - Nếu thành công, hệ thống sẽ báo: `✅ Kết nối thành công tới Dropbox: Tên bạn (email) · Dung lượng: X GB / Y GB · Sẵn sàng đồng bộ.`
6. Khi chuyển đổi tài liệu tại tab **Từ tệp** hoặc **Từ URL**, đảm bảo tùy chọn **"Tự động đồng bộ lên Dropbox"** trong mục *Tùy chọn nâng cao* đang được bật.
7. Sau khi chuyển đổi từng tệp, bạn sẽ thấy thông báo trạng thái:
   ```text
   ☁️ [Dropbox] đã lưu: /MarkItDown/Sach_Co_Vua.md
   ☁️ [Dropbox] đã lưu: /MarkItDown/Sach_Co_Vua_vn.md
   ☁️ [Dropbox] đã lưu: /MarkItDown/Sach_Co_Vua_fen.txt
   ```

---

## 🔒 Bảo mật & Lưu trữ Cấu hình
- **Ghi nhớ tự động**: Toàn bộ cấu hình Dropbox được lưu an toàn trực tiếp trên trình duyệt cá nhân của bạn (`localStorage`) thông qua `BrowserState`, bạn không cần nhập lại khi tải lại trang.
- **Biến môi trường trên Server / Docker**: Bạn cũng có thể thiết lập sẵn qua biến môi trường:
  - `DROPBOX_ACCESS_TOKEN`
  - `DROPBOX_REFRESH_TOKEN`
  - `DROPBOX_APP_KEY`
  - `DROPBOX_APP_SECRET`
  - `DROPBOX_TARGET_FOLDER` (mặc định: `/MarkItDown`)
