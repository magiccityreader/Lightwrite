import re
import shutil
import subprocess


def _spell_tool():
    if shutil.which("hunspell"):
        return "hunspell"
    if shutil.which("aspell"):
        return "aspell"
    return None


def _dicts_for(lang):
    if lang == "es":
        return ["es_ES", "es_MX", "es", "es-ES"]
    return ["en_US", "en_GB", "en", "en-US"]


_WORD_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", re.UNICODE)


def run_spell_check(text, lang):
    tool = _spell_tool()
    if not tool:
        return None

    misspelled = set()
    ok = False
    for dict_name in _dicts_for(lang):
        try:
            if tool == "hunspell":
                cmd = ["hunspell", "-l", "-d", dict_name]
            else:
                cmd = ["aspell", "list", "--lang=" + dict_name]
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15
            )
            if result.returncode == 0:
                for line in result.stdout.decode(
                        "utf-8", errors="replace").splitlines():
                    w = line.strip()
                    if w:
                        misspelled.add(w.lower())
                ok = True
                break
        except Exception:
            continue

    if not ok:
        return None

    positions = []
    for m in _WORD_PATTERN.finditer(text):
        if m.group().lower() in misspelled:
            positions.append((m.start(), m.end()))
    return positions


def get_suggestions(word, lang):
    tool = _spell_tool()
    if not tool:
        return []
    for dict_name in _dicts_for(lang):
        try:
            if tool == "hunspell":
                cmd = ["hunspell", "-a", "-d", dict_name]
            else:
                cmd = ["aspell", "-a", "--lang=" + dict_name]
            result = subprocess.run(
                cmd,
                input=(word + "\n").encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.decode("utf-8", errors="replace")
                for line in output.splitlines():
                    if line.startswith("&"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            sugs = [s.strip()
                                    for s in parts[1].split(",")]
                            return [s for s in sugs if s][:5]
                    if line.startswith("#"):
                        return []
                return []
        except Exception:
            continue
    return []

