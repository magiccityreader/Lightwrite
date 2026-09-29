#!/usr/bin/env bash
# Build lightwrite_VERSION_all.deb from the source tree (run on Linux/Debian).
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
  "$PKG_ROOT/usr/share/lightwrite/locale" \
  "$PKG_ROOT/usr/share/applications" \
  "$PKG_ROOT/usr/share/pixmaps" \
  "$PKG_ROOT/usr/share/doc/lightwrite" \
  "$DIST"

install -m 0755 "$ROOT/packaging/debian/postinst" "$PKG_ROOT/DEBIAN/postinst"
install -m 0644 "$ROOT/packaging/debian/control" "$PKG_ROOT/DEBIAN/control"
install -m 0755 "$ROOT/packaging/lightwrite" "$PKG_ROOT/usr/bin/lightwrite"
install -m 0644 "$ROOT/src/lightwrite.py" "$PKG_ROOT/usr/share/lightwrite/lightwrite.py"
install -m 0644 "$ROOT/src/locale/"*.txt "$PKG_ROOT/usr/share/lightwrite/locale/"
install -m 0644 "$ROOT/packaging/lightwrite.desktop" "$PKG_ROOT/usr/share/applications/lightwrite.desktop"
install -m 0644 "$ROOT/packaging/lightwrite.png" "$PKG_ROOT/usr/share/pixmaps/lightwrite.png"
install -m 0644 "$ROOT/packaging/copyright" "$PKG_ROOT/usr/share/doc/lightwrite/copyright"
install -m 0644 "$ROOT/CHANGELOG.md" "$PKG_ROOT/usr/share/doc/lightwrite/changelog"
gzip -9fn "$PKG_ROOT/usr/share/doc/lightwrite/changelog"

# Installed size in KiB
INSTALLED_SIZE="$(du -sk "$PKG_ROOT" | awk '{print $1}')"
if ! grep -q '^Installed-Size:' "$PKG_ROOT/DEBIAN/control"; then
  printf 'Installed-Size: %s\n' "$INSTALLED_SIZE" >> "$PKG_ROOT/DEBIAN/control"
fi

OUT="$DIST/lightwrite_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT"
echo "Built $OUT"
