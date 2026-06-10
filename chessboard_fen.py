# -*- coding: utf-8 -*-
"""
Nhận diện hình bàn cờ vua trong ảnh -> FEN, chạy CỤC BỘ bằng các model ONNX
của dự án ocrchessboard (port từ src/lib/inference/pipeline.ts sang Python).

Pipeline 5 model: existence (có bàn cờ?) -> bbox (tách vùng) -> rotation
(góc xoay ảnh) -> fen (phân loại quân từng ô, ensemble) -> orientation
(bàn cờ bị lật 180°?). Độ chính xác ~94%, không tốn quota Claude.

Phụ thuộc: onnxruntime, opencv-python-headless, numpy, chess (python-chess),
Pillow. Thiếu thư viện/model -> available() trả False, caller tự fallback.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import chess
except ImportError:
    chess = None

# Model nằm trong dự án ocrchessboard; đổi qua biến môi trường nếu cần.
DEFAULT_MODELS_DIR = r"C:\Users\duongsinh\Documents\code\ocrchessboard\public\models"
MODELS_DIR = os.environ.get("OCRCHESS_MODELS_DIR", DEFAULT_MODELS_DIR)

BBOX_IMAGE_SIZE = 512
BOARD_PIXEL_WIDTH = 256
# Thứ tự lớp PHẢI khớp ocrchessboard/src/lib/chess-utils.ts PIECE_TYPES
PIECE_TYPES = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k", None]
ROTATIONS = [0, 90, 180, 270]
FEN_TAIL = "w - - 0 1"

_sessions = {}
_sessions_lock = threading.Lock()


def _get_session(name):
    """Lazy-load + cache InferenceSession cho 1 model; None nếu không có.

    Có lock vì fens_for_page chạy infer_fen song song nhiều thread.
    """
    if ort is None:
        return None
    if name in _sessions:
        return _sessions[name]
    with _sessions_lock:
        if name in _sessions:
            return _sessions[name]
        path = os.path.join(MODELS_DIR, f"{name}.onnx")
        sess = None
        if os.path.isfile(path):
            try:
                sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
            except Exception:
                sess = None
        _sessions[name] = sess
        return sess


def available():
    """True nếu đủ thư viện + model cốt lõi để nhận diện FEN cục bộ."""
    return (
        ort is not None
        and cv2 is not None
        and os.path.isfile(os.path.join(MODELS_DIR, "fen.onnx"))
        and os.path.isfile(os.path.join(MODELS_DIR, "bbox.onnx"))
    )


def _run(sess, arr):
    """Chạy session với input đầu tiên, trả output đầu tiên (np array)."""
    name = sess.get_inputs()[0].name
    return sess.run(None, {name: arr})[0]


# --- Tiền xử lý ảnh (port preprocessing.ts) ----------------------------------


def _auto_enhance(pil_img):
    """autoEnhanceLowContrast: ảnh tương phản thấp (std<50) -> autocontrast 1%."""
    img = pil_img.convert("RGB")
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    if gray.std() >= 50:
        return img
    return ImageOps.autocontrast(img, cutoff=1)


def _to_tensor(pil_img, size):
    """imageDataToTensorNchw: resize -> RGB/255 NCHW -> min-max toàn tensor -> trừ mean."""
    img = pil_img.convert("RGB").resize((size, size), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
    mn, mx = float(arr.min()), float(arr.max())
    if mn >= mx:
        return np.zeros((1, 3, size, size), dtype=np.float32)
    arr = (arr - mn) / (mx - mn)
    arr -= arr.mean()
    return arr.reshape(1, 3, size, size).astype(np.float32)


def _pad_white(pil_img, pad_x, pad_y):
    px, py = int(round(pad_x)), int(round(pad_y))
    out = Image.new("RGB", (pil_img.width + 2 * px, pil_img.height + 2 * py), "white")
    out.paste(pil_img.convert("RGB"), (px, py))
    return out


# --- Các stage model (port pipeline.ts) ---------------------------------------


def _check_existence(pil_img, threshold=0.5):
    sess = _get_session("existence")
    if sess is None:
        return True  # thiếu model existence thì không chặn
    score = float(_run(sess, _to_tensor(pil_img, BBOX_IMAGE_SIZE)).reshape(-1)[0])
    return score > threshold


def _mask_to_bbox(mask, img_w, img_h):
    """maskToBBox: ngưỡng 0.5, lấy thành phần liên thông lớn nhất (4-connectivity)."""
    size = BBOX_IMAGE_SIZE
    m = (np.asarray(mask).reshape(size, size) >= 0.5).astype(np.uint8)
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    if n <= 1:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    li = 1 + int(np.argmax(areas))
    x = stats[li, cv2.CC_STAT_LEFT]
    y = stats[li, cv2.CC_STAT_TOP]
    w = stats[li, cv2.CC_STAT_WIDTH]
    h = stats[li, cv2.CC_STAT_HEIGHT]
    xf, yf = img_w / size, img_h / size
    x1 = max(0, min(img_w - 1, int(np.floor(x * xf))))
    y1 = max(0, min(img_h - 1, int(np.floor(y * yf))))
    x2 = max(0, min(img_w, int(np.ceil((x + w) * xf))))
    y2 = max(0, min(img_h, int(np.ceil((y + h) * yf))))
    return (x1, y1, x2, y2)


def _crop_to_chessboard(pil_img, max_tries=10, work_max_side=1024):
    """cropToChessboard: pad 5% trắng, lặp bbox đến khi phủ >70% mỗi chiều.

    Vòng lặp bbox chạy trên bản thu nhỏ (cạnh dài <= work_max_side, model chỉ
    nhìn 512px nên không mất thông tin); hội tụ rồi mới crop ảnh gốc theo tọa
    độ quy đổi để giữ nguyên độ phân giải cho các stage sau.
    """
    sess = _get_session("bbox")
    if sess is None:
        return pil_img
    full = _pad_white(pil_img, pil_img.width * 0.05, pil_img.height * 0.05)

    scale = min(1.0, work_max_side / max(full.width, full.height, 1))
    if scale < 1.0:
        img = full.resize(
            (max(1, round(full.width * scale)), max(1, round(full.height * scale))),
            Image.BILINEAR,
        )
    else:
        img = full
    ox, oy = 0, 0  # gốc viewport hiện tại trên bản thu nhỏ

    for _ in range(max_tries):
        if img.width == 0 or img.height == 0:
            return None
        mask = _run(sess, _to_tensor(img, BBOX_IMAGE_SIZE))
        bbox = _mask_to_bbox(mask, img.width, img.height)
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        new_w, new_h = x2 - x1, y2 - y1
        if new_w / img.width > 0.7 and new_h / img.height > 0.7:
            if scale >= 1.0:
                return img.crop((x1, y1, x2, y2))
            return full.crop(
                (
                    max(0, int((ox + x1) / scale)),
                    max(0, int((oy + y1) / scale)),
                    min(full.width, int(np.ceil((ox + x2) / scale))),
                    min(full.height, int(np.ceil((oy + y2) / scale))),
                )
            )
        # ngưỡng 420 được chỉnh theo kích thước gốc -> quy đổi qua scale
        small = img.width / scale < 420 or img.height / scale < 420
        pad_mult = 0.2 if small else 0.12
        x_add, y_add = new_w * pad_mult, new_h * pad_mult
        cx1 = int(max(x1 - x_add, 0))
        cy1 = int(max(y1 - y_add, 0))
        img = img.crop(
            (
                cx1,
                cy1,
                int(min(x2 + x_add, img.width)),
                int(min(y2 + y_add, img.height)),
            )
        )
        ox += cx1
        oy += cy1
    return None


def _image_rotation_angle(pil_img):
    sess = _get_session("rotation")
    if sess is None:
        return 0
    logits = _run(sess, _to_tensor(pil_img, BOARD_PIXEL_WIDTH)).reshape(-1)
    return ROTATIONS[int(np.argmax(logits[:4]))]


def _augment(pil_img):
    """augmentImageData: contrast 1.05-1.15, brightness 0.9-1.1 ngẫu nhiên."""
    img = ImageEnhance.Contrast(pil_img).enhance(1 + 0.05 + np.random.random() * 0.1)
    return ImageEnhance.Brightness(img).enhance(0.9 + np.random.random() * 0.2)


def _flip_color_rows(squares):
    """flipColorTensor: hoán giá trị lớp trắng <-> đen từng ô; lớp 'trống' giữ nguyên."""
    flipped = squares.copy()
    flipped[:, 0:6] = squares[:, 6:12]
    flipped[:, 6:12] = squares[:, 0:6]
    return flipped


def _board_squares_ensemble(pil_img, num_tries=10, min_tries=4, margin=0.35):
    """getBoardFromCropped: ensemble numTries lần, lần lẻ đảo màu, lần >=2 augment.

    Dừng sớm sau số lần chẵn (giữ cân bằng cặp thường/đảo màu) >= min_tries khi
    lưới argmax tích lũy không đổi giữa 2 lần kiểm và mọi ô có biên độ tin cậy
    (top1 - top2 trung bình) > margin — ảnh rõ nét hội tụ sau ~4 lần.
    """
    if pil_img.width < 32 or pil_img.height < 32:
        return None
    sess = _get_session("fen")
    if sess is None:
        return None

    base = pil_img.convert("RGB").resize(
        (BOARD_PIXEL_WIDTH, BOARD_PIXEL_WIDTH), Image.BILINEAR
    )
    total = np.zeros((64, len(PIECE_TYPES)), dtype=np.float32)
    prev_grid = None
    for tries in range(num_tries):
        working = _augment(base) if tries >= 2 else base
        tensor = _to_tensor(working, BOARD_PIXEL_WIDTH)
        color_flipped = tries % 2 == 1
        if color_flipped:
            tensor = -tensor
        out = _run(sess, tensor).reshape(64, len(PIECE_TYPES))
        out = np.clip(out, 0.0, 1.0)
        if color_flipped:
            out = _flip_color_rows(out)
        total += out

        done = tries + 1
        if done % 2 == 0 and done < num_tries:
            grid = np.argmax(total, axis=1)
            if (
                done >= min_tries
                and prev_grid is not None
                and np.array_equal(grid, prev_grid)
            ):
                top2 = np.sort(total, axis=1)[:, -2:] / done
                if float(np.min(top2[:, 1] - top2[:, 0])) > margin:
                    break
            prev_grid = grid
    return total


def _is_board_flipped(squares_onehot, no_rotate_bias=0.2):
    sess = _get_session("orientation")
    if sess is None:
        return False
    arr = squares_onehot.reshape(1, 64, len(PIECE_TYPES)).astype(np.float32)
    score = float(_run(sess, arr).reshape(-1)[0])
    return (score - no_rotate_bias) > 0.5


# --- Ghép FEN (port chess-utils.ts) -------------------------------------------


def _squares_to_grid(squares):
    """Tensor (64,13) -> lưới 8x8 ký tự quân (hàng 0 = rank 8). None nếu trống trơn."""
    grid = []
    has_piece = False
    for row in range(8):
        cells = []
        for col in range(8):
            best = int(np.argmax(squares[row * 8 + col]))
            piece = PIECE_TYPES[best]
            if piece:
                has_piece = True
            cells.append(piece)
        grid.append(cells)
    return grid if has_piece else None


def _grid_to_onehot(grid):
    """Lưới 8x8 -> one-hot (64,13) cho model orientation."""
    onehot = np.zeros((64, len(PIECE_TYPES)), dtype=np.float32)
    for row in range(8):
        for col in range(8):
            piece = grid[row][col]
            idx = PIECE_TYPES.index(piece)
            onehot[row * 8 + col, idx] = 1.0
    return onehot


def _rotate_grid_180(grid):
    return [list(reversed(row)) for row in reversed(grid)]


def _grid_to_fen_board(grid):
    ranks = []
    for row in grid:
        s = ""
        empty = 0
        for piece in row:
            if piece is None:
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += piece
        if empty:
            s += str(empty)
        ranks.append(s or "8")
    return "/".join(ranks)


def refine_fen(fen):
    """Port fixSideToMove: bên KHÔNG được đi đang bị chiếu -> đảo lượt đi.

    Không thêm Vua thiếu (thế cờ thiếu Vua giữ nguyên, hiển thị bằng strict: false).
    """
    if chess is None:
        return fen
    try:
        board = chess.Board(fen)
    except ValueError:
        return fen
    try:
        probe = board.copy()
        probe.turn = not probe.turn
        if probe.is_check():
            return probe.fen()
    except Exception:
        pass
    return fen


# --- API chính -----------------------------------------------------------------


def infer_fen(pil_img, num_tries=10, skip_existence=False):
    """Nhận diện 1 ảnh (chứa bàn cờ) -> FEN 6 trường, hoặc None nếu thất bại."""
    img = _auto_enhance(pil_img)

    if not skip_existence and not _check_existence(img):
        return None

    cropped = _crop_to_chessboard(img, max_tries=num_tries)
    if cropped is None:
        return None

    angle = _image_rotation_angle(cropped)
    if angle:
        # rotateImageData(img, -angle) trên canvas = xoay ngược chiều kim đồng hồ
        # `angle` độ = PIL rotate(angle).
        cropped = cropped.rotate(angle, expand=True)

    squares = _board_squares_ensemble(cropped, num_tries=num_tries)
    if squares is None:
        return None
    grid = _squares_to_grid(squares)
    if grid is None:
        return None

    if _is_board_flipped(_grid_to_onehot(grid)):
        grid = _rotate_grid_180(grid)

    return refine_fen(f"{_grid_to_fen_board(grid)} {FEN_TAIL}")


def detect_boards(pil_page, min_frac=0.12):
    """Tìm các hình bàn cờ trong ảnh trang sách (OpenCV contour + existence).

    Trả về list bbox (x1, y1, x2, y2) theo thứ tự đọc: trên->dưới, trái->phải.
    """
    if cv2 is None:
        return []
    page = pil_page.convert("RGB")
    gray = np.asarray(page.convert("L"))
    h, w = gray.shape

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thr = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    thr = cv2.dilate(thr, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_side = min(w, h) * min_frac
    cands = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < min_side or bh < min_side:
            continue
        ratio = bw / bh
        if not (0.75 <= ratio <= 1.33):
            continue
        if bw > 0.9 * w or bh > 0.9 * h:  # bỏ khung viền cả trang
            continue
        cands.append((x, y, bw, bh))

    cands = _dedupe_boxes(cands)

    boards = []
    for x, y, bw, bh in cands:
        pad = int(0.04 * max(bw, bh))
        box = (max(0, x - pad), max(0, y - pad), min(w, x + bw + pad), min(h, y + bh + pad))
        if _check_existence(page.crop(box)):
            boards.append(box)

    return _reading_order(boards)


def _dedupe_boxes(cands):
    """Khử box chồng lấp/lồng nhau: ưu tiên box to, bỏ box giao >50% diện tích."""
    cands = sorted(cands, key=lambda b: b[2] * b[3], reverse=True)
    kept = []
    for x, y, bw, bh in cands:
        overlapped = False
        for kx, ky, kw, kh in kept:
            ix = max(0, min(x + bw, kx + kw) - max(x, kx))
            iy = max(0, min(y + bh, ky + kh) - max(y, ky))
            if ix * iy > 0.5 * min(bw * bh, kw * kh):
                overlapped = True
                break
        if not overlapped:
            kept.append((x, y, bw, bh))
    return kept


def _reading_order(boxes):
    """Sắp xếp theo thứ tự đọc: nhóm hàng (tâm dọc gần nhau) rồi trái->phải."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    rows = [[boxes[0]]]
    for box in boxes[1:]:
        prev = rows[-1][-1]
        prev_cy = (prev[1] + prev[3]) / 2
        prev_h = prev[3] - prev[1]
        cy = (box[1] + box[3]) / 2
        if abs(cy - prev_cy) < 0.5 * prev_h:
            rows[-1].append(box)
        else:
            rows.append([box])
    ordered = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda b: b[0]))
    return ordered


