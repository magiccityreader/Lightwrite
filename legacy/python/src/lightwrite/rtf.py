from lightwrite.constants import (
    ALIGN_CENTER, ALIGN_JUSTIFY, ALIGN_LEFT, ALIGN_RIGHT,
    BOLD, H1, H2, H3, ITALIC, PAGE_BREAK, UNDERLINE,
)
from lightwrite.model import get_line_align


RTF_ALIGN = {
    ALIGN_LEFT:    r"\ql ",
    ALIGN_CENTER:  r"\qc ",
    ALIGN_RIGHT:   r"\qr ",
    ALIGN_JUSTIFY: r"\qj ",
}


def rtf_escape_char(ch):
    if ch == "\\":
        return "\\\\"
    if ch == "{":
        return "\\{"
    if ch == "}":
        return "\\}"
    code = ord(ch)
    if code < 128:
        return ch
    if code > 0xFFFF:
        code -= 0x10000
        high = 0xD800 + (code >> 10)
        low = 0xDC00 + (code & 0x3FF)
        if high > 32767:
            high -= 65536
        if low > 32767:
            low -= 65536
        return "\\u%d?\\u%d?" % (high, low)
    if code > 32767:
        code -= 65536
    return "\\u%d?" % code


def save_rtf(document, formatting, alignments, path):
    parts = []
    parts.append(r"{\rtf1\ansi\ansicpg1252\deff0")
    parts.append(r"{\fonttbl{\f0\froman Times New Roman;}}")
    parts.append(r"\viewkind4\uc1\f0\fs24 ")

    cur_b = False
    cur_i = False
    cur_u = False

    def close_styles():
        nonlocal cur_b, cur_i, cur_u
        if cur_b:
            parts.append(r"\b0 ")
            cur_b = False
        if cur_i:
            parts.append(r"\i0 ")
            cur_i = False
        if cur_u:
            parts.append(r"\ul0 ")
            cur_u = False

    for i, line in enumerate(document):
        if i < len(formatting):
            fmt_line = formatting[i]
        else:
            fmt_line = [0] * len(line)

        align = get_line_align(alignments, i)
        parts.append(r"\pard" + RTF_ALIGN[align])

        if line == PAGE_BREAK:
            close_styles()
            parts.append(r"\page ")
            continue

        heading_level = 0
        if fmt_line:
            first_attrs = fmt_line[0]
            if first_attrs & H1:
                heading_level = 1
            elif first_attrs & H2:
                heading_level = 2
            elif first_attrs & H3:
                heading_level = 3

        if heading_level > 0:
            parts.append("\\outlinelevel%d " % (heading_level - 1))

        for j, ch in enumerate(line):
            if ch == PAGE_BREAK:
                close_styles()
                parts.append(r"\page ")
                continue

            attrs = fmt_line[j] if j < len(fmt_line) else 0
            b = bool(attrs & BOLD) or (heading_level > 0)
            it = bool(attrs & ITALIC) or (heading_level == 3)
            u = bool(attrs & UNDERLINE) or (heading_level == 1)

            if b != cur_b:
                parts.append(r"\b " if b else r"\b0 ")
                cur_b = b
            if it != cur_i:
                parts.append(r"\i " if it else r"\i0 ")
                cur_i = it
            if u != cur_u:
                parts.append(r"\ul " if u else r"\ul0 ")
                cur_u = u

            parts.append(rtf_escape_char(ch))

        parts.append("\\par\n")

    if cur_b:
        parts.append(r"\b0 ")
    if cur_i:
        parts.append(r"\i0 ")
    if cur_u:
        parts.append(r"\ul0 ")

    parts.append("}")
    with open(path, "w", encoding="ascii", errors="ignore") as f:
        f.write("".join(parts))


