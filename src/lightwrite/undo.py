"""Operation-log undo for Lightwrite.

Entries are either:
  ("insert", line, col, text)           — undo deletes text
  ("delete", line, col, text, attrs)    — undo reinserts text+attrs on one line
  ("join", line, col, right_text, right_fmt, right_align)
        — undo splits: line was joined from line and line+1
  ("span", start, old_doc, old_fmt, old_align, old_len)
        — line-range snapshot fallback for complex edits
  legacy 3-tuple deepcopy / 5-tuple span without tag
"""
from __future__ import annotations

from lightwrite.constants import ALIGN_LEFT, MAX_UNDO


def push_span(undo_stack, document, formatting, alignments, start=None, end=None):
    if start is None:
        start = 0
    if end is None:
        end = len(document)
    start = max(0, start)
    end = max(start, min(len(document), end))
    undo_stack.append((
        "span",
        start,
        document[start:end],
        [fl[:] for fl in formatting[start:end]],
        alignments[start:end],
        len(document),
    ))
    _trim(undo_stack)


def push_insert(undo_stack, line, col, text):
    if undo_stack and not text.isspace():
        last = undo_stack[-1]
        if (len(last) == 4 and last[0] == "insert" and last[1] == line
                and last[2] + len(last[3]) == col
                and not last[3][-1:].isspace()):
            undo_stack[-1] = ("insert", line, last[2], last[3] + text)
            return
    undo_stack.append(("insert", line, col, text))
    _trim(undo_stack)


def push_delete(undo_stack, line, col, text, attrs):
    undo_stack.append(("delete", line, col, text, list(attrs)))
    _trim(undo_stack)


def push_join(undo_stack, line, col, right_text, right_fmt, right_align):
    undo_stack.append((
        "join", line, col, right_text, list(right_fmt), right_align,
    ))
    _trim(undo_stack)


def push_undo(undo_stack, document, formatting, alignments, start=None, end=None):
    """Backward-compatible alias → span snapshot."""
    push_span(undo_stack, document, formatting, alignments, start, end)


def _trim(undo_stack):
    while len(undo_stack) > MAX_UNDO:
        undo_stack.pop(0)


def apply_undo(undo_stack, document, formatting, alignments):
    if not undo_stack:
        return None
    entry = undo_stack.pop()

    # Legacy deepcopy triple
    if len(entry) == 3 and not isinstance(entry[0], str):
        return entry[0], entry[1], entry[2]

    # Legacy untagged span 5-tuple
    if len(entry) == 5 and not isinstance(entry[0], str):
        start, old_doc, old_fmt, old_align, old_len = entry
        return _restore_span(
            document, formatting, alignments,
            start, old_doc, old_fmt, old_align, old_len,
        )

    kind = entry[0]
    if kind == "span":
        _, start, old_doc, old_fmt, old_align, old_len = entry
        return _restore_span(
            document, formatting, alignments,
            start, old_doc, old_fmt, old_align, old_len,
        )

    if kind == "insert":
        _, line, col, text = entry
        n = len(text)
        document[line] = document[line][:col] + document[line][col + n:]
        if line < len(formatting):
            del formatting[line][col:col + n]
        return document, formatting, alignments

    if kind == "delete":
        _, line, col, text, attrs = entry
        document[line] = document[line][:col] + text + document[line][col:]
        if line >= len(formatting):
            formatting.append([])
        for i, a in enumerate(attrs):
            formatting[line].insert(col + i, a)
        return document, formatting, alignments

    if kind == "join":
        _, line, col, right_text, right_fmt, right_align = entry
        # Current: document[line] contains left+right; split at col
        left = document[line][:col]
        document[line] = left
        if line < len(formatting):
            formatting[line] = formatting[line][:col]
        document.insert(line + 1, right_text)
        formatting.insert(line + 1, list(right_fmt))
        alignments.insert(line + 1, right_align)
        return document, formatting, alignments

    # Unknown — ignore
    return document, formatting, alignments


def _restore_span(document, formatting, alignments,
                  start, old_doc, old_fmt, old_align, old_len):
    delta = len(document) - old_len
    span_end = start + len(old_doc) + delta
    if span_end < start:
        span_end = start
    if span_end > len(document):
        span_end = len(document)
    document[start:span_end] = list(old_doc)
    formatting[start:span_end] = [fl[:] for fl in old_fmt]
    alignments[start:span_end] = list(old_align)
    while len(alignments) < len(document):
        alignments.append(ALIGN_LEFT)
    alignments[:] = alignments[:len(document)]
    return document, formatting, alignments
