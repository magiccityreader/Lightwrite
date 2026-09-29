"""Visual layout and cursor mapping with versioned cache."""
import unicodedata

from lightwrite.constants import (
    ALIGN_CENTER, ALIGN_JUSTIFY, ALIGN_RIGHT,
)


def display_width(s):
    w = 0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def truncate_display(s, max_width):
    result = ""
    w = 0
    for ch in s:
        cw = display_width(ch)
        if w + cw > max_width:
            break
        result += ch
        w += cw
    return result


def truncate_left(s, max_width):
    if max_width <= 0:
        return ""
    if display_width(s) <= max_width:
        return s
    result = ""
    w = 0
    for ch in reversed(s):
        cw = display_width(ch)
        if w + cw > max_width - 1:
            break
        result = ch + result
        w += cw
    return "…" + result


def compute_line_layout(text, text_width, align, is_last_subline):
    n = len(text)

    if align == ALIGN_CENTER:
        return text, max(0, (text_width - n) // 2), None

    if align == ALIGN_RIGHT:
        return text, max(0, text_width - n), None

    if align == ALIGN_JUSTIFY and not is_last_subline:
        words = [w for w in text.split(" ") if w]
        if len(words) >= 2:
            total_chars = sum(len(w) for w in words)
            gaps = len(words) - 1
            extra = text_width - total_chars - gaps

            if extra > 0:
                extra_per_gap = extra // gaps
                remainder = extra % gaps

                word_positions = []
                pos = 0
                for w in words:
                    idx = text.find(w, pos)
                    word_positions.append(idx)
                    pos = idx + len(w)

                result = []
                mapping = []
                for wi, w in enumerate(words):
                    wp = word_positions[wi]
                    for k, c in enumerate(w):
                        result.append(c)
                        mapping.append(wp + k)
                    if wi < len(words) - 1:
                        space_col = wp + len(w)
                        num = 1 + extra_per_gap
                        if wi < remainder:
                            num += 1
                        for _pad in range(num):
                            result.append(" ")
                            mapping.append(space_col)

                return "".join(result), 0, mapping

    return text, 0, None


def _compute_visual_lines(document, width):
    result = []
    for line_index, line in enumerate(document):
        if line == "":
            result.append((line_index, 0, ""))
            continue
        start = 0
        while start < len(line):
            remaining = line[start:]
            if len(remaining) <= width:
                result.append((line_index, start, remaining))
                break
            cut = remaining.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = width
            piece = remaining[:cut]
            result.append((line_index, start, piece))
            start += cut
            while start < len(line) and line[start] == " ":
                start += 1
    if not result:
        result.append((0, 0, ""))
    return result


class LayoutCache:
    """Cache visual_lines keyed by (doc_version, width, document identity)."""

    __slots__ = ("_key", "_lines")

    def __init__(self):
        self._key = None
        self._lines = None

    def invalidate(self):
        self._key = None
        self._lines = None

    def visual_lines(self, document, width, version=0):
        key = (version, width, id(document), len(document))
        if key != self._key or self._lines is None:
            self._lines = _compute_visual_lines(document, width)
            self._key = key
        return self._lines


# Module-level cache used when callers don't pass their own
_DEFAULT_CACHE = LayoutCache()
_active_version = 0


def set_layout_version(version: int):
    global _active_version
    _active_version = version


def visual_lines(document, width, version=None, cache=None):
    if version is None:
        version = _active_version
    c = cache if cache is not None else _DEFAULT_CACHE
    return c.visual_lines(document, width, version)


def cursor_visual_position(document, cursor_line, cursor_col, width,
                           version=None, cache=None):
    lines = visual_lines(document, width, version=version, cache=cache)
    for row, (line_index, start, text) in enumerate(lines):
        if line_index != cursor_line:
            continue
        end = start + len(text)
        if start <= cursor_col <= end:
            return row, cursor_col - start
    last_row, (line_index, start, text) = len(lines) - 1, lines[-1]
    if line_index == cursor_line:
        return last_row, max(0, cursor_col - start)
    return 0, 0


def adjust_scroll(document, cursor_line, cursor_col, width,
                  visible_rows, scroll_row, version=None, cache=None):
    cursor_row, _unused = cursor_visual_position(
        document, cursor_line, cursor_col, width,
        version=version, cache=cache)
    if cursor_row < scroll_row:
        scroll_row = cursor_row
    elif cursor_row >= scroll_row + visible_rows:
        scroll_row = cursor_row - visible_rows + 1
    return max(0, scroll_row)


def mouse_to_document_position(
    mouse_x, mouse_y, document, alignments,
    text_width, scroll_row, top, bottom, text_x,
    version=None, cache=None,
):
    from lightwrite.model import get_line_align

    if mouse_y < top:
        visual_row = scroll_row
    elif mouse_y >= bottom:
        lines = visual_lines(document, text_width, version=version, cache=cache)
        visible_rows = max(1, bottom - top)
        visual_row = scroll_row + visible_rows - 1
    else:
        visual_row = mouse_y - top + scroll_row

    lines = visual_lines(document, text_width, version=version, cache=cache)
    if not lines:
        return 0, 0
    visual_row = max(0, min(visual_row, len(lines) - 1))
    line_index, start, text = lines[visual_row]

    if visual_row == len(lines) - 1:
        is_last_subline = True
    else:
        is_last_subline = lines[visual_row + 1][0] != line_index

    align = get_line_align(alignments, line_index)
    display_text, offset, mapping = compute_line_layout(
        text, text_width, align, is_last_subline
    )

    screen_col = mouse_x - text_x - offset
    if screen_col < 0:
        screen_col = 0

    if screen_col >= len(display_text):
        orig_col = (mapping[-1] + 1) if mapping else len(text)
    else:
        orig_col = mapping[screen_col] if mapping else screen_col

    if orig_col > len(text):
        orig_col = len(text)

    return line_index, start + orig_col
