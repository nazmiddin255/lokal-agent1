"""Yo'l xavfsizligi va vositalar testi. Vaqtinchalik papka ishlatiladi (o'zi tozalanadi)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402
import vositalar as v  # noqa: E402


class YolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ish = Path(self.tmp.name) / "ish"
        self.ish.mkdir()
        (Path(self.tmp.name) / "sir.txt").write_text("sir")
        os.symlink(Path(self.tmp.name), self.ish / "tashqi")      # tashqariga symlink
        os.symlink("/etc/passwd", self.ish / "passwd")
        (self.ish / "ichki").mkdir()
        os.symlink(self.ish / "ichki", self.ish / "ichki_link")   # ichkariga symlink

    def tearDown(self):
        self.tmp.cleanup()

    def test_rad_etiladi(self):
        yomon = ["/etc/passwd", "../sir.txt", "a/../../sir.txt", "~/x", "tashqi/sir.txt",
                 "passwd", "tashqi", "..", "a/..", "\x00x", "..\\sir.txt"]
        for y in yomon:
            with self.assertRaises(v.YolXatosi, msg=y):
                v.xavfsiz_yol(self.ish, y)

    def test_ruxsat(self):
        self.assertEqual(v.xavfsiz_yol(self.ish, "."), self.ish.resolve())
        self.assertEqual(v.xavfsiz_yol(self.ish, ""), self.ish.resolve())
        self.assertEqual(v.xavfsiz_yol(self.ish, "test/hello.txt"), self.ish.resolve() / "test/hello.txt")
        self.assertEqual(v.xavfsiz_yol(self.ish, "ichki_link"), (self.ish / "ichki").resolve())

    def test_ochirish_vositasi_yoq(self):
        nomlar = {t["function"]["name"] for t in v.TARIFLAR}
        self.assertEqual(nomlar, {"list_dir", "read_file", "create_folder", "write_file", "run_python",
                                  "make_docx", "make_xlsx", "make_pptx"})
        for n in nomlar:
            for soz in ("delete", "remove", "rm", "unlink", "rmdir"):
                self.assertNotIn(soz, n)
        with self.assertRaises(v.VositaXatosi):
            v.tayyorla(self.ish, "delete_file", {"path": "x"})
        manba = Path(v.__file__).read_text()
        for soz in ("unlink(", "rmtree", "os.remove", "rmdir("):
            self.assertNotIn(soz, manba)

    def test_yozuvchilar_tasdiq_talab(self):
        self.assertTrue(v.tayyorla(self.ish, "create_folder", {"path": "a"})["yozuvchi"])
        self.assertTrue(v.tayyorla(self.ish, "write_file", {"path": "a/b.txt", "content": "x"})["yozuvchi"])
        self.assertTrue(v.tayyorla(self.ish, "run_python", {"code": "print(1)"})["yozuvchi"])
        self.assertFalse(v.tayyorla(self.ish, "list_dir", {})["yozuvchi"])

    def test_yozish_va_ustidan_yozish(self):
        v.bajar(self.ish, "write_file", {"path": "t/hello.txt", "content": "Salom"})
        self.assertEqual((self.ish / "t/hello.txt").read_text(), "Salom")
        with self.assertRaises(v.VositaXatosi):
            v.tayyorla(self.ish, "write_file", {"path": "t/hello.txt", "content": "yangi"})
        with self.assertRaises(v.VositaXatosi):
            v.bajar(self.ish, "write_file", {"path": "t/hello.txt", "content": "yangi"})
        info = v.tayyorla(self.ish, "write_file", {"path": "t/hello.txt", "content": "yangi", "overwrite": True})
        self.assertTrue(info["ogohlantirish"])
        self.assertEqual((self.ish / "t/hello.txt").read_text(), "Salom")
        with self.assertRaises(v.YolXatosi):
            v.bajar(self.ish, "write_file", {"path": "tashqi/yangi.txt", "content": "x"})
        self.assertFalse((Path(self.tmp.name) / "yangi.txt").exists())

    def test_alifbo_faylga(self):
        v.bajar(self.ish, "write_file", {"path": "a.txt", "content": "shahar o'g'il"}, alifbo_yoq=True)
        self.assertEqual((self.ish / "a.txt").read_text(), "şahar öğil")
        v.bajar(self.ish, "write_file", {"path": "a.py", "content": "x = 'shahar'"}, alifbo_yoq=True)
        self.assertEqual((self.ish / "a.py").read_text(), "x = 'shahar'")

    def test_run_python(self):
        m, _ = v.bajar(self.ish, "run_python", {"code": "import os;print(os.getcwd())"})
        self.assertIn(str(self.ish.resolve()), m)
        m, _ = v.bajar(self.ish, "run_python", {"code": "import time;time.sleep(5)"}, vaqt=1)
        self.assertIn("Timeout", m)

    def test_list_va_read(self):
        (self.ish / "x.txt").write_text("abc")
        m, _ = v.bajar(self.ish, "list_dir", {"path": "."})
        self.assertIn("x.txt", m)
        self.assertNotIn("tashqi", m)
        m, _ = v.bajar(self.ish, "read_file", {"path": "x.txt"})
        self.assertEqual(m, "abc")


class MatndanChaqiruvTest(unittest.TestCase):
    def test_tool_call_teg(self):
        r = agent.matndan_chaqiruv('<tool_call>\n{"name": "create_folder", "arguments": {"path": "test"},}\n</tool_call>')
        self.assertEqual(r[0]["function"]["name"], "create_folder")
        self.assertEqual(r[0]["function"]["arguments"], {"path": "test"})

    def test_oddiy_json(self):
        r = agent.matndan_chaqiruv('{"name": "list_dir", "arguments": {}}')
        self.assertEqual(r[0]["function"]["name"], "list_dir")

    def test_buzuq(self):
        self.assertEqual(agent.matndan_chaqiruv("<tool_call>{name: x</tool_call>"), "xato")
        self.assertIsNone(agent.matndan_chaqiruv("Salom, qalaysiz?"))


if __name__ == "__main__":
    unittest.main()
