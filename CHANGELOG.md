# Changelog

All notable changes to Lightwrite are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).
This project follows [Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-09-29

### Changed
- **Go + Charm rewrite.** The editor is now Bubble Tea + Lip Gloss + Bubbles.
  Document core (`doc`, `undo`, `layout`, `rtf`) ports the 1.2 Python packages
  with the same RTF format and keybindings.
- Debian package ships a static amd64 Go binary (`Architecture: amd64`).
- Python/curses 1.2.x archived under `legacy/python/` (still tested in CI).

### Added
- Lip Gloss theme (page, chrome, selection, menus).
- `go test ./...` coverage for doc, undo, layout, RTF, and smoke checklist.

## [1.2.0] — 2026-09-29

### Changed
- The editor loop is split into an `EditorState` session object and handler
  modules under `src/lightwrite/handlers/` (chapters, help, browse, save-as,
  confirms, search, mouse, keys, typing). Keyboard shortcuts are further
  split into `keys_menu`, `keys_file`, `keys_format`, `keys_edit` and
  `keys_nav`. `app.py` is the redraw/input shell.
- Undo is an operation log: typing records inserts, and consecutive
  characters in a word undo as one step. Backspace, Delete and Enter snapshot
  only the one or two lines they touch instead of the whole document.
- Line-wrap layout is cached per document version and width, so cursor moves
  and redraws no longer re-wrap the document.
- Quit, New and Open share one unsaved-changes prompt. A successful DOCX save
  clears the unsaved flag.
- `LIGHTWRITE_PROFILE=1` prints edit/spell/redraw timing totals on exit.

### Added
- GitHub Actions CI: pyflakes, unit tests, and a pyte-backed pty smoke suite
  (16 scenarios) that drives the real editor; `.deb` build on `v*` tags.
- Tests for operation-log undo and the layout cache.

## [1.1.0] — 2026-09-29

### Changed
- Split the monolith into a `lightwrite` Python package (`i18n`, `model`,
  `layout`, `rtf`, `export`, `spell`, `ui_draw`, `input`, `app`).
- Undo uses shallow line-range snapshots instead of `copy.deepcopy`.
- Plain-text cache for spell-check / status avoids rejoining the document
  every frame.
- Typing can skip a full-screen erase (partial redraw of chrome).
- Format toggles and single-line deletes avoid full cell-list round-trips.
- Prompt before quit / New when the document has unsaved changes.
- Unit tests for undo, cache, attrs, and RTF round-trip (`tests/`).
- Dropped the 1.2 MB demo GIF from the repo; screenshots remain.

## [1.0.0] — 2026-09-29

### Changed (magiccityreader — Lightwrite)

- Renamed the product from Underwood to **Lightwrite** (binary, package,
  config dir `~/.config/lightwrite`, docs dir `~/lightwrite`).
- Repository is a normal source tree (`src/`, `packaging/`, `scripts/`) instead of
  shipping multi‑megabyte release tarballs that embedded a full Python venv and
  PyInstaller binary.
- Flatpak LibreOffice conversions no longer request `--filesystem=home`; only
  `/tmp` and the directories of the files being converted are exposed.
- Language switch recovery for unsaved documents uses
  `~/.config/lightwrite/session.rtf` instead of silently overwriting
  `~/lightwrite/documento.rtf`.
- Save-as asks before overwriting an existing file (`s`/`y` or `n`).
- Save / folder-creation failures catch `OSError` more narrowly on critical paths.

### Notes

- Based on upstream Underwood 2.6.x (headings, Hunspell, bilingual UI,
  DOCX/PDF export). Entries below for 2.0–2.1 are from upstream Underwood;
  intermediate 2.2–2.6 upstream notes were not published in-repo.


## [2.1.0] — 2026-09-26

### Added
- Bilingual interface (Spanish / English) with Language menu; preference stored in
  `~/.config/lightwrite/language`.
- Manual and About as external locale text files.
- New icon for 2.1.

### Changed
- `.deb` appears under Office; bilingual package description.
- Language priority: config file → `LIGHTWRITE_LANG` → `LANG` → Spanish default.
- Autosave document when switching language so unsaved work is not lost.

### Fixed
- Faster `Ctrl+A` selection on large documents.
- Mouse-drag selection no longer stalls when many events queue up.


## [2.0.0] — 2026-09-25

### Added
- Top menu bar with mouse support.
- Paragraph alignment (left/center/right/justify) with RTF `\ql`/`\qc`/`\qr`/`\qj`.
- Page break (`Ctrl+K`) as RTF `\page`.
- In-terminal file browser (`Ctrl+O`).
- Async PDF export with progress spinner.
- Status bar (word count, active format, messages).
- Manual (`Ctrl+G`) and About (`Ctrl+H`).
- Mouse selection and wheel/trackpad scroll.
- Undo (`Ctrl+Z`), Select all (`Ctrl+A`).
- MIME association for `.rtf`.
- Installable `.deb` with icon and desktop launcher.

### Changed
- Selection rendering optimized; mouse reporting uses mode `1002`.
- Content width centered at 80 columns.

### Fixed
- Spanish characters no longer duplicated when reading LibreOffice RTF `\uN`.
- Format changes inside RTF groups `{...}` revert correctly when groups close.


## [1.0.0] — 2026-09-25

### Added
- First public release: rich-text terminal editor.
- Bold / italic / underline, find (`Ctrl+F`), replace (`Ctrl+R`).
- Cut / copy / paste via `xclip` or `xsel`.
- Save as `.rtf`; PDF export via LibreOffice.
- Spanish UI; Debian/Ubuntu/Mint `.deb`.
