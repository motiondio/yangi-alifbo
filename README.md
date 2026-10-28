# Yangi Alifbo — yangi oʻzbek lotin alifbosi uchun avtomatik harf toʻgʻirlagich

[![Build](https://github.com/motiondio/yangi-alifbo/actions/workflows/build.yml/badge.svg)](https://github.com/motiondio/yangi-alifbo/actions/workflows/build.yml)
[![Yuklab olish](https://img.shields.io/github/v/release/motiondio/yangi-alifbo?label=Yuklab%20olish)](https://github.com/motiondio/yangi-alifbo/releases/latest)

Windows va macOS (Linux/X11 ham) uchun. Siz odatdagidek **o'zbek, g'isht, shahar, choy**
deb terasiz, dastur esa istalgan ilovada (Word, Telegram, brauzer, Excel …) harflarni
darhol yangi alifboga almashtiradi:

| Eski yozuv        | Yangi harf | Misol                      |
|-------------------|------------|----------------------------|
| `oʻ` / `o'`       | **ö / Ö**  | o'zbek → özbek             |
| `gʻ` / `g'`       | **ğ / Ğ**  | g'isht → ğişt              |
| `sh` / `Sh` / `SH`| **ş / Ş**  | shahar → şahar             |
| `ch` / `Ch` / `CH`| **ç / Ç**  | choy → çoy                 |
| `ng`              | oʻzgarmaydi| tong → tong                |
| tutuq belgisi `ʼ` | saqlanadi  | sheʼr → şeʼr, maʼno → maʼno|

Qonun: OʻRQ-1184 (2026-yil 21-oktabr), 28 harf + tutuq belgisi, kuchga kirishi 2027-yil 22-aprel.

---

## 0. Tayyor dastur — yuklab olish (eng oson yoʻl)

Tayyor fayllar **[Releases](https://github.com/motiondio/yangi-alifbo/releases/latest)** sahifasida
(GitHub Actions Windows va Mac serverlarida avtomatik yigʻadi):

| Fayl | Kimga |
|------|-------|
| `YangiAlifbo-Setup-windows-x64.exe` | **Windows 10/11 — oʻrnatuvchi** (Start menyu, avtomatik ishga tushish, oʻchirish) |
| `YangiAlifbo-windows-x64.exe` | Windows — bitta fayl, oʻrnatishsiz |
| `YangiAlifbo-windows-x64-portable.zip` | Windows — papka varianti (Defender `.exe` ga shubha qilsa) |
| `YangiAlifbo-macos-apple-silicon.dmg` / `.zip` | Mac — M1/M2/M3/M4 |
| `YangiAlifbo-macos-intel.dmg` / `.zip` | Mac — Intel |
| `YangiAlifbo.ahk` | Windows — AutoHotkey varianti (pastda) |

**Windows:** `YangiAlifbo-Setup-windows-x64.exe` ni ishga tushiring. SmartScreen "Windows protected your PC" desa —
*More info → Run anyway* (dastur imzolanmagan, chunki imzo sertifikati pullik).
Soat yonida yashil **ö** belgisi chiqadi: chap tugma — yoqish/oʻchirish, oʻng tugma — menyu.
Avtomatik ishga tushishi uchun: `Win+R` → `shell:startup` → shu papkaga `.exe` yorligʻini qoʻying.

**macOS (3 qadam):**
1. `.dmg` ni oching va `Yangi Alifbo` ni **Applications** papkasiga sudrab tashlang.
   (`.zip` yuklab olgan boʻlsangiz, ilovani ikki marta bosing — u oʻzi Applications ga
   oʻrnatishni taklif qiladi. Downloads papkasidan ishlatmang: macOS bunday ilovani har safar
   tasodifiy vaqtinchalik papkadan ochadi va bergan ruxsatingizni saqlab qolmaydi.)
2. Applications dan oching. Birinchi ochishda macOS toʻsadi: "Apple could not verify…" / "Not Opened"
   (ruscha tizimda: «Не удалось открыть» / «Не удаётся открыть программу»). Bu Gatekeeper — ilova Apple
   tomonidan notarizatsiya qilinmagan ($99/yil developer akkaunti kerak). Yechim: *System Settings →
   Privacy & Security* ga tushing, pastda **Open Anyway** («Всё равно открыть») ni bosing, keyin yana oching.
   Terminal orqali ham mumkin: `xattr -cr "/Applications/Yangi Alifbo.app"`.
   M1/M2/M3/M4 Mac uchun `apple-silicon`, eski Intel Mac uchun `intel` faylini oling.
3. Ilova ikkita ruxsat soʻraydi: *System Settings → Privacy & Security* → **Accessibility** va
   **Input Monitoring** roʻyxatlarida "Yangi Alifbo" ni yoqing. Ruxsat berilgach dastur oʻzi davom etadi
   (macOS "Quit & Reopen" desa — bosing). Davom etmasa — menyu satridagi belgidan *Chiqish* qilib, qayta oching.

**Terminal orqali oʻrnatish (eng ishonchli yoʻl, Gatekeeper'ga bogʻliq emas).** `install-mac.sh` ni
yuklab olib (Releases'da ham bor), Terminal'da ishga tushiring:

```bash
sh ~/Downloads/install-mac.sh
```

U Downloads (shu jumladan "Telegram Desktop") papkasidan mos `.dmg`/`.zip` ni topadi, ilovani Applications'ga
koʻchiradi, karantin belgisini olib tashlaydi, eski ruxsat yozuvlarini tozalaydi va ilovani ochadi.

Ruxsat har safar qayta soʻralaversa (roʻyxatda "Yangi Alifbo" yoqilgan koʻrinsa ham): bu eski versiyadan
qolgan yozuv — macOS ruxsatni ilovaning imzosiga bogʻlaydi. Ilova oynasidagi **Eski yozuvlarni tozalash**
tugmasini bosing (administrator paroli soʻraladi) yoki roʻyxatda "Yangi Alifbo" ni belgilab **−** bilan
oʻchiring, soʻng ilovani qayta oching. Yangilanishlarda ruxsat saqlanib qolishi uchun `.app` ni doimiy
sertifikat bilan imzolash mumkin — bir martalik sozlash `signing/README.md` da.

Belgi **menyu satrida** (yuqori oʻngda) chiqadi, Dock'da koʻrinmaydi. Chiqish: belgi → *Chiqish*.
Dastur ikkinchi marta ochilsa, "allaqachon ishlamoqda" deb ogohlantiradi (ikki nusxa harfni ikki marta
almashtirib qoʻyardi). Avtomatik ishga tushishi: *System Settings → General → Login Items* ga qoʻshing.
Yangi versiyaga oʻtganda macOS eski ruxsatni tanimasligi mumkin — roʻyxatda "Yangi Alifbo" ni oʻchirib (−)
qayta qoʻshing.

Yangi versiyani yigʻish: GitHub'da *Actions → Build Yangi Alifbo → Run workflow* →
versiya raqamini kiriting. 5–10 daqiqadan soʻng Releases'da paydo boʻladi.

---

Papkada uch xil variant bor:

| Fayl | Platforma | Nima kerak |
|------|-----------|------------|
| Releases'dagi `.exe` / `.app` | **Windows, macOS** | hech narsa |
| `yangi_alifbo.py` | **Windows, macOS, Linux** | Python 3.8+ va `pynput` |
| `YangiAlifbo.ahk` | faqat Windows | [AutoHotkey v2](https://www.autohotkey.com) (Python kerak emas) |
| `convert_text.py` | hamma joyda | tayyor matn/fayllarni oʻgirish uchun |

---

## 1. Python varianti (Mac + Windows)

### Oʻrnatish

```bash
pip install pynput
# ixtiyoriy: tray (soat yonida) belgisi uchun
pip install pystray pillow
# Windows: brauzer manzil satri (Edge/Chrome) uchun – pastdagi "Qanday ishlaydi" ga qarang
pip install comtypes
```

### Ishga tushirish

```bash
python yangi_alifbo.py
```

Konsolda `Yangi Alifbo ishga tushdi` chiqadi. Endi istalgan dasturga oʻtib yozing.

**macOS da birinchi marta:** System Settings → Privacy & Security →
**Accessibility** va **Input Monitoring** boʻlimlarida Terminal (yoki iTerm, yoki
yigʻilgan `.app`) ga ruxsat bering, soʻng dasturni qayta ishga tushiring.
Ruxsatsiz macOS klaviaturani kuzatishga yoʻl qoʻymaydi.

### Boshqaruv

| Amal | Qanday |
|------|--------|
| Yoqish / oʻchirish | **Ctrl+Alt+U** (Mac: Control+Option+U) yoki tray belgisi |
| Almashtirishni bekor qilish | almashgandan keyin **darhol Backspace** — `ş` yana `sh` boʻladi va qayta almashmaydi |
| `s` va `h` ni alohida qoldirish | `s'h` deb tering: `Is'hoq` → `Ishoq`, `as'hob` → `ashob` |
| Chiqish | konsolda Ctrl+C yoki tray → Chiqish |

Ingliz tilida yozayotganda (`shop`, `chat`) dasturni Ctrl+Alt+U bilan vaqtincha oʻchirib qoʻying.

### Sozlamalar — `config.json`

```json
{
  "hotkey": "<ctrl>+<alt>+u",
  "enabled_on_start": true,
  "backspace_undo": true,
  "strip_sh_apostrophe": true,
  "tutuq_belgisi": null,
  "tray": true
}
```

* `hotkey` — pynput formati: `<ctrl>`, `<alt>`, `<cmd>`, `<shift>`, `<f9>` … masalan `"<cmd>+<shift>+u"`.
* `backspace_undo` — Backspace bilan asl yozuvni qaytarish.
* `strip_sh_apostrophe` — `s'h` → `sh`. `false` boʻlsa apostrof qoladi (`Is'hoq`), lekin baribir `ş` boʻlmaydi.
* `tutuq_belgisi` — `"ʼ"` qilib qoʻysangiz, harfdan keyingi oddiy `'` rasmiy tutuq belgisi
  (U+02BC) ga almashadi: `ma'no` → `maʼno`. Standart holatda apostroflar tegilmaydi.

Buyruq qatori orqali ham: `--hotkey "<f9>"`, `--off`, `--no-undo`, `--keep-sh-apostrophe`, `--tutuq`, `--no-tray`.

### Avtomatik ishga tushishi

* **Windows:** `Win+R` → `shell:startup` → shu papkaga `yangi_alifbo.py` yorligʻini qoʻying
  (yoki `pythonw yangi_alifbo.py` buyrugʻi bilan yorliq — konsol oynasiz ishlaydi, tray belgisi orqali boshqariladi).
* **macOS:** System Settings → General → Login Items ga yigʻilgan `.app` ni qoʻshing (pastga qarang).

### Oʻzingiz .exe / .app qilib yigʻish

Avtomatik yoʻl: `.github/workflows/build-yangi-alifbo.yml` — GitHub Actions Windows, Mac (Apple Silicon)
va Mac (Intel) serverlarida yigʻib, Release'ga yuklaydi.

Qoʻlda (oʻz kompyuteringizda, faqat oʻz tizimingiz uchun):

```bash
pip install pyinstaller pynput pystray pillow
pip install comtypes                     # faqat Windows
python make_icon.py                      # icon.ico / icon.icns yaratadi

# Windows  → dist\YangiAlifbo.exe
pyinstaller --onefile --noconsole --name YangiAlifbo --icon icon.ico --add-data "config.json;." yangi_alifbo.py

# macOS    → dist/Yangi Alifbo.app
pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
pyinstaller --onedir --windowed --name "Yangi Alifbo" --icon icon.icns --add-data "config.json:." yangi_alifbo.py
```

`--noconsole`/`--windowed` bilan yigʻsangiz, boshqaruv uchun tray belgisi kerak —
shuning uchun `pystray` va `pillow` ni oldindan oʻrnating. macOS da yigʻilgan `.app` ga
Accessibility va Input Monitoring ruxsatini alohida berish kerak (ilova oʻzi soʻraydi).

---

## 2. AutoHotkey varianti (faqat Windows, eng yengil yoʻl)

1. [AutoHotkey v2](https://www.autohotkey.com) ni oʻrnating.
2. `YangiAlifbo.ahk` faylini ikki marta bosing — tray da yashil "H" belgisi paydo boʻladi.
3. Yoqish/oʻchirish: **Ctrl+Alt+U**. Chiqish: tray belgisi → Exit.
4. Avtomatik ishga tushishi uchun faylni `Win+R` → `shell:startup` papkasiga nusxalang.

Qoidalar Python variantidagi bilan bir xil (`s'h` → `sh`, katta-kichik harf avtomatik).
Faqat Backspace bilan qaytarish yoʻq — xato almashgan boʻlsa, oʻchirib `s'h` deb yozing.

---

## 3. Tayyor matnni oʻgirish — `convert_text.py`

```bash
python convert_text.py "O'zbekiston sho'x g'isht choy"
# → Özbekiston şöx ğişt çoy

python convert_text.py -i eski.txt -o yangi.txt
python convert_text.py --tutuq -i eski.txt -o yangi.txt     # ' → ʼ ham
cat eski.txt | python convert_text.py
```

Faqat oddiy matn (`.txt`, `.md`, `.csv`, `.srt` …) bilan ishlaydi. Word/Excel fayllari uchun matnni
nusxalab oʻgiring yoki Python ichidan `alifbo_core.convert_text()` funksiyasini chaqiring.

---

## Keng tarqatish — istalgan foydalanuvchi uchun

Dasturni istalgan odam yuklab olib, ikki marta bosib oʻrnatishi uchun ikki narsa kerak:
**ommaviy yuklab olish manzili** va **imzolangan fayllar**. Texnik tomoni CI'da tayyor — faqat
sertifikatlar (secret'lar) qoʻshilsa, bas.

### Hozirgi holat (secret'larsiz)

| Platforma | Foydalanuvchi nimani koʻradi |
|-----------|------------------------------|
| Windows | `YangiAlifbo-Setup-windows-x64.exe` oʻrnatuvchi ishlaydi, lekin SmartScreen "Windows protected your PC" deydi → *More info → Run anyway* |
| macOS | `.dmg` ochiladi, lekin Gatekeeper "Apple could not verify…" deydi → *System Settings → Privacy & Security → Open Anyway* |

Bu ogohlantirishlarni **faqat** rasmiy imzo olib tashlaydi. Boshqa yoʻli yoʻq — Apple va Microsoft
shunday qilib qoʻygan. Ruxsat soʻrovlari (Accessibility / Input Monitoring) esa har qanday
klaviatura dasturida boʻladi, imzolangan boʻlsa ham; farqi — imzolangan ilovada ruxsat bir marta beriladi.

### macOS — ogohlantirishsiz ochilishi uchun (Apple Developer Program, $99/yil)

1. https://developer.apple.com/programs/ da roʻyxatdan oʻting (1–2 kun tasdiqlanadi).
2. Mac'da Keychain Access → *Certificate Assistant → Request a Certificate from a Certificate Authority*
   (fayl sifatida saqlang). developer.apple.com → *Certificates* → **+** → **Developer ID Application** →
   soʻrov faylini yuklang → sertifikatni yuklab olib ikki marta bosing (Keychain'ga tushadi).
3. Keychain Access'da "Developer ID Application: …" sertifikatini oʻng tugma → *Export* → `.p12` (parol qoʻying).
   Terminal: `base64 -i sertifikat.p12 | pbcopy`
4. https://appleid.apple.com → *Sign-In and Security → App-Specific Passwords* → yangi parol yarating.
5. developer.apple.com → *Membership* → **Team ID** ni koʻchiring.
6. GitHub: repo → *Settings → Secrets and variables → Actions* → quyidagi secret'larni qoʻshing:

| Secret | Qiymat |
|--------|--------|
| `MACOS_SIGNING_P12_B64` | 3-qadamdagi base64 matn |
| `MACOS_SIGNING_P12_PASSWORD` | `.p12` paroli |
| `APPLE_ID` | Apple ID email |
| `APPLE_APP_PASSWORD` | 4-qadamdagi app-specific parol |
| `APPLE_TEAM_ID` | 5-qadamdagi Team ID |

7. *Actions → Build Yangi Alifbo → Run workflow*. CI ilovani Developer ID bilan imzolaydi, Apple'da
   notarizatsiya qiladi, `.app` va `.dmg` ga tasdiq (staple) qoʻshadi. Natija: foydalanuvchi `.dmg` ni
   ochadi, ilovani Applications'ga sudraydi, ochadi — hech qanday ogohlantirish yoʻq, faqat ikkita ruxsat.

Apple akkaunti boʻlmasa, oraliq variant — `signing/README.md` dagi self-signed sertifikat: Gatekeeper
ogohlantirishi qoladi, lekin ruxsat yangilanishlarda saqlanadi.

### Windows — SmartScreen'siz (ixtiyoriy)

Kod imzolash sertifikati kerak: OV sertifikat (~$200–400/yil, masalan Sectigo/Certum) yoki
[Azure Trusted Signing](https://learn.microsoft.com/azure/trusted-signing/) (~$10/oy). `.pfx` faylni olib:

| Secret | Qiymat |
|--------|--------|
| `WINDOWS_CERT_PFX_B64` | `.pfx` ning base64 matni (`base64 -i cert.pfx`) |
| `WINDOWS_CERT_PASSWORD` | `.pfx` paroli |

CI `.exe`, portativ nusxa va oʻrnatuvchini `signtool` bilan imzolaydi. Imzosiz tarqatish ham mumkin:
SmartScreen ogohlantirishi vaqt oʻtib, yuklab olishlar koʻpaygach, oʻzi yoʻqoladi (reputatsiya).

### Ommaviy yuklab olish manzili

Repo public, shuning uchun eng soʻnggi versiya har doim shu havolada:
**https://github.com/motiondio/yangi-alifbo/releases/latest** — uni saytga, Telegram kanalga
yoki QR-kodga qoʻyish mumkin. Yangi versiya chiqarish: *Actions → Build Yangi Alifbo → Run workflow* → versiya raqami.

### Foydalanuvchi uchun oʻrnatish (imzolangandan keyin)

* **Windows:** `YangiAlifbo-Setup-windows-x64.exe` → Next → Install. Start menyuda paydo boʻladi,
  "Windows bilan ishga tushirish" belgisi oʻrnatuvchida bor. Oʻchirish: Settings → Apps.
* **macOS:** `.dmg` → ilovani Applications'ga sudrash → ochish → Accessibility va Input Monitoring ni yoqish.
  Avtomatik ishga tushirish: menyu satridagi belgi → *Kompyuter bilan ishga tushirish*.

## Qanday ishlaydi

`alifbo_core.py` — tizimga bogʻliq boʻlmagan mantiq: oxirgi terilgan harflarni kuzatib,
`sh`, `ch`, `o'`, `g'` tugaganda "2 ta belgini oʻchirib, oʻrniga ş yoz" degan buyruq qaytaradi.
`yangi_alifbo.py` — `pynput` orqali klaviaturani tinglaydi va shu buyruqni bajaradi
(Backspace + yangi harf). Sichqoncha bosilganda, strelka/Enter/Tab bosilganda,
Ctrl/Alt/Cmd kombinatsiyalarida kontekst tozalanadi, shuning uchun eski matn buzilmaydi.

Brauzer manzil satri (Edge, Chrome, Safari) va Win+R oynasi terilgan matnga taklifni
belgilangan holda qoʻshadi: `Sh[opify.com]`. Bunda birinchi Backspace faqat taklifni oʻchiradi —
shuning uchun dastur almashtirishdan oldin fokusdagi maydonda matn oxirigacha belgilangan qism
bor-yoʻqligini tekshiradi (macOS: Accessibility API, Windows: UI Automation) va bor boʻlsa,
bitta qoʻshimcha Backspace yuboradi. Aks holda `Shahzod` → `Sşahzod` boʻlib qolardi.

Testlar: `python -m unittest -v test_alifbo_core` (25 ta test).

## Cheklovlar

* Dastur "sh" ni koʻrgan zahoti almashtiradi — u oʻzbekcha yoki inglizcha ekanini bilmaydi.
  Boshqa tilda yozganda oʻchirib qoʻying.
* Oʻyinlar va baʼzi eski dasturlar Unicode klaviatura kiritishini qabul qilmasligi mumkin.
* macOS Wayland yoʻq, Linux da esa faqat X11 da ishlaydi.
* AutoHotkey varianti brauzer manzil satridagi taklifni sezmaydi (`Shahzod` → `Sşahzod`) —
  u yerda Python/.exe variantini ishlating.
* Parol maydonlarida ham ishlaydi — paroli `sh` boʻlganlar ehtiyot boʻlsin (Ctrl+Alt+U).
