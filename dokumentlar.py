"""Word / Excel / PowerPoint yaratish.
Model faqat tuzilgan ma'lumot beradi (sarlavha, bandlar, jadval qatorlari); maketni shu modul qiladi.
Shrift: Arial (ş ç ö ğ ni ko'rsatadi). Yangi alifbo yoqilgan bo'lsa matn o'giriladi.
Shablonlar: ~/Local_model1/namunalar/ (ixtiyoriy)."""
import re
from pathlib import Path

import alifbo

ILDIZ = Path(__file__).resolve().parent
SHABLON_PAPKA = ILDIZ / "namunalar"
SHRIFT = "Arial"

KENGAYTMA = {"make_docx": ".docx", "make_xlsx": ".xlsx", "make_pptx": ".pptx"}

MAX_BLOK = 500
MAX_QATOR = 2000
MAX_USTUN = 50
MAX_SLAYD = 40
MAX_BAND = 12
MAX_MATN = 2000


# ---------------- kirish ma'lumotini tozalash ----------------

def _matn(v, uz):
    s = "" if v is None else str(v).strip()
    s = s[:MAX_MATN]
    return alifbo.yangiga(s) if uz else s


_BAND = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+")


def _royxat(v, uz):
    """str (qatorlarga bo'linadi) yoki list -> toza matnlar ro'yxati."""
    if v is None:
        return []
    if isinstance(v, str):
        v = v.splitlines()
    if not isinstance(v, (list, tuple)):
        raise ValueError("a list of strings was expected")
    chiq = []
    for x in v:
        if isinstance(x, (dict, list)):
            raise ValueError("list items must be plain strings")
        t = _matn(_BAND.sub("", str(x)) if x is not None else "", uz)
        if t:
            chiq.append(t)
    return chiq


def _qatorlar(v, uz):
    """Jadval: list of list. Qator satr bo'lsa '|' yoki ',' bo'yicha bo'linadi."""
    if v is None:
        return []
    if isinstance(v, str):
        v = v.splitlines()
    if not isinstance(v, (list, tuple)):
        raise ValueError("rows must be a list of rows")
    qatorlar = []
    for q in v:
        if isinstance(q, dict):
            q = list(q.values())
        elif isinstance(q, str):
            if not q.strip():
                continue
            q = q.split("|") if "|" in q else q.split("\t") if "\t" in q else q.split(",")
        elif not isinstance(q, (list, tuple)):
            q = [q]
        qatorlar.append([_matn(x, uz) for x in q][:MAX_USTUN])
        if len(qatorlar) >= MAX_QATOR:
            break
    ust = max((len(q) for q in qatorlar), default=0)
    return [q + [""] * (ust - len(q)) for q in qatorlar]


def _bolimlar(args):
    b = args.get("sections")
    if b is None:
        b = args.get("content") or args.get("blocks") or args.get("paragraphs")
    if isinstance(b, str):
        b = [{"paragraphs": b}]
    if isinstance(b, dict):
        b = [b]
    return b or []


