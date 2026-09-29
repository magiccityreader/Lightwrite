import gettext
import os
import sys


def get_locale_dir():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "locale")


def current_language():
    config_path = os.path.expanduser("~/.config/lightwrite/language")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            pref = f.read().strip().lower()
            if pref in ("es", "en"):
                return pref
    except Exception:
        pass

    forced = os.environ.get("LIGHTWRITE_LANG", "").strip().lower()
    if forced in ("es", "en"):
        return forced
    # Compat with upstream Underwood env name
    forced = os.environ.get("UNDERWOOD_LANG", "").strip().lower()
    if forced in ("es", "en"):
        return forced

    lang = os.environ.get("LANG", "").strip().lower()
    if lang.startswith("en"):
        return "en"

    return "es"


def save_language_preference(code):
    config_dir = os.path.expanduser("~/.config/lightwrite")
    config_path = os.path.join(config_dir, "language")
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(code)
        return True
    except Exception:
        return False


def load_text_doc(name):
    lang = current_language()
    base = get_locale_dir()
    for candidate_lang in (lang, "es"):
        path = os.path.join(base, f"{name}.{candidate_lang}.txt")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return "(texto no disponible)"


def setup_i18n():
    lang = current_language()
    os.environ["LANGUAGE"] = lang
    try:
        os.environ.setdefault("LANG", f"{lang}_{lang.upper()}.UTF-8")
    except Exception:
        pass

    local_path = get_locale_dir()
    candidates = [
        local_path,
        os.path.expanduser("~/.local/share/locale"),
        "/usr/local/share/locale",
        "/usr/share/locale",
    ]
    chosen = "/usr/share/locale"
    for path in candidates:
        found = False
        for lc in ("en", "es"):
            mo = os.path.join(path, lc, "LC_MESSAGES", "lightwrite.mo")
            if os.path.isfile(mo):
                chosen = path
                found = True
                break
        if found:
            break

    try:
        gettext.bindtextdomain("lightwrite", chosen)
        gettext.textdomain("lightwrite")
        return gettext.gettext
    except Exception:
        return lambda s: s


_EN_FALLBACK = {
    "Archivo": "File",
    "Edición": "Edit",
    "Formato": "Format",
    "Alineación": "Alignment",
    "Capítulos": "Add chapters",
    "Ayuda": "Help",
    "Idioma": "Language",
    "Salir": "Quit",
    "Nuevo documento": "New document",
    "Abrir documento…": "Open document…",
    "Guardar": "Save",
    "Guardar como…": "Save as…",
    "Guardar como .docx…": "Save as .docx…",
    "Exportar a PDF": "Export to PDF",
    "Seleccionar todo": "Select all",
    "Deshacer": "Undo",
    "Copiar": "Copy",
    "Cortar": "Cut",
    "Pegar": "Paste",
    "Buscar": "Find",
    "Reemplazar": "Replace",
    "Corrector ortográfico": "Spell checker",
    "Negrita": "Bold",
    "Cursiva": "Italic",
    "Subrayado": "Underline",
    "Izquierda": "Left",
    "Centrada": "Center",
    "Derecha": "Right",
    "Justificada": "Justify",
    "Salto de página": "Page break",
    "Crear capítulo": "Add chapter",
    "Crear sección": "Add section",
    "Crear subsección": "Add subsection",
    "Quitar nivel de título": "Remove heading level",
    "Mapa de capítulos": "Chapter map",
    "Nivel %d aplicado": "Level %d applied",
    "Nivel quitado": "Level removed",
    "Nuevo capítulo": "New chapter",
    "Saltado a: %s": "Jumped to: %s",
    "(sin capítulos — usa Capítulos → Insertar capítulo)":
        "(no chapters — use Add chapter → Chapter)",
    " ↑↓ mover · Enter ir · n: nuevo · Esc cerrar ":
        " ↑↓ move · Enter go · n: new · Esc close ",
    " Mapa de capítulos ": " Chapter map ",
    "Manual": "Manual",
    "Acerca de": "About",
    "Nombre (se guarda en ~/lightwrite/):":
        "Name (saved in ~/lightwrite/):",
    "Nombre para .docx (se guarda en ~/lightwrite/):":
        "Name for .docx (saved in ~/lightwrite/):",
    "Guardar como:": "Save as:",
    "Buscar:": "Find:",
    "Reemplazar con:": "Replace with:",
    "Abierto: %s": "Opened: %s",
    "Guardado: %s": "Saved: %s",
    "Error al guardar": "Error saving",
    "No se puede crear carpeta": "Cannot create folder",
    "Deshecho": "Undone",
    "Nada que deshacer": "Nothing to undo",
    "Copiado": "Copied",
    "Cortado": "Cut",
    "Pegado": "Pasted",
    "No encontrado": "Not found",
    "1 reemplazo": "1 replacement",
    "%d reemplazos": "%d replacements",
    "PDF: %s": "PDF: %s",
    "Exportando a PDF… %s": "Exporting to PDF… %s",
    "Guardando .docx… %s": "Saving .docx… %s",
    "Ya hay una exportación en curso": "An export is already running",
    "Ya hay un guardado en curso": "A save is already running",
    "LibreOffice no instalado": "LibreOffice not installed",
    "hunspell no instalado": "hunspell not installed",
    "Ortografía activada": "Spell check on",
    "Ortografía desactivada": "Spell check off",
    "Ortografía: ": "Spelling: ",
    "Ortografía ✓": "Spell ✓",
    "Ya estás en ese idioma": "Already in that language",
    "Seleccionado todo: %d líneas · %d palabras":
        "Selected all: %d lines · %d words",
    "Palabras: %d": "Words: %d",
    "Manual de Lightwrite": "Lightwrite Manual",
    "↑↓ desplazar  ·  Esc para volver":
        "↑↓ scroll  ·  Esc to go back",
    "Error: ": "Error: ",
    "Error al copiar: ": "Copy error: ",
    "Error al generar PDF": "Error generating PDF",
    "Error al guardar .docx": "Error saving .docx",
    " Enter: abrir  ·  Retroceso: subir  ·  Esc: cancelar ":
        " Enter: open  ·  Backspace: up  ·  Esc: cancel ",
    " Abrir documento ": " Open document ",
    "Herramientas: F9": "Tools: F9",
    "Selección: Shift→": "Selection: Shift→",
    "Selección: Ctrl+Space": "Selection: Ctrl+Space",
    "Selección iniciada": "Selection started",
    "Selección terminada": "Selection ended",
    "¿Sobrescribir %s? (s/n):": "Overwrite %s? (y/n):",
    "Cancelado": "Cancelled",
    "Sesión recuperada": "Session restored",
    "¿Salir sin guardar? (s/n):": "Quit without saving? (y/n):",
    "¿Descartar cambios? (s/n):": "Discard changes? (y/n):",
    "¿Descartar cambios y abrir? (s/n):":
        "Discard changes and open? (y/n):",
}


_gettext_fn = setup_i18n()


def tr(s):
    try:
        result = _gettext_fn(s)
    except Exception:
        result = s
    if result == s and s in _EN_FALLBACK:
        try:
            if current_language() == "en":
                return _EN_FALLBACK[s]
        except Exception:
            pass
    return result


MANUAL_TEXT = load_text_doc("manual")


ABOUT_TEXT = load_text_doc("about")

