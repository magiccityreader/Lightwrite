"""Menu-bar keyboard navigation."""
from __future__ import annotations
from lightwrite.ui_draw import MENUS

def handle_menu_keys(ed, value):
    if value == 'MENU':
        if ed.menu_open >= 0:
            ed.full_redraw = True
            ed.menu_open = -1
        else:
            n = len(MENUS)
            idx = 0
            while idx < n and MENUS[idx][1] is None:
                idx += 1
            if idx < n:
                ed.full_redraw = True
                ed.menu_open = idx
                ed.menu_selected = 0
                items = MENUS[idx][1]
                while ed.menu_selected < len(items) and items[ed.menu_selected] is None:
                    ed.menu_selected += 1
        return True
    if ed.menu_open >= 0:
        if value == 'ESC':
            ed.full_redraw = True
            ed.menu_open = -1
        elif value == 'LEFT':
            n = len(MENUS)
            for i in range(1, n + 1):
                idx = (ed.menu_open - i) % n
                if MENUS[idx][1] is not None:
                    ed.full_redraw = True
                    ed.menu_open = idx
                    ed.menu_selected = 0
                    items = MENUS[idx][1]
                    while ed.menu_selected < len(items) and items[ed.menu_selected] is None:
                        ed.menu_selected += 1
                    break
        elif value == 'RIGHT':
            n = len(MENUS)
            for i in range(1, n + 1):
                idx = (ed.menu_open + i) % n
                if MENUS[idx][1] is not None:
                    ed.full_redraw = True
                    ed.menu_open = idx
                    ed.menu_selected = 0
                    items = MENUS[idx][1]
                    while ed.menu_selected < len(items) and items[ed.menu_selected] is None:
                        ed.menu_selected += 1
                    break
        elif value == 'UP':
            items = MENUS[ed.menu_open][1]
            idx = ed.menu_selected - 1
            while idx >= 0 and items[idx] is None:
                idx -= 1
            if idx >= 0:
                ed.menu_selected = idx
        elif value == 'DOWN':
            items = MENUS[ed.menu_open][1]
            idx = ed.menu_selected + 1
            while idx < len(items) and items[idx] is None:
                idx += 1
            if idx < len(items):
                ed.menu_selected = idx
        elif value == 'ENTER':
            items = MENUS[ed.menu_open][1]
            if items and 0 <= ed.menu_selected < len(items):
                item = items[ed.menu_selected]
                if item is not None:
                    action_key = item[2]
                    ed.full_redraw = True
                    ed.menu_open = -1
                    ed.pending_key = action_key
                    return True
        return True
    return False
