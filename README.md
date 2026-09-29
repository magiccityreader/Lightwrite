# Lightwrite

Terminal word processor for Debian and derivatives (curses + RTF).
Fork of [SilvestreParbut/Underwood](https://github.com/SilvestreParbut/Underwood)
maintained at [magiccityreader/Lightwrite](https://github.com/magiccityreader/Lightwrite).

Inspired by WordPerfect, MS-Word 6.0 for DOS, and the Underwood Standard No. 5.

![start](assets/screenshots/start.png)

## Features

- Bold, italic, underline, headings, page breaks, alignment
- Native `.rtf` (also `.txt`; `.docx` / PDF via LibreOffice)
- Mouse selection / scroll, or keyboard-only (`Shift`+arrows, `F9` menus)
- Hunspell spell-check (optional), find/replace, bilingual UI (es/en)

## Run from source

```bash
python3 src/lightwrite.py
# or:
PYTHONPATH=src python3 -m lightwrite
# open a file:
python3 src/lightwrite.py ~/notes/draft.rtf
```

Optional: `hunspell` (+ dictionaries), `xclip`/`xsel`, LibreOffice Writer.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
pip install pyte && python3 tests/smoke_pty.py   # drives the real editor (Linux)
LIGHTWRITE_PROFILE=1 python3 src/lightwrite.py   # timing totals on exit
```

CI (GitHub Actions) runs pyflakes, the unit tests, and the pty smoke test on
Python 3.8 and 3.12. Pushing a `v*` tag also builds the `.deb` and attaches it
to the release.

## Build a `.deb` (Linux)

```bash
./scripts/build-deb.sh
sudo apt install ./dist/lightwrite_1.2.0_all.deb
```

## Layout

| Path | Role |
|------|------|
| `src/lightwrite.py` | Entrypoint |
| `src/lightwrite/` | Application package |
| `src/lightwrite/handlers/` | Modal and input handlers |
| `src/lightwrite/session.py` | `EditorState` shared by the loop |
| `src/lightwrite/locale/` | Manual / About text (es + en) |
| `packaging/` | Desktop entry, icon, Debian metadata |
| `scripts/build-deb.sh` | Assemble `.deb` from source |
| `tests/` | Unit tests (no curses) + pty smoke test |
| `.github/workflows/ci.yml` | Lint, tests, smoke; `.deb` on tags |
| `assets/screenshots/` | UI screenshots |

Release tarballs and PyInstaller/venv trees are **not** kept in git.

## License

GNU GPL v3 — see [LICENSE](LICENSE). Upstream copyright Silvestre Parbut (2026).
