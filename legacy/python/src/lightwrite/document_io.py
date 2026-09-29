import os
import shutil
import tempfile

from lightwrite.constants import ALIGN_LEFT
from lightwrite.export import convert_with_libreoffice
from lightwrite.model import document_to_string, string_to_document
from lightwrite.rtf import parse_rtf, save_rtf


def load_document(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return [""], [[]], [ALIGN_LEFT]

    try:
        lower = path.lower()

        if lower.endswith((".docx", ".doc")):
            tmp_dir = tempfile.mkdtemp(prefix="lightwrite_docx_")
            try:
                ok, rtf_path, _err = convert_with_libreoffice(
                    path, "rtf", tmp_dir)
                if not ok:
                    return [""], [[]], [ALIGN_LEFT]
                with open(rtf_path, "r", encoding="ascii",
                          errors="replace") as f:
                    content = f.read()
                if content.lstrip().startswith("{\\rtf"):
                    return parse_rtf(content)
                doc = string_to_document(content)
                fmt = [[] for _i in doc]
                al = [ALIGN_LEFT for _i in doc]
                return doc, fmt, al
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        if lower.endswith(".rtf"):
            with open(path, "r", encoding="ascii",
                      errors="replace") as f:
                content = f.read()
            if content.lstrip().startswith("{\\rtf"):
                return parse_rtf(content)
            doc = string_to_document(content)
            fmt = [[] for _i in doc]
            al = [ALIGN_LEFT for _i in doc]
            return doc, fmt, al

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        doc = string_to_document(content)
        fmt = [[] for _i in doc]
        al = [ALIGN_LEFT for _i in doc]
        return doc, fmt, al

    except Exception:
        return [""], [[]], [ALIGN_LEFT]


def save_document(document, formatting, alignments, path):
    try:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        lower = path.lower()

        if lower.endswith(".rtf"):
            save_rtf(document, formatting, alignments, path)
            return True

        if lower.endswith((".docx", ".doc")):
            tmp_dir = tempfile.mkdtemp(prefix="lightwrite_docx_")
            try:
                tmp_rtf = os.path.join(tmp_dir, "doc.rtf")
                save_rtf(document, formatting, alignments, tmp_rtf)
                ext = "docx" if lower.endswith(".docx") else "doc"
                ok, out_path, _err = convert_with_libreoffice(
                    tmp_rtf, ext, tmp_dir
                )
                if not ok:
                    return False
                shutil.copy(out_path, path)
                return True
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(document_to_string(document))
        return True
    except OSError:
        return False

