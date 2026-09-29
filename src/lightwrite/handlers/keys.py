"""Keyboard shortcut handlers (menus, editing, navigation)."""
import os
import sys
import time
from lightwrite import state
from lightwrite.constants import ALIGN_CENTER, ALIGN_JUSTIFY, ALIGN_LEFT, ALIGN_RIGHT, BOLD, ITALIC, SESSION_RTF, UNDERLINE
from lightwrite.document_io import save_document
from lightwrite.export import start_pdf_export
from lightwrite.i18n import current_language, save_language_preference, tr
from lightwrite.layout import adjust_scroll
from lightwrite.model import absolute_to_position, apply_alignment, apply_attr_to_selection, cells_to_text, collect_headings, count_words, delete_at_cursor_rich, delete_before_cursor_rich, delete_selection_rich, document_to_string, enter_rich, get_system_clipboard, insert_cells_at_cursor, insert_page_break_rich, move_down, move_left, move_right, move_up, selected_cells, selection_range, set_line_heading, set_system_clipboard, text_to_cells
from lightwrite.prompts import CONFIRM_NEW, CONFIRM_OPEN, CONFIRM_QUIT, begin_confirm
from lightwrite.spell import _spell_tool
from lightwrite.ui_draw import MENUS, list_directory
from lightwrite.undo import apply_undo
import curses
from lightwrite.input import disable_mouse_tracking
from lightwrite.ui_draw import chapter_panel_geometry
import lightwrite.model as model_mod

