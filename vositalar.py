"""Agent vositalari. Hammasi FAQAT ish papkasi ichida ishlaydi.
O'chirish vositasi ataylab YO'Q. Yozuvchi vositalar foydalanuvchi tasdig'isiz bajarilmaydi."""
import io
import os
import resource
import subprocess
import sys
from pathlib import Path

import alifbo
import dokumentlar

MAX_OQISH = 4000        # modelga beriladigan fayl matni (belgi)
MAX_CHIQISH = 3000      # run_python chiqishi (belgi)
MAX_ROYXAT = 200


class YolXatosi(Exception):
    pass


class VositaXatosi(Exception):
    pass


def xavfsiz_yol(ish, rel):
    """rel yo'lni ish papkasi ichidagi haqiqiy yo'lga aylantiradi.
    Absolyut yo'l, '~', '..', tashqariga olib chiquvchi symlink — rad etiladi."""
    if not isinstance(rel, str):
        raise YolXatosi("path must be a string")
    rel = rel.strip().replace("\\", "/")
    if "\x00" in rel:
        raise YolXatosi("invalid path")
    if rel in ("", ".", "./"):
        return Path(ish).resolve()
    if rel.startswith("~"):
        raise YolXatosi("'~' paths are not allowed; use a path relative to the work folder")
    p = Path(rel)
    if p.is_absolute():
        raise YolXatosi("absolute paths are not allowed; use a path relative to the work folder")
    if ".." in p.parts:
        raise YolXatosi("'..' is not allowed in paths")
    asos = Path(ish).resolve()
    toliq = (asos / p).resolve()
    if toliq != asos and not toliq.is_relative_to(asos):
        raise YolXatosi("path points outside the work folder (symlink?)")
    return toliq


def nisbiy(ish, yol):
    r = Path(yol).relative_to(Path(ish).resolve()).as_posix()
    return r if r != "." else "."


# ---------------- vosita ta'riflari (Ollama tools formati) ----------------

def _f(nom, tavsif, xossalar, majburiy):
    return {"type": "function", "function": {
        "name": nom, "description": tavsif,
        "parameters": {"type": "object", "properties": xossalar, "required": majburiy}}}


TARIFLAR = [
    _f("list_dir", "List files and folders in a folder of the work folder.",
       {"path": {"type": "string", "description": "Relative folder path, '.' for the work folder root"}}, []),
    _f("read_file", "Read a text file from the work folder.",
       {"path": {"type": "string", "description": "Relative file path"}}, ["path"]),
    _f("create_folder", "Create a folder (and parents) in the work folder.",
       {"path": {"type": "string", "description": "Relative folder path, e.g. 'test'"}}, ["path"]),
    _f("write_file", "Save a text file. Use ONLY when the user explicitly asks to save or create a file. To just show code, answer in chat instead. Fails if the file exists unless overwrite is true.",
       {"path": {"type": "string", "description": "Relative file path, e.g. 'test/hello.txt'"},
        "content": {"type": "string", "description": "Full file content"},
        "overwrite": {"type": "boolean", "description": "Only true if the user clearly asked to replace the existing file"}},
       ["path", "content"]),
    _f("run_python", "Run Python code inside the work folder. Use only when the user asks to run or test code. Give either 'code' or 'path' to a .py file.",
       {"code": {"type": "string", "description": "Python source code to run"},
        "path": {"type": "string", "description": "Relative path of a .py file to run"}}, []),
]

_S = {"type": "string"}
_ROYXAT = {"type": "array", "items": _S}
_JADVAL = {"type": "array", "description": "Table rows; the first row is the header",
           "items": {"type": "array", "items": _S}}
_OVERWRITE = {"type": "boolean", "description": "Only true if the user clearly asked to replace the existing file"}

