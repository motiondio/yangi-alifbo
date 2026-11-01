# -*- coding: utf-8 -*-
"""
Interfeys tillari: oʻzbekcha (lotin), oʻzbekcha yangi alifboda, ruscha, inglizcha.

Barcha foydalanuvchiga koʻrinadigan matnlar shu yerda.  "uz-new" (yangi alifbo) qoʻlda
yozilmaydi – oʻzbekcha matndan dasturning oʻz oʻgirgichi (convert_text) bilan hosil qilinadi;
eski yozuvni misol sifatida koʻrsatadigan matnlar uchungina alohida yoziladi (UZ_NEW).

Til tanlash tartibi (resolve): sozlamalardagi "language" → Windows oʻrnatuvchisida tanlangan til
(HKCU\\Software\\Yangi Alifbo\\Language) → tizim tili (rus → ruscha, qolganlari → oʻzbekcha).
"""
from __future__ import annotations

import datetime
import re
import sys
from typing import Optional

from alifbo_core import convert_text

LANGS = ("uz", "uz-new", "ru", "en")
LANG_NAMES = {"uz": "Oʻzbekcha", "uz-new": "Özbekça (yangi alifbo)", "ru": "Русский", "en": "English"}
DEFAULT = "uz"

# kalit: (oʻzbekcha, ruscha, inglizcha).  {nom} – oʻrniga qiymat qoʻyiladi.
STRINGS = {
    # ---- umumiy
    "on": ("Yoqilgan", "Включено", "On"),
    "off": ("Oʻchirilgan", "Выключено", "Off"),
    "not_running": ("Dastur ishlamayapti", "Программа не запущена", "Not running"),
    "btn_download": ("Yuklab olish", "Скачать", "Download"),
    "btn_quit": ("Chiqish", "Выход", "Quit"),

    # ---- tray menyusi va xabarlari (asosiy jarayon)
    "tray_update": ("Yangi versiya {version} – yuklab olish", "Новая версия {version} — скачать",
                    "New version {version} – download"),
    "tray_open_panel": ("Panelni ochish", "Открыть панель", "Open panel"),
    "tray_turn_off": ("Oʻchirish", "Выключить", "Turn off"),
    "tray_turn_on": ("Yoqish", "Включить", "Turn on"),
    "tray_settings": ("Sozlamalar…", "Настройки…", "Settings…"),
    "tray_autostart": ("Kompyuter bilan ishga tushirish", "Запускать вместе с компьютером",
                       "Start with computer"),
    "tray_links": ("Biz bilan", "Мы в соцсетях", "Follow us"),
    "tray_hotkey": ("Tezkor tugma: {hotkey}", "Горячая клавиша: {hotkey}", "Shortcut: {hotkey}"),
    "tray_title_on": ("{app}: yoqilgan", "{app}: включено", "{app}: on"),
    "tray_title_off": ("{app}: oʻchirilgan", "{app}: выключено", "{app}: off"),
    "tray_title_update": (" · {version} chiqdi", " · вышла {version}", " · {version} available"),
    "notify_update": ("{app} {version} chiqdi. Yangilash uchun belgini bosing.",
                      "Вышла {app} {version}. Нажмите на значок, чтобы обновить.",
                      "{app} {version} is available. Click the icon to update."),
    "notify_milestone": ("{n} ta harf yangi alifboda toʻgʻirlandi! Statistikani sozlamalarda koʻring.",
                         "Исправлено {n} букв по новому алфавиту! Статистика — в настройках.",
                         "{n} letters fixed in the new alphabet! See your statistics in Settings."),

    # ---- macOS: oʻrnatish va ruxsatlar
    "where_translocated": ("macOS'ning vaqtinchalik xavfsizlik papkasidan",
                           "из временной папки безопасности macOS",
                           "from a temporary macOS security folder"),
    "where_outside": ("Applications papkasidan tashqaridan", "не из папки «Программы» (Applications)",
                      "from outside the Applications folder"),
    "self_install": (
        "{app} hozir {where} ishga tushdi. Bu holatda macOS siz bergan ruxsatlarni saqlab qolmaydi va "
        "dastur har safar qayta ruxsat soʻrayveradi.\n\nIlovani Applications papkasiga oʻrnatib, u yerdan "
        "ishga tushiraylikmi?",
        "{app} запущена {where}. В этом случае macOS не сохраняет выданные разрешения, и программа будет "
        "запрашивать их при каждом запуске.\n\nУстановить программу в папку «Программы» и запустить оттуда?",
        "{app} was started {where}. In this case macOS does not keep the permissions you grant, and the app "
        "will keep asking for them.\n\nInstall the app to the Applications folder and run it from there?"),
    "btn_later": ("Keyinroq", "Позже", "Later"),
    "btn_install": ("Oʻrnatish", "Установить", "Install"),
    "self_install_failed": (
        "Applications papkasiga koʻchirib boʻlmadi: {error}\n\nIlovani Finder orqali qoʻlda Applications "
        "papkasiga koʻchiring va u yerdan oching.",
        "Не удалось скопировать в папку «Программы»: {error}\n\nПеретащите программу в папку «Программы» "
        "через Finder и откройте её оттуда.",
        "Could not copy to the Applications folder: {error}\n\nMove the app to the Applications folder in "
        "Finder and open it from there."),
    "perm_accessibility": ("Accessibility", "Универсальный доступ", "Accessibility"),
    "perm_input": ("Input Monitoring", "Мониторинг ввода", "Input Monitoring"),
    "perm_path": ("System Settings → Privacy & Security → Accessibility va Input Monitoring",
                  "«Системные настройки» → «Конфиденциальность и безопасность» → «Универсальный доступ» "
                  "и «Мониторинг ввода»",
                  "System Settings → Privacy & Security → Accessibility and Input Monitoring"),
    "perm_needed": (
        "{app} ishlashi uchun ruxsat kerak: {missing}.\n\n{path} roʻyxatlarida \"{app}\" ni yoqing. Ruxsat "
        "berilgach dastur oʻzi qayta ishga tushadi (macOS \"Quit & Reopen\" desa – bosing).\n\nRoʻyxatda "
        "\"{app}\" allaqachon YOQILGAN koʻrinsa-yu, bu oyna baribir chiqaversa – bu eski versiyadan qolgan "
        "yozuv. \"{reset}\" ni bosing (administrator paroli soʻraladi) yoki roʻyxatda uni − bilan oʻchirib, "
        "qayta qoʻshing.",
        "Для работы {app} нужны разрешения: {missing}.\n\nВключите «{app}» в разделах {path}. После этого "
        "программа перезапустится сама (если macOS предложит «Завершить и снова открыть» — нажмите).\n\n"
        "Если «{app}» в списке уже ВКЛЮЧЕНА, а это окно всё равно появляется — это запись от старой версии. "
        "Нажмите «{reset}» (потребуется пароль администратора) или удалите её из списка кнопкой − и "
        "добавьте снова.",
        "{app} needs permission to work: {missing}.\n\nIn {path}, turn on \"{app}\". Once allowed, the app "
        "restarts by itself (if macOS says \"Quit & Reopen\", click it).\n\nIf \"{app}\" already looks ON "
        "in the list but this window keeps appearing, it is a leftover entry from an older version. Click "
        "\"{reset}\" (an administrator password is required) or remove it from the list with − and add it "
        "again."),
    "btn_reset_entries": ("Eski yozuvlarni tozalash", "Очистить старые записи", "Clear old entries"),
    "btn_open_settings": ("Sozlamalarni ochish", "Открыть настройки", "Open Settings"),
    "perm_reset_ok": ("Eski yozuvlar tozalandi. Endi {path} da \"{app}\" ni qayta yoqing.",
                      "Старые записи удалены. Теперь снова включите «{app}» в разделах {path}.",
                      "Old entries cleared. Now turn \"{app}\" on again in {path}."),
    "perm_reset_fail": (
        "Tozalab boʻlmadi. Qoʻlda: {path} roʻyxatlarida \"{app}\" ni belgilab − bilan oʻchiring, soʻng "
        "ilovani qayta oching.",
        "Не удалось очистить. Вручную: в разделах {path} выберите «{app}», удалите кнопкой − и откройте "
        "программу снова.",
        "Could not clear them. Manually: in {path}, select \"{app}\", remove it with −, then open the app "
        "again."),
    "perm_denied": ("Ruxsat berilmadi, {app} ishlay olmaydi.\n\n{path} da \"{app}\" ni yoqib, ilovani qayta oching.",
                    "Разрешение не выдано — {app} не может работать.\n\nВключите «{app}» в разделах {path} и "
                    "откройте программу снова.",
                    "Permission was not granted, so {app} cannot work.\n\nTurn on \"{app}\" in {path}, then "
                    "open the app again."),
    "listener_failed": ("Klaviatura kuzatuvchisi ishga tushmadi.", "Не удалось запустить отслеживание клавиатуры.",
                        "The keyboard listener did not start."),
    "listener_hint_mac": (
        "Ruxsat endigina berilgan boʻlsa, ilovani yopib qayta oching. {path} da \"{app}\" yoqilganini tekshiring.",
        "Если разрешение только что выдано, закройте и снова откройте программу. Проверьте, что «{app}» "
        "включена в разделах {path}.",
        "If you have just granted permission, quit and reopen the app. Check that \"{app}\" is on in {path}."),
    "listener_hint_win": ("Dasturni qayta ishga tushirib koʻring.", "Попробуйте перезапустить программу.",
                          "Try restarting the app."),
    "tray_failed": ("Menyu satri belgisini yaratib boʻlmadi, shuning uchun dastur ishga tushmadi.",
                    "Не удалось создать значок в строке меню, поэтому программа не запустилась.",
                    "Could not create the menu bar icon, so the app did not start."),
    "running_no_tray": ("{app} ishlamoqda.\nYoqish/oʻchirish: {hotkey}\nToʻxtatish: Task Manager orqali.",
                        "{app} работает.\nВключить/выключить: {hotkey}\nОстановить: через Диспетчер задач.",
                        "{app} is running.\nTurn on/off: {hotkey}\nTo stop it, use Task Manager."),

    # ---- panel
    "panel_update_title": ("Yangi versiya: {version}", "Новая версия: {version}", "New version: {version}"),
    "panel_update_hint": ("Yuklangan faylni ochib oʻrnating – sozlamalar saqlanadi.",
                          "Откройте скачанный файл и установите — настройки сохранятся.",
                          "Open the downloaded file to install – your settings are kept."),
    "panel_front": ("Hozir oldinda", "Сейчас активно", "Active now"),
    "panel_unknown_app": ("Aniqlanmadi", "Не определено", "Unknown"),
    "panel_unknown_hint": ("Biror dasturga oʻtib, panelni qayta oching.",
                           "Переключитесь на программу и снова откройте панель.",
                           "Switch to an app and open the panel again."),
    "hint_all_apps": ("Hamma dasturlarda ishlaydi (sozlamalarda oʻzgartiriladi).",
                      "Работает во всех программах (меняется в настройках).",
                      "Works in all apps (change this in Settings)."),
    "hint_app_on": ("Shu dasturda harflar almashtiriladi.", "В этой программе буквы заменяются.",
                    "Letters are replaced in this app."),
    "hint_app_off": ("Bu dasturda ishlamaydi – yoqish uchun tugmani bosing.",
                     "В этой программе не работает — включите переключателем.",
                     "Not active in this app – use the switch to turn it on."),
    "hint_disabled": ("Dastur oʻchirilgan – yuqoridagi tugma bilan yoqing.",
                      "Программа выключена — включите её переключателем вверху.",
                      "The app is off – turn it on with the switch above."),
    "stat_today_fixed": ("Bugun toʻgʻirlandi", "Исправлено сегодня", "Fixed today"),
    "stat_total": ("Jami", "Всего", "Total"),
    "panel_all_settings": ("Barcha sozlamalar  →", "Все настройки  →", "All settings  →"),
    "milestone_title": ("{n} ta harf!", "{n} букв!", "{n} letters!"),
    "milestone_text": ("Siz yangi alifboda yozyapsiz – natijangizni doʻstlaringizga ulashing!",
                       "Вы пишете по новому алфавиту — поделитесь результатом с друзьями!",
                       "You are writing in the new alphabet – share your result with friends!"),
    "btn_share_short": ("Ulashish", "Поделиться", "Share"),

    # ---- sozlamalar oynasi
    "settings_title": ("{app} — Sozlamalar", "{app} — Настройки", "{app} — Settings"),
    "nav_general": ("Umumiy", "Основные", "General"),
    "nav_apps": ("Dasturlar", "Программы", "Apps"),
    "nav_stats": ("Statistika", "Статистика", "Statistics"),
    "nav_about": ("Biz bilan", "О нас", "About"),
    "sidebar_version": ("versiya {version}", "версия {version}", "version {version}"),
    "sidebar_update": ("{current}  →  {latest} chiqdi", "{current}  →  вышла {latest}",
                       "{current}  →  {latest} available"),
    "status_click_off": ("Bosing – oʻchirish", "Нажмите — выключить", "Click to turn off"),
    "status_click_on": ("Bosing – yoqish", "Нажмите — включить", "Click to turn on"),
    "status_reopen": ("{app} ni qayta oching", "Откройте {app} снова", "Open {app} again"),

    # Umumiy
    "general_sub": ("Harflar qanday almashtirilishi va dastur qachon ishga tushishi.",
                    "Как заменяются буквы и когда запускается программа.",
                    "How letters are replaced and when the app starts."),
    "sec_language": ("Til", "Язык", "Language"),
    "language_row": ("Interfeys tili", "Язык интерфейса", "Interface language"),
    "language_sub": ("Panel, menyu va sozlamalar shu tilda koʻrsatiladi.",
                     "Панель, меню и настройки будут на этом языке.",
                     "The panel, menu and settings use this language."),
    "sec_try": ("Sinab koʻring", "Попробуйте", "Try it"),
    "try_placeholder": ("Eski yozuvda yozing: o'zbek, g'isht, choy…", "Напишите по-старому: o'zbek, g'isht, choy…",
                        "Type in the old spelling: o'zbek, g'isht, choy…"),
    "sec_startup": ("Ishga tushish", "Запуск", "Startup"),
    "autostart_row": ("Kompyuter yoqilganda ishga tushsin", "Запускать при включении компьютера",
                      "Start when the computer starts"),
    "autostart_sub": ("Belgi menyu satrida / soat yonida paydo boʻladi.",
                      "Значок появится в строке меню / рядом с часами.",
                      "The icon appears in the menu bar / next to the clock."),
    "enabled_on_start": ("Ochilganda almashtirish yoqilgan boʻlsin", "Включать замену при запуске",
                         "Turn replacement on at launch"),
    "sec_typing": ("Yozish", "Ввод", "Typing"),
    "undo_row": ("Backspace – asl yozuvni qaytaradi", "Backspace — возвращает исходное написание",
                 "Backspace restores the original spelling"),
    "undo_sub": ("Almashgandan keyin darhol bosilsa: ş → sh", "Если нажать сразу после замены: ş → sh",
                 "If pressed right after a replacement: ş → sh"),
    "sh_row": ("s'h – ş emas, sh boʻlib qoladi", "s'h — остаётся sh, а не ş", "s'h stays sh, not ş"),
    "sh_sub": ("Is'hoq → Ishoq, as'hob → ashob", "Is'hoq → Ishoq, as'hob → ashob", "Is'hoq → Ishoq, as'hob → ashob"),
    "tutuq_row": ("Apostrof – rasmiy tutuq belgisi", "Апостроф — официальный знак «тутук»",
                  "Apostrophe becomes the official tutuq sign"),
    "tutuq_sub": ("ma'no → maʼno (U+02BC)", "ma'no → maʼno (U+02BC)", "ma'no → maʼno (U+02BC)"),
    "sec_hotkey": ("Tezkor tugma", "Горячая клавиша", "Keyboard shortcut"),
    "hotkey_row": ("Yoqish / oʻchirish", "Включить / выключить", "Turn on / off"),
    "hotkey_sub": ("Inglizcha yozayotganda vaqtincha oʻchirish uchun",
                   "Чтобы временно выключить, например при наборе на английском",
                   "To pause it while typing in English, for example"),

    # Dasturlar
    "apps_sub": ("Harflar faqat tanlangan dasturlarda almashtiriladi – terminal, kod muharriri, "
                 "oʻyinlarda dastur aralashmaydi.",
                 "Буквы заменяются только в выбранных программах — в терминале, редакторе кода и играх "
                 "программа не вмешивается.",
                 "Letters are replaced only in the apps you choose – the app stays out of terminals, "
                 "code editors and games."),
    "mode_list": ("Faqat roʻyxatdagilarda", "Только в списке", "Only listed apps"),
    "mode_all": ("Hamma dasturlarda", "Во всех программах", "All apps"),
    "mode_all_hint": ("Roʻyxat hisobga olinmaydi – hamma joyda almashtiriladi.",
                      "Список не учитывается — замена работает везде.",
                      "The list is ignored – letters are replaced everywhere."),
    "mode_list_hint": ("Roʻyxatdagi dasturlarda ishlaydi. Panel orqali ham qoʻshish mumkin.",
                       "Работает в программах из списка. Добавлять можно и через панель.",
                       "Works in the listed apps. You can also add apps from the panel."),
    "sec_list": ("Roʻyxat", "Список", "List"),
    "btn_add_app": ("+  Dastur qoʻshish", "+  Добавить программу", "+  Add app"),
    "btn_default_list": ("Standart roʻyxat", "Стандартный список", "Default list"),
    "btn_remove": ("Olib tashlash", "Убрать", "Remove"),
    "list_empty": ("Roʻyxat boʻsh – «Dastur qoʻshish» ni bosing.", "Список пуст — нажмите «Добавить программу».",
                   "The list is empty – click “Add app”."),
    "pick_title": ("Dastur qoʻshish", "Добавить программу", "Add app"),
    "pick_head": ("Hozir ochiq dasturlar", "Открытые программы", "Open apps"),
    "pick_hint": ("Kerakli dastur koʻrinmasa – uni oching va «Yangilash» ni bosing.",
                  "Если нужной программы нет — откройте её и нажмите «Обновить».",
                  "If the app isn't listed, open it and click “Refresh”."),
    "btn_added": ("Qoʻshildi ✓", "Добавлено ✓", "Added ✓"),
    "btn_add": ("Qoʻshish", "Добавить", "Add"),
    "pick_none": ("Qoʻshiladigan dastur yoʻq.", "Нечего добавить.", "Nothing to add."),
    "btn_refresh": ("Yangilash", "Обновить", "Refresh"),
    "btn_done": ("Tayyor", "Готово", "Done"),

    # Statistika
    "stats_sub": ("Faqat sonlar saqlanadi – yozgan matningiz saqlanmaydi va hech qayerga yuborilmaydi.",
                  "Сохраняются только числа — ваш текст не сохраняется и никуда не отправляется.",
                  "Only numbers are stored – your text is never saved or sent anywhere."),
    "stat_today": ("Bugun", "Сегодня", "Today"),
    "stat_week": ("Oxirgi 7 kun", "За 7 дней", "Last 7 days"),
    "sec_30days": ("Oxirgi 30 kun", "Последние 30 дней", "Last 30 days"),
    "no_data": ("Hali maʼlumot yoʻq – yozishni boshlang.", "Пока нет данных — начните писать.",
                "No data yet – start typing."),
    "sec_letters": ("Harflar", "Буквы", "Letters"),
    "app_other": ("Boshqa", "Другое", "Other"),
    "sec_achievements": ("Yutuqlar", "Достижения", "Achievements"),
    "ach_streak": ("Ketma-ket kunlar", "Дней подряд", "Day streak"),
    "ach_best": ("Rekord kun", "Рекордный день", "Best day"),
    "ach_since": ("Birinchi kun", "Первый день", "First day"),
    "btn_share": ("Natijamni ulashish", "Поделиться результатом", "Share my result"),
    "btn_reset_stats": ("Statistikani tozalash", "Сбросить статистику", "Reset statistics"),
    "reset_confirm": ("Statistika butunlay oʻchiriladi. Davom etasizmi?",
                      "Статистика будет полностью удалена. Продолжить?",
                      "All statistics will be deleted. Continue?"),
    "share_saved": ("Rasm saqlandi: {path}", "Картинка сохранена: {path}", "Image saved: {path}"),
    "share_failed": ("Rasmni saqlab boʻlmadi: {error}", "Не удалось сохранить картинку: {error}",
                     "Could not save the image: {error}"),
    "share_line": ("harf yangi alifboda toʻgʻirlandi", "букв исправлено по новому алфавиту",
                   "letters fixed in the new alphabet"),
    "share_footer": ("Bepul dastur – Windows va Mac uchun", "Бесплатная программа для Windows и Mac",
                     "Free app for Windows and Mac"),

    # Biz bilan
    "about_sub": ("Eʼlonlar, yangiliklar va ijtimoiy tarmoqlar.", "Объявления, новости и соцсети.",
                  "News, announcements and social media."),
    "sec_ad": ("Eʼlon", "Объявление", "Announcement"),
    "sec_follow": ("Bizni kuzatib boring", "Следите за нами", "Follow us"),
    "links_soon": ("Havolalar tez orada qoʻshiladi.", "Ссылки скоро появятся.", "Links coming soon."),
    "sec_about_app": ("Dastur haqida", "О программе", "About the app"),
    "upd_available": ("Yangi versiya chiqdi: {version}. Yuklab olib, ustidan oʻrnating – sozlamalar saqlanadi.",
                      "Вышла новая версия {version}. Скачайте и установите поверх — настройки сохранятся.",
                      "Version {version} is available. Download and install it over this one – your "
                      "settings are kept."),
    "upd_download": ("{version} ni yuklab olish", "Скачать {version}", "Download {version}"),
    "upd_checking": ("Tekshirilmoqda…", "Проверка…", "Checking…"),
    "upd_failed": ("Tekshirib boʻlmadi – internet aloqasini tekshiring.",
                   "Не удалось проверить — проверьте подключение к интернету.",
                   "Could not check – check your internet connection."),
    "upd_dev": ("Manba koddan ishga tushirilgan", "Запущено из исходного кода", "Running from source"),
    "upd_dev_latest": (" · eng soʻnggi: {version}", " · последняя: {version}", " · latest: {version}"),
    "upd_latest": ("Eng soʻnggi versiya oʻrnatilgan · tekshirildi {when}",
                   "Установлена последняя версия · проверено {when}",
                   "You have the latest version · checked {when}"),
    "upd_never": ("Hali tekshirilmagan", "Ещё не проверялось", "Not checked yet"),
    "btn_check": ("Tekshirish", "Проверить", "Check"),
    "upd_auto_row": ("Yangi versiyani avtomatik tekshirish", "Автоматически проверять обновления",
                     "Check for updates automatically"),
    "upd_auto_sub": ("Kuniga bir marta GitHub'dan faqat versiya raqami soʻraladi, boshqa hech narsa yuborilmaydi.",
                     "Раз в день у GitHub запрашивается только номер версии — больше ничего не отправляется.",
                     "Once a day only the version number is requested from GitHub – nothing else is sent."),
    "about_alphabet": ("Yangi oʻzbek lotin alifbosi (OʻRQ-1184)", "Новый узбекский латинский алфавит (ЗРУ-1184)",
                       "New Uzbek Latin alphabet (Law ZRU-1184)"),
    "about_source": ("Ochiq manba kodi va barcha versiyalar", "Открытый исходный код и все версии",
                     "Open source code and all versions"),
}

