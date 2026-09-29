"""Keyboard and mouse input for Lightwrite."""
import os
import select
import sys
import time

from lightwrite import state

def parse_mouse_sequence(sequence):
    try:
        text = sequence.decode("ascii", errors="ignore")
        if not text.startswith("\x1b[<"):
            return None
        final = text[-1]
        if final not in ("M", "m"):
            return None
        body = text[3:-1]
        parts = body.split(";")
        if len(parts) != 3:
            return None
        button = int(parts[0])
        x = int(parts[1]) - 1
        y = int(parts[2]) - 1
        return (button, x, y, final)
    except Exception:
        return None


def read_input_event(fd):
    first = os.read(fd, 1)
    if not first:
        return None

    if first == b"\x1b":
        sequence = bytearray(first)
        end_time = time.monotonic() + 0.08

        while time.monotonic() < end_time:
            ready, _r, _w = select.select([fd], [], [], 0.005)
            if not ready:
                continue
            data = os.read(fd, 1)
            if not data:
                break
            sequence.extend(data)
            if (len(sequence) >= 3
                    and sequence[1:2] in (b"[", b"O")
                    and sequence[2:3] in (b"A", b"B", b"C", b"D")):
                break
            if len(sequence) == 3 and sequence[1:2] == b"O":
                break
            if data == b"~":
                break
            if data in (b"M", b"m"):
                break
            if len(sequence) > 64:
                break

        mouse = parse_mouse_sequence(bytes(sequence))
        if mouse is not None:
            return ("mouse", mouse)

        data = bytes(sequence)

        # Shift + flechas / Inicio / Fin / RePág / AvPág
        # (extienden la selección; útiles sin ratón)
        if data in (b"\x1b[1;2A", b"\x1b[2A"):
            return ("key", "SELECT_UP")
        if data in (b"\x1b[1;2B", b"\x1b[2B"):
            return ("key", "SELECT_DOWN")
        if data in (b"\x1b[1;2C", b"\x1b[2C"):
            return ("key", "SELECT_RIGHT")
        if data in (b"\x1b[1;2D", b"\x1b[2D"):
            return ("key", "SELECT_LEFT")
        if data in (b"\x1b[1;2H", b"\x1b[2H"):
            return ("key", "SELECT_HOME")
        if data in (b"\x1b[1;2F", b"\x1b[2F"):
            return ("key", "SELECT_END")
        if data == b"\x1b[5;2~":
            return ("key", "SELECT_PAGE_UP")
        if data == b"\x1b[6;2~":
            return ("key", "SELECT_PAGE_DOWN")

        if data in (b"\x1b[A", b"\x1bOA"):
            return ("key", "UP")
        if data in (b"\x1b[B", b"\x1bOB"):
            return ("key", "DOWN")
        if data in (b"\x1b[C", b"\x1bOC"):
            return ("key", "RIGHT")
        if data in (b"\x1b[D", b"\x1bOD"):
            return ("key", "LEFT")
        if data == b"\x1b[3~":
            return ("key", "DELETE")
        if data == b"\x1b[5~":
            return ("key", "PAGE_UP")
        if data == b"\x1b[6~":
            return ("key", "PAGE_DOWN")
        if data in (b"\x1b[H", b"\x1bOH", b"\x1b[1~"):
            return ("key", "HOME")
        if data in (b"\x1b[F", b"\x1bOF", b"\x1b[4~"):
            return ("key", "END")

        # F2, F3, F4, F5 = niveles de título
        # (algunos terminales usan \x1bO?, otros \x1b[??~)
        if data in (b"\x1bOQ", b"\x1b[12~"):
            return ("key", "H1")
        if data in (b"\x1bOR", b"\x1b[13~"):
            return ("key", "H2")
        if data in (b"\x1bOS", b"\x1b[14~"):
            return ("key", "H3")
        if data == b"\x1b[17~":
            return ("key", "H0")

        # F9 = abrir menú con teclado
        if data == b"\x1b[20~":
            return ("key", "MENU")

        # F7 = corrector ortográfico
        if data == b"\x1b[18~":
            return ("key", "SPELL")

        if data in (b"\x1bb", b"\x1bB"):
            return ("key", "BOLD")
        if data in (b"\x1bi", b"\x1bI"):
            return ("key", "ITALIC")
        if data in (b"\x1bu", b"\x1bU"):
            return ("key", "UNDERLINE")

        return ("key", "ESC")

    # Ctrl+Space solo tiene sentido en consola pura (sin Xorg).
    # En una terminal dentro de Xorg, Shift+flechas y el ratón
    # ya cubren la selección, así que no lo interceptamos.
    if first == b"\x00" and state.TTY_MODE:
        return ("key", "MARK")
    if first == b"\x11":
        return ("key", "QUIT")
    if first == b"\x13":
        return ("key", "SAVE")
    if first == b"\x17":
        return ("key", "SAVE_AS")
    if first == b"\x03":
        return ("key", "COPY")
    if first == b"\x18":
        return ("key", "CUT")
    if first == b"\x16":
        return ("key", "PASTE")
    if first == b"\x02":
        return ("key", "BOLD")
    if first == b"\x09":
        return ("key", "ITALIC")
    if first == b"\x15":
        return ("key", "UNDERLINE")
    if first == b"\x06":
        return ("key", "FIND")
    if first == b"\x12":
        return ("key", "REPLACE")
    if first == b"\x10":
        return ("key", "PDF")
    if first == b"\x14":
        return ("key", "CHAPTERS")
    if first == b"\x07":
        return ("key", "HELP")
    if first == b"\x1a":
        return ("key", "UNDO")
    if first == b"\x0b":
        return ("key", "PAGEBREAK")
    if first == b"\x01":
        return ("key", "SELECT_ALL")
    if first == b"\x0e":
        return ("key", "NEW")
    if first == b"\x0f":
        return ("key", "OPEN")
    if first == b"\x08":
        return ("key", "ABOUT")

    if first == b"\x0c":
        return ("key", "ALIGN_LEFT")
    if first == b"\x05":
        return ("key", "ALIGN_CENTER")
    if first == b"\x04":
        return ("key", "ALIGN_RIGHT")
    if first == b"\x0a":
        return ("key", "ALIGN_JUSTIFY")

    if first in (b"\x7f", b"\x08"):
        return ("key", "BACKSPACE")
    if first in (b"\r", b"\n"):
        return ("key", "ENTER")

    expected = 1
    value = first[0]
    if value & 0xE0 == 0xC0:
        expected = 2
    elif value & 0xF0 == 0xE0:
        expected = 3
    elif value & 0xF8 == 0xF0:
        expected = 4

    data = bytearray(first)
    while len(data) < expected:
        part = os.read(fd, 1)
        if not part:
            break
        data.extend(part)

    try:
        char = bytes(data).decode("utf-8")
        if char:
            return ("char", char)
    except UnicodeDecodeError:
        pass

    return None


def has_pending_input(fd, timeout=0):
    try:
        r, _w, _x = select.select([fd], [], [], timeout)
        return bool(r)
    except Exception:
        return False


def enable_mouse_tracking():
    sys.stdout.write("\033[?1002h\033[?1006h")
    sys.stdout.flush()


def disable_mouse_tracking():
    sys.stdout.write("\033[?1002l\033[?1006l")
    sys.stdout.flush()