TARIFLAR += [
    _f("make_docx",
       "Create a Word (.docx) document. Give only the content; the program makes the layout. "
       "Use only when the user asks for a Word document.",
       {"path": {"type": "string", "description": "Relative file path ending with .docx, e.g. 'ariza.docx'"},
        "title": {"type": "string", "description": "Document title"},
        "sections": {"type": "array", "description": "Sections in order", "items": {
            "type": "object", "properties": {
                "heading": _S, "paragraphs": _ROYXAT, "bullets": _ROYXAT, "table": _JADVAL}}},
        "overwrite": _OVERWRITE}, ["path", "sections"]),
    _f("make_xlsx",
       "Create an Excel (.xlsx) workbook. Give only the data; the program formats it. "
       "Use only when the user asks for an Excel file. Numbers can be written as strings. "
       "Simple formulas like =SUM(B2:B5) are allowed.",
       {"path": {"type": "string", "description": "Relative file path ending with .xlsx, e.g. 'hisob.xlsx'"},
        "sheets": {"type": "array", "description": "Sheets in order", "items": {
            "type": "object", "properties": {"name": _S, "rows": _JADVAL}}},
        "overwrite": _OVERWRITE}, ["path", "sheets"]),
    _f("make_pptx",
       "Create a PowerPoint (.pptx) presentation. Give only the content; the program makes the layout. "
       "Use only when the user asks for a presentation.",
       {"path": {"type": "string", "description": "Relative file path ending with .pptx, e.g. 'taqdimot.pptx'"},
        "title": {"type": "string", "description": "Title of the first slide"},
        "subtitle": {"type": "string", "description": "Subtitle of the first slide"},
        "slides": {"type": "array", "description": "Content slides in order", "items": {
            "type": "object", "properties": {"title": _S, "bullets": _ROYXAT}}},
        "overwrite": _OVERWRITE}, ["path", "slides"]),
]

NOMLAR = {t["function"]["name"] for t in TARIFLAR}
YOZUVCHI = {"create_folder", "write_file", "run_python"} | set(dokumentlar.KENGAYTMA)


ASOSIY_VOSITALAR = ("list_dir", "read_file", "create_folder", "write_file", "run_python")


def tariflar(hujjat=()):
    """Modelga beriladigan ta'riflar: 5 ta asosiy + so'ralgan hujjat vositalari (kontekst tejash uchun).
    Namunalar papkasida shablon bo'lsa, 'template' parametri qo'shiladi."""
    import copy
    t = [copy.deepcopy(x) for x in TARIFLAR
         if x["function"]["name"] in ASOSIY_VOSITALAR or x["function"]["name"] in hujjat]
    for x in t:
        nom = x["function"]["name"]
        if nom in dokumentlar.KENGAYTMA:
            mavjud = dokumentlar.shablonlar(dokumentlar.KENGAYTMA[nom])
            if mavjud:
                x["function"]["parameters"]["properties"]["template"] = {
                    "type": "string",
                    "description": "Optional template file name. Use only if the user asks for a template. Available: "
                                   + ", ".join(mavjud)}
    return t


def _hujjat_yol(ish, nom, args):
    ext = dokumentlar.KENGAYTMA[nom]
    rel = str(args["path"]).strip()
    ism = rel.replace("\\", "/").rsplit("/", 1)[-1]
    if not rel.lower().endswith(ext):
        if "." in ism:
            raise VositaXatosi(f"path must end with {ext}")
        rel += ext
    return xavfsiz_yol(ish, rel)


def _tekshir_arglar(nom, args):
    if nom not in NOMLAR:
        raise VositaXatosi(f"unknown tool '{nom}'. Available: {', '.join(sorted(NOMLAR))}")
    if not isinstance(args, dict):
        raise VositaXatosi("arguments must be a JSON object")
    sxema = next(t for t in TARIFLAR if t["function"]["name"] == nom)["function"]["parameters"]
    for m in sxema["required"]:
        if m not in args:
            raise VositaXatosi(f"missing required argument '{m}'")
    for k, v in args.items():
        if k not in sxema["properties"]:
            continue
        tur = sxema["properties"][k]["type"]
        if tur == "string" and not isinstance(v, str):
            if isinstance(v, (int, float)):
                args[k] = str(v)
            else:
                raise VositaXatosi(f"argument '{k}' must be a string")
        if tur == "boolean" and not isinstance(v, bool):
            args[k] = str(v).lower() in ("true", "1", "yes")
    if nom == "run_python" and not (args.get("code") or args.get("path")):
        raise VositaXatosi("give 'code' or 'path'")


def _matnga(fayl, kontent, alifbo_yoq):
    if alifbo_yoq and Path(fayl).suffix.lower() in (".txt", ".md"):
        return alifbo.yangiga(kontent)
    return kontent


