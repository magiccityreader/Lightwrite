"""Unit tests for Lightwrite model/RTF (no curses required)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lightwrite.constants import BOLD, ITALIC, ALIGN_LEFT
from lightwrite.model import (
    PlainTextCache,
    apply_attr_to_selection,
    document_to_string,
    insert_character_rich,
)
from lightwrite.undo import apply_undo, push_undo
from lightwrite.rtf import parse_rtf, save_rtf


class UndoTests(unittest.TestCase):
    def test_line_span_undo_typing(self):
        doc = ["hello", "world"]
        fmt = [[0] * 5, [0] * 5]
        al = [ALIGN_LEFT, ALIGN_LEFT]
        stack = []
        push_undo(stack, doc, fmt, al, start=0, end=1)
        doc, fmt, _, _ = insert_character_rich(doc, fmt, 0, 5, "!", 0)
        self.assertEqual(doc[0], "hello!")
        doc, fmt, al = apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc[0], "hello")
        self.assertEqual(doc[1], "world")

    def test_full_undo_enter_split(self):
        doc = ["ab"]
        fmt = [[0, 0]]
        al = [ALIGN_LEFT]
        stack = []
        push_undo(stack, doc, fmt, al)
        # simulate enter at col 1
        doc = ["a", "b"]
        fmt = [[0], [0]]
        al = [ALIGN_LEFT, ALIGN_LEFT]
        doc, fmt, al = apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc, ["ab"])


class CacheTests(unittest.TestCase):
    def test_plain_cache(self):
        cache = PlainTextCache()
        doc = ["a", "b"]
        self.assertEqual(cache.get(doc), "a\nb")
        doc[0] = "z"
        self.assertEqual(cache.get(doc), "a\nb")  # stale until invalidate
        cache.invalidate()
        self.assertEqual(cache.get(doc), "z\nb")


class AttrTests(unittest.TestCase):
    def test_apply_attr_single_line(self):
        doc = ["hello"]
        fmt = [[0, 0, 0, 0, 0]]
        start = (0, 0)
        end = (0, 5)
        fmt = apply_attr_to_selection(doc, fmt, start, end, BOLD)
        self.assertTrue(all(a & BOLD for a in fmt[0]))
        fmt = apply_attr_to_selection(doc, fmt, start, end, BOLD)
        self.assertTrue(all(not (a & BOLD) for a in fmt[0]))


class RtfTests(unittest.TestCase):
    def test_roundtrip_basic(self):
        doc = ["Hola", "mundo"]
        fmt = [[BOLD, BOLD, BOLD, BOLD], [ITALIC] * 5]
        al = [ALIGN_LEFT, ALIGN_LEFT]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.rtf")
            save_rtf(doc, fmt, al, path)
            with open(path, "r", encoding="ascii", errors="replace") as f:
                content = f.read()
            self.assertTrue(content.lstrip().startswith("{\\rtf"))
            d2, f2, a2 = parse_rtf(content)
            self.assertEqual(document_to_string(d2).replace("\r", ""),
                             "Hola\nmundo")


if __name__ == "__main__":
    unittest.main()
