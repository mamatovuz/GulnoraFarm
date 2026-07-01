"""Telegram Mini App (CRM) — operator chat paneli uchun web server (aiohttp).

Bot bilan bitta jarayonda ishlaydi, bitta bazaga ulanadi. Operator mini app'da:
login/parol -> chat ro'yxati -> yozishma -> mijozga yuborish (bot orqali) -> chatni o'chirish.
"""
import os
import json
import hmac
import hashlib
import logging
from urllib.parse import parse_qsl

from aiohttp import web

from config import BOT_TOKEN, WEBAPP_URL
from database import queries as q
import locales as loc

logger = logging.getLogger("bot")
_HTML = os.path.join(os.path.dirname(__file__), "webapp", "operator.html")


# ---------------- Auth: Telegram WebApp initData ----------------
def _check_init(init_data: str, token: str):
    """initData imzosini token bilan tekshiradi. To'g'ri bo'lsa parsed dict qaytaradi."""
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        return None
    got = parsed.pop("hash", None)
    if not got:
        return None
    data_check = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return parsed if hmac.compare_digest(calc, got) else None


async def _all_tokens():
    """Asosiy bot + barcha operator bot tokenlari (mini app istalgan botdan ochilishi mumkin)."""
    tokens = [BOT_TOKEN]
    try:
        for b in await q.list_operator_bots(only_enabled=True):
            if b["token"]:
                tokens.append(b["token"])
    except Exception:
        pass
    return tokens


async def _auth_user(request, body=None):
    """initData'dan (header/body/query) haqiqiy Telegram foydalanuvchisini qaytaradi.
    Imzo to'g'ri bo'lmasa None — bu faqat onlayn bog'lash uchun, majburiy emas."""
    init_data = (request.headers.get("X-Init-Data", "")
                 or (body or {}).get("_init", "")
                 or request.query.get("_init", ""))
    if not init_data:
        return None
    for tok in await _all_tokens():
        parsed = _check_init(init_data, tok)
        if parsed:
            raw = parsed.get("user")
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    return None
    return None


def _sign(operator_id) -> str:
    """Operator sessiya tokeni (login/parol bilan olinadi, server siri bilan imzolanadi)."""
    return hmac.new(BOT_TOKEN.encode(), f"op-session:{operator_id}".encode(),
                    hashlib.sha256).hexdigest()


async def _auth_op(request, data):
    """Operatorni imzolangan token orqali tasdiqlaydi (login/parol bilan olingan)."""
    try:
        operator_id = int(data.get("operator_id"))
    except (TypeError, ValueError):
        return None, None
    token = str(data.get("token", ""))
    if not token or not hmac.compare_digest(_sign(operator_id), token):
        return None, None
    op = await q.get_operator(operator_id)
    if not op or op["status"] != "active":
        return None, None
    return op, None


def _json(data, status=200):
    return web.json_response(data, status=status)


# ---------------- Sahifa ----------------
async def index(request):
    if os.path.exists(_HTML):
        return web.FileResponse(_HTML)
    return web.Response(text="Mini app fayli topilmadi.", status=404)


async def health(request):
    return web.Response(text="ok")