def normallash(nom, args, uz=False):
    """Model argumentlarini toza tuzilmaga aylantiradi. Xato bo'lsa ValueError (inglizcha)."""
    if nom == "make_docx":
        bloklar = []
        for b in _bolimlar(args):
            if isinstance(b, str):
                b = {"paragraphs": b}
            if not isinstance(b, dict):
                raise ValueError("each section must be an object")
            h = _matn(b.get("heading") or b.get("title"), uz)
            if h:
                bloklar.append(("h", h))
            for p in _royxat(b.get("paragraphs", b.get("text")), uz):
                bloklar.append(("p", p))
            for p in _royxat(b.get("bullets"), uz):
                bloklar.append(("li", p))
            jad = _qatorlar(b.get("table"), uz)
            if jad:
                bloklar.append(("table", jad))
        if not bloklar:
            raise ValueError("document is empty: give 'sections' with heading, paragraphs, bullets or table")
        return {"title": _matn(args.get("title"), uz), "bloklar": bloklar[:MAX_BLOK]}
    if nom == "make_xlsx":
        sheets = args.get("sheets")
        if sheets is None and args.get("rows") is not None:
            sheets = [{"name": args.get("title") or "Sheet1", "rows": args["rows"]}]
        if isinstance(sheets, dict):
            sheets = [sheets]
        if not isinstance(sheets, list) or not sheets:
            raise ValueError("give 'sheets': a list of {name, rows}; rows is a list of rows, first row = header")
        chiq, ishlatilgan = [], set()
        for i, sh in enumerate(sheets[:20], 1):
            if not isinstance(sh, dict):
                raise ValueError("each sheet must be an object with 'name' and 'rows'")
            nomi = re.sub(r"[\[\]:*?/\\]", " ", _matn(sh.get("name") or f"Varaq{i}", uz)).strip()[:31] or f"Varaq{i}"
            while nomi.lower() in ishlatilgan:
                nomi = (nomi[:28] + f"_{i}")[:31]
            ishlatilgan.add(nomi.lower())
            qatorlar = _qatorlar(sh.get("rows"), uz)
            if not qatorlar:
                raise ValueError(f"sheet '{nomi}' has no rows")
            chiq.append({"name": nomi, "rows": qatorlar})
        return {"sheets": chiq}
    if nom == "make_pptx":
        slaydlar = args.get("slides")
        if isinstance(slaydlar, dict):
            slaydlar = [slaydlar]
        if not isinstance(slaydlar, list) or not slaydlar:
            raise ValueError("give 'slides': a list of {title, bullets}")
        chiq = []
        for sl in slaydlar[:MAX_SLAYD]:
            if isinstance(sl, str):
                sl = {"title": sl}
            if not isinstance(sl, dict):
                raise ValueError("each slide must be an object with 'title' and 'bullets'")
            chiq.append({"title": _matn(sl.get("title"), uz),
                         "bullets": _royxat(sl.get("bullets", sl.get("text")), uz)[:MAX_BAND]})
        return {"title": _matn(args.get("title"), uz), "subtitle": _matn(args.get("subtitle"), uz), "slides": chiq}
    raise ValueError(f"unknown document tool '{nom}'")


# ---------------- ko'rsatma (tasdiq kartasi uchun) ----------------

def xulosa_qator(nom, n):
    if nom == "make_docx":
        j = sum(1 for t, _ in n["bloklar"] if t == "table")
        return f"Word hujjat: {sum(1 for t, _ in n['bloklar'] if t == 'h')} bo'lim, {j} jadval"
    if nom == "make_xlsx":
        return f"Excel jadval: {len(n['sheets'])} varaq, {sum(len(s['rows']) for s in n['sheets'])} qator"
    return f"PowerPoint: {len(n['slides']) + (1 if n['title'] else 0)} slayd"


def korsatma(nom, n):
    q = []
    if nom == "make_docx":
        if n["title"]:
            q.append(f"# {n['title']}")
        for t, v in n["bloklar"]:
            if t == "h":
                q.append(f"\n## {v}")
            elif t == "p":
                q.append(v[:160] + ("…" if len(v) > 160 else ""))
            elif t == "li":
                q.append(f"  • {v[:120]}")
            else:
                q.append(f"  [jadval {len(v)}×{len(v[0])}] " + " | ".join(v[0])[:100])
    elif nom == "make_xlsx":
        for s in n["sheets"]:
            q.append(f"[{s['name']}] {len(s['rows'])} qator")
            for r in s["rows"][:4]:
                q.append("  " + " | ".join(r)[:110])
    else:
        if n["title"]:
            q.append(f"[Sarlavha] {n['title']}" + (f" — {n['subtitle']}" if n["subtitle"] else ""))
        for i, s in enumerate(n["slides"], 1):
            q.append(f"[{i}] {s['title']}")
            for b in s["bullets"][:5]:
                q.append(f"    • {b[:100]}")
    return "\n".join(q)[:1800]


