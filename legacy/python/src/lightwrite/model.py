import shutil
import subprocess

from lightwrite.constants import (
    ALIGN_LEFT, H1, H2, H3, HEADING_MASK, PAGE_BREAK,
)
from lightwrite.layout import cursor_visual_position, visual_lines


class DocVersion:
    """Monotonic counter bumped on every document mutation."""

    __slots__ = ("n",)

    def __init__(self):
        self.n = 0

    def bump(self):
        self.n += 1
        return self.n


def count_words(document):
    text = document_to_string(document).replace(PAGE_BREAK, " ")
    return len(text.split())


def get_line_heading_level(formatting, line_index):
    if line_index < 0 or line_index >= len(formatting):
        return 0
    fmt = formatting[line_index]
    if not fmt:
        return 0
    first = fmt[0]
    if first & H1:
        return 1
    if first & H2:
        return 2
    if first & H3:
        return 3
    return 0


def set_line_heading(formatting, line_index, level):
    if line_index < 0 or line_index >= len(formatting):
        return formatting
    fmt = formatting[line_index]
    new_fmt = []
    for attrs in fmt:
        attrs = attrs & ~HEADING_MASK
        if level == 1:
            attrs |= H1
        elif level == 2:
            attrs |= H2
        elif level == 3:
            attrs |= H3
        new_fmt.append(attrs)
    formatting[line_index] = new_fmt
    return formatting


def collect_headings(document, formatting):
    """Devuelve lista de (line_index, level, text)."""
    result = []
    for i, line in enumerate(document):
        level = get_line_heading_level(formatting, i)
        if level > 0 and line.strip():
            result.append((i, level, line.strip()))
    return result


def get_line_align(alignments, line_index):
    if 0 <= line_index < len(alignments):
        return alignments[line_index]
    return ALIGN_LEFT


def apply_alignment(document, alignments, cursor_line,
                    selection_start, selection_end, new_align):
    new_alignments = list(alignments)
    while len(new_alignments) < len(document):
        new_alignments.append(ALIGN_LEFT)
    while len(new_alignments) > len(document):
        new_alignments.pop()

    if selection_start is not None and selection_end is not None:
        selected = selection_range(document, selection_start, selection_end)
        if selected is not None:
            a, b = selected
            text = document_to_string(document)
            start_line, _unused = absolute_to_position(text, a)
            end_line, _unused = absolute_to_position(text, b)
            if b > a:
                before = text[:b]
                last_nl = before.rfind("\n")
                if last_nl == len(before) - 1 and end_line > start_line:
                    end_line -= 1
            for i in range(start_line, end_line + 1):
                if 0 <= i < len(new_alignments):
                    new_alignments[i] = new_align
    else:
        if 0 <= cursor_line < len(new_alignments):
            new_alignments[cursor_line] = new_align

    return new_alignments


class PlainTextCache:
    """Cache for document_to_string; invalidate on every edit."""

    __slots__ = ("_text", "_dirty")

    def __init__(self):
        self._text = ""
        self._dirty = True

    def invalidate(self):
        self._dirty = True

    def get(self, document):
        if self._dirty:
            self._text = "\n".join(document)
            self._dirty = False
        return self._text


def line_offsets(document):
    offsets = [0]
    total = 0
    for line in document:
        total += len(line) + 1
        offsets.append(total)
    return offsets


def position_to_absolute(document, line, col):
    absolute = 0
    for i in range(line):
        absolute += len(document[i]) + 1
    absolute += col
    return absolute


def absolute_to_position(text, absolute):
    before = text[:absolute]
    line = before.count("\n")
    last_newline = before.rfind("\n")
    if last_newline == -1:
        col = len(before)
    else:
        col = len(before) - last_newline - 1
    return line, col


def selection_range(document, start, end):
    if start is None or end is None:
        return None
    a = position_to_absolute(document, start[0], start[1])
    b = position_to_absolute(document, end[0], end[1])
    if a <= b:
        return a, b
    return b, a


