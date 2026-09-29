# Changelog

All notable changes to Lightwrite are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/).
This project follows [Semantic Versioning](https://semver.org/).

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