# Yangi alifbo varianti: eski yozuv misollari oʻgirilmasin
UZ_NEW = {
    "try_placeholder": "Eski yozuvda yozing: o'zbek, g'isht, choy…",
    "undo_sub": "Almaşgandan keyin darhol bosilsa: ş → sh",
    "sh_row": "s'h – ş emas, sh bölib qoladi",
    "sh_sub": "Is'hoq → Ishoq, as'hob → ashob",
    "tutuq_sub": "ma'no → maʼno (U+02BC)",
}

MONTHS = {
    "uz": ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr",
           "noyabr", "dekabr"),
    "ru": ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
           "октября", "ноября", "декабря"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}

_PLACEHOLDER = re.compile(r"(\{[a-z_]+\})")
_lang = DEFAULT
_cache: dict = {}


def _to_new(text: str) -> str:
    """Oʻzbekcha matn → yangi alifbo; {oʻrinbosarlar} tegilmaydi."""
    return "".join(part if _PLACEHOLDER.fullmatch(part) else convert_text(part)
                   for part in _PLACEHOLDER.split(text))


def _lookup(key: str, lang: str) -> str:
    row = STRINGS.get(key)
    if row is None:
        return key
    if lang == "uz-new":
        if key not in _cache:
            _cache[key] = UZ_NEW.get(key) or _to_new(row[0])
        return _cache[key]
    return row[{"ru": 1, "en": 2}.get(lang, 0)]


