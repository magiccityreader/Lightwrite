import curses
import os

from lightwrite import state

from lightwrite.constants import (
    BOLD, DROPDOWN_ROW, H1, H2, H3, HEADING_MASK, ITALIC,
    MENU_ROW, MENU_SEPARATOR, PAGE_BREAK, SEP_TITLE_ROW, SEP_TOP_ROW,
    TEXT_TOP, TEXT_WIDTH, TITLE_ROW,
    UNDERLINE, BROWSE_EXTENSIONS,
)
from lightwrite.i18n import ABOUT_TEXT, MANUAL_TEXT, tr
from lightwrite.layout import (
    _compute_visual_lines, compute_line_layout, cursor_visual_position,
    truncate_display,
    truncate_left, visual_lines,
)
from lightwrite.model import (
    count_words, get_line_align, line_offsets, selection_range,
)






def _base_attr():
    if state.COLORS_READY:
        try:
            return curses.color_pair(2)
        except Exception:
            return 0
    return 0


def curses_attr_for(attrs):
    a = _base_attr()
    if attrs & BOLD:
        a |= curses.A_BOLD
    if attrs & ITALIC:
        a |= getattr(curses, "A_ITALIC", 0)
    if attrs & UNDERLINE:
        a |= curses.A_UNDERLINE
    return a


def _style_for_attrs(attrs):
    """Devuelve el atributo curses adecuado según el modo."""
    if state.TTY_MODE:
        h = attrs & HEADING_MASK
        b = bool(attrs & BOLD)
        i = bool(attrs & ITALIC)
        u = bool(attrs & UNDERLINE)

        if h == H1:
            return curses.color_pair(7) | curses.A_BOLD
        if h == H2:
            return curses.color_pair(8) | curses.A_BOLD
        if h == H3:
            return curses.color_pair(4) | curses.A_BOLD
        if b and i:
            return curses.color_pair(6) | curses.A_BOLD
        if b:
            return curses.color_pair(3) | curses.A_BOLD
        if i:
            return curses.color_pair(4)
        if u:
            return curses.color_pair(5) | curses.A_UNDERLINE
        return curses.color_pair(2)

    a = _base_attr()
    if attrs & BOLD:
        a |= curses.A_BOLD
    if attrs & ITALIC:
        a |= getattr(curses, "A_ITALIC", 0)
    if attrs & UNDERLINE:
        a |= curses.A_UNDERLINE
    return a