def tayyorla(ish, nom, args, alifbo_yoq=False):
    """Vositani tekshiradi. Yozuvchi bo'lsa tasdiq uchun ma'lumot qaytaradi.
    Qaytadi: dict(yozuvchi, tavsif, tafsilot, ogohlantirish). Xato bo'lsa VositaXatosi/YolXatosi."""
    _tekshir_arglar(nom, args)
    r = {"yozuvchi": nom in YOZUVCHI, "tavsif": "", "tafsilot": "", "ogohlantirish": ""}
    ish_nomi = Path(ish).name
    if nom == "list_dir":
        y = xavfsiz_yol(ish, args.get("path", "."))
        r["tavsif"] = f"Papka ko'rilmoqda: {ish_nomi}/{nisbiy(ish, y)}"
    elif nom == "read_file":
        y = xavfsiz_yol(ish, args["path"])
        r["tavsif"] = f"Fayl o'qilmoqda: {ish_nomi}/{nisbiy(ish, y)}"
    elif nom == "create_folder":
        y = xavfsiz_yol(ish, args["path"])
        if y.exists() and not y.is_dir():
            raise VositaXatosi("a file with this name already exists")
        r["tavsif"] = f"Papka yaratish: {ish_nomi}/{nisbiy(ish, y)}"
        if y.is_dir():
            r["tafsilot"] = "(papka allaqachon bor)"
    elif nom == "write_file":
        y = xavfsiz_yol(ish, args["path"])
        if y.is_dir():
            raise VositaXatosi("path is a folder, not a file")
        if y.exists() and not args.get("overwrite"):
            raise VositaXatosi("file already exists. Do not overwrite unless the user clearly asks; "
                               "then call again with overwrite=true")
        kontent = _matnga(y, args["content"], alifbo_yoq)
        r["tavsif"] = f"Fayl yozish: {ish_nomi}/{nisbiy(ish, y)} ({len(kontent)} belgi)"
        if not y.parent.exists():
            r["tavsif"] += " — papkasi ham yaratiladi"
        r["tafsilot"] = kontent[:1500] + ("\n…" if len(kontent) > 1500 else "")
        if y.exists():
            r["ogohlantirish"] = "DIQQAT: bu fayl allaqachon bor. Ha bosilsa, eski matn o'rniga yangisi yoziladi!"
    elif nom in dokumentlar.KENGAYTMA:
        y = _hujjat_yol(ish, nom, args)
        if y.is_dir():
            raise VositaXatosi("path is a folder, not a file")
        if y.exists() and not args.get("overwrite"):
            raise VositaXatosi("file already exists. Do not overwrite unless the user clearly asks; "
                               "then call again with overwrite=true")
        try:
            n = dokumentlar.normallash(nom, args, alifbo_yoq)
            dokumentlar.shablon_yol(args.get("template"), dokumentlar.KENGAYTMA[nom])
        except ValueError as e:
            raise VositaXatosi(str(e))
        r["tavsif"] = f"{dokumentlar.xulosa_qator(nom, n)} — saqlanadi: {ish_nomi}/{nisbiy(ish, y)}"
        r["tafsilot"] = dokumentlar.korsatma(nom, n)
        if y.exists():
            r["ogohlantirish"] = "DIQQAT: bu fayl allaqachon bor. Ha bosilsa, eskisi o'rniga yangisi yoziladi!"
    elif nom == "run_python":
        if args.get("code"):
            r["tavsif"] = f"Python kodini ishga tushirish ({ish_nomi}/ ichida)"
            r["tafsilot"] = args["code"][:1500]
        else:
            y = xavfsiz_yol(ish, args["path"])
            if not y.is_file():
                raise VositaXatosi("file not found")
            r["tavsif"] = f"Python faylini ishga tushirish: {ish_nomi}/{nisbiy(ish, y)}"
            try:
                r["tafsilot"] = y.read_text(encoding="utf-8", errors="replace")[:1500]
            except OSError:
                pass
        r["ogohlantirish"] = "Kod kompyuteringizda ishlaydi. Faqat ishonchli kodga Ha bosing."
    return r


def _cheklov(chegara_mb=512):
    def f():
        b = chegara_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (b, b))
        except (ValueError, OSError):
            pass
        os.setsid()
    return f