# ---------------- shablonlar ----------------

def shablonlar(kengaytma):
    if not SHABLON_PAPKA.is_dir():
        return []
    return sorted(p.name for p in SHABLON_PAPKA.iterdir()
                  if p.is_file() and not p.is_symlink() and p.suffix.lower() == kengaytma)


def shablon_yol(nom, kengaytma):
    if not nom:
        return None
    ism = Path(str(nom)).name
    mavjud = shablonlar(kengaytma)
    if ism not in mavjud:
        raise ValueError("template not found. Available: " + (", ".join(mavjud) or "none"))
    return SHABLON_PAPKA / ism


# ---------------- Word ----------------

def _stil_shrifti(stil, olcham=None, qalin=None):
    from docx.oxml.ns import qn
    stil.font.name = SHRIFT
    if olcham:
        from docx.shared import Pt
        stil.font.size = Pt(olcham)
    if qalin is not None:
        stil.font.bold = qalin
    rpr = stil.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is not None:
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(a), SHRIFT)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]


def docx_yarat(yol, n, shablon=None):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor
    d = Document(str(shablon)) if shablon else Document()
    if not shablon:
        for nom, olcham in (("Normal", 11), ("Title", 24), ("Heading 1", 16), ("Heading 2", 13),
                            ("List Bullet", 11), ("Table Grid", None)):
            try:
                _stil_shrifti(d.styles[nom], olcham)
            except KeyError:
                pass
    if n["title"]:
        d.core_properties.title = n["title"]
        try:
            d.add_heading(n["title"], 0)
        except KeyError:
            d.add_paragraph(n["title"]).runs[0].bold = True
    for t, v in n["bloklar"]:
        if t == "h":
            try:
                d.add_heading(v, 1)
            except KeyError:
                d.add_paragraph(v).runs[0].bold = True
        elif t == "p":
            d.add_paragraph(v)
        elif t == "li":
            try:
                d.add_paragraph(v, style="List Bullet")
            except KeyError:
                d.add_paragraph("• " + v)
        else:
            jad = d.add_table(rows=len(v), cols=len(v[0]))
            try:
                jad.style = "Table Grid"
            except (KeyError, ValueError):
                pass
            for i, qator in enumerate(v):
                for j, h in enumerate(qator):
                    kat = jad.cell(i, j)
                    kat.text = h
                    for par in kat.paragraphs:
                        for run in par.runs:
                            run.font.name = SHRIFT
                            run.font.size = Pt(10.5)
                            if i == 0:
                                run.bold = True
            d.add_paragraph()
    d.save(yol)


# ---------------- Excel ----------------

