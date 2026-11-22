"""Ollama bilan ishlovchi agent sikli (streaming + tool calling + tasdiq)."""
import json
import re
import threading
import time
import urllib.error
import urllib.request

import alifbo
import saqlash
import vositalar

SYSTEM_PROMPT = """You are a helpful local assistant on the user's Linux computer.
The user writes in Uzbek. Answer in simple Uzbek using the plain Latin script (o' g' sh ch). Never use the letters ş ç ö ğ.
Give complete, useful answers: a short explanation plus the result. Do not answer with a single word.
When the user asks for code or a command: show the full, correct code in a fenced code block in the chat, then explain it in 1-3 short sentences. Code, comments and identifiers in English.
Use tools only when the user asks to work with files, folders or documents (create, save, read, list, run). Do not save files the user did not ask for.
Files: only inside the work folder. You are already in it: save directly like "hisob.py", or "test/hello.txt" only if the user named the folder "test". Do not invent folder names. Never use absolute paths or "..". There is no delete tool.
Every write action needs the user's approval. If the user rejects an action, do not repeat it; ask what to do instead.
Do not overwrite an existing file unless the user clearly asked for it.
For Word, Excel or PowerPoint files use make_docx, make_xlsx, make_pptx: give only structured content (headings, bullet lists, table rows); the program does the layout. Write the text content in simple Uzbek.
After tool work, tell the user briefly what was done."""

MAX_TUZATISH = 2

# Foydalanuvchi faylga saqlashni so'radimi? (aks holda model kodni chatda ko'rsatsin)
_SAQLASH_NIYATI = re.compile(
    r"saqla|fayl|papka|jild|yarat|ichiga|hujjat|jadval|taqdimot|prezentatsiya|slayd|word|excel|powerpoint|"
    r"\.[a-z0-9]{1,5}\b|save|file|folder", re.I)


_HUJJAT_NIYATI = {
    "make_docx": re.compile(r"word|docx|hujjat|ariza|ma'lumotnoma|xat yoz", re.I),
    "make_xlsx": re.compile(r"excel|xlsx|jadval|hisob-kitob", re.I),
    "make_pptx": re.compile(r"powerpoint|pptx|taqdimot|prezentatsiya|slayd", re.I),
}


def tariflar(s):
    """Oxirgi 3 ta foydalanuvchi xabaridan qaysi hujjat vositalari kerakligini aniqlaydi."""
    matn = " ".join([m["content"] for m in s.xabarlar if m["role"] == "user" and m.get("content")][-3:])
    return vositalar.tariflar({n for n, r in _HUJJAT_NIYATI.items() if r.search(matn)})


def saqlash_soraldimi(s):
    for m in reversed(s.xabarlar):
        if m["role"] == "user":
            return bool(_SAQLASH_NIYATI.search(m["content"]))
    return False


class Suhbat:
    def __init__(self):
        self.xabarlar = []      # system siz tarix (oddiy lotinda)
        self.kutilayotgan = []  # tasdiq kutayotgan / navbatdagi tool chaqiruvlari
        self.tuzatish = 0
        self.toxtat = threading.Event()
        self.band = False
        self.alifbo = False
        self.loyiha = None      # joriy loyiha nomi
        self.chat_id = None
        self.sarlavha = ""
        self.yaratildi = ""
        self.xulosalangan = 0   # shu indeksgacha bo'lgan xabarlar xulosa.md ga o'tgan

    def yangila(self):
        band = self.band
        self.__init__()
        self.band = band


def _hodisa(t, **kw):
    kw["t"] = t
    return json.dumps(kw, ensure_ascii=False) + "\n"


def tizim_matni(s):
    t = SYSTEM_PROMPT
    if s.loyiha:
        x = saqlash.xotira_matni(s.loyiha)
        if x:
            t += "\n\n" + x
    return t


def taxmin_token(tizim, xabarlar, tarif=None):
    """Taxminiy token soni (~3 belgi = 1 token), vosita ta'riflari bilan."""
    n = len(tizim) + len(json.dumps(tarif if tarif is not None else vositalar.tariflar()))
    for m in xabarlar:
        n += len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) + 12
    return n // 3