def bajar(ish, nom, args, alifbo_yoq=False, vaqt=30):
    """Vositani bajaradi. Qaytadi: (modelga_inglizcha, foydalanuvchiga_ozbekcha)."""
    _tekshir_arglar(nom, args)
    ish_nomi = Path(ish).name
    Path(ish).mkdir(parents=True, exist_ok=True)
    if nom == "list_dir":
        y = xavfsiz_yol(ish, args.get("path", "."))
        if not y.is_dir():
            raise VositaXatosi("folder not found")
        qatorlar = []
        for i, e in enumerate(sorted(y.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))):
            if i >= MAX_ROYXAT:
                qatorlar.append("... (more)")
                break
            if e.is_symlink():
                continue
            qatorlar.append(e.name + "/" if e.is_dir() else f"{e.name} ({e.stat().st_size} bytes)")
        matn = "\n".join(qatorlar) or "(empty folder)"
        return matn, f"Ko'rildi: {ish_nomi}/{nisbiy(ish, y)} — {len(qatorlar)} ta narsa"
    if nom == "read_file":
        y = xavfsiz_yol(ish, args["path"])
        if not y.is_file():
            raise VositaXatosi("file not found")
        xom = y.read_bytes()[:200_000]
        if b"\x00" in xom[:4096]:
            raise VositaXatosi("binary file, cannot read as text")
        m = xom.decode("utf-8", errors="replace")
        if len(m) > MAX_OQISH:
            m = m[:MAX_OQISH] + f"\n... (truncated, total {len(m)} chars)"
        return m, f"O'qildi: {ish_nomi}/{nisbiy(ish, y)}"
    if nom == "create_folder":
        y = xavfsiz_yol(ish, args["path"])
        y.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {nisbiy(ish, y)}", f"✓ Papka yaratildi: {ish_nomi}/{nisbiy(ish, y)}"
    if nom == "write_file":
        y = xavfsiz_yol(ish, args["path"])
        if y.exists() and not args.get("overwrite"):
            raise VositaXatosi("file already exists")
        if y.is_dir():
            raise VositaXatosi("path is a folder")
        y.parent.mkdir(parents=True, exist_ok=True)
        # yozishdan oldin yana tekshir (papka yaratilgandan keyin symlink bo'lmasin)
        y = xavfsiz_yol(ish, args["path"])
        y.write_text(_matnga(y, args["content"], alifbo_yoq), encoding="utf-8")
        return f"File written: {nisbiy(ish, y)}", f"✓ Fayl saqlandi: {ish_nomi}/{nisbiy(ish, y)}"
    if nom in dokumentlar.KENGAYTMA:
        y = _hujjat_yol(ish, nom, args)
        if y.is_dir():
            raise VositaXatosi("path is a folder")
        if y.exists() and not args.get("overwrite"):
            raise VositaXatosi("file already exists")
        y.parent.mkdir(parents=True, exist_ok=True)
        y = _hujjat_yol(ish, nom, args)
        buf = io.BytesIO()
        try:
            n = dokumentlar.yarat(nom, buf, args, alifbo_yoq)
        except ValueError as e:
            raise VositaXatosi(str(e))
        except Exception as e:      # kutubxona xatosi: modelga qaytaramiz, dastur yiqilmasin
            raise VositaXatosi(f"could not build the document ({type(e).__name__}: {e})")
        y.write_bytes(buf.getvalue())
        return (f"Document created: {nisbiy(ish, y)}",
                f"✓ Hujjat saqlandi: {ish_nomi}/{nisbiy(ish, y)} ({dokumentlar.xulosa_qator(nom, n)})")
    if nom == "run_python":
        asos = Path(ish).resolve()
        if args.get("code"):
            buyruq = [sys.executable, "-I", "-c", args["code"]]
        else:
            y = xavfsiz_yol(ish, args["path"])
            buyruq = [sys.executable, "-I", str(y)]
        muhit = {"PATH": "/usr/bin:/bin", "HOME": str(asos), "LANG": "C.UTF-8",
                 "PYTHONIOENCODING": "utf-8"}
        try:
            p = subprocess.run(buyruq, cwd=asos, env=muhit, capture_output=True, text=True,
                               timeout=vaqt, preexec_fn=_cheklov(), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return (f"Timeout: stopped after {vaqt} s",
                    f"⏱ Kod {vaqt} soniyada tugamadi, to'xtatildi")
        chiqish = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        if len(chiqish) > MAX_CHIQISH:
            chiqish = chiqish[:MAX_CHIQISH] + "\n... (truncated)"
        modelga = f"Exit code {p.returncode}\n{chiqish or '(no output)'}"
        belgi = "✓" if p.returncode == 0 else "✗"
        return modelga, f"{belgi} Kod ishladi (kod {p.returncode})\n{chiqish.strip()[:800]}"
    raise VositaXatosi(f"unknown tool '{nom}'")
