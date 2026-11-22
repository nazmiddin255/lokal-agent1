# TOPSHIRIQ: Local_model1 — lokal kundalik yordamchi (agent)

Sen Claude Code'san. Bu papkada (`~/Local_model1`) kichik, xavfsiz va yengil lokal agent quryapsan. Avval `CLAUDE.md` ni o'qi, qoidalar o'sha yerda.

## 1. Maqsad
Foydalanuvchi o'zbekcha yozadi. Lokal model (Ollama) kundalik ishlarni bajaradi:
1. Hujjat tayyorlash (Word, Excel, PowerPoint).
2. Kerakli kod/skriptni aniq yozib berish.
3. Kompyuterda papka yaratish va aytilgan faylni kerakli joyda saqlash.
Hammasi brauzerda ochiladigan chat oynasida, kam RAM bilan.

## 2. Muhit (tayyor, qayta o'rnatma)
- Debian Linux, CPU: Intel i3-1215U, RAM 7.5 GB, videokarta YO'Q. Internet trafigi cheklangan: katta yuklashdan oldin so'ra.
- Python 3.14, virtual muhit: `~/Local_model1/.venv` (o'rnatilgan: flask, openpyxl, python-docx, python-pptx). Boshqa paket kerak bo'lsa avval so'ra.
- Ollama xizmati ishlayapti: `http://localhost:11434`. Model: `qwen3:4b-instruct-2507-q4_K_M` (tekshirilgan: inglizcha kod yaxshi, o'zbekcha uzun matn yomon va takrorlaydi).

## 3. Ish tartibi (MUHIM — chatni maydalama)
- Ishni 2 ta KATTA bosqichda qil (A va B, quyida). Har kichik narsada to'xtama, savol berma.
- Chatga uzun tushuntirma yozma. Sinovlarni o'zing jim o'tkaz.
- Har bosqich oxirida BITTA qisqa hisobot ber: nima tayyor, qanday ishga tushiriladi, nima sinaldi. Keyin to'xta, foydalanuvchi o'zi sinaydi.
- Batafsil holatni `HOLAT.md` ga yoz (chatga emas).
- Faqat `~/Local_model1` ichida ishla. Hech narsani o'chirma. Git push, GitHub, tizim sozlamalari — TEGMA.

## 4. A bosqich — asos
**Tuzilma:** Flask server faqat `127.0.0.1` da (internetga chiqmaydi), port 5000. Ishga tushirish: `ishga_tushir.sh` (venv ni o'zi ishlatadi va brauzerni ochadi).

**Ish papkasi:** `~/Local_model1/ish/` (sozlamada o'zgartirsa bo'ladi). Agent FAQAT shu papka ichida ishlaydi.

**Agent vositalari (tool calling, qwen3 qo'llaydi):**
`list_dir`, `read_file`, `create_folder`, `write_file`, `run_python` (faqat ish papkasi ichida, vaqt chegarasi bilan, sinov uchun).
- O'chirish vositasi UMUMAN YO'Q. Mavjud faylni ustidan yozish ham faqat alohida tasdiq bilan.
- Har yozuvchi amaldan (papka/fayl yaratish, yozish, kod ishga tushirish) oldin brauzerda foydalanuvchidan **Ha/Yo'q** tasdig'i so'ralsin: nima va qayerda ko'rsatilsin.
- Yo'l tekshiruvi: `resolve()` qilib ish papkasidan tashqarisini (`..`, absolyut yo'l, symlink) rad et. Buning uchun test yoz.

**Model bilan ishlash:**
- Ollama `/api/chat`, streaming. Sozlamalar: `temperature 0.7, top_p 0.8, top_k 20, repeat_penalty 1.1`, `num_ctx` 4096 (kerak bo'lsa 8192 gacha), `keep_alive 5m`.
- Modelga system prompt INGLIZCHA bo'lsin (qisqa, aniq). Foydalanuvchi o'zbekcha yozadi, model vositalarni inglizcha buyruq bilan chaqiradi.
- Model xato JSON/tool chaqirsa, dastur o'zi 1–2 marta tuzatishga urinsin, keyin foydalanuvchiga qisqa xabar.
- `qwen3:4b-instruct-2507-q4_K_M` nomi sozlamada bo'lsin (keyin almashtirish oson).

**Chat oynasi (UI matnlari o'zbekcha, oddiy, chiroyli, yengil, tashqi kutubxonasiz/CDN siz):**
Tugmalar: Yuborish, To'xtatish, Yangi suhbat, Ha/Yo'q (tasdiq), Kun/Tun rejimi, Fayllar (ish papkasi ro'yxati, faqat ko'rish), **Yangi alifbo** yoqish/o'chirish.
Modelning javobi streaming bo'lib chiqsin. RAM kam: sahifa og'ir bo'lmasin.

**Yangi alifbo moduli (`alifbo.py`, modelsiz):**
- Model hamma narsani oddiy lotinda yozadi. Dastur chiqishda o'giradi: `sh→ş, ch→ç, o'→ö, g'→ğ` (bosh harflar ham: Sh→Ş, Ch→Ç, O'→Ö, G'→Ğ).
- Foydalanuvchi yangi alifboda yozsa, avval oddiy lotinga qaytar, keyin modelga ber.
- Apostrof variantlari (`'`, `‘`, `’`, `ʻ`) bir xil qabul qilinsin.
- O'girilmasin: kod bloklari, inglizcha so'zlar, fayl nomlari, URL, buyruqlar.
- Istisno ro'yxati alohida fayl (`alifbo_istisno.txt`), foydalanuvchi tahrirlay oladi.
- Tugma holati saqlansin. Aylanma (lotin→yangi→lotin) testlari yoz.

## 5. B bosqich — loyihalar, tarix, xotira, hujjatlar
(A bosqichni foydalanuvchi sinab, "davom et" deganidan keyin.)

**Loyihalar va tarix** (oddiy fayllar, JSON/Markdown):
```
data/umumiy_xotira.md            # juda qisqa doimiy qoidalar (<=200 so'z), har chatda o'qiladi
data/loyihalar/<nom>/xulosa.md   # loyiha xulosasi (<=300 so'z)
data/loyihalar/<nom>/chatlar/*.json
```
- UI da "Loyihalar" bo'limi: loyiha yaratish, tanlash, chatlar ro'yxati.
- Har loyihada ko'pi bilan 20 ta chat saqlansin (eskisini ko'rsatib so'rab, keyin chetga ol, o'chirma).
- Yangi chat boshlanganda modelga faqat `umumiy_xotira.md` + shu loyihaning `xulosa.md` beriladi (to'liq tarix emas).
- Chat uzayganda: oxirgi 12 xabar to'liq qoladi, eskilari **"Xulosa qil" tugmasi bosilganda** model orqali qisqa xulosaga aylanib `xulosa.md` ga qo'shiladi (avtomatik emas, CPU og'ir). Xulosa ichkarida inglizcha bo'lsin. Foydalanuvchi `xulosa.md` ni tahrirlay olsin.
- Kontekst chegarasi tekshirilsin, oshsa foydalanuvchiga ogohlantirish.

**Hujjatlar (Word/Excel/PowerPoint):**
- Model faqat tuzilgan ma'lumot beradi (sarlavha, bandlar, jadval qatorlari, maydonlar), maketni dastur qiladi (python-docx, openpyxl, python-pptx).
- Fayl `ish/` ichida saqlansin (tasdiqdan keyin). Yangi alifbo yoqilgan bo'lsa, matn o'girilib yozilsin, shrift `ş ç ö ğ` ni ko'rsatadigan bo'lsin.
- Namunalar papkasi (`namunalar/`) bo'lsa, shablon sifatida ishlatish imkonini qoldir (hozir majburiy emas).

## 6. Sinovlar (o'zing, jim)
- Yo'l xavfsizligi (tashqariga chiqish rad etiladi), o'chirish vositasi yo'qligi.
- Alifbo aylanma testlari.
- Ollama ulanishi va bitta oxirigacha sinov: "test papka yarat, ichiga hello.txt ga Salom yoz" → tasdiq → fayl paydo bo'ladi.
- RAM: server o'zi ~100 MB dan oshmasin.

## 7. Yetkazib berish
`ishga_tushir.sh`, qisqa o'zbekcha `README.md` (qanday ishga tushiriladi, qanday ishlatiladi, cheklovlar), `HOLAT.md`.
Loyiha "AI yordamida yaratilgan" ekani README da bitta qisqa qatorda aytilsin.
