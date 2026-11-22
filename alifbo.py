"""Yangi alifbo o'giruvchisi (modelsiz).

lotin -> yangi:  sh->ş, ch->ç, o'->ö, g'->ğ  (bosh harflar ham)
yangi -> lotin:  teskarisi.
O'girilmaydi: kod bloklari, `inline kod`, URL, email, fayl nomlari/yo'llar,
"$ buyruq" qatorlari, inglizcha ko'rinadigan so'zlar, istisno ro'yxatidagi so'zlar.
"""
import re
from pathlib import Path

ISTISNO_FAYL = Path(__file__).resolve().parent / "alifbo_istisno.txt"

APOS = "'‘’ʻʼ"  # ' ‘ ’ ʻ ʼ
_A = "[" + APOS + "]"

# Himoyalangan bo'laklar (o'girilmaydi). Tartib muhim.
_HIMOYA = re.compile(
    r"```[\s\S]*?(?:```|\Z)"                    # kod bloki (yopilmagani ham)
    r"|`[^`\n]*`"                               # inline kod
    r"|(?:https?://|ftp://|www\.)\S+"           # URL
    r"|[\w.+-]+@[\w-]+\.[\w.]+"                 # email
    r"|(?m:^[ \t]*\$ .*$)"                      # $ buyruq qatori
    r"|[^\s`'\"()\[\]{}<>,;]*[/\\][^\s`'\"()\[\]{}<>,;]+"   # yo'l (/ yoki \ bor)
    r"|\b[\w-]+(?:\.[A-Za-z0-9]{1,5})+\b"      # fayl nomi: hello.txt
)

# So'z: harf/raqam/_ va ichidagi apostroflar
_SOZ = re.compile(r"[\w" + APOS + r"]+")

_cache = {"mtime": None, "sozlar": set()}


def istisnolar():
    try:
        m = ISTISNO_FAYL.stat().st_mtime
    except OSError:
        return set()
    if _cache["mtime"] != m:
        sozlar = set()
        for q in ISTISNO_FAYL.read_text(encoding="utf-8").splitlines():
            q = q.split("#", 1)[0].strip().lower()
            if q:
                sozlar.add(_A_tozala(q))
        _cache.update(mtime=m, sozlar=sozlar)
    return _cache["sozlar"]


def _A_tozala(s):
    return re.sub(_A, "'", s)


def _inglizchami(soz):
    """Inglizcha (yoki kod) so'zga o'xshaydimi?"""
    if any(c.isdigit() or c == "_" for c in soz):
        return True
    toza = re.sub(_A, "", soz)
    k = toza.lower()
    if "w" in k or "th" in k or "ph" in k:
        return True
    if re.search(r"c(?!h)", k):           # o'zbekchada yolg'iz 'c' yo'q
        return True
    if re.search(r"[a-z][A-Z]", toza):    # camelCase, iPhone
        return True
    return False


def _katta(next_ch):
    return next_ch.isalpha() and next_ch.isupper()


def _soz_yangiga(soz):
    # Qo'shtirnoq sifatidagi apostrof: 'kino' -> ichini o'gir
    if len(soz) >= 2 and soz[0] in APOS:
        bosh = soz[0]
        ichi = soz[1:]
        oxir = ""
        if ichi and ichi[-1] in APOS and not (len(ichi) >= 2 and ichi[-2] in "gG"):
            ichi, oxir = ichi[:-1], ichi[-1]
        return bosh + (_soz_yangiga(ichi) if ichi else "") + oxir
    if _A_tozala(soz).lower().strip("'") in istisnolar():
        return soz
    if _inglizchami(soz):
        return soz

    def sh(m):
        return "Ş" if m.group(0)[0] == "S" else "ş"

    def ch(m):
        return "Ç" if m.group(0)[0] == "C" else "ç"

    s = re.sub(r"[Ss][Hh]", sh, soz)
    s = re.sub(r"[Cc][Hh]", ch, s)
    s = re.sub(r"([Oo])" + _A + r"(?=[^\W\d_])", lambda m: "Ö" if m.group(1) == "O" else "ö", s)
    s = re.sub(r"([Gg])" + _A, lambda m: "Ğ" if m.group(1) == "G" else "ğ", s)
    return s


def _ochiq_qism(matn, fn):
    """Himoyalanmagan qismlarga fn ni qo'llaydi."""
    natija = []
    oxirgi = 0
    for m in _HIMOYA.finditer(matn):
        natija.append(fn(matn[oxirgi:m.start()]))
        natija.append(m.group(0))
        oxirgi = m.end()
    natija.append(fn(matn[oxirgi:]))
    return "".join(natija)


def yangiga(matn):
    """Oddiy lotin -> yangi alifbo."""
    if not matn:
        return matn
    return _ochiq_qism(matn, lambda q: _SOZ.sub(lambda m: _soz_yangiga(m.group(0)), q))


def _lotinga_qism(q):
    # apostrof variantlarini bir xil qilish (o‘ -> o', g‘ -> g')
    q = re.sub(r"([OoGg])" + _A, r"\1'", q)

    def rep(m):
        c = m.group(0)
        nxt = q[m.end():m.end() + 1]
        if c == "ş":
            return "sh"
        if c == "ç":
            return "ch"
        if c == "ö":
            return "o'"
        if c == "ğ":
            return "g'"
        if c == "Ş":
            return "SH" if _katta(nxt) else "Sh"
        if c == "Ç":
            return "CH" if _katta(nxt) else "Ch"
        if c == "Ö":
            return "O'"
        if c == "Ğ":
            return "G'"
        return c

    return re.sub("[şçöğŞÇÖĞ]", rep, q)


def lotinga(matn):
    """Yangi alifbo (yoki aralash) -> oddiy lotin. Apostroflar bir xil qilinadi."""
    if not matn:
        return matn
    return _ochiq_qism(matn, _lotinga_qism)


class OqimOgirgich:
    """Streaming matnni bo'lib-bo'lib o'giradi.
    Oxirgi tugallanmagan so'z ushlab turiladi. Agar oldin chiqarilgan matn
    keyinchalik boshqacha bo'lib chiqsa, 'almashtir' hodisasi qaytadi."""

    def __init__(self, yoqilgan=True):
        self.yoq = yoqilgan
        self.xom = ""
        self.chiqdi = ""

    def _xavfsiz_kesim(self):
        x = self.xom
        k = max(x.rfind(" "), x.rfind("\n"), x.rfind("\t"))
        if k < 0:
            return 0
        kesim = k + 1
        # yopilmagan inline ` bo'lsa, undan oldin kes
        qism = x[:kesim]
        if qism.count("```") % 2 == 0:
            tashqi = re.sub(r"```[\s\S]*?```", "", qism)
            if tashqi.count("`") % 2 == 1:
                kesim = qism.rfind("`")
        return kesim

    def _hodisa(self, yangi):
        if yangi.startswith(self.chiqdi):
            qosh = yangi[len(self.chiqdi):]
            self.chiqdi = yangi
            return [("matn", qosh)] if qosh else []
        self.chiqdi = yangi
        return [("almashtir", yangi)]

    def qosh(self, bolak):
        self.xom += bolak
        if not self.yoq:
            self.chiqdi += bolak
            return [("matn", bolak)] if bolak else []
        k = self._xavfsiz_kesim()
        return self._hodisa(yangiga(self.xom[:k]))

    def tugat(self):
        if not self.yoq:
            return []
        return self._hodisa(yangiga(self.xom))