def t(key: str, **values) -> str:
    text = _lookup(key, _lang)
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def normalize(code) -> Optional[str]:
    if not isinstance(code, str):
        return None
    code = code.strip().lower().replace("_", "-")
    if code in LANGS:
        return code
    base = code.split("-")[0]
    return base if base in ("uz", "ru", "en") else None


def set_language(code) -> str:
    global _lang
    _lang = normalize(code) or DEFAULT
    return _lang


def language() -> str:
    return _lang


def base_language(lang: Optional[str] = None) -> str:
    """Sana, son va oy nomlari uchun: "uz-new" → "uz"."""
    return {"uz-new": "uz"}.get(lang or _lang, lang or _lang)


def system_language(platform: str = sys.platform) -> str:
    """Tizim tili: ruscha → "ru", qolgan hammasi → "uz" (dastur oʻzbek tilida yozuvchilar uchun)."""
    codes = []
    try:
        if platform == "darwin":
            from Foundation import NSLocale
            codes = [str(c) for c in NSLocale.preferredLanguages()[:1]]
        elif platform.startswith("win"):
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            codes = [{0x19: "ru", 0x43: "uz", 0x09: "en"}.get(lang_id & 0x3FF, "")]
        else:
            import locale
            codes = [(locale.getlocale()[0] or "")]
    except Exception:
        pass
    for code in codes:
        if normalize(code) == "ru":
            return "ru"
    return DEFAULT


