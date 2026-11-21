# -*- coding: utf-8 -*-
"""
Hủy được công việc đang chạy AI: đăng ký tiến trình con (`agy`, `claude`) để nút Dừng diệt thật.

Cách dùng:
- Người điều khiển công việc tạo một `CancelToken`, bọc việc chạy bằng `use_token(token)` và gọi `token.cancel()` khi cần dừng.
- Mọi chỗ gọi CLI dùng `run_cli(...)` thay cho `subprocess.run`: tiến trình được đăng ký vào token hiện hành, `cancel()`
  diệt cả cây tiến trình (Windows: `taskkill /T`; POSIX: `killpg`).
- Token đi qua `contextvars`, nên luồng trong `ThreadPoolExecutor` phải được nộp bằng `submit_in_context` để thừa hưởng nó.
- `OperationCancelled` kế thừa `BaseException` (như `KeyboardInterrupt`) để các khối `except Exception` sẵn có không nuốt mất nó.
"""

import contextlib
import contextvars
import os
import signal
import subprocess
import threading
import time

_subprocess_run = subprocess.run  # giữ bản gốc (test có thể thay subprocess.run bằng bản giả)


class OperationCancelled(BaseException):
    """Công việc bị người dùng dừng."""


class CancelToken:
    """Cờ hủy + danh sách tiến trình con đang chạy của một công việc."""

    def __init__(self):
        self._event = threading.Event()
        self._procs = set()
        self._lock = threading.Lock()

    def is_set(self):
        return self._event.is_set()

    def wait(self, seconds):
        """Ngủ tối đa `seconds`; trả True nếu bị hủy trong lúc đó."""
        return self._event.wait(seconds)

    def raise_if_cancelled(self):
        if self._event.is_set():
            raise OperationCancelled()

    def cancel(self):
        self._event.set()
        with self._lock:
            procs = list(self._procs)
        for proc in procs:
            kill_tree(proc)

    def _register(self, proc):
        with self._lock:
            self._procs.add(proc)
            already = self._event.is_set()
        if already:  # cancel() chạy đúng lúc tiến trình vừa được tạo
            kill_tree(proc)

    def _unregister(self, proc):
        with self._lock:
            self._procs.discard(proc)


_CURRENT = contextvars.ContextVar("mid_cancel_token", default=None)


def current_token():
    return _CURRENT.get()


def check_cancelled():
    """Ném OperationCancelled nếu công việc hiện hành đã bị hủy (không làm gì nếu không có token)."""
    token = _CURRENT.get()
    if token is not None:
        token.raise_if_cancelled()


def sleep(seconds):
    """Như time.sleep nhưng thức dậy và ném OperationCancelled ngay khi bị hủy."""
    token = _CURRENT.get()
    if token is None:
        time.sleep(seconds)
    elif token.wait(seconds):
        raise OperationCancelled()


@contextlib.contextmanager
def use_token(token):
    """Đặt token hiện hành cho khối lệnh (token=None -> không đổi gì)."""
    if token is None:
        yield
        return
    reset = _CURRENT.set(token)
    try:
        yield
    finally:
        _CURRENT.reset(reset)


def submit_in_context(pool, fn, *args, **kwargs):
    """pool.submit nhưng chạy trong bản sao ngữ cảnh hiện tại (để luồng con thấy token)."""
    ctx = contextvars.copy_context()
    return pool.submit(ctx.run, fn, *args, **kwargs)


def kill_tree(proc, grace_s=2.0):
    """Diệt tiến trình và mọi tiến trình con của nó. TERM trước, KILL sau (POSIX)."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    pid = proc.pid
    try:
        if os.name == "nt":
            _subprocess_run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            deadline = time.time() + grace_s
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.05)
            if proc.poll() is None:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.kill()
    except Exception:
        pass


def run_cli(cmd, *, input=None, timeout=None, cwd=None, env=None):
    """Thay `subprocess.run(..., capture_output=True, text=True, encoding='utf-8', errors='replace')`.

    Trả `subprocess.CompletedProcess`. Ném `subprocess.TimeoutExpired` khi quá giờ (đã diệt cây tiến trình)
    và `OperationCancelled` khi token hiện hành bị hủy. Không có `input` thì stdin = DEVNULL.
    """
    token = _CURRENT.get()
    if token is not None:
        token.raise_if_cancelled()
    popen_kw = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL if input is None else subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )
    if os.name == "nt":
        popen_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        popen_kw["start_new_session"] = True  # để killpg diệt cả nhóm
    proc = subprocess.Popen(cmd, **popen_kw)
    if token is not None:
        token._register(proc)
    try:
        try:
            out, err = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            proc.communicate()
            raise
    finally:
        if token is not None:
            token._unregister(proc)
    if token is not None and token.is_set():
        raise OperationCancelled()
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
