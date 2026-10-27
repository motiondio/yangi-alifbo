#Requires AutoHotkey v2.0
#SingleInstance Force
; ============================================================================
;  Yangi Alifbo – Windows uchun AutoHotkey v2 varianti (Python talab qilmaydi)
;  oʻ/o' → ö    gʻ/g' → ğ    sh → ş    ch → ç
;
;  Oʻrnatish: https://www.autohotkey.com (v2) ni oʻrnating, soʻng bu faylni
;  ikki marta bosing.  Avtomatik ishga tushishi uchun faylni
;  Win+R → shell:startup papkasiga nusxalang (yoki yorliq qoʻying).
;
;  Yoqish/oʻchirish: Ctrl+Alt+U        Chiqish: tray belgisi → Exit
;  "s" va "h" ni alohida qoldirish:  s'h  deb tering  (Is'hoq → Ishoq)
;
;  Hotstring parametrlari:  * – tugash belgisi (boʻsh joy) kutilmaydi,
;  ? – soʻz ichida ham ishlaydi.  Katta-kichik harf avtomatik moslanadi
;  (sh → ş, Sh → Ş, SH → Ş).
; ============================================================================
SendMode "Input"
A_IconTip := "Yangi Alifbo: YOQILGAN (Ctrl+Alt+U – oʻchirish)"

; --- s'h → sh  (ş EMAS) – "sh" qoidalaridan OLDIN turishi shart ---------------
:*?:s'h::sh
:*?:sʼh::sh
:*?:sʻh::sh
:*?:s’h::sh

; --- oʻ → ö --------------------------------------------------------------------
:*?:o'::ö
:*?:oʻ::ö
:*?:oʼ::ö
:*?:o’::ö
:*?:o‘::ö

; --- gʻ → ğ --------------------------------------------------------------------
:*?:g'::ğ
:*?:gʻ::ğ
:*?:gʼ::ğ
:*?:g’::ğ
:*?:g‘::ğ

; --- sh → ş,  ch → ç ---------------------------------------------------------
:*?:sh::ş
:*?:ch::ç

; --- Yoqish / oʻchirish --------------------------------------------------------
#SuspendExempt
^!u:: {
    Suspend -1
    if A_IsSuspended {
        A_IconTip := "Yangi Alifbo: OʻCHIRILGAN (Ctrl+Alt+U – yoqish)"
        TrayTip "Almashtirish OʻCHIRILDI", "Yangi Alifbo", "Iconi"
    } else {
        A_IconTip := "Yangi Alifbo: YOQILGAN (Ctrl+Alt+U – oʻchirish)"
        TrayTip "Almashtirish YOQILDI", "Yangi Alifbo", "Iconi"
    }
}
#SuspendExempt False
