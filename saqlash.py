"""Loyihalar, chat tarixi va xotira — oddiy fayllar (JSON/Markdown).

data/umumiy_xotira.md             doimiy qoidalar (<=200 so'z)
data/loyihalar/<nom>/xulosa.md    loyiha xulosasi (<=300 so'z)
data/loyihalar/<nom>/chatlar/*.json   chatlar (ko'pi bilan 20 ta)
data/loyihalar/<nom>/chatlar/arxiv/   chetga olingan eski chatlar (O'CHIRILMAYDI)
"""
import json
import os
import re
import secrets
import time
from pathlib import Path

ILDIZ = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LM1_DATA") or ILDIZ / "data")

MAX_CHAT = 20
XOTIRA_SOZ = 200
XULOSA_SOZ = 300
# modelga beriladigan matn chegarasi (qo'lda juda uzun yozilgan bo'lsa ham kontekst to'lmasin)
BERISH_SOZ = 600

BOSH_XOTIRA = "- Javoblar qisqa va oddiy o'zbek tilida bo'lsin.\n"


class SaqlashXatosi(Exception):
    pass


def _loyihalar_yol():
    return DATA / "loyihalar"


def tayyorla():
    """Papkalar va standart fayllarni yaratadi (bor narsaga tegmaydi)."""
    _loyihalar_yol().mkdir(parents=True, exist_ok=True)
    f = DATA / "umumiy_xotira.md"
    if not f.exists():
        f.write_text(BOSH_XOTIRA, encoding="utf-8")
    if not loyihalar():
        loyiha_yarat("Umumiy")


def soz_soni(m):
    return len((m or "").split())


# ---------------- loyihalar ----------------

_NOM = re.compile(r"^[^\W_][\w \-]{0,39}$")


def nom_tekshir(nom):
    nom = " ".join(str(nom or "").split())
    if not _NOM.match(nom):
        raise SaqlashXatosi("Loyiha nomi: 1–40 belgi; harf, raqam, bo'sh joy, - yoki _ bo'lishi mumkin")
    return nom


def loyiha_yol(nom):
    """Mavjud loyiha papkasi (katta-kichik harf farqsiz). Yo'q bo'lsa xato."""
    nom = nom_tekshir(nom)
    asos = _loyihalar_yol()
    if asos.is_dir():
        for p in asos.iterdir():
            if p.is_dir() and not p.is_symlink() and p.name.lower() == nom.lower():
                return p
    raise SaqlashXatosi(f"Loyiha topilmadi: {nom}")


def loyihalar():
    asos = _loyihalar_yol()
    if not asos.is_dir():
        return []
    return sorted((p.name for p in asos.iterdir() if p.is_dir() and not p.is_symlink()), key=str.lower)


def loyiha_yarat(nom):
    nom = nom_tekshir(nom)
    if nom.lower() in (n.lower() for n in loyihalar()):
        raise SaqlashXatosi("Bunday loyiha bor")
    p = _loyihalar_yol() / nom
    if not p.resolve().is_relative_to(_loyihalar_yol().resolve()):
        raise SaqlashXatosi("Noto'g'ri nom")
    (p / "chatlar").mkdir(parents=True)
    (p / "xulosa.md").write_text("", encoding="utf-8")
    return nom


# ---------------- xotira va xulosa ----------------

def xotira_oqi():
    f = DATA / "umumiy_xotira.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def xotira_yoz(matn):
    n = soz_soni(matn)
    if n > XOTIRA_SOZ:
        raise SaqlashXatosi(f"Umumiy xotira {XOTIRA_SOZ} so'zdan oshmasin (hozir {n}). Qisqartiring.")
    (DATA).mkdir(parents=True, exist_ok=True)
    (DATA / "umumiy_xotira.md").write_text(matn, encoding="utf-8")


def xulosa_oqi(nom):
    f = loyiha_yol(nom) / "xulosa.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def xulosa_yoz(nom, matn):
    n = soz_soni(matn)
    if n > XULOSA_SOZ:
        raise SaqlashXatosi(f"Xulosa {XULOSA_SOZ} so'zdan oshmasin (hozir {n}). Qisqartiring.")
    (loyiha_yol(nom) / "xulosa.md").write_text(matn, encoding="utf-8")


def xulosa_qosh(nom, yangi):
    """Model xulosasini oxiriga qo'shadi (chegaradan oshsa ham yozadi). Qaytadi: jami so'z soni."""
    f = loyiha_yol(nom) / "xulosa.md"
    eski = f.read_text(encoding="utf-8") if f.exists() else ""
    sana = time.strftime("%Y-%m-%d")
    matn = (eski.rstrip() + "\n\n" if eski.strip() else "") + f"## {sana}\n{yangi.strip()}\n"
    f.write_text(matn, encoding="utf-8")
    return soz_soni(matn)


