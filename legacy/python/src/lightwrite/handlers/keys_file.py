"""File / quit / language / export shortcuts."""
from __future__ import annotations
import curses
import os
import sys
import time
import lightwrite
from lightwrite.constants import ALIGN_LEFT, SESSION_RTF
from lightwrite.document_io import save_document
from lightwrite.export import start_pdf_export
from lightwrite.i18n import current_language, save_language_preference, tr
from lightwrite.input import disable_mouse_tracking
from lightwrite.prompts import (
    CONFIRM_NEW, CONFIRM_OPEN, CONFIRM_QUIT, begin_confirm,
)
from lightwrite.ui_draw import list_directory

def handle_new_open(ed, value):
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
    return False

def handle_file_keys(ed, value):
    if value == 'QUIT':
        if ed.doc_dirty and (not ed.pending_quit):
            ed.pending_quit = True
            ed.mode, ed.prompt_label, ed.prompt_buffer = begin_confirm(CONFIRM_QUIT)
            ed.full_redraw = True
            return True
        return 'quit'
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
            pkg_dir = os.path.dirname(os.path.abspath(lightwrite.__file__))
            src_dir = os.path.dirname(pkg_dir)
            entry = os.path.join(src_dir, 'lightwrite.py')
            if os.path.isfile(entry):
                new_argv = [sys.executable, entry, save_path]
            else:
                new_argv = [sys.executable, '-m', 'lightwrite', save_path]
        os.execv(sys.executable, new_argv)
        return True
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
        return True
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
        return True
    elif value == 'SAVE_AS':
        ed.mode = 'save_as'
        ed.prompt_label = tr('Nombre (se guarda en ~/lightwrite/):')
        if ed.current_path:
            base = os.path.basename(ed.current_path)
            ed.prompt_buffer = os.path.splitext(base)[0]
        else:
            ed.prompt_buffer = ''
        return True
    elif value == 'SAVE_AS_DOCX':
        ed.mode = 'save_as_docx'
        ed.prompt_label = tr('Nombre para .docx (se guarda en ~/lightwrite/):')
        if ed.current_path:
            base = os.path.basename(ed.current_path)
            ed.prompt_buffer = os.path.splitext(base)[0]
        else:
            ed.prompt_buffer = ''
        return True
    return False
