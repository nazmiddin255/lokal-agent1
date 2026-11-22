"""Oxirigacha sinov (haqiqiy Ollama bilan). Ishga tushirish:
    LM1_ISH=/vaqtinchalik/papka .venv/bin/python tests/e2e_ollama.py
LM1_ISH berilmasa, sozlamadagi ish papkasi ishlatiladi."""
import json
import os
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402

SO_ROV = os.environ.get("SOROV", "test papka yarat, ichiga hello.txt ga Salom yoz")


def oqim(c, url, tana):
    r = c.post(url, json=tana)
    hod = [json.loads(q) for q in r.get_data(as_text=True).splitlines() if q.strip()]
    for h in hod:
        if h["t"] != "matn":
            print("  ", h)
    matn = "".join(h["v"] for h in hod if h["t"] == "matn")
    if matn:
        print("   [model]:", matn[:300])
    return hod


def main():
    c = server.app.test_client()
    t0 = time.time()
    hod = oqim(c, "/api/chat", {"sid": "e2e", "matn": SO_ROV, "alifbo": False})
    tasdiqlar = 0
    while any(h["t"] == "tasdiq" for h in hod) and tasdiqlar < 6:
        tasdiqlar += 1
        hod = oqim(c, "/api/tasdiq", {"sid": "e2e", "ha": True, "alifbo": False})
    f = server.ISH / "test" / "hello.txt"
    print(f"vaqt: {time.time() - t0:.1f} s, tasdiqlar: {tasdiqlar}")
    print("fayl bor:", f.exists(), "| matn:", f.read_text() if f.exists() else "-")
    print(f"server RAM (maks RSS): {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")
    return 0 if f.exists() and "salom" in f.read_text().lower() else 1


if __name__ == "__main__":
    sys.exit(main())
