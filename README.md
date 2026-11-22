# lokal-agent1 — lokal kundalik yordamchi

![AI yordamida yaratilgan](https://img.shields.io/badge/AI%20yordamida-yaratilgan-blue)
![Litsenziya: MIT](https://img.shields.io/badge/litsenziya-MIT-green)

> **AI yordamida yaratilgan.** Bu loyiha AI (Claude Code) yordamida yozilgan. Men kodni o'qib chiqdim,
> o'zim ishga tushirib sinadim va nima qilishini tushunaman: qaysi fayl nima uchun javob beradi,
> xavfsizlik tekshiruvlari qanday ishlaydi, testlar nimani tekshiradi. AI menga tez yozishga yordam berdi,
> lekin natijaga javobgar — men.

Kompyuteringizda ishlaydigan kichik yordamchi. Brauzerda ochiladigan chat oynasi, model (Ollama) shu kompyuterning o'zida ishlaydi, internetga ma'lumot chiqmaydi. Foydalanuvchi o'zbekcha yozadi.

## Nima qiladi

- **Hujjat tayyorlaydi:** Word, Excel, PowerPoint (model mazmunni beradi, maketni dastur qiladi).
- **Kod yozib beradi:** aniq, to'liq kod chatda ko'rsatiladi; xohlasangiz faylga saqlaydi.
- **Papka va fayl yaratadi:** aytilgan joyda, har amaldan oldin sizdan **Ha / Yo'q** so'rab.
- **Loyihalar, tarix, xotira:** suhbatlar loyiha bo'yicha saqlanadi, doimiy qoidalar va loyiha xulosasi modelga beriladi.
- **Yangi alifbo:** javoblarni `sh→ş, ch→ç, o'→ö, g'→ğ` ko'rinishida chiqarish (tugma bilan yoqiladi).

Yengil: videokartasiz, 8 GB RAM li oddiy kompyuterda ishlashi uchun mo'ljallangan.

## O'rnatish

Talab: Linux (Debian da sinalgan), Python 3.10+, [Ollama](https://ollama.com).

1. Ollama ni o'rnating (https://ollama.com/download) va modelni yuklab oling. Model fayli repoda yo'q, Ollama o'zi yuklaydi:
   ```bash
   ollama pull qwen3:4b-instruct-2507-q4_K_M
   ```
2. Loyihani oling va virtual muhit yarating:
   ```bash
   git clone https://github.com/nazmiddin255/lokal-agent1.git
   cd lokal-agent1
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

## Ishga tushirish

```bash
./ishga_tushir.sh
```

Brauzer o'zi ochiladi: http://127.0.0.1:5000 . To'xtatish: terminalda **Ctrl+C**.
Oynaning yuqorisida yashil ● bo'lsa, Ollama va model tayyor.

## Ishlatish

- Savolni o'zbekcha yozing, **Yuborish** (yoki Enter). Misol: *test papka yarat, ichiga hello.txt ga Salom yoz*.
- **To'xtatish** javobni to'xtatadi, **Yangi suhbat** yangi bo'sh suhbat ochadi.
- **Fayllar** — ish papkasidagi fayllar (faqat ko'rish, hujjatlarni yuklab olish).
- **Loyihalar** — loyiha tanlash va yaratish, suhbatlar ro'yxati (bir loyihada 20 tagacha; ortig'i arxivga olinadi).
- **Xotira** — umumiy qoidalar (≤200 so'z) va loyiha xulosasi (≤300 so'z) ni tahrirlash.
- **Xulosa qil** — oxirgi 12 xabardan oldingi suhbatni qisqa xulosaga aylantirib xulosaga qo'shadi.
- **Yangi alifbo**, **Kun/Tun** rejimi.

Hujjat misoli: *Shahar tozaligi haqida Word hujjat tayyorla, sarlavha, kirish bo'limi va jadval bo'lsin. Fayl nomi hisobot.docx*.
Shablon ishlatish uchun `namunalar/` papkasiga `.docx/.xlsx/.pptx` qo'yish mumkin (majburiy emas).

## Sozlamalar

`config.json`: model nomi, ish papkasi (`ish_papka`), model parametrlari (`num_ctx` va boshqalar). O'zgartirgach serverni qayta ishga tushiring.
Yangi alifboda o'girilmaydigan so'zlar `alifbo_istisno.txt` da.

## Xavfsizlik qoidalari

- Server faqat `127.0.0.1` da ishlaydi, tashqaridan ko'rinmaydi.
- Agent faqat **ish papkasi** (`ish/`) ichida ishlaydi. `..`, absolyut yo'l, `~` va papkadan tashqariga olib chiquvchi symlink rad etiladi (testlari bor).
- **O'chirish vositasi yo'q.** Mavjud faylni ustidan yozish faqat alohida, ogohlantirishli tasdiq bilan.
- Fayl/papka yaratish, hujjat yozish va kod ishga tushirishdan oldin har safar **Ha / Yo'q** so'raladi: nima va qayerda ko'rsatiladi.
- Chatlar va xotira (`data/`) faqat sizning kompyuteringizda, repoga kirmaydi.
- Excelda faqat xavfsiz oddiy formulalar (`SUM`, `AVERAGE`, …) formula bo'ladi, qolgan `=...` yozuvlar matn bo'lib qoladi.

## Cheklovlar

- **`run_python` to'liq himoyalangan muhit emas:** kod kompyuteringizda bajariladi (vaqt va xotira chegarasi bor). Faqat tushunadigan kodingizga **Ha** bosing.
- Model kichik (4B) va CPU da ishlaydi: javob sekin (10–90 soniya, birinchi so'rov undan ham uzoq), o'zbekcha uzun matnda xato qilishi mumkin. Hujjat matnini albatta o'qib chiqing.
- RAM kam bo'lsa `num_ctx` ni 4096 dan oshirmang.
- Flask ning ishlab chiqish serveri ishlatiladi: bitta foydalanuvchi uchun, internetga ochmang.

## Testlar

```bash
.venv/bin/python -m unittest discover -s tests -v
```

(`tests/e2e_*.py` haqiqiy Ollama kerak bo'lgan qo'lda ishga tushiriladigan sinovlar.)

## Litsenziya

[MIT](LICENSE)

---

## English

**lokal-agent1** is a small, lightweight local assistant with a browser chat UI. The model runs on your own machine through Ollama, nothing is sent to the internet. You write in Uzbek; it can prepare Word/Excel/PowerPoint files, write code, and create folders and files for you.

- **Requirements:** Linux, Python 3.10+, [Ollama](https://ollama.com) and the model `qwen3:4b-instruct-2507-q4_K_M` (`ollama pull qwen3:4b-instruct-2507-q4_K_M`; the model is not in this repo).
- **Install:** `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- **Run:** `./ishga_tushir.sh`, then open http://127.0.0.1:5000 (the server listens on localhost only).
- **Safety:** the agent works only inside the `ish/` folder (`..`, absolute paths and escaping symlinks are rejected); there is no delete tool; every write action (create folder/file, make document, run Python) needs your Yes/No approval first.
- **Limitations:** slow on CPU (tens of seconds per answer); the small 4B model is weak at long Uzbek text, so always review generated documents; `run_python` is not a full sandbox; the built-in Flask server is for a single local user only.

Created with AI assistance (Claude Code); reviewed and tested by the author. Licensed under MIT.
