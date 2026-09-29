"""Clipboard, undo, find/replace and text edits."""
from __future__ import annotations
import time
from lightwrite.constants import ALIGN_LEFT
from lightwrite.i18n import tr
from lightwrite.model import cells_to_text, count_words, delete_at_cursor_rich, delete_before_cursor_rich, delete_selection_rich, enter_rich, get_system_clipboard, insert_cells_at_cursor, insert_page_break_rich, selected_cells, set_system_clipboard, text_to_cells
from lightwrite.undo import apply_undo
import lightwrite.model as model_mod

def handle_edit_keys(ed, value):
    if value == 'SELECT_ALL':
        if ed.document:
            last_line = len(ed.document) - 1
            ed.selection_start = (0, 0)
            ed.selection_end = (last_line, len(ed.document[last_line]))
            ed.cursor_line = last_line
            ed.cursor_col = len(ed.document[last_line])
            n_lines = len(ed.document)
            wc = count_words(ed.document)
            ed.status_message = tr('Seleccionado todo: %d líneas · %d palabras') % (n_lines, wc)
            ed.status_time = time.monotonic()
        return True
    elif value == 'UNDO':
        restored = apply_undo(ed.undo_stack, ed.document, ed.formatting, ed.alignments)
        if restored is not None:
            ed.document, ed.formatting, ed.alignments = restored
            if ed.cursor_line >= len(ed.document):
                ed.cursor_line = max(0, len(ed.document) - 1)
            if ed.cursor_col > len(ed.document[ed.cursor_line]):
                ed.cursor_col = len(ed.document[ed.cursor_line])
            while len(ed.alignments) < len(ed.document):
                ed.alignments.append(ALIGN_LEFT)
            ed.alignments = ed.alignments[:len(ed.document)]
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
            ed.search_active = False
            ed.touch_document()
            ed.doc_dirty = True
            ed.full_redraw = True
            ed.status_message = tr('Deshecho')
        else:
            ed.status_message = tr('Nada que deshacer')
        ed.status_time = time.monotonic()
        return True
    elif value == 'PAGEBREAK':
        ed.record_undo()
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
        ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = insert_page_break_rich(ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col)
        ed.status_message = tr('Salto de página')
        ed.status_time = time.monotonic()
        return True
    elif value == 'FIND':
        ed.mode = 'search'
        ed.prompt_label = tr('Buscar:')
        ed.prompt_buffer = ed.search_term
        return True
    elif value == 'REPLACE':
        ed.mode = 'replace_find'
        ed.prompt_label = tr('Buscar:')
        ed.prompt_buffer = ed.search_term
        return True
    elif value == 'COPY':
        cells = selected_cells(ed.document, ed.formatting, ed.selection_start, ed.selection_end)
        if cells:
            model_mod.internal_rich_clipboard = cells
            set_system_clipboard(cells_to_text(cells))
            ed.status_message = tr('Copiado')
            ed.status_time = time.monotonic()
        return True
    elif value == 'CUT':
        cells = selected_cells(ed.document, ed.formatting, ed.selection_start, ed.selection_end)
        if cells:
            ed.record_undo()
            model_mod.internal_rich_clipboard = cells
            set_system_clipboard(cells_to_text(cells))
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
            ed.status_message = tr('Cortado')
            ed.status_time = time.monotonic()
        return True
    elif value == 'PASTE':
        plain = get_system_clipboard()
        rich_plain = cells_to_text(model_mod.internal_rich_clipboard)
        if model_mod.internal_rich_clipboard and plain == rich_plain:
            paste_cells = list(model_mod.internal_rich_clipboard)
        else:
            paste_cells = text_to_cells(plain, ed.typing_attrs)
        if paste_cells:
            ed.record_undo()
            if ed.selection_start is not None and ed.selection_end is not None:
                ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
                ed.selection_start = None
                ed.selection_end = None
                ed.selecting = False
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = insert_cells_at_cursor(ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col, paste_cells)
            ed.status_message = tr('Pegado')
            ed.status_time = time.monotonic()
        return True
    elif value == 'BACKSPACE':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
        else:
            ed.record_undo(max(0, ed.cursor_line - 1), ed.cursor_line + 1)
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_before_cursor_rich(ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col)
        return True
    elif value == 'DELETE':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
        else:
            ed.record_undo(ed.cursor_line, ed.cursor_line + 2)
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_at_cursor_rich(ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col)
        return True
    elif value == 'ENTER':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
        else:
            ed.record_undo(ed.cursor_line, ed.cursor_line + 1)
        ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = enter_rich(ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col)
        return True
    return False