def _oxirgi_sozlar(m, n):
    s = m.split()
    return m if len(s) <= n else "... " + " ".join(s[-n:])


def _birinchi_sozlar(m, n):
    q = m.split("\n")
    chiq, k = [], 0
    for qator in q:
        k += len(qator.split())
        if k > n:
            break
        chiq.append(qator)
    return "\n".join(chiq)


def xotira_matni(nom):
    """Modelga beriladigan doimiy kontekst: umumiy xotira + loyiha xulosasi."""
    qism = []
    try:
        x = xotira_oqi().strip()
    except OSError:
        x = ""
    if x:
        qism.append("User's standing rules (general memory):\n" + _birinchi_sozlar(x, BERISH_SOZ))
    try:
        s = xulosa_oqi(nom).strip() if nom else ""
    except (SaqlashXatosi, OSError):
        s = ""
    if s:
        qism.append(f"Summary of earlier work in project '{nom}':\n" + _oxirgi_sozlar(s, BERISH_SOZ))
    return "\n\n".join(qism)


# ---------------- chatlar ----------------

_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


def yangi_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def _chatlar_yol(nom):
    return loyiha_yol(nom) / "chatlar"


def chat_yol(nom, cid):
    if not _ID.match(str(cid or "")):
        raise SaqlashXatosi("Noto'g'ri chat identifikatori")
    return _chatlar_yol(nom) / f"{cid}.json"


def _vaqt():
    return time.strftime("%Y-%m-%d %H:%M")


def chat_saqla(nom, d):
    """d: dict(id, sarlavha, yaratildi, xabarlar, xulosalangan). Atomik yozadi."""
    f = chat_yol(nom, d["id"])
    f.parent.mkdir(parents=True, exist_ok=True)
    d = dict(d)
    d["yangilandi"] = _vaqt()
    d["_t"] = time.time()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def _tuzat(xabarlar):
    """Javobsiz qolgan tool chaqiruvlariga 'bajarilmadi' javobi qo'shadi (model chalkashmasin)."""
    idx = None
    for i in range(len(xabarlar) - 1, -1, -1):
        m = xabarlar[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            idx = i
            break
        if m.get("role") in ("user", "assistant"):
            break
    if idx is None:
        return xabarlar
    kerak = len(xabarlar[idx]["tool_calls"])
    javob = sum(1 for m in xabarlar[idx + 1:] if m.get("role") == "tool")
    for c in xabarlar[idx]["tool_calls"][javob:kerak]:
        xabarlar.append({"role": "tool", "tool_name": c.get("function", {}).get("name", ""),
                         "content": "Not done: the session was interrupted before this action ran."})
    return xabarlar


def chat_yukla(nom, cid):
    f = chat_yol(nom, cid)
    if not f.is_file():
        raise SaqlashXatosi("Chat topilmadi")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        raise SaqlashXatosi("Chat fayli buzilgan")
    d.setdefault("xabarlar", [])
    d.setdefault("xulosalangan", 0)
    d["xabarlar"] = _tuzat(d["xabarlar"])
    return d


def chatlar(nom):
    """Chatlar ro'yxati (yangisi birinchi). Arxivdagilar kirmaydi."""
    r = []
    for f in _chatlar_yol(nom).glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        r.append({"id": d.get("id", f.stem), "sarlavha": d.get("sarlavha", "(nomsiz)"),
                  "yangilandi": d.get("yangilandi", ""), "xabar_soni": len(d.get("xabarlar", [])),
                  "_t": d.get("_t", f.stat().st_mtime)})
    r.sort(key=lambda x: x["_t"], reverse=True)
    return r


def eng_eskisi(nom):
    r = chatlar(nom)
    return r[-1] if r else None


def arxivla(nom, cid):
    """Chatni arxiv papkasiga ko'chiradi (o'chirmaydi)."""
    f = chat_yol(nom, cid)
    if not f.is_file():
        raise SaqlashXatosi("Chat topilmadi")
    arx = f.parent / "arxiv"
    arx.mkdir(exist_ok=True)
    hedef = arx / f.name
    n = 1
    while hedef.exists():
        hedef = arx / f"{f.stem}_{n}.json"
        n += 1
    os.rename(f, hedef)
    return hedef.name


def toldi(nom):
    return len(chatlar(nom)) >= MAX_CHAT


def sarlavha(matn):
    s = " ".join(str(matn or "").split())
    return (s[:47] + "…") if len(s) > 48 else (s or "(nomsiz)")
