"""AI (Gemini / Groq): Excel'dagi dori ro'yxatini tahlil qilib, har bir dorini qaysi filialga qo'shishni aniqlaydi.

API kalitlar admin panel → Sozlamalar → «AI (Gemini / Groq)» orqali settings jadvalida saqlanadi.
Model kiritilmaydi — kalit saqlanganda mavjud modellar ro'yxatidan eng mosi avtomatik tanlanadi.
Ikkala kalit bo'lsa: avval Gemini, u xato bersa (limit, tarmoq) — Groq.
"""
import io
import json
import asyncio
import logging

import aiohttp

from database import queries as q

logger = logging.getLogger("bot")

PROVIDERS = ("gemini", "groq")
LABEL = {"gemini": "Gemini", "groq": "Groq"}
_GEM_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GROQ_BASE = "https://api.groq.com/openai/v1"
# Afzal modellar (tez va arzon, katta kontekst) — ro'yxatda birinchi topilgani tanlanadi
_GEM_PREF = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite",
             "gemini-1.5-flash")
_GROQ_PREF = ("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b",
              "meta-llama/llama-4-maverick-17b-128e-instruct", "meta-llama/llama-4-scout-17b-16e-instruct",
              "llama-3.1-8b-instant")
CHUNK_ROWS = 120        # bitta so'rovga nechta Excel qatori
MAX_ROWS = 4000         # bitta fayldan ko'pi bilan
PARALLEL = 3


class AIError(Exception):
    def __init__(self, msg, fatal=False):
        super().__init__(msg)
        self.fatal = fatal       # kalit noto'g'ri — boshqa urinish foydasiz


