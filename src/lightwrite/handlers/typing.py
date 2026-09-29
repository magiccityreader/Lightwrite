"""Plain character insertion (typing path)."""
from lightwrite.constants import ALIGN_LEFT
from lightwrite.layout import adjust_scroll
from lightwrite.model import delete_selection_rich, insert_character_rich

def handle_typing(ed, event_type, value):
    if event_type == 'char':
        if ed.menu_open >= 0:
            return True
        char = value
        insert_line, insert_col = (ed.cursor_line, ed.cursor_col)
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.document, ed.formatting, ed.alignments, ed.cursor_line, ed.cursor_col = delete_selection_rich(ed.document, ed.formatting, ed.alignments, ed.selection_start, ed.selection_end)
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
            insert_line, insert_col = (ed.cursor_line, ed.cursor_col)
        old_scroll = ed.scroll_row
        ed.document, ed.formatting, ed.cursor_line, ed.cursor_col = insert_character_rich(ed.document, ed.formatting, ed.cursor_line, ed.cursor_col, char, ed.typing_attrs)
        ed.record_insert(insert_line, insert_col, char)
        while len(ed.alignments) < len(ed.document):
            ed.alignments.append(ALIGN_LEFT)
        ed.alignments = ed.alignments[:len(ed.document)]
        ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
        if ed.scroll_row != old_scroll:
            ed.full_redraw = True
    return False
