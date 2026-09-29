"""Help and About modal handlers."""
from lightwrite.constants import DROPDOWN_ROW, MENU_ROW
from lightwrite.ui_draw import MENUS, dropdown_item_at, dropdown_x, menu_bar_layout, menu_index_at

def handle_help_about(ed, event_type, value):
    if ed.mode in ('help', 'about'):
        if event_type == 'key':
            if value in ('ESC', 'QUIT', 'HELP', 'ABOUT'):
                if ed.menu_open >= 0:
                    ed.full_redraw = True
                    ed.menu_open = -1
                else:
                    ed.mode = 'normal'
                    ed.help_scroll = 0
            elif value == 'UP':
                ed.help_scroll = max(0, ed.help_scroll - 1)
            elif value == 'DOWN':
                ed.help_scroll += 1
            elif value == 'PAGE_UP':
                ed.help_scroll = max(0, ed.help_scroll - ed.visible_rows)
            elif value == 'PAGE_DOWN':
                ed.help_scroll += ed.visible_rows
        elif event_type == 'mouse':
            button, mx, my, action = value
            if button == 0 and action == 'M':
                idx = menu_index_at(MENUS, mx, ed.width)
                if my == MENU_ROW and idx >= 0:
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
                    return True
                if ed.menu_open >= 0:
                    _name, items = MENUS[ed.menu_open]
                    if items is not None:
                        layout = menu_bar_layout(MENUS, ed.width)
                        menu_label_x = layout[ed.menu_open][1]
                        dx = dropdown_x(items, menu_label_x, ed.width)
                        item_idx = dropdown_item_at(items, mx, my, dx, DROPDOWN_ROW)
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
    return False