# ---------------- API: login ----------------
async def api_login(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    login = str(body.get("login", "")).strip()
    password = str(body.get("password", "")).strip()
    op = await q.get_operator_by_login(login)
    if not op or op["password_hash"] != q.hash_password(password):
        return _json({"ok": False, "error": "Login yoki parol xato"}, 200)
    if op["status"] != "active":
        return _json({"ok": False, "error": "Hisob bloklangan"}, 200)
    # Telegram foydalanuvchisini (imzo to'g'ri bo'lsa) operatorga bog'laymiz — online bo'ladi
    user = await _auth_user(request, body)
    if user:
        try:
            await q.login_operator(op["id"], user["id"])
        except Exception:
            pass
    return _json({"ok": True, "operator_id": op["id"], "name": op["name"],
                  "token": _sign(op["id"])})


# ---------------- API: chatlar ----------------
def _ct_label(ct):
    return {"photo": "📷 rasm", "video": "🎥 video", "document": "📄 hujjat", "voice": "🎤 ovoz",
            "sticker": "🎭 stiker", "animation": "🎞 GIF", "location": "📍 lokatsiya"}.get(ct, "📎 media")


async def api_chats(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    rows = await q.op_chats(op["id"])
    chats = []
    for r in rows:
        preview = r["last_text"] or (_ct_label(r["last_ct"]) if r["last_ct"] else "")
        chats.append({
            "order_id": r["id"],
            "name": r["full_name"] or "—",
            "phone": r["phone"] or "",
            "status": r["status"],
            "incoming": r["status"] == "new",
            "mine": r["operator_id"] == op["id"],
            "preview": (preview or "")[:60],
            "time": (r["last_at"] or r["created_at"] or "")[11:16],
        })
    return _json({"ok": True, "chats": chats})


# ---------------- API: yozishma ----------------
async def api_messages(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(request.query.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "not found"}, 404)
    user = await q.get_user(order["user_id"])
    msgs = await q.order_messages(order_id)
    out = []
    for m in msgs:
        out.append({
            "sender": m["sender"],
            "text": m["text"] or _ct_label(m["content_type"]),
            "time": (m["created_at"] or "")[11:16],
        })
    return _json({"ok": True, "order_id": order_id, "status": order["status"],
                  "client": {"name": user["full_name"] if user else "—",
                             "phone": user["phone"] if user else ""},
                  "messages": out})


# ---------------- API: yuborish ----------------
async def api_send(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, user = await _auth_op(request, body)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    text = str(body.get("text", "")).strip()
    if not text:
        return _json({"ok": False, "error": "empty"}, 400)
    order = await q.get_order(order_id)
    if not order or order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "yopilgan"}, 200)

    # yangi bo'lsa — avval qabul qilamiz (o'zimizga biriktiramiz)
    if order["status"] == "new" and not order["operator_id"]:
        if await q.claim_order(order_id, op["id"]):
            await q.set_operator_availability(op["id"], "busy")
    await q.set_operator_active_order(op["id"], order_id)

    from utils import cbot, post_operator_to_channel
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"}, 200)
    await q.add_message(order_id, "operator", "text", text, None, None)
    clang = await q.get_lang(order["user_id"])
    try:
        await client.send_message(order["user_id"],
                                  loc.t("operator_reply", clang, name=op["name"], text=text))
    except Exception:
        return _json({"ok": False, "error": "mijozga yuborilmadi (bloklagan bo'lishi mumkin)"}, 200)
    try:
        await post_operator_to_channel(client, order, op["name"], text=text)
    except Exception:
        pass
    return _json({"ok": True})


# ---------------- API: qabul qilish ----------------
async def api_accept(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    from utils import cbot
    from handlers.operator import do_accept
    ok, err = await do_accept(cbot(), op, order_id, op["telegram_id"] or 0)
    return _json({"ok": ok, "error": err})


# ---------------- API: yakunlash ----------------
async def api_close(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    from utils import cbot
    from handlers.operator import _finish_with_rating
    await _finish_with_rating(cbot(), order_id, f"operator:{op['id']}")
    return _json({"ok": True})


# ---------------- API: chatni o'chirish (yashirish) ----------------
async def api_hide(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    await q.hide_chat(op["id"], order_id)
    return _json({"ok": True})


# ---------------- Server ----------------
def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/operator", index)
    app.router.add_get("/health", health)
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/chats", api_chats)
    app.router.add_get("/api/messages", api_messages)
    app.router.add_post("/api/send", api_send)
    app.router.add_post("/api/accept", api_accept)
    app.router.add_post("/api/close", api_close)
    app.router.add_post("/api/hide", api_hide)
    return app


async def start(port: int):
    runner = web.AppRunner(build_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🖥 Mini app server: 0.0.0.0:%s  (URL: %s)", port, WEBAPP_URL or "— sozlanmagan")