def handle_keys(ed, event_type, value):
    if event_type == 'key':
        ed.auto_scroll = True
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
        if value == 'NEW':
            if ed.doc_dirty:
                ed.mode, ed.prompt_label, ed.prompt_buffer = begin_confirm(CONFIRM_NEW)
                ed.full_redraw = True
                return True
            ed.record_undo()
            ed.document = ['']
            ed.formatting = [[]]
            ed.alignments = [ALIGN_LEFT]
            ed.current_path = None
            ed.cursor_line = 0
            ed.cursor_col = 0
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
            ed.search_active = False
            ed.scroll_row = 0
            ed.touch_document()
            ed.doc_dirty = False
            ed.full_redraw = True
            ed.status_message = tr('Nuevo documento')
            ed.status_time = time.monotonic()
            return True
        if value == 'OPEN':
            if ed.doc_dirty:
                ed.mode, ed.prompt_label, ed.prompt_buffer = begin_confirm(CONFIRM_OPEN)
                ed.full_redraw = True
                return True
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
            ed.full_redraw = True
            return True
        if ed.search_active and value != 'ENTER':
            ed.search_active = False
        if value == 'ENTER' and ed.search_active and ed.search_matches:
            ed.search_index = (ed.search_index + 1) % len(ed.search_matches)
            result = ed.search_matches[ed.search_index]
            ed.cursor_line, ed.cursor_col = result
            ed.selection_start = result
            ed.selection_end = (result[0], result[1] + len(ed.search_term))
            ed.status_message = '%d/%d' % (ed.search_index + 1, len(ed.search_matches))
            ed.status_time = time.monotonic()
            ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
            return True
        if value == 'MARK' and state.TTY_MODE:
            if ed.selecting:
                ed.selecting = False
                ed.status_message = tr('Selección terminada')
            else:
                ed.selection_start = (ed.cursor_line, ed.cursor_col)
                ed.selection_end = (ed.cursor_line, ed.cursor_col)
                ed.selecting = True
                ed.status_message = tr('Selección iniciada')
            ed.status_time = time.monotonic()
            return True
        if value == 'QUIT':
            if ed.doc_dirty and (not ed.pending_quit):
                ed.pending_quit = True
                ed.mode, ed.prompt_label, ed.prompt_buffer = begin_confirm(CONFIRM_QUIT)
                ed.full_redraw = True
                return True
            return 'quit'
        elif value == 'HELP':
            ed.mode = 'help'
            ed.help_scroll = 0
        elif value == 'ABOUT':
            ed.mode = 'about'
            ed.help_scroll = 0
        elif value == 'CHAPTERS':
            ed.chapter_headings = collect_headings(ed.document, ed.formatting)
            ed.chapter_index = 0
            ed.chapter_scroll = 0
            for k, (ln, _lvl, _t) in enumerate(ed.chapter_headings):
                if ln >= ed.cursor_line:
                    ed.chapter_index = k
                    break
            else:
                if ed.chapter_headings:
                    ed.chapter_index = len(ed.chapter_headings) - 1
            _bx, _by, _bw, _bh, _ls, _lh = chapter_panel_geometry(ed.width, ed.height)
            if ed.chapter_index >= ed.chapter_scroll + _lh:
                ed.chapter_scroll = max(0, ed.chapter_index - _lh + 1)
            ed.mode = 'chapters'
        elif value in ('H1', 'H2', 'H3', 'H0'):
            ed.record_undo()
            lvl = {'H1': 1, 'H2': 2, 'H3': 3, 'H0': 0}[value]
            if ed.selection_start is not None and ed.selection_end is not None:
                sel = selection_range(ed.document, ed.selection_start, ed.selection_end)
                if sel is not None:
                    text = document_to_string(ed.document)
                    sline, _u = absolute_to_position(text, sel[0])
                    eline, _u = absolute_to_position(text, sel[1])
                    if sel[1] > sel[0]:
                        before = text[:sel[1]]
                        last_nl = before.rfind('\n')
                        if last_nl == len(before) - 1 and eline > sline:
                            eline -= 1
                    for ln in range(sline, eline + 1):
                        if 0 <= ln < len(ed.formatting):
                            ed.formatting = set_line_heading(ed.formatting, ln, lvl)
            else:
                ed.formatting = set_line_heading(ed.formatting, ed.cursor_line, lvl)
            if lvl == 0:
                ed.status_message = tr('Nivel quitado')
            else:
                ed.status_message = tr('Nivel %d aplicado') % lvl
            ed.status_time = time.monotonic()
        elif value == 'SPELL':
            if not _spell_tool():
                ed.status_message = tr('hunspell no instalado')
                ed.status_time = time.monotonic()
            else:
                ed.spell_check_active = not ed.spell_check_active
                ed.spell_dirty = True
                ed.spell_last_change = 0.0
                ed.spell_suggest_cache = {}
                if ed.spell_check_active:
                    ed.status_message = tr('Ortografía activada')
                else:
                    ed.spell_positions = []
                    ed.spell_suggestions = []
                    ed.spell_unavailable_msg = ''
                    ed.status_message = tr('Ortografía desactivada')
                ed.status_time = time.monotonic()
        elif value in ('LANG_ES', 'LANG_EN'):
            new_lang = 'es' if value == 'LANG_ES' else 'en'
            if new_lang == current_language():
                ed.status_message = tr('Ya estás en ese idioma')
                ed.status_time = time.monotonic()
                return True
            save_language_preference(new_lang)
            if ed.current_path is None:
                save_path = SESSION_RTF
            else:
                save_path = ed.current_path
            if not save_document(ed.document, ed.formatting, ed.alignments, save_path):
                ed.status_message = tr('Error al guardar')
                ed.status_time = time.monotonic()
                return True
            disable_mouse_tracking()
            try:
                curses.nocbreak()
                curses.echo()
                curses.endwin()
            except curses.error:
                pass
            os.environ['LIGHTWRITE_LANG'] = new_lang
            if getattr(sys, 'frozen', False):
                new_argv = [sys.executable, save_path]
            else:
                pkg_dir = os.path.dirname(os.path.abspath(__file__))
                src_dir = os.path.dirname(pkg_dir)
                entry = os.path.join(src_dir, 'lightwrite.py')
                if os.path.isfile(entry):
                    new_argv = [sys.executable, entry, save_path]
                else:
                    new_argv = [sys.executable, '-m', 'lightwrite', save_path]
            os.execv(sys.executable, new_argv)
        elif value in ('ALIGN_LEFT', 'ALIGN_CENTER', 'ALIGN_RIGHT', 'ALIGN_JUSTIFY'):
            ed.record_undo()
            new_align = {'ALIGN_LEFT': ALIGN_LEFT, 'ALIGN_CENTER': ALIGN_CENTER, 'ALIGN_RIGHT': ALIGN_RIGHT, 'ALIGN_JUSTIFY': ALIGN_JUSTIFY}[value]
            ed.alignments = apply_alignment(ed.document, ed.alignments, ed.cursor_line, ed.selection_start, ed.selection_end, new_align)
            labels = {'ALIGN_LEFT': tr('Izquierda'), 'ALIGN_CENTER': tr('Centrada'), 'ALIGN_RIGHT': tr('Derecha'), 'ALIGN_JUSTIFY': tr('Justificada')}
            ed.status_message = labels[value]
            ed.status_time = time.monotonic()
        elif value == 'SELECT_ALL':
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
        elif value == 'FIND':
            ed.mode = 'search'
            ed.prompt_label = tr('Buscar:')
            ed.prompt_buffer = ed.search_term
        elif value == 'REPLACE':
            ed.mode = 'replace_find'
            ed.prompt_label = tr('Buscar:')
            ed.prompt_buffer = ed.search_term
        elif value == 'PDF':
            if ed.export_state is not None:
                ed.status_message = tr('Ya hay una exportación en curso')
                ed.status_time = time.monotonic()
            else:
                if ed.current_path is None:
                    base_path = os.path.expanduser('~/lightwrite/documento.rtf')
                else:
                    base_path = ed.current_path
                job, err = start_pdf_export(ed.document, ed.formatting, ed.alignments, base_path)
                if job is None:
                    ed.status_message = err
                    ed.status_time = time.monotonic()
                else:
                    ed.export_state = job
                    ed.export_kind = 'pdf'
                    ed.export_frames = 0
                    ed.status_message = ''
                    ed.status_time = 0
        elif value == 'SAVE':
            if ed.current_path is None:
                ed.mode = 'save_as'
                ed.prompt_label = tr('Nombre (se guarda en ~/lightwrite/):')
                ed.prompt_buffer = ''
            else:
                if save_document(ed.document, ed.formatting, ed.alignments, ed.current_path):
                    ed.doc_dirty = False
                    ed.status_message = tr('Guardado: %s') % os.path.basename(ed.current_path)
                else:
                    ed.status_message = tr('Error al guardar')
                ed.status_time = time.monotonic()
        elif value == 'SAVE_AS':
            ed.mode = 'save_as'
            ed.prompt_label = tr('Nombre (se guarda en ~/lightwrite/):')
            if ed.current_path:
                base = os.path.basename(ed.current_path)
                ed.prompt_buffer = os.path.splitext(base)[0]
            else:
                ed.prompt_buffer = ''
        elif value == 'SAVE_AS_DOCX':
            ed.mode = 'save_as_docx'
            ed.prompt_label = tr('Nombre para .docx (se guarda en ~/lightwrite/):')
            if ed.current_path:
                base = os.path.basename(ed.current_path)
                ed.prompt_buffer = os.path.splitext(base)[0]
            else:
                ed.prompt_buffer = ''
        elif value == 'COPY':
            cells = selected_cells(ed.document, ed.formatting, ed.selection_start, ed.selection_end)
            if cells:
                model_mod.internal_rich_clipboard = cells
                set_system_clipboard(cells_to_text(cells))
                ed.status_message = tr('Copiado')
                ed.status_time = time.monotonic()
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
        elif value == 'BOLD':
            if ed.selection_start is not None and ed.selection_end is not None:
                ed.record_undo()
                ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, BOLD)
                ed.status_message = tr('Negrita')
            else:
                ed.typing_attrs ^= BOLD
                ed.status_message = tr('Negrita')
            ed.status_time = time.monotonic()
        elif value == 'ITALIC':
            if ed.selection_start is not None and ed.selection_end is not None:
                ed.record_undo()
                ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, ITALIC)
                ed.status_message = tr('Cursiva')
            else:
                ed.typing_attrs ^= ITALIC
                ed.status_message = tr('Cursiva')
            ed.status_time = time.monotonic()
        elif value == 'UNDERLINE':
            if ed.selection_start is not None and ed.selection_end is not None:
                ed.record_undo()
                ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, UNDERLINE)
                ed.status_message = tr('Subrayado')
            else:
                ed.typing_attrs ^= UNDERLINE
                ed.status_message = tr('Subrayado')
            ed.status_time = time.monotonic()
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
        elif value in ('SELECT_LEFT', 'SELECT_RIGHT', 'SELECT_UP', 'SELECT_DOWN', 'SELECT_HOME', 'SELECT_END', 'SELECT_PAGE_UP', 'SELECT_PAGE_DOWN'):
            if ed.selection_start is None:
                ed.selection_start = (ed.cursor_line, ed.cursor_col)
            if value == 'SELECT_LEFT':
                ed.cursor_line, ed.cursor_col = move_left(ed.document, ed.cursor_line, ed.cursor_col)
            elif value == 'SELECT_RIGHT':
                ed.cursor_line, ed.cursor_col = move_right(ed.document, ed.cursor_line, ed.cursor_col)
            elif value == 'SELECT_UP':
                ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
            elif value == 'SELECT_DOWN':
                ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
            elif value == 'SELECT_HOME':
                ed.cursor_col = 0
            elif value == 'SELECT_END':
                ed.cursor_col = len(ed.document[ed.cursor_line])
            elif value == 'SELECT_PAGE_UP':
                for _ in range(ed.visible_rows):
                    ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
            elif value == 'SELECT_PAGE_DOWN':
                for _ in range(ed.visible_rows):
                    ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
            ed.selection_end = (ed.cursor_line, ed.cursor_col)
            if ed.selection_start == ed.selection_end:
                ed.selection_start = None
                ed.selection_end = None
            ed.auto_scroll = True
            ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
            return True
        elif value == 'LEFT':
            ed.cursor_line, ed.cursor_col = move_left(ed.document, ed.cursor_line, ed.cursor_col)
        elif value == 'RIGHT':
            ed.cursor_line, ed.cursor_col = move_right(ed.document, ed.cursor_line, ed.cursor_col)
        elif value == 'UP':
            ed.cursor_line, ed.cursor_col = move_up(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        elif value == 'DOWN':
            ed.cursor_line, ed.cursor_col = move_down(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width)
        if value in ('LEFT', 'RIGHT', 'UP', 'DOWN'):
            if ed.selecting and state.TTY_MODE:
                ed.selection_end = (ed.cursor_line, ed.cursor_col)
            else:
                ed.selection_start = None
                ed.selection_end = None
        elif value in ('BACKSPACE', 'DELETE', 'ENTER'):
            ed.selection_start = None
            ed.selection_end = None
            ed.selecting = False
        ed.scroll_row = adjust_scroll(ed.document, ed.cursor_line, ed.cursor_col, ed.text_width, ed.visible_rows, ed.scroll_row)
        return True
    return False