def is_selected(document, line, col, selection_start, selection_end):
    selected = selection_range(document, selection_start, selection_end)
    if selected is None:
        return False
    current = position_to_absolute(document, line, col)
    return selected[0] <= current < selected[1]


def document_to_string(document):
    return "\n".join(document)


def string_to_document(text):
    return text.split("\n")


def document_to_cells(document, formatting):
    cells = []
    for i, line in enumerate(document):
        if i < len(formatting):
            fmt_line = formatting[i]
        else:
            fmt_line = [0] * len(line)
        for j, ch in enumerate(line):
            attrs = fmt_line[j] if j < len(fmt_line) else 0
            cells.append((ch, attrs))
        if i < len(document) - 1:
            cells.append(("\n", 0))
    return cells


def cells_to_document(cells):
    document = []
    formatting = []
    line_chars = []
    line_fmt = []
    for ch, attrs in cells:
        if ch == "\n":
            document.append("".join(line_chars))
            formatting.append(line_fmt)
            line_chars = []
            line_fmt = []
        else:
            line_chars.append(ch)
            line_fmt.append(attrs)
    document.append("".join(line_chars))
    formatting.append(line_fmt)
    return document, formatting


def text_to_cells(text, attrs=0):
    cells = []
    for ch in text:
        if ch == "\n":
            cells.append(("\n", 0))
        else:
            cells.append((ch, attrs))
    return cells


def cells_to_text(cells):
    return "".join(ch for ch, _attrs in cells)


def selected_cells(document, formatting, start, end):
    selected = selection_range(document, start, end)
    if selected is None:
        return []
    a, b = selected
    cells = document_to_cells(document, formatting)
    return cells[a:b]


def delete_selection_rich(document, formatting, alignments, start, end):
    selected = selection_range(document, start, end)
    if selected is None:
        return document, formatting, alignments, 0, 0

    a, b = selected
    # Fast path: deletion within a single line (no cell flatten)
    abs_pos = 0
    for li, line in enumerate(document):
        line_end = abs_pos + len(line)
        if abs_pos <= a < b <= line_end:
            c0 = a - abs_pos
            c1 = b - abs_pos
            document[li] = line[:c0] + line[c1:]
            if li < len(formatting):
                fl = formatting[li]
                formatting[li] = fl[:c0] + fl[c1:]
            return document, formatting, alignments, li, c0
        abs_pos = line_end + 1

    text = document_to_string(document)
    start_line, _unused = absolute_to_position(text, a)

    cells = document_to_cells(document, formatting)
    del cells[a:b]

    new_doc, new_fmt = cells_to_document(cells)
    n_removed = len(document) - len(new_doc)

    before = cells_to_text(cells[:a])
    new_line = before.count("\n")
    last_newline = before.rfind("\n")
    if last_newline == -1:
        new_col = len(before)
    else:
        new_col = len(before) - last_newline - 1

    new_align = list(alignments)
    while len(new_align) < len(document):
        new_align.append(ALIGN_LEFT)

    keep_align = get_line_align(alignments, start_line)
    head = new_align[:start_line]
    tail = new_align[start_line + n_removed + 1:]
    new_align = head + [keep_align] + tail

    while len(new_align) < len(new_doc):
        new_align.append(ALIGN_LEFT)
    new_align = new_align[:len(new_doc)]

    return new_doc, new_fmt, new_align, new_line, new_col


def insert_cells_at_cursor(document, formatting, alignments, line, col, cells):
    absolute = position_to_absolute(document, line, col)
    all_cells = document_to_cells(document, formatting)
    all_cells[absolute:absolute] = cells

    new_doc, new_fmt = cells_to_document(all_cells)
    n_added = len(new_doc) - len(document)

    new_align = list(alignments)
    while len(new_align) < len(document):
        new_align.append(ALIGN_LEFT)
    for _i in range(n_added):
        new_align.insert(line + 1, ALIGN_LEFT)
    while len(new_align) < len(new_doc):
        new_align.append(ALIGN_LEFT)
    new_align = new_align[:len(new_doc)]

    after = cells_to_text(all_cells[:absolute + len(cells)])
    new_line = after.count("\n")
    last_newline = after.rfind("\n")
    if last_newline == -1:
        new_col = len(after)
    else:
        new_col = len(after) - last_newline - 1

    return new_doc, new_fmt, new_align, new_line, new_col


