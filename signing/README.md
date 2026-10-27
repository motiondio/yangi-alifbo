# Doimiy imzo sertifikati (macOS, ixtiyoriy lekin tavsiya etiladi)

macOS ruxsatlari (Accessibility, Input Monitoring) ilovaning **imzosiga** bogʻlanadi.
Standart holatda `.app` *ad-hoc* imzolanadi — har yangi yigʻilish boshqa imzo oladi, shuning
uchun har yangilanishdan keyin macOS ilovani "yangi" deb hisoblab ruxsatni qayta soʻraydi
(ilova eski yozuvni oʻzi tozalaydi, lekin ruxsatni qayta yoqish kerak boʻladi).

Doimiy (self-signed) sertifikat bilan imzolansa, imzo barqaror boʻladi: ruxsat bir marta
beriladi va keyingi yangilanishlarda saqlanib qoladi.

## Sozlash (bir marta, oʻz Mac'ingizda)

```bash
cd signing
sh make_cert.sh
```

Skript sertifikat yaratadi va ikkita GitHub secret qiymatini chiqaradi:

| Secret nomi | Qiymat |
|-------------|--------|
| `MACOS_SIGNING_P12_B64` | `codesign.p12.b64` faylining ichidagi matn |
| `MACOS_SIGNING_P12_PASSWORD` | skript chiqargan parol |

GitHub: repo → *Settings → Secrets and variables → Actions → New repository secret*.
Keyingi yigʻilishdan boshlab `.app` shu sertifikat bilan imzolanadi (workflow jurnalida
`Imzolandi: sertifikat …` yoziladi; secret boʻlmasa — `ad-hoc imzo ishlatiladi`).

Maxfiy kalit (`codesign.p12`) repoga **kiritilmaydi** (`.gitignore` da) — faqat sizda va
GitHub Secrets'da boʻladi. Yoʻqolsa `make_cert.sh` ni qayta ishga tushiring: yangi sertifikat
bilan imzolangan birinchi versiyada ruxsatni bir marta qayta berish kerak boʻladi.

Bu sertifikat Apple tomonidan tasdiqlanmagan: Gatekeeper ("Apple could not verify…", *Open Anyway*)
baribir bir marta chiqadi. Uni faqat Apple Developer akkaunti ($99/yil) bilan notarizatsiya olib tashlaydi.
