"""Keyboard shortcut dispatcher."""
from __future__ import annotations

import time

from lightwrite import state
from lightwrite.handlers.keys_edit import handle_edit_keys
from lightwrite.handlers.keys_file import handle_file_keys, handle_new_open
from lightwrite.handlers.keys_format import handle_format_keys
from lightwrite.handlers.keys_menu import handle_menu_keys
from lightwrite.handlers.keys_nav import handle_nav_keys
from lightwrite.i18n import tr
from lightwrite.layout import adjust_scroll


def handle_keys(ed, event_type, value):
    if event_type != "key":
        return False

    ed.auto_scroll = True

    if handle_menu_keys(ed, value):
        return True
    if handle_new_open(ed, value):
        return True

    if ed.search_active and value != "ENTER":
        ed.search_active = False
    if value == "ENTER" and ed.search_active and ed.search_matches:
        ed.search_index = (ed.search_index + 1) % len(ed.search_matches)
        result = ed.search_matches[ed.search_index]
        ed.cursor_line, ed.cursor_col = result
        ed.selection_start = result
        ed.selection_end = (result[0], result[1] + len(ed.search_term))
        ed.status_message = "%d/%d" % (
            ed.search_index + 1, len(ed.search_matches))
        ed.status_time = time.monotonic()
        ed.scroll_row = adjust_scroll(
            ed.document, ed.cursor_line, ed.cursor_col,
            ed.text_width, ed.visible_rows, ed.scroll_row)
        return True

    if value == "MARK" and state.TTY_MODE:
        if ed.selecting:
            ed.selecting = False
            ed.status_message = tr("Selección terminada")
        else:
            ed.selection_start = (ed.cursor_line, ed.cursor_col)
            ed.selection_end = (ed.cursor_line, ed.cursor_col)
            ed.selecting = True
            ed.status_message = tr("Selección iniciada")
        ed.status_time = time.monotonic()
        return True

    for handler in (
        handle_file_keys, handle_format_keys, handle_edit_keys, handle_nav_keys,
    ):
        result = handler(ed, value)
        if result:
            if value in ("LEFT", "RIGHT", "UP", "DOWN"):
                if ed.selecting and state.TTY_MODE:
                    ed.selection_end = (ed.cursor_line, ed.cursor_col)
                else:
                    ed.selection_start = None
                    ed.selection_end = None
            elif value in ("BACKSPACE", "DELETE", "ENTER"):
                ed.selection_start = None
                ed.selection_end = None
                ed.selecting = False
            ed.scroll_row = adjust_scroll(
                ed.document, ed.cursor_line, ed.cursor_col,
                ed.text_width, ed.visible_rows, ed.scroll_row)
            return result

    # Unrecognized key: still consume it (matches prior continue-always).
    return True
