#!/usr/bin/env bash
# Build lightwrite_VERSION_amd64.deb from the Go binary (run on Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(grep -E '^Version:' "$ROOT/packaging/debian/control" | awk '{print $2}')"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/lightwrite-deb.XXXXXX")"
PKG_ROOT="$STAGE/lightwrite_${VERSION}"
DIST="$ROOT/dist"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

mkdir -p \
  "$PKG_ROOT/DEBIAN" \
  "$PKG_ROOT/usr/bin" \
  "$PKG_ROOT/usr/share/applications" \
  "$PKG_ROOT/usr/share/pixmaps" \
  "$PKG_ROOT/usr/share/doc/lightwrite" \
  "$DIST"

export CGO_ENABLED=0
GOOS=linux GOARCH=amd64 go build -C "$ROOT/go" -ldflags="-s -w" \
  -o "$PKG_ROOT/usr/bin/lightwrite" ./cmd/lightwrite
chmod 0755 "$PKG_ROOT/usr/bin/lightwrite"

install -m 0644 "$ROOT/packaging/debian/control" "$PKG_ROOT/DEBIAN/control"
if [[ -f "$ROOT/packaging/debian/postinst" ]]; then
  install -m 0755 "$ROOT/packaging/debian/postinst" "$PKG_ROOT/DEBIAN/postinst"
fi

install -m 0644 "$ROOT/packaging/lightwrite.desktop" "$PKG_ROOT/usr/share/applications/lightwrite.desktop"
install -m 0644 "$ROOT/packaging/lightwrite.png" "$PKG_ROOT/usr/share/pixmaps/lightwrite.png"
install -m 0644 "$ROOT/packaging/copyright" "$PKG_ROOT/usr/share/doc/lightwrite/copyright"
install -m 0644 "$ROOT/CHANGELOG.md" "$PKG_ROOT/usr/share/doc/lightwrite/changelog"
gzip -9fn "$PKG_ROOT/usr/share/doc/lightwrite/changelog"

INSTALLED_SIZE="$(du -sk "$PKG_ROOT" | awk '{print $1}')"
if ! grep -q '^Installed-Size:' "$PKG_ROOT/DEBIAN/control"; then
  printf 'Installed-Size: %s\n' "$INSTALLED_SIZE" >> "$PKG_ROOT/DEBIAN/control"
fi

OUT="$DIST/lightwrite_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT"
echo "Built $OUT"
