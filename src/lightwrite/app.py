import curses
import os
import select
import sys
import time

from lightwrite import profile
from lightwrite.constants import (
    ALIGN_LEFT, SPINNER_FRAMES, STATUS_DURATION, TEXT_TOP, TEXT_WIDTH,
)
from lightwrite.document_io import load_document
from lightwrite.export import poll_docx_save, poll_pdf_export
from lightwrite.handlers.browse import handle_browse
from lightwrite.handlers.chapters import handle_chapters
from lightwrite.handlers.confirm_dirty import handle_confirm_dirty
from lightwrite.handlers.confirm_overwrite import handle_confirm_overwrite
from lightwrite.handlers.help_about import handle_help_about
from lightwrite.handlers.keys import handle_keys
from lightwrite.handlers.mouse import handle_mouse
from lightwrite.handlers.save_as import handle_save_as
from lightwrite.handlers.search import handle_search
from lightwrite.handlers.typing import handle_typing
from lightwrite.i18n import current_language, tr
from lightwrite.input import (
    disable_mouse_tracking, enable_mouse_tracking, has_pending_input,
    read_input_event,
)
from lightwrite.layout import adjust_scroll, visual_lines
from lightwrite.model import position_to_absolute
from lightwrite.session import EditorState
from lightwrite.spell import get_suggestions, run_spell_check
from lightwrite.ui_draw import draw_editor, init_colors


def _dispatch(ed, event_type, value):
    """Run modal/input handlers. Return 'quit', True, or False."""
    for handler in (
        handle_chapters, handle_help_about, handle_browse,
        handle_save_as, handle_confirm_overwrite,
        handle_confirm_dirty, handle_search, handle_mouse,
        handle_keys, handle_typing,
    ):
        result = handler(ed, event_type, value)
        if result:
            return result
    return False


def editor(stdscr, initial_path=None):
    curses.raw()
    curses.noecho()
    curses.curs_set(1)
    curses.mousemask(0)
    enable_mouse_tracking()

    init_colors()

    if initial_path:
        document, formatting, alignments = load_document(initial_path)
    else:
        document = [""]
        formatting = [[]]
        alignments = [ALIGN_LEFT]

    ed = EditorState(document, formatting, alignments, initial_path)

    try:
        while True:
            if ed.export_state is not None:
                if ed.export_kind == 'pdf':
                    done, success, message = poll_pdf_export(ed.export_state)
                else:
                    done, success, message = poll_docx_save(ed.export_state)
                if done:
                    if ed.export_kind == 'docx' and success:
                        ed.doc_dirty = False
                    ed.export_state = None
                    ed.export_kind = None
                    ed.export_frames = 0
                    ed.status_message = message
                    ed.status_time = time.monotonic()
                else:
                    ed.export_frames = (ed.export_frames + 1) % len(SPINNER_FRAMES)
            ed.height, ed.width = stdscr.getmaxyx()
            ed.top = TEXT_TOP
            ed.bottom = ed.height - 2
            if ed.bottom <= ed.top:
                ed.bottom = ed.top + 1
            ed.text_width = min(TEXT_WIDTH, max(1, ed.width - 4))
            ed.text_x = max(2, (ed.width - ed.text_width) // 2)
            ed.visible_rows = max(1, ed.bottom - ed.top)
            if ed.spell_check_active:
                cur_str = ed.plain_cache.get(ed.document)
                if cur_str != ed.last_spell_doc_str:
                    ed.spell_dirty = True
                    ed.spell_last_change = time.monotonic()
                    ed.last_spell_doc_str = cur_str
                if ed.spell_dirty and time.monotonic() - ed.spell_last_change > 0.5:
                    with profile.span('spell'):
                        positions = run_spell_check(cur_str, current_language())
                    if positions is None:
                        ed.spell_positions = []
                        ed.spell_unavailable_msg = tr('hunspell no instalado')
                        ed.spell_check_active = False
                    else:
                        ed.spell_positions = positions
                        ed.spell_unavailable_msg = ''
                    ed.spell_dirty = False
            ed.spell_suggestions = []
            if ed.spell_check_active and ed.spell_positions:
                doc_str_now = ed.plain_cache.get(ed.document)
                cursor_abs = position_to_absolute(ed.document, ed.cursor_line, ed.cursor_col)
                for s, e in ed.spell_positions:
                    if s <= cursor_abs < e:
                        word = doc_str_now[s:e]
                        key = (word, current_language())
                        if key in ed.spell_suggest_cache:
                            ed.spell_suggestions = ed.spell_suggest_cache[key]
                        else:
                            ed.spell_suggestions = get_suggestions(word, current_language())
                            ed.spell_suggest_cache[key] = ed.spell_suggestions
                        break
            force_draw = ed.export_state is not None
            if force_draw or not has_pending_input(0, 0):
                if ed.auto_scroll:
                    ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
                else:
                    total_rows = len(visual_lines(ed.document, ed.text_width))
                    max_scroll = max(0, total_rows - ed.visible_rows)
                    ed.scroll_row = max(0, min(ed.scroll_row, max_scroll))
                if ed.status_message and time.monotonic() - ed.status_time > STATUS_DURATION:
                    ed.status_message = ''
                if ed.current_path:
                    window_title = 'LIGHTWRITE  ·  ' + os.path.basename(ed.current_path)
                else:
                    window_title = 'LIGHTWRITE'
                with profile.span('redraw'):
                    draw_editor(stdscr, ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col, ed.selection_start, ed.selection_end, ed.scroll_row, ed.status_message, ed.typing_attrs, window_title, ed.mode, ed.prompt_buffer, ed.prompt_label, ed.help_scroll, ed.search_active, ed.search_matches, ed.search_index, ed.menu_open, ed.menu_selected, ed.browse_dir, ed.browse_entries, ed.browse_index, ed.browse_scroll, ed.export_state is not None, SPINNER_FRAMES[ed.export_frames], ed.export_kind, ed.spell_positions, ed.spell_suggestions, ed.spell_unavailable_msg, ed.spell_check_active, ed.chapter_headings, ed.chapter_index, ed.chapter_scroll, full_redraw=ed.full_redraw)
                ed.full_redraw = False
            input_timeout = None
            if ed.export_state is not None:
                input_timeout = 0.12
            elif ed.spell_check_active and ed.spell_dirty:
                input_timeout = 0.1
            if input_timeout is not None:
                r, _w, _x = select.select([0], [], [], input_timeout)
                if not r:
                    continue
            if ed.pending_key is not None:
                event_type = 'key'
                value = ed.pending_key
                ed.pending_key = None
            else:
                event = read_input_event(0)
                if event is None:
                    continue
                event_type, value = event
            if event_type == 'mouse' and ed.mode in ('search', 'replace_find', 'replace_with', 'save_as', 'save_as_docx', 'confirm_overwrite', 'confirm_quit', 'confirm_new', 'confirm_open'):
                button, mx, my, action = value
                if button == 0 and action == 'M':
                    ed.mode = 'normal'
                    ed.prompt_buffer = ''
                    ed.prompt_label = ''
                    ed.pending_overwrite_path = ''
                    ed.pending_quit = False
                    ed.full_redraw = True
            result = _dispatch(ed, event_type, value)
            if result == "quit":
                break
            # Handled or not, the next while-iteration redraws.
            continue

    finally:
        profile.dump()
        if ed.export_state is not None:
            try:
                ed.export_state["proc"].terminate()
            except Exception:
                pass
        disable_mouse_tracking()


def main():
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]

    try:
        curses.wrapper(lambda stdscr: editor(stdscr, path))
    except KeyboardInterrupt:
        pass