def apply_attr_to_selection(document, formatting, start, end, attr):
    rng = selection_range(document, start, end)
    if rng is None:
        return formatting
    a, b = rng
    if a == b:
        return formatting

    # Map absolute offsets to line/col without building a full cell list
    line_a = col_a = line_b = col_b = 0
    abs_pos = 0
    found_b = False
    for i, line in enumerate(document):
        line_end = abs_pos + len(line)
        if abs_pos <= a <= line_end:
            line_a, col_a = i, a - abs_pos
        if abs_pos <= b <= line_end:
            line_b, col_b = i, b - abs_pos
            found_b = True
            break
        abs_pos = line_end + 1
    if not found_b:
        line_b = len(document) - 1
        col_b = len(document[line_b]) if document else 0

    all_set = True
    any_char = False
    for li in range(line_a, line_b + 1):
        if li >= len(formatting):
            continue
        c0 = col_a if li == line_a else 0
        c1 = col_b if li == line_b else len(document[li])
        fl = formatting[li]
        for ci in range(c0, min(c1, len(fl))):
            any_char = True
            if not (fl[ci] & attr):
                all_set = False
                break
        if any_char and not all_set:
            break
    if not any_char:
        return formatting

    for li in range(line_a, line_b + 1):
        if li >= len(formatting):
            continue
        c0 = col_a if li == line_a else 0
        c1 = col_b if li == line_b else len(document[li])
        fl = formatting[li]
        for ci in range(c0, min(c1, len(fl))):
            if all_set:
                fl[ci] = fl[ci] & ~attr
            else:
                fl[ci] = fl[ci] | attr
    return formatting



def insert_character_rich(document, formatting, line, col, char, attrs):
    document[line] = document[line][:col] + char + document[line][col:]
    if line >= len(formatting):
        formatting.append([])
    for offset, _c in enumerate(char):
        formatting[line].insert(col + offset, attrs)
    col += len(char)
    return document, formatting, line, col


def delete_before_cursor_rich(document, formatting, alignments, line, col):
    if col > 0:
        document[line] = document[line][:col - 1] + document[line][col:]
        if line < len(formatting) and col - 1 < len(formatting[line]):
            del formatting[line][col - 1]
        col -= 1
    elif line > 0:
        previous_length = len(document[line - 1])
        document[line - 1] += document[line]
        if line < len(formatting):
            formatting[line - 1] += formatting[line]
            del formatting[line]
        del document[line]
        if line < len(alignments):
            del alignments[line]
        line -= 1
        col = previous_length
    return document, formatting, alignments, line, col


def delete_at_cursor_rich(document, formatting, alignments, line, col):
    line_text = document[line]
    if col < len(line_text):
        document[line] = line_text[:col] + line_text[col + 1:]
        if line < len(formatting) and col < len(formatting[line]):
            del formatting[line][col]
    elif line < len(document) - 1:
        document[line] += document[line + 1]
        if line + 1 < len(formatting):
            formatting[line] += formatting[line + 1]
            del formatting[line + 1]
        del document[line + 1]
        if line + 1 < len(alignments):
            del alignments[line + 1]
    return document, formatting, alignments, line, col


def enter_rich(document, formatting, alignments, line, col):
    left = document[line][:col]
    right = document[line][col:]
    if line < len(formatting):
        fmt_line = formatting[line]
        left_fmt = fmt_line[:col]
        right_fmt = fmt_line[col:]
    else:
        left_fmt = [0] * len(left)
        right_fmt = [0] * len(right)

    document[line] = left
    formatting[line] = left_fmt
    document.insert(line + 1, right)
    formatting.insert(line + 1, right_fmt)

    current_align = get_line_align(alignments, line)
    alignments.insert(line + 1, current_align)
    return document, formatting, alignments, line + 1, 0


