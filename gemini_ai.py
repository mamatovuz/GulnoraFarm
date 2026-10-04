"""Gemini AI: Excel'dagi dori ro'yxatini tahlil qilib, har bir dorini qaysi filialga qo'shishni aniqlaydi.

API kaliti admin panel → Sozlamalar → «Gemini AI» orqali settings jadvalida saqlanadi (gemini_api_key).
"""
import io
import json
import asyncio
import logging

import aiohttp

from database import queries as q

logger = logging.getLogger("bot")

DEFAULT_MODEL = "gemini-2.5-flash"
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CHUNK_ROWS = 120        # bitta so'rovga nechta Excel qatori
MAX_ROWS = 4000         # bitta fayldan ko'pi bilan
PARALLEL = 3


class AIError(Exception):
    pass


async def get_config():
    key = (await q.get_setting("gemini_api_key", "") or "").strip()
    model = (await q.get_setting("gemini_model", "") or "").strip() or DEFAULT_MODEL
    return key, model


def mask_key(key: str) -> str:
    return (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("…" if key else "")


async def generate_json(prompt: str, schema: dict = None, key: str = None, model: str = None,
                        timeout: int = 120) -> dict:
    """Gemini'ga so'rov — javob JSON (responseSchema bilan majburlanadi)."""
    if not key:
        key, model2 = await get_config()
        model = model or model2
    model = model or DEFAULT_MODEL
    if not key:
        raise AIError("Gemini API kaliti kiritilmagan (Sozlamalar → Gemini AI)")
    gen = {"temperature": 0, "responseMimeType": "application/json"}
    if schema:
        gen["responseSchema"] = schema
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.post(_URL.format(model=model), json=payload,
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"}) as r:
                data = await r.json(content_type=None)
                status = r.status
    except asyncio.TimeoutError:
        raise AIError("Gemini javob bermadi (vaqt tugadi). Keyinroq urinib ko'ring.")
    except aiohttp.ClientError as e:
        raise AIError(f"Gemini bilan aloqa yo'q: {e.__class__.__name__}")
    if status != 200:
        msg = ((data or {}).get("error") or {}).get("message", "") if isinstance(data, dict) else ""
        if status in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or status != 400):
            raise AIError("Gemini API kaliti noto'g'ri yoki ruxsati yo'q")
        if status == 404:
            raise AIError(f"«{model}» modeli topilmadi — Sozlamalarda modelni tekshiring")
        if status == 429:
            raise AIError("Gemini limiti tugadi (429). Birozdan keyin urinib ko'ring.")
        raise AIError(f"Gemini xatosi ({status}): {msg[:160]}")
    try:
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        return json.loads(text)
    except (KeyError, IndexError, TypeError):
        reason = ((data.get("candidates") or [{}])[0].get("finishReason")
                  or (data.get("promptFeedback") or {}).get("blockReason") or "bo'sh javob")
        raise AIError(f"Gemini javobi bo'sh ({reason})")
    except json.JSONDecodeError:
        raise AIError("Gemini javobi JSON emas — qayta urinib ko'ring")


async def test_key(key: str, model: str) -> str:
    r = await generate_json('Reply with JSON {"ok": true}', key=key, model=model, timeout=30)
    return "ok" if isinstance(r, dict) else "?"


# ---------------- Excel -> matn bo'laklari ----------------
def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).replace("\t", " ").replace("\n", " ").strip()


def excel_chunks(raw: bytes):
    """Barcha varaqlar -> [(varaq nomi, sarlavha qatorlari, [qatorlar])] bo'laklari (TSV matn)."""
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
        head = rows[:3]          # sarlavha/izoh qatorlari har bo'lakka kontekst sifatida
        body = rows[3:] if len(rows) > 3 else []
        if not body:
            chunks.append((ws.title, [], head))
            total += len(head)
            continue
        for i in range(0, len(body), CHUNK_ROWS):
            part = body[i:i + CHUNK_ROWS]
            chunks.append((ws.title, head, part))
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

Varaq: {sheet}
Sarlavha qatorlari:
{chr(10).join(head) if head else "(yo'q)"}

Qatorlar:
{chr(10).join(rows)}
"""


async def analyze_catalog_excel(raw: bytes):
    """Excel -> {"items": [...], "truncated": bool}. Har bir element: name, price, unit, note, in_stock, branch_id."""
    key, model = await get_config()
    if not key:
        raise AIError("Gemini API kaliti kiritilmagan (Sozlamalar → Gemini AI)")
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
            res = await generate_json(_prompt(branches, sheet, head, rows), _ITEM_SCHEMA, key, model)
        return res.get("items") or []

    results = await asyncio.gather(*(run(c) for c in chunks), return_exceptions=True)
    errs = [r for r in results if isinstance(r, Exception)]
    if errs and len(errs) == len(results):
        e = errs[0]
        raise e if isinstance(e, AIError) else AIError("Gemini tahlili bajarilmadi")
    items = {}   # (nom, filial) -> element; bir faylda takror bo'lsa oxirgisi qoladi
    for res in results:
        if isinstance(res, Exception):
            logger.warning("ai chunk failed: %s", res)
            continue
        for it in res:
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
