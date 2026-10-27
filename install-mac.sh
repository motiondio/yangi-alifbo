#!/bin/sh
# Yangi Alifbo – macOS oʻrnatish skripti.
# Gatekeeper ("Не удаётся открыть программу" / "Apple could not verify…") va karantin
# muammolarini chetlab oʻtadi, eski ruxsat yozuvlarini tozalaydi va ilovani ochadi.
#
# Ishlatish (Terminal):   sh install-mac.sh
#   yoki fayl yoʻli bilan: sh install-mac.sh ~/Downloads/YangiAlifbo-macos-apple-silicon.dmg
set -e
APP_NAME="Yangi Alifbo"
BUNDLE_ID="uz.yangialifbo.app"
DEST="/Applications/$APP_NAME.app"

case "$(uname -m)" in arm64) WANT="apple-silicon" ;; *) WANT="intel" ;; esac

SRC="$1"
if [ -z "$SRC" ]; then
  # Downloads / Desktop / Telegram Desktop papkalaridan eng yangi faylni topamiz
  SRC="$(find "$HOME/Downloads" "$HOME/Desktop" -maxdepth 3 \
          \( -name "YangiAlifbo-macos-$WANT.dmg" -o -name "YangiAlifbo-macos-$WANT.zip" \) -print0 2>/dev/null \
        | xargs -0 ls -t 2>/dev/null | head -1)"
fi
if [ -z "$SRC" ] || [ ! -e "$SRC" ]; then
  echo "Fayl topilmadi. YangiAlifbo-macos-$WANT.dmg ni yuklab oling yoki yoʻlini bering:"
  echo "  sh install-mac.sh /yoʻl/YangiAlifbo-macos-$WANT.dmg"
  exit 1
fi
echo "Manba: $SRC   (Mac: $(uname -m) → $WANT)"

# ishlayotgan nusxani toʻxtatish va eskisini oʻchirish
pkill -f "$APP_NAME.app/Contents/MacOS/" 2>/dev/null || true
sleep 1
rm -rf "$DEST"

case "$SRC" in
  *.dmg)
    MNT="$(mktemp -d)"
    hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$SRC" >/dev/null
    if [ ! -d "$MNT/$APP_NAME.app" ]; then
      echo "DMG ichida '$APP_NAME.app' topilmadi"; hdiutil detach "$MNT" >/dev/null 2>&1 || true; exit 1
    fi
    ditto "$MNT/$APP_NAME.app" "$DEST"
    hdiutil detach "$MNT" >/dev/null 2>&1 || true
    ;;
  *.zip)
    TMP="$(mktemp -d)"
    ditto -x -k "$SRC" "$TMP"
    ditto "$TMP/$APP_NAME.app" "$DEST"
    rm -rf "$TMP"
    ;;
  *.app)
    ditto "$SRC" "$DEST"
    ;;
  *)
    echo "Nomaʼlum fayl turi: $SRC"; exit 1
    ;;
esac

# Karantin belgisini olib tashlash – Gatekeeper endi toʻsmaydi ("Open Anyway" shart emas)
xattr -cr "$DEST"
# Eski versiyadan qolgan ruxsat yozuvlarini tozalash (xatosi eʼtiborsiz)
tccutil reset Accessibility "$BUNDLE_ID" >/dev/null 2>&1 || true
tccutil reset ListenEvent "$BUNDLE_ID" >/dev/null 2>&1 || true

echo "Oʻrnatildi: $DEST"
if codesign --verify --deep --strict "$DEST" 2>/dev/null; then
  echo "Imzo: OK"
else
  echo "Imzo: XATO – quyidagi matnni yuboring:"; codesign --verify --deep --strict --verbose=2 "$DEST" 2>&1 | head -5 || true
fi
open "$DEST"
echo
echo "Ilova ochildi. Endi: System Settings → Privacy & Security → Accessibility va Input Monitoring"
echo "roʻyxatlarida \"$APP_NAME\" ni yoqing. Ruxsat berilgach ilova oʻzi davom etadi."
