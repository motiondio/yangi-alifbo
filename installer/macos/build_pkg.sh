#!/bin/sh
# Yangi Alifbo – macOS .pkg oʻrnatuvchi (Introduction → Read Me → License → Install → Summary).
#
#   sh installer/macos/build_pkg.sh "dist/Yangi Alifbo.app" 1.0.5 arm64 dist/YangiAlifbo.pkg
#
# ARCHS: "arm64" (Apple Silicon) yoki "x86_64,arm64" (Intel; M1 da Rosetta orqali ham ishlaydi).
# Ish papkasida installer_bg.png boʻlsa (make_icon.py yaratadi) – oynaning chap pastida koʻrinadi.
set -e
APP="$1"; VERSION="$2"; ARCHS="$3"; OUT="$4"
if [ -z "$OUT" ]; then echo "Ishlatish: sh build_pkg.sh <app> <versiya> <arxitektura> <chiqish.pkg>"; exit 1; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/root/Applications" "$WORK/resources"
ditto "$APP" "$WORK/root/Applications/Yangi Alifbo.app"
# Ilovaning boshqa nusxasi (masalan Downloads'da) topilsa ham Installer uni oʻsha yerda
# yangilamasin – doim /Applications ga oʻrnatilsin
pkgbuild --analyze --root "$WORK/root" "$WORK/component.plist" >/dev/null
plutil -replace 0.BundleIsRelocatable -bool NO "$WORK/component.plist"
cp -R "$HERE/scripts" "$WORK/scripts"
chmod +x "$WORK/scripts/"*
pkgbuild --root "$WORK/root" --install-location / --component-plist "$WORK/component.plist" \
  --scripts "$WORK/scripts" --identifier uz.yangialifbo.app --version "$VERSION" \
  "$WORK/YangiAlifbo-component.pkg"

for f in "$HERE"/resources/*.html; do
  sed "s/@VERSION@/$VERSION/g" "$f" > "$WORK/resources/$(basename "$f")"
done
sed -e "s/@VERSION@/$VERSION/g" -e "s/@ARCHS@/$ARCHS/g" "$HERE/distribution.xml" > "$WORK/distribution.xml"
if [ -f installer_bg.png ]; then
  cp installer_bg.png "$WORK/resources/background.png"
else
  sed -i '' '/<background/d' "$WORK/distribution.xml"
fi
productbuild --distribution "$WORK/distribution.xml" --resources "$WORK/resources" \
  --package-path "$WORK" "$OUT"
echo "Tayyor: $OUT"
