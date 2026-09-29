"""Unsaved-changes confirmation for Quit / New / Open."""
import os
import time
from lightwrite.constants import ALIGN_LEFT
from lightwrite.i18n import tr
from lightwrite.prompts import CONFIRM_NEW, CONFIRM_OPEN, CONFIRM_QUIT, interpret_answer, is_confirm_mode
from lightwrite.ui_draw import list_directory

def handle_confirm_dirty(ed, event_type, value):
    if is_confirm_mode(ed.mode):
        if event_type == 'key':
            if value == 'ESC':
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
                ed.pending_quit = False
                ed.status_message = tr('Cancelado')
                ed.status_time = time.monotonic()
                ed.full_redraw = True
            elif value == 'ENTER':
                yes = interpret_answer(ed.prompt_buffer)
                action = ed.mode
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
                if yes:
                    if action == CONFIRM_QUIT:
                        return 'quit'
                    if action == CONFIRM_NEW:
                        ed.record_undo()
                        ed.document = ['']
                        ed.formatting = [[]]
                        ed.alignments = [ALIGN_LEFT]
                        ed.current_path = None
                        ed.cursor_line = ed.cursor_col = 0
                        ed.scroll_row = 0
                        ed.selection_start = None
                        ed.selection_end = None
                        ed.selecting = False
                        ed.search_active = False
                        ed.touch_document()
                        ed.doc_dirty = False
                        ed.status_message = tr('Nuevo documento')
                        ed.status_time = time.monotonic()
                    elif action == CONFIRM_OPEN:
                        if ed.current_path:
                            start_dir = os.path.dirname(os.path.abspath(ed.current_path))
                        else:
                            start_dir = os.path.expanduser('~/lightwrite')
                        if not os.path.isdir(start_dir):
                            start_dir = os.path.expanduser('~')
                        ed.browse_dir = start_dir
                        ed.browse_entries = list_directory(ed.browse_dir)
                        ed.browse_index = 0
                        ed.browse_scroll = 0
                        ed.mode = 'browse'
                    ed.pending_quit = False
                else:
                    ed.pending_quit = False
                    ed.status_message = tr('Cancelado')
                    ed.status_time = time.monotonic()
                ed.full_redraw = True
            elif value == 'BACKSPACE':
                ed.prompt_buffer = ed.prompt_buffer[:-1]
        elif event_type == 'char':
            if value and value != '\t':
                ch = value.lower()
                if ch in ('s', 'n', 'y'):
                    ed.prompt_buffer = ch
        return True
    return False
