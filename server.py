"""Local_model1 — Flask server (faqat 127.0.0.1)."""
import json
import threading
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import agent
import saqlash
import sozlama
import vositalar

SOZL = sozlama.yukla()
ISH = SOZL["ish_yol"]
ISH.mkdir(parents=True, exist_ok=True)
saqlash.tayyorla()
STATIK = Path(__file__).resolve().parent / "static"

app = Flask(__name__, static_folder=None)
_suhbatlar = {}
_qulf = threading.Lock()


def suhbat(sid):
    sid = str(sid or "")[:64] or "standart"
    with _qulf:
        if sid not in _suhbatlar:
            if len(_suhbatlar) > 20:      # eski sessiyalar xotirani band qilmasin
                _suhbatlar.pop(next(iter(_suhbatlar)))
            _suhbatlar[sid] = agent.Suhbat()
        return _suhbatlar[sid]


def _hodisa(t, **kw):
    kw["t"] = t
    return json.dumps(kw, ensure_ascii=False) + "\n"


def _xato(matn, kod=400, **kw):
    return jsonify(xato=matn, **kw), kod


def _saqla(s):
    try:
        agent.saqla(s)
    except (OSError, saqlash.SaqlashXatosi) as e:
        print(f"[ogohlantirish] chat saqlanmadi: {e}")


def _oqim(s, gen):
    def ichki():
        try:
            yield from gen
        finally:
            _saqla(s)
            s.band = False
    r = Response(ichki(), mimetype="application/x-ndjson")
    r.headers["Cache-Control"] = "no-cache"
    r.headers["X-Accel-Buffering"] = "no"
    return r


def _band_qil(s):
    with _qulf:
        if s.band:
            return False
        s.band = True
        return True


def _kontekst_holati(s):
    n = agent.taxmin_token(agent.tizim_matni(s), s.xabarlar[s.xulosalangan:])
    return {"n": n, "chegara": SOZL["options"]["num_ctx"]}


def _loyiha(nom):
    return saqlash.loyiha_yol(nom).name


@app.errorhandler(saqlash.SaqlashXatosi)
def _saqlash_xatosi(e):
    return _xato(str(e))


@app.get("/")
def bosh():
    return send_from_directory(STATIK, "index.html")


# ---------------- chat ----------------

@app.post("/api/chat")
def chat():
    d = request.get_json(force=True, silent=True) or {}
    matn = (d.get("matn") or "").strip()
    if not matn:
        return _xato("Bo'sh xabar")
    loyiha = _loyiha(d.get("loyiha"))
    chat_id = d.get("chat_id") or None
    s = suhbat(d.get("sid"))
    if not chat_id and saqlash.toldi(loyiha):
        eski = saqlash.eng_eskisi(loyiha)
        return _xato(f"Bu loyihada {saqlash.MAX_CHAT} ta chat bor.", 409, limit=True, eng_eski=eski)
    if not _band_qil(s):
        return _xato("Oldingi javob hali tugamadi", 409)
    try:
        if not chat_id:
            agent.yangi_chat(s, loyiha, matn)
        elif s.chat_id != chat_id or s.loyiha != loyiha:
            agent.yukla(s, loyiha, chat_id)
    except saqlash.SaqlashXatosi as e:
        s.band = False
        return _xato(str(e), 404)
    s.alifbo = bool(d.get("alifbo"))
    agent.foydalanuvchi_xabari(s, matn)
    _saqla(s)

    def gen():
        yield _hodisa("chat", id=s.chat_id, sarlavha=s.sarlavha)
        yield from agent.davom_et(s, SOZL)
    return _oqim(s, gen())


@app.post("/api/tasdiq")
def tasdiq():
    d = request.get_json(force=True, silent=True) or {}
    s = suhbat(d.get("sid"))
    if not _band_qil(s):
        return _xato("Band", 409)
    s.alifbo = bool(d.get("alifbo"))
    if not agent.tasdiq_javobi(s, bool(d.get("ha"))):
        s.band = False
        return _xato("Tasdiq kutilayotgan amal yo'q")
    return _oqim(s, agent.davom_et(s, SOZL))


@app.post("/api/toxtat")
def toxtat():
    d = request.get_json(force=True, silent=True) or {}
    suhbat(d.get("sid")).toxtat.set()
    return jsonify(ok=True)


@app.post("/api/yangi")
def yangi():
    d = request.get_json(force=True, silent=True) or {}
    s = suhbat(d.get("sid"))
    s.toxtat.set()
    s.yangila()
    return jsonify(ok=True)


@app.post("/api/ochish")
def ochish():
    d = request.get_json(force=True, silent=True) or {}
    loyiha = _loyiha(d.get("loyiha"))
    s = suhbat(d.get("sid"))
    if s.band:
        return _xato("Oldingi javob hali tugamadi", 409)
    agent.yukla(s, loyiha, d.get("id"))
    s.alifbo = bool(d.get("alifbo"))
    return jsonify(id=s.chat_id, sarlavha=s.sarlavha, korinish=agent.korinish(s),
                   kontekst=_kontekst_holati(s), xulosalangan=s.xulosalangan)


