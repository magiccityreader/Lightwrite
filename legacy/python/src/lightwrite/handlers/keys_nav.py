"""Cursor movement, selection and view modes."""
from __future__ import annotations
from lightwrite.layout import adjust_scroll
from lightwrite.model import collect_headings, move_down, move_left, move_right, move_up
from lightwrite.ui_draw import chapter_panel_geometry

def handle_nav_keys(ed, value):
    if value == 'HELP':
        ed.mode = 'help'
        ed.help_scroll = 0
        return True
    elif value == 'ABOUT':
        ed.mode = 'about'
        ed.help_scroll = 0
        return True
    elif value == 'CHAPTERS':
        ed.chapter_headings = collect_headings(ed.document, ed.formatting)
        ed.chapter_index = 0
        ed.chapter_scroll = 0
        for k, (ln, _lvl, _t) in enumerate(ed.chapter_headings):
            if ln >= ed.cursor_line:
                ed.chapter_index = k
                break
        else:
            if ed.chapter_headings:
                ed.chapter_index = len(ed.chapter_headings) - 1
        _bx, _by, _bw, _bh, _ls, _lh = chapter_panel_geometry(ed.width, ed.height)
        if ed.chapter_index >= ed.chapter_scroll + _lh:
            ed.chapter_scroll = max(0, ed.chapter_index - _lh + 1)
        ed.mode = 'chapters'
        return True
    elif value in ('SELECT_LEFT', 'SELECT_RIGHT', 'SELECT_UP', 'SELECT_DOWN', 'SELECT_HOME', 'SELECT_END', 'SELECT_PAGE_UP', 'SELECT_PAGE_DOWN'):
        if ed.selection_start is None:
            ed.selection_start = (ed.cursor_line, ed.cursor_col)
        if value == 'SELECT_LEFT':
            ed.cursor_line, ed.cursor_col = move_left(ed.document, ed.cursor_line, ed.cursor_col)
        elif value == 'SELECT_RIGHT':
            ed.cursor_line, ed.cursor_col = move_right(ed.document, ed.cursor_line, ed.cursor_col)
        elif value == 'SELECT_UP':
            ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        elif value == 'SELECT_DOWN':
            ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        elif value == 'SELECT_HOME':
            ed.cursor_col = 0
        elif value == 'SELECT_END':
            ed.cursor_col = len(ed.document[ed.cursor_line])
        elif value == 'SELECT_PAGE_UP':
            for _ in range(ed.visible_rows):
                ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        elif value == 'SELECT_PAGE_DOWN':
            for _ in range(ed.visible_rows):
                ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        ed.selection_end = (ed.cursor_line, ed.cursor_col)
        if ed.selection_start == ed.selection_end:
            ed.selection_start = None
            ed.selection_end = None
        ed.auto_scroll = True
        ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
        return True
    elif value == 'LEFT':
        ed.cursor_line, ed.cursor_col = move_left(ed.document, ed.cursor_line, ed.cursor_col)
        return True
    elif value == 'RIGHT':
        ed.cursor_line, ed.cursor_col = move_right(ed.document, ed.cursor_line, ed.cursor_col)
        return True
    elif value == 'UP':
        ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        return True
    elif value == 'DOWN':
        ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        return True
    return False
