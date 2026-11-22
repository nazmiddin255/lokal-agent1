import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import alifbo  # noqa: E402
from alifbo import lotinga, yangiga  # noqa: E402


class AlifboTest(unittest.TestCase):
    def test_asosiy(self):
        self.assertEqual(yangiga("shahar choy o'zbek tog'"), "şahar çoy özbek toğ")
        self.assertEqual(yangiga("Shahar Choy O'zbekiston G'alaba"), "Şahar Çoy Özbekiston Ğalaba")
        self.assertEqual(yangiga("SHAHAR CHOY O'ZBEK G'OZ"), "ŞAHAR ÇOY ÖZBEK ĞOZ")

    def test_apostrof_variantlari(self):
        for a in ["'", "‘", "’", "ʻ", "ʼ"]:
            self.assertEqual(yangiga(f"o{a}zbek tog{a}"), "özbek toğ", repr(a))
            self.assertEqual(lotinga(f"o{a}zbek g{a}isht"), "o'zbek g'isht", repr(a))

    def test_tutuq_va_s_h(self):
        self.assertEqual(yangiga("Is'hoq ta'lim she'r"), "Is'hoq ta'lim şe'r")

    def test_himoya(self):
        kod = "```python\nprint('shu chiroyli o'g'il')\n```"
        self.assertEqual(yangiga(kod), kod)
        self.assertEqual(yangiga("`shell.sh` ni och"), "`shell.sh` ni oç")
        self.assertEqual(yangiga("https://shop.uz/chat sahifa"), "https://shop.uz/chat sahifa")
        self.assertEqual(yangiga("fayl: hisobot_shu.txt va chizma.png"), "fayl: hisobot_shu.txt va chizma.png")
        self.assertEqual(yangiga("papka ish/shaxsiy/choy"), "papka ish/shaxsiy/choy")
        self.assertEqual(yangiga("$ chmod +x ishga_tushir.sh\nshu"), "$ chmod +x ishga_tushir.sh\nşu")

    def test_inglizcha(self):
        self.assertEqual(yangiga("bash shell chat search switch the show"),
                         "bash shell chat search switch the show")
        self.assertEqual(yangiga("JavaScript fetchData my_shell sh2"), "JavaScript fetchData my_shell sh2")

    def test_istisno_fayl(self):
        self.assertIn("shell", alifbo.istisnolar())

    def test_qoshtirnoq(self):
        self.assertEqual(yangiga("'choy' dedi"), "'çoy' dedi")
        self.assertEqual(yangiga("'kino' ko'r"), "'kino' kör")

    def test_aylanma_lotin(self):
        matnlar = [
            "O'zbekiston — go'zal shahar. Choy ichamiz, keyin bog'ga boramiz.",
            "SHAHAR, CHOY, O'G'IL, G'ISHT",
            "Men kecha ishga bordim. Shu yerda qo'shiq eshitdim.",
            "Kod: `print(1)` va https://example.com sahifa, fayl.txt",
            "```\nshell chat o'g'il\n```\nShu ham.",
        ]
        for m in matnlar:
            self.assertEqual(lotinga(yangiga(m)), m, m)

    def test_aylanma_yangi(self):
        matnlar = ["Özbekiston — gözal şahar. Çoy içamiz.", "ŞAHAR ÇOY ÖĞIL", "Şu yerda qöşiq eşitdim, toğ."]
        for m in matnlar:
            self.assertEqual(yangiga(lotinga(m)), m, m)

    def test_bosh_harf_teskari(self):
        self.assertEqual(lotinga("Şahar ŞAHAR Ş"), "Shahar SHAHAR Sh")

    def test_oqim(self):
        m = "Salom! Shu yerda `shell` buyrug'i va ```\nchoy\n``` bor, o'g'il bola choy ichdi."
        for qadam in (1, 2, 3, 5, 7):
            og = alifbo.OqimOgirgich(True)
            chiq = ""
            for i in range(0, len(m), qadam):
                for t, v in og.qosh(m[i:i + qadam]):
                    chiq = v if t == "almashtir" else chiq + v
            for t, v in og.tugat():
                chiq = v if t == "almashtir" else chiq + v
            self.assertEqual(chiq, yangiga(m), qadam)

    def test_oqim_ochiq(self):
        og = alifbo.OqimOgirgich(False)
        self.assertEqual(og.qosh("shu"), [("matn", "shu")])


if __name__ == "__main__":
    unittest.main()