def _kontekst(s, sozl):
    """Xulosa qilinmagan xabarlarning oxirgilarini num_ctx ga sig'adigan qilib tanlaydi."""
    tizim = tizim_matni(s)
    tarix = s.xabarlar[s.xulosalangan:]
    byudjet = max(1500, int(sozl["options"]["num_ctx"] * 3) - 4500 - len(tizim))
    tanlangan, jami = [], 0
    for m in reversed(tarix):
        uz = len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) + 20
        if tanlangan and jami + uz > byudjet:
            break
        tanlangan.append(m)
        jami += uz
    tanlangan.reverse()
    kesildi = len(tanlangan) < len(tarix)
    # boshida tool/assistant javobi yolg'iz qolmasin
    while len(tanlangan) > 1 and tanlangan[0]["role"] != "user":
        tanlangan.pop(0)
    return [{"role": "system", "content": tizim}] + tanlangan, kesildi


def _json_tuzat(m):
    m = m.strip()
    m = re.sub(r"^```(?:json)?\s*|\s*```$", "", m)
    m = re.sub(r",\s*([}\]])", r"\1", m)
    return json.loads(m)


def matndan_chaqiruv(matn):
    """Model tool chaqiruvini oddiy matn qilib yozsa, ajratib oladi."""
    s = matn.strip()
    m = re.search(r"<tool_call>\s*([\s\S]*?)\s*(?:</tool_call>|$)", s)
    nomzod = m.group(1) if m else (s if s.startswith("{") or s.startswith("```") else None)
    if not nomzod:
        return None
    try:
        d = _json_tuzat(nomzod)
    except ValueError:
        return "xato" if m else None
    if not isinstance(d, dict) or "name" not in d:
        return "xato" if m else None
    args = d.get("arguments", d.get("parameters", {}))
    return [{"function": {"name": d["name"], "arguments": args}}]


def _ollama_oqim(sozl, xabarlar, toxtat, tarif):
    tana = {
        "model": sozl["model"], "messages": xabarlar, "tools": tarif,
        "stream": True, "options": sozl["options"], "keep_alive": sozl["keep_alive"],
    }
    req = urllib.request.Request(sozl["ollama_url"].rstrip("/") + "/api/chat",
                                 data=json.dumps(tana).encode(),
                                 headers={"Content-Type": "application/json"})
    javob = urllib.request.urlopen(req, timeout=600)
    try:
        for qator in javob:
            if toxtat.is_set():
                return
            qator = qator.strip()
            if not qator:
                continue
            d = json.loads(qator)
            if d.get("error"):
                raise RuntimeError(d["error"])
            yield d
            if d.get("done"):
                return
    finally:
        javob.close()


def _uz(s, matn):
    return alifbo.yangiga(matn) if s.alifbo else matn


def _vositalarni_ishla(s, sozl):
    """Navbatdagi tool chaqiruvlarini ishlaydi. Yozuvchiga yetganda tasdiq so'raydi.
    Qaytadi: (hodisalar_ro'yxati, to'xtash_kerakmi)."""
    ish = sozl["ish_yol"]
    chiq = []
    while s.kutilayotgan:
        tc = s.kutilayotgan[0]
        nom, args = tc["nom"], tc["args"]
        if tc.get("tasdiq") is None:
            if nom in vositalar.YOZUVCHI - {"run_python"} and not saqlash_soraldimi(s):
                s.kutilayotgan.pop(0)
                s.xabarlar.append({"role": "tool", "tool_name": nom, "content":
                                   "Not done: the user did not ask to save anything. "
                                   "Show the code or text directly in the chat instead."})
                continue
            try:
                info = vositalar.tayyorla(ish, nom, args, s.alifbo)
            except (vositalar.VositaXatosi, vositalar.YolXatosi) as e:
                s.kutilayotgan.pop(0)
                s.xabarlar.append({"role": "tool", "tool_name": nom, "content": f"Error: {e}"})
                chiq.append(_hodisa("vosita", v=_uz(s, f"✗ {nom}: rad etildi ({e})"), xato=True))
                continue
            if info["yozuvchi"]:
                tc["tasdiq"] = "kutilmoqda"
                chiq.append(_hodisa("tasdiq", tavsif=_uz(s, info["tavsif"]),
                                    tafsilot=info["tafsilot"],
                                    ogohlantirish=_uz(s, info["ogohlantirish"])))
                return chiq, True
            tc["tasdiq"] = "shart_emas"
        if tc["tasdiq"] == "kutilmoqda":
            return chiq, True
        s.kutilayotgan.pop(0)
        if tc["tasdiq"] == "yoq":
            s.xabarlar.append({"role": "tool", "tool_name": nom,
                               "content": "The user REJECTED this action. Do not repeat it. If it was code, show the code in the chat instead."})
            chiq.append(_hodisa("vosita", v=_uz(s, "✗ Bekor qilindi"), xato=True))
            continue
        try:
            modelga, odamga = vositalar.bajar(ish, nom, args, s.alifbo, sozl["python_vaqt_chegarasi"])
            chiq.append(_hodisa("vosita", v=_uz(s, odamga)))
        except (vositalar.VositaXatosi, vositalar.YolXatosi, OSError) as e:
            modelga = f"Error: {e}"
            chiq.append(_hodisa("vosita", v=_uz(s, f"✗ {nom}: xato ({e})"), xato=True))
        s.xabarlar.append({"role": "tool", "tool_name": nom, "content": modelga})
    return chiq, False


