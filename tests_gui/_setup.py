"""Đặt biến môi trường cho test TRƯỚC khi import mã của ứng dụng (engine giả, không trễ)."""

import os
import tempfile

os.environ["MID_FAKE_ENGINE"] = "1"
os.environ["MID_FAKE_DELAY"] = "0"
# Dữ liệu công việc của test nằm trong thư mục tạm riêng (JobManager dùng chung đọc biến này ở lần gọi đầu).
os.environ.setdefault("MID_DATA_DIR", tempfile.mkdtemp(prefix="mid_test_data_"))
os.environ.pop("MID_FAKE_FAIL_PAGES", None)
os.environ.pop("MID_AUTH_USER", None)
os.environ.pop("MID_AUTH_PASS", None)
