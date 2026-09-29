import os
import shutil
import subprocess
import tempfile
import time

from lightwrite.i18n import tr
from lightwrite.rtf import save_rtf


def _filesystem_dirs_for(*paths):
    """Unique absolute directories needed for Flatpak LibreOffice access."""
    dirs = []
    seen = set()
    for path in paths:
        if not path:
            continue
        abspath = os.path.abspath(os.path.expanduser(path))
        directory = abspath if os.path.isdir(abspath) else os.path.dirname(abspath)
        if not directory or directory in seen:
            continue
        seen.add(directory)
        dirs.append(directory)
    return dirs


def find_libreoffice(extra_paths=None):
    native = shutil.which("soffice") or shutil.which("libreoffice")
    if native:
        return [native]
    if shutil.which("flatpak"):
        try:
            check = subprocess.run(
                ["flatpak", "info", "org.libreoffice.LibreOffice"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            if check.returncode == 0:
                cmd = ["flatpak", "run", "--filesystem=/tmp"]
                for directory in _filesystem_dirs_for(*(extra_paths or ())):
                    cmd.append("--filesystem=" + directory)
                cmd.append("org.libreoffice.LibreOffice")
                return cmd
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def convert_with_libreoffice(input_path, output_ext, output_dir=None):
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="lightwrite_conv_")

    base_cmd = find_libreoffice([input_path, output_dir])
    if not base_cmd:
        return False, None, "LibreOffice no instalado"

    try:
        subprocess.run(
            base_cmd + [
                "--headless", "--norestore",
                "--convert-to", output_ext,
                "--outdir", output_dir, input_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90
        )
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_path = os.path.join(output_dir, base + "." + output_ext)
        if os.path.exists(out_path):
            return True, out_path, None
        return False, None, "Conversión fallida"
    except Exception as e:
        return False, None, str(e)[:60]


def start_pdf_export(document, formatting, alignments, rtf_path):
    if rtf_path:
        pdf_path = os.path.splitext(rtf_path)[0] + ".pdf"
    else:
        pdf_path = os.path.expanduser("~/lightwrite/documento.pdf")

    out_dir = os.path.dirname(os.path.abspath(pdf_path)) or "."
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError:
        return None, tr("No se puede crear carpeta")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="lightwrite_pdf_")
        tmp_rtf = os.path.join(tmp_dir, "doc.rtf")
        save_rtf(document, formatting, alignments, tmp_rtf)

        base_cmd = find_libreoffice([tmp_rtf, tmp_dir, pdf_path])
        if not base_cmd:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None, tr("LibreOffice no instalado")

        proc = subprocess.Popen(
            base_cmd + [
                "--headless", "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmp_dir, tmp_rtf
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        state = {
            "proc": proc,
            "tmp_dir": tmp_dir,
            "pdf_path": pdf_path,
            "started_at": time.monotonic(),
        }
        return state, None
    except Exception as e:
        return None, tr("Error: ") + str(e)[:40]


def poll_pdf_export(state):
    proc = state["proc"]
    ret = proc.poll()
    if ret is None:
        return False, None, None

    tmp_dir = state["tmp_dir"]
    pdf_path = state["pdf_path"]

    try:
        proc.communicate(timeout=2)
    except Exception:
        pass

    generated = os.path.join(tmp_dir, "doc.pdf")

    if os.path.exists(generated):
        try:
            shutil.copy(generated, pdf_path)
            result = (True, True,
                      tr("PDF: %s") % os.path.basename(pdf_path))
        except Exception as e:
            result = (True, False,
                      tr("Error al copiar: ") + str(e)[:30])
    else:
        result = (True, False, tr("Error al generar PDF"))

    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return result


def start_docx_save(document, formatting, alignments, target_path):
    out_dir = os.path.dirname(os.path.abspath(target_path)) or "."
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError:
        return None, tr("No se puede crear carpeta")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="lightwrite_docxsave_")
        tmp_rtf = os.path.join(tmp_dir, "doc.rtf")
        save_rtf(document, formatting, alignments, tmp_rtf)

        base_cmd = find_libreoffice([tmp_rtf, tmp_dir, target_path])
        if not base_cmd:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None, tr("LibreOffice no instalado")

        proc = subprocess.Popen(
            base_cmd + [
                "--headless", "--norestore",
                "--convert-to", "docx",
                "--outdir", tmp_dir, tmp_rtf
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        state = {
            "proc": proc,
            "tmp_dir": tmp_dir,
            "target_path": target_path,
            "started_at": time.monotonic(),
        }
        return state, None
    except Exception as e:
        return None, tr("Error: ") + str(e)[:40]


def poll_docx_save(state):
    proc = state["proc"]
    ret = proc.poll()
    if ret is None:
        return False, None, None

    tmp_dir = state["tmp_dir"]
    target_path = state["target_path"]

    try:
        proc.communicate(timeout=2)
    except Exception:
        pass

    generated = os.path.join(tmp_dir, "doc.docx")

    if os.path.exists(generated):
        try:
            shutil.copy(generated, target_path)
            result = (True, True,
                      tr("Guardado: %s")
                      % os.path.basename(target_path))
        except Exception as e:
            result = (True, False,
                      tr("Error al copiar: ") + str(e)[:30])
    else:
        result = (True, False, tr("Error al guardar .docx"))

    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return result

