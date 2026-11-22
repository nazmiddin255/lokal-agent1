"""Sozlamalarni yuklash: config.json + standart qiymatlar.
Ish papkasini sinov uchun LM1_ISH muhit o'zgaruvchisi bilan almashtirish mumkin."""
import json
import os
from pathlib import Path

ILDIZ = Path(__file__).resolve().parent

STANDART = {
    "model": "qwen3:4b-instruct-2507-q4_K_M",
    "ollama_url": "http://localhost:11434",
    "ish_papka": "ish",
    "host": "127.0.0.1",
    "port": 5000,
    "keep_alive": "5m",
    "options": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.1,
        "num_ctx": 4096,
    },
    "python_vaqt_chegarasi": 30,
    "max_qadam": 8,
}


def yukla():
    s = json.loads(json.dumps(STANDART))
    fayl = ILDIZ / "config.json"
    if fayl.exists():
        try:
            d = json.loads(fayl.read_text(encoding="utf-8"))
            opts = d.pop("options", {})
            s.update(d)
            s["options"].update(opts)
        except (OSError, ValueError) as e:
            print(f"[ogohlantirish] config.json o'qilmadi: {e}")
    ish = os.environ.get("LM1_ISH") or s["ish_papka"]
    p = Path(ish).expanduser()
    if not p.is_absolute():
        p = ILDIZ / p
    s["ish_yol"] = p
    # num_ctx 8192 dan oshmasin (RAM kam)
    s["options"]["num_ctx"] = max(2048, min(int(s["options"].get("num_ctx", 4096)), 8192))
    return s
