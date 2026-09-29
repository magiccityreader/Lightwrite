"""Overwrite-confirmation prompt handlers."""
import os
import time
from lightwrite.document_io import save_document
from lightwrite.export import start_docx_save
from lightwrite.i18n import tr

def handle_confirm_overwrite(ed, event_type, value):
    if ed.mode == 'confirm_overwrite':
        if event_type == 'key':
            if value == 'ESC':
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
                ed.pending_overwrite_path = ''
                ed.status_message = tr('Cancelado')
                ed.status_time = time.monotonic()
            elif value == 'BACKSPACE':
                ed.prompt_buffer = ed.prompt_buffer[:-1]
            elif value == 'ENTER':
                answer = ed.prompt_buffer.strip().lower()
                full_path = ed.pending_overwrite_path
                as_docx = ed.pending_overwrite_docx
                ed.prompt_buffer = ''
                ed.prompt_label = ''
                ed.pending_overwrite_path = ''
                ed.mode = 'normal'
                if answer in ('s', 'si', 'sí', 'y', 'yes'):
                    if as_docx or full_path.lower().endswith(('.docx', '.doc')):
                        if ed.export_state is not None:
                            ed.status_message = tr('Ya hay un guardado en curso')
                            ed.status_time = time.monotonic()
                        else:
                            job, err = start_docx_save(ed.document, ed.formatting, ed.alignments, full_path)
                            if job is None:
                                ed.status_message = err
                                ed.status_time = time.monotonic()
                            else:
                                ed.current_path = full_path
                                ed.export_state = job
                                ed.export_kind = 'docx'
                                ed.export_frames = 0
                                ed.status_message = ''
                                ed.status_time = 0
                    else:
                        if save_document(ed.document, ed.formatting, ed.alignments, full_path):
                            ed.current_path = full_path
                            ed.doc_dirty = False
                            ed.status_message = tr('Guardado: %s') % os.path.basename(full_path)
                        else:
                            ed.status_message = tr('Error al guardar')
                        ed.status_time = time.monotonic()
                else:
                    ed.status_message = tr('Cancelado')
                    ed.status_time = time.monotonic()
        elif event_type == 'char':
            if value and value != '\t':
                ch = value.lower()
                if ch in ('s', 'n', 'y'):
                    ed.prompt_buffer = ch
                elif value.isalpha() and len(ed.prompt_buffer) < 3:
                    ed.prompt_buffer += value
        return True
    return False
