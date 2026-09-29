"""Mouse event handlers (menus, selection, chapters)."""
from lightwrite.layout import mouse_to_document_position
from lightwrite.ui_draw import MENUS, dropdown_item_at, dropdown_x, menu_bar_layout, menu_index_at
from lightwrite.constants import DROPDOWN_ROW, MENU_ROW
from lightwrite.layout import visual_lines

def handle_mouse(ed, event_type, value):
    if event_type == 'mouse':
        button, mouse_x, mouse_y, action = value
        if action == 'M' and button == 64:
            ed.scroll_row = max(0, ed.scroll_row - ed.SCROLL_LINES)
            ed.auto_scroll = False
            return True
        if action == 'M' and button == 65:
            total_rows = len(visual_lines(ed.document, ed.text_width))
            max_scroll = max(0, total_rows - ed.visible_rows)
            ed.scroll_row = min(max_scroll, ed.scroll_row + ed.SCROLL_LINES)
            ed.auto_scroll = False
            return True
        if button == 0 and action == 'M':
            if mouse_y == MENU_ROW:
                idx = menu_index_at(MENUS, mouse_x, ed.width)
                if idx >= 0:
                    name, items = MENUS[idx]
                    if items is None:
                        ed.full_redraw = True
                        ed.menu_open = -1
                        ed.pending_key = 'QUIT'
                    elif ed.menu_open == idx:
                        ed.full_redraw = True
                        ed.menu_open = -1
                    else:
                        ed.full_redraw = True
                        ed.menu_open = idx
                else:
                    ed.full_redraw = True
                    ed.menu_open = -1
                return True
            if ed.menu_open >= 0:
                _name, items = MENUS[ed.menu_open]
                if items is not None:
                    layout = menu_bar_layout(MENUS, ed.width)
                    menu_label_x = layout[ed.menu_open][1]
                    dx = dropdown_x(items, menu_label_x, ed.width)
                    item_idx = dropdown_item_at(items, mouse_x, mouse_y, dx, DROPDOWN_ROW)
                    if item_idx >= 0:
                        item = items[item_idx]
                        action_key = item[2]
                        ed.full_redraw = True
                        ed.menu_open = -1
                        ed.pending_key = action_key
                        return True
                ed.full_redraw = True
                ed.menu_open = -1
                return True
            ed.auto_scroll = True
            position = mouse_to_document_position(mouse_x, mouse_y, ed.document, ed.alignments, ed.text_width, ed.scroll_row, ed.top, ed.bottom, ed.text_x)
            if position is None:
                return True
            line, col = position
            ed.cursor_line = line
            ed.cursor_col = col
            ed.selection_start = (ed.cursor_line, ed.cursor_col)
            ed.selection_end = (ed.cursor_line, ed.cursor_col)
            ed.selecting = True
            ed.search_active = False
        elif button >= 32 and button < 64 and (action == 'M') and ed.selecting:
            ed.auto_scroll = True
            if mouse_y >= ed.bottom - 1:
                total_rows = len(visual_lines(ed.document, ed.text_width))
                max_scroll = max(0, total_rows - ed.visible_rows)
                if ed.scroll_row < max_scroll:
                    ed.scroll_row += 1
            elif mouse_y <= ed.top:
                if ed.scroll_row > 0:
                    ed.scroll_row -= 1
            position = mouse_to_document_position(mouse_x, mouse_y, ed.document, ed.alignments, ed.text_width, ed.scroll_row, ed.top, ed.bottom, ed.text_x)
            if position is not None:
                line, col = position
                ed.cursor_line = line
                ed.cursor_col = col
                ed.selection_end = (ed.cursor_line, ed.cursor_col)
        elif action == 'm' and ed.selecting:
            ed.auto_scroll = True
            position = mouse_to_document_position(mouse_x, mouse_y, ed.document, ed.alignments, ed.text_width, ed.scroll_row, ed.top, ed.bottom, ed.text_x)
            if position is not None:
                line, col = position
                ed.cursor_line = line
                ed.cursor_col = col
                ed.selection_end = (ed.cursor_line, ed.cursor_col)
            ed.selecting = False
            if ed.selection_start == ed.selection_end:
                ed.selection_start = None
                ed.selection_end = None
        return True
    return False