def insert_page_break_rich(document, formatting, alignments, line, col):
    left = document[line][:col]
    right = document[line][col:]
    if line < len(formatting):
        fmt_line = formatting[line]
        left_fmt = fmt_line[:col]
        right_fmt = fmt_line[col:]
    else:
        left_fmt = [0] * len(left)
        right_fmt = [0] * len(right)

    document[line] = left
    formatting[line] = left_fmt
    document.insert(line + 1, PAGE_BREAK)
    formatting.insert(line + 1, [0])
    document.insert(line + 2, right)
    formatting.insert(line + 2, right_fmt)

    current_align = get_line_align(alignments, line)
    alignments.insert(line + 1, current_align)
    alignments.insert(line + 2, current_align)
    return document, formatting, alignments, line + 2, 0


def find_all(document, term):
    if not term:
        return []
    text = document_to_string(document)
    lower_text = text.lower()
    lower_term = term.lower()
    positions = []
    start = 0
    step = max(1, len(lower_term))
    while True:
        idx = lower_text.find(lower_term, start)
        if idx == -1:
            break
        positions.append(absolute_to_position(text, idx))
        start = idx + step
    return positions


def replace_all(document, formatting, term, replacement):
    if not term:
        return document, formatting, 0
    replacement = replacement.replace("\\n", "\n")
    cells = document_to_cells(document, formatting)
    plain = "".join(ch for ch, _attrs in cells)
    term_lower = term.lower()
    plain_lower = plain.lower()
    result = []
    count = 0
    i = 0
    n = len(plain)
    tlen = len(term)
    while i < n:
        if i + tlen <= n and plain_lower[i:i + tlen] == term_lower:
            attrs = cells[i][1]
            for ch in replacement:
                if ch == "\n":
                    result.append(("\n", 0))
                else:
                    result.append((ch, attrs))
            i += tlen
            count += 1
        else:
            result.append(cells[i])
            i += 1
    doc, fmt = cells_to_document(result)
    return doc, fmt, count


def move_left(document, cursor_line, cursor_col):
    if cursor_col > 0:
        cursor_col -= 1
    elif cursor_line > 0:
        cursor_line -= 1
        cursor_col = len(document[cursor_line])
    return cursor_line, cursor_col


def move_right(document, cursor_line, cursor_col):
    if cursor_col < len(document[cursor_line]):
        cursor_col += 1
    elif cursor_line < len(document) - 1:
        cursor_line += 1
        cursor_col = 0
    return cursor_line, cursor_col


def move_up(document, cursor_line, cursor_col, text_width):
    current_row, current_x = cursor_visual_position(
        document, cursor_line, cursor_col, text_width
    )
    if current_row <= 0:
        return cursor_line, cursor_col
    target_row = current_row - 1
    lines = visual_lines(document, text_width)
    line_index, start, text = lines[target_row]
    return line_index, start + min(current_x, len(text))


def move_down(document, cursor_line, cursor_col, text_width):
    current_row, current_x = cursor_visual_position(
        document, cursor_line, cursor_col, text_width
    )
    lines = visual_lines(document, text_width)
    if current_row >= len(lines) - 1:
        return cursor_line, cursor_col
    target_row = current_row + 1
    line_index, start, text = lines[target_row]
    return line_index, start + min(current_x, len(text))


internal_clipboard = ""


internal_rich_clipboard = []


def set_system_clipboard(text):
    global internal_clipboard
    internal_clipboard = text
    try:
        if shutil.which("xclip"):
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            process.communicate(text.encode("utf-8"))
            return
        if shutil.which("xsel"):
            process = subprocess.Popen(
                ["xsel", "--clipboard", "--input"],
                stdin=subprocess.PIPE
            )
            process.communicate(text.encode("utf-8"))
            return
    except Exception:
        pass


def get_system_clipboard():
    try:
        if shutil.which("xclip"):
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace")
        if shutil.which("xsel"):
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return internal_clipboard

