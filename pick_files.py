# -*- coding: utf-8 -*-
"""Mở hộp thoại chọn tệp gốc của Windows, in mỗi đường dẫn một dòng (UTF-8).

Chạy như tiến trình con (từ markitdown_gui.py) để tránh xung đột tkinter với
luồng nền mà Gradio dùng chạy event handler, và để khởi động nhanh (chỉ import
tkinter, không kéo theo gradio/markitdown).
"""
import sys
import tkinter as tk
from tkinter import filedialog


def main():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    paths = filedialog.askopenfilenames(title="Chọn tệp để chuyển đổi")
    root.destroy()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write("\n".join(paths))


if __name__ == "__main__":
    main()
