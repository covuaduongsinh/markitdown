# -*- coding: utf-8 -*-
"""
Cầu nối đăng nhập Claude Code CLI ngay trên giao diện web (không cần SSH).

Dùng `claude setup-token`: lệnh chính thức sinh OAuth token sống ~1 năm cho gói thuê bao
Claude Pro/Max, thiết kế riêng cho server/CI không có trình duyệt — khi trình duyệt không
reach được localhost callback (đúng tình huống container VPS), CLI tự chuyển sang hiện một
mã để dán ngược lại terminal, rồi in token ra thẳng stdout (không tự lưu file, không cần
Docker volume).

KHÁC VỚI `infrastructure.py`: các hàm `test_*_connection` ở đó chạy-xong-là-xong (một
`subprocess.run` chặn). Module này giữ một tiến trình `claude setup-token` SỐNG xuyên nhiều
request HTTP (Gradio chạy callback trong cùng một tiến trình Python, nhiều thread) — nên cần
một singleton cấp module bảo vệ bằng lock, không thể gói gọn trong một hàm chạy-xong-là-xong.

QUAN TRỌNG — đã kiểm chứng thật trên VPS (2026-10-13): CLI Node.js của `claude` dùng block
buffering cho stdout khi nó KHÔNG phải TTY (pipe thường) — khi gọi qua `subprocess.PIPE`,
tiến trình chạy nhưng không in ra byte nào, treo vô thời hạn cho tới khi tự thoát. Vì vậy
module này BẮT BUỘC cấp một pseudo-terminal thật (`pty.openpty`) cho stdin/stdout/stderr của
tiến trình con trên POSIX; `subprocess.PIPE` chỉ còn lại làm fallback để đọc code trên Windows
(không hoạt động đúng ở đó, chỉ POSIX/Linux production mới chạy đúng).

CHƯA KIỂM CHỨNG — cần thử thêm, đừng tin các giả định dưới đây tới khi đã quan sát hành vi thật:
  - Tiền tố thật của token sinh ra (để sau này siết `_BARE_TOKEN_RE` bằng tiền tố thật).
  - `claude setup-token` có ghi `~/.claude/.credentials.json` như side-effect không.
  - CLI có tự thoát (exit 0) ngay sau khi in token, hay treo chờ thêm (ảnh hưởng tới
    _SUCCESS_LINGER_S bên dưới).
"""

import os
import re
import signal
import subprocess
import threading
import time
import uuid

try:
    import pty
    import fcntl
    import termios
    import struct

    _HAS_PTY = True
except ImportError:  # Windows — không có module pty/fcntl/termios
    _HAS_PTY = False

_PTY_COLS = 500  # rộng bất thường để URL đăng nhập dài không bị terminal tự ngắt dòng giữa chừng
_PTY_ROWS = 50

_LOCK = threading.Lock()

_STATE = {
    "proc": None,  # Popen đang chạy, hoặc None
    "master_fd": None,  # fd đầu "cha" của pty (None nếu dùng fallback PIPE trên Windows)
    "session_id": None,  # uuid hex — phân biệt lần login hiện tại với lần cũ đã bị dọn
    "status": "idle",  # idle | starting | waiting_code | working | success | error | unknown
    "url": None,
    "token": None,
    "error": None,
    "lines": [],  # tối đa 200 dòng log gần nhất, để debug + đường thoát cho người dùng tự đọc
    "last_activity": None,
    "watchdog": None,  # threading.Timer đang chờ dọn do nhàn rỗi
}

IDLE_TIMEOUT_S = 300  # 5 phút không ai tương tác -> dọn tiến trình bỏ dở
URL_WAIT_TIMEOUT_S = 45  # ước lượng thời gian hợp lý để CLI in URL
CODE_RESULT_TIMEOUT_S = 60  # ước lượng thời gian từ lúc dán mã tới khi có token
_SUCCESS_LINGER_S = 3.0  # chờ thêm sau khi bắt được token trước khi tự kill (phòng CLI treo)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b.")
_URL_RE = re.compile(r"https?://\S+")
_ERROR_RE = re.compile(r"(error|failed|invalid|expired|denied)", re.I)
_SUCCESS_RE = re.compile(r"(success|logged in|authentication successful)", re.I)
_BARE_TOKEN_RE = re.compile(r"^\S{20,}$")  # dòng không khoảng trắng, dài — ứng viên token


def _snapshot_locked():
    return {
        "status": _STATE["status"],
        "url": _STATE["url"],
        "token": _STATE["token"],
        "error": _STATE["error"],
        "session_id": _STATE["session_id"],
        "tail": list(_STATE["lines"][-15:]),
    }


