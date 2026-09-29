"""Find / replace prompt handlers."""
import time
from lightwrite.constants import ALIGN_LEFT
from lightwrite.i18n import tr
from lightwrite.model import find_all, position_to_absolute, replace_all

def handle_search(ed, event_type, value):
    if ed.mode in ('search', 'replace_find', 'replace_with'):
        if event_type == 'key':
            if value == 'ESC':
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
            elif value == 'BACKSPACE':
                ed.prompt_buffer = ed.prompt_buffer[:-1]
            elif value == 'ENTER':
                if ed.mode == 'search':
                    ed.search_term = ed.prompt_buffer
                    ed.prompt_buffer = ''
                    ed.prompt_label = ''
                    ed.mode = 'normal'
                    if ed.search_term:
                        ed.search_matches = find_all(ed.document, ed.search_term)
                        if ed.search_matches:
                            current_abs = position_to_absolute(ed.document, ed.cursor_line, ed.cursor_col)
                            start_idx = 0
                            for idx, (l, c) in enumerate(ed.search_matches):
                                m_abs = position_to_absolute(ed.document, l, c)
                                if m_abs > current_abs:
                                    start_idx = idx
                                    break
                            ed.search_index = start_idx
                            result = ed.search_matches[ed.search_index]
                            ed.cursor_line, ed.cursor_col = result
                            ed.selection_start = result
                            ed.selection_end = (result[0], result[1] + len(ed.search_term))
                            ed.search_active = True
                            ed.auto_scroll = True
                            ed.status_message = '%d/%d' % (ed.search_index + 1, len(ed.search_matches))
                        else:
                            ed.search_matches = []
                            ed.search_active = False
                            ed.status_message = tr('No encontrado')
                        ed.status_time = time.monotonic()
                elif ed.mode == 'replace_find':
                    ed.search_term = ed.prompt_buffer
                    ed.prompt_buffer = ed.replace_term
                    ed.prompt_label = tr('Reemplazar con:')
                    ed.mode = 'replace_with'
                elif ed.mode == 'replace_with':
                    ed.replace_term = ed.prompt_buffer
                    ed.prompt_buffer = ''
                    ed.prompt_label = ''
                    ed.mode = 'normal'
                    if ed.search_term:
                        ed.record_undo()
                        ed.document, ed.formatting, count = replace_all(ed.document, ed.formatting, ed.search_term, ed.replace_term)
                        while len(ed.alignments) < len(ed.document):
                            ed.alignments.append(ALIGN_LEFT)
                        ed.alignments = ed.alignments[:len(ed.document)]
                        if count == 1:
                            ed.status_message = tr('1 reemplazo')
                        elif count > 1:
                            ed.status_message = tr('%d reemplazos') % count
                        else:
                            ed.status_message = tr('No encontrado')
                        ed.status_time = time.monotonic()
                        if ed.document:
                            ed.cursor_line = min(ed.cursor_line, len(ed.document) - 1)
                            ed.cursor_col = min(ed.cursor_col, len(ed.document[ed.cursor_line]))
                        ed.auto_scroll = True
        elif event_type == 'char':
            if value and value != '\t':
                ed.prompt_buffer += value
        return True
    return False
