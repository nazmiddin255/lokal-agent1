"""B bosqich: haqiqiy Ollama bilan oxirigacha sinov (vaqtincha ish/data papkalarida).
    LM1_ISH=/tmp/x/ish LM1_DATA=/tmp/x/data .venv/bin/python tests/e2e_b.py"""
import json
import os
import sys
import time
from pathlib import Path

assert os.environ.get("LM1_ISH") and os.environ.get("LM1_DATA"), "LM1_ISH va LM1_DATA kerak (sinov papkalari)"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402
import saqlash  # noqa: E402

c = server.app.test_client()
SID = "e2e-b"


def oqim(url, tana):
    r = c.post(url, json=tana)
    if r.status_code != 200 and r.mimetype == "application/json":
        print("   HTTP", r.status_code, r.get_json())
        return []
    hod = [json.loads(q) for q in r.get_data(as_text=True).splitlines() if q.strip()]
    for h in hod:
        if h["t"] not in ("matn", "tugadi"):
            print("  ", {k: (v[:200] if isinstance(v, str) else v) for k, v in h.items()})
    return hod


def main():
    t0 = time.time()
    assert c.post("/api/loyiha", json={"nom": "Sinov"}).status_code == 200
    tana = {"sid": SID, "loyiha": "Sinov", "chat_id": None, "alifbo": True,
            "matn": "Shahar tozaligi haqida Word hujjat tayyorla: sarlavha, kirish bo'limi (2 ta band) va 3 qatorli jadval. Fayl nomi hisobot.docx"}
    hod = oqim("/api/chat", tana)
    cid = next(h["id"] for h in hod if h["t"] == "chat")
    n = 0
    while any(h["t"] == "tasdiq" for h in hod) and n < 4:
        n += 1
        hod = oqim("/api/tasdiq", {"sid": SID, "ha": True, "alifbo": True})
    f = server.ISH / "hisobot.docx"
    print(f"1) Word: fayl bor={f.exists()}  tasdiqlar={n}  vaqt={time.time() - t0:.0f}s")
    if f.exists():
        from docx import Document
        d = Document(str(f))
        print("   matn:", [p.text for p in d.paragraphs][:6], "jadval:", len(d.tables))

    ch = c.get("/api/chatlar?loyiha=Sinov").get_json()["chatlar"]
    print("2) chatlar:", ch)
    o = c.post("/api/ochish", json={"sid": "boshqa", "loyiha": "Sinov", "id": cid, "alifbo": True}).get_json()
    print("   qayta ochildi, ko'rinish:", [(x["rol"], x["matn"][:50]) for x in o["korinish"]], o["kontekst"])

    # xulosa: 14 ta xabarli chat (haqiqiy tarixga qo'shamiz)
    s = server.suhbat("boshqa")
    for i in range(7):
        s.xabarlar += [{"role": "user", "content": f"Men {i}-hafta uchun choy hisoboti kerak, shahar Samarqand."},
                       {"role": "assistant", "content": f"Yaxshi, {i}-hafta hisobotini tayyorlayman. Fayl nomi hisobot{i}.docx bo'ladi."}]
    server.agent.saqla(s)
    t1 = time.time()
    r = c.post("/api/xulosa", json={"sid": "boshqa"})
    print(f"3) xulosa: {r.status_code} {time.time() - t1:.0f}s", r.get_json())
    print("   xulosa.md:", repr(saqlash.xulosa_oqi("Sinov")[:400]))
    print("   xulosalangan =", s.xulosalangan, "/", len(s.xabarlar))
    r2 = c.post("/api/chat", json={"sid": "boshqa", "loyiha": "Sinov", "chat_id": cid, "alifbo": False,
                                   "matn": "Oldingi hisobotlar haqida nima bilasan? Qisqa ayt."})
    hod = [json.loads(q) for q in r2.get_data(as_text=True).splitlines() if q.strip()]
    print("4) xotira bilan javob:", "".join(h["v"] for h in hod if h["t"] == "matn")[:300])
    print("   kontekst:", [h for h in hod if h["t"] == "kontekst"])
    return 0 if f.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