def _kill_tree(proc, grace_s=2.0):
    """Giết tiến trình `claude setup-token` và mọi tiến trình con (node...). TERM trước, KILL sau."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    pid = proc.pid
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        if os.name == "nt":
            # Windows: chỉ dùng để đọc code khi dev — chưa chạy thật được ở đây.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                creationflags=flags,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            deadline = time.time() + grace_s
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.1)
            if proc.poll() is None:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _close_fd_quiet(fd):
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _write_stdin_safe(proc, master_fd, text, chunk_size=4096):
    """Ghi mã xác nhận vào pty (hoặc stdin PIPE fallback), dạng byte, không cắt giữa ký tự UTF-8."""
    data = text.encode("utf-8", errors="replace")
    try:
        if master_fd is not None:
            i = 0
            while i < len(data):
                n = os.write(master_fd, data[i:])
                if n <= 0:
                    return False
                i += n
            return True
        if proc.stdin is None:
            return False
        if proc.poll() is not None:
            return False
        i = 0
        while i < len(data):
            j = min(i + chunk_size, len(data))
            while j > i and (data[j - 1] & 0xC0) == 0xC0:
                j -= 1  # byte mở đầu ký tự nhiều byte đứng cuối mẩu -> lùi lại, không cắt đôi
            if j <= i:
                j = min(i + chunk_size, len(data))
            proc.stdin.write(data[i:j])
            proc.stdin.flush()
            i = j
        return True
    except OSError:
        return False
    except Exception:
        return False


def _arm_watchdog_locked(session_id):
    old = _STATE.get("watchdog")
    if old:
        old.cancel()
    t = threading.Timer(IDLE_TIMEOUT_S, _on_idle_timeout, args=(session_id,))
    t.daemon = True
    t.start()
    _STATE["watchdog"] = t


def _on_idle_timeout(session_id):
    with _LOCK:
        if _STATE["session_id"] != session_id:
            return
        proc = _STATE["proc"]
        if proc is None or _STATE["status"] in ("success", "error"):
            return
        _STATE["status"] = "unknown"
        _STATE["error"] = "Quá 5 phút không có tương tác — phiên đăng nhập bị hủy."
        _STATE["proc"] = None
        master_fd = _STATE["master_fd"]
        _STATE["master_fd"] = None
    _kill_tree(proc)
    _close_fd_quiet(master_fd)


def _finalize_locked(rc, candidate_token, saw_success_marker):
    """Tiến trình thoát mã 0 -> LUÔN coi là thành công dù heuristic không khớp chuỗi nào.
    Không bao giờ khẳng định thất bại chỉ vì không match heuristic (timeout != đăng xuất)."""
    if rc == 0:
        _STATE["status"] = "success"
        _STATE["token"] = candidate_token  # có thể None — UI phải xử lý: hiện log để tự copy tay
        _STATE["error"] = None
    elif saw_success_marker and not _STATE.get("error"):
        _STATE["status"] = "unknown"
    else:
        _STATE["status"] = "error"
        _STATE["error"] = _STATE.get("error") or f"Tiến trình `claude setup-token` thoát mã {rc}."


def _scan_buffer_locked(clean_text, candidate_token, saw_success_marker):
    """Quét TOÀN BỘ văn bản đã làm sạch ANSI (không chỉ dòng mới nhất) để tìm URL/token —
    cần thiết vì output qua pty có animation/cursor-control, ranh giới dòng không đáng tin."""
    if _STATE["url"] is None:
        m = _URL_RE.search(clean_text)
        if m:
            _STATE["url"] = m.group(0)
            if _STATE["status"] == "starting":
                _STATE["status"] = "waiting_code"

    if _SUCCESS_RE.search(clean_text):
        saw_success_marker = True

    for line in reversed(clean_text.splitlines()):
        s = line.strip()
        if s and _BARE_TOKEN_RE.match(s) and not _URL_RE.search(s):
            candidate_token = s
            break

    if _ERROR_RE.search(clean_text) and not saw_success_marker:
        _STATE["error"] = clean_text.strip()[-300:]

    return candidate_token, saw_success_marker


def _reader_loop(session_id, proc, master_fd):
    """Đọc output non-blocking. Nếu có `master_fd` (pty POSIX), đọc bằng os.read theo chunk
    và quét lại toàn bộ buffer tích lũy mỗi lần (tránh vỡ dòng do animation/cursor-control của
    CLI). Nếu không (fallback PIPE trên Windows), đọc theo dòng như một pipe thường."""
    candidate_token = None
    saw_success_marker = False
    linger_timer = None
    raw_buf = b""
    try:
        while True:
            try:
                if master_fd is not None:
                    chunk = os.read(master_fd, 4096)
                else:
                    chunk = proc.stdout.readline()
                    if not chunk:
                        break
            except OSError:
                break  # slave đóng (CLI thoát) -> master đọc báo lỗi, coi như EOF
            if not chunk:
                break
            raw_buf += chunk
            if len(raw_buf) > 65536:
                raw_buf = raw_buf[-65536:]  # chặn phình vô hạn nếu CLI in rất nhiều
            clean_text = _ANSI_RE.sub("", raw_buf.decode("utf-8", errors="replace"))

            with _LOCK:
                if _STATE["session_id"] != session_id:
                    return  # phiên này đã bị dọn/thay thế -> tự rút lui
                _STATE["lines"] = clean_text.splitlines()[-200:]
                _STATE["last_activity"] = time.time()
                candidate_token, saw_success_marker = _scan_buffer_locked(
                    clean_text, candidate_token, saw_success_marker
                )
                got_token_now = candidate_token is not None and saw_success_marker

            if got_token_now and linger_timer is None:
                # Phòng trường hợp CLI treo sau khi in token thay vì tự thoát — chờ thêm một
                # chút rồi tự kill để không treo người dùng vô thời hạn.
                linger_timer = threading.Timer(_SUCCESS_LINGER_S, _kill_tree, args=(proc,))
                linger_timer.daemon = True
                linger_timer.start()
    except Exception as exc:
        with _LOCK:
            if _STATE["session_id"] == session_id:
                _STATE["lines"].append(f"[reader lỗi: {exc}]")
    finally:
        if linger_timer is not None:
            linger_timer.cancel()
        try:
            proc.wait(timeout=5)
            rc = proc.returncode
        except Exception:
            rc = None
        with _LOCK:
            if _STATE["session_id"] != session_id:
                return
            _finalize_locked(rc, candidate_token, saw_success_marker)
            _STATE["proc"] = None
            fd_to_close = _STATE["master_fd"]
            _STATE["master_fd"] = None
            if _STATE["watchdog"]:
                _STATE["watchdog"].cancel()
        _close_fd_quiet(fd_to_close)


def _login_env():
    """Env sạch cho riêng tiến trình `claude setup-token`: bỏ các biến credential cũ để không
    làm nhiễu luồng đăng nhập mới đang tạo ra token mới."""
    env = os.environ.copy()
    for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(k, None)
    env["DISABLE_AUTOUPDATER"] = "1"
    env["TERM"] = env.get("TERM") or "xterm"
    return env


def _spawn_claude_setup_token(bin_path, env):
    """Spawn `claude setup-token` cấp pty thật trên POSIX (bắt buộc — CLI block-buffer stdout
    khi không phải TTY, đã xác nhận thật trên VPS). Trả về (proc, master_fd); master_fd là
    None khi dùng fallback PIPE (chỉ Windows, không chạy đúng ở đó)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if _HAS_PTY and os.name != "nt":
        master_fd, slave_fd = pty.openpty()
        try:
            # URL đăng nhập rất dài (>200 ký tự); pty mặc định 80 cột sẽ khiến terminal tự
            # ngắt dòng giữa URL, làm regex chỉ bắt được đoạn đầu. Đặt cửa sổ rộng bất
            # thường để tránh ngắt dòng (đã xác nhận cần thiết qua thử nghiệm thật trên VPS).
            fcntl.ioctl(
                slave_fd, termios.TIOCSWINSZ,
                struct.pack("HHHH", _PTY_ROWS, _PTY_COLS, 0, 0),
            )
        except Exception:
            pass
        try:
            proc = subprocess.Popen(
                [bin_path, "setup-token"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                close_fds=True,
                start_new_session=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)  # cha chỉ giữ master; slave đã được con kế thừa
        return proc, master_fd

    proc = subprocess.Popen(
        [bin_path, "setup-token"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        env=env,
        creationflags=flags,
        start_new_session=(os.name != "nt"),
    )
    return proc, None


def start_claude_login(claude_bin=None):
    """Spawn `claude setup-token`, chờ có giới hạn thời gian để lấy URL đăng nhập.

    Trả về dict (xem `_snapshot_locked`): status một trong
    idle|starting|waiting_code|working|success|error|unknown.
    """
    from ai_engine import find_claude  # import trong hàm, tránh vòng phụ thuộc (quy ước dự án)

    with _LOCK:
        if _STATE["status"] in ("starting", "waiting_code", "working"):
            return _snapshot_locked()  # đang có phiên chạy -> trả lại, không spawn chồng
        old_proc = _STATE["proc"]
        old_fd = _STATE["master_fd"]
        session_id = uuid.uuid4().hex
        bin_path = claude_bin or find_claude()
        if not bin_path:
            _STATE.update(
                status="error",
                error=(
                    "Không tìm thấy lệnh 'claude' CLI trên server. Hãy đảm bảo Claude Code "
                    "đã được cài trong container (xem Dockerfile)."
                ),
                proc=None,
                master_fd=None,
                session_id=session_id,
            )
            return _snapshot_locked()

        env = _login_env()
        try:
            proc, master_fd = _spawn_claude_setup_token(bin_path, env)
        except Exception as exc:
            _STATE.update(
                status="error",
                error=f"Không chạy được 'claude setup-token': {exc}",
                proc=None,
                master_fd=None,
                session_id=session_id,
            )
            return _snapshot_locked()

        _STATE.update(
            proc=proc,
            master_fd=master_fd,
            session_id=session_id,
            status="starting",
            url=None,
            token=None,
            error=None,
            lines=[],
            last_activity=time.time(),
        )
        _arm_watchdog_locked(session_id)
        t = threading.Thread(target=_reader_loop, args=(session_id, proc, master_fd), daemon=True)
        t.start()

    if old_proc is not None:
        _kill_tree(old_proc)  # dọn phiên cũ (idle/success/error) ngoài lock
        _close_fd_quiet(old_fd)

    deadline = time.time() + URL_WAIT_TIMEOUT_S
    while time.time() < deadline:
        with _LOCK:
            if _STATE["session_id"] != session_id:
                return _snapshot_locked()
            if _STATE["url"] or _STATE["status"] in ("success", "error"):
                return _snapshot_locked()
        time.sleep(0.2)
    with _LOCK:
        if _STATE["session_id"] == session_id and _STATE["status"] == "starting":
            _STATE["status"] = "unknown"
            _STATE["error"] = (
                f"Chưa thấy link đăng nhập sau {URL_WAIT_TIMEOUT_S}s — CLI có thể vẫn đang chạy, "
                "thử chờ thêm hoặc bấm lại."
            )
        return _snapshot_locked()


def submit_claude_login_code(code, session_id=None):
    """Ghi mã xác nhận vào pty/stdin tiến trình đang chờ, chờ kết quả (token hoặc lỗi)."""
    with _LOCK:
        if _STATE["status"] == "success":
            return _snapshot_locked()  # đã có kết quả từ trước
        if _STATE["proc"] is None or _STATE["status"] not in ("waiting_code", "starting"):
            return {
                "status": "error",
                "error": "Không có phiên đăng nhập đang chờ mã. Hãy bấm 'Đăng nhập Claude Code' lại.",
            }
        if session_id and session_id != _STATE["session_id"]:
            return {
                "status": "error",
                "error": "Phiên đăng nhập đã thay đổi hoặc hết hạn. Hãy bấm 'Đăng nhập Claude Code' lại.",
            }
        proc = _STATE["proc"]
        master_fd = _STATE["master_fd"]
        sid = _STATE["session_id"]
        _STATE["status"] = "working"
        _STATE["last_activity"] = time.time()
        _arm_watchdog_locked(sid)

    if not _write_stdin_safe(proc, master_fd, (code or "").strip() + "\n"):
        with _LOCK:
            if _STATE["session_id"] == sid:
                _STATE["status"] = "error"
                _STATE["error"] = "Không ghi được mã vào tiến trình 'claude' (có thể đã tự thoát)."
            return _snapshot_locked()

    deadline = time.time() + CODE_RESULT_TIMEOUT_S
    while time.time() < deadline:
        with _LOCK:
            if _STATE["session_id"] != sid or _STATE["status"] in ("success", "error"):
                return _snapshot_locked()
        time.sleep(0.3)
    with _LOCK:
        if _STATE["session_id"] == sid and _STATE["status"] == "working":
            _STATE["status"] = "unknown"  # timeout != thất bại
            _STATE["error"] = (
                "Quá thời gian chờ kết quả — có thể vẫn đang xử lý. Hãy thử 'Kiểm tra kết nối "
                "Claude Code CLI' ở trên, hoặc bấm 'Đăng nhập Claude Code' để thử lại."
            )
        return _snapshot_locked()


def cleanup_claude_login(force=False):
    """Dọn tiến trình bỏ dở. force=True: dọn bất kể trạng thái (dùng cho nút 'Hủy')."""
    with _LOCK:
        proc = _STATE["proc"]
        master_fd = _STATE["master_fd"]
        if proc is None and not force:
            return _snapshot_locked()
        if _STATE["watchdog"]:
            _STATE["watchdog"].cancel()
        _STATE["proc"] = None
        _STATE["master_fd"] = None
        if _STATE["status"] not in ("success", "error"):
            _STATE["status"] = "idle"
            _STATE["error"] = None
        snap = _snapshot_locked()
    _kill_tree(proc)
    _close_fd_quiet(master_fd)
    return snap


def get_claude_login_snapshot():
    """Đọc trạng thái hiện tại không làm thay đổi gì — dùng khi người dùng tải lại trang."""
    with _LOCK:
        return _snapshot_locked()
