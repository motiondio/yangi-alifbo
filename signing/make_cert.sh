#!/bin/sh
# Oʻz Mac'ingizda ishga tushiring:  sh make_cert.sh
# Self-signed Code Signing sertifikati (10 yil) yaratadi va GitHub Secrets uchun
# qiymatlarni chiqaradi.  Maxfiy kalit faqat sizning kompyuteringizda qoladi.
set -e
cd "$(dirname "$0")"
PW="$(openssl rand -hex 12)"
openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
  -keyout key.pem -out cert.pem \
  -subj "/CN=Yangi Alifbo Signing/O=Yangi Alifbo/C=UZ" \
  -addext "keyUsage=critical,digitalSignature" \
  -addext "extendedKeyUsage=critical,codeSigning" \
  -addext "basicConstraints=critical,CA:false" \
  -addext "subjectKeyIdentifier=hash" 2>/dev/null
# macOS `security import` eski (3DES/SHA1) PKCS#12 formatini ishonchli oʻqiydi
if openssl pkcs12 -help 2>&1 | grep -q -- '-legacy'; then LEGACY="-legacy"; else LEGACY=""; fi
openssl pkcs12 -export -out codesign.p12 -inkey key.pem -in cert.pem -name "Yangi Alifbo Signing" \
  -passout "pass:$PW" -keypbe PBE-SHA1-3DES -certpbe PBE-SHA1-3DES -macalg sha1 $LEGACY
rm -f key.pem
base64 < codesign.p12 | tr -d '\n' > codesign.p12.b64
echo
echo "Sertifikat tayyor:  $(openssl x509 -in cert.pem -noout -fingerprint -sha1)"
echo
echo "GitHub: repo → Settings → Secrets and variables → Actions → New repository secret"
echo "  1) Name:  MACOS_SIGNING_P12_B64"
echo "     Value: codesign.p12.b64 faylining ichidagi matn (Mac'da:  pbcopy < codesign.p12.b64 )"
echo "  2) Name:  MACOS_SIGNING_P12_PASSWORD"
echo "     Value: $PW"
echo
echo "Shundan soʻng Actions → Build Yangi Alifbo → Run workflow.  codesign.p12 va .b64 fayllarini"
echo "xavfsiz joyda saqlang (yoʻqolsa yangi sertifikat = ruxsatni bir marta qayta berish)."
