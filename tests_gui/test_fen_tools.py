"""fen_tools: liệt kê, sửa, xoay FEN, vẽ bàn cờ, liên kết Lichess — hàm thuần."""

import unittest

import tests_gui._setup  # noqa: F401
import claude_ocr
import fen_tools as ft

F1 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
F2 = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
F3 = "8/8/8/8/8/8/8/4K3 w - - 0 1"   # thiếu Vua đen -> hợp lệ về cú pháp nhưng không đủ hai Vua


def block(fen, extra=""):
    return "```chessboard\nfen: " + fen + "\n" + extra + "```"


MD = "# Chương\n\n" + block(F1) + "\n\nVăn bản giữa.\n\n" + block(F2) + "\n\n" + block(F1) + "\n\nHết."


class TestListAndValidate(unittest.TestCase):
    def test_list_boards_in_order(self):
        boards = ft.list_boards(MD)
        self.assertEqual([b["n"] for b in boards], [1, 2, 3])
        self.assertEqual([b["fen"] for b in boards], [F1, F2, F1])
        self.assertTrue(all(b["valid"] for b in boards))
        self.assertEqual(ft.list_boards("không có bàn cờ"), [])

    def test_valid_needs_both_kings_and_full_rows(self):
        self.assertTrue(ft.fen_is_valid(F1))
        self.assertFalse(ft.fen_is_valid(F3))                       # thiếu Vua đen
        self.assertFalse(ft.fen_is_valid("8/8/8/8/8/8/8 w - - 0 1"))  # 7 hàng
        self.assertFalse(ft.fen_is_valid("9/8/8/8/8/8/8/4K2k"))
        self.assertFalse(ft.fen_is_valid(""))

    def test_matches_extract_fens(self):
        self.assertEqual([b["fen"] for b in ft.list_boards(MD)], claude_ocr.extract_fens(MD))
        self.assertEqual(ft.fens_text(MD).splitlines(), claude_ocr.extract_fens(MD))


class TestReplaceNth(unittest.TestCase):
    def test_replaces_only_the_nth_block(self):
        out = ft.replace_nth_fen(MD, 2, F1)
        self.assertEqual([b["fen"] for b in ft.list_boards(out)], [F1, F1, F1])
        # phần ngoài các khối không đổi
        self.assertIn("Văn bản giữa.", out)
        self.assertTrue(out.startswith("# Chương"))
        self.assertTrue(out.endswith("Hết."))

    def test_round_trip_restores_original(self):
        edited = ft.replace_nth_fen(MD, 1, F2)
        self.assertNotEqual(edited, MD)
        self.assertEqual(ft.replace_nth_fen(edited, 1, F1), MD)

    def test_normalizes_short_fen_and_flags_strict(self):
        out = ft.replace_nth_fen(MD, 3, "8/8/8/8/8/8/8/4K2k")           # chỉ có trường vị trí
        self.assertIn("fen: 8/8/8/8/8/8/8/4K2k w - - 0 1", out)
        self.assertNotIn("strict: false", ft.replace_nth_fen(MD, 3, "8/8/8/8/8/8/8/4K2k"))
        odd = ft.replace_nth_fen(MD, 3, F3)
        self.assertIn("strict: false", odd)                              # không đủ hai Vua -> plugin cần strict:false

    def test_keeps_single_line_fen_format(self):
        out = ft.replace_nth_fen(MD, 1, "  " + F2 + "  ")
        self.assertIn("```chessboard\nfen: " + F2 + "\n```", out)

    def test_errors(self):
        with self.assertRaises(ValueError):
            ft.replace_nth_fen(MD, 4, F1)
        with self.assertRaises(ValueError):
            ft.replace_nth_fen(MD, 0, F1)
        with self.assertRaises(ValueError):
            ft.replace_nth_fen(MD, 1, "không phải fen")
        with self.assertRaises(ValueError):
            ft.replace_nth_fen(MD, 1, "")


class TestFlipAndLinks(unittest.TestCase):
    def test_flip_is_an_involution_and_keeps_tail(self):
        flipped = ft.flip_fen(F1)
        self.assertEqual(flipped.split(" ")[1:], F1.split(" ")[1:])
        self.assertEqual(ft.flip_fen(flipped), F1)
        self.assertEqual(ft.flip_fen("8/8/8/8/8/8/8/4K2k"), "k2K4/8/8/8/8/8/8/8")

    def test_flip_matches_rotating_the_grid(self):
        import chessboard_fen as cf

        def grid(fen):
            rows = []
            for rank in fen.split(" ")[0].split("/"):
                row = []
                for ch in rank:
                    row.extend([None] * int(ch) if ch.isdigit() else [ch])
                rows.append(row)
            return rows

        self.assertEqual(grid(ft.flip_fen(F1)), cf._rotate_grid_180(grid(F1)))

    def test_lichess_url(self):
        url = ft.lichess_url(F2)
        self.assertTrue(url.startswith("https://lichess.org/editor/6k1/5ppp/8/8/8/8/5PPP/3R2K1_w_-_-_0_1"))
        self.assertNotIn(" ", url)


class TestBoardHtml(unittest.TestCase):
    def test_board_has_64_squares_and_right_pieces(self):
        h = ft.board_html(F2, 200)
        self.assertEqual(h.count('class="mid-sq'), 64)
        self.assertEqual(h.count('class="mid-pc'), 9)    # k + 3 tốt đen, R + K + 3 tốt trắng
        self.assertIn("mid-pc bk", h)
        self.assertIn("mid-pc wr", h)
        self.assertIn("--px:200px", h)
        self.assertIn("FEN chưa hợp lệ", ft.board_html("xyz"))

    def test_checkerboard_colours(self):
        h = ft.board_html("8/8/8/8/8/8/8/8")
        self.assertTrue(h.index('mid-sq l') < h.index('mid-sq d'))   # ô a8 sáng
        self.assertEqual(h.count("mid-sq l"), 32)


if __name__ == "__main__":
    unittest.main()
