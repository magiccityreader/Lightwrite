"""Save-as / save-as-docx prompt handlers."""
import os
import time
from lightwrite.document_io import save_document
from lightwrite.export import start_docx_save
from lightwrite.i18n import tr

def handle_save_as(ed, event_type, value):
    if ed.mode in ('save_as', 'save_as_docx'):
        if event_type == 'key':
            if value == 'ESC':
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
            elif value == 'BACKSPACE':
                ed.prompt_buffer = ed.prompt_buffer[:-1]
            elif value == 'ENTER':
                name = ed.prompt_buffer.strip()
                force_docx = ed.mode == 'save_as_docx'
                ed.mode = 'normal'
                ed.prompt_buffer = ''
                ed.prompt_label = ''
                if name:
                    if '/' in name or name.startswith('~'):
                        full_path = os.path.expanduser(name)
                    else:
                        full_path = os.path.expanduser(os.path.join('~/lightwrite', name))
                    lower = full_path.lower()
                    if not lower.endswith(('.rtf', '.txt', '.docx', '.doc')):
                        if force_docx:
                            full_path += '.docx'
                        else:
                            full_path += '.rtf'
                    if os.path.exists(full_path):
                        ed.pending_overwrite_path = full_path
                        ed.pending_overwrite_docx = force_docx or full_path.lower().endswith(('.docx', '.doc'))
                        ed.mode = 'confirm_overwrite'
                        ed.prompt_label = tr('¿Sobrescribir %s? (s/n):') % os.path.basename(full_path)
                        ed.prompt_buffer = ''
                        return True
                    directory = os.path.dirname(os.path.abspath(full_path))
                    if directory:
                        try:
                            os.makedirs(directory, exist_ok=True)
                        except OSError:
                            ed.status_message = tr('No se puede crear carpeta')
                            ed.status_time = time.monotonic()
                            return True
                    if full_path.lower().endswith(('.docx', '.doc')):
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
        elif event_type == 'char':
            if value and value != '\t':
                ed.prompt_buffer += value
        return True
    return False