def mask_key(key: str) -> str:
    return (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("…" if key else "")


async def get_config() -> dict:
    """{provider: (key, model)} — faqat kaliti borlari, ustuvorlik tartibida."""
    out = {}
    for p in PROVIDERS:
        key = (await q.get_setting(f"{p}_api_key", "") or "").strip()
        if key:
            out[p] = (key, (await q.get_setting(f"{p}_model", "") or "").strip())
    return out


async def enabled() -> bool:
    return bool(await get_config())


# ---------------- HTTP ----------------
async def _http(method, url, headers, payload=None, timeout=120):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.request(method, url, json=payload, headers=headers) as r:
                return r.status, await r.json(content_type=None)
    except asyncio.TimeoutError:
        raise AIError("AI javob bermadi (vaqt tugadi). Keyinroq urinib ko'ring.")
    except aiohttp.ClientError as e:
        raise AIError(f"AI bilan aloqa yo'q: {e.__class__.__name__}")
    except ValueError:
        raise AIError("AI javobi noto'g'ri formatda")


def _err(provider, status, data):
    msg = ""
    if isinstance(data, dict):
        e = data.get("error")
        msg = (e.get("message", "") if isinstance(e, dict) else str(e or ""))
    name = LABEL[provider]
    if status in (401, 403) or (status == 400 and ("API key" in msg or "API_KEY" in msg)):
        return AIError(f"{name} API kaliti noto'g'ri yoki ruxsati yo'q", fatal=True)
    if status == 429:
        return AIError(f"{name} limiti tugadi (429). Birozdan keyin urinib ko'ring.")
    if status == 404:
        return AIError(f"{name}: model topilmadi")
    return AIError(f"{name} xatosi ({status}): {msg[:160]}")


# ---------------- Model avtomatik tanlash ----------------
async def detect_model(provider, key) -> str:
    """Kalit bilan mavjud modellar ro'yxatini olib, eng mosini tanlaydi (kalitni ham tekshiradi)."""
    if provider == "gemini":
        st, data = await _http("GET", f"{_GEM_BASE}/models?pageSize=200", {"x-goog-api-key": key}, timeout=30)
        if st != 200:
            raise _err(provider, st, data)
        names = [m["name"].split("/", 1)[-1] for m in (data.get("models") or [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        pref = _GEM_PREF
        fallback = [n for n in names if "flash" in n and "image" not in n and "tts" not in n
                    and "live" not in n and "audio" not in n] or names
    else:
        st, data = await _http("GET", f"{_GROQ_BASE}/models", {"Authorization": f"Bearer {key}"}, timeout=30)
        if st != 200:
            raise _err(provider, st, data)
        names = [m["id"] for m in (data.get("data") or []) if m.get("active", True)]
        pref = _GROQ_PREF
        skip = ("whisper", "tts", "guard", "playai", "orpheus", "distil", "compound")
        fallback = [n for n in names if not any(s in n for s in skip)] or names
    for p in pref:
        if p in names:
            return p
    if fallback:
        return sorted(fallback)[-1]       # eng yangi versiya (nom bo'yicha)
    raise AIError(f"{LABEL[provider]}: mos model topilmadi")


# ---------------- So'rov ----------------
_SCHEMA_TXT = ('{"items": [{"name": "string", "price": 0, "unit": "string", "note": "string", '
               '"in_stock": true, "branch_id": 0}]}')


async def _call(provider, key, model, prompt, schema=None, timeout=120) -> dict:
    if provider == "gemini":
        gen = {"temperature": 0, "responseMimeType": "application/json"}
        if schema:
            gen["responseSchema"] = schema
        st, data = await _http("POST", f"{_GEM_BASE}/models/{model}:generateContent",
                               {"x-goog-api-key": key},
                               {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                "generationConfig": gen}, timeout)
        if st != 200:
            raise _err(provider, st, data)
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            reason = ((data.get("candidates") or [{}])[0].get("finishReason")
                      or (data.get("promptFeedback") or {}).get("blockReason") or "bo'sh javob")
            raise AIError(f"Gemini javobi bo'sh ({reason})")
    else:
        st, data = await _http("POST", f"{_GROQ_BASE}/chat/completions",
                               {"Authorization": f"Bearer {key}"},
                               {"model": model, "temperature": 0, "max_tokens": 8192,
                                "response_format": {"type": "json_object"},
                                "messages": [
                                    {"role": "system", "content": "Faqat to'g'ri JSON qaytar, boshqa matn yozma."
                                                                  + (f" Format: {_SCHEMA_TXT}" if schema else "")},
                                    {"role": "user", "content": prompt}]}, timeout)
        if st != 200:
            raise _err(provider, st, data)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIError("Groq javobi bo'sh")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise AIError(f"{LABEL[provider]} javobi JSON emas — qayta urinib ko'ring")


async def generate_json(prompt, schema=None, cfg=None, timeout=120) -> dict:
    """Kaliti bor provayderlarni navbat bilan sinaydi (Gemini → Groq)."""
    cfg = cfg if cfg is not None else await get_config()
    if not cfg:
        raise AIError("AI kaliti kiritilmagan (Sozlamalar → AI)")
    last = None
    for p, (key, model) in cfg.items():
        try:
            if not model:
                model = await detect_model(p, key)
                await q.set_setting(f"{p}_model", model)
            try:
                return await _call(p, key, model, prompt, schema, timeout)
            except AIError as e:
                if "model topilmadi" not in str(e):
                    raise
                model = await detect_model(p, key)        # model eskirgan — qayta tanlaymiz
                await q.set_setting(f"{p}_model", model)
                return await _call(p, key, model, prompt, schema, timeout)
        except AIError as e:
            logger.warning("AI %s: %s", p, e)
            last = e
    raise last


async def check_key(provider, key) -> str:
    """Kalitni tekshiradi va modelni tanlaydi. Qaytaradi: model nomi."""
    model = await detect_model(provider, key)
    r = await _call(provider, key, model, 'Return JSON: {"ok": true}', timeout=40)
    if not isinstance(r, dict):
        raise AIError(f"{LABEL[provider]} javobi noto'g'ri")
    return model


# ---------------- Excel -> matn bo'laklari ----------------
def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).replace("\t", " ").replace("\n", " ").strip()


def excel_chunks(raw: bytes):
    """Barcha varaqlar -> [(varaq nomi, sarlavha (kontekst), [qatorlar])] bo'laklari (TSV matn)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    chunks, total = [], 0
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [_cell(v) for v in row]
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                rows.append("\t".join(cells))
        if not rows:
            continue
        # Birinchi bo'lak varaqni boshidan oladi; keyingilariga dastlabki 3 qator (sarlavha)
        # faqat kontekst sifatida qo'shiladi — ustunlar ma'nosi va filial nomi yo'qolmasin
        for i in range(0, len(rows), CHUNK_ROWS):
            part = rows[i:i + CHUNK_ROWS]
            chunks.append((ws.title, rows[:3] if i else [], part))
            total += len(part)
            if total >= MAX_ROWS:
                return chunks, True
    return chunks, False


_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "price": {"type": "INTEGER"},
                    "unit": {"type": "STRING"},
                    "note": {"type": "STRING"},
                    "in_stock": {"type": "BOOLEAN"},
                    "branch_id": {"type": "INTEGER"},
                },
                "required": ["name", "price", "in_stock", "branch_id"],
            },
        },
    },
    "required": ["items"],
}


def _prompt(branches, sheet, head, rows):
    blist = "\n".join(f'- id={b["id"]}: {b["name"]}' + (f' ({b["address"]})' if b["address"] else "")
                      for b in branches)
    return f"""Sen dorixona katalogini tartiblovchi yordamchisan. Quyida Excel varag'idan qatorlar (TAB bilan ajratilgan).
Har bir DORI uchun bitta element qaytar: name (dori nomi, dozasi bilan, ortiqcha belgisiz), price (so'mda butun son; yo'q bo'lsa 0),
unit (quti/dona/ml...; bo'lmasa ""), note (ishlab chiqaruvchi yoki qisqa izoh; bo'lmasa ""),
in_stock (qoldiq/soni 0 yoki "yo'q"/"нет" bo'lsa false, aks holda true), branch_id.

branch_id qanday aniqlanadi — dorixona filiallari:
{blist}
- Qatorda, ustunda, sarlavhada yoki varaq nomida ("{sheet}") filial nomi/manzili ko'rsatilgan bo'lsa — o'sha filial id si
  (nomlar biroz boshqacha, lotin/kirill, qisqartma bo'lishi mumkin — eng mosini tanla).
- Bir qatorda bir nechta filial uchun alohida narx/qoldiq bo'lsa — HAR filial uchun alohida element qaytar.
- Filial umuman ko'rsatilmagan bo'lsa — branch_id = 0 (umumiy katalog, barcha filiallar).
- Filial ko'rsatilgan-u, ro'yxatdagi birortasiga mos kelmasa — branch_id = -1.
Jami/itogo qatorlari, sarlavhalar, bo'sh va dori bo'lmagan qatorlarni tashlab ket. Narxdagi bo'sh joy/vergulni olib tashla.
Javob JSON: {_SCHEMA_TXT}

Varaq: {sheet}
Varaq boshidagi sarlavha qatorlari (faqat kontekst — ulardan element QAYTARMA):
{chr(10).join(head) if head else "(bu varaqning boshi — sarlavha quyidagi qatorlar ichida)"}

Qatorlar:
{chr(10).join(rows)}
"""


async def analyze_catalog_excel(raw: bytes):
    """Excel -> {"items": [...], "truncated", "failed_chunks", "chunks"}.
    Har bir element: name, price, unit, note, in_stock, branch_id (0 — umumiy, -1 — aniqlanmadi)."""
    cfg = await get_config()
    if not cfg:
        raise AIError("AI kaliti kiritilmagan (Sozlamalar → AI)")
    try:
        chunks, truncated = excel_chunks(raw)
    except Exception:
        logger.exception("ai excel read")
        raise AIError("Faylni o'qib bo'lmadi. .xlsx formatida yuklang.")
    if not chunks:
        raise AIError("Faylda ma'lumot topilmadi")
    branches = await q.list_branches()
    valid = {b["id"] for b in branches}
    sem = asyncio.Semaphore(PARALLEL)

    async def run(ch):
        sheet, head, rows = ch
        async with sem:
            res = await generate_json(_prompt(branches, sheet, head, rows), _ITEM_SCHEMA, cfg)
        its = res.get("items") if isinstance(res, dict) else None
        return its if isinstance(its, list) else []

    results = await asyncio.gather(*(run(c) for c in chunks), return_exceptions=True)
    errs = [r for r in results if isinstance(r, Exception)]
    if errs and len(errs) == len(results):
        e = errs[0]
        raise e if isinstance(e, AIError) else AIError("AI tahlili bajarilmadi")
    items = {}   # (nom, filial) -> element; bir faylda takror bo'lsa oxirgisi qoladi
    for res in results:
        if isinstance(res, Exception):
            logger.warning("ai chunk failed: %s", res)
            continue
        for it in res:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()[:200]
            if not name:
                continue
            try:
                price = max(0, int(float(it.get("price") or 0)))
            except (TypeError, ValueError):
                price = 0
            try:
                bid = int(it.get("branch_id") or 0)
            except (TypeError, ValueError):
                bid = 0
            if bid > 0 and bid not in valid:
                bid = -1
            items[(q.norm_name(name), bid)] = {
                "name": name, "price": price, "unit": str(it.get("unit") or "")[:30],
                "note": str(it.get("note") or "")[:300], "in_stock": bool(it.get("in_stock", True)),
                "branch_id": bid}
    return {"items": list(items.values()), "truncated": truncated,
            "failed_chunks": len(errs), "chunks": len(chunks)}
