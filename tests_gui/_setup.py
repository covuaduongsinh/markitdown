"""Đặt biến môi trường cho test TRƯỚC khi import mã của ứng dụng (engine giả, không trễ)."""

import os

os.environ["MID_FAKE_ENGINE"] = "1"
os.environ["MID_FAKE_DELAY"] = "0"
os.environ.pop("MID_FAKE_FAIL_PAGES", None)
os.environ.pop("MID_AUTH_USER", None)
os.environ.pop("MID_AUTH_PASS", None)
