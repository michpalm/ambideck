#!/usr/bin/env bash
# Build the plugin and package it for Decky's "Install plugin from ZIP/URL". Usage: scripts/package.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
pnpm build
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/ambideck"
mkdir -p "$PKG/py_modules" out
cp plugin.json package.json main.py LICENSE "$PKG/"
cp -R dist "$PKG/dist"
rm -f "$PKG"/dist/*.map
cp -R py_modules/ambideck "$PKG/py_modules/ambideck"
find "$PKG" -name '__pycache__' -prune -exec rm -rf {} +
rm -f out/ambideck.zip
(cd "$STAGE" && zip -qr "$ROOT/out/ambideck.zip" ambideck)
unzip -l out/ambideck.zip
