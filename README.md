# Lightwrite

A terminal word processor for creative writing — novels, essays, scripts.

**2.0** is a Go rewrite on the [Charm](https://charm.sh) stack (Bubble Tea, Lip Gloss, Bubbles).
The previous Python/curses app lives under [`legacy/python/`](legacy/python/).

## Install (Linux `.deb`)

```bash
./scripts/build-deb.sh
sudo apt install ./dist/lightwrite_2.0.0_amd64.deb
```

## Run from source

```bash
cd go
go run ./cmd/lightwrite [file.rtf]
# or
go build -o ../dist/lightwrite ./cmd/lightwrite
../dist/lightwrite
```

Requires a modern terminal (Windows Terminal + WSL, iTerm, GNOME Terminal, etc.).

Optional: `hunspell` (+ dictionaries), `xclip`/`xsel`, LibreOffice Writer.

## Tests

```bash
cd go && go test ./...
```

Legacy Python suite (still in CI):

```bash
cd legacy/python
PYTHONPATH=src python3 -m unittest discover -s tests -v
pip install pyte && python3 tests/smoke_pty.py
```

## Layout

| Path | Role |
|------|------|
| `go/cmd/lightwrite` | Entrypoint |
| `go/internal/doc` | Document model |
| `go/internal/undo` | Operation-log undo |
| `go/internal/layout` | Line wrap + cache |
| `go/internal/rtf` | RTF load/save |
| `go/internal/docio` | Files + LibreOffice export |
| `go/internal/ui` | Bubble Tea shell |
| `go/internal/i18n` | Spanish / English |
| `legacy/python/` | 1.2.x curses implementation |
| `packaging/` | Desktop entry, icon, Debian metadata |
| `scripts/build-deb.sh` | Assemble `.deb` from Go binary |

## License

GNU GPL v3 — see [LICENSE](LICENSE). Upstream copyright Silvestre Parbut (2026).
