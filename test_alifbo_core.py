# -*- coding: utf-8 -*-
"""alifbo_core uchun testlar.  Ishga tushirish:  python3 -m unittest -v test_alifbo_core"""
import unittest

from alifbo_core import Engine, convert_text


class Screen:
    """Haqiqiy dastur oʻrniga: terilgan belgilar va Action'larni matnga qoʻllaydi."""

    def __init__(self, **engine_kwargs):
        self.engine = Engine(**engine_kwargs)
        self.text = ""

    def _apply(self, action):
        if action is None:
            return
        if action.delete:
            self.text = self.text[: -action.delete]
        self.text += action.insert

    def type(self, s):
        for ch in s:
            if ch == "\b":
                self.backspace()
                continue
            self.text += ch  # dastur belgini allaqachon qabul qildi
            self._apply(self.engine.feed_char(ch))
        return self.text

    def backspace(self):
        self.text = self.text[:-1]
        self._apply(self.engine.feed_backspace())
        return self.text

    def click(self):
        self.engine.reset()


class EngineTests(unittest.TestCase):
    def test_basic_lowercase(self):
        self.assertEqual(Screen().type("o'zbek"), "özbek")
        self.assertEqual(Screen().type("g'isht"), "ğişt")
        self.assertEqual(Screen().type("shahar"), "şahar")
        self.assertEqual(Screen().type("choy"), "çoy")

    def test_all_apostrophe_variants(self):
        for ap in "'ʻʼ‘’`´":
            self.assertEqual(Screen().type(f"o{ap}zbek"), "özbek", ap)
            self.assertEqual(Screen().type(f"g{ap}oz"), "ğoz", ap)

    def test_case(self):
        self.assertEqual(Screen().type("O'zbekiston"), "Özbekiston")
        self.assertEqual(Screen().type("G'ALABA"), "ĞALABA")
        self.assertEqual(Screen().type("Shahar"), "Şahar")
        self.assertEqual(Screen().type("SHAHAR"), "ŞAHAR")
        self.assertEqual(Screen().type("Chiroq"), "Çiroq")
        self.assertEqual(Screen().type("CHIROQ"), "ÇIROQ")
        self.assertEqual(Screen().type("sH"), "ş")  # katta-kichiklik birinchi harfdan

    def test_combined_word(self):
        self.assertEqual(Screen().type("ko'cha"), "köça")
        self.assertEqual(Screen().type("o'sha"), "öşa")
        self.assertEqual(Screen().type("qashqirg'a"), "qaşqirğa")
        self.assertEqual(Screen().type("Toshkent shahri, O'zbekiston"), "Toşkent şahri, Özbekiston")

    def test_ng_unchanged(self):
        self.assertEqual(Screen().type("tong keng ming"), "tong keng ming")

    def test_tutuq_kept_by_default(self):
        self.assertEqual(Screen().type("ma'no san'at she'r"), "ma'no san'at şe'r")
        self.assertEqual(Screen().type("maʼno"), "maʼno")

    def test_tutuq_normalisation(self):
        s = Screen(tutuq="ʼ")
        self.assertEqual(s.type("ma'no she'r o'g'il"), "maʼno şeʼr öğil")
        # harfdan keyin kelmagan apostrof tegilmaydi
        self.assertEqual(Screen(tutuq="ʼ").type("'salom"), "'salom")

    def test_s_apostrophe_h_is_not_sh(self):
        self.assertEqual(Screen().type("Is'hoq"), "Ishoq")
        self.assertEqual(Screen().type("as'hob"), "ashob")
        self.assertEqual(Screen().type("Isʼhoq"), "Ishoq")
        # strip oʻchirilgan boʻlsa – apostrof qoladi, lekin ş boʻlmaydi
        self.assertEqual(Screen(strip_sh_apostrophe=False).type("Is'hoq"), "Is'hoq")
        # tutuq normalizatsiyasi bilan birga ham
        self.assertEqual(Screen(tutuq="ʼ").type("Is'hoq"), "Ishoq")

    def test_backspace_undo(self):
        s = Screen()
        s.type("sh")
        self.assertEqual(s.text, "ş")
        s.backspace()
        self.assertEqual(s.text, "sh")  # asl yozuv qaytdi
        s.type("oq")
        self.assertEqual(s.text, "shoq")  # va qayta almashtirilmaydi
        # keyingi "sh" lar yana normal ishlaydi
        s.type(" shu")
        self.assertEqual(s.text, "shoq şu")

    def test_backspace_undo_single(self):
        s = Screen()
        s.type("o'")
        self.assertEqual(s.text, "ö")
        s.backspace()
        self.assertEqual(s.text, "o'")
        s.type("zbek")
        self.assertEqual(s.text, "o'zbek")

    def test_backspace_undo_only_immediately(self):
        s = Screen()
        s.type("sha")
        s.backspace()  # "a" oʻchdi, ş qoladi
        self.assertEqual(s.text, "ş")
        s.backspace()  # endi ş oʻchadi, undo yoʻq
        self.assertEqual(s.text, "")

    def test_backspace_undo_disabled(self):
        s = Screen(backspace_undo=False)
        s.type("sh")
        s.backspace()
        self.assertEqual(s.text, "")

    def test_backspace_then_retype_after_undo_stays_locked(self):
        s = Screen()
        s.type("sh")
        s.backspace()           # "sh"
        s.backspace()           # "s" (qulflangan)
        s.type("h")
        self.assertEqual(s.text, "sh")

    def test_reset_breaks_context(self):
        s = Screen()
        s.type("s")
        s.click()
        s.type("h")
        self.assertEqual(s.text, "sh")
        s = Screen()
        s.type("o")
        s.engine.feed_char("\n")  # Enter / boshqaruv belgisi
        s.type("'")
        self.assertEqual(s.engine.context, "'")

    def test_non_letters_reset(self):
        self.assertEqual(Screen().type("s h"), "s h")
        self.assertEqual(Screen().type("s-h"), "s-h")
        self.assertEqual(Screen().type("o 'z"), "o 'z")
        self.assertEqual(Screen().type("3sh"), "3ş")

    def test_already_new_letters_untouched(self):
        self.assertEqual(Screen().type("Özbekiston şahri çoy ğoz"), "Özbekiston şahri çoy ğoz")

    def test_english_words_do_convert(self):
        # Bu dastur yoqilganda ingliz tilidagi "sh" ham almashadi – shuning
        # uchun tezkor tugma bilan oʻchirish mumkin.  Hujjatlashtirilgan xatti-harakat.
        self.assertEqual(Screen().type("shop"), "şop")

    def test_buffer_limit(self):
        s = Screen(maxlen=4)
        s.type("abcdefghijklmnop")
        self.assertEqual(len(s.engine.context), 4)
        s.type("sh")
        self.assertTrue(s.text.endswith("ş"))