@app.post("/api/xulosa")
def xulosa():
    d = request.get_json(force=True, silent=True) or {}
    s = suhbat(d.get("sid"))
    if not _band_qil(s):
        return _xato("Oldingi javob hali tugamadi", 409)
    try:
        r = agent.xulosa_qil(s, SOZL)
    except RuntimeError as e:
        return _xato(str(e))
    finally:
        s.band = False
    r["kontekst"] = _kontekst_holati(s)
    r["limit"] = saqlash.XULOSA_SOZ
    return jsonify(r)


@app.get("/api/kontekst")
def kontekst():
    return jsonify(_kontekst_holati(suhbat(request.args.get("sid"))))


# ---------------- loyihalar, chatlar, xotira ----------------

@app.get("/api/loyihalar")
def loyihalar():
    return jsonify(loyihalar=[{"nom": n, "chat_soni": len(saqlash.chatlar(n))} for n in saqlash.loyihalar()],
                   max_chat=saqlash.MAX_CHAT)


@app.post("/api/loyiha")
def loyiha_yarat():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(nom=saqlash.loyiha_yarat(d.get("nom")))


@app.get("/api/chatlar")
def chatlar():
    nom = _loyiha(request.args.get("loyiha"))
    return jsonify(chatlar=[{k: v for k, v in c.items() if k != "_t"} for c in saqlash.chatlar(nom)])


@app.post("/api/arxivla")
def arxivla():
    d = request.get_json(force=True, silent=True) or {}
    nom = _loyiha(d.get("loyiha"))
    for s in list(_suhbatlar.values()):       # ochiq chat bo'lsa, u keyin qayta yaratilmasin
        if s.loyiha == nom and s.chat_id == d.get("id"):
            s.yangila()
    return jsonify(arxiv=saqlash.arxivla(nom, d.get("id")))


@app.get("/api/xotira")
def xotira_ol():
    tur = request.args.get("tur")
    if tur == "umumiy":
        m, lim = saqlash.xotira_oqi(), saqlash.XOTIRA_SOZ
    elif tur == "loyiha":
        m, lim = saqlash.xulosa_oqi(request.args.get("loyiha")), saqlash.XULOSA_SOZ
    else:
        return _xato("tur: umumiy yoki loyiha")
    return jsonify(matn=m, limit=lim, soz=saqlash.soz_soni(m))


@app.post("/api/xotira")
def xotira_yoz():
    d = request.get_json(force=True, silent=True) or {}
    matn = str(d.get("matn") or "")
    if len(matn) > 20000:
        return _xato("Matn juda uzun")
    if d.get("tur") == "umumiy":
        saqlash.xotira_yoz(matn)
    elif d.get("tur") == "loyiha":
        saqlash.xulosa_yoz(d.get("loyiha"), matn)
    else:
        return _xato("tur: umumiy yoki loyiha")
    return jsonify(ok=True, soz=saqlash.soz_soni(matn))


# ---------------- ish papkasi (faqat ko'rish) ----------------

@app.get("/api/fayllar")
def fayllar():
    asos = ISH.resolve()
    natija = []

    def yur(p, chuqur):
        try:
            elementlar = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in elementlar:
            if len(natija) >= 500:
                return
            if e.is_symlink():
                continue
            rel = e.relative_to(asos).as_posix()
            if e.is_dir():
                natija.append({"yol": rel, "papka": True, "chuqur": chuqur})
                if chuqur < 6:
                    yur(e, chuqur + 1)
            else:
                natija.append({"yol": rel, "papka": False, "chuqur": chuqur, "hajm": e.stat().st_size})

    yur(asos, 0)
    return jsonify(ish=str(asos), fayllar=natija)


@app.get("/api/fayl")
def fayl():
    try:
        y = vositalar.xavfsiz_yol(ISH, request.args.get("yol", ""))
    except vositalar.YolXatosi:
        return _xato("Ruxsat yo'q", 403)
    if not y.is_file():
        return _xato("Fayl topilmadi", 404)
    xom = y.read_bytes()[:20000]
    if b"\x00" in xom[:4096]:
        return jsonify(matn="(bu fayl matn emas — ko'rsatib bo'lmaydi)")
    return jsonify(matn=xom.decode("utf-8", errors="replace"))


@app.get("/api/yuklash")
def yuklash():
    try:
        y = vositalar.xavfsiz_yol(ISH, request.args.get("yol", ""))
    except vositalar.YolXatosi:
        return _xato("Ruxsat yo'q", 403)
    if not y.is_file():
        return _xato("Fayl topilmadi", 404)
    return send_file(y, as_attachment=True, download_name=y.name)


@app.get("/api/holat")
def holat():
    ok = False
    try:
        with urllib.request.urlopen(SOZL["ollama_url"].rstrip("/") + "/api/tags", timeout=3) as r:
            nomlar = [m["name"] for m in json.load(r).get("models", [])]
            ok = SOZL["model"] in nomlar
    except Exception:
        pass
    return jsonify(model=SOZL["model"], ollama=ok, ish=str(ISH.resolve()))


if __name__ == "__main__":
    print(f"Local_model1: http://127.0.0.1:{SOZL['port']}  (ish papkasi: {ISH})")
    app.run(host="127.0.0.1", port=SOZL["port"], threaded=True, debug=False, use_reloader=False)
