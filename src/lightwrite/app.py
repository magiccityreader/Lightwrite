import curses
import os
import select
import sys
import time

from lightwrite import profile
from lightwrite import state
from lightwrite.layout import LayoutCache, set_layout_version
from lightwrite.prompts import (
    CONFIRM_NEW, CONFIRM_OPEN, CONFIRM_QUIT,
    begin_confirm, interpret_answer, is_confirm_mode,
)
import lightwrite.model as model_mod
from lightwrite.constants import (
    ALIGN_CENTER, ALIGN_JUSTIFY, ALIGN_LEFT, ALIGN_RIGHT,
    BOLD, DROPDOWN_ROW, H1, ITALIC, MENU_ROW,
    SESSION_RTF, SPINNER_FRAMES, STATUS_DURATION, TEXT_TOP, TEXT_WIDTH,
    UNDERLINE,
)
from lightwrite.document_io import load_document, save_document
from lightwrite.export import (
    poll_docx_save, poll_pdf_export, start_docx_save, start_pdf_export,
)
from lightwrite.i18n import (
    current_language, save_language_preference, tr,
)
from lightwrite.input import (
    disable_mouse_tracking, enable_mouse_tracking, has_pending_input,
    read_input_event,
)
from lightwrite.layout import (
    adjust_scroll, mouse_to_document_position, visual_lines,
)
from lightwrite.model import (
    DocVersion, PlainTextCache, absolute_to_position, apply_alignment,
    apply_attr_to_selection,
    cells_to_text, collect_headings, count_words,
    delete_at_cursor_rich, delete_before_cursor_rich, delete_selection_rich,
    document_to_string, enter_rich, find_all, get_system_clipboard,
    insert_cells_at_cursor, insert_character_rich, insert_page_break_rich,
    move_down, move_left, move_right, move_up, position_to_absolute,
    replace_all, selected_cells, selection_range,
    set_line_heading, set_system_clipboard, text_to_cells,
)
from lightwrite.undo import apply_undo, push_insert, push_undo
from lightwrite.spell import _spell_tool, get_suggestions, run_spell_check
from lightwrite.ui_draw import (
    MENUS, browser_box_geometry, chapter_panel_geometry, draw_editor,
    dropdown_item_at, dropdown_x,
    init_colors, list_directory, menu_bar_layout, menu_index_at,
)

