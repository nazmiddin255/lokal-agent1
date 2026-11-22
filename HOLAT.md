# HOLAT — Local_model1

Oxirgi yangilanish: 2026-11-23. **A va B bosqich tayyor**, foydalanuvchi B ni sinashini kutmoqda.

## Fayllar
| Fayl | Vazifasi |
|---|---|
| `server.py` | Flask, faqat 127.0.0.1:5000 (host kodda qat'iy). API: `/api/chat`, `/api/tasdiq`, `/api/toxtat`, `/api/yangi`, `/api/fayllar`, `/api/fayl`, `/api/holat`. Javob NDJSON oqim. |
| `agent.py` | Ollama `/api/chat` streaming, tool calling sikli, tasdiq navbati, JSON tuzatish (2 marta), kontekst kesish, inglizcha system prompt. |
| `vositalar.py` | `list_dir, read_file, create_folder, write_file, run_python`. `xavfsiz_yol()` — resolve + tashqarini rad etish. O'chirish yo'q. |
| `alifbo.py` | lotin↔yangi o'giruvchi + `OqimOgirgich` (streaming uchun). |
| `alifbo_istisno.txt` | o'girilmaydigan so'zlar (tahrirlanadi, qayta yuklash shart emas — mtime bo'yicha). |
| `sozlama.py`, `config.json` | sozlamalar (model nomi, ish papkasi, options). `LM1_ISH` env — sinov uchun ish papkasini almashtirish. |
| `static/index.html` | UI (bitta fayl, CDN siz, ~15 KB). |
| `ishga_tushir.sh` | venv bilan server + `xdg-open`. Server ishlayotgan bo'lsa faqat brauzerni ochadi. |
| `tests/` | `test_alifbo.py`, `test_xavfsiz.py` (unittest), `e2e_ollama.py` (haqiqiy Ollama bilan). |

## Qarorlar
- Tasdiq oqimi: yozuvchi vosita kelganda oqim `tasdiq` hodisasi bilan tugaydi; brauzer Ha/Yo'q ni `/api/tasdiq` ga yuboradi, agent davom etadi. Tasdiq kutilayotganda yangi xabar yozilsa — rad deb hisoblanadi.
- Ustidan yozish: fayl mavjud bo'lsa `write_file` modelga xato qaytaradi; model `overwrite=true` bersa — qizil ogohlantirishli alohida tasdiq.
- Model "kod yoz" ni ko'pincha "faylga yoz" deb tushunadi. Shuning uchun dastur tekshiradi: oxirgi foydalanuvchi xabarida `saqla|fayl|papka|yarat|ichiga|.ext|save|file|folder` bo'lmasa, `write_file/create_folder` foydalanuvchiga ko'rsatilmay rad etiladi va model kodni chatda ko'rsatadi.
- Model tool chaqiruvini matn qilib yozsa (`<tool_call>` yoki `{...}`), dastur ajratib oladi; boshidagi JSON ekranga chiqarilmaydi.
- Yangi alifbo yoqilganda: kirish → `lotinga()` (har doim, apostroflarni ham bir xil qiladi), chiqish → `yangiga()`. `write_file` da faqat `.txt/.md` fayllar matni o'giriladi (kod fayllari emas). Tarix modelga oddiy lotinda boradi.
- `o'` so'z oxirida o'girilmaydi (qo'shtirnoq bilan adashmaslik uchun); `g'` oxirida o'giriladi (tog' → toğ).
- `run_python`: `python -I`, cwd = ish, minimal env, 30 s chegara, 512 MB xotira chegarasi. Bu qafas EMAS — himoya = tasdiq.
- Kontekst: num_ctx×1.5 belgi byudjeti, eskisi kesiladi + ogohlantirish (B da xulosa bilan yaxshilanadi).

## Sinov natijalari (2026-11-23)
- Unit testlar: 23/23 OK (yo'l xavfsizligi: `..`, absolyut, `~`, tashqi symlink, `\x00`; o'chirish vositasi yo'qligi; ustidan yozish; alifbo aylanma, apostrof variantlari, himoya, streaming bo'laklari).
- E2E (Ollama, test client): "test papka yarat, ichiga hello.txt ga Salom yoz" → 2 tasdiq → `test/hello.txt` = "Salom". ~52 s.
- Brauzer UI orqali ham shu sinov o'tdi; Fayllar paneli, Tun rejimi ishladi.
- To'xtatish: oqim to'xtadi, "To'xtatildi." chiqdi. `/api/fayl?yol=../../etc/passwd` → 403.
- Server RAM: ~40 MB (RSS).
- Sinovlar vaqtinchalik papkada qilindi, `ish/` bo'sh.

## B bosqich (2026-11-23)
### Yangi fayllar
| Fayl | Vazifasi |
|---|---|
| `saqlash.py` | loyihalar, chatlar (JSON), umumiy xotira, xulosa.md. Loyiha nomi tekshiriladi (harf/raqam/bo'sh joy/-/_, ≤40). Chat yozish atomik. `arxivla()` faylni `chatlar/arxiv/` ga KO'CHIRADI (o'chirmaydi). Kodda o'chirish chaqiruvi yo'q (test tekshiradi). |
| `dokumentlar.py` | `make_docx/xlsx/pptx` uchun: ma'lumotni tozalash (`normallash`), tasdiq uchun reja (`korsatma`), python-docx/openpyxl/python-pptx bilan maket. Shrift Arial. Shablon: `namunalar/` (bor bo'lsa `template` parametri paydo bo'ladi). |
| `tests/test_b.py` | saqlash, kontekst, xulosa nuqtasi, hujjatlar testlari. `tests/e2e_b.py` — Ollama bilan (LM1_ISH va LM1_DATA majburiy, sinov papkalari). |
| `data/` | `umumiy_xotira.md`, `loyihalar/<nom>/{xulosa.md,chatlar/}`. Boshida "Umumiy" loyiha bor. |

### Qarorlar
- Modelga: system prompt + umumiy_xotira + xulosa.md (har so'rovda qayta o'qiladi, tahrir darrov ta'sir qiladi) + `xabarlar[xulosalangan:]`. `xulosalangan` — xulosa.md ga o'tgan xabarlar soni, chat JSON ida saqlanadi.
- "Xulosa qil": oxirgi 12 xabar qoladi, kesim 'user' xabarida (tool juftligi buzilmaydi). Model inglizcha ≤100 so'z yozadi, `## sana` bilan oxiriga qo'shiladi. 300 so'zdan oshsa UI ogohlantiradi; qo'lda saqlashda chegara qat'iy (xotira 200, xulosa 300), modelga beriladigan matn 600 so'zdan oshmaydi.
- Kontekst: `max(taxmin, prompt_eval_count+eval_count)`; UI da "Kontekst ~N/4096", ≥85% da qizil + ogohlantirish.
- 20 chat chegarasi: server 409 `limit` qaytaradi → UI "eng eskisini arxivga olaymi?" so'raydi → Ha → `/api/arxivla` → qayta yuboradi.
- Hujjat vositalari modelga faqat oxirgi 3 foydalanuvchi xabarida kalit so'z (word/excel/taqdimot...) bo'lsa beriladi — prompt 1600 → ~900 token (CPU da tez).
- Excel: son ko'rinishidagi matn songa aylanadi (007 — yo'q), faqat oq ro'yxatdagi formulalar (SUM, AVERAGE, MIN, MAX, COUNT, ROUND, IF, ABS) formula bo'ladi, qolgan `=...` matn. Hujjat xotirada (BytesIO) yig'ilib bir martada yoziladi.
- Yozuvchi vositalar (`make_*` ham) faqat foydalanuvchi xabarida saqlash niyati bo'lsa ko'rsatiladi (aks holda model chatda javob beradi).
- `num_ctx` 4096 ga qaytarildi: 6144 da RAM yetmay (swap) javob 2–3 daqiqa bo'ldi. Bo'sh RAM hozir ~200 MB, kompyuterda boshqa dasturlar ko'p.

### Sinov natijalari
- 46 unit test OK (jami A+B).
- E2E (Ollama): Word hujjat so'rovi → 1 tasdiq → `hisobot.docx` (sarlavha, bo'lim, jadval; yangi alifbo bilan `Şahar`, `Kiriş`) ~177 s (birinchi chaqiruvda model yuklanadi). Chat saqlandi, boshqa sessiyada `/api/ochish` bilan qayta ochildi. "Xulosa qil" 29 s: 18 xabardan 6 tasi xulosa.md ga o'tdi (42 so'z, inglizcha), keyingi savolga model xulosadan foydalanib javob berdi.
- LibreOffice bilan docx/xlsx/pptx ochildi: `ş ç ö ğ` to'g'ri chiqdi.
- Brauzer: Loyihalar paneli, chat ro'yxati, ✕ tugmalari (tor oynada) ishladi. Sinovlar vaqtincha papkada, `ish/` bo'sh, `data/` da faqat "Umumiy".

## Ma'lum cheklovlar / keyinga
- 4B model ba'zan kodni fence siz yozadi yoki ortiqcha papka o'ylab topadi (prompt bilan kamaytirildi).
- Flask dev server (bitta foydalanuvchi uchun yetarli).
- 4B model o'zbekcha hujjat matnini ba'zan mazmunsiz yozadi (jadval to'ldirishi ham). Foydalanuvchi matnni tekshirishi kerak. Aniq matnni o'zi aytsa yaxshiroq.
- Chat sarlavhalari ro'yxatda har doim oddiy lotinda (yangi alifbo faqat chat matnida).
- Xotira oynasi (200 so'z chegarasi, saqlash) va 20-chat arxiv kartasi brauzerda sinaldi: eng eski chat arxiv/ ga ko'chdi, yangisi ochildi.
