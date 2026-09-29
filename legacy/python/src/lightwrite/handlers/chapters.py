"""Chapter-map modal handlers."""
import time
from lightwrite.constants import ALIGN_LEFT, H1
from lightwrite.i18n import tr
from lightwrite.ui_draw import chapter_panel_geometry
from lightwrite.layout import adjust_scroll

def handle_chapters(ed, event_type, value):
    if ed.mode == 'chapters':
        _bx, _by, _bw, _bh, _ls, _lh = chapter_panel_geometry(ed.width, ed.height)
        if event_type == 'key':
            if value in ('ESC', 'QUIT'):
                ed.mode = 'normal'
            elif value == 'UP':
                if ed.chapter_index > 0:
                    ed.chapter_index -= 1
            elif value == 'DOWN':
                if ed.chapter_index < len(ed.chapter_headings) - 1:
                    ed.chapter_index += 1
            elif value == 'PAGE_UP':
                ed.chapter_index = max(0, ed.chapter_index - _lh)
            elif value == 'PAGE_DOWN':
                ed.chapter_index = min(max(0, len(ed.chapter_headings) - 1), ed.chapter_index + _lh)
            elif value == 'HOME':
                ed.chapter_index = 0
            elif value == 'END':
                ed.chapter_index = max(0, len(ed.chapter_headings) - 1)
            elif value == 'ENTER':
                if 0 <= ed.chapter_index < len(ed.chapter_headings):
                    line_index, _lvl, txt = ed.chapter_headings[ed.chapter_index]
                    ed.record_undo()
                    ed.cursor_line = line_index
                    ed.cursor_col = 0
                    ed.selection_start = None
                    ed.selection_end = None
                    ed.selecting = False
                    ed.search_active = False
                    ed.auto_scroll = True
                    ed.mode = 'normal'
                    ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
                    ed.status_message = tr('Saltado a: %s') % txt
                    ed.status_time = time.monotonic()
            elif value == 'CHAPTERS':
                ed.mode = 'normal'
            elif len(value) == 1 and value.lower() == 'n':
                ed.record_undo()
                new_title = tr('Nuevo capítulo')
                if ed.document and ed.document[-1] != '':
                    ed.document.append('')
                    ed.formatting.append([])
                    ed.alignments.append(ALIGN_LEFT)
                if ed.document[-1] == '':
                    idx = len(ed.document) - 1
                else:
                    ed.document.append('')
                    ed.formatting.append([])
                    ed.alignments.append(ALIGN_LEFT)
                    idx = len(ed.document) - 1
                ed.document[idx] = new_title
                ed.formatting[idx] = [H1] * len(new_title)
                while len(ed.alignments) < len(ed.document):
                    ed.alignments.append(ALIGN_LEFT)
                ed.alignments = ed.alignments[:len(ed.document)]
                ed.cursor_line = idx
                ed.cursor_col = 0
                ed.selection_start = (idx, 0)
                ed.selection_end = (idx, len(new_title))
                ed.selecting = False
                ed.search_active = False
                ed.auto_scroll = True
                ed.mode = 'normal'
                ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
                ed.status_message = tr('Nuevo capítulo')
                ed.status_time = time.monotonic()
            if ed.chapter_index < ed.chapter_scroll:
                ed.chapter_scroll = ed.chapter_index
            elif ed.chapter_index >= ed.chapter_scroll + _lh:
                ed.chapter_scroll = ed.chapter_index - _lh + 1
            if ed.chapter_scroll < 0:
                ed.chapter_scroll = 0
        elif event_type == 'mouse':
            button, mx, my, action = value
            if action == 'M' and button == 64:
                ed.chapter_scroll = max(0, ed.chapter_scroll - 3)
                return True
            if action == 'M' and button == 65:
                max_scroll = max(0, len(ed.chapter_headings) - _lh)
                ed.chapter_scroll = min(max_scroll, ed.chapter_scroll + 3)
                return True
            if button == 0 and action == 'M':
                list_x = _bx + 2
                list_w = _bw - 4
                if list_x <= mx < list_x + list_w and _ls <= my < _ls + _lh:
                    clicked_row = my - _ls
                    clicked_idx = ed.chapter_scroll + clicked_row
                    if 0 <= clicked_idx < len(ed.chapter_headings):
                        if clicked_idx == ed.chapter_index:
                            line_index, _lvl, txt = ed.chapter_headings[clicked_idx]
                            ed.record_undo()
                            ed.cursor_line = line_index
                            ed.cursor_col = 0
                            ed.selection_start = None
                            ed.selection_end = None
                            ed.selecting = False
                            ed.search_active = False
                            ed.auto_scroll = True
                            ed.mode = 'normal'
                            ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
                            ed.status_message = tr('Saltado a: %s') % txt
                            ed.status_time = time.monotonic()
                        else:
                            ed.chapter_index = clicked_idx
            if ed.chapter_index < ed.chapter_scroll:
                ed.chapter_scroll = ed.chapter_index
            elif ed.chapter_index >= ed.chapter_scroll + _lh:
                ed.chapter_scroll = ed.chapter_index - _lh + 1
            if ed.chapter_scroll < 0:
                ed.chapter_scroll = 0
        return True
    return False