class ConvertTextTests(unittest.TestCase):
    def test_sentence(self):
        self.assertEqual(
            convert_text("O'zbekiston Respublikasi, Toshkent shahri. Sho'x g'oz cho'l."),
            "Özbekiston Respublikasi, Toşkent şahri. Şöx ğoz çöl.",
        )

    def test_official_apostrophes(self):
        self.assertEqual(convert_text("Oʻzbekiston, gʻisht, sheʼr"), "Özbekiston, ğişt, şeʼr")

    def test_case(self):
        self.assertEqual(convert_text("SHAHAR Shahar shahar CH Ch ch O' o' G' g'"),
                         "ŞAHAR Şahar şahar Ç Ç ç Ö ö Ğ ğ")

    def test_s_apostrophe_h(self):
        self.assertEqual(convert_text("Is'hoq, as'hob, mas'ul"), "Ishoq, ashob, mas'ul")
        self.assertEqual(convert_text("Is'hoq", strip_sh_apostrophe=False), "Is'hoq")

    def test_tutuq(self):
        self.assertEqual(convert_text("ma'no san'at she'r", tutuq="ʼ"), "maʼno sanʼat şeʼr")
        self.assertEqual(convert_text("'quote'", tutuq="ʼ"), "'quoteʼ")

    def test_ng(self):
        self.assertEqual(convert_text("tong, keng, ming"), "tong, keng, ming")

    def test_idempotent(self):
        once = convert_text("O'zbekiston sho'x g'isht choy")
        self.assertEqual(convert_text(once), once)


if __name__ == "__main__":
    unittest.main()