def davom_et(s, sozl):
    """Generator: NDJSON hodisalarini chiqaradi."""
    s.toxtat.clear()
    yield from _davom(s, sozl)
    yield _hodisa("tugadi")


def _davom(s, sozl):
    hod, kut = _vositalarni_ishla(s, sozl)
    yield from hod
    if kut:
        return
    for _ in range(sozl["max_qadam"]):
        if s.toxtat.is_set():
            yield _hodisa("ogoh", v="To'xtatildi.")
            return
        xabarlar, kesildi = _kontekst(s, sozl)
        tarif = tariflar(s)
        if kesildi:
            yield _hodisa("ogoh", v=_uz(s, "Suhbat uzun: eng eski xabarlar modelga berilmadi. «Xulosa qil» ni bosing yoki yangi suhbat boshlang."))
        og = alifbo.OqimOgirgich(s.alifbo)
        matn, chaqiruvlar, oxirgi = "", [], {}
        ushlab = True   # boshida JSON/tool_call bo'lishi mumkin — ko'rsatmay tur
        try:
            for d in _ollama_oqim(sozl, xabarlar, s.toxtat, tarif):
                msg = d.get("message") or {}
                if d.get("done"):
                    oxirgi = d
                if msg.get("tool_calls"):
                    chaqiruvlar.extend(msg["tool_calls"])
                bolak = msg.get("content") or ""
                if not bolak:
                    continue
                matn += bolak
                if ushlab:
                    bosh = matn.lstrip()
                    if not bosh:
                        continue
                    if bosh.startswith("{") or bosh.startswith("<tool_call>") or \
                            "<tool_call>".startswith(bosh) or bosh.startswith("```json"):
                        continue
                    ushlab = False
                    bolak = matn
                for t, v in og.qosh(bolak):
                    yield _hodisa(t, v=v)
        except urllib.error.URLError as e:
            yield _hodisa("xato", v=f"Ollama bilan aloqa yo'q ({e.reason}). Ollama ishlayaptimi?")
            return
        except (RuntimeError, ValueError, OSError) as e:
            yield _hodisa("xato", v=f"Model xatosi: {e}")
            return
        taxmin = taxmin_token(xabarlar[0]["content"], xabarlar[1:], tarif) + len(matn) // 3
        ishlatildi = max(taxmin, (oxirgi.get("prompt_eval_count") or 0) + (oxirgi.get("eval_count") or 0))
        chegara = sozl["options"]["num_ctx"]
        yield _hodisa("kontekst", n=ishlatildi, chegara=chegara)
        if s.toxtat.is_set():
            if matn.strip():
                s.xabarlar.append({"role": "assistant", "content": matn + " [stopped]"})
            yield _hodisa("ogoh", v="To'xtatildi.")
            return
        if not chaqiruvlar and ushlab and matn.strip():
            topildi = matndan_chaqiruv(matn)
            if isinstance(topildi, list):
                chaqiruvlar = topildi
                matn = ""
            elif topildi == "xato":
                chaqiruvlar = [{"function": {"name": "__bad_json__", "arguments": {}}}]
                matn = ""
            else:
                for t, v in og.qosh(matn):
                    yield _hodisa(t, v=v)
        for t, v in og.tugat():
            yield _hodisa(t, v=v)

        if not chaqiruvlar:
            s.xabarlar.append({"role": "assistant", "content": matn})
            s.tuzatish = 0
            if ishlatildi >= 0.85 * chegara:
                yield _hodisa("ogoh", v=_uz(s, "Kontekst to'lib boryapti. «Xulosa qil» tugmasini bosing yoki yangi suhbat boshlang."))
            return

        # tool chaqiruvlarini tekshirish
        yaxshi, xatolar = [], []
        for c in chaqiruvlar:
            f = c.get("function") or {}
            nom, args = f.get("name", ""), f.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = _json_tuzat(args) if args.strip() else {}
                except ValueError:
                    xatolar.append(f"{nom}: arguments are not valid JSON")
                    continue
            if nom == "__bad_json__":
                xatolar.append("tool call JSON is invalid")
                continue
            if nom not in vositalar.NOMLAR:
                xatolar.append(f"unknown tool '{nom}'. Use one of: {', '.join(sorted(vositalar.NOMLAR))}")
                continue
            if not isinstance(args, dict):
                xatolar.append(f"{nom}: arguments must be a JSON object")
                continue
            yaxshi.append({"nom": nom, "args": args})
        s.xabarlar.append({"role": "assistant", "content": matn,
                           "tool_calls": [{"function": {"name": t["nom"], "arguments": t["args"]}}
                                          for t in yaxshi]})
        if xatolar:
            s.tuzatish += 1
            s.xabarlar.append({"role": "tool", "content":
                               "Error: " + "; ".join(xatolar) + ". Call the tool again with valid JSON arguments."})
            if s.tuzatish > MAX_TUZATISH:
                s.tuzatish = 0
                yield _hodisa("xato", v=_uz(s, "Model vositani to'g'ri chaqira olmadi. So'rovni boshqacha, aniqroq yozib ko'ring."))
                return
            if not yaxshi:
                continue
        else:
            s.tuzatish = 0
        s.kutilayotgan = yaxshi
        hod, kut = _vositalarni_ishla(s, sozl)
        yield from hod
        if kut:
            return
    yield _hodisa("ogoh", v=_uz(s, "Qadamlar soni chegarasiga yetildi, to'xtadim."))


