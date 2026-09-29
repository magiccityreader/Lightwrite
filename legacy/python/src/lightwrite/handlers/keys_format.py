"""Heading, alignment, style and spell shortcuts."""
from __future__ import annotations
import time
from lightwrite.constants import ALIGN_CENTER, ALIGN_JUSTIFY, ALIGN_LEFT, ALIGN_RIGHT, BOLD, ITALIC, UNDERLINE
from lightwrite.i18n import tr
from lightwrite.model import absolute_to_position, apply_alignment, apply_attr_to_selection, document_to_string, selection_range, set_line_heading
from lightwrite.spell import _spell_tool

def handle_format_keys(ed, value):
    if value in ('H1', 'H2', 'H3', 'H0'):
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
        return True
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
        return True
    elif value in ('ALIGN_LEFT', 'ALIGN_CENTER', 'ALIGN_RIGHT', 'ALIGN_JUSTIFY'):
        ed.record_undo()
        new_align = {'ALIGN_LEFT': ALIGN_LEFT, 'ALIGN_CENTER': ALIGN_CENTER, 'ALIGN_RIGHT': ALIGN_RIGHT, 'ALIGN_JUSTIFY': ALIGN_JUSTIFY}[value]
        ed.alignments = apply_alignment(ed.document, ed.alignments, ed.cursor_line, ed.selection_start, ed.selection_end, new_align)
        labels = {'ALIGN_LEFT': tr('Izquierda'), 'ALIGN_CENTER': tr('Centrada'), 'ALIGN_RIGHT': tr('Derecha'), 'ALIGN_JUSTIFY': tr('Justificada')}
        ed.status_message = labels[value]
        ed.status_time = time.monotonic()
        return True
    elif value == 'BOLD':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, BOLD)
            ed.status_message = tr('Negrita')
        else:
            ed.typing_attrs ^= BOLD
            ed.status_message = tr('Negrita')
        ed.status_time = time.monotonic()
        return True
    elif value == 'ITALIC':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, ITALIC)
            ed.status_message = tr('Cursiva')
        else:
            ed.typing_attrs ^= ITALIC
            ed.status_message = tr('Cursiva')
        ed.status_time = time.monotonic()
        return True
    elif value == 'UNDERLINE':
        if ed.selection_start is not None and ed.selection_end is not None:
            ed.record_undo()
            ed.formatting = apply_attr_to_selection(ed.document, ed.formatting, ed.selection_start, ed.selection_end, UNDERLINE)
            ed.status_message = tr('Subrayado')
        else:
            ed.typing_attrs ^= UNDERLINE
            ed.status_message = tr('Subrayado')
        ed.status_time = time.monotonic()
        return True
    return False