def editor(stdscr, initial_path=None):
    curses.raw()
    curses.noecho()
    curses.curs_set(1)
    curses.mousemask(0)
    enable_mouse_tracking()

    init_colors()

    if initial_path:
        document, formatting, alignments = load_document(initial_path)
    else:
        document = [""]
        formatting = [[]]
        alignments = [ALIGN_LEFT]

    current_path = initial_path

    typing_attrs = 0
    cursor_line = 0
    cursor_col = 0

    selection_start = None
    selection_end = None
    selecting = False

    status_message = ""
    status_time = 0

    scroll_row = 0
    auto_scroll = True

    mode = "normal"
    prompt_buffer = ""
    prompt_label = ""
    search_term = ""
    replace_term = ""
    help_scroll = 0
    pending_overwrite_path = ""
    pending_overwrite_docx = False

    search_active = False
    search_matches = []
    search_index = 0

    undo_stack = []

    menu_open = -1
    menu_selected = 0
    pending_key = None

    browse_dir = ""
    browse_entries = []
    browse_index = 0
    browse_scroll = 0

    export_state = None
    export_kind = None
    export_frames = 0

    spell_check_active = False
    spell_positions = []
    spell_dirty = False
    spell_last_change = 0.0
    spell_suggestions = []
    spell_suggest_cache = {}
    spell_unavailable_msg = ""
    plain_cache = PlainTextCache()
    plain_cache.get(document)
    doc_version = DocVersion()
    layout_cache = LayoutCache()
    set_layout_version(doc_version.n)
    doc_dirty = False
    full_redraw = True
    pending_quit = False
    last_spell_doc_str = plain_cache.get(document)

    def touch_document():
        plain_cache.invalidate()
        layout_cache.invalidate()
        doc_version.bump()
        set_layout_version(doc_version.n)

    def record_undo(*args, **kwargs):
        nonlocal doc_dirty
        push_undo(*args, **kwargs)
        touch_document()
        doc_dirty = True

    def record_insert(line, col, text):
        nonlocal doc_dirty
        push_insert(undo_stack, line, col, text)
        touch_document()
        doc_dirty = True


    chapter_headings = []
    chapter_index = 0
    chapter_scroll = 0

    SCROLL_LINES = 3

    try:
        while True:
            if export_state is not None:
                if export_kind == "pdf":
                    done, success, message = poll_pdf_export(export_state)
                else:
                    done, success, message = poll_docx_save(export_state)
                if done:
                    if export_kind == "docx" and success:
                        doc_dirty = False
                    export_state = None
                    export_kind = None
                    export_frames = 0
                    status_message = message
                    status_time = time.monotonic()
                else:
                    export_frames = (export_frames + 1) % len(SPINNER_FRAMES)

            height, width = stdscr.getmaxyx()
            top = TEXT_TOP
            bottom = height - 2
            if bottom <= top:
                bottom = top + 1

            text_width = min(TEXT_WIDTH, max(1, width - 4))
            text_x = max(2, (width - text_width) // 2)
            visible_rows = max(1, bottom - top)

            if spell_check_active:
                cur_str = plain_cache.get(document)
                if cur_str != last_spell_doc_str:
                    spell_dirty = True
                    spell_last_change = time.monotonic()
                    last_spell_doc_str = cur_str

                if (spell_dirty
                        and time.monotonic() - spell_last_change > 0.5):
                    with profile.span("spell"):
                        positions = run_spell_check(cur_str, current_language())
                    if positions is None:
                        spell_positions = []
                        spell_unavailable_msg = tr(
                            "hunspell no instalado")
                        spell_check_active = False
                    else:
                        spell_positions = positions
                        spell_unavailable_msg = ""
                    spell_dirty = False

            spell_suggestions = []
            if spell_check_active and spell_positions:
                doc_str_now = plain_cache.get(document)
                cursor_abs = position_to_absolute(
                    document, cursor_line, cursor_col)
                for s, e in spell_positions:
                    if s <= cursor_abs < e:
                        word = doc_str_now[s:e]
                        key = (word, current_language())
                        if key in spell_suggest_cache:
                            spell_suggestions = spell_suggest_cache[key]
                        else:
                            spell_suggestions = get_suggestions(
                                word, current_language())
                            spell_suggest_cache[key] = spell_suggestions
                        break

            force_draw = export_state is not None

            if force_draw or not has_pending_input(0, 0):
                if auto_scroll:
                    scroll_row = adjust_scroll(
                        document, cursor_line, cursor_col,
                        text_width, visible_rows, scroll_row
                    )
                else:
                    total_rows = len(visual_lines(document, text_width))
                    max_scroll = max(0, total_rows - visible_rows)
                    scroll_row = max(0, min(scroll_row, max_scroll))

                if (status_message
                        and time.monotonic() - status_time > STATUS_DURATION):
                    status_message = ""

                if current_path:
                    window_title = (
                        "LIGHTWRITE  ·  " + os.path.basename(current_path)
                    )
                else:
                    window_title = "LIGHTWRITE"

                with profile.span("redraw"):
                  draw_editor(
                    stdscr, document, formatting, alignments,
                    cursor_line, cursor_col,
                    selection_start, selection_end,
                    scroll_row, status_message, typing_attrs,
                    window_title, mode, prompt_buffer, prompt_label,
                    help_scroll, search_active, search_matches,
                    search_index, menu_open, menu_selected,
                    browse_dir, browse_entries,
                    browse_index, browse_scroll,
                    export_state is not None,
                    SPINNER_FRAMES[export_frames],
                    export_kind,
                    spell_positions,
                    spell_suggestions,
                    spell_unavailable_msg,
                    spell_check_active,
                    chapter_headings,
                    chapter_index,
                    chapter_scroll,
                    full_redraw=full_redraw,
                )
                full_redraw = False

            input_timeout = None
            if export_state is not None:
                input_timeout = 0.12
            elif spell_check_active and spell_dirty:
                input_timeout = 0.1

            if input_timeout is not None:
                r, _w, _x = select.select([0], [], [], input_timeout)
                if not r:
                    continue

            if pending_key is not None:
                event_type = "key"
                value = pending_key
                pending_key = None
            else:
                event = read_input_event(0)
                if event is None:
                    continue
                event_type, value = event

            if (event_type == "mouse"
                    and mode in ("search", "replace_find",
                                 "replace_with", "save_as",
                                 "save_as_docx", "confirm_overwrite",
                                 "confirm_quit", "confirm_new",
                                 "confirm_open")):
                (button, mx, my, action) = value
                if button == 0 and action == "M":
                    mode = "normal"
                    prompt_buffer = ""
                    prompt_label = ""
                    pending_overwrite_path = ""
                    pending_quit = False
                    full_redraw = True

            # ====================================================
            # MAPA DE CAPÍTULOS
            # ====================================================
            if mode == "chapters":
                _bx, _by, _bw, _bh, _ls, _lh = chapter_panel_geometry(
                    width, height
                )
                if event_type == "key":
                    if value in ("ESC", "QUIT"):
                        mode = "normal"
                    elif value == "UP":
                        if chapter_index > 0:
                            chapter_index -= 1
                    elif value == "DOWN":
                        if chapter_index < len(chapter_headings) - 1:
                            chapter_index += 1
                    elif value == "PAGE_UP":
                        chapter_index = max(0, chapter_index - _lh)
                    elif value == "PAGE_DOWN":
                        chapter_index = min(
                            max(0, len(chapter_headings) - 1),
                            chapter_index + _lh
                        )
                    elif value == "HOME":
                        chapter_index = 0
                    elif value == "END":
                        chapter_index = max(
                            0, len(chapter_headings) - 1
                        )
                    elif value == "ENTER":
                        if 0 <= chapter_index < len(chapter_headings):
                            line_index, _lvl, txt = (
                                chapter_headings[chapter_index]
                            )
                            record_undo(undo_stack, document,
                                      formatting, alignments)
                            cursor_line = line_index
                            cursor_col = 0
                            selection_start = None
                            selection_end = None
                            selecting = False
                            search_active = False
                            auto_scroll = True
                            mode = "normal"
                            scroll_row = adjust_scroll(
                                document, cursor_line, cursor_col,
                                text_width, visible_rows, scroll_row
                            )
                            status_message = (
                                tr("Saltado a: %s") % txt
                            )
                            status_time = time.monotonic()
                    elif value == "CHAPTERS":
                        mode = "normal"
                    elif len(value) == 1 and value.lower() == "n":
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        new_title = tr("Nuevo capítulo")
                        if document and document[-1] != "":
                            document.append("")
                            formatting.append([])
                            alignments.append(ALIGN_LEFT)
                        if document[-1] == "":
                            idx = len(document) - 1
                        else:
                            document.append("")
                            formatting.append([])
                            alignments.append(ALIGN_LEFT)
                            idx = len(document) - 1
                        document[idx] = new_title
                        formatting[idx] = [H1] * len(new_title)
                        while len(alignments) < len(document):
                            alignments.append(ALIGN_LEFT)
                        alignments = alignments[:len(document)]
                        cursor_line = idx
                        cursor_col = 0
                        selection_start = (idx, 0)
                        selection_end = (idx, len(new_title))
                        selecting = False
                        search_active = False
                        auto_scroll = True
                        mode = "normal"
                        scroll_row = adjust_scroll(
                            document, cursor_line, cursor_col,
                            text_width, visible_rows, scroll_row
                        )
                        status_message = tr("Nuevo capítulo")
                        status_time = time.monotonic()

                    if chapter_index < chapter_scroll:
                        chapter_scroll = chapter_index
                    elif chapter_index >= chapter_scroll + _lh:
                        chapter_scroll = chapter_index - _lh + 1
                    if chapter_scroll < 0:
                        chapter_scroll = 0

                elif event_type == "mouse":
                    (button, mx, my, action) = value

                    # Rueda del ratón: subir
                    if action == "M" and button == 64:
                        chapter_scroll = max(0, chapter_scroll - 3)
                        continue

                    # Rueda del ratón: bajar
                    if action == "M" and button == 65:
                        max_scroll = max(
                            0, len(chapter_headings) - _lh
                        )
                        chapter_scroll = min(
                            max_scroll, chapter_scroll + 3
                        )
                        continue

                    # Clic izquierdo
                    if button == 0 and action == "M":
                        list_x = _bx + 2
                        list_w = _bw - 4
                        if (list_x <= mx < list_x + list_w
                                and _ls <= my < _ls + _lh):
                            clicked_row = my - _ls
                            clicked_idx = (
                                chapter_scroll + clicked_row
                            )
                            if 0 <= clicked_idx < len(
                                    chapter_headings):
                                if clicked_idx == chapter_index:
                                    # Segundo clic sobre el mismo:
                                    # saltar al capítulo
                                    (line_index, _lvl, txt
                                     ) = chapter_headings[clicked_idx]
                                    record_undo(
                                        undo_stack, document,
                                        formatting, alignments
                                    )
                                    cursor_line = line_index
                                    cursor_col = 0
                                    selection_start = None
                                    selection_end = None
                                    selecting = False
                                    search_active = False
                                    auto_scroll = True
                                    mode = "normal"
                                    scroll_row = adjust_scroll(
                                        document,
                                        cursor_line, cursor_col,
                                        text_width, visible_rows,
                                        scroll_row
                                    )
                                    status_message = (
                                        tr("Saltado a: %s") % txt
                                    )
                                    status_time = time.monotonic()
                                else:
                                    # Primer clic: seleccionar
                                    chapter_index = clicked_idx

                    # Ajustar scroll tras mover el índice
                    if chapter_index < chapter_scroll:
                        chapter_scroll = chapter_index
                    elif chapter_index >= chapter_scroll + _lh:
                        chapter_scroll = chapter_index - _lh + 1
                    if chapter_scroll < 0:
                        chapter_scroll = 0
                continue

            # ====================================================
            # AYUDA / ACERCA DE
            # ====================================================
            if mode in ("help", "about"):
                if event_type == "key":
                    if value in ("ESC", "QUIT", "HELP", "ABOUT"):
                        if menu_open >= 0:
                            full_redraw = True
                            menu_open = -1
                        else:
                            mode = "normal"
                            help_scroll = 0
                    elif value == "UP":
                        help_scroll = max(0, help_scroll - 1)
                    elif value == "DOWN":
                        help_scroll += 1
                    elif value == "PAGE_UP":
                        help_scroll = max(0, help_scroll - visible_rows)
                    elif value == "PAGE_DOWN":
                        help_scroll += visible_rows

                elif event_type == "mouse":
                    (button, mx, my, action) = value
                    if button == 0 and action == "M":
                        idx = menu_index_at(MENUS, mx, width)
                        if my == MENU_ROW and idx >= 0:
                            name, items = MENUS[idx]
                            if items is None:
                                full_redraw = True
                                menu_open = -1
                                pending_key = "QUIT"
                            elif menu_open == idx:
                                full_redraw = True
                                menu_open = -1
                            else:
                                full_redraw = True
                                menu_open = idx
                            continue
                        if menu_open >= 0:
                            _name, items = MENUS[menu_open]
                            if items is not None:
                                layout = menu_bar_layout(MENUS, width)
                                menu_label_x = layout[menu_open][1]
                                dx = dropdown_x(items,
                                                menu_label_x, width)
                                item_idx = dropdown_item_at(
                                    items, mx, my, dx, DROPDOWN_ROW
                                )
                                if item_idx >= 0:
                                    item = items[item_idx]
                                    action_key = item[2]
                                    full_redraw = True
                                    menu_open = -1
                                    pending_key = action_key
                                    continue
                            full_redraw = True
                            menu_open = -1
                continue

            # ====================================================
            # EXPLORADOR
            # ====================================================
            if mode == "browse":
                box_x, box_y, box_w, box_h = browser_box_geometry(
                    width, height)
                list_x = box_x + 2
                list_y = box_y + 3
                list_w = box_w - 4
                list_h = box_h - 5

                if event_type == "key":
                    if value == "ESC":
                        mode = "normal"
                        browse_dir = ""
                        browse_entries = []
                    elif value == "UP":
                        if browse_index > 0:
                            browse_index -= 1
                    elif value == "DOWN":
                        if browse_index < len(browse_entries) - 1:
                            browse_index += 1
                    elif value == "PAGE_UP":
                        browse_index = max(0, browse_index - list_h)
                    elif value == "PAGE_DOWN":
                        browse_index = min(
                            len(browse_entries) - 1,
                            browse_index + list_h
                        )
                    elif value == "HOME":
                        browse_index = 0
                    elif value == "END":
                        browse_index = max(
                            0, len(browse_entries) - 1)
                    elif value == "ENTER":
                        if 0 <= browse_index < len(browse_entries):
                            name, full, is_dir = (
                                browse_entries[browse_index])
                            if is_dir:
                                browse_dir = full
                                browse_entries = list_directory(
                                    browse_dir)
                                browse_index = 0
                                browse_scroll = 0
                            else:
                                push_undo(undo_stack, document,
                                          formatting, alignments)
                                (document, formatting, alignments
                                 ) = load_document(full)
                                touch_document()
                                current_path = full
                                cursor_line = 0
                                cursor_col = 0
                                selection_start = None
                                selection_end = None
                                selecting = False
                                search_active = False
                                scroll_row = 0
                                mode = "normal"
                                browse_dir = ""
                                browse_entries = []
                                status_message = (
                                    tr("Abierto: %s")
                                    % os.path.basename(full))
                                plain_cache.invalidate()
                                doc_dirty = False
                                full_redraw = True
                                status_time = time.monotonic()
                    elif value == "BACKSPACE":
                        parent = os.path.dirname(
                            os.path.abspath(browse_dir))
                        if (parent
                                and parent != os.path.abspath(browse_dir)):
                            old_basename = os.path.basename(browse_dir)
                            browse_dir = parent
                            browse_entries = list_directory(browse_dir)
                            browse_index = 0
                            for i, (nm, _full, is_dir) in enumerate(
                                    browse_entries):
                                if is_dir and nm == old_basename:
                                    browse_index = i
                                    break
                            browse_scroll = 0
                    elif len(value) == 1 and value.isprintable():
                        start = browse_index + 1
                        n_entries = len(browse_entries)
                        for i in range(n_entries):
                            idx = (start + i) % n_entries
                            name = browse_entries[idx][0]
                            if name.lower().startswith(value.lower()):
                                browse_index = idx
                                break

                    if browse_index < browse_scroll:
                        browse_scroll = browse_index
                    elif browse_index >= browse_scroll + list_h:
                        browse_scroll = browse_index - list_h + 1
                    if browse_scroll < 0:
                        browse_scroll = 0

                elif event_type == "mouse":
                    (button, mx, my, action) = value
                    if action == "M" and button == 64:
                        browse_scroll = max(
                            0, browse_scroll - SCROLL_LINES)
                    elif action == "M" and button == 65:
                        max_scroll = max(
                            0, len(browse_entries) - list_h)
                        browse_scroll = min(
                            max_scroll, browse_scroll + SCROLL_LINES
                        )
                    elif button == 0 and action == "M":
                        if (list_x <= mx < list_x + list_w
                                and list_y <= my < list_y + list_h):
                            clicked_row = my - list_y
                            clicked_idx = browse_scroll + clicked_row
                            if 0 <= clicked_idx < len(browse_entries):
                                if clicked_idx == browse_index:
                                    (name, full, is_dir
                                     ) = browse_entries[clicked_idx]
                                    if is_dir:
                                        browse_dir = full
                                        browse_entries = list_directory(
                                            browse_dir)
                                        browse_index = 0
                                        browse_scroll = 0
                                    else:
                                        push_undo(
                                            undo_stack, document,
                                            formatting, alignments
                                        )
                                        (document, formatting,
                                         alignments
                                         ) = load_document(full)
                                        touch_document()
                                        current_path = full
                                        cursor_line = 0
                                        cursor_col = 0
                                        selection_start = None
                                        selection_end = None
                                        selecting = False
                                        search_active = False
                                        scroll_row = 0
                                        mode = "normal"
                                        browse_dir = ""
                                        browse_entries = []
                                        status_message = (
                                            tr("Abierto: %s")
                                            % os.path.basename(full))
                                        plain_cache.invalidate()
                                        doc_dirty = False
                                        full_redraw = True
                                        status_time = time.monotonic()
                                else:
                                    browse_index = clicked_idx
                continue

            # ====================================================
            # GUARDAR COMO
            # ====================================================
            if mode in ("save_as", "save_as_docx"):
                if event_type == "key":
                    if value == "ESC":
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""

                    elif value == "BACKSPACE":
                        prompt_buffer = prompt_buffer[:-1]

                    elif value == "ENTER":
                        name = prompt_buffer.strip()
                        force_docx = (mode == "save_as_docx")
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""

                        if name:
                            if "/" in name or name.startswith("~"):
                                full_path = os.path.expanduser(name)
                            else:
                                full_path = os.path.expanduser(
                                    os.path.join("~/lightwrite", name)
                                )

                            lower = full_path.lower()
                            if not lower.endswith(
                                    (".rtf", ".txt", ".docx", ".doc")):
                                if force_docx:
                                    full_path += ".docx"
                                else:
                                    full_path += ".rtf"

                            if os.path.exists(full_path):
                                pending_overwrite_path = full_path
                                pending_overwrite_docx = (
                                    force_docx
                                    or full_path.lower().endswith(
                                        (".docx", ".doc"))
                                )
                                mode = "confirm_overwrite"
                                prompt_label = tr(
                                    "¿Sobrescribir %s? (s/n):"
                                ) % os.path.basename(full_path)
                                prompt_buffer = ""
                                continue

                            directory = os.path.dirname(
                                os.path.abspath(full_path))
                            if directory:
                                try:
                                    os.makedirs(directory, exist_ok=True)
                                except OSError:
                                    status_message = tr(
                                        "No se puede crear carpeta")
                                    status_time = time.monotonic()
                                    continue

                            if full_path.lower().endswith(
                                    (".docx", ".doc")):
                                if export_state is not None:
                                    status_message = tr(
                                        "Ya hay un guardado en curso")
                                    status_time = time.monotonic()
                                else:
                                    job, err = start_docx_save(
                                        document, formatting,
                                        alignments, full_path
                                    )
                                    if job is None:
                                        status_message = err
                                        status_time = time.monotonic()
                                    else:
                                        current_path = full_path
                                        export_state = job
                                        export_kind = "docx"
                                        export_frames = 0
                                        status_message = ""
                                        status_time = 0
                            else:
                                if save_document(document, formatting,
                                                 alignments, full_path):
                                    current_path = full_path
                                    doc_dirty = False
                                    status_message = (
                                        tr("Guardado: %s")
                                        % os.path.basename(full_path))
                                else:
                                    status_message = tr(
                                        "Error al guardar")
                                status_time = time.monotonic()

                elif event_type == "char":
                    if value and value != "\t":
                        prompt_buffer += value

                continue

            # ====================================================
            # CONFIRMAR SOBRESCRITURA
            # ====================================================
            if mode == "confirm_overwrite":
                if event_type == "key":
                    if value == "ESC":
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""
                        pending_overwrite_path = ""
                        status_message = tr("Cancelado")
                        status_time = time.monotonic()

                    elif value == "BACKSPACE":
                        prompt_buffer = prompt_buffer[:-1]

                    elif value == "ENTER":
                        answer = prompt_buffer.strip().lower()
                        full_path = pending_overwrite_path
                        as_docx = pending_overwrite_docx
                        prompt_buffer = ""
                        prompt_label = ""
                        pending_overwrite_path = ""
                        mode = "normal"

                        if answer in ("s", "si", "sí", "y", "yes"):
                            if as_docx or full_path.lower().endswith(
                                    (".docx", ".doc")):
                                if export_state is not None:
                                    status_message = tr(
                                        "Ya hay un guardado en curso")
                                    status_time = time.monotonic()
                                else:
                                    job, err = start_docx_save(
                                        document, formatting,
                                        alignments, full_path
                                    )
                                    if job is None:
                                        status_message = err
                                        status_time = time.monotonic()
                                    else:
                                        current_path = full_path
                                        export_state = job
                                        export_kind = "docx"
                                        export_frames = 0
                                        status_message = ""
                                        status_time = 0
                            else:
                                if save_document(document, formatting,
                                                 alignments, full_path):
                                    current_path = full_path
                                    doc_dirty = False
                                    status_message = (
                                        tr("Guardado: %s")
                                        % os.path.basename(full_path))
                                else:
                                    status_message = tr(
                                        "Error al guardar")
                                status_time = time.monotonic()
                        else:
                            status_message = tr("Cancelado")
                            status_time = time.monotonic()

                elif event_type == "char":
                    if value and value != "\t":
                        ch = value.lower()
                        if ch in ("s", "n", "y"):
                            prompt_buffer = ch
                        elif value.isalpha() and len(prompt_buffer) < 3:
                            prompt_buffer += value

                continue


            # ====================================================
            # CONFIRMAR SALIDA / NUEVO / ABRIR
            # ====================================================
            if is_confirm_mode(mode):
                if event_type == "key":
                    if value == "ESC":
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""
                        pending_quit = False
                        status_message = tr("Cancelado")
                        status_time = time.monotonic()
                        full_redraw = True
                    elif value == "ENTER":
                        yes = interpret_answer(prompt_buffer)
                        action = mode
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""
                        if yes:
                            if action == CONFIRM_QUIT:
                                break
                            if action == CONFIRM_NEW:
                                record_undo(undo_stack, document,
                                            formatting, alignments)
                                document = [""]
                                formatting = [[]]
                                alignments = [ALIGN_LEFT]
                                current_path = None
                                cursor_line = cursor_col = 0
                                scroll_row = 0
                                selection_start = None
                                selection_end = None
                                selecting = False
                                search_active = False
                                touch_document()
                                doc_dirty = False
                                status_message = tr("Nuevo documento")
                                status_time = time.monotonic()
                            elif action == CONFIRM_OPEN:
                                if current_path:
                                    start_dir = os.path.dirname(
                                        os.path.abspath(current_path))
                                else:
                                    start_dir = os.path.expanduser(
                                        "~/lightwrite")
                                if not os.path.isdir(start_dir):
                                    start_dir = os.path.expanduser("~")
                                browse_dir = start_dir
                                browse_entries = list_directory(browse_dir)
                                browse_index = 0
                                browse_scroll = 0
                                mode = "browse"
                            pending_quit = False
                        else:
                            pending_quit = False
                            status_message = tr("Cancelado")
                            status_time = time.monotonic()
                        full_redraw = True
                    elif value == "BACKSPACE":
                        prompt_buffer = prompt_buffer[:-1]
                elif event_type == "char":
                    if value and value != "\t":
                        ch = value.lower()
                        if ch in ("s", "n", "y"):
                            prompt_buffer = ch
                continue

            # ====================================================
            # BUSCAR / REEMPLAZAR
            # ====================================================
            if mode in ("search", "replace_find", "replace_with"):
                if event_type == "key":
                    if value == "ESC":
                        mode = "normal"
                        prompt_buffer = ""
                        prompt_label = ""
                    elif value == "BACKSPACE":
                        prompt_buffer = prompt_buffer[:-1]
                    elif value == "ENTER":
                        if mode == "search":
                            search_term = prompt_buffer
                            prompt_buffer = ""
                            prompt_label = ""
                            mode = "normal"

                            if search_term:
                                search_matches = find_all(
                                    document, search_term)
                                if search_matches:
                                    current_abs = position_to_absolute(
                                        document, cursor_line, cursor_col
                                    )
                                    start_idx = 0
                                    for idx, (l, c) in enumerate(
                                            search_matches):
                                        m_abs = position_to_absolute(
                                            document, l, c)
                                        if m_abs > current_abs:
                                            start_idx = idx
                                            break
                                    search_index = start_idx
                                    result = search_matches[search_index]
                                    cursor_line, cursor_col = result
                                    selection_start = result
                                    selection_end = (
                                        result[0],
                                        result[1] + len(search_term)
                                    )
                                    search_active = True
                                    auto_scroll = True
                                    status_message = "%d/%d" % (
                                        search_index + 1,
                                        len(search_matches))
                                else:
                                    search_matches = []
                                    search_active = False
                                    status_message = tr("No encontrado")
                                status_time = time.monotonic()

                        elif mode == "replace_find":
                            search_term = prompt_buffer
                            prompt_buffer = replace_term
                            prompt_label = tr("Reemplazar con:")
                            mode = "replace_with"

                        elif mode == "replace_with":
                            replace_term = prompt_buffer
                            prompt_buffer = ""
                            prompt_label = ""
                            mode = "normal"

                            if search_term:
                                record_undo(undo_stack, document,
                                          formatting, alignments)
                                (document, formatting, count
                                 ) = replace_all(
                                     document, formatting,
                                     search_term, replace_term)
                                while len(alignments) < len(document):
                                    alignments.append(ALIGN_LEFT)
                                alignments = alignments[:len(document)]

                                if count == 1:
                                    status_message = tr("1 reemplazo")
                                elif count > 1:
                                    status_message = (
                                        tr("%d reemplazos") % count)
                                else:
                                    status_message = tr("No encontrado")
                                status_time = time.monotonic()

                                if document:
                                    cursor_line = min(
                                        cursor_line, len(document) - 1
                                    )
                                    cursor_col = min(
                                        cursor_col,
                                        len(document[cursor_line])
                                    )
                                auto_scroll = True

                elif event_type == "char":
                    if value and value != "\t":
                        prompt_buffer += value
                continue

            # ====================================================
            # MOUSE
            # ====================================================
            if event_type == "mouse":
                (button, mouse_x, mouse_y, action) = value

                if action == "M" and button == 64:
                    scroll_row = max(0, scroll_row - SCROLL_LINES)
                    auto_scroll = False
                    continue
                if action == "M" and button == 65:
                    total_rows = len(visual_lines(document, text_width))
                    max_scroll = max(0, total_rows - visible_rows)
                    scroll_row = min(max_scroll,
                                     scroll_row + SCROLL_LINES)
                    auto_scroll = False
                    continue

                if button == 0 and action == "M":
                    if mouse_y == MENU_ROW:
                        idx = menu_index_at(MENUS, mouse_x, width)
                        if idx >= 0:
                            name, items = MENUS[idx]
                            if items is None:
                                full_redraw = True
                                menu_open = -1
                                pending_key = "QUIT"
                            elif menu_open == idx:
                                full_redraw = True
                                menu_open = -1
                            else:
                                full_redraw = True
                                menu_open = idx
                        else:
                            full_redraw = True
                            menu_open = -1
                        continue

                    if menu_open >= 0:
                        _name, items = MENUS[menu_open]
                        if items is not None:
                            layout = menu_bar_layout(MENUS, width)
                            menu_label_x = layout[menu_open][1]
                            dx = dropdown_x(items, menu_label_x, width)
                            item_idx = dropdown_item_at(
                                items, mouse_x, mouse_y, dx, DROPDOWN_ROW
                            )
                            if item_idx >= 0:
                                item = items[item_idx]
                                action_key = item[2]
                                full_redraw = True
                                menu_open = -1
                                pending_key = action_key
                                continue
                        full_redraw = True
                        menu_open = -1
                        continue

                    auto_scroll = True
                    position = mouse_to_document_position(
                        mouse_x, mouse_y, document, alignments,
                        text_width, scroll_row, top, bottom, text_x
                    )
                    if position is None:
                        continue
                    line, col = position
                    cursor_line = line
                    cursor_col = col
                    selection_start = (cursor_line, cursor_col)
                    selection_end = (cursor_line, cursor_col)
                    selecting = True
                    search_active = False

                elif (button >= 32 and button < 64
                        and action == "M" and selecting):
                    auto_scroll = True
                    if mouse_y >= bottom - 1:
                        total_rows = len(visual_lines(
                            document, text_width))
                        max_scroll = max(0, total_rows - visible_rows)
                        if scroll_row < max_scroll:
                            scroll_row += 1
                    elif mouse_y <= top:
                        if scroll_row > 0:
                            scroll_row -= 1

                    position = mouse_to_document_position(
                        mouse_x, mouse_y, document, alignments,
                        text_width, scroll_row, top, bottom, text_x
                    )
                    if position is not None:
                        line, col = position
                        cursor_line = line
                        cursor_col = col
                        selection_end = (cursor_line, cursor_col)

                elif action == "m" and selecting:
                    auto_scroll = True
                    position = mouse_to_document_position(
                        mouse_x, mouse_y, document, alignments,
                        text_width, scroll_row, top, bottom, text_x
                    )
                    if position is not None:
                        line, col = position
                        cursor_line = line
                        cursor_col = col
                        selection_end = (cursor_line, cursor_col)
                    selecting = False
                    if selection_start == selection_end:
                        selection_start = None
                        selection_end = None
                continue

            # ====================================================
            # TECLADO
            # ====================================================

            if event_type == "key":
                auto_scroll = True

                # F10 abre/cierra la barra de menús
                if value == "MENU":
                    if menu_open >= 0:
                        full_redraw = True
                        menu_open = -1
                    else:
                        n = len(MENUS)
                        idx = 0
                        while idx < n and MENUS[idx][1] is None:
                            idx += 1
                        if idx < n:
                            full_redraw = True
                            menu_open = idx
                            menu_selected = 0
                            items = MENUS[idx][1]
                            while (menu_selected < len(items)
                                   and items[menu_selected] is None):
                                menu_selected += 1
                    continue

                # Navegación del menú cuando está abierto
                if menu_open >= 0:
                    if value == "ESC":
                        full_redraw = True
                        menu_open = -1
                    elif value == "LEFT":
                        n = len(MENUS)
                        for i in range(1, n + 1):
                            idx = (menu_open - i) % n
                            if MENUS[idx][1] is not None:
                                full_redraw = True
                                menu_open = idx
                                menu_selected = 0
                                items = MENUS[idx][1]
                                while (menu_selected < len(items)
                                       and items[menu_selected] is None):
                                    menu_selected += 1
                                break
                    elif value == "RIGHT":
                        n = len(MENUS)
                        for i in range(1, n + 1):
                            idx = (menu_open + i) % n
                            if MENUS[idx][1] is not None:
                                full_redraw = True
                                menu_open = idx
                                menu_selected = 0
                                items = MENUS[idx][1]
                                while (menu_selected < len(items)
                                       and items[menu_selected] is None):
                                    menu_selected += 1
                                break
                    elif value == "UP":
                        items = MENUS[menu_open][1]
                        idx = menu_selected - 1
                        while idx >= 0 and items[idx] is None:
                            idx -= 1
                        if idx >= 0:
                            menu_selected = idx
                    elif value == "DOWN":
                        items = MENUS[menu_open][1]
                        idx = menu_selected + 1
                        while (idx < len(items)
                               and items[idx] is None):
                            idx += 1
                        if idx < len(items):
                            menu_selected = idx
                    elif value == "ENTER":
                        items = MENUS[menu_open][1]
                        if (items and 0 <= menu_selected
                                < len(items)):
                            item = items[menu_selected]
                            if item is not None:
                                action_key = item[2]
                                full_redraw = True
                                menu_open = -1
                                pending_key = action_key
                                continue
                    continue

                if value == "NEW":
                    if doc_dirty:
                        mode, prompt_label, prompt_buffer = begin_confirm(
                            CONFIRM_NEW)
                        full_redraw = True
                        continue
                    record_undo(undo_stack, document, formatting,
                              alignments)
                    document = [""]
                    formatting = [[]]
                    alignments = [ALIGN_LEFT]
                    current_path = None
                    cursor_line = 0
                    cursor_col = 0
                    selection_start = None
                    selection_end = None
                    selecting = False
                    search_active = False
                    scroll_row = 0
                    touch_document()
                    doc_dirty = False
                    full_redraw = True
                    status_message = tr("Nuevo documento")
                    status_time = time.monotonic()
                    continue

                if value == "OPEN":
                    if doc_dirty:
                        mode, prompt_label, prompt_buffer = begin_confirm(
                            CONFIRM_OPEN)
                        full_redraw = True
                        continue
                    if current_path:
                        start_dir = os.path.dirname(
                            os.path.abspath(current_path))
                    else:
                        start_dir = os.path.expanduser("~/lightwrite")
                    if not os.path.isdir(start_dir):
                        start_dir = os.path.expanduser("~")
                    browse_dir = start_dir
                    browse_entries = list_directory(browse_dir)
                    browse_index = 0
                    browse_scroll = 0
                    mode = "browse"
                    full_redraw = True
                    continue

                if search_active and value != "ENTER":
                    search_active = False

                if value == "ENTER" and search_active and search_matches:
                    search_index = (search_index + 1) % len(search_matches)
                    result = search_matches[search_index]
                    cursor_line, cursor_col = result
                    selection_start = result
                    selection_end = (result[0],
                                     result[1] + len(search_term))
                    status_message = "%d/%d" % (
                        search_index + 1, len(search_matches))
                    status_time = time.monotonic()
                    scroll_row = adjust_scroll(
                        document, cursor_line, cursor_col,
                        text_width, visible_rows, scroll_row
                    )
                    continue

                if value == "MARK" and state.TTY_MODE:
                    if selecting:
                        selecting = False
                        status_message = tr("Selección terminada")
                    else:
                        selection_start = (cursor_line, cursor_col)
                        selection_end = (cursor_line, cursor_col)
                        selecting = True
                        status_message = tr("Selección iniciada")
                    status_time = time.monotonic()
                    continue

                if value == "QUIT":
                    if doc_dirty and not pending_quit:
                        pending_quit = True
                        mode, prompt_label, prompt_buffer = begin_confirm(
                            CONFIRM_QUIT)
                        full_redraw = True
                        continue
                    break

                elif value == "HELP":
                    mode = "help"
                    help_scroll = 0

                elif value == "ABOUT":
                    mode = "about"
                    help_scroll = 0

                elif value == "CHAPTERS":
                    chapter_headings = collect_headings(
                        document, formatting)
                    chapter_index = 0
                    chapter_scroll = 0
                    for k, (ln, _lvl, _t) in enumerate(chapter_headings):
                        if ln >= cursor_line:
                            chapter_index = k
                            break
                    else:
                        if chapter_headings:
                            chapter_index = len(chapter_headings) - 1
                    _bx, _by, _bw, _bh, _ls, _lh = (
                        chapter_panel_geometry(width, height)
                    )
                    if chapter_index >= chapter_scroll + _lh:
                        chapter_scroll = max(
                            0, chapter_index - _lh + 1
                        )
                    mode = "chapters"

                elif value in ("H1", "H2", "H3", "H0"):
                    record_undo(undo_stack, document, formatting,
                              alignments)
                    lvl = {"H1": 1, "H2": 2, "H3": 3, "H0": 0}[value]
                    if (selection_start is not None
                            and selection_end is not None):
                        # Aplicar a todas las líneas de la selección
                        sel = selection_range(document,
                                              selection_start,
                                              selection_end)
                        if sel is not None:
                            text = document_to_string(document)
                            sline, _u = absolute_to_position(
                                text, sel[0])
                            eline, _u = absolute_to_position(
                                text, sel[1])
                            if sel[1] > sel[0]:
                                before = text[:sel[1]]
                                last_nl = before.rfind("\n")
                                if (last_nl == len(before) - 1
                                        and eline > sline):
                                    eline -= 1
                            for ln in range(sline, eline + 1):
                                if 0 <= ln < len(formatting):
                                    formatting = set_line_heading(
                                        formatting, ln, lvl
                                    )
                    else:
                        formatting = set_line_heading(
                            formatting, cursor_line, lvl
                        )
                    if lvl == 0:
                        status_message = tr("Nivel quitado")
                    else:
                        status_message = tr(
                            "Nivel %d aplicado") % lvl
                    status_time = time.monotonic()

                elif value == "SPELL":
                    if not _spell_tool():
                        status_message = tr("hunspell no instalado")
                        status_time = time.monotonic()
                    else:
                        spell_check_active = not spell_check_active
                        spell_dirty = True
                        spell_last_change = 0.0
                        spell_suggest_cache = {}
                        if spell_check_active:
                            status_message = tr("Ortografía activada")
                        else:
                            spell_positions = []
                            spell_suggestions = []
                            spell_unavailable_msg = ""
                            status_message = tr(
                                "Ortografía desactivada")
                        status_time = time.monotonic()

                elif value in ("LANG_ES", "LANG_EN"):
                    new_lang = "es" if value == "LANG_ES" else "en"

                    if new_lang == current_language():
                        status_message = tr("Ya estás en ese idioma")
                        status_time = time.monotonic()
                        continue

                    save_language_preference(new_lang)

                    if current_path is None:
                        save_path = SESSION_RTF
                    else:
                        save_path = current_path

                    if not save_document(document, formatting,
                                         alignments, save_path):
                        status_message = tr("Error al guardar")
                        status_time = time.monotonic()
                        continue

                    disable_mouse_tracking()
                    try:
                        curses.nocbreak()
                        curses.echo()
                        curses.endwin()
                    except curses.error:
                        pass

                    os.environ["LIGHTWRITE_LANG"] = new_lang

                    if getattr(sys, "frozen", False):
                        new_argv = [sys.executable, save_path]
                    else:
                        pkg_dir = os.path.dirname(os.path.abspath(__file__))
                        src_dir = os.path.dirname(pkg_dir)
                        entry = os.path.join(src_dir, "lightwrite.py")
                        if os.path.isfile(entry):
                            new_argv = [sys.executable, entry, save_path]
                        else:
                            new_argv = [
                                sys.executable, "-m", "lightwrite", save_path
                            ]
                    os.execv(sys.executable, new_argv)

                elif value in (
                    "ALIGN_LEFT", "ALIGN_CENTER",
                    "ALIGN_RIGHT", "ALIGN_JUSTIFY"
                ):
                    record_undo(undo_stack, document, formatting,
                              alignments)
                    new_align = {
                        "ALIGN_LEFT": ALIGN_LEFT,
                        "ALIGN_CENTER": ALIGN_CENTER,
                        "ALIGN_RIGHT": ALIGN_RIGHT,
                        "ALIGN_JUSTIFY": ALIGN_JUSTIFY,
                    }[value]
                    alignments = apply_alignment(
                        document, alignments, cursor_line,
                        selection_start, selection_end, new_align
                    )
                    labels = {
                        "ALIGN_LEFT": tr("Izquierda"),
                        "ALIGN_CENTER": tr("Centrada"),
                        "ALIGN_RIGHT": tr("Derecha"),
                        "ALIGN_JUSTIFY": tr("Justificada"),
                    }
                    status_message = labels[value]
                    status_time = time.monotonic()

                elif value == "SELECT_ALL":
                    if document:
                        last_line = len(document) - 1
                        selection_start = (0, 0)
                        selection_end = (
                            last_line,
                            len(document[last_line])
                        )
                        cursor_line = last_line
                        cursor_col = len(document[last_line])

                        n_lines = len(document)
                        wc = count_words(document)

                        status_message = tr(
                            "Seleccionado todo: %d líneas · %d palabras"
                        ) % (n_lines, wc)
                        status_time = time.monotonic()

                elif value == "UNDO":
                    restored = apply_undo(
                        undo_stack, document, formatting, alignments)
                    if restored is not None:
                        document, formatting, alignments = restored
                        if cursor_line >= len(document):
                            cursor_line = max(0, len(document) - 1)
                        if cursor_col > len(document[cursor_line]):
                            cursor_col = len(document[cursor_line])
                        while len(alignments) < len(document):
                            alignments.append(ALIGN_LEFT)
                        alignments = alignments[:len(document)]
                        selection_start = None
                        selection_end = None
                        selecting = False
                        search_active = False
                        touch_document()
                        doc_dirty = True
                        full_redraw = True
                        status_message = tr("Deshecho")
                    else:
                        status_message = tr("Nada que deshacer")
                    status_time = time.monotonic()

                elif value == "PAGEBREAK":
                    record_undo(undo_stack, document, formatting,
                              alignments)
                    if (selection_start is not None
                            and selection_end is not None):
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_selection_rich(
                             document, formatting, alignments,
                             selection_start, selection_end)
                        selection_start = None
                        selection_end = None
                        selecting = False
                    (document, formatting, alignments,
                     cursor_line, cursor_col
                     ) = insert_page_break_rich(
                         document, formatting, alignments,
                         cursor_line, cursor_col)
                    status_message = tr("Salto de página")
                    status_time = time.monotonic()

                elif value == "FIND":
                    mode = "search"
                    prompt_label = tr("Buscar:")
                    prompt_buffer = search_term

                elif value == "REPLACE":
                    mode = "replace_find"
                    prompt_label = tr("Buscar:")
                    prompt_buffer = search_term

                elif value == "PDF":
                    if export_state is not None:
                        status_message = tr(
                            "Ya hay una exportación en curso")
                        status_time = time.monotonic()
                    else:
                        if current_path is None:
                            base_path = os.path.expanduser(
                                "~/lightwrite/documento.rtf")
                        else:
                            base_path = current_path

                        job, err = start_pdf_export(
                            document, formatting, alignments, base_path
                        )

                        if job is None:
                            status_message = err
                            status_time = time.monotonic()
                        else:
                            export_state = job
                            export_kind = "pdf"
                            export_frames = 0
                            status_message = ""
                            status_time = 0

                elif value == "SAVE":
                    if current_path is None:
                        mode = "save_as"
                        prompt_label = tr(
                            "Nombre (se guarda en ~/lightwrite/):")
                        prompt_buffer = ""
                    else:
                        if save_document(
                            document, formatting, alignments,
                            current_path
                        ):
                            doc_dirty = False
                            status_message = tr("Guardado: %s") % (
                                os.path.basename(current_path))
                        else:
                            status_message = tr("Error al guardar")
                        status_time = time.monotonic()

                elif value == "SAVE_AS":
                    mode = "save_as"
                    prompt_label = tr(
                        "Nombre (se guarda en ~/lightwrite/):")
                    if current_path:
                        base = os.path.basename(current_path)
                        prompt_buffer = os.path.splitext(base)[0]
                    else:
                        prompt_buffer = ""

                elif value == "SAVE_AS_DOCX":
                    mode = "save_as_docx"
                    prompt_label = tr(
                        "Nombre para .docx (se guarda en ~/lightwrite/):")
                    if current_path:
                        base = os.path.basename(current_path)
                        prompt_buffer = os.path.splitext(base)[0]
                    else:
                        prompt_buffer = ""

                elif value == "COPY":
                    cells = selected_cells(
                        document, formatting,
                        selection_start, selection_end
                    )
                    if cells:
                        import lightwrite.model as _m
                        _m.model_mod.internal_rich_clipboard = cells
                        set_system_clipboard(cells_to_text(cells))
                        status_message = tr("Copiado")
                        status_time = time.monotonic()

                elif value == "CUT":
                    cells = selected_cells(
                        document, formatting,
                        selection_start, selection_end
                    )
                    if cells:
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        import lightwrite.model as _m
                        _m.model_mod.internal_rich_clipboard = cells
                        set_system_clipboard(cells_to_text(cells))
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_selection_rich(
                             document, formatting, alignments,
                             selection_start, selection_end)
                        selection_start = None
                        selection_end = None
                        selecting = False
                        status_message = tr("Cortado")
                        status_time = time.monotonic()

                elif value == "PASTE":
                    plain = get_system_clipboard()
                    rich_plain = cells_to_text(model_mod.internal_rich_clipboard)
                    if model_mod.internal_rich_clipboard and plain == rich_plain:
                        paste_cells = list(model_mod.internal_rich_clipboard)
                    else:
                        paste_cells = text_to_cells(plain, typing_attrs)

                    if paste_cells:
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        if (selection_start is not None
                                and selection_end is not None):
                            (document, formatting, alignments,
                             cursor_line, cursor_col
                             ) = delete_selection_rich(
                                 document, formatting, alignments,
                                 selection_start, selection_end)
                            selection_start = None
                            selection_end = None
                            selecting = False
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = insert_cells_at_cursor(
                             document, formatting, alignments,
                             cursor_line, cursor_col, paste_cells)
                        status_message = tr("Pegado")
                        status_time = time.monotonic()

                elif value == "BOLD":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        formatting = apply_attr_to_selection(
                            document, formatting,
                            selection_start, selection_end, BOLD
                        )
                        status_message = tr("Negrita")
                    else:
                        typing_attrs ^= BOLD
                        status_message = tr("Negrita")
                    status_time = time.monotonic()

                elif value == "ITALIC":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        formatting = apply_attr_to_selection(
                            document, formatting,
                            selection_start, selection_end, ITALIC
                        )
                        status_message = tr("Cursiva")
                    else:
                        typing_attrs ^= ITALIC
                        status_message = tr("Cursiva")
                    status_time = time.monotonic()

                elif value == "UNDERLINE":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document,
                                  formatting, alignments)
                        formatting = apply_attr_to_selection(
                            document, formatting,
                            selection_start, selection_end, UNDERLINE
                        )
                        status_message = tr("Subrayado")
                    else:
                        typing_attrs ^= UNDERLINE
                        status_message = tr("Subrayado")
                    status_time = time.monotonic()

                elif value == "BACKSPACE":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document, formatting,
                                    alignments)
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_selection_rich(
                             document, formatting, alignments,
                             selection_start, selection_end)
                        selection_start = None
                        selection_end = None
                        selecting = False
                    else:
                        record_undo(undo_stack, document, formatting,
                                    alignments, max(0, cursor_line - 1),
                                    cursor_line + 1)
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_before_cursor_rich(
                             document, formatting, alignments,
                             cursor_line, cursor_col)

                elif value == "DELETE":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document, formatting,
                                    alignments)
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_selection_rich(
                             document, formatting, alignments,
                             selection_start, selection_end)
                        selection_start = None
                        selection_end = None
                        selecting = False
                    else:
                        record_undo(undo_stack, document, formatting,
                                    alignments, cursor_line,
                                    cursor_line + 2)
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_at_cursor_rich(
                             document, formatting, alignments,
                             cursor_line, cursor_col)

                elif value == "ENTER":
                    if (selection_start is not None
                            and selection_end is not None):
                        record_undo(undo_stack, document, formatting,
                                    alignments)
                        (document, formatting, alignments,
                         cursor_line, cursor_col
                         ) = delete_selection_rich(
                             document, formatting, alignments,
                             selection_start, selection_end)
                        selection_start = None
                        selection_end = None
                        selecting = False
                    else:
                        record_undo(undo_stack, document, formatting,
                                    alignments, cursor_line,
                                    cursor_line + 1)
                    (document, formatting, alignments,
                     cursor_line, cursor_col
                     ) = enter_rich(
                         document, formatting, alignments,
                         cursor_line, cursor_col)

                elif value in ("SELECT_LEFT", "SELECT_RIGHT",
                               "SELECT_UP", "SELECT_DOWN",
                               "SELECT_HOME", "SELECT_END",
                               "SELECT_PAGE_UP", "SELECT_PAGE_DOWN"):
                    # Extender selección con Shift + flechas.
                    # Si aún no hay selección, la iniciamos aquí.
                    if selection_start is None:
                        selection_start = (cursor_line, cursor_col)

                    if value == "SELECT_LEFT":
                        cursor_line, cursor_col = move_left(
                            document, cursor_line, cursor_col
                        )
                    elif value == "SELECT_RIGHT":
                        cursor_line, cursor_col = move_right(
                            document, cursor_line, cursor_col
                        )
                    elif value == "SELECT_UP":
                        cursor_line, cursor_col = move_up(
                            document, cursor_line, cursor_col,
                            text_width
                        )
                    elif value == "SELECT_DOWN":
                        cursor_line, cursor_col = move_down(
                            document, cursor_line, cursor_col,
                            text_width
                        )
                    elif value == "SELECT_HOME":
                        cursor_col = 0
                    elif value == "SELECT_END":
                        cursor_col = len(document[cursor_line])
                    elif value == "SELECT_PAGE_UP":
                        for _ in range(visible_rows):
                            cursor_line, cursor_col = move_up(
                                document, cursor_line, cursor_col,
                                text_width
                            )
                    elif value == "SELECT_PAGE_DOWN":
                        for _ in range(visible_rows):
                            cursor_line, cursor_col = move_down(
                                document, cursor_line, cursor_col,
                                text_width
                            )

                    selection_end = (cursor_line, cursor_col)
                    # Si la selección vuelve al punto de origen,
                    # la cancelamos (se comporta como el ratón).
                    if selection_start == selection_end:
                        selection_start = None
                        selection_end = None
                    auto_scroll = True

                    scroll_row = adjust_scroll(
                        document, cursor_line, cursor_col,
                        text_width, visible_rows, scroll_row
                    )
                    continue

                elif value == "LEFT":
                    cursor_line, cursor_col = move_left(
                        document, cursor_line, cursor_col
                    )
                elif value == "RIGHT":
                    cursor_line, cursor_col = move_right(
                        document, cursor_line, cursor_col
                    )
                elif value == "UP":
                    cursor_line, cursor_col = move_up(
                        document, cursor_line, cursor_col, text_width
                    )
                elif value == "DOWN":
                    cursor_line, cursor_col = move_down(
                        document, cursor_line, cursor_col, text_width
                    )

                if value in ("LEFT", "RIGHT", "UP", "DOWN"):
                    if selecting and state.TTY_MODE:
                        selection_end = (cursor_line, cursor_col)
                    else:
                        selection_start = None
                        selection_end = None
                elif value in ("BACKSPACE", "DELETE", "ENTER"):
                    selection_start = None
                    selection_end = None
                    selecting = False

                scroll_row = adjust_scroll(
                    document, cursor_line, cursor_col,
                    text_width, visible_rows, scroll_row
                )
                continue

            # ====================================================
            # TEXTO
            # ====================================================
            if event_type == "char":
                if menu_open >= 0:
                    continue
                char = value
                insert_line, insert_col = cursor_line, cursor_col
                if (selection_start is not None
                        and selection_end is not None):
                    record_undo(undo_stack, document, formatting, alignments)
                    (document, formatting, alignments,
                     cursor_line, cursor_col
                     ) = delete_selection_rich(
                         document, formatting, alignments,
                         selection_start, selection_end)
                    selection_start = None
                    selection_end = None
                    selecting = False
                    insert_line, insert_col = cursor_line, cursor_col

                old_scroll = scroll_row
                (document, formatting, cursor_line, cursor_col
                 ) = insert_character_rich(
                     document, formatting, cursor_line, cursor_col,
                     char, typing_attrs)

                record_insert(insert_line, insert_col, char)

                while len(alignments) < len(document):
                    alignments.append(ALIGN_LEFT)
                alignments = alignments[:len(document)]

                scroll_row = adjust_scroll(
                    document, cursor_line, cursor_col,
                    text_width, visible_rows, scroll_row
                )
                if scroll_row != old_scroll:
                    full_redraw = True

    finally:
        profile.dump()
        if export_state is not None:
            try:
                export_state["proc"].terminate()
            except Exception:
                pass
        disable_mouse_tracking()


def main():
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]

    try:
        curses.wrapper(lambda stdscr: editor(stdscr, path))
    except KeyboardInterrupt:
        pass