def foydalanuvchi_xabari(s, matn):
    # tasdiq kutayotgan amal bo'lsa — yangi xabar = rad etish
    for tc in s.kutilayotgan:
        s.xabarlar.append({"role": "tool", "tool_name": tc["nom"],
                           "content": "Not approved: the user sent a new message instead."})
    s.kutilayotgan = []
    s.xabarlar.append({"role": "user", "content": alifbo.lotinga(matn)})


def tasdiq_javobi(s, ha):
    if s.kutilayotgan and s.kutilayotgan[0].get("tasdiq") == "kutilmoqda":
        s.kutilayotgan[0]["tasdiq"] = "ha" if ha else "yoq"
        return True
    return False


# ---------------- chatni saqlash / yuklash ----------------

def saqla(s):
    """Suhbatni loyiha papkasiga yozadi (loyiha va chat_id bo'lsa)."""
    if not s.loyiha or not s.chat_id:
        return
    saqlash.chat_saqla(s.loyiha, {
        "id": s.chat_id, "sarlavha": s.sarlavha, "yaratildi": s.yaratildi,
        "xabarlar": s.xabarlar, "xulosalangan": s.xulosalangan})


def yukla(s, loyiha, cid):
    d = saqlash.chat_yukla(loyiha, cid)
    s.yangila()
    s.loyiha, s.chat_id = loyiha, d["id"]
    s.sarlavha, s.yaratildi = d.get("sarlavha", ""), d.get("yaratildi", "")
    s.xabarlar = d["xabarlar"]
    s.xulosalangan = min(int(d.get("xulosalangan", 0)), len(s.xabarlar))


def yangi_chat(s, loyiha, matn):
    s.yangila()
    s.loyiha = loyiha
    s.chat_id = saqlash.yangi_id()
    s.sarlavha = saqlash.sarlavha(matn)
    s.yaratildi = time.strftime("%Y-%m-%d %H:%M")