_SON = re.compile(r"^-?(?:0|[1-9]\d*)(?:[.,]\d+)?$")
_FORMULA = re.compile(r'^=[A-Za-z0-9_+\-*/(),.:$<>= !"]+$')
_FUNK = {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA", "ROUND", "IF", "ABS"}


def _xavfsiz_formula(s):
    return bool(_FORMULA.match(s)) and all(f.upper() in _FUNK for f in re.findall(r"([A-Za-z_]+)\(", s))


def _qiymat(s):
    if _SON.match(s):
        return float(s.replace(",", ".")) if re.search(r"[.,]", s) else int(s)
    return s


def xlsx_yarat(yol, n, shablon=None):
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    if shablon:
        wb = load_workbook(str(shablon))
        bor = {s.lower() for s in wb.sheetnames}
    else:
        wb = Workbook()
        wb.remove(wb.active)
        bor = set()
    qalin = Font(name=SHRIFT, bold=True)
    oddiy = Font(name=SHRIFT)
    fon = PatternFill("solid", fgColor="E8EEF7")
    for sh in n["sheets"]:
        nomi = sh["name"]
        k = 2
        while nomi.lower() in bor:
            nomi = f"{sh['name'][:27]}_{k}"
            k += 1
        bor.add(nomi.lower())
        ws = wb.create_sheet(nomi)
        eni = {}
        for i, q in enumerate(sh["rows"], 1):
            for j, h in enumerate(q, 1):
                v = h if i == 1 else _qiymat(h)
                c = ws.cell(row=i, column=j)
                c.value = v
                if isinstance(v, str) and v.startswith("="):
                    if i == 1 or not _xavfsiz_formula(v):
                        c.data_type = "s"          # formula emas, oddiy matn
                c.font = qalin if i == 1 else oddiy
                if i == 1:
                    c.fill = fon
                    c.alignment = Alignment(vertical="center", wrap_text=True)
                eni[j] = max(eni.get(j, 0), len(str(h)))
        for j, e in eni.items():
            ws.column_dimensions[get_column_letter(j)].width = min(max(10, e + 3), 50)
        if len(sh["rows"]) > 1:
            ws.freeze_panes = "A2"
    wb.save(yol)


# ---------------- PowerPoint ----------------

def _pptx_matn(shakl, matnlar, olcham, qalin=False, markaz=False):
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt
    tf = shakl.text_frame
    tf.word_wrap = True
    for i, m in enumerate(matnlar):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = m
        if markaz:
            p.alignment = PP_ALIGN.CENTER
        for r in p.runs:
            r.font.name = SHRIFT
            r.font.size = Pt(olcham)
            r.font.bold = qalin


def pptx_yarat(yol, n, shablon=None):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation(str(shablon)) if shablon else Presentation()
    keng = not shablon
    if keng:
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    tartib = prs.slide_layouts
    sarlavha_l = tartib[0]
    mazmun_l = tartib[1] if len(tartib) > 1 else tartib[0]

    def joy(shakl, x, y, w, h):
        if keng:
            shakl.left, shakl.top, shakl.width, shakl.height = Inches(x), Inches(y), Inches(w), Inches(h)

    if n["title"]:
        s = prs.slides.add_slide(sarlavha_l)
        if s.shapes.title is not None:
            joy(s.shapes.title, 0.9, 2.3, 11.5, 1.8)
            _pptx_matn(s.shapes.title, [n["title"]], 40, True, True)
        alt = [sh for sh in s.placeholders if sh.placeholder_format.idx == 1]
        if alt:
            if n["subtitle"]:
                joy(alt[0], 0.9, 4.3, 11.5, 1.2)
                _pptx_matn(alt[0], [n["subtitle"]], 22, False, True)
            else:
                alt[0]._element.getparent().remove(alt[0]._element)
    for sl in n["slides"]:
        s = prs.slides.add_slide(mazmun_l)
        if s.shapes.title is not None:
            joy(s.shapes.title, 0.7, 0.4, 11.9, 1.3)
            _pptx_matn(s.shapes.title, [sl["title"]], 32, True)
        govda = [sh for sh in s.placeholders if sh.placeholder_format.idx == 1]
        if govda:
            if sl["bullets"]:
                k = len(sl["bullets"])
                joy(govda[0], 0.9, 1.9, 11.5, 5.0)
                _pptx_matn(govda[0], sl["bullets"], 26 if k <= 5 else 22 if k <= 8 else 18)
            else:
                govda[0]._element.getparent().remove(govda[0]._element)
    prs.save(yol)


YARATUVCHI = {"make_docx": docx_yarat, "make_xlsx": xlsx_yarat, "make_pptx": pptx_yarat}


def yarat(nom, yol, args, uz=False):
    """Hujjatni yol (fayl yo'li yoki BytesIO) ga yozadi. Qaytadi: normallashgan tuzilma."""
    n = normallash(nom, args, uz)
    shablon = shablon_yol(args.get("template"), KENGAYTMA[nom])
    YARATUVCHI[nom](yol, n, shablon)
    return n