def fens_for_page(pil_page, num_tries=10):
    """Pipeline trọn gói cho 1 trang: detect -> infer từng hình.

    Trả về list (bbox, fen) theo thứ tự đọc; hình nhận diện thất bại bị bỏ qua.
    Các hình được nhận diện song song (onnxruntime thả GIL khi inference),
    kết quả vẫn theo thứ tự đọc. Không tìm thấy hình nào qua contour -> thử coi
    CẢ ảnh là 1 bàn cờ (ảnh chụp riêng 1 sơ đồ, hoặc sơ đồ không có khung
    viền) — existence model sẽ gác cổng.
    """

    def _infer_box(box):
        try:
            # existence đã kiểm trong detect_boards -> bỏ qua cho nhanh
            return infer_fen(
                pil_page.crop(box), num_tries=num_tries, skip_existence=True
            )
        except Exception:
            return None

    results = []
    boxes = detect_boards(pil_page)
    if boxes:
        with ThreadPoolExecutor(max_workers=min(4, len(boxes))) as pool:
            fens = list(pool.map(_infer_box, boxes))
        results = [(box, fen) for box, fen in zip(boxes, fens) if fen]

    if not results:
        try:
            fen = infer_fen(pil_page, num_tries=num_tries)
        except Exception:
            fen = None
        if fen:
            results.append(((0, 0, pil_page.width, pil_page.height), fen))
    return results
