"""Tests for operation-log undo and the layout cache (no curses required)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lightwrite.constants import ALIGN_CENTER, ALIGN_LEFT
from lightwrite.layout import LayoutCache, _compute_visual_lines
from lightwrite.undo import (
    apply_undo, push_delete, push_insert, push_join, push_span,
)


class OpLogUndoTests(unittest.TestCase):
    def test_insert_undo(self):
        doc, fmt, al = ["helo"], [[0] * 4], [ALIGN_LEFT]
        stack = []
        doc[0] = "hello"
        fmt[0].insert(3, 0)
        push_insert(stack, 0, 3, "l")
        apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc, ["helo"])
        self.assertEqual(len(fmt[0]), 4)

    def test_typing_coalesces_into_one_entry(self):
        stack = []
        for i, ch in enumerate("abc"):
            push_insert(stack, 0, i, ch)
        self.assertEqual(stack, [("insert", 0, 0, "abc")])

    def test_space_breaks_coalescing(self):
        stack = []
        push_insert(stack, 0, 0, "a")
        push_insert(stack, 0, 1, " ")
        push_insert(stack, 0, 2, "b")
        self.assertEqual(len(stack), 3)

    def test_non_adjacent_insert_not_coalesced(self):
        stack = []
        push_insert(stack, 0, 0, "a")
        push_insert(stack, 0, 5, "b")
        push_insert(stack, 1, 6, "c")
        self.assertEqual(len(stack), 3)

    def test_delete_undo_restores_attrs(self):
        doc, fmt, al = ["ac"], [[1, 3]], [ALIGN_LEFT]
        stack = []
        push_delete(stack, 0, 1, "b", [2])
        apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc, ["abc"])
        self.assertEqual(fmt, [[1, 2, 3]])

    def test_join_undo_splits_line(self):
        doc, fmt, al = ["abcd"], [[0, 0, 1, 1]], [ALIGN_LEFT]
        stack = []
        push_join(stack, 0, 2, "cd", [1, 1], ALIGN_CENTER)
        apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc, ["ab", "cd"])
        self.assertEqual(fmt, [[0, 0], [1, 1]])
        self.assertEqual(al, [ALIGN_LEFT, ALIGN_CENTER])

    def test_scoped_span_undo_after_backspace_join(self):
        doc = ["one", "two", "three"]
        fmt = [[0] * 3, [0] * 3, [0] * 5]
        al = [ALIGN_LEFT] * 3
        stack = []
        push_span(stack, doc, fmt, al, 0, 2)
        doc[0:2] = ["onetwo"]
        fmt[0:2] = [[0] * 6]
        al[0:2] = [ALIGN_LEFT]
        apply_undo(stack, doc, fmt, al)
        self.assertEqual(doc, ["one", "two", "three"])
        self.assertEqual(len(al), 3)

    def test_full_span_restores_previous_document(self):
        old = ["a", "b", "c"]
        stack = []
        push_span(stack, old, [[0], [0], [0]], [ALIGN_LEFT] * 3)
        new_doc, new_fmt, new_al = ["x"], [[0]], [ALIGN_LEFT]
        doc, _, al = apply_undo(stack, new_doc, new_fmt, new_al)
        self.assertEqual(doc, ["a", "b", "c"])
        self.assertEqual(len(al), 3)

    def test_empty_stack(self):
        self.assertIsNone(apply_undo([], [""], [[]], [ALIGN_LEFT]))


class LayoutCacheTests(unittest.TestCase):
    def test_hit_returns_same_object(self):
        cache = LayoutCache()
        doc = ["hello world"]
        first = cache.visual_lines(doc, 20, version=1)
        self.assertIs(cache.visual_lines(doc, 20, version=1), first)

    def test_version_bump_recomputes(self):
        cache = LayoutCache()
        doc = ["hello"]
        cache.visual_lines(doc, 20, version=1)
        doc[0] = "hello " * 10
        lines = cache.visual_lines(doc, 20, version=2)
        self.assertEqual(lines, _compute_visual_lines(doc, 20))

    def test_width_change_recomputes(self):
        cache = LayoutCache()
        doc = ["word " * 10]
        wide = cache.visual_lines(doc, 80, version=1)
        narrow = cache.visual_lines(doc, 10, version=1)
        self.assertGreater(len(narrow), len(wide))

    def test_distinct_documents_do_not_collide(self):
        cache = LayoutCache()
        a = ["aaa"]
        b = ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]
        cache.visual_lines(a, 10, version=1)
        self.assertEqual(cache.visual_lines(b, 10, version=1),
                         _compute_visual_lines(b, 10))


if __name__ == "__main__":
    unittest.main()