def korinish(s):
    """Brauzerda chatni qayta chizish uchun: [{rol, matn}]."""
    chiq = []
    for m in s.xabarlar:
        r, c = m.get("role"), (m.get("content") or "").strip()
        if r == "user" and c:
            chiq.append({"rol": "men", "matn": _uz(s, c)})
        elif r == "assistant":
            if c:
                chiq.append({"rol": "model", "matn": _uz(s, c)})
            for tc in m.get("tool_calls") or []:
                f = tc.get("function", {})
                yol = (f.get("arguments") or {}).get("path", "")
                chiq.append({"rol": "vosita", "matn": f"• {f.get('name', '')} {yol}".strip()})
    return chiq


# ---------------- "Xulosa qil" ----------------

OXIRGI_TOLA = 12   # oxirgi shuncha xabar to'liq qoladi


def xulosa_nuqtasi(s):
    """Xulosa qilinadigan qism: s.xabarlar[s.xulosalangan:k]. Qoladigan qism 'user' xabaridan boshlanadi.
    Qaytadi k yoki None (xulosa qilinadigan narsa yo'q)."""
    chek = len(s.xabarlar) - OXIRGI_TOLA
    for i in range(chek, s.xulosalangan, -1):
        if s.xabarlar[i]["role"] == "user":
            return i
    return None


def _qism_matni(xabarlar, jami):
    qatorlar = []
    kesim = max(150, min(500, jami // max(1, len(xabarlar))))
    for m in xabarlar:
        r, c = m.get("role"), (m.get("content") or "").strip().replace("\n", " ")
        if r == "user":
            qatorlar.append("User: " + c[:kesim])
        elif r == "assistant":
            q = "Assistant: " + c[:kesim]
            for tc in m.get("tool_calls") or []:
                f = tc.get("function", {})
                q += f" [used {f.get('name', '')} {(f.get('arguments') or {}).get('path', '')}]"
            qatorlar.append(q)
        elif r == "tool":
            qatorlar.append("Tool result: " + c[:120])
    return "\n".join(qatorlar)[:jami]


XULOSA_PROMPT = """Below is an excerpt of a conversation between a user and an assistant.
Write short notes in plain English (at most 100 words, bullet points) that keep only lasting facts: the user's goals, decisions, names, file names and paths, preferences, unfinished tasks.
No greetings, no code, no commentary. Output only the notes.

Excerpt:
"""


def xulosa_qil(s, sozl):
    """Eski xabarlarni model orqali qisqa xulosaga aylantirib xulosa.md ga qo'shadi.
    Qaytadi: dict(matn, soz, qoldi). Xato: RuntimeError (o'zbekcha xabar bilan)."""
    if not s.loyiha:
        raise RuntimeError("Loyiha tanlanmagan")
    k = xulosa_nuqtasi(s)
    if k is None:
        raise RuntimeError(f"Xulosa qiladigan eski xabarlar yo'q (oxirgi {OXIRGI_TOLA} ta xabar o'zgarishsiz qoladi)")
    qism = s.xabarlar[s.xulosalangan:k]
    matn = _qism_matni(qism, int(sozl["options"]["num_ctx"] * 1.8))
    tana = {"model": sozl["model"], "stream": False, "keep_alive": sozl["keep_alive"],
            "options": {**sozl["options"], "temperature": 0.3, "num_predict": 300},
            "messages": [{"role": "system", "content": "You write concise, factual notes."},
                         {"role": "user", "content": XULOSA_PROMPT + matn}]}
    req = urllib.request.Request(sozl["ollama_url"].rstrip("/") + "/api/chat", data=json.dumps(tana).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            natija = (json.load(r).get("message") or {}).get("content", "").strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama bilan aloqa yo'q ({e.reason})")
    except (ValueError, OSError) as e:
        raise RuntimeError(f"Model xatosi: {e}")
    if len(natija) < 10:
        raise RuntimeError("Model xulosa yoza olmadi. Qayta urinib ko'ring.")
    natija = natija[:1500]
    soz = saqlash.xulosa_qosh(s.loyiha, natija)
    s.xulosalangan = k
    saqla(s)
    return {"matn": natija, "soz": soz, "qoldi": len(s.xabarlar) - k}