def parse_rtf(text):
    document = [""]
    formatting = [[]]
    alignments = []
    style = [False, False, False]
    style_stack = []
    cur_align = ALIGN_LEFT
    cur_outline = 0
    uc = 1
    group_skip = []

    def current_attrs():
        a = 0
        if style[0]:
            a |= BOLD
        if style[1]:
            a |= ITALIC
        if style[2]:
            a |= UNDERLINE
        if cur_outline == 1:
            a |= H1
        elif cur_outline == 2:
            a |= H2
        elif cur_outline == 3:
            a |= H3
        return a

    def add_char(ch):
        document[-1] += ch
        formatting[-1].append(current_attrs())

    def add_newline():
        nonlocal cur_outline
        alignments.append(cur_align)
        document.append("")
        formatting.append([])
        cur_outline = 0

    i = 0
    n = len(text)
    skip_words = (
        "fonttbl", "colortbl", "stylesheet",
        "info", "pict", "header", "footer",
        "footnote", "filetbl", "listtable",
        "listoverridetable", "rsidtbl",
        "generator", "xmlnstbl"
    )

    while i < n:
        c = text[i]

        if c == "{":
            style_stack.append(tuple(style))
            j = i + 1
            will_skip = False
            if j < n and text[j] == "\\":
                if j + 1 < n and text[j + 1] == "*":
                    will_skip = True
                else:
                    k = j + 1
                    word = ""
                    while k < n and text[k].isalpha():
                        word += text[k]
                        k += 1
                    if word in skip_words:
                        will_skip = True
            group_skip.append(will_skip)
            i += 1

        elif c == "}":
            if style_stack:
                saved = style_stack.pop()
                style[0], style[1], style[2] = saved
            if group_skip:
                group_skip.pop()
            i += 1

        elif any(group_skip):
            i += 1

        elif c == "\\":
            i += 1
            if i >= n:
                break
            nc = text[i]

            if nc in ("\\", "{", "}"):
                add_char(nc)
                i += 1

            elif nc == "'":
                if i + 2 < n:
                    hex_str = text[i + 1:i + 3]
                    try:
                        code = int(hex_str, 16)
                        try:
                            ch = bytes([code]).decode("cp1252")
                        except Exception:
                            ch = chr(code)
                        add_char(ch)
                    except ValueError:
                        pass
                    i += 3
                else:
                    i += 1

            elif nc.isalpha():
                word = ""
                while i < n and text[i].isalpha():
                    word += text[i]
                    i += 1

                sign = 1
                if i < n and text[i] == "-":
                    sign = -1
                    i += 1

                num = ""
                while i < n and text[i].isdigit():
                    num += text[i]
                    i += 1

                has_param = bool(num)
                param = sign * int(num) if has_param else None

                if i < n and text[i] == " ":
                    i += 1

                if word == "u":
                    if has_param:
                        code = param
                        if code < 0:
                            code += 65536
                        try:
                            add_char(chr(code))
                        except (ValueError, OverflowError):
                            pass
                    skipped = 0
                    while skipped < uc and i < n:
                        c2 = text[i]
                        if c2 in ("{", "}"):
                            break
                        if c2 == "\\" and i + 1 < n and text[i + 1] == "'":
                            i += 4
                            skipped += 1
                        elif c2 == "\\" and i + 1 < n and text[i + 1].isalpha():
                            i += 2
                            while i < n and text[i].isalpha():
                                i += 1
                            if i < n and text[i] == "-":
                                i += 1
                            while i < n and text[i].isdigit():
                                i += 1
                            if i < n and text[i] == " ":
                                i += 1
                            skipped += 1
                        else:
                            i += 1
                            skipped += 1

                elif word in ("par", "line"):
                    add_newline()
                elif word == "page":
                    if document[-1] != "":
                        add_newline()
                    add_char(PAGE_BREAK)
                    add_newline()
                elif word == "pard":
                    cur_align = ALIGN_LEFT
                    cur_outline = 0
                elif word == "ql":
                    cur_align = ALIGN_LEFT
                elif word == "qc":
                    cur_align = ALIGN_CENTER
                elif word == "qr":
                    cur_align = ALIGN_RIGHT
                elif word == "qj":
                    cur_align = ALIGN_JUSTIFY
                elif word == "outlinelevel":
                    if has_param and 0 <= param <= 2:
                        cur_outline = param + 1
                elif word == "b":
                    style[0] = True if param is None else (param != 0)
                elif word == "i":
                    style[1] = True if param is None else (param != 0)
                elif word == "ul":
                    style[2] = True if param is None else (param != 0)
                elif word == "ulnone":
                    style[2] = False
                elif word == "uc":
                    if has_param:
                        uc = max(0, param)
            else:
                i += 1

        elif c in ("\r", "\n"):
            i += 1

        else:
            add_char(c)
            i += 1

    alignments.append(cur_align)
    if len(document) > 1 and document[-1] == "" and not formatting[-1]:
        document.pop()
        formatting.pop()
        alignments.pop()

    while len(alignments) < len(document):
        alignments.append(ALIGN_LEFT)
    alignments = alignments[:len(document)]
    return document, formatting, alignments

