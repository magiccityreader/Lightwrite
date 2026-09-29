"""File-browser modal handlers."""
import os
import time
from lightwrite.document_io import load_document
from lightwrite.i18n import tr
from lightwrite.ui_draw import browser_box_geometry, list_directory
from lightwrite.undo import push_undo

def handle_browse(ed, event_type, value):
    if ed.mode == 'browse':
        box_x, box_y, box_w, box_h = browser_box_geometry(ed.width, ed.height)
        list_x = box_x + 2
        list_y = box_y + 3
        list_w = box_w - 4
        list_h = box_h - 5
        if event_type == 'key':
            if value == 'ESC':
                ed.mode = 'normal'
                ed.browse_dir = ''
                ed.browse_entries = []
            elif value == 'UP':
                if ed.browse_index > 0:
                    ed.browse_index -= 1
            elif value == 'DOWN':
                if ed.browse_index < len(ed.browse_entries) - 1:
                    ed.browse_index += 1
            elif value == 'PAGE_UP':
                ed.browse_index = max(0, ed.browse_index - list_h)
            elif value == 'PAGE_DOWN':
                ed.browse_index = min(len(ed.browse_entries) - 1, ed.browse_index + list_h)
            elif value == 'HOME':
                ed.browse_index = 0
            elif value == 'END':
                ed.browse_index = max(0, len(ed.browse_entries) - 1)
            elif value == 'ENTER':
                if 0 <= ed.browse_index < len(ed.browse_entries):
                    name, full, is_dir = ed.browse_entries[ed.browse_index]
                    if is_dir:
                        ed.browse_dir = full
                        ed.browse_entries = list_directory(ed.browse_dir)
                        ed.browse_index = 0
                        ed.browse_scroll = 0
                    else:
                        push_undo(ed.undo_stack, ed.document, ed.formatting, ed.alignments)
                        ed.document, ed.formatting, ed.alignments = load_document(full)
                        ed.touch_document()
                        ed.current_path = full
                        ed.cursor_line = 0
                        ed.cursor_col = 0
                        ed.selection_start = None
                        ed.selection_end = None
                        ed.selecting = False
                        ed.search_active = False
                        ed.scroll_row = 0
                        ed.mode = 'normal'
                        ed.browse_dir = ''
                        ed.browse_entries = []
                        ed.status_message = tr('Abierto: %s') % os.path.basename(full)
                        ed.plain_cache.invalidate()
                        ed.doc_dirty = False
                        ed.full_redraw = True
                        ed.status_time = time.monotonic()
            elif value == 'BACKSPACE':
                parent = os.path.dirname(os.path.abspath(ed.browse_dir))
                if parent and parent != os.path.abspath(ed.browse_dir):
                    old_basename = os.path.basename(ed.browse_dir)
                    ed.browse_dir = parent
                    ed.browse_entries = list_directory(ed.browse_dir)
                    ed.browse_index = 0
                    for i, (nm, _full, is_dir) in enumerate(ed.browse_entries):
                        if is_dir and nm == old_basename:
                            ed.browse_index = i
                            break
                    ed.browse_scroll = 0
            elif len(value) == 1 and value.isprintable():
                start = ed.browse_index + 1
                n_entries = len(ed.browse_entries)
                for i in range(n_entries):
                    idx = (start + i) % n_entries
                    name = ed.browse_entries[idx][0]
                    if name.lower().startswith(value.lower()):
                        ed.browse_index = idx
                        break
            if ed.browse_index < ed.browse_scroll:
                ed.browse_scroll = ed.browse_index
            elif ed.browse_index >= ed.browse_scroll + list_h:
                ed.browse_scroll = ed.browse_index - list_h + 1
            if ed.browse_scroll < 0:
                ed.browse_scroll = 0
        elif event_type == 'mouse':
            button, mx, my, action = value
            if action == 'M' and button == 64:
                ed.browse_scroll = max(0, ed.browse_scroll - ed.SCROLL_LINES)
            elif action == 'M' and button == 65:
                max_scroll = max(0, len(ed.browse_entries) - list_h)
                ed.browse_scroll = min(max_scroll, ed.browse_scroll + ed.SCROLL_LINES)
            elif button == 0 and action == 'M':
                if list_x <= mx < list_x + list_w and list_y <= my < list_y + list_h:
                    clicked_row = my - list_y
                    clicked_idx = ed.browse_scroll + clicked_row
                    if 0 <= clicked_idx < len(ed.browse_entries):
                        if clicked_idx == ed.browse_index:
                            name, full, is_dir = ed.browse_entries[clicked_idx]
                            if is_dir:
                                ed.browse_dir = full
                                ed.browse_entries = list_directory(ed.browse_dir)
                                ed.browse_index = 0
                                ed.browse_scroll = 0
                            else:
                                push_undo(ed.undo_stack, ed.document, ed.formatting, ed.alignments)
                                ed.document, ed.formatting, ed.alignments = load_document(full)
                                ed.touch_document()
                                ed.current_path = full
                                ed.cursor_line = 0
                                ed.cursor_col = 0
                                ed.selection_start = None
                                ed.selection_end = None
                                ed.selecting = False
                                ed.search_active = False
                                ed.scroll_row = 0
                                ed.mode = 'normal'
                                ed.browse_dir = ''
                                ed.browse_entries = []
                                ed.status_message = tr('Abierto: %s') % os.path.basename(full)
                                ed.plain_cache.invalidate()
                                ed.doc_dirty = False
                                ed.full_redraw = True
                                ed.status_time = time.monotonic()
                        else:
                            ed.browse_index = clicked_idx
        return True
    return False