def installer_language() -> Optional[str]:
    """Windows oʻrnatuvchisida tanlangan til (Inno Setup reyestrga yozadi)."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Yangi Alifbo") as key:
            value, _ = winreg.QueryValueEx(key, "Language")
        return normalize(value)
    except OSError:
        return None


def resolve(cfg: dict) -> str:
    return normalize(cfg.get("language")) or installer_language() or system_language()


def fmt_num(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 0
    return f"{n:,}".replace(",", "," if base_language() == "en" else " ")


def fmt_date(day, lang: Optional[str] = None) -> str:
    """"2026-11-01" → "1-noyabr" / "1 ноября" / "Nov 1"."""
    try:
        d = day if isinstance(day, datetime.date) else datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        return str(day)
    lang = base_language(lang)
    month = MONTHS[lang][d.month - 1]
    if lang == "ru":
        return f"{d.day} {month}"
    if lang == "en":
        return f"{month} {d.day}"
    return f"{d.day}-{month}"  # oy nomlarida oʻ, gʻ, sh, ch yoʻq – yangi alifboda ham shunday


def fmt_date_year(day, lang: Optional[str] = None) -> str:
    try:
        d = day if isinstance(day, datetime.date) else datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        return str(day)
    lang = base_language(lang)
    if lang == "uz":
        return f"{d.year}-yil {fmt_date(d, lang)}"
    if lang == "ru":
        return f"{fmt_date(d, lang)} {d.year}"
    return f"{fmt_date(d, lang)}, {d.year}"
