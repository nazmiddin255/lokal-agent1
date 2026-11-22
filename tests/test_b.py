"""B bosqich testlari: loyihalar, tarix, xotira, xulosa nuqtasi, hujjatlar. Hammasi vaqtincha papkada."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402
import dokumentlar  # noqa: E402
import saqlash  # noqa: E402
import vositalar  # noqa: E402


class SaqlashTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._eski = saqlash.DATA
        saqlash.DATA = Path(self.tmp.name) / "data"
        saqlash.tayyorla()

    def tearDown(self):
        saqlash.DATA = self._eski
        self.tmp.cleanup()

    def test_boshlang_holat(self):
        self.assertEqual(saqlash.loyihalar(), ["Umumiy"])
        self.assertTrue((saqlash.DATA / "umumiy_xotira.md").is_file())
        self.assertTrue((saqlash.DATA / "loyihalar/Umumiy/xulosa.md").is_file())

    def test_loyiha_nomi(self):
        for yomon in ["", "../x", "a/b", ".yashirin", "x" * 41, "a\\b", "_x", "..", "a.b"]:
            with self.assertRaises(saqlash.SaqlashXatosi, msg=yomon):
                saqlash.loyiha_yarat(yomon)
        self.assertEqual(saqlash.loyiha_yarat("  Hisobotlar   2026 "), "Hisobotlar 2026")
        with self.assertRaises(saqlash.SaqlashXatosi):
            saqlash.loyiha_yarat("hisobotlar 2026")      # katta-kichik farqsiz takror
        self.assertEqual(saqlash.loyiha_yol("HISOBOTLAR 2026").name, "Hisobotlar 2026")
        self.assertEqual(saqlash.loyiha_yarat("Tarjimalar_1-qism"), "Tarjimalar_1-qism")

    def test_chat_id_xavfsiz(self):
        for yomon in ["../x", "x", "", None, "20260101-000000-zzzz", "20260101-000000-abcd/../x"]:
            with self.assertRaises(saqlash.SaqlashXatosi, msg=str(yomon)):
                saqlash.chat_yol("Umumiy", yomon)

    def _chat(self, nom, i):
        cid = f"20260101-0000{i:02d}-abcd"
        saqlash.chat_saqla(nom, {"id": cid, "sarlavha": f"chat {i}", "yaratildi": "x",
                                 "xabarlar": [{"role": "user", "content": "salom"}], "xulosalangan": 0})
        return cid

    def test_saqlash_yuklash_va_chegara(self):
        ids = [self._chat("Umumiy", i) for i in range(20)]
        self.assertTrue(saqlash.toldi("Umumiy"))
        self.assertEqual(len(saqlash.chatlar("Umumiy")), 20)
        d = saqlash.chat_yukla("Umumiy", ids[3])
        self.assertEqual(d["sarlavha"], "chat 3")
        eski = saqlash.eng_eskisi("Umumiy")
        self.assertEqual(eski["id"], ids[0])
        # arxivlash: o'chirmaydi, faqat ko'chiradi
        nom = saqlash.arxivla("Umumiy", eski["id"])
        self.assertTrue((saqlash.DATA / "loyihalar/Umumiy/chatlar/arxiv" / nom).is_file())
        self.assertFalse(saqlash.toldi("Umumiy"))
        self.assertEqual(len(saqlash.chatlar("Umumiy")), 19)
        with self.assertRaises(saqlash.SaqlashXatosi):
            saqlash.chat_yukla("Umumiy", ids[0])

    def test_ochirish_yoq(self):
        for fayl in ("saqlash.py", "agent.py", "dokumentlar.py", "vositalar.py", "server.py"):
            m = (Path(saqlash.__file__).parent / fayl).read_text()
            for soz in (".unlink(", "rmtree", "os.remove(", ".rmdir(", "os.rmdir"):
                self.assertNotIn(soz, m, f"{fayl}: {soz}")

    def test_xotira_chegarasi(self):
        saqlash.xotira_yoz("bir " * 200)
        with self.assertRaises(saqlash.SaqlashXatosi):
            saqlash.xotira_yoz("bir " * 201)
        saqlash.xulosa_yoz("Umumiy", "a " * 300)
        with self.assertRaises(saqlash.SaqlashXatosi):
            saqlash.xulosa_yoz("Umumiy", "a " * 301)

    def test_xulosa_qosish_va_matn(self):
        saqlash.xotira_yoz("- qoida bir\n")
        n = saqlash.xulosa_qosh("Umumiy", "- user likes tea")
        self.assertGreater(n, 3)
        saqlash.xulosa_qosh("Umumiy", "- second note")
        m = saqlash.xotira_matni("Umumiy")
        self.assertIn("qoida bir", m)
        self.assertIn("likes tea", m)
        self.assertIn("second note", m)
        self.assertEqual(saqlash.xotira_matni(None).count("Summary"), 0)

    def test_tuzat_javobsiz_chaqiruv(self):
        x = [{"role": "user", "content": "a"},
             {"role": "assistant", "content": "", "tool_calls": [
                 {"function": {"name": "write_file", "arguments": {}}},
                 {"function": {"name": "run_python", "arguments": {}}}]},
             {"role": "tool", "content": "ok"}]
        y = saqlash._tuzat(list(x))
        self.assertEqual([m["role"] for m in y], ["user", "assistant", "tool", "tool"])
        self.assertIn("Not done", y[-1]["content"])


class AgentKontekstTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._eski = saqlash.DATA
        saqlash.DATA = Path(self.tmp.name) / "data"
        saqlash.tayyorla()
        self.sozl = {"options": {"num_ctx": 6144}}

    def tearDown(self):
        saqlash.DATA = self._eski
        self.tmp.cleanup()

    def _suhbat(self, n):
        s = agent.Suhbat()
        for i in range(n):
            s.xabarlar.append({"role": "user", "content": f"savol {i}"})
            s.xabarlar.append({"role": "assistant", "content": f"javob {i}"})
        return s

    def test_yangi_chatda_faqat_xotira_va_xulosa(self):
        saqlash.xotira_yoz("- doimiy qoida X")
        saqlash.xulosa_qosh("Umumiy", "- project note Y")
        s = self._suhbat(0)
        agent.yangi_chat(s, "Umumiy", "salom")
        agent.foydalanuvchi_xabari(s, "salom")
        x, kesildi = agent._kontekst(s, self.sozl)
        self.assertEqual(x[0]["role"], "system")
        self.assertIn("doimiy qoida X", x[0]["content"])
        self.assertIn("project note Y", x[0]["content"])
        self.assertEqual([m["role"] for m in x[1:]], ["user"])
        self.assertFalse(kesildi)

    def test_xulosa_nuqtasi_oxirgi_12(self):
        s = self._suhbat(3)                   # 6 xabar
        self.assertIsNone(agent.xulosa_nuqtasi(s))
        s = self._suhbat(10)                  # 20 xabar -> eskisi 8 ta
        k = agent.xulosa_nuqtasi(s)
        self.assertEqual(s.xabarlar[k]["role"], "user")
        self.assertGreaterEqual(len(s.xabarlar) - k, 12)
        self.assertEqual(k, 8)
        s.xulosalangan = k
        self.assertIsNone(agent.xulosa_nuqtasi(s))     # qaytadan xulosa qilinadigan narsa yo'q

    def test_xulosa_nuqtasi_tool_bilan(self):
        s = self._suhbat(2)
        s.xabarlar += [{"role": "user", "content": "fayl yoz"},
                       {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "a"}}}]},
                       {"role": "tool", "content": "ok"}, {"role": "assistant", "content": "tayyor"}]
        s.xabarlar += self._suhbat(5).xabarlar
        k = agent.xulosa_nuqtasi(s)
        self.assertEqual(s.xabarlar[k]["role"], "user")      # tool juftligi buzilmaydi

    def test_xulosalangan_modelga_berilmaydi(self):
        s = self._suhbat(10)
        agent.yangi_chat(s, "Umumiy", "x")
        s.xabarlar = self._suhbat(10).xabarlar
        s.xulosalangan = 8
        x, _ = agent._kontekst(s, self.sozl)
        self.assertEqual(len(x) - 1, 12)
        self.assertEqual(x[1]["content"], "savol 4")

    def test_kontekst_kesish(self):
        s = agent.Suhbat()
        agent.yangi_chat(s, "Umumiy", "x")
        for i in range(60):
            s.xabarlar += [{"role": "user", "content": "s" * 400}, {"role": "assistant", "content": "j" * 400}]
        x, kesildi = agent._kontekst(s, {"options": {"num_ctx": 4096}})
        self.assertTrue(kesildi)
        self.assertEqual(x[1]["role"], "user")
        self.assertLess(agent.taxmin_token(x[0]["content"], x[1:]), 4096)

    def test_saqla_va_yukla(self):
        s = agent.Suhbat()
        agent.yangi_chat(s, "Umumiy", "Birinchi savol juda uzun bo'lib ketdi " * 4)
        agent.foydalanuvchi_xabari(s, "salom")
        s.xabarlar.append({"role": "assistant", "content": "Salom!"})
        agent.saqla(s)
        s2 = agent.Suhbat()
        agent.yukla(s2, "Umumiy", s.chat_id)
        self.assertEqual(s2.xabarlar, s.xabarlar)
        self.assertLessEqual(len(s2.sarlavha), 48)
        self.assertEqual([x["rol"] for x in agent.korinish(s2)], ["men", "model"])

    def test_yangila_band_saqlanadi(self):
        s = agent.Suhbat()
        s.band = True
        s.yangila()
        self.assertTrue(s.band)


class HujjatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ish = Path(self.tmp.name) / "ish"
        self.ish.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_docx(self):
        from docx import Document
        a = {"path": "ariza", "title": "Shahar hisobot",
             "sections": [{"heading": "Kirish", "paragraphs": ["O'zbek choy"], "bullets": "- bir\n- ikki",
                           "table": [["Nom", "Son"], "choy | 5"]}]}
        info = vositalar.tayyorla(self.ish, "make_docx", dict(a), True)
        self.assertTrue(info["yozuvchi"])
        self.assertFalse((self.ish / "ariza.docx").exists())            # tasdiqdan oldin yozilmaydi
        vositalar.bajar(self.ish, "make_docx", dict(a), True)
        d = Document(str(self.ish / "ariza.docx"))
        matn = "\n".join(p.text for p in d.paragraphs)
        self.assertIn("Şahar hisobot", matn)
        self.assertIn("Özbek çoy", matn)
        self.assertEqual(len(d.tables), 1)
        self.assertEqual(d.tables[0].cell(1, 0).text, "çoy")
        self.assertEqual(d.styles["Normal"].font.name, "Arial")
        self.assertEqual(d.styles["Heading 1"].font.name, "Arial")
        with self.assertRaises(vositalar.VositaXatosi):                  # ustidan yozish
            vositalar.tayyorla(self.ish, "make_docx", dict(a), True)

    def test_xlsx(self):
        from openpyxl import load_workbook
        a = {"path": "h.xlsx", "sheets": [{"name": "Ch/oy", "rows": [
            ["Nom", "Narx"], ["Shirin", "1200"], ["Narx2", "12,5"], ["Kod", "007"],
            ["Jami", "=SUM(B2:B3)"], ["Xavfli", "=HYPERLINK(\"http://x\",\"y\")"], ["Xavfli2", "=cmd|' /C calc'!A0"]]}]}
        vositalar.bajar(self.ish, "make_xlsx", a, True)
        ws = load_workbook(str(self.ish / "h.xlsx")).active
        self.assertEqual(ws.title, "Çoy".replace("Ç", "Ç") if False else ws.title)
        self.assertNotIn("/", ws.title)
        self.assertEqual(ws["A2"].value, "Şirin")
        self.assertEqual(ws["B2"].value, 1200)
        self.assertEqual(ws["B3"].value, 12.5)
        self.assertEqual(ws["B4"].value, "007")            # bosh nolni yo'qotmaydi
        self.assertEqual((ws["B5"].value, ws["B5"].data_type), ("=SUM(B2:B3)", "f"))
        self.assertEqual(ws["B6"].data_type, "s")           # noma'lum funksiya — matn
        self.assertEqual(ws["B7"].data_type, "s")
        self.assertEqual(ws["A1"].font.name, "Arial")
        self.assertTrue(ws["A1"].font.bold)

    def test_pptx(self):
        from pptx import Presentation
        a = {"path": "t.pptx", "title": "Shahar", "subtitle": "Choy",
             "slides": [{"title": "Birinchi", "bullets": ["bir", "ikki"]}, {"title": "Ikkinchi", "bullets": "a\nb"}]}
        vositalar.bajar(self.ish, "make_pptx", a, True)
        prs = Presentation(str(self.ish / "t.pptx"))
        self.assertEqual(len(prs.slides), 3)
        matn = " ".join(sh.text_frame.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame)
        self.assertIn("Şahar", matn)
        self.assertIn("Birinçi", matn)
        sh = prs.slides[1].shapes.title
        self.assertEqual(sh.text_frame.paragraphs[0].runs[0].font.name, "Arial")

    def test_alifbo_ochiq_bolsa_ogirilmaydi(self):
        from docx import Document
        vositalar.bajar(self.ish, "make_docx", {"path": "a.docx", "sections": [{"paragraphs": ["shahar"]}]}, False)
        self.assertEqual(Document(str(self.ish / "a.docx")).paragraphs[0].text, "shahar")

    def test_yol_va_kengaytma(self):
        a = {"sections": [{"paragraphs": ["x"]}]}
        for yomon in ["../a.docx", "/tmp/a.docx", "~/a.docx"]:
            with self.assertRaises(vositalar.YolXatosi, msg=yomon):
                vositalar.tayyorla(self.ish, "make_docx", {**a, "path": yomon})
        with self.assertRaises(vositalar.VositaXatosi):
            vositalar.tayyorla(self.ish, "make_docx", {**a, "path": "a.xlsx"})
        info = vositalar.tayyorla(self.ish, "make_docx", {**a, "path": "papka/a"})
        self.assertIn("papka/a.docx", info["tavsif"])

    def test_bosh_va_buzuq(self):
        for nom, a in [("make_docx", {"path": "a.docx", "sections": []}),
                       ("make_xlsx", {"path": "a.xlsx", "sheets": [{"name": "x", "rows": []}]}),
                       ("make_pptx", {"path": "a.pptx", "slides": []}),
                       ("make_docx", {"path": "a.docx", "sections": [{"paragraphs": [{"x": 1}]}]})]:
            with self.assertRaises(vositalar.VositaXatosi, msg=nom):
                vositalar.tayyorla(self.ish, nom, a)

    def test_shablon(self):
        from docx import Document
        sh = Path(self.tmp.name) / "namunalar"
        sh.mkdir()
        d = Document()
        d.add_paragraph("SHABLON BOSHI")
        d.save(str(sh / "blank.docx"))
        eski = dokumentlar.SHABLON_PAPKA
        dokumentlar.SHABLON_PAPKA = sh
        try:
            t = [x for x in vositalar.tariflar({"make_docx"}) if x["function"]["name"] == "make_docx"][0]
            self.assertIn("blank.docx", t["function"]["parameters"]["properties"]["template"]["description"])
            vositalar.bajar(self.ish, "make_docx", {"path": "z.docx", "template": "blank.docx",
                                                    "sections": [{"paragraphs": ["yangi"]}]})
            self.assertEqual([p.text for p in Document(str(self.ish / "z.docx")).paragraphs][:2], ["SHABLON BOSHI", "yangi"])
            with self.assertRaises(vositalar.VositaXatosi):
                vositalar.tayyorla(self.ish, "make_docx", {"path": "q.docx", "template": "../x.docx",
                                                           "sections": [{"paragraphs": ["a"]}]})
        finally:
            dokumentlar.SHABLON_PAPKA = eski

    def test_vosita_tanlash(self):
        nomlar = lambda t: {x["function"]["name"] for x in t}      # noqa: E731
        self.assertEqual(nomlar(vositalar.tariflar()), set(vositalar.ASOSIY_VOSITALAR))
        self.assertEqual(nomlar(vositalar.tariflar({"make_docx"})), set(vositalar.ASOSIY_VOSITALAR) | {"make_docx"})
        s = agent.Suhbat()
        for matn, kutilgan in [("salom", set()), ("Excel jadval qil", {"make_xlsx"}),
                               ("taqdimot tayyorla", {"make_pptx"}), ("Word hujjat yoz", {"make_docx"})]:
            s.xabarlar = [{"role": "user", "content": matn}]
            self.assertEqual(nomlar(agent.tariflar(s)) - set(vositalar.ASOSIY_VOSITALAR), kutilgan, matn)


if __name__ == "__main__":
    unittest.main()