def init_colors():
    pass  # flags on lightwrite.state
    try:
        if not curses.has_colors():
            state.COLORS_READY = False  # mutated by init_colors
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass

        term = os.environ.get("TERM", "").lower()
        state.TTY_MODE = term in ("linux", "linux-16color", "cons25")
        state.USE_256 = curses.COLORS >= 256

        if state.TTY_MODE:
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(8, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        else:
            if state.USE_256:
                try:
                    curses.init_pair(1, 208, curses.COLOR_BLACK)
                except Exception:
                    curses.init_pair(1, curses.COLOR_YELLOW,
                                     curses.COLOR_BLACK)
            else:
                curses.init_pair(1, curses.COLOR_YELLOW,
                                 curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)

        state.COLORS_READY = True
    except Exception:
        state.COLORS_READY = False  # mutated by init_colors


def chapter_panel_geometry(width, height):
    box_w = min(72, max(40, width - 4))
    box_h = min(22, max(10, height - 4))
    box_x = max(0, (width - box_w) // 2)
    box_y = max(0, (height - box_h) // 2)
    list_start = box_y + 1
    list_height = box_h - 3
    return box_x, box_y, box_w, box_h, list_start, list_height


def draw_chapter_panel(stdscr, headings, index, scroll, width, height):
    box_x, box_y, box_w, box_h, list_start, list_height = (
        chapter_panel_geometry(width, height)
    )
    base = _base_attr()

    title = tr(" Mapa de capítulos ")
    top_bar_left = "┌─" + title
    top_bar_right = "─" * max(0, box_w - len(top_bar_left) - 1) + "┐"
    top_bar = (top_bar_left + top_bar_right)[:box_w]

    try:
        stdscr.addstr(box_y, box_x, top_bar, base | curses.A_BOLD)
    except curses.error:
        pass

    inner_w = box_w - 2
    spaces = " " * inner_w
    for i in range(1, box_h - 1):
        try:
            stdscr.addstr(box_y + i, box_x, "│", base)
            stdscr.addstr(box_y + i, box_x + 1, spaces, base)
            stdscr.addstr(box_y + i, box_x + box_w - 1, "│", base)
        except curses.error:
            pass

    list_x = box_x + 2
    list_w = box_w - 4

    if not headings:
        msg = truncate_display(
            tr("(sin capítulos — usa Capítulos → Crear capítulo)"), list_w
        )
        try:
            stdscr.addstr(list_start, list_x, msg, base)
        except curses.error:
            pass
    else:
        for i in range(list_height):
            entry_i = scroll + i
            if entry_i >= len(headings):
                break
            _line_index, level, text = headings[entry_i]
            indent = "    " * (level - 1)
            bullet = "▸ " if level == 1 else "· "
            display = indent + bullet + text
            display = truncate_display(display, list_w).ljust(list_w)

            attr = base
            if level == 1:
                attr |= curses.A_BOLD
            if entry_i == index:
                attr |= curses.A_REVERSE

            try:
                stdscr.addstr(list_start + i, list_x, display, attr)
            except curses.error:
                pass

    try:
        stdscr.addstr(box_y + box_h - 2, box_x + 1,
                      "─" * (box_w - 2), base)
    except curses.error:
        pass

    try:
        stdscr.addstr(box_y + box_h - 1, box_x, "│", base)
        stdscr.addstr(box_y + box_h - 1, box_x + 1, spaces, base)
        stdscr.addstr(box_y + box_h - 1, box_x + box_w - 1, "│", base)
    except curses.error:
        pass

    hints = tr(" ↑↓ mover · Enter ir · n: nuevo · Esc cerrar ")
    hints = truncate_display(hints, box_w - 4)
    hint_x = box_x + max(1, (box_w - len(hints)) // 2)
    try:
        stdscr.addstr(box_y + box_h - 1, hint_x, hints, base)
    except curses.error:
        pass


def list_directory(path):
    entries = []
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and parent != os.path.abspath(path):
            entries.append(("..", parent, True))

        dirs = []
        files = []
        for name in sorted(os.listdir(path)):
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            try:
                if os.path.isdir(full):
                    dirs.append((name, full, True))
                elif name.lower().endswith(BROWSE_EXTENSIONS):
                    files.append((name, full, False))
            except Exception:
                continue

        entries.extend(dirs)
        entries.extend(files)
    except Exception:
        pass
    return entries


def browser_box_geometry(width, height):
    box_w = min(72, max(40, width - 4))
    box_h = min(22, max(10, height - 4))
    box_x = max(0, (width - box_w) // 2)
    box_y = max(0, (height - box_h) // 2)
    return box_x, box_y, box_w, box_h


def draw_browser(stdscr, browse_dir, entries, index, scroll, width, height):
    box_x, box_y, box_w, box_h = browser_box_geometry(width, height)
    base = _base_attr()

    title = tr(" Abrir documento ")
    top_bar_left = "┌─" + title
    top_bar_right = "─" * max(0, box_w - len(top_bar_left) - 1) + "┐"
    top_bar = (top_bar_left + top_bar_right)[:box_w]

    try:
        stdscr.addstr(box_y, box_x, top_bar, base | curses.A_BOLD)
    except curses.error:
        pass

    inner_w = box_w - 2
    spaces = " " * inner_w
    for i in range(1, box_h - 1):
        try:
            stdscr.addstr(box_y + i, box_x, "│", base)
            stdscr.addstr(box_y + i, box_x + 1, spaces, base)
            stdscr.addstr(box_y + i, box_x + box_w - 1, "│", base)
        except curses.error:
            pass

    path_display = truncate_left(browse_dir, box_w - 4)
    try:
        stdscr.addstr(box_y + 1, box_x + 2, path_display, base)
    except curses.error:
        pass

    try:
        stdscr.addstr(box_y + 2, box_x + 1, "─" * (box_w - 2), base)
    except curses.error:
        pass

    list_start = box_y + 3
    list_height = box_h - 5
    list_x = box_x + 2
    list_w = box_w - 4

    for i in range(list_height):
        entry_i = scroll + i
        if entry_i >= len(entries):
            break
        name, full, is_dir = entries[entry_i]
        row_y = list_start + i
        selected = (entry_i == index)

        if is_dir:
            display = name + "/" if name != ".." else ".."
        else:
            display = name

        display = truncate_display(display, list_w).ljust(list_w)
        attr = base
        if is_dir:
            attr |= curses.A_BOLD
        if selected:
            attr |= curses.A_REVERSE

        try:
            stdscr.addstr(row_y, list_x, display, attr)
        except curses.error:
            pass

    try:
        stdscr.addstr(box_y + box_h - 2, box_x + 1,
                      "─" * (box_w - 2), base)
    except curses.error:
        pass

    hints = tr(" Enter: abrir  ·  Retroceso: subir  ·  Esc: cancelar ")
    hints = truncate_display(hints, box_w - 4)
    hint_x = box_x + max(1, (box_w - len(hints)) // 2)
    try:
        stdscr.addstr(box_y + box_h - 1, hint_x, hints, base)
    except curses.error:
        pass


def menu_bar_total_width(menus):
    total = 0
    sep = MENU_SEPARATOR
    for i, (name, _items) in enumerate(menus):
        total += len(name)
        if i < len(menus) - 1:
            total += len(sep)
    return total


def menu_bar_layout(menus, width):
    total = menu_bar_total_width(menus)
    start_x = max(2, (width - total) // 2)
    layout = []
    x = start_x
    sep = MENU_SEPARATOR
    for i, (name, _items) in enumerate(menus):
        end = x + len(name)
        layout.append((name, x, end))
        x = end
        if i < len(menus) - 1:
            x += len(sep)
    return layout


def menu_index_at(menus, x, width):
    for i, (_name, start, end) in enumerate(menu_bar_layout(menus, width)):
        if start <= x < end:
            return i
    return -1


def dropdown_size(menu):
    max_label = 0
    max_shortcut = 0
    for item in menu:
        if item is None:
            continue
        label, shortcut, _action = item
        max_label = max(max_label, len(label))
        max_shortcut = max(max_shortcut, len(shortcut))
    return 1 + 1 + max_label + 2 + max_shortcut + 1 + 1


def dropdown_x(menu, menu_label_x, width):
    w = dropdown_size(menu)
    x = menu_label_x
    if x + w > width:
        x = max(0, width - w)
    return x


def dropdown_item_at(menu, mx, my, dx, dy):
    w = dropdown_size(menu)
    if mx < dx or mx >= dx + w:
        return -1
    if my <= dy or my >= dy + len(menu) + 2:
        return -1
    idx = my - dy - 1
    if idx < 0 or idx >= len(menu):
        return -1
    if menu[idx] is None:
        return -1
    return idx


def draw_title_bar(stdscr, window_title, width):
    base = _base_attr()
    left_text = tr("Herramientas: F9")
    if state.TTY_MODE:
        right_text = tr("Selección: Ctrl+Space")
    else:
        right_text = tr("Selección: Shift→")

    # En terminales muy estrechas se omiten las pistas.
    show_left = width >= 50
    show_right = width >= 70

    left_x = 2
    left_end = left_x + len(left_text) if show_left else 0

    right_x = width - len(right_text) - 2
    right_end = right_x + len(right_text)

    # Pista izquierda
    if show_left and left_end < width - 1:
        try:
            stdscr.addstr(TITLE_ROW, left_x, left_text, base)
        except curses.error:
            pass

    # Pista derecha
    if show_right and right_x > left_end + 2 and right_end <= width - 1:
        try:
            stdscr.addstr(TITLE_ROW, right_x, right_text, base)
        except curses.error:
            pass

    # Espacio disponible para el título, entre las dos pistas
    avail_start = (left_end + 2) if show_left else 2
    if show_right and right_x > avail_start + 2:
        avail_end = right_x - 2
    else:
        avail_end = width - 2

    avail = avail_end - avail_start
    if avail <= 0:
        return

    title = window_title
    if len(title) > avail:
        title = title[:avail]

    title_x = avail_start + (avail - len(title)) // 2

    try:
        stdscr.addstr(TITLE_ROW, title_x, title,
                      base | curses.A_BOLD)
    except curses.error:
        pass


def draw_menu_bar(stdscr, menus, menu_open, width):
    layout = menu_bar_layout(menus, width)
    sep = MENU_SEPARATOR
    base = _base_attr()
    for i, (name, start, _end) in enumerate(layout):
        is_open = (i == menu_open)
        attr = base | curses.A_BOLD
        if is_open:
            attr |= curses.A_REVERSE
        try:
            stdscr.addstr(MENU_ROW, start, name, attr)
        except curses.error:
            pass
        if i < len(menus) - 1:
            try:
                stdscr.addstr(MENU_ROW, start + len(name), sep, base)
            except curses.error:
                pass


def draw_dropdown(stdscr, menu, dx, dy, selected_index=-1):
    w = dropdown_size(menu)
    x = dx
    y = dy
    base = _base_attr()

    max_label = 0
    max_shortcut = 0
    for item in menu:
        if item is None:
            continue
        l2, s2, _a = item
        max_label = max(max_label, len(l2))
        max_shortcut = max(max_shortcut, len(s2))

    try:
        stdscr.addstr(y, x, "┌" + "─" * (w - 2) + "┐", base)
    except curses.error:
        pass

    y += 1
    item_index = 0
    for item in menu:
        if item is None:
            try:
                stdscr.addstr(y, x, "├" + "─" * (w - 2) + "┤", base)
            except curses.error:
                pass
        else:
            label, shortcut, _a = item
            inner = (" " + label.ljust(max_label) + "  "
                     + shortcut.rjust(max_shortcut) + " ")
            inner = inner[:w - 2].ljust(w - 2)
            item_attr = base
            if item_index == selected_index:
                item_attr |= curses.A_REVERSE
            try:
                stdscr.addstr(y, x, "│", base)
                stdscr.addstr(y, x + 1, inner, item_attr)
                stdscr.addstr(y, x + w - 1, "│", base)
            except curses.error:
                pass
        item_index += 1
        y += 1

    try:
        stdscr.addstr(y, x, "└" + "─" * (w - 2) + "┘", base)
    except curses.error:
        pass


def _draw_open_menu(stdscr, menu_open, width, selected_index=-1):
    if menu_open < 0 or menu_open >= len(MENUS):
        return
    _name, menu_items = MENUS[menu_open]
    if menu_items is None:
        return
    layout = menu_bar_layout(MENUS, width)
    menu_label_x = layout[menu_open][1]
    dx = dropdown_x(menu_items, menu_label_x, width)
    draw_dropdown(stdscr, menu_items, dx, DROPDOWN_ROW, selected_index)


def draw_editor(
    stdscr, document, formatting, alignments,
    cursor_line, cursor_col, selection_start, selection_end,
    scroll_row, status_message, typing_attrs, window_title,
    mode, prompt_buffer, prompt_label, help_scroll,
    search_active, search_matches, search_index,
    menu_open, menu_selected,
    browse_dir, browse_entries, browse_index, browse_scroll,
    export_animating, export_spinner, export_kind,
    spell_positions=None,
    spell_suggestions=None,
    spell_unavailable_msg="",
    spell_active=False,
    chapter_headings=None,
    chapter_index=0,
    chapter_scroll=0,
    full_redraw=True,
):
    height, width = stdscr.getmaxyx()
    if full_redraw:
        stdscr.erase()

        # Fondo negro intenso
        if state.COLORS_READY:
            try:
                stdscr.bkgd(" ", curses.color_pair(2))
            except Exception:
                pass
    else:
        # Light path: clear status row only; body/title kept from last frame
        try:
            stdscr.move(height - 1, 0)
            stdscr.clrtoeol()
        except curses.error:
            pass

    text_width = min(TEXT_WIDTH, max(1, width - 4))
    text_x = max(2, (width - text_width) // 2)

    top = TEXT_TOP
    bottom = height - 2
    if bottom <= top:
        bottom = top + 1

    if full_redraw:
        draw_title_bar(stdscr, window_title, width)

        try:
            stdscr.addstr(SEP_TITLE_ROW, 0, "─" * max(1, width - 1),
                          _base_attr())
        except curses.error:
            pass

        draw_menu_bar(stdscr, MENUS, menu_open, width)

        try:
            stdscr.addstr(SEP_TOP_ROW, 0, "─" * max(1, width - 1),
                          _base_attr())
        except curses.error:
            pass
        try:
            stdscr.addstr(bottom, 0, "─" * max(1, width - 1), _base_attr())
        except curses.error:
            pass

    status_y = height - 1

    if mode in ("help", "about"):
        if not full_redraw:
            # Overlays always need a complete paint
            stdscr.erase()
        if mode == "help":
            source_text = MANUAL_TEXT
            title_line = tr("Manual de Lightwrite")
        else:
            source_text = ABOUT_TEXT
            title_line = tr("Acerca de")

        doc_lines = source_text.split("\n")
        doc_visual = _compute_visual_lines(doc_lines, text_width)

        try:
            tx = max(2, (width - len(title_line)) // 2)
            stdscr.addstr(top, tx, title_line,
                          _base_attr() | curses.A_BOLD)
        except curses.error:
            pass

        body_top = top + 2
        base = _base_attr()

        for visual_row, (_idx, _start, text) in enumerate(doc_visual):
            screen_y = body_top + visual_row - help_scroll
            if screen_y < body_top or screen_y >= bottom:
                continue
            try:
                stdscr.addstr(screen_y, text_x,
                              text[:width - text_x - 1], base)
            except curses.error:
                pass

        try:
            footer = tr("↑↓ desplazar  ·  Esc para volver")
            fx = max(2, (width - len(footer)) // 2)
            stdscr.addstr(status_y, fx, footer[:width - 3], base)
        except curses.error:
            pass

        if menu_open >= 0:
            _draw_open_menu(stdscr, menu_open, width, menu_selected)
        stdscr.refresh()
        return

    lines = visual_lines(document, text_width)
    n_lines = len(lines)

    sel_range = None
    if selection_start is not None and selection_end is not None:
        sel_range = selection_range(
            document, selection_start, selection_end
        )

    offsets = line_offsets(document)

    misspelled_set = set()
    if spell_positions:
        for s, e in spell_positions:
            for p in range(s, e):
                misspelled_set.add(p)

    spell_attr = 0
    if state.COLORS_READY:
        try:
            spell_attr = curses.color_pair(1)
        except Exception:
            spell_attr = 0

    for visual_row, (line_index, start, text) in enumerate(lines):
        screen_y = top + visual_row - scroll_row
        if screen_y < top or screen_y >= bottom:
            continue

        if visual_row == n_lines - 1:
            is_last_subline = True
        else:
            is_last_subline = lines[visual_row + 1][0] != line_index

        align = get_line_align(alignments, line_index)
        display_text, offset, mapping = compute_line_layout(
            text, text_width, align, is_last_subline
        )

        fmt_line = (formatting[line_index]
                    if line_index < len(formatting) else [])
        line_base = offsets[line_index] if line_index < len(offsets) else 0

        for i, char in enumerate(display_text):
            screen_x = text_x + offset + i
            if screen_x >= width - 1:
                break
            orig_col = start + (mapping[i] if mapping else i)

            if char == PAGE_BREAK:
                remaining = text_x + text_width - screen_x
                if remaining > 0:
                    try:
                        stdscr.addstr(screen_y, screen_x, "━" * remaining,
                                      _base_attr())
                    except curses.error:
                        pass
                break

            abs_col = line_base + orig_col

            selected = False
            if sel_range is not None:
                selected = sel_range[0] <= abs_col < sel_range[1]

            attrs = fmt_line[orig_col] if orig_col < len(fmt_line) else 0

            if spell_attr and abs_col in misspelled_set:
                if state.TTY_MODE:
                    cattr = curses.color_pair(1) | curses.A_UNDERLINE
                else:
                    cattr = spell_attr
                    if attrs & BOLD:
                        cattr |= curses.A_BOLD
                    if attrs & ITALIC:
                        cattr |= getattr(curses, "A_ITALIC", 0)
                    if attrs & UNDERLINE:
                        cattr |= curses.A_UNDERLINE
            else:
                cattr = _style_for_attrs(attrs)
                if not state.TTY_MODE:
                    heading_bits = attrs & HEADING_MASK
                    if heading_bits == H1:
                        cattr |= curses.A_BOLD | curses.A_UNDERLINE
                    elif heading_bits == H2:
                        cattr |= curses.A_BOLD
                    elif heading_bits == H3:
                        cattr |= curses.A_BOLD | getattr(
                            curses, "A_ITALIC", 0)

            if selected:
                cattr |= curses.A_REVERSE

            try:
                stdscr.addstr(screen_y, screen_x, char, cattr)
            except curses.error:
                pass

    cursor_row, cursor_subcol = cursor_visual_position(
        document, cursor_line, cursor_col, text_width
    )
    cursor_y = top + cursor_row - scroll_row

    if 0 <= cursor_row < n_lines:
        cl_line, cl_start, cl_text = lines[cursor_row]
        if cursor_row == n_lines - 1:
            is_last = True
        else:
            is_last = lines[cursor_row + 1][0] != cl_line

        cl_align = get_line_align(alignments, cl_line)
        _display_text, cl_offset, cl_mapping = compute_line_layout(
            cl_text, text_width, cl_align, is_last
        )

        if cl_mapping:
            display_pos = len(cl_mapping)
            for k, m in enumerate(cl_mapping):
                if m >= cursor_subcol:
                    display_pos = k
                    break
        else:
            display_pos = cursor_subcol

        cursor_screen_x = text_x + cl_offset + display_pos
    else:
        cursor_screen_x = text_x

    if top <= cursor_y < bottom and 0 <= cursor_screen_x < width:
        try:
            cursor_attr = curses.A_REVERSE | curses_attr_for(typing_attrs)
            if (cursor_line < len(document)
                    and cursor_col < len(document[cursor_line])):
                char = document[cursor_line][cursor_col]
                if char == PAGE_BREAK:
                    stdscr.addstr(cursor_y, cursor_screen_x, "━",
                                  cursor_attr)
                else:
                    stdscr.addstr(cursor_y, cursor_screen_x, char,
                                  cursor_attr)
            else:
                stdscr.addstr(cursor_y, cursor_screen_x, " ", cursor_attr)
            stdscr.move(cursor_y, cursor_screen_x)
        except curses.error:
            pass

    if mode in ("search", "replace_find", "replace_with", "save_as",
                "save_as_docx", "confirm_overwrite",
                "confirm_quit", "confirm_new", "confirm_open"):
        label = prompt_label
        text = label + " " + prompt_buffer
        try:
            stdscr.addstr(status_y, text_x, text[:text_width],
                          _base_attr())
        except curses.error:
            pass
        try:
            cursor_pos = min(
                text_x + len(label) + 1 + len(prompt_buffer),
                text_x + text_width - 1
            )
            stdscr.move(status_y, cursor_pos)
        except curses.error:
            pass

    elif export_animating:
        wc = count_words(document)
        left = tr("Palabras: %d") % wc
        if export_kind == "pdf":
            right = tr("Exportando a PDF… %s") % export_spinner
        else:
            right = tr("Guardando .docx… %s") % export_spinner

        try:
            stdscr.addstr(status_y, text_x, left[:text_width],
                          _base_attr())
        except curses.error:
            pass

        rx = text_x + text_width - len(right)
        min_rx = text_x + len(left) + 2
        if rx < min_rx:
            rx = min_rx
        max_len = text_x + text_width - rx
        if max_len > 0:
            try:
                stdscr.addstr(status_y, rx, right[:max_len],
                              _base_attr() | curses.A_BOLD)
            except curses.error:
                pass

    else:
        wc = count_words(document)
        left = tr("Palabras: %d") % wc
        right_parts = []

        indicators = []
        if typing_attrs & BOLD:
            indicators.append("B")
        if typing_attrs & ITALIC:
            indicators.append("I")
        if typing_attrs & UNDERLINE:
            indicators.append("U")
        if indicators:
            right_parts.append("[" + "".join(indicators) + "]")

        if search_active and search_matches:
            right_parts.append("%d/%d" % (search_index + 1,
                                          len(search_matches)))

        if spell_unavailable_msg:
            right_parts.append(spell_unavailable_msg)
        elif spell_suggestions:
            right_parts.append(
                tr("Ortografía: ") + ", ".join(spell_suggestions[:3])
            )
        elif spell_active:
            right_parts.append(tr("Ortografía ✓"))

        if status_message:
            right_parts.append(status_message)

        right = "  ·  ".join(right_parts)

        try:
            stdscr.addstr(status_y, text_x, left[:text_width],
                          _base_attr())
        except curses.error:
            pass

        if right:
            rx = text_x + text_width - len(right)
            min_rx = text_x + len(left) + 2
            if rx < min_rx:
                rx = min_rx
            max_len = text_x + text_width - rx
            if max_len > 0:
                try:
                    stdscr.addstr(status_y, rx, right[:max_len],
                                  _base_attr())
                except curses.error:
                    pass

    if menu_open >= 0:
        _draw_open_menu(stdscr, menu_open, width, menu_selected)

    if mode == "browse":
        draw_browser(
            stdscr, browse_dir, browse_entries,
            browse_index, browse_scroll, width, height
        )

    if mode == "chapters":
        draw_chapter_panel(
            stdscr,
            chapter_headings if chapter_headings else [],
            chapter_index,
            chapter_scroll,
            width, height
        )

    stdscr.refresh()


MENUS = [
    (tr("Archivo"), [
        (tr("Nuevo documento"),  "Ctrl+N", "NEW"),
        (tr("Abrir documento…"), "Ctrl+O", "OPEN"),
        None,
        (tr("Guardar"),          "Ctrl+S", "SAVE"),
        (tr("Guardar como…"),    "Ctrl+W", "SAVE_AS"),
        (tr("Guardar como .docx…"), "",    "SAVE_AS_DOCX"),
        (tr("Exportar a PDF"),   "Ctrl+P", "PDF"),
        None,
        (tr("Salir"),            "Ctrl+Q", "QUIT"),
    ]),
    (tr("Edición"), [
        (tr("Seleccionar todo"), "Ctrl+A", "SELECT_ALL"),
        None,
        (tr("Deshacer"),   "Ctrl+Z", "UNDO"),
        None,
        (tr("Copiar"),     "Ctrl+C", "COPY"),
        (tr("Cortar"),     "Ctrl+X", "CUT"),
        (tr("Pegar"),      "Ctrl+V", "PASTE"),
        None,
        (tr("Buscar"),     "Ctrl+F", "FIND"),
        (tr("Reemplazar"), "Ctrl+R", "REPLACE"),
        None,
        (tr("Corrector ortográfico"), "F7", "SPELL"),
    ]),
    (tr("Formato"), [
        (tr("Negrita"),   "Ctrl+B", "BOLD"),
        (tr("Cursiva"),   "Ctrl+I", "ITALIC"),
        (tr("Subrayado"), "Ctrl+U", "UNDERLINE"),
    ]),
    (tr("Alineación"), [
        (tr("Izquierda"),   "Ctrl+L", "ALIGN_LEFT"),
        (tr("Centrada"),    "Ctrl+E", "ALIGN_CENTER"),
        (tr("Derecha"),     "Ctrl+D", "ALIGN_RIGHT"),
        (tr("Justificada"), "Ctrl+J", "ALIGN_JUSTIFY"),
    ]),
    (tr("Capítulos"), [
        (tr("Crear capítulo"),   "F2", "H1"),
        (tr("Crear sección"),    "F3", "H2"),
        (tr("Crear subsección"), "F4", "H3"),
        (tr("Quitar nivel de título"), "F6", "H0"),
        None,
        (tr("Mapa de capítulos"),    "Ctrl+T", "CHAPTERS"),
        None,
        (tr("Salto de página"),      "Ctrl+K", "PAGEBREAK"),
    ]),
    (tr("Ayuda"), [
        (tr("Manual"),    "Ctrl+G", "HELP"),
        (tr("Acerca de"), "Ctrl+H", "ABOUT"),
    ]),
    (tr("Idioma"), [
        ("Español", "", "LANG_ES"),
        ("English", "", "LANG_EN"),
    ]),
    (tr("Salir"), None),
]

