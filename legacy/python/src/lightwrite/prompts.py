"""Shared unsaved-document confirmation prompts."""
from __future__ import annotations

from lightwrite.i18n import tr

CONFIRM_QUIT = "confirm_quit"
CONFIRM_NEW = "confirm_new"
CONFIRM_OPEN = "confirm_open"

_YES = ("s", "si", "sí", "y", "yes")


def begin_confirm(mode_name: str) -> tuple[str, str, str]:
    """Return (mode, prompt_label, prompt_buffer)."""
    labels = {
        CONFIRM_QUIT: tr("¿Salir sin guardar? (s/n):"),
        CONFIRM_NEW: tr("¿Descartar cambios? (s/n):"),
        CONFIRM_OPEN: tr("¿Descartar cambios y abrir? (s/n):"),
    }
    return mode_name, labels[mode_name], ""


def is_confirm_mode(mode: str) -> bool:
    return mode in (CONFIRM_QUIT, CONFIRM_NEW, CONFIRM_OPEN)


def interpret_answer(buffer: str) -> bool | None:
    """True = yes, False = no, None = incomplete."""
    answer = buffer.strip().lower()
    if not answer:
        return None
    if answer in _YES:
        return True
    if answer in ("n", "no"):
        return False
    # Treat any other non-empty as no
    return False
