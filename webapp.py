"""Telegram Mini App (CRM) — operator chat paneli uchun web server (aiohttp).

Bot bilan bitta jarayonda ishlaydi, bitta bazaga ulanadi. Operator mini app'da:
login/parol -> chat ro'yxati -> yozishma -> mijozga yuborish (bot orqali) -> chatni o'chirish.
"""
import os
import html as _htm
import json
import time
import hmac
import base64
import hashlib
import asyncio
import logging
import mimetypes
from datetime import timedelta
from urllib.parse import parse_qsl, quote

from aiohttp import web
from aiogram.types import BufferedInputFile

from config import BOT_TOKEN, WEBAPP_URL, AVATAR_DIR, MEDIA_CACHE, ADMIN_IDS, now_local
from database import queries as q
from utils import BILL_TAG, send_branch_to_client, branch_card_text, op_client_name
import locales as loc

logger = logging.getLogger("bot")
_HTML = os.path.join(os.path.dirname(__file__), "webapp", "operator.html")
_ADMIN_HTML = os.path.join(os.path.dirname(__file__), "webapp", "admin.html")
_VIEW_HTML = os.path.join(os.path.dirname(__file__), "webapp", "view.html")


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


def _hm(msg: str) -> str:
    return hmac.new(BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()


_OP_TTL = 14 * 86400          # operator sessiyasi: 14 kun (faol bo'lsa avtomatik yangilanadi)
_ADM_TTL = 7 * 86400          # admin sessiyasi: 7 kun (har ochilishda initData bilan yangilanadi)


def _op_epoch(op) -> int:
    try:
        return int(op["sess_epoch"] or 0)
    except (IndexError, KeyError, TypeError, ValueError):
        return 0


def _sign(operator_id, password_hash="", epoch=0, exp=None) -> str:
    """Operator sessiya tokeni: muddati bor (exp), parol xeshi va sessiya davriga (epoch) bog'langan.
    Parol o'zgarsa yoki admin «sessiyalarni bekor qilish»ni bossa — eski tokenlar ishlamaydi."""
    exp = int(exp or (time.time() + _OP_TTL))
    return f"v2.{exp}.{_hm(f'op2:{operator_id}:{password_hash}:{epoch}:{exp}')}"


def _op_token_exp(op, token: str):
    """Token to'g'ri bo'lsa uning tugash vaqtini (exp), aks holda None qaytaradi."""
    try:
        ver, exp_s, sig = str(token).split(".", 2)
        exp = int(exp_s)
    except (ValueError, AttributeError):
        return None
    if ver != "v2" or exp < time.time():
        return None
    good = _sign(op["id"], op["password_hash"] or "", _op_epoch(op), exp)
    return exp if hmac.compare_digest(good, str(token)) else None


def _fresh_op_token(op, token):
    """Sessiya tugashiga 7 kundan kam qolsa — yangi token beradi (sliding session)."""
    exp = _op_token_exp(op, token)
    if exp and exp - time.time() < 7 * 86400:
        return _sign(op["id"], op["password_hash"] or "", _op_epoch(op))
    return None


# ---- Media kaliti: rasm/ovoz URL'larida sessiya tokeni o'rniga qisqa muddatli imzo ----
def _media_key() -> str:
    exp = (int(time.time()) // 3600 + 25) * 3600   # ~1 kun, soat boshiga yaxlitlangan (kesh uchun)
    return f"{exp}.{_hm(f'media:{exp}')[:40]}"


def _check_media_key(mk: str) -> bool:
    try:
        exp_s, sig = str(mk).split(".", 1)
        exp = int(exp_s)
    except (ValueError, AttributeError):
        return False
    return exp > time.time() and hmac.compare_digest(_hm(f"media:{exp}")[:40], sig)


# ---- Login urinishlarini cheklash (parolni tanlab topishdan himoya) ----
_RL: dict = {}
_RL_WINDOW = 600      # 10 daqiqa
_RL_BLOCK = 600


def _client_ip(request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() if xff else "") or (request.remote or "?")


def _rl_left(key) -> int:
    rec = _RL.get(key)
    if rec and rec[2] > time.time():
        return int(rec[2] - time.time())
    return 0


def _rl_fail(key, limit):
    t = time.time()
    rec = _RL.get(key)
    if not rec or t - rec[1] > _RL_WINDOW:
        rec = [0, t, 0]
    rec[0] += 1
    if rec[0] >= limit:
        rec[2] = t + _RL_BLOCK
        rec[0] = 0
        rec[1] = t
    _RL[key] = rec
    if len(_RL) > 5000:          # xotira to'lib ketmasin
        for k in [k for k, v in _RL.items() if v[2] < t and t - v[1] > _RL_WINDOW][:2500]:
            _RL.pop(k, None)


async def _auth_op(request, data):
    """Operatorni imzolangan token orqali tasdiqlaydi (login/parol bilan olingan)."""
    try:
        operator_id = int(data.get("operator_id"))
    except (TypeError, ValueError):
        return None, None
    token = str(data.get("token", ""))
    if not token:
        return None, None
    op = await q.get_operator(operator_id)
    if not op or op["status"] != "active":
        return None, None
    if not _op_token_exp(op, token):
        return None, None
    # Ish vaqti tekshiruvi: vaqt tugagach mini app sessiyasi ham yopiladi
    try:
        from utils import operator_in_hours
        within, _ws, _we = operator_in_hours(op)
        if not within:
            return None, None
    except Exception:
        pass
    return op, None


async def _operator_order(op, order_id, *, allow_unassigned_new=False, claim_unassigned=False,
                          allow_shared=False):
    """Operatorning murojaatga kirish huquqini bitta joyda tekshiradi.

    O'ziga biriktirilgan murojaat doim ruxsat etiladi. Hali hech kim olmagan yangi
    murojaatni faqat aniq ruxsat berilgan oqimlar ko'rishi yoki atomar qabul qilishi
    mumkin. ``allow_shared`` faqat Umumiy bo'limdagi biriktirilgan, jarayondagi
    chatni ko'rish/javoblash oqimida ishlatiladi; chat egasi o'zgarmaydi.
    """
    order = await q.get_order(order_id)
    if not order:
        return None, _json({"ok": False, "error": "Murojaat topilmadi"}, 404)
    if order["operator_id"] == op["id"]:
        return order, None
    if (allow_shared and order["status"] == "in_progress" and order["operator_id"]):
        return order, None
    if (allow_unassigned_new and order["status"] == "new" and not order["operator_id"]):
        if claim_unassigned:
            if not await q.claim_order(order_id, op["id"]):
                order = await q.get_order(order_id)
                if not order or order["operator_id"] != op["id"]:
                    return None, _json({"ok": False, "error": "Murojaatni boshqa operator qabul qildi"}, 409)
            else:
                order = await q.get_order(order_id)
            await q.set_operator_active_order(op["id"], order_id)
            await q.set_operator_availability(op["id"], "busy")
        return order, None
    return None, _json({"ok": False, "error": "Bu sizning suhbatingiz emas"}, 403)


def _json(data, status=200):
    return web.json_response(data, status=status)


# ---------------- Sahifa ----------------
_STATIC = os.path.join(os.path.dirname(__file__), "webapp", "static")
_NOCACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}


def _assets_version() -> str:
    """CSS/JS fayllar o'zgarganda yangilanadigan versiya — Telegram eski keshni ishlatmasin."""
    mt = 0
    for root in (_STATIC, os.path.dirname(_HTML)):
        try:
            for n in os.listdir(root):
                mt = max(mt, int(os.path.getmtime(os.path.join(root, n))))
        except OSError:
            pass
    return str(mt)


def _page(path):
    if not os.path.exists(path):
        return web.Response(text="Mini app fayli topilmadi.", status=404)
    with open(path, encoding="utf-8") as fh:
        html = fh.read().replace("{{V}}", _assets_version())
    return web.Response(text=html, content_type="text/html", headers=_NOCACHE)


async def index(request):
    # Kesh o'chirilgan: har ochilganda eng yangi dizayn yuklanadi
    return _page(_HTML)


async def static_file(request):
    name = os.path.basename(request.match_info.get("name", ""))
    path = os.path.join(_STATIC, name)
    if not name or not os.path.isfile(path):
        return web.Response(status=404)
    ctype = {"js": "application/javascript", "css": "text/css"}.get(name.rsplit(".", 1)[-1],
                                                                   mimetypes.guess_type(name)[0] or "application/octet-stream")
    return web.FileResponse(path, headers={"Content-Type": ctype + "; charset=utf-8" if "/" in ctype and ctype.startswith(("application/javascript", "text/")) else ctype,
                                           "Cache-Control": "public, max-age=31536000, immutable"
                                           if request.query.get("v") else "no-cache"})


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
    ip_key, lg_key = "ip:" + _client_ip(request), "login:" + login.lower()
    left = max(_rl_left(ip_key), _rl_left(lg_key))
    if left:
        return _json({"ok": False, "error": f"Juda ko'p noto'g'ri urinish. "
                                            f"{max(1, left // 60)} daqiqadan keyin qayta urining."}, 200)
    op = await q.get_operator_by_login(login)
    if not op or not q.verify_password(password, op["password_hash"]):
        _rl_fail(ip_key, 15)
        _rl_fail(lg_key, 5)
        await q.audit(f"ip:{_client_ip(request)}", "login_fail", None, {"login": login[:40]})
        return _json({"ok": False, "error": "Login yoki parol xato"}, 200)
    _RL.pop(lg_key, None)
    if op["status"] != "active":
        return _json({"ok": False, "error": "Hisob bloklangan"}, 200)
    # Eski sha256 xeshni pbkdf2 ga jimgina yangilaymiz
    if q.password_needs_upgrade(op["password_hash"]):
        await q.set_password_hash_raw(op["id"], q.hash_password(password))
        op = await q.get_operator(op["id"])
    # Ish vaqtidan tashqarida mini appga kirib bo'lmaydi
    from utils import operator_in_hours
    within, ws, we = operator_in_hours(op)
    if not within:
        return _json({"ok": False, "error": f"Hozir ish vaqtingiz emas.\n"
                                            f"Ish vaqtingiz: {ws}–{we}. "
                                            f"Faqat shu oraliqda kira olasiz."}, 200)
    # Telegram foydalanuvchisini (imzo to'g'ri bo'lsa) operatorga bog'laymiz — online bo'ladi
    user = await _auth_user(request, body)
    if user:
        try:
            await q.login_operator(op["id"], user["id"])
        except Exception:
            pass
    return _json({"ok": True, "operator_id": op["id"], "name": op["name"],
                  "token": _sign(op["id"], op["password_hash"] or "", _op_epoch(op)),
                  "mk": _media_key()})


# ---------------- API: chatlar ----------------
def _ct_label(ct):
    return {"photo": "📷 rasm", "video": "🎥 video", "document": "📄 hujjat", "voice": "🎤 ovoz",
            "sticker": "🎭 stiker", "animation": "🎞 GIF", "location": "📍 lokatsiya"}.get(ct, "📎 media")


def _short_time(ts: str) -> str:
    """Chat ro'yxati uchun Telegramdek vaqt: bugun -> 14:05, shu hafta -> Du, eski -> 12.09.24."""
    if not ts:
        return ""
    try:
        from datetime import datetime as _dt
        from config import now_local
        d = _dt.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
        n = now_local().replace(tzinfo=None)
        if d.date() == n.date():
            return ts[11:16]
        days = (n.date() - d.date()).days
        if 0 < days < 7:
            return ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"][d.weekday()]
        return d.strftime("%d.%m.%y")
    except Exception:
        return ts[11:16]


def _chat_json(r, op_id):
    preview = r["last_text"] or (_ct_label(r["last_ct"]) if r["last_ct"] else "")
    keys = r.keys()
    return {
        "order_id": r["id"],
        "name": r["full_name"] or "—",
        "phone": r["phone"] or "",
        "branch": (r["branch"] or "") if "branch" in keys else "",
        "status": r["status"],
        "mine": r["operator_id"] == op_id,
        "reply": r["last_sender"] == "client",   # javob kutyapti
        "last_sender": r["last_sender"] or "",
        "last_mid": r["last_mid"] or 0,
        "unread": r["unread"] or 0,
        "marked_unread": bool(r["marked_unread"]) if "marked_unread" in keys else False,
        "pinned": bool(r["pinned"]) if "pinned" in keys else False,
        "archived": bool(r["archived"]) if "archived" in keys else False,
        "draft": (r["draft"] or "") if "draft" in keys else "",
        "tags": [t for t in (r["tags"] or "").split(",") if t] if "tags" in keys else [],
        "paused": bool(r["paused_at"]) if "paused_at" in keys else False,
        "rejected": bool(r["rejected_at"]) if "rejected_at" in keys else False,
        "paused_until": (r["paused_until"] or "") if "paused_until" in keys else "",
        "auto_close_at": (r["auto_close_at"] or "") if "auto_close_at" in keys else "",
        "operator_name": (r["operator_name"] or "") if "operator_name" in keys else "",
        "preview": (preview or "")[:90],
        "time": _short_time(r["last_at"] or r["created_at"] or ""),
        "ts": r["last_at"] or r["created_at"] or "",
    }


async def _chat_list(op):
    return [_chat_json(r, op["id"]) for r in await q.op_chats(op["id"])]


async def _general_chat_list(op):
    return [_chat_json(r, op["id"]) for r in await q.op_general_chats(op["id"])]


async def api_chats(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    return _json({"ok": True, "chats": await _chat_list(op)})


async def api_general_chats(request):
    """Umumiy navbat: barcha operatorlarning jarayondagi murojaatlari."""
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    return _json({"ok": True, "chats": await _general_chat_list(op)})


async def api_done_chats(request):
    """Yakunlangan / bekor qilingan suhbatlar (papka: «Yakunlangan»)."""
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    kind = request.query.get("kind") or "done"
    if kind not in ("done", "canceled", "rejected"):
        kind = "done"
    out = []
    for r in await q.op_done_chats(op["id"], kind=kind):
        prev = r["last_text"] or (_ct_label(r["last_ct"]) if r["last_ct"] else "")
        out.append({"order_id": r["id"], "name": r["full_name"] or r["phone"] or "Mijoz",
                    "phone": r["phone"] or "", "status": r["status"], "rating": r["rating"] or 0,
                    "last_sender": r["last_sender"] or "",
                    "rejected": bool(r["rejected_at"]),
                    "tags": [t for t in (r["tags"] or "").split(",") if t],
                    "preview": prev[:90], "time": _short_time(r["closed_at"] or r["created_at"] or "")})
    return _json({"ok": True, "chats": out})


# ---------------- API: yozishma ----------------
def _msg_json(m):
    keys = m.keys()
    g = (lambda k: m[k] if k in keys else None)
    return {
        "mid": m["id"],
        "sender": m["sender"],
        "own": m["sender"] == "operator",
        "type": m["content_type"] or "text",
        "text": m["text"] or "",
        "html": g("html") or "",
        "file_id": m["file_id"] or "",
        "file_name": m["file_name"] or "",
        "mime_type": m["mime_type"] or "",
        "size": g("file_size") or 0,
        "tgid": m["tg_msg_id"] or 0,         # reply (iqtibos) uchun — mijoz xabari IDsi
        "cmid": m["client_msg_id"] or 0,     # mijoz chatidagi ID — o'chirish/tahrirlash mumkin
        "reply_to": g("reply_to_mid") or 0,
        "edited": bool(g("edited_at")),
        "ts": m["created_at"] or "",
        "time": (m["created_at"] or "")[11:16],
    }


async def _msgs_with_replies(rows):
    """Xabarlar + ular javob bergan (iqtibos) xabarlarning qisqa ko'rinishi."""
    out = [_msg_json(m) for m in rows]
    ids = {o["reply_to"] for o in out if o["reply_to"]}
    have = {o["mid"] for o in out}
    need = [i for i in ids if i not in have]
    refs = {r["id"]: r for r in await q.messages_by_ids(need)} if need else {}
    for o in out:
        rid = o["reply_to"]
        if rid and rid in refs:
            r = refs[rid]
            o["reply"] = {"mid": rid, "own": r["sender"] == "operator",
                          "type": r["content_type"] or "text", "text": (r["text"] or "")[:120]}
    return out


def _note_json(n):
    return {"id": n["id"], "kind": n["author_kind"], "author": n["author_name"] or "",
            "text": n["text"] or "", "ts": n["created_at"] or "",
            "time": (n["created_at"] or "")[11:16]}


async def _chat_meta(order, user):
    pinned = None
    pm = order["pinned_mid"] if "pinned_mid" in order.keys() else None
    if pm:
        r = await q.get_message(pm)
        if r:
            pinned = _msg_json(r)
    uname = user["username"] if user and "username" in user.keys() else ""
    # Murojaat filiali (operator/mijoz tanlagan), bo'lmasa mijozning asosiy filiali
    bid = order["branch_id"] or (user["branch_id"] if user else None)
    br = await q.get_branch(bid) if bid else None
    import webapp_extra
    owner = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    return {
        "rejected": bool(order["rejected_at"]) if "rejected_at" in order.keys() else False,
        "pause": webapp_extra.pause_json(order, await q.order_pauses(order["id"])),
        "order_id": order["id"], "status": order["status"],
        "operator_id": order["operator_id"] or 0,
        "operator_name": (owner["name"] if owner else "") or "",
        "auto_close_at": (order["auto_close_at"] or "") if "auto_close_at" in order.keys() else "",
        "fulfillment": order["fulfillment"] or "",
        "tags": [t for t in ((order["tags"] if "tags" in order.keys() else "") or "").split(",") if t],
        "pinned": pinned,
        "notes": [_note_json(n) for n in await q.internal_notes(order["id"])],
        "client": {"name": user["full_name"] if user else "—",
                   "phone": user["phone"] if user else "",
                   "username": uname or "",
                   "branch": br["name"] if br else "",
                   "branch_id": br["id"] if br else 0},
    }


async def api_messages(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(request.query.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    shared = bool(request.query.get("shared"))
    order, denied = await _operator_order(op, order_id, allow_unassigned_new=not shared,
                                          allow_shared=shared)
    if denied is not None:
        return denied
    user = await q.get_user(order["user_id"])
    try:
        before = int(request.query.get("before") or 0) or None
    except ValueError:
        before = None
    limit = 5000 if request.query.get("all") else 60
    rows = await q.order_messages_page(order_id, before, limit + 1)
    has_more = len(rows) > limit
    rows = rows[-limit:]
    st = await q.chat_state(op["id"], order_id)
    last_read = (st["last_read_mid"] if st else None)
    if last_read is None:
        # holat yozuvi yo'q — oxirgi operator xabarigacha o'qilgan deb hisoblaymiz
        last_read = max([m["id"] for m in rows if m["sender"] == "operator"] or [0])
    if request.query.get("mark") and (order["operator_id"] == op["id"] or shared):
        await q.mark_read(op["id"], order_id)
    meta = await _chat_meta(order, user)
    meta.update({"ok": True, "messages": await _msgs_with_replies(rows), "has_more": has_more,
                 "last_read_mid": last_read or 0, "draft": (st["draft"] if st else "") or "",
                 "server_ts": q.now()})
    return _json(meta)


async def api_sync(request):
    """Long-poll: o'zgarish bo'lmasa 20 soniyagacha kutadi, bo'lsa darhol javob beradi.
    Bitta so'rov: chatlar ro'yxati + yangi murojaatlar soni + ochiq chatdagi yangi/tahrirlangan xabarlar."""
    qd = request.query
    op, _ = await _auth_op(request, qd)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        v = int(qd.get("v") or 0)
    except ValueError:
        v = 0
    if v and v == q.change_ver():
        await q.wait_change(v, 20)
    ver = q.change_ver()
    res = {"ok": True, "v": ver, "server_ts": q.now(), "newcount": await q.new_count(),
           "notify_unread": await q.operator_notifications_unread(op["id"]),
           "operator_unread": sum(int(r["unread"] or 0) for r in await q.operator_peers(op["id"])),
           "chats": await _chat_list(op), "general_chats": await _general_chat_list(op),
           "mk": _media_key()}
    tok = _fresh_op_token(op, qd.get("token", ""))
    if tok:
        res["token"] = tok
    try:
        oid = int(qd.get("order_id") or 0)
    except ValueError:
        oid = 0
    if oid:
        shared = bool(qd.get("shared"))
        order, denied = await _operator_order(op, oid, allow_unassigned_new=not shared,
                                              allow_shared=shared)
        if denied is not None:
            res["chat_error"] = "Bu suhbat boshqa operatorga o'tkazilgan"
        elif order:
            try:
                after = int(qd.get("after") or 0)
            except ValueError:
                after = 0
            rows = await q.order_messages_delta(oid, after, qd.get("since") or "")
            if qd.get("mark") and (order["operator_id"] == op["id"] or shared):
                await q.mark_read(op["id"], oid)
            user = await q.get_user(order["user_id"])
            chat = await _chat_meta(order, user)
            chat["messages"] = await _msgs_with_replies(rows)
            res["chat"] = chat
    return _json(res)


# ---------------- API: mini-app bildirishnomalari ----------------
async def api_notifications(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.operator_notifications(op["id"])
    return _json({"ok": True, "items": [
        {"id": r["id"], "kind": r["kind"] or "info", "title": r["title"] or "",
         "body": r["body"] or "", "order_id": r["order_id"] or 0,
         "created_at": r["created_at"] or "", "read": bool(r["read_at"])} for r in rows]})


async def api_notifications_read(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        nid = int(body.get("id") or 0) or None
    except (TypeError, ValueError):
        nid = None
    await q.mark_operator_notifications_read(op["id"], nid)
    return _json({"ok": True})


# ---------------- API: operatorlararo ichki chat ----------------
async def api_operator_peers(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.operator_peers(op["id"])
    return _json({"ok": True, "operators": [
        {"id": r["id"], "name": r["name"] or "Operator",
         "availability": r["availability"] or "free", "last_active": r["last_active"] or "",
         "open_count": r["open_count"] or 0,
         "last_text": r["last_text"] or "", "last_at": r["last_at"] or "",
         "unread": r["unread"] or 0} for r in rows]})


async def api_operator_messages(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    try:
        peer_id = int(request.query.get("peer_id"))
        after = max(0, int(request.query.get("after") or 0))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "peer_id"}, 400)
    peer = await q.get_operator(peer_id)
    if not peer or peer["status"] != "active" or peer_id == op["id"]:
        return _json({"ok": False, "error": "Operator topilmadi"}, 404)
    rows = await q.operator_messages_between(op["id"], peer_id, after)
    await q.mark_operator_messages_read(op["id"], peer_id)
    return _json({"ok": True, "operator": {"id": peer["id"], "name": peer["name"] or "Operator",
                                             "availability": peer["availability"] or "free"},
                  "messages": [{"id": r["id"], "own": r["from_operator_id"] == op["id"],
                                "from_name": r["from_name"] or "Operator", "text": r["text"] or "",
                                "created_at": r["created_at"] or "", "read": bool(r["read_at"])}
                               for r in rows]})


async def api_operator_send(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        peer_id = int(body.get("peer_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "peer_id"}, 400)
    text = str(body.get("text") or "").strip()[:4000]
    peer = await q.get_operator(peer_id)
    if not text:
        return _json({"ok": False, "error": "Xabar bo'sh"}, 400)
    if not peer or peer["status"] != "active" or peer_id == op["id"]:
        return _json({"ok": False, "error": "Operator topilmadi"}, 404)
    mid = await q.add_operator_message(op["id"], peer_id, text)
    await q.add_operator_notification(peer_id, "operator_message", f"{op['name']}dan yangi xabar",
                                      text[:240], None, f"operator-message:{mid}")
    # Mini-app yopiq bo'lsa ham operator xabarni Telegram botida ko'radi.
    if peer["telegram_id"]:
        try:
            import botreg
            from utils import cbot
            ob = (botreg.get_operator_bot(peer["bot_id"]) if peer["bot_id"] else None) or cbot()
            if ob:
                await ob.send_message(peer["telegram_id"],
                                      f"💬 <b>{_htm.escape(op['name'] or 'Operator')}</b>\n{_htm.escape(text)}")
        except Exception:
            pass
    return _json({"ok": True, "id": mid, "created_at": q.now()})


async def api_media_key(request):
    op, _ = await _auth_op(request, request.query)
    if not op and not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    return _json({"ok": True, "mk": _media_key()})


# ---------------- API: media (rasm/ovoz/hujjat) ko'rsatish ----------------
def _safe_file_name(value):
    """Content-Disposition uchun yo'l va boshqaruv belgilarisiz fayl nomi."""
    name = os.path.basename(str(value or "").replace("\\", "/")).strip()
    name = "".join(ch for ch in name if ch >= " " and ch not in "\r\n")
    return name[:180]


def _file_response_meta(kind, raw, file_name="", mime_type="", remote_path=""):
    """Fayl baytlari/nomidan brauzerga to'g'ri MIME va yuklash nomini beradi."""
    name = _safe_file_name(file_name) or _safe_file_name(remote_path)
    supplied = str(mime_type or "").split(";", 1)[0].strip().lower()
    if ("/" not in supplied
            or any(not (ch.isascii() and (ch.isalnum() or ch in "!#$&^_.+-/"))
                   for ch in supplied)):
        supplied = ""

    # Telegram eski yozuvlarda MIME/nomni saqlamagan bo'lishi mumkin. Muhim
    # formatlarni magic bytes orqali aniqlaymiz, shunda eski PDF ham ochiladi.
    if raw.startswith(b"%PDF-"):
        ctype = "application/pdf"
        if not name.lower().endswith(".pdf"):
            name = (name or "document") + ".pdf"
    elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
        ctype = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        ctype = "image/jpeg"
    elif raw[:6] in (b"GIF87a", b"GIF89a"):
        ctype = "image/gif"
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        ctype = "image/webp"
    elif supplied and supplied != "application/octet-stream":
        ctype = supplied
    else:
        guessed = mimetypes.guess_type(name)[0] if name else None
        ctype = guessed or {
            "voice": "audio/ogg", "audio": "audio/ogg", "video": "video/mp4",
            "sticker": "image/webp", "photo": "image/jpeg",
        }.get(kind, "application/octet-stream")

    if not name:
        ext = mimetypes.guess_extension(ctype) or ""
        name = "document" + (".pdf" if ctype == "application/pdf" else ext)
    return ctype, name


def _media_response(raw, kind, file_name="", mime_type="", remote_path=""):
    ctype, name = _file_response_meta(kind, raw, file_name, mime_type, remote_path)
    headers = {"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"}
    if kind == "document":
        # PDF brauzer/WebView ichida ochiladi; qolgan hujjatlar o'z nomi bilan yuklanadi.
        disposition = "inline" if ctype == "application/pdf" else "attachment"
        fallback = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "._- ") else "_"
                           for ch in name) or "document"
        headers["Content-Disposition"] = (
            f'{disposition}; filename="{fallback}"; filename*=UTF-8\'\'{quote(name, safe="")}'
        )
    return web.Response(body=raw, content_type=ctype, headers=headers)


async def api_file(request):
    # URL'da sessiya tokeni emas, qisqa muddatli media kaliti (mk) bo'ladi
    if not _check_media_key(request.query.get("mk", "")):
        op, _ = await _auth_op(request, request.query)
        if not op and not await _auth_admin(request, request.query):
            return web.Response(status=401, text="auth")
    fid = request.query.get("fid", "")
    kind = request.query.get("kind", "")
    if not fid:
        return web.Response(status=400)
    file_name = request.query.get("name", "")
    mime_type = request.query.get("mime", "")
    if kind == "document" and (not file_name or not mime_type):
        try:
            meta = await q.file_meta(fid)
            if meta:
                file_name = file_name or (meta["file_name"] or "")
                mime_type = mime_type or (meta["mime_type"] or "")
        except Exception:
            pass
    cache_path = os.path.join(MEDIA_CACHE, hashlib.sha256(fid.encode()).hexdigest())
    # 1) Keshdan (Telegram'ga qayta so'rov yubormaymiz — egress tejaladi)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as fh:
                return _media_response(fh.read(), kind, file_name, mime_type)
        except Exception:
            pass
    # 2) Telegram'dan bir marta yuklab, keshga saqlaymiz.
    # file_id asosiy botniki ham, operator botiniki ham bo'lishi mumkin — hammasini sinaymiz
    from utils import cbot
    import botreg
    candidates = [b for b in ([cbot()] + list(botreg.all_operator_bots().values())) if b]
    if not candidates:
        return web.Response(status=503)
    raw = None
    remote_path = ""
    for b in candidates:
        try:
            f = await b.get_file(fid)
            buf = await b.download_file(f.file_path)
            raw = buf.read()
            remote_path = f.file_path or ""
            break
        except Exception:
            continue
    if raw is None:
        return web.Response(status=404, text="not found")
    try:
        os.makedirs(MEDIA_CACHE, exist_ok=True)
        with open(cache_path, "wb") as fh:
            fh.write(raw)
    except Exception:
        pass
    return _media_response(raw, kind, file_name, mime_type, remote_path)


# ---------------- API: yuborish ----------------
async def _template_vars(order, op):
    """Shablon o'zgaruvchilari: {ism} {telefon} {filial} {operator}."""
    user = await q.get_user(order["user_id"])
    branch = ""
    try:
        bid = order["branch_id"] or (user["branch_id"] if user else None)
        if bid:
            b = await q.get_branch(bid)
            branch = b["name"] if b else ""
    except Exception:
        pass
    return {"{ism}": (user["full_name"] if user else "") or "",
            "{telefon}": (user["phone"] if user else "") or "",
            "{filial}": branch, "{operator}": op_client_name(op)}


async def _prepare_text(body, order, op):
    """Kiruvchi matn/HTML -> (oddiy matn, xavfsiz Telegram-HTML yoki None)."""
    import tghtml
    raw_html = str(body.get("html") or "").strip()
    text = str(body.get("text") or "").strip()
    markup = bool(raw_html) or "<" in text
    src = raw_html or (text if markup else _htm.escape(text, quote=False))
    if "{" in src:
        for k, v in (await _template_vars(order, op)).items():
            src = src.replace(k, _htm.escape(v, quote=False))
    clean = tghtml.sanitize(src) if markup else src
    plain = tghtml.to_plain(clean).strip()
    return plain, (clean if tghtml.has_markup(clean) else None)


async def _send_html(coro_html, coro_plain):
    """Avval HTML bilan yuboradi; Telegram formatlashni qabul qilmasa — oddiy matn bilan."""
    from aiogram.exceptions import TelegramBadRequest
    try:
        return await coro_html()
    except TelegramBadRequest as e:
        if "parse" in str(e).lower() or "entit" in str(e).lower() or "tag" in str(e).lower():
            return await coro_plain()
        raise


async def _reply_kwargs(body, order_id):
    """Reply (iqtibos): bazadagi xabar ID si (reply_mid) yoki mijoz xabarining Telegram ID si."""
    rtg = 0
    reply_mid = None
    try:
        rm = int(body.get("reply_mid") or 0)
    except (TypeError, ValueError):
        rm = 0
    if rm:
        row = await q.get_message(rm)
        if row and row["order_id"] == order_id:
            reply_mid = rm
            rtg = (row["tg_msg_id"] if row["sender"] == "client" else row["client_msg_id"]) or 0
    if not rtg:
        try:
            rtg = int(body.get("reply_tgid") or 0)
        except (TypeError, ValueError):
            rtg = 0
        if rtg and not reply_mid:
            reply_mid = await q.find_order_message(order_id, tg_msg_id=rtg)
    kw = {"reply_to_message_id": rtg, "allow_sending_without_reply": True} if rtg else {}
    return kw, reply_mid


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
    media_kind = body.get("media_kind")          # 'photo' | 'voice' | 'document' | None
    media_data = body.get("media_data")          # base64 (dataURL bo'lishi mumkin)
    shared = bool(body.get("shared"))
    order, denied = await _operator_order(
        op, order_id, allow_unassigned_new=not shared, claim_unassigned=not shared,
        allow_shared=shared)
    if denied is not None:
        return denied
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"}, 200)
    # Umumiy bo'limdan yozilganda mijoz chat egasi bo'lgan operator nomini
    # ko'radi. Haqiqiy javob bergan operator audit jurnalida saqlanadi.
    send_op = op
    if shared and order["operator_id"] != op["id"]:
        send_op = await q.get_operator(order["operator_id"]) or op
    text, html_text = await _prepare_text(body, order, send_op)
    if not text and not (media_kind and media_data):
        return _json({"ok": False, "error": "empty"}, 400)

    # yangi bo'lsa — avval qabul qilamiz (o'zimizga biriktiramiz)
    if order["operator_id"] == op["id"]:
        await q.set_operator_active_order(op["id"], order_id)

    from utils import cbot, post_operator_to_channel
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"}, 200)
    uid = order["user_id"]
    clang = await q.get_lang(uid)
    rkw, reply_mid = await _reply_kwargs(body, order_id)
    body_html = html_text or _htm.escape(text, quote=False)
    mid = None
    try:
        if media_kind and media_data:
            raw = base64.b64decode(str(media_data).split(",")[-1])
            cap_h = f"👨‍⚕️ {_htm.escape(send_op['name'])}" + (f": {body_html}" if text else "")
            cap_p = f"👨‍⚕️ {_htm.escape(send_op['name'])}" + (f": {_htm.escape(text)}" if text else "")
            if media_kind == "document":
                fname = str(body.get("media_name") or "hujjat")[:64] or "hujjat"
                sent = await _send_html(
                    lambda: client.send_document(uid, BufferedInputFile(raw, fname), caption=cap_h, **rkw),
                    lambda: client.send_document(uid, BufferedInputFile(raw, fname), caption=cap_p, **rkw))
                fid = sent.document.file_id
                mid = await q.add_message(order_id, "operator", "document",
                                          text or fname, fid, None, client_msg_id=sent.message_id,
                                          file_name=fname,
                                          mime_type=sent.document.mime_type or body.get("media_mime"),
                                          html=html_text, reply_to_mid=reply_mid, file_size=len(raw))
                await post_operator_to_channel(client, order, send_op["name"], content_type="document",
                                               file_id=fid, src_bot=client, text=text or fname)
            elif media_kind == "photo":
                sent = await _send_html(
                    lambda: client.send_photo(uid, BufferedInputFile(raw, "photo.jpg"), caption=cap_h, **rkw),
                    lambda: client.send_photo(uid, BufferedInputFile(raw, "photo.jpg"), caption=cap_p, **rkw))
                fid = sent.photo[-1].file_id
                mid = await q.add_message(order_id, "operator", "photo", text or None, fid, None,
                                          client_msg_id=sent.message_id, html=html_text,
                                          reply_to_mid=reply_mid, file_size=len(raw))
                await post_operator_to_channel(client, order, send_op["name"], content_type="photo",
                                               file_id=fid, src_bot=client, text=text or "")
            else:  # voice — voice -> audio -> document zanjiri (Telegram formatga qarab)
                mime = str(body.get("media_mime", "")).lower()
                ext = "ogg" if "ogg" in mime else ("webm" if "webm" in mime else
                                                   ("mp4" if "mp4" in mime else "audio"))
                fid, ctype, snt = None, "voice", None
                for kind in ("voice", "audio", "document"):
                    try:
                        if kind == "voice":
                            snt = await client.send_voice(uid, BufferedInputFile(raw, "voice.ogg"), **rkw)
                            fid, ctype = snt.voice.file_id, "voice"
                        elif kind == "audio":
                            snt = await client.send_audio(uid, BufferedInputFile(raw, "audio." + ext), **rkw)
                            fid, ctype = snt.audio.file_id, "audio"
                        else:
                            snt = await client.send_document(uid, BufferedInputFile(raw, "voice." + ext),
                                                             caption="🎤 ovozli xabar", **rkw)
                            fid, ctype = snt.document.file_id, "document"
                        break
                    except Exception:
                        continue
                if not fid:
                    return _json({"ok": False, "error": "ovoz yuborilmadi (format qo'llanmadi)"}, 200)
                mid = await q.add_message(order_id, "operator", ctype, None, fid, None,
                                          client_msg_id=snt.message_id, reply_to_mid=reply_mid,
                                          file_size=len(raw))
                await post_operator_to_channel(client, order, send_op["name"], content_type=ctype,
                                               file_id=fid, src_bot=client, text="🎤 ovozli xabar")
        else:
            name = op_client_name(send_op)
            snt = await _send_html(
                lambda: client.send_message(uid, loc.t("operator_reply", clang, name=_htm.escape(name),
                                                       text=body_html), **rkw),
                lambda: client.send_message(uid, loc.t("operator_reply", clang, name=_htm.escape(name),
                                                       text=_htm.escape(text)), **rkw))
            mid = await q.add_message(order_id, "operator", "text", text, None, None,
                                      client_msg_id=snt.message_id, html=html_text,
                                      reply_to_mid=reply_mid)
            await post_operator_to_channel(client, order, send_op["name"], text=text)
    except Exception:
        logger.exception("api_send #%s", order_id)
        return _json({"ok": False, "error": "mijozga yuborilmadi (bloklagan bo'lishi mumkin)"}, 200)
    await q.set_chat_state(op["id"], order_id, draft=None)
    await q.mark_read(op["id"], order_id)
    if send_op["id"] != op["id"]:
        await q.audit(f"op:{op['name']}", "shared_reply", order_id,
                      {"as_operator_id": send_op["id"], "as_operator": send_op["name"],
                       "content_type": media_kind or "text"})
    row = await q.get_message(mid) if mid else None
    out = (await _msgs_with_replies([row]))[0] if row else None
    return _json({"ok": True, "mid": mid, "message": out})


# ---------------- API: "yozmoqda..." (mijozga Telegramda ko'rinadi) ----------------
_TYPING: dict = {}


async def api_typing(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    t = time.time()
    if t - _TYPING.get(order_id, 0) < 4:
        return _json({"ok": True})
    _TYPING[order_id] = t
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False})
    from utils import cbot
    client = cbot()
    if client:
        try:
            await client.send_chat_action(order["user_id"], "typing")
        except Exception:
            pass
    return _json({"ok": True})


# ---------------- API: chat holati (qadash / arxiv / o'qilmagan / qoralama) ----------------
async def api_chat_state(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    shared = bool(body.get("shared"))
    _order, denied = await _operator_order(op, order_id, allow_unassigned_new=not shared,
                                           allow_shared=shared)
    if denied is not None:
        return denied
    f = {}
    for k in ("pinned", "archived", "marked_unread"):
        if k in body:
            f[k] = 1 if body.get(k) else 0
    if "draft" in body:
        f["draft"] = str(body.get("draft") or "")[:4000] or None
    if body.get("read"):
        await q.mark_read(op["id"], order_id)
    if f:
        await q.set_chat_state(op["id"], order_id, **f)
    if "draft" not in body:
        q.bump()
    return _json({"ok": True})


# ---------------- API: xabarni qadash ----------------
async def api_pin(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
        mid = int(body.get("mid") or 0)
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    _order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if mid:
        row = await q.get_message(mid)
        if not row or row["order_id"] != order_id:
            return _json({"ok": False, "error": "xabar topilmadi"})
    await q.set_order_pinned(order_id, mid)
    await q.audit(f"op:{op['name']}", "pin" if mid else "unpin", order_id, {"mid": mid})
    return _json({"ok": True})


# ---------------- API: teglar ----------------
async def _tag_preset():
    raw = await q.get_setting("tags_preset", "") or ""
    return [t.strip()[:40] for t in raw.replace(",", "\n").split("\n") if t.strip()]


async def api_tags(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    return _json({"ok": True, "tags": await _tag_preset()})


async def api_order_tags(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    _order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    tags = []
    for t in body.get("tags") or []:
        t = str(t).replace(",", " ").strip()[:40]
        if t and t not in tags:
            tags.append(t)
    await q.set_order_tags(order_id, tags[:10])
    await q.audit(f"op:{op['name']}", "tags", order_id, {"tags": tags})
    return _json({"ok": True, "tags": tags})


# ---------------- API: ichki izoh (mijoz ko'rmaydi) ----------------
async def api_inote(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    _order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    text = str(body.get("text", "")).strip()[:2000]
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    await q.add_internal_note(order_id, "operator", op["name"], text)
    return _json({"ok": True})


# ---------------- API: murojaatni boshqa operatorga o'tkazish ----------------
async def _transfer(order, new_op, actor: str, actor_label: str):
    """Murojaatni boshqa operatorga o'tkazadi; ikkala operatorni ham bot orqali xabardor qiladi."""
    order_id = order["id"]
    prev_id = order["operator_id"]
    newop_id = new_op["id"]
    if order["status"] == "new":
        moved = await q.claim_order(order_id, newop_id)
    else:
        moved = await q.transfer_order(order_id, prev_id, newop_id)
    if not moved:
        return False
    await q.set_operator_active_order(newop_id, order_id)
    await q.set_operator_availability(newop_id, "busy")
    await q.unhide_chat(newop_id, order_id)
    import botreg
    from utils import cbot, update_group_card
    client = cbot()
    if prev_id and prev_id != newop_id:
        prev = await q.get_operator(prev_id)
        await q.set_operator_active_order(prev_id, None)
        await q.set_operator_availability(prev_id, "free")
        if prev and prev["telegram_id"]:
            pb = (botreg.get_operator_bot(prev["bot_id"]) if prev["bot_id"] else client) or client
            try:
                await pb.send_message(prev["telegram_id"],
                                      f"ℹ️ Murojaat #{order_id} {actor_label} tomonidan "
                                      f"{_htm.escape(new_op['name'])} ga o'tkazildi.")
            except Exception:
                pass
    if new_op["telegram_id"]:
        nb = (botreg.get_operator_bot(new_op["bot_id"]) if new_op["bot_id"] else client) or client
        try:
            await nb.send_message(new_op["telegram_id"],
                                  f"🔄 {actor_label} sizga murojaat #{order_id} ni biriktirdi. "
                                  f"CRM yoki botda oching.")
        except Exception:
            pass
    if client:
        try:
            await update_group_card(client, order_id)
        except Exception:
            pass
    await q.audit(actor, "transfer", order_id, {"from": prev_id, "to": new_op["name"]})
    return True


async def api_ops_list(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    load = await q.operator_open_load()
    items = []
    shared = bool(request.query.get("shared"))
    for o in await q.list_operators():
        if o["status"] != "active" or (o["id"] == op["id"] and not shared):
            continue
        st = "offline" if not o["telegram_id"] else ("busy" if o["availability"] == "busy" else "free")
        items.append({"id": o["id"], "name": o["name"], "state": st, "load": load.get(o["id"], 0)})
    items.sort(key=lambda x: ({"free": 0, "busy": 1, "offline": 2}[x["state"]], x["load"]))
    return _json({"ok": True, "items": items})


async def api_transfer(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
        # «to_id»: «operator_id» sessiya egasini bildiradi — uni ustidan yozib bo'lmaydi
        newop_id = int(body.get("to_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    if newop_id == op["id"] and not body.get("shared"):
        return _json({"ok": False, "error": "O'zingizga o'tkazib bo'lmaydi"})
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    new_op = await q.get_operator(newop_id)
    if not order or not new_op or new_op["status"] != "active":
        return _json({"ok": False, "error": "topilmadi"}, 404)
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"})
    note = str(body.get("note", "")).strip()[:500]
    if note:
        await q.add_internal_note(order_id, "operator", op["name"], f"↪️ O'tkazish izohi: {note}")
    if not await _transfer(order, new_op, f"op:{op['name']}", f"Operator {_htm.escape(op['name'])}"):
        return _json({"ok": False, "error": "Murojaat holati o'zgardi, qayta ochib ko'ring"}, 409)
    await q.hide_chat(op["id"], order_id)
    return _json({"ok": True, "info": f"#{order_id} → {new_op['name']} ga o'tkazildi"})


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
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Bu murojaat allaqachon yopilgan"})
    from utils import cbot
    from handlers.operator import _finish_with_rating
    try:
        await _finish_with_rating(cbot(), order_id, f"operator:{op['id']}")
    except Exception:
        logger.exception("api_close #%s", order_id)
        return _json({"ok": False, "error": "Yakunlab bo'lmadi, qayta urinib ko'ring"})
    await q.audit(f"op:{op['name']}", "close", order_id)
    return _json({"ok": True})


# ---------------- API: bekor qilish / Отказ ----------------
async def api_cancel(request):
    """Murojaatni bekor qiladi (botdagi «Bekor» bilan bir xil): mijozga xabar boradi."""
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
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Bu murojaat allaqachon yopilgan"})
    await q.set_order_status(order_id, "canceled", f"operator:{op['id']}")
    owner_id = order["operator_id"] or op["id"]
    await q.set_operator_active_order(owner_id, None)
    await q.set_operator_availability(owner_id, "free")
    await q.set_user_active_order(order["user_id"], None)
    from utils import cbot, update_group_card
    client = cbot()
    if client:
        try:
            await update_group_card(client, order_id)
        except Exception:
            pass
        try:
            clang = await q.get_lang(order["user_id"])
            await client.send_message(order["user_id"], loc.t("order_canceled", clang, id=order_id))
        except Exception:
            pass
    await q.audit(f"op:{op['name']}", "cancel", order_id)
    return _json({"ok": True, "info": "Murojaat bekor qilindi"})


async def api_reject(request):
    """«Отказ» — murojaat Отказ kanaliga joylanadi va belgilanadi, LEKIN yopilmaydi."""
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
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"})
    try:
        from utils import post_canceled_to_channel
        await post_canceled_to_channel(order_id, op_name=op["name"])
    except Exception:
        logger.exception("reject -> channel")
    await q.set_order_rejected(order_id, op["id"])
    await q.audit(f"op:{op['name']}", "reject", order_id)
    return _json({"ok": True, "info": "Отказ belgilandi — chat ochiq qoladi"})


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
    _order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    if newop_id != op["id"]:
        await q.hide_chat(op["id"], order_id)
    await q.audit(f"op:{op['name']}", "hide_chat", order_id)
    q.bump()
    return _json({"ok": True})


# ---------------- API: profil ----------------
async def api_profile(request):
    import webapp_extra
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    s = await q.operator_stats(op["id"])
    incoming = await q.new_count()
    return _json({"ok": True, "name": op["name"], "login": op["login"],
                  "availability": op["availability"], "incoming": incoming,
                  "token": _fresh_op_token(op, request.query.get("token", "")),
                  "mk": _media_key(), "ws": op["work_start"], "we": op["work_end"],
                  "goal": await webapp_extra.operator_goal(op),
                  "has_avatar": os.path.exists(os.path.join(AVATAR_DIR, f"{op['id']}.jpg")),
                  "stats": {"accepted": s["accepted"], "done": s["done"],
                            "today_done": s["today_done"], "rating": s["avg_rating"],
                            "rated": s["rated_count"]}})


async def api_status(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    new = "busy" if op["availability"] == "free" else "free"
    await q.set_operator_availability(op["id"], new)
    return _json({"ok": True, "availability": new})


async def api_avatar(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return web.Response(status=401)
    path = os.path.join(AVATAR_DIR, f"{op['id']}.jpg")
    if os.path.exists(path):
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})
    return web.Response(status=404)


async def api_avatar_upload(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    data = body.get("data")
    if not data:
        return _json({"ok": False, "error": "empty"}, 400)
    try:
        raw = base64.b64decode(str(data).split(",")[-1])
    except Exception:
        return _json({"ok": False, "error": "bad"}, 400)
    os.makedirs(AVATAR_DIR, exist_ok=True)
    with open(os.path.join(AVATAR_DIR, f"{op['id']}.jpg"), "wb") as f:
        f.write(raw)
    return _json({"ok": True})


# ---------------- API: mijozlar ----------------
async def api_clients(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    search = request.query.get("q") or None
    rows = await q.my_clients(op["id"], search)
    out = [{"tg": r["telegram_id"], "name": r["full_name"] or r["phone"] or "Mijoz",
            "phone": r["phone"] or "", "cnt": r["cnt"], "last_order": r["last_order"]} for r in rows]
    return _json({"ok": True, "total": len(out), "clients": out})


async def api_client_open(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    try:
        tg = int(request.query.get("tg"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "tg"}, 400)
    oid = await q.last_order_of(tg)
    if not oid:
        # Murojaat bo'lmasa — yangi suhbat (murojaat) yaratamiz, shu operatorга biriktiramiz
        user = await q.get_user(tg)
        if not user:
            return _json({"ok": False, "error": "Mijoz topilmadi"})
        oid = await q.create_order(tg, user["branch_id"], "text")
        await q.claim_order(oid, op["id"])
        await q.set_operator_active_order(op["id"], oid)
        await q.set_operator_availability(op["id"], "busy")
    return _json({"ok": True, "order_id": oid})


async def api_branches(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    bs = await q.list_branches()
    return _json({"ok": True, "branches": [{"id": b["id"], "name": b["name"],
                                            "address": b["address"] or ""} for b in bs]})


async def api_newcount(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    return _json({"ok": True, "count": await q.new_count()})


# ---------------- API: CRM kanali (murojaatlar tushadi) ----------------
async def api_channel(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.channel_feed()
    items = []
    for r in rows:
        items.append({
            "order_id": r["id"], "name": r["full_name"] or "—", "phone": r["phone"] or "",
            "uname": r["username"] or "", "branch": r["branch"] or "",
            "time": (r["created_at"] or "")[11:16],
            "text": r["first_text"] or "", "file_id": r["first_file"] or "",
            "ftype": r["first_ct"] or "", "file_name": r["first_name"] or "",
            "mime_type": r["first_mime"] or ""})
    return _json({"ok": True, "count": len(items), "items": items})


async def api_channel_accept(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    if order["status"] != "new" or not await q.claim_order(order_id, op["id"]):
        return _json({"ok": False, "error": "Boshqa operator qabul qildi"})
    await q.set_operator_active_order(op["id"], order_id)
    await q.set_operator_availability(op["id"], "busy")
    # operator botlaridagi bildirishnomalarni o'chiramiz (boshqalardan yo'qoladi)
    import botreg
    for n in await q.order_notifs(order_id):
        nb = botreg.get_operator_bot(n["bot_id"])
        if nb:
            try:
                await nb.delete_message(n["chat_id"], n["message_id"])
            except Exception:
                pass
    await q.clear_order_notifs(order_id)
    # haqiqiy Telegram kanalidagi kartani yangilaymiz (Jarayonda + kim qabul qildi)
    from utils import cbot, update_group_card
    from config import OPERATORS_GROUP_ID
    client = cbot()
    if client and order["group_msg_id"] and OPERATORS_GROUP_ID:
        try:
            await client.unpin_chat_message(OPERATORS_GROUP_ID, message_id=order["group_msg_id"])
        except Exception:
            pass
        try:
            await update_group_card(client, order_id)
        except Exception:
            pass
    if client:
        clang = await q.get_lang(order["user_id"])
        try:
            await client.send_message(order["user_id"], loc.t("accept_notify", clang))
        except Exception:
            pass
    return _json({"ok": True, "order_id": order_id})


# ---------------- API: chat buyruqlari (/10daqiqa, /filialtanlatish ...) ----------------
def _card_html(card: str):
    """Bot HTML matni (<b>...) -> (xavfsiz html, oddiy matn) — CRM yozishmasida karta chiroyli chiqadi."""
    import tghtml
    h = tghtml.sanitize(card)
    return h, tghtml.to_plain(h)


async def api_cmd(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    cmd = body.get("cmd")
    arg = body.get("arg")
    shared = bool(body.get("shared"))
    order, denied = await _operator_order(op, order_id, allow_shared=shared)
    if denied is not None:
        return denied
    send_op = op
    if shared and order["operator_id"] != op["id"]:
        send_op = await q.get_operator(order["operator_id"]) or op
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"})
    from utils import cbot, post_operator_to_channel
    import keyboards as kb
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"}, 200)
    uid = order["user_id"]
    clang = await q.get_lang(uid)
    try:
        if cmd == "fulfillment":
            # Yetkazish turi: delivery (yetkazib berish) | pickup (olib ketish) | "" (bekor).
            # Faqat statistikaga yoziladi — mijozga hech narsa yuborilmaydi.
            kind = (arg or "").strip()
            if kind not in ("delivery", "pickup", ""):
                return _json({"ok": False, "error": "noto'g'ri qiymat"}, 400)
            await q.set_fulfillment(order_id, kind or None)
            info = {"delivery": "🚚 Yetkazib berish belgilandi",
                    "pickup": "🏃 Olib ketish belgilandi",
                    "": "Belgi olib tashlandi"}[kind]
            return _json({"ok": True, "info": info, "fulfillment": kind})

        if cmd == "autoclose":
            from handlers.operator import spawn_auto_close, AUTO_CLOSE_MIN
            close_at = (now_local() + timedelta(minutes=AUTO_CLOSE_MIN)).strftime("%Y-%m-%d %H:%M:%S")
            await q.set_auto_close(order_id, close_at)
            # Kuchli havola bilan ishga tushiramiz (aks holda vazifa GC'da yo'qoladi)
            spawn_auto_close(client, order_id, q.now(), op["telegram_id"] or 0)
            await client.send_message(uid, loc.t("auto_close_warning", clang, min=AUTO_CLOSE_MIN))
            return _json({"ok": True, "info": f"{AUTO_CLOSE_MIN} daqiqada avto-yakunlash yoqildi",
                          "auto_close_at": close_at})

        if cmd == "askbranch":
            regions = await q.list_regions()
            if len(regions) > 1:
                await client.send_message(
                    uid, loc.t("op_ask_branch", clang),
                    reply_markup=kb.regions_choose_kb(regions, clang, op_order=order_id))
            else:
                branches = await q.list_branches()
                await client.send_message(
                    uid, loc.t("op_ask_branch", clang),
                    reply_markup=kb.op_ask_branch_kb(branches, order_id, clang))
            # Majburiy: mijoz filial tanlamaguncha boshqa amal bloklanadi
            await q.set_pending_branch(uid, order_id)
            return _json({"ok": True, "info": "Mijozga filial tanlash so'rovi yuborildi"})

        if cmd == "sendbranch":
            b = await q.get_branch(int(arg))
            if not b:
                return _json({"ok": False, "error": "filial topilmadi"})
            header = loc.t("op_branch_info", clang)
            # rasm + nomi/manzili/telefoni/ish vaqti + «Yo'l ko'rsatish» + xaritadagi nuqta
            ids = await send_branch_to_client(client, uid, b, clang, header=header, src_bot=client)
            if not ids:
                return _json({"ok": False, "error": "mijozga yuborilmadi"}, 200)
            ids = [i for i in ids if i]
            h, plain = _card_html(branch_card_text(b, clang, header))
            await q.add_message(order_id, "operator", "text", plain, None, None, html=h,
                                client_msg_id=ids[0] if ids else None, extra_cmids=ids[1:])
            return _json({"ok": True, "info": "Filial ma'lumoti yuborildi"})

        if cmd == "changebranch":
            # Operator filialni o'zi tanlaydi: murojaat + mijoz profiliga yoziladi,
            # mijozga to'liq filial kartasi boradi (bot ichidagi «Filialni o'zgartirish» bilan bir xil)
            try:
                b = await q.get_branch(int(arg))
            except (TypeError, ValueError):
                b = None
            if not b:
                return _json({"ok": False, "error": "filial topilmadi"})
            from utils import update_group_card
            await q.set_order_branch(order_id, b["id"])
            await q.set_user_branch(uid, b["id"])
            await q.clear_pending_branch(uid)
            try:
                await update_group_card(client, order_id)
            except Exception:
                logger.exception("changebranch -> group card")
            header = loc.t("op_branch_changed", clang)
            ids = await send_branch_to_client(client, uid, b, clang, header=header, src_bot=client)
            ids = [i for i in (ids or []) if i]
            h, plain = _card_html(branch_card_text(b, clang, header)) if ids else \
                (None, f"🏥 Filial operator tomonidan o'zgartirildi: {b['name']}")
            await q.add_message(order_id, "operator", "text", plain, None, None, html=h,
                                client_msg_id=ids[0] if ids else None, extra_cmids=ids[1:])
            if ids:
                try:
                    await post_operator_to_channel(client, order, send_op["name"],
                                                   text=f"🏥 Filial yuborildi: {b['name']}")
                except Exception:
                    logger.exception("changebranch -> channel")
            return _json({"ok": True, "branch": b["name"], "branch_id": b["id"],
                          "info": f"Filial: {b['name']} — mijozga yuborildi" if ids
                          else f"Filial saqlandi: {b['name']} (mijozga yuborilmadi)"})

        if cmd == "billitems":
            # Hisob-kitob yaratuvchi: dorilar ro'yxati -> tayyor matn, keyin oddiy «bill» yo'li
            from webapp_extra import build_bill_text
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                return _json({"ok": False, "error": "Ro'yxat bo'sh"})
            arg, _total = build_bill_text(items, body.get("delivery") or 0, body.get("note") or "")
            cmd = "bill"
        if cmd == "bill":
            billtext = str(arg or "").strip()
            media_kind = body.get("media_kind")
            media_data = body.get("media_data")
            sticker_id = body.get("sticker_id")
            cap = loc.t("bill_to_client", clang, id=order_id, bill=_htm.escape(billtext))
            label = f"{BILL_TAG}: {billtext}" if billtext else BILL_TAG

            async def _bill_to_channel(**kw):
                # Kanalga joylash uzilsa ham CRM yozishmasidagi yozuv yo'qolmasin
                try:
                    await post_operator_to_channel(client, order, send_op["name"], src_bot=client, **kw)
                except Exception:
                    logger.exception("bill -> channel")

            if media_kind == "photo" and media_data:
                raw = base64.b64decode(str(media_data).split(",")[-1])
                sent = await client.send_photo(uid, BufferedInputFile(raw, "bill.jpg"), caption=cap)
                fid = sent.photo[-1].file_id
                await q.set_order_bill(order_id, billtext, fid)
                await q.add_message(order_id, "operator", "photo", label, fid, None,
                                    client_msg_id=sent.message_id)
                await _bill_to_channel(content_type="photo", file_id=fid, text=label)
            elif media_kind == "voice" and media_data:
                # Brauzer ogg/webm/mp4 yozishi mumkin — voice -> audio -> document zanjiri
                raw = base64.b64decode(str(media_data).split(",")[-1])
                mime = str(body.get("media_mime", "")).lower()
                ext = "ogg" if "ogg" in mime else ("webm" if "webm" in mime else
                                                   ("mp4" if "mp4" in mime else "audio"))
                vlabel = f"{BILL_TAG} (ovozli)" + (f": {billtext}" if billtext else "")
                fid, ct2, sent = None, "voice", None
                for kind in ("voice", "audio", "document"):
                    try:
                        if kind == "voice":
                            sent = await client.send_voice(uid, BufferedInputFile(raw, "voice.ogg"))
                            fid, ct2 = sent.voice.file_id, "voice"
                        elif kind == "audio":
                            sent = await client.send_audio(
                                uid, BufferedInputFile(raw, "bill_audio." + ext))
                            fid, ct2 = sent.audio.file_id, "audio"
                        else:
                            sent = await client.send_document(
                                uid, BufferedInputFile(raw, "bill_voice." + ext), caption=vlabel)
                            fid, ct2 = sent.document.file_id, "document"
                        break
                    except Exception:
                        continue
                if not fid:
                    return _json({"ok": False, "error": "ovoz yuborilmadi (format qo'llanmadi)"}, 200)
                try:
                    await client.send_message(uid, cap)
                except Exception:
                    logger.exception("bill caption")
                await q.set_order_bill(order_id, billtext or "🎤 ovozli hisob-kitob", None)
                await q.add_message(order_id, "operator", ct2, vlabel, fid, None,
                                    client_msg_id=sent.message_id)
                await _bill_to_channel(content_type=ct2, file_id=fid, text=vlabel)
            elif sticker_id:
                tpl = await q.get_template(int(sticker_id))
                if not tpl or not tpl["sticker"]:
                    return _json({"ok": False, "error": "stiker topilmadi"})
                sent = await client.send_sticker(uid, tpl["sticker"])
                try:
                    await client.send_message(uid, cap)
                except Exception:
                    logger.exception("bill caption")
                await q.set_order_bill(order_id, billtext or "🎭 stiker", None)
                await q.add_message(order_id, "operator", "sticker", label, tpl["sticker"], None,
                                    client_msg_id=sent.message_id)
                await _bill_to_channel(content_type="sticker", file_id=tpl["sticker"], text=label)
            else:
                if not billtext:
                    return _json({"ok": False, "error": "Hisob-kitob matni bo'sh"}, 200)
                sent = await client.send_message(uid, cap)
                await q.set_order_bill(order_id, billtext, None)
                await q.add_message(order_id, "operator", "text", label, None, None,
                                    client_msg_id=sent.message_id)
                await _bill_to_channel(text=label)
            return _json({"ok": True, "info": "Hisob-kitob yuborildi"})
    except Exception:
        logger.exception("api_cmd %s (order %s)", cmd, order_id)
        return _json({"ok": False, "error": "bajarilmadi"}, 200)
    return _json({"ok": False, "error": "noma'lum buyruq"}, 400)


# ---------------- API: sozlamalar ro'yxatlari ----------------
async def api_unfinished(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.unfinished_orders()
    items = [{"order_id": r["id"], "name": r["full_name"] or "—", "status": r["status"],
              "operator": r["operator"] or "", "mine": r["operator_id"] == op["id"],
              "time": (r["created_at"] or "")[11:16]} for r in rows]
    return _json({"ok": True, "items": items})


async def api_done(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    search = request.query.get("q") or None
    rows = await q.operator_done_orders(op["id"], search, limit=100)
    items = [{"order_id": r["id"],
              "name": r["full_name"] or r["phone"] or "Mijoz",
              "status": r["status"],
              "time": (r["closed_at"] or r["created_at"] or "")[:16],
              "rating": r["rating"] or 0} for r in rows]
    return _json({"ok": True, "items": items})


async def api_my_ratings(request):
    """Operatorning o'z so'nggi baholari (baho + izoh)."""
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.operator_recent_ratings(op["id"], 20)
    items = [{"order_id": r["id"], "rating": r["rating"], "feedback": r["feedback"] or "",
              "name": r["full_name"] or "Mijoz",
              "time": (r["closed_at"] or "")[:10]} for r in rows]
    return _json({"ok": True, "items": items})


async def api_rating(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    rows = await q.operators_rating()
    items = [{"name": r["name"], "score": r["score"], "done": r["done"],
              "rating": r["avg_rating"]} for r in rows]
    return _json({"ok": True, "items": items, "me": op["name"]})


# ---------------- API: stikerlar (admin shablonlari) ----------------
async def api_stickers(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    tpls = await q.list_templates()
    items = [{"id": t["id"], "file_id": t["sticker"]} for t in tpls if t["sticker"]]
    return _json({"ok": True, "items": items})


async def api_send_sticker(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id")); tid = int(body.get("sticker_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "arg"}, 400)
    shared = bool(body.get("shared"))
    order, denied = await _operator_order(
        op, order_id, allow_unassigned_new=not shared, claim_unassigned=not shared,
        allow_shared=shared)
    if denied is not None:
        return denied
    tpl = await q.get_template(tid)
    if not order or not tpl or not tpl["sticker"]:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "yopilgan"})
    send_op = op
    if shared and order["operator_id"] != op["id"]:
        send_op = await q.get_operator(order["operator_id"]) or op
    if order["operator_id"] == op["id"]:
        await q.set_operator_active_order(op["id"], order_id)
    from utils import cbot, post_operator_to_channel
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    try:
        snt = await client.send_sticker(order["user_id"], tpl["sticker"])
        await q.add_message(order_id, "operator", "sticker", None, tpl["sticker"], None,
                            client_msg_id=snt.message_id)
        await post_operator_to_channel(client, order, send_op["name"],
                                       content_type="sticker", file_id=tpl["sticker"], src_bot=client)
    except Exception:
        return _json({"ok": False, "error": "yuborilmadi"})
    if send_op["id"] != op["id"]:
        await q.audit(f"op:{op['name']}", "shared_reply", order_id,
                      {"as_operator_id": send_op["id"], "as_operator": send_op["name"],
                       "content_type": "sticker"})
    return _json({"ok": True})


# ---------------- API: xabarni o'chirish / tahrirlash ----------------
async def api_msg_del(request):
    """Operator o'z xabarini o'chiradi: mijoz chatidan ham (Telegram 48 soat ichida ruxsat beradi).
    Mijoz chatidagi ID si saqlanmagan eski/tizim xabarlari faqat yozishmadan o'chiriladi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        mid = int(body.get("mid"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    row = await q.get_message(mid)
    if not row or row["sender"] != "operator":
        return _json({"ok": False, "error": "Bu xabarni o'chirib bo'lmaydi"})
    order, denied = await _operator_order(op, row["order_id"],
                                          allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    ids = [row["client_msg_id"]] if row["client_msg_id"] else []
    extra = row["extra_cmids"] if "extra_cmids" in row.keys() else None
    ids += [int(x) for x in (extra or "").split(",") if x.strip().isdigit()]
    from utils import cbot
    client = cbot()
    removed = 0
    if ids and client:
        for cm in ids:
            try:
                await client.delete_message(order["user_id"], cm)
                removed += 1
            except Exception:
                pass
        if not removed:
            return _json({"ok": False, "error": "Mijozda o'chirib bo'lmadi (48 soatdan oshgan)"})
    await q.audit(f"op:{op['name']}", "msg_delete", row["order_id"],
                  {"mid": mid, "type": row["content_type"], "text": row["text"] or "",
                   "file_id": row["file_id"] or "", "sent_at": row["created_at"],
                   "client_deleted": bool(removed)})
    await q.delete_message_row(mid)
    if (order["pinned_mid"] if "pinned_mid" in order.keys() else None) == mid:
        await q.set_order_pinned(order["id"], None)
    return _json({"ok": True, "client": bool(removed),
                  "info": "Xabar mijozdan ham o'chirildi" if removed else "Xabar yozishmadan o'chirildi"})


async def api_msg_delete_many(request):
    """Tanlangan operator xabarlarini bitta amalda o'chiradi.
    Mijoz yuborgan xabarlar o'chirilmaydi; natijada nechta o'tkazib yuborilgani qaytadi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    raw = body.get("mids") if isinstance(body.get("mids"), list) else []
    mids = []
    for value in raw[:100]:
        try:
            mid = int(value)
            if mid > 0 and mid not in mids:
                mids.append(mid)
        except (TypeError, ValueError):
            pass
    if not mids:
        return _json({"ok": False, "error": "Xabar tanlanmagan"}, 400)
    from utils import cbot
    client = cbot()
    deleted, skipped = [], []
    for mid in mids:
        row = await q.get_message(mid)
        if not row or row["sender"] != "operator":
            skipped.append(mid)
            continue
        order, denied = await _operator_order(op, row["order_id"],
                                              allow_shared=bool(body.get("shared")))
        if denied is not None:
            skipped.append(mid)
            continue
        ids = [row["client_msg_id"]] if row["client_msg_id"] else []
        extra = row["extra_cmids"] if "extra_cmids" in row.keys() else None
        ids += [int(x) for x in (extra or "").split(",") if x.strip().isdigit()]
        removed = 0
        if ids and client:
            for cmid in ids:
                try:
                    await client.delete_message(order["user_id"], cmid)
                    removed += 1
                except Exception:
                    pass
            if not removed:
                skipped.append(mid)
                continue
        await q.audit(f"op:{op['name']}", "msg_delete", row["order_id"],
                      {"mid": mid, "type": row["content_type"], "text": row["text"] or "",
                       "file_id": row["file_id"] or "", "sent_at": row["created_at"],
                       "client_deleted": bool(removed), "batch": True})
        await q.delete_message_row(mid)
        if (order["pinned_mid"] if "pinned_mid" in order.keys() else None) == mid:
            await q.set_order_pinned(order["id"], None)
        deleted.append(mid)
    if not deleted:
        return _json({"ok": False, "error": "Tanlangan xabarlarni o'chirib bo'lmadi",
                      "deleted": [], "skipped": skipped})
    return _json({"ok": True, "deleted": deleted, "skipped": skipped,
                  "info": f"{len(deleted)} ta xabar o'chirildi" +
                          (f", {len(skipped)} tasi o'tkazib yuborildi" if skipped else "")})


async def api_msg_edit(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        mid = int(body.get("mid"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    row = await q.get_message(mid)
    if not row:
        return _json({"ok": False, "error": "Xabar topilmadi"})
    order0 = await q.get_order(row["order_id"])
    shared = bool(body.get("shared"))
    if not order0:
        return _json({"ok": False, "error": "Murojaat topilmadi"}, 404)
    order, denied = await _operator_order(op, row["order_id"], allow_shared=shared)
    if denied is not None:
        return denied
    edit_op = op
    if shared and order["operator_id"] != op["id"]:
        edit_op = await q.get_operator(order["operator_id"]) or op
    new_text, new_html = await _prepare_text(body, order, edit_op)
    if not new_text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    if (not row or row["sender"] != "operator" or not row["client_msg_id"]
            or (row["content_type"] or "text") != "text"):
        return _json({"ok": False, "error": "Faqat o'z matnli xabaringizni tahrirlash mumkin"})
    from utils import cbot
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    clang = await q.get_lang(order["user_id"])
    name = _htm.escape(op_client_name(edit_op))
    try:
        await _send_html(
            lambda: client.edit_message_text(
                loc.t("operator_reply", clang, name=name, text=new_html or _htm.escape(new_text)),
                chat_id=order["user_id"], message_id=row["client_msg_id"]),
            lambda: client.edit_message_text(
                loc.t("operator_reply", clang, name=name, text=_htm.escape(new_text)),
                chat_id=order["user_id"], message_id=row["client_msg_id"]))
    except Exception as e:
        if "not modified" in str(e).lower():
            return _json({"ok": True})
        return _json({"ok": False, "error": "Tahrirlab bo'lmadi (48 soatdan oshgan)"})
    await q.audit(f"op:{op['name']}", "msg_edit", row["order_id"],
                  {"mid": mid, "old": row["text"] or "", "new": new_text})
    await q.update_message_text(mid, new_text, new_html)
    return _json({"ok": True})


# ---------------- API: eslatma ----------------
async def api_remind(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
        minutes = int(body.get("minutes"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    _order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    minutes = max(1, min(minutes, 7 * 24 * 60))
    from datetime import timedelta
    from config import now_local
    remind_at = (now_local() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    await q.add_reminder(op["id"], order_id, remind_at, str(body.get("note", "")).strip()[:200])
    label = f"{minutes} daqiqadan" if minutes < 60 else f"{minutes // 60} soatdan"
    return _json({"ok": True, "info": f"Eslatma qo'yildi — {label} keyin botda xabar keladi"})


# ---------------- API: shaxsiy statistika (7 kun) ----------------
async def api_mystats(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    from datetime import timedelta
    from config import now_local
    daily = await q.my_daily_done(op["id"], 7)
    wd = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    days = []
    for i in range(6, -1, -1):
        d = now_local() - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        days.append({"label": wd[d.weekday()], "c": daily.get(key, 0)})
    return _json({"ok": True, "days": days})


# ---------------- API: mijoz kartasi (chat ichida) ----------------
async def api_client_info(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(request.query.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    shared = bool(request.query.get("shared"))
    order, denied = await _operator_order(op, order_id, allow_unassigned_new=not shared,
                                          allow_shared=shared)
    if denied is not None:
        return denied
    u = await q.user_full(order["user_id"])
    if not u:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    note = await q.get_client_note(order["user_id"])
    orders = await q.orders_by_user(order["user_id"])
    return _json({"ok": True,
                  "fulfillment": order["fulfillment"] or "",
                  "client": {"name": u["full_name"] or u["phone"] or "Mijoz",
                             "phone": u["phone"] or "", "username": u["username"] or "",
                             "branch": u["branch"] or "", "reg": (u["registered_at"] or "")[:10],
                             "note": note},
                  "orders": [{"id": o["id"], "status": o["status"],
                              "date": (o["created_at"] or "")[:10],
                              "rating": o["rating"] or 0,
                              "can_open": o["operator_id"] == op["id"] or
                                          (shared and o["status"] == "in_progress" and bool(o["operator_id"])) or
                                          (o["status"] == "new" and not o["operator_id"])}
                             for o in orders[:12]]})


# ---------------- API: yakunlangan murojaatni davom ettirish ----------------
async def api_reopen(request):
    """Operator yakunlangan/bekor qilingan murojaatni qayta ochadi va yozishni davom ettiradi."""
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
    order, denied = await _operator_order(op, order_id)
    if denied is not None:
        return denied
    if order["status"] in ("new", "in_progress"):
        return _json({"ok": True, "info": "allaqachon ochiq"})   # allaqachon ochiq
    await q.reopen_order(order_id, op["id"])
    await q.set_operator_availability(op["id"], "busy")
    await q.set_operator_active_order(op["id"], order_id)
    await q.set_user_active_order(order["user_id"], order_id)
    # CRM yozishmasida ko'rinsin + operator kanaliga qaytsin
    await q.add_message(order_id, "operator", "text", "🔄 Suhbat qayta ochildi (davom ettirildi)", None, None)
    await q.audit(f"op:{op['name']}", "reopen", order_id)
    return _json({"ok": True, "info": "Suhbat davom ettirildi"})


# ---------------- API: matnli tayyor javoblar ----------------
async def api_templates(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    tpls = await q.templates_for_operator(op["id"])
    items = [{"id": t["id"], "text": t["text"], "own": bool(t["operator_id"])}
             for t in tpls if t["text"]]
    return _json({"ok": True, "items": items})


async def api_tpl_add(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    text = str(body.get("text", "")).strip()[:2000]
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    tid = await q.add_operator_template(op["id"], text)
    return _json({"ok": True, "id": tid})


async def api_tpl_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        tid = int(body.get("id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    ok = await q.delete_operator_template(op["id"], tid)
    return _json({"ok": ok, "error": None if ok else "Faqat o'zingizning shabloningizni o'chira olasiz"})


# ---------------- API: mijoz izohi ----------------
async def api_note(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(request.query.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    shared = bool(request.query.get("shared"))
    order, denied = await _operator_order(op, order_id, allow_unassigned_new=not shared,
                                          allow_shared=shared)
    if denied is not None:
        return denied
    return _json({"ok": True, "note": await q.get_client_note(order["user_id"])})


async def api_note_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order, denied = await _operator_order(op, order_id, allow_shared=bool(body.get("shared")))
    if denied is not None:
        return denied
    await q.set_client_note(order["user_id"], str(body.get("note", "")).strip())
    await q.audit(f"op:{op['name']}", "client_note", order_id)
    return _json({"ok": True})


# ================================================================
#                        ADMIN MINI APP
# ================================================================
async def _admin_epoch() -> int:
    try:
        return int(await q.get_setting("admin_epoch", "0") or 0)
    except ValueError:
        return 0


async def _admin_sign(tg_id, exp=None) -> str:
    """Admin sessiya tokeni: 7 kunlik, «barcha sessiyalarni bekor qilish» bilan o'chiriladi."""
    exp = int(exp or (time.time() + _ADM_TTL))
    ep = await _admin_epoch()
    return f"v2.{exp}.{_hm(f'adm2:{tg_id}:{ep}:{exp}')}"


# Faqat ko'rish (supervayzer) rolida ham ruxsat etilgan POST so'rovlar (hech narsani o'zgartirmaydi)
_VIEWER_POST_OK = {"/api/admin/login", "/api/admin/excel", "/api/admin/excel_clients", "/api/admin/products_file",
                   "/api/admin/ai_test"}


async def _is_admin(tg_id) -> bool:
    """Admin — .env ADMIN_IDS'da yoki CRM'dan qo'shilgan (DB) adminlar.
    CRM'dan «o'chirilgan» .env adminlari admin hisoblanmaydi."""
    if tg_id in await q.disabled_admin_ids():
        return False
    if tg_id in ADMIN_IDS:
        return True
    return tg_id in await q.admin_telegram_ids()


def _is_super(tg_id) -> bool:
    """Bosh admin (super-admin) — faqat u asosiy adminni tanlaydi."""
    from config import SUPER_ADMIN_ID
    return SUPER_ADMIN_ID and int(tg_id) == SUPER_ADMIN_ID


async def _can_manage_admins(tg_id) -> bool:
    """Admin qo'sha/o'chira oladimi? Faqat bosh admin va u tayinlagan asosiy admin."""
    if _is_super(tg_id):
        return True
    mgr = await q.get_manager_admin_id()
    return mgr is not None and int(tg_id) == mgr


async def _auth_admin(request, data):
    """Admin sessiya tokenini tekshiradi (avto-login orqali olingan)."""
    try:
        tg = int(data.get("admin_id"))
    except (TypeError, ValueError):
        return None
    token = str(data.get("token", ""))
    if not await _is_admin(tg):
        return None
    try:
        ver, exp_s, _sig = token.split(".", 2)
        exp = int(exp_s)
    except ValueError:
        return None
    if ver != "v2" or exp < time.time() or not hmac.compare_digest(await _admin_sign(tg, exp), token):
        return None
    # Supervayzer (faqat ko'rish) — hech narsani o'zgartira olmaydi
    if request.method == "POST" and request.path not in _VIEWER_POST_OK:
        if tg not in ADMIN_IDS and await q.admin_role(tg) == "viewer":
            raise web.HTTPForbidden(text=json.dumps({"ok": False, "error": "Sizda faqat ko'rish huquqi bor"}),
                                    content_type="application/json")
    return tg


async def admin_index(request):
    if os.path.exists(_ADMIN_HTML):
        return web.FileResponse(_ADMIN_HTML, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", "Expires": "0"})
    return web.Response(text="Admin mini app topilmadi.", status=404)


async def view_index(request):
    """Отказ murojaat chatini faqat ko'rish (read-only) uchun alohida mini app sahifasi."""
    if os.path.exists(_VIEW_HTML):
        return web.FileResponse(_VIEW_HTML, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", "Expires": "0"})
    return web.Response(text="Ko'rish sahifasi topilmadi.", status=404)


async def api_admin_login(request):
    """Avto-login: Telegram initData imzosi tekshiriladi, ADMIN_IDS'da bo'lsa kiradi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    user = await _auth_user(request, body)
    if not user:
        return _json({"ok": False, "error": "Telegram tekshiruvi o'tmadi. "
                                            "Asosiy botdagi Mini app tugmasidan oching."})
    # username orqali qo'shilgan admin birinchi marta ochsa — id'sini bog'lab qo'yamiz
    if user["id"] not in ADMIN_IDS and user.get("username"):
        if await q.claim_pending_admin(user["id"], user["username"]):
            from utils import refresh_admins
            await refresh_admins()
    if not await _is_admin(user["id"]):
        return _json({"ok": False, "error": "Siz admin emassiz."})
    role = "admin" if user["id"] in ADMIN_IDS else await q.admin_role(user["id"])
    return _json({"ok": True, "admin_id": user["id"],
                  "name": user.get("first_name") or "Admin",
                  "role": role, "mk": _media_key(),
                  "token": await _admin_sign(user["id"])})


def _period_start_str(period: str) -> str:
    from datetime import timedelta
    from config import now_local
    n = now_local()
    if period == "today":
        return n.strftime("%Y-%m-%d 00:00:00")
    if period == "week":
        return (n - timedelta(days=n.weekday())).strftime("%Y-%m-%d 00:00:00")
    if period == "lastweek":
        # o'tgan hafta boshi (o'tgan dushanba)
        return (n - timedelta(days=n.weekday() + 7)).strftime("%Y-%m-%d 00:00:00")
    if period == "month":
        return n.strftime("%Y-%m-01 00:00:00")
    if period == "3months":
        return (n - timedelta(days=90)).strftime("%Y-%m-%d 00:00:00")
    if period == "year":
        return n.strftime("%Y-01-01 00:00:00")
    return "0000-01-01 00:00:00"


# Dash natijasi qisqa muddat keshlanadi: ma'lumot o'zgarmagan bo'lsa (change_ver) va
# 15 soniya o'tmagan bo'lsa — avto-yangilanish va bir nechta admin bazani qayta hisoblatmaydi.
_DASH_TTL = 15
_DASH_CACHE: dict = {}


async def api_admin_dash(request):
    tg = await _auth_admin(request, request.query)
    if not tg:
        return _json({"ok": False, "error": "auth"}, 401)
    qs = request.query
    key = (qs.get("period", "week"), qs.get("gran") or "auto", qs.get("from") or "", qs.get("to") or "")
    ver, now_ = q.change_ver(), time.monotonic()
    hit = _DASH_CACHE.get(key)
    if hit and hit[0] == ver and now_ - hit[1] < _DASH_TTL:
        data = hit[2]
    else:
        data = await _admin_dash_data(qs)
        if len(_DASH_CACHE) > 50:
            _DASH_CACHE.clear()
        _DASH_CACHE[key] = (ver, now_, data)
    return _json({**data, "mk": _media_key()})


async def _admin_dash_data(query) -> dict:
    period = query.get("period", "week")
    gran_req = (query.get("gran") or "auto").strip()
    f_ = query.get("from") or ""
    t_ = query.get("to") or ""
    until = None
    from datetime import datetime as _dt0, timedelta as _td0
    from config import now_local as _nl2
    if period == "custom" and f_ and t_:
        try:
            fd = _dt0.strptime(f_[:10], "%Y-%m-%d")
            td_ = _dt0.strptime(t_[:10], "%Y-%m-%d")
            if td_ < fd:
                fd, td_ = td_, fd
            since = fd.strftime("%Y-%m-%d 00:00:00")
            until = (td_ + _td0(days=1)).strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            period = "week"
            since = _period_start_str(period)
    else:
        since = _period_start_str(period)
        if period == "lastweek":
            # o'tgan hafta: dushanba–yakshanba (until = joriy hafta boshi)
            _n = _nl2()
            until = (_n - _td0(days=_n.weekday())).strftime("%Y-%m-%d 00:00:00")
    # Davr uzunligi (kunlarda) — kesim (gran) avto-tanlash va himoya uchun
    _end_date = (_dt0.strptime(until[:10], "%Y-%m-%d").date() if until
                 else (_nl2() + _td0(days=1)).date())
    span_days = max((_end_date - _dt0.strptime(since[:10], "%Y-%m-%d").date()).days, 1)

    def _auto_gran():
        if span_days > 180:
            return "month"
        if span_days > 31:
            return "week"
        if span_days <= 1:
            return "hour"
        return "day"

    # "Kesim/Taqqoslash" — Davrdan MUSTAQIL ikkinchi filtr. 'auto' bo'lsa davrga moslanadi.
    if gran_req in ("hour", "day", "week", "month"):
        gran = gran_req
        # juda ko'p ustun chiqib ketmasligi uchun himoya
        if gran == "hour" and span_days > 2:
            gran = _auto_gran()
        elif gran == "day" and span_days > 370:
            gran = _auto_gran()
    else:
        gran = _auto_gran()

    rep = await q.period_report(since, until)
    hours = await q.hourly_load(since, until)
    live = await q.live_stats()
    series_rows = await q.series_counts(since, gran, until)
    # Vaqt o'qi UZLUKSIZ bo'lsin: bo'sh soat/kun/hafta/oylar 0 bilan to'ldiriladi
    smap = {r["d"]: (r["total"], r["done"] or 0, r["canceled"] or 0) for r in series_rows}
    _UZ_MON = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
               "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
    import calendar as _cal
    series = []
    if gran == "hour":
        # bugun -> 00:00 dan hozirgi soatgacha; o'tgan kun -> 00:00-23:00
        end_h = _nl2().hour if not until else 23
        if until:
            lastd = (_dt0.strptime(until[:10], "%Y-%m-%d") - _td0(days=1)).date()
            if lastd >= _nl2().date():
                end_h = _nl2().hour
        for h in range(0, end_h + 1):
            k = f"{h:02d}:00"
            t, dn, cn = smap.get(k, (0, 0, 0))
            series.append({"d": k, "total": t, "done": dn, "canceled": cn,
                           "lab": f"Soat {h:02d}:00–{h:02d}:59"})
    elif gran == "day":
        cur = _dt0.strptime(since[:10], "%Y-%m-%d")
        endd = (_dt0.strptime(until[:10], "%Y-%m-%d") - _td0(days=1)) if until             else _dt0.strptime(_nl2().strftime("%Y-%m-%d"), "%Y-%m-%d")
        while cur <= endd and len(series) < 370:
            k = cur.strftime("%Y-%m-%d")
            t, dn, cn = smap.get(k, (0, 0, 0))
            series.append({"d": k, "total": t, "done": dn, "canceled": cn,
                           "lab": f"{cur.day}-{_UZ_MON[cur.month]} {cur.year}"})
            cur += _td0(days=1)
    elif gran == "week":
        # Kunma-kun yurib, har hafta kalitini (SQLite '%Y-W%W' bilan bir xil) bir marta qo'shamiz
        cur = _dt0.strptime(since[:10], "%Y-%m-%d")
        endd = (_dt0.strptime(until[:10], "%Y-%m-%d") - _td0(days=1)) if until             else _dt0.strptime(_nl2().strftime("%Y-%m-%d"), "%Y-%m-%d")
        seen = set()
        _guard = 0
        while cur <= endd and len(series) < 200 and _guard < 800:
            k = cur.strftime("%Y-W%W")
            if k not in seen:
                seen.add(k)
                t, dn, cn = smap.get(k, (0, 0, 0))
                # Haftaning haqiqiy oralig'i: dushanba–yakshanba
                mon = cur - _td0(days=cur.weekday())
                sun = mon + _td0(days=6)
                if mon.month == sun.month:
                    lab = f"{mon.day}–{sun.day}-{_UZ_MON[mon.month]}"
                else:
                    lab = f"{mon.day}-{_UZ_MON[mon.month]} – {sun.day}-{_UZ_MON[sun.month]}"
                series.append({"d": k, "total": t, "done": dn, "canceled": cn, "lab": lab})
            cur += _td0(days=1)
            _guard += 1
    else:  # month
        sy, sm = int(since[:4]), int(since[5:7])
        endd = (_dt0.strptime(until[:10], "%Y-%m-%d") - _td0(days=1)) if until else _nl2()
        ey, em = endd.year, endd.month
        while (sy, sm) <= (ey, em) and len(series) < 60:
            k = f"{sy:04d}-{sm:02d}"
            t, dn, cn = smap.get(k, (0, 0, 0))
            last = _cal.monthrange(sy, sm)[1]
            series.append({"d": k, "total": t, "done": dn, "canceled": cn,
                           "lab": f"{_UZ_MON[sm]} {sy} (1–{last})"})
            sm += 1
            if sm > 12:
                sm = 1
                sy += 1
    rating, rated = await q.period_rating(since)
    ops = []
    for o in live["per_op"]:
        st = "offline" if not o["telegram_id"] else ("busy" if o["availability"] == "busy" else "free")
        ops.append({"id": o["id"], "name": o["name"], "state": st,
                    "cnt": o["cnt"], "done_today": o["done_today"]})
    # Hozir javob kutayotgan murojaatlar (necha daqiqadan beri)
    from datetime import datetime as _dt
    from config import now_local as _nl
    waiting = []
    for w in await q.waiting_orders():
        try:
            age = int((_nl() - _dt.strptime(w["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() // 60)
        except Exception:
            age = 0
        waiting.append({"id": w["id"], "name": w["full_name"] or "—", "mins": max(age, 0)})
    # Davr ichida eng ko'p murojaat yuborgan mijozlar
    tc_rows, _tc_total = await q.top_clients(since, 6, 0, until)
    topclients = [{"tg": r["telegram_id"], "name": r["full_name"] or r["phone"] or "Mijoz",
                   "phone": r["phone"] or "", "cnt": r["cnt"]} for r in tc_rows]
    # Trend: o'tgan xuddi shunday davr bilan taqqoslash (kartalarda ↑/↓ %)
    trend = {"total": None, "done": None}
    if period in ("today", "week", "lastweek", "month", "3months", "year", "custom"):
        from datetime import datetime as _dt2, timedelta as _td2
        st = _dt2.strptime(since, "%Y-%m-%d %H:%M:%S")
        if period == "today":
            pst = st - _td2(days=1)
        elif period in ("week", "lastweek"):
            pst = st - _td2(days=7)
        elif period == "month":
            pst = (st - _td2(days=1)).replace(day=1)
        elif period in ("3months", "custom"):
            pst = st - _td2(days=span_days)
        else:
            pst = st.replace(year=st.year - 1)
        pt, pd = await q.counts_between(pst.strftime("%Y-%m-%d %H:%M:%S"), since)
        if pt:
            trend["total"] = round((rep["total"] - pt) / pt * 100)
        if pd:
            trend["done"] = round((rep["done"] - pd) / pd * 100)
    # Operatorlar taqqoslash (davr bo'yicha yakunlar) + filial kesimi
    oprep = await q.operators_report(since, until)
    opstats = sorted([{"name": o["name"], "done": o["done"]} for o in oprep if o["done"]],
                     key=lambda x: x["done"], reverse=True)[:8]
    branches = [{"name": b["name"], "cnt": b["cnt"]} for b in await q.branch_counts(since, until)]
    heat = await q.heatmap_data(since, until or q.now())
    tagc = [{"name": n, "cnt": c} for n, c in await q.tag_counts(since, until)][:10]
    try:
        esc_min = int(await q.get_setting("escalate_min", "5") or 5)
    except ValueError:
        esc_min = 5
    return {"ok": True, "period": period, "gran": gran, "waiting": waiting, "topclients": topclients,
                  "tags": tagc, "escalate_min": esc_min,
                  "pauses": await q.pause_stats(since, until),
                  "opstats": opstats, "branches": branches, "trend": trend, "heatmap": heat,
                  "kpi": {"total": rep["total"], "new": rep["new"], "prog": rep["prog"],
                          "done": rep["done"], "canceled": rep["canceled"],
                          "delivery": rep["delivery"], "pickup": rep["pickup"],
                          "resp": rep["resp"], "resol": rep["resol"],
                          "rating": rating, "rated": rated, "online": live["online"]},
                  "series": series,
                  "hours": [{"h": h, "c": hours.get(h, 0)} for h in range(24)],
                  "ops": ops}


# ---------------- Admin: murojaatlar ro'yxati + yozishma ----------------
async def api_admin_orders(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        page = int(request.query.get("page", "0") or 0)
    except ValueError:
        page = 0
    search = request.query.get("q") or None
    status = request.query.get("status") or None
    period = request.query.get("period") or None
    since = _period_start_str(period) if period and period != "all" else None
    tag = (request.query.get("tag") or "").strip() or None
    rows, total = await q.orders_page(20, page * 20, search, status, since, tag)
    items = [{"id": r["id"], "name": r["full_name"] or "—", "phone": r["phone"] or "",
              "status": r["status"], "operator": r["operator"] or "",
              "bill": bool((r["bill"] or "").strip()),   # hisob-kitob qilinganmi
              "tags": [t for t in (r["tags"] or "").split(",") if t],
              "paused": bool(r["paused_at"]),
              "time": (r["created_at"] or "")[5:16], "rating": r["rating"] or 0} for r in rows]
    return _json({"ok": True, "total": total, "page": page, "items": items,
                  "tag_preset": await _tag_preset()})


async def api_admin_msgs(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(request.query.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    user = await q.get_user(order["user_id"])
    op = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    msgs = await q.order_messages(order_id)
    out = []
    for m in await _msgs_with_replies(msgs):
        m["bill"] = (m["text"] or "").startswith(BILL_TAG)   # hisob-kitob alohida rangda
        out.append(m)
    # Ichki izohlar va o'chirilgan xabarlar (asl nusxasi) — vaqt bo'yicha yozishmaga qo'shiladi
    for n in await q.internal_notes(order_id):
        nj = _note_json(n)
        out.append({"kind": "note", "own": False, "type": "note", "text": nj["text"],
                    "author": nj["author"], "akind": nj["kind"], "ts": nj["ts"], "time": nj["time"]})
    for p_ in await q.order_pauses(order_id):
        out.append({"kind": "pause", "own": False, "type": "pause", "text": p_["reason"] or "",
                    "start": p_["started_at"], "end": p_["ended_at"] or "", "minutes": round(p_["minutes"] or 0),
                    "by": p_["ended_by"] or "", "ts": p_["started_at"], "time": (p_["started_at"] or "")[11:16]})
    for d in await q.deleted_messages(order_id):
        try:
            det = json.loads(d["details"] or "{}")
        except Exception:
            det = {}
        out.append({"kind": "deleted", "own": True, "type": det.get("type") or "text",
                    "text": det.get("text") or "", "file_id": det.get("file_id") or "",
                    "by": d["actor"], "deleted_at": d["at"],
                    "ts": det.get("sent_at") or d["at"], "time": (det.get("sent_at") or d["at"] or "")[11:16]})
    out.sort(key=lambda x: x.get("ts") or "")
    # Yozishmada xabar bo'lmasa ham (bot orqali «saqlangan» hisob-kitob) ko'rinib tursin
    bill_text = (order["bill"] or "") if "bill" in order.keys() else ""
    bill_photo = (order["bill_photo"] or "") if "bill_photo" in order.keys() else ""
    return _json({"ok": True, "order_id": order_id, "status": order["status"],
                  "operator": op["name"] if op else "",
                  "tags": [t for t in (order["tags"] or "").split(",") if t],
                  "paused": bool(order["paused_at"]), "paused_total_min": round(order["paused_total_min"] or 0),
                  "mk": _media_key(),
                  "rating": order["rating"] or 0,
                  "feedback": (order["feedback"] or "") if "feedback" in order.keys() else "",
                  "bill": {"text": bill_text, "photo": bill_photo},
                  "client": {"tg": order["user_id"],
                             "name": user["full_name"] if user else "—",
                             "phone": user["phone"] if user else ""},
                  "messages": out})


async def api_admin_close(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order = await q.get_order(order_id)
    if not order or order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Bu murojaat allaqachon yopilgan"})
    from utils import cbot
    from handlers.operator import _finish_with_rating
    await _finish_with_rating(cbot(), order_id, f"admin:{tg}")
    await q.audit(f"admin:{tg}", "close", order_id)
    return _json({"ok": True})


# ---------------- Admin: mijozlar ----------------
async def api_admin_clients(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        page = int(request.query.get("page", "0") or 0)
    except ValueError:
        page = 0
    search = request.query.get("q") or None
    rows, total = await q.users_page(20, page * 20, search)
    items = [{"tg": r["telegram_id"], "name": r["full_name"] or r["phone"] or "Mijoz",
              "phone": r["phone"] or "", "branch": r["branch"] or "", "cnt": r["cnt"],
              "last": (r["last_at"] or "")[:10]} for r in rows]
    return _json({"ok": True, "total": total, "page": page, "items": items})


async def api_admin_client(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        tg_ = int(request.query.get("tg"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "tg"}, 400)
    u = await q.user_full(tg_)
    if not u:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    orders = await q.orders_by_user(tg_)
    note = await q.get_client_note(tg_)
    return _json({"ok": True,
                  "client": {"tg": tg_, "name": u["full_name"] or u["phone"] or "Mijoz", "phone": u["phone"] or "",
                             "branch": u["branch"] or "", "reg": (u["registered_at"] or "")[:10],
                             "blocked": u["status"] == "blocked", "note": note},
                  "orders": [{"id": o["id"], "status": o["status"],
                              "date": (o["created_at"] or "")[:10],
                              "rating": o["rating"] or 0} for o in orders[:30]]})


# ================= Admin: OPERATORLAR BOSHQARUVI =================
async def api_admin_ops(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    ops = await q.list_operators()
    bots = {b["id"]: b["username"] for b in await q.list_operator_bots()}
    items = []
    for o in ops:
        items.append({"id": o["id"], "name": o["name"],
                      "display_name": o["display_name"] or "", "login": o["login"],
                      "active": o["status"] == "active",
                      "online": bool(o["telegram_id"]),
                      "avail": o["availability"],
                      "ws": o["work_start"], "we": o["work_end"],
                      "bot": ("@" + bots[o["bot_id"]]) if o["bot_id"] in bots else "asosiy bot"})
    return _json({"ok": True, "items": items})


async def api_admin_op_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    name = str(body.get("name", "")).strip()
    display_name = str(body.get("display_name", "")).strip()
    login = str(body.get("login", "")).strip()
    password = str(body.get("password", "")).strip()
    ws = str(body.get("ws", "08:00")).strip() or "08:00"
    we = str(body.get("we", "23:00")).strip() or "23:00"
    oid = body.get("id")
    if not name or not login:
        return _json({"ok": False, "error": "Ism va login bo'sh bo'lmasin"})
    existing = await q.get_operator_by_login(login)
    if existing and (not oid or existing["id"] != int(oid)):
        return _json({"ok": False, "error": "Bu login band"})
    if oid:
        oid = int(oid)
        await q.update_operator(oid, "name", name)
        await q.update_operator(oid, "display_name", display_name)
        await q.update_operator(oid, "login", login)
        await q.update_operator(oid, "work_start", ws)
        await q.update_operator(oid, "work_end", we)
        if password:
            await q.update_operator_password(oid, password)
            await q.clear_operator_session(oid)
            await q.audit(f"admin:{body.get('admin_id')}", "op_password", None, {"operator": name})
    else:
        if not password:
            return _json({"ok": False, "error": "Parol kiriting"})
        new_id = await q.add_operator(name, login, password, bot_id=None)
        if display_name:
            await q.update_operator(new_id, "display_name", display_name)
    return _json({"ok": True})


async def api_admin_op_toggle(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    oid = int(body.get("id"))
    op = await q.get_operator(oid)
    if not op:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    new = "inactive" if op["status"] == "active" else "active"
    await q.update_operator(oid, "status", new)
    await q.audit(f"admin:{body.get('admin_id')}", "op_" + new, None, {"operator": op["name"]})
    if new == "inactive" and op["telegram_id"]:
        await q.logout_operator(op["telegram_id"], op["bot_id"])
    return _json({"ok": True, "active": new == "active"})


async def api_admin_op_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    dop = await q.get_operator(int(body.get("id")))
    await q.delete_operator(int(body.get("id")))
    await q.audit(f"admin:{body.get('admin_id')}", "op_delete", None,
                  {"operator": dop["name"] if dop else body.get("id")})
    return _json({"ok": True})


async def api_admin_op_logout(request):
    """Operatorning barcha mini app sessiyalarini bekor qiladi (telefon yo'qolsa va h.k.)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    try:
        oid = int(body.get("id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    await q.bump_operator_epoch(oid)
    await q.clear_operator_session(oid)
    await q.audit(f"admin:{body.get('admin_id')}", "op_sessions_revoked", None, {"operator_id": oid})
    return _json({"ok": True})


async def api_admin_op_detail(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    try:
        oid = int(request.query.get("id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    op = await q.get_operator(oid)
    if not op:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    s = await q.operator_stats(oid)
    recent = await q.orders_by_operator(oid)
    return _json({"ok": True,
                  "op": {"name": op["name"], "display_name": op["display_name"] or "",
                         "login": op["login"],
                         "active": op["status"] == "active", "online": bool(op["telegram_id"]),
                         "ws": op["work_start"], "we": op["work_end"]},
                  "stats": s,
                  "recent": [{"id": r["id"], "name": r["full_name"] or "—", "status": r["status"],
                              "date": (r["created_at"] or "")[:10], "rating": r["rating"] or 0}
                             for r in recent[:15]]})


async def api_admin_opbots(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    bots = await q.list_operator_bots()
    items = []
    for b in bots:
        ops = await q.operators_by_bot(b["id"])
        items.append({"id": b["id"], "username": b["username"], "title": b["title"],
                      "enabled": bool(b["enabled"]), "ops": len(ops),
                      "logins": ", ".join(o["login"] for o in ops)})
    return _json({"ok": True, "items": items})


async def api_admin_opbot_add(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    token = str(body.get("token", "")).strip()
    login = str(body.get("login", "")).strip()
    password = str(body.get("password", "")).strip()
    if not token or not login or not password:
        return _json({"ok": False, "error": "Token, login va parolni kiriting"})
    if await q.get_operator_bot_by_token(token):
        return _json({"ok": False, "error": "Bu bot allaqachon qo'shilgan"})
    if await q.get_operator_by_login(login):
        return _json({"ok": False, "error": "Bu login band"})
    from aiogram import Bot as _TgBot
    try:
        tb = _TgBot(token)
        me = await tb.get_me()
        await tb.session.close()
    except Exception:
        return _json({"ok": False, "error": "Token noto'g'ri yoki bot topilmadi"})
    bot_id = await q.add_operator_bot(token, me.username, me.first_name)
    await q.add_operator(me.first_name, login, password, bot_id=bot_id)
    import botreg
    try:
        await botreg.start_operator_bot(bot_id, token)
    except Exception:
        pass
    return _json({"ok": True, "username": me.username})


async def api_admin_opbot_toggle(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    bid = int(body.get("id"))
    b = await q.get_operator_bot(bid)
    if not b:
        return _json({"ok": False}, 404)
    import botreg
    new = not b["enabled"]
    await q.set_operator_bot_enabled(bid, new)
    try:
        if new:
            await botreg.start_operator_bot(bid, b["token"])
        else:
            await botreg.stop_operator_bot(bid)
    except Exception:
        pass
    return _json({"ok": True, "enabled": new})


async def api_admin_opbot_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    bid = int(body.get("id"))
    import botreg
    try:
        await botreg.stop_operator_bot(bid)
    except Exception:
        pass
    await q.delete_operator_bot(bid)
    return _json({"ok": True})


async def api_admin_lowratings(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    rows = await q.low_rated_orders()
    return _json({"ok": True, "items": [
        {"id": r["id"], "rating": r["rating"], "feedback": r["feedback"] or "",
         "name": r["full_name"] or "—", "operator": r["operator"] or "—",
         "date": (r["closed_at"] or "")[:10]} for r in rows]})


async def api_admin_reviews(request):
    """Barcha otzivlar — yulduz bo'yicha filtr: stars=1..5, 'low' (1-3) yoki bo'sh (hammasi)."""
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    stars = str(request.query.get("stars", "") or "")
    if stars == "low":
        mn, mx = 1, 3
    elif stars in ("1", "2", "3", "4", "5"):
        mn = mx = int(stars)
    else:
        mn, mx = 1, 5
    rows = await q.all_rated_orders(mn, mx, 100)
    return _json({"ok": True, "items": [
        {"id": r["id"], "rating": r["rating"], "feedback": r["feedback"] or "",
         "name": r["full_name"] or "—", "operator": r["operator"] or "—",
         "date": (r["closed_at"] or r["created_at"] or "")[:10]} for r in rows]})


# ---------------- Admin: mijozga yozish + o'tkazish ----------------
async def api_admin_send(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    order = await q.get_order(order_id)
    if not order or order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"})
    import tghtml
    raw = str(body.get("html") or "").strip()
    text = str(body.get("text", "")).strip()
    html_text = tghtml.sanitize(raw or text) if (raw or "<" in text) else None
    if html_text:
        text = tghtml.to_plain(html_text).strip()
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    from utils import cbot, post_operator_to_channel
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    body_html = html_text if (html_text and tghtml.has_markup(html_text)) else _htm.escape(text)
    try:
        snt = await _send_html(
            lambda: client.send_message(order["user_id"], f"👨‍💼 <b>Admin:</b>\n{body_html}"),
            lambda: client.send_message(order["user_id"], f"👨‍💼 <b>Admin:</b>\n{_htm.escape(text)}"))
    except Exception:
        return _json({"ok": False, "error": "Mijozga yuborilmadi"})
    await q.add_message(order_id, "operator", "text", f"👨‍💼 Admin: {text}", None, None,
                        client_msg_id=snt.message_id,
                        html=(f"👨‍💼 <b>Admin:</b> {body_html}" if tghtml.has_markup(body_html) else None))
    await q.audit(f"admin:{tg}", "admin_send", order_id)
    try:
        await post_operator_to_channel(client, order, "Admin", text=text)
    except Exception:
        pass
    return _json({"ok": True})


async def api_admin_transfer(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
        newop_id = int(body.get("operator_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    order = await q.get_order(order_id)
    new_op = await q.get_operator(newop_id)
    if not order or not new_op:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "Murojaat yopilgan"})
    if not await _transfer(order, new_op, f"admin:{tg}", "Admin"):
        return _json({"ok": False, "error": "Murojaat holati o'zgardi, qayta ochib ko'ring"}, 409)
    return _json({"ok": True, "info": f"#{order_id} → {new_op['name']} ga o'tkazildi"})


# ---------------- Admin: mijozni bloklash / to'liq o'chirish / izoh ----------------
async def api_admin_client_block(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    try:
        tg_ = int(body.get("tg"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    block = bool(body.get("block"))
    await q.set_user_status(tg_, "blocked" if block else "active")
    await q.audit(f"admin:{body.get('admin_id')}", "client_block" if block else "client_unblock",
                  None, {"client": tg_})
    return _json({"ok": True, "blocked": block})


async def api_admin_client_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    try:
        tg_ = int(body.get("tg"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    n = await q.delete_client_full(tg_)
    await q.audit(f"admin:{body.get('admin_id')}", "client_delete", None, {"client": tg_, "orders": n})
    return _json({"ok": True, "orders_removed": n})


async def api_admin_note_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    try:
        tg_ = int(body.get("tg"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    await q.set_client_note(tg_, str(body.get("note", "")).strip())
    return _json({"ok": True})


# ---------------- Admin: mijoz otzivini (baho + izoh) tahrirlash / o'chirish ----------------
async def api_admin_review(request):
    """Otziv boshqaruvi. body:
      order_id                              — majburiy
      delete=True                           — otzivni butunlay o'chirish (baho+izoh NULL)
      rating (0..5)                         — bahoni o'zgartirish (0 = bahoni o'chirish)
      feedback (matn)                       — izohni tahrirlash ("" = izohni o'chirish)
    'rating' yoki 'feedback' kalitini yubormasangiz — o'sha qism o'zgarmaydi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False, "error": "auth"}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "order_id"}, 400)
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "topilmadi"}, 404)

    await q.audit(f"admin:{body.get('admin_id')}", "review_delete" if body.get("delete") else "review_edit",
                  order_id, {"old_rating": order["rating"], "old_feedback": order["feedback"] or ""})
    if body.get("delete"):
        await q.set_order_rating(order_id, None)
        await q.set_order_feedback(order_id, None)
        return _json({"ok": True, "rating": 0, "feedback": ""})

    if "rating" in body:
        try:
            rv = int(body.get("rating"))
        except (TypeError, ValueError):
            rv = 0
        await q.set_order_rating(order_id, rv if 1 <= rv <= 5 else None)
    if "feedback" in body:
        fb = str(body.get("feedback", "")).strip()
        await q.set_order_feedback(order_id, fb or None)

    upd = await q.get_order(order_id)
    return _json({"ok": True, "rating": upd["rating"] or 0,
                  "feedback": (upd["feedback"] or "") if "feedback" in upd.keys() else ""})


# ---------------- Admin: eski ochiq murojaatlarni yopish ----------------
async def api_admin_close_stale(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    try:
        days = max(1, min(int(body.get("days", 7)), 90))
    except (TypeError, ValueError):
        days = 7
    from datetime import timedelta
    from config import now_local
    cutoff = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = await q.stale_open_orders(cutoff)
    for r in rows:
        await q.set_order_status(r["id"], "done", f"admin:stale:{tg}")
        if r["operator_id"]:
            await q.set_operator_active_order(r["operator_id"], None)
            await q.set_operator_availability(r["operator_id"], "free")
        await q.set_user_active_order(r["user_id"], None)
    await q.audit(f"admin:{tg}", "close_stale", None, {"days": days, "closed": len(rows)})
    return _json({"ok": True, "closed": len(rows)})


async def api_admin_bc_pending(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    rows = await q.pending_sched_bc()
    return _json({"ok": True, "items": [
        {"id": r["id"], "text": (r["text"] or "")[:60], "target": r["target"],
         "send_at": r["send_at"], "has_media": bool(r["has_media"])} for r in rows]})


async def api_admin_bc_cancel(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    await q.delete_sched_bc(int(body.get("id")))
    return _json({"ok": True})


# ================= Admin: SOZLAMALAR (3-bosqich) =================
async def api_admin_branches(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    bs = await q.list_branches()
    return _json({"ok": True, "items": [
        {"id": b["id"], "name": b["name"], "address": b["address"] or "",
         "phone": b["phone"] or "", "open": b["open_time"], "close": b["close_time"],
         "region": b["region"] or "", "has_loc": b["lat"] is not None} for b in bs]})


async def api_admin_branch_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    name = str(body.get("name", "")).strip()
    if not name:
        return _json({"ok": False, "error": "Nomi bo'sh"})
    addr = str(body.get("address", "")).strip()
    phone = str(body.get("phone", "")).strip()
    open_t = str(body.get("open", "08:00")).strip() or "08:00"
    close_t = str(body.get("close", "23:00")).strip() or "23:00"
    region = str(body.get("region", "")).strip()
    bid = body.get("id")
    if bid:
        for f, v in (("name", name), ("address", addr), ("phone", phone),
                     ("open_time", open_t), ("close_time", close_t), ("region", region)):
            await q.update_branch(int(bid), f, v)
    else:
        await q.add_branch(name, addr, phone, open_time=open_t, close_time=close_t, region=region)
    return _json({"ok": True})


async def api_admin_branch_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    await q.delete_branch(int(body.get("id")))
    return _json({"ok": True})


async def api_admin_faqs(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    fs = await q.list_faqs()
    return _json({"ok": True, "items": [
        {"id": f["id"], "title": f["title"], "answer": f["answer"]} for f in fs]})


async def api_admin_faq_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    title = str(body.get("title", "")).strip()
    answer = str(body.get("answer", "")).strip()
    if not title or not answer:
        return _json({"ok": False, "error": "Sarlavha va javob bo'sh bo'lmasin"})
    fid = body.get("id")
    if fid:
        await q.update_faq(int(fid), title, answer)
    else:
        await q.add_faq(title, answer)
    return _json({"ok": True})


async def api_admin_faq_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    await q.delete_faq(int(body.get("id")))
    return _json({"ok": True})


async def api_admin_tpls(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    ts = await q.list_templates()
    return _json({"ok": True, "items": [
        {"id": t["id"], "text": t["text"] or "", "sticker": bool(t["sticker"])} for t in ts]})


async def api_admin_tpl_add(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    text = str(body.get("text", "")).strip()
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    await q.add_template(text)
    return _json({"ok": True})


async def api_admin_tpl_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    await q.delete_template(int(body.get("id")))
    return _json({"ok": True})


async def api_admin_settings(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    return _json({"ok": True,
                  "work_start": await q.get_setting("work_start", "08:00"),
                  "work_end": await q.get_setting("work_end", "23:00"),
                  "op_work_start": await q.get_setting("op_work_start", "08:00"),
                  "op_work_end": await q.get_setting("op_work_end", "23:00"),
                  "escalate_min": await q.get_setting("escalate_min", "5"),
                  "auto_assign": await q.get_setting("auto_assign", "off"),
                  "sla_target_min": await q.get_setting("sla_target_min", "5"),
                  "tags_preset": await q.get_setting("tags_preset", ""),
                  "daily_report": await q.get_setting("daily_report", "21:00"),
                  "op_daily_goal": await q.get_setting("op_daily_goal", "0"),
                  "contact_text": await q.get_setting("contact_text", "")})


async def api_admin_settings_save(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not await _auth_admin(request, body):
        return _json({"ok": False}, 401)
    changed = {}
    for k in ("work_start", "work_end", "op_work_start", "op_work_end",
              "escalate_min", "contact_text", "auto_assign", "sla_target_min", "tags_preset",
              "daily_report", "op_daily_goal"):
        if k == "daily_report" and k in body and str(body[k]).strip() in ("", "off"):
            await q.set_setting(k, "")
            changed[k] = "off"
            continue
        if k in body and str(body[k]).strip() != "":
            v = str(body[k]).strip()
            if k == "auto_assign" and v not in ("off", "rr", "least"):
                continue
            await q.set_setting(k, v)
            changed[k] = v[:80]
    if changed:
        await q.audit(f"admin:{body.get('admin_id')}", "settings", None, changed)
    return _json({"ok": True})


# ---------------- Admin: adminlarni boshqarish ----------------
async def api_admin_admins(request):
    tg = await _auth_admin(request, request.query)
    if not tg:
        return _json({"ok": False}, 401)
    items = []
    disabled = await q.disabled_admin_ids()
    mgr = await q.get_manager_admin_id()
    seen = set()
    # .env ADMIN_IDS (bosh admin bu ro'yxatda) — CRM'dan o'chirilganlari ko'rinmaydi
    for aid in ADMIN_IDS:
        if aid in disabled or aid in seen:
            continue
        seen.add(aid)
        u = await q.get_user(aid)
        items.append({
            "telegram_id": aid,
            "username": (u["username"] if u and u["username"] else None),
            "name": (u["full_name"] if u and u["full_name"] else "Admin"),
            "super": _is_super(aid), "manager": (mgr is not None and aid == mgr),
            "you": aid == tg})
    # DB'dan qo'shilganlar
    for a in await q.list_admins():
        aid = a["telegram_id"]
        if aid is not None and aid in seen:
            continue
        if aid is not None:
            seen.add(aid)
        items.append({
            "telegram_id": aid,
            "username": a["username"],
            "name": a["name"] or (("@" + a["username"]) if a["username"]
                                  else str(aid)),
            "pending": aid is None,
            "role": (a["role"] if "role" in a.keys() and a["role"] else "admin"),
            "super": False, "manager": (mgr is not None and aid == mgr),
            "you": aid == tg})
    return _json({"ok": True, "items": items,
                  "me_super": bool(_is_super(tg)),
                  "me_can_manage": await _can_manage_admins(tg)})


async def api_admin_admin_add(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    if not await _can_manage_admins(tg):
        return _json({"ok": False, "error": "Sizda admin qo'shish huquqi yo'q"}, 403)
    ident = str(body.get("ident", "")).strip()
    if not ident:
        return _json({"ok": False, "error": "ID yoki username kiriting"})

    telegram_id = None
    username = None
    name = None
    if ident.lstrip("@").isdigit() and not ident.startswith("@"):
        # Raqam — telegram_id
        telegram_id = int(ident)
        u = await q.get_user(telegram_id)
        if u:
            username = u["username"]
            name = u["full_name"]
    else:
        # Username
        username = ident.lstrip("@").strip()
        if not username:
            return _json({"ok": False, "error": "Username noto'g'ri"})
        u = await q.find_user_by_username(username)
        if u:
            telegram_id = u["telegram_id"]
            name = u["full_name"]

    # Avval o'chirilgan .env admini bo'lsa — qayta faollashtiramiz
    if telegram_id is not None and telegram_id in ADMIN_IDS:
        if telegram_id in await q.disabled_admin_ids():
            await q.set_admin_disabled(telegram_id, False)
            from utils import refresh_admins
            await refresh_admins()
            return _json({"ok": True, "pending": False})
        return _json({"ok": False, "error": "Bu foydalanuvchi allaqachon admin"})

    # Allaqachon adminmi?
    if telegram_id is not None and await q.admin_exists(telegram_id=telegram_id):
        return _json({"ok": False, "error": "Bu foydalanuvchi allaqachon admin"})
    if username and await q.admin_exists(username=username):
        return _json({"ok": False, "error": "Bu username allaqachon admin"})

    await q.add_admin(telegram_id, username, name, added_by=tg)
    from utils import refresh_admins
    await refresh_admins()
    pending = telegram_id is None
    return _json({"ok": True, "pending": pending})


async def api_admin_admin_del(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    if not await _can_manage_admins(tg):
        return _json({"ok": False, "error": "Sizda admin o'chirish huquqi yo'q"}, 403)
    tid = body.get("telegram_id")
    username = body.get("username")
    try:
        tid = int(tid) if tid is not None and str(tid) != "" else None
    except (TypeError, ValueError):
        tid = None
    # O'zini o'chirib qo'yishdan saqlaymiz
    if tid is not None and tid == tg:
        return _json({"ok": False, "error": "O'zingizni o'chira olmaysiz"})
    # Bosh admin (super-admin) hech qachon o'chirilmaydi.
    if tid is not None and _is_super(tid):
        return _json({"ok": False, "error": "Bosh adminni o'chirib bo'lmaydi"})
    # Tayinlangan asosiy admin o'chirilsa — tayinlashni ham bekor qilamiz.
    mgr = await q.get_manager_admin_id()
    if tid is not None and mgr is not None and tid == mgr:
        await q.set_manager_admin_id(None)
    # .env adminini bazadan o'chirib bo'lmaydi (u .env'da yozilgan), shuning uchun
    # uni «o'chirilgan» deb belgilaymiz — admin huquqi va bildirishnomalari olib tashlanadi.
    if tid is not None and tid in ADMIN_IDS:
        await q.set_admin_disabled(tid, True)
    else:
        await q.remove_admin(telegram_id=tid, username=username)
    from utils import refresh_admins
    await refresh_admins()
    return _json({"ok": True})


async def api_admin_set_manager(request):
    """Bosh admin (SUPER_ADMIN_ID) bitta «asosiy admin»ni tanlaydi/bekor qiladi.
    Asosiy admin admin qo'sha/o'chira oladi; boshqa adminlar bu ishni qila olmaydi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    if not _is_super(tg):
        return _json({"ok": False, "error": "Faqat bosh admin asosiy admin tayinlaydi"}, 403)
    tid = body.get("telegram_id")
    try:
        tid = int(tid) if tid is not None and str(tid) != "" else None
    except (TypeError, ValueError):
        tid = None
    if tid is None:
        await q.set_manager_admin_id(None)   # bekor qilish
        return _json({"ok": True, "manager_id": None})
    if _is_super(tid):
        return _json({"ok": False, "error": "Bosh admin allaqachon to'liq huquqli"})
    # Tanlangan shaxs haqiqatan admin bo'lishi shart.
    if not await _is_admin(tid):
        return _json({"ok": False, "error": "Avval bu shaxsni admin qiling"})
    await q.set_manager_admin_id(tid)
    return _json({"ok": True, "manager_id": tid})


# ---------------- Admin: bildirishnomalar (kim «Javobsiz murojaat» oladi) ----------------
async def api_admin_notify_list(request):
    tg = await _auth_admin(request, request.query)
    if not tg:
        return _json({"ok": False}, 401)
    disabled = await q.disabled_admin_ids()
    sel = await q.notify_admin_ids()   # None bo'lsa — hammaga yoqilgan

    def _on(aid):
        return True if sel is None else (aid in sel)

    items = []
    seen = set()
    for aid in ADMIN_IDS:
        if aid in disabled or aid in seen:
            continue
        seen.add(aid)
        u = await q.get_user(aid)
        items.append({
            "telegram_id": aid,
            "name": (u["full_name"] if u and u["full_name"] else "Admin"),
            "username": (u["username"] if u and u["username"] else None),
            "on": _on(aid)})
    for a in await q.list_admins():
        aid = a["telegram_id"]
        if aid is None or aid in seen:
            continue   # hali botni ochmagan (pending) admin bildirishnoma ololmaydi
        seen.add(aid)
        items.append({
            "telegram_id": aid,
            "name": a["name"] or (("@" + a["username"]) if a["username"] else str(aid)),
            "username": a["username"],
            "on": _on(aid)})
    return _json({"ok": True, "items": items})


async def api_admin_notify_toggle(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    try:
        tid = int(body.get("telegram_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "telegram_id noto'g'ri"})
    on = bool(body.get("on"))
    # Joriy holatni aniqlaymiz: sozlanmagan bo'lsa — barcha amaldagi adminlar yoqilgan.
    eff = await q.effective_admin_ids()
    sel = await q.notify_admin_ids()
    cur = set(eff) if sel is None else {i for i in sel if i in eff}
    if on:
        cur.add(tid)
    else:
        cur.discard(tid)
    await q.set_notify_admin_ids(cur)
    return _json({"ok": True})


async def api_admin_broadcast(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    text = str(body.get("text", "")).strip()
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    target = body.get("target", "all")
    branch_id = body.get("branch_id")
    # Rejalashtirilgan yuborish: vaqt berilsa navbatga qo'yiladi (bot fonda yuboradi)
    send_at = str(body.get("send_at", "")).strip()
    if send_at:
        sa = send_at.replace("T", " ")[:16] + ":00"
        if sa <= q.now():
            return _json({"ok": False, "error": "Vaqt kelajakda bo'lishi kerak"})
        await q.add_sched_bc(text, body.get("media_data") or None, target,
                             int(branch_id) if (target == "branch" and branch_id) else None, sa)
        return _json({"ok": True, "scheduled": True, "send_at": sa})
    from utils import cbot
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    if target == "active":
        users = await q.all_users(only_active=True)
    elif target == "branch" and branch_id:
        users = await q.all_users(branch_id=int(branch_id))
    else:
        users = await q.all_users()
    # Rasm bo'lsa: birinchi yuborishda yuklab, keyin file_id bilan (tez)
    media_data = body.get("media_data")
    raw = None
    if media_data:
        try:
            raw = base64.b64decode(str(media_data).split(",")[-1])
        except Exception:
            raw = None
    sent = failed = 0
    fid = None
    for u in users:
        try:
            if raw:
                if fid:
                    await client.send_photo(u["telegram_id"], fid, caption=_htm.escape(text))
                else:
                    s = await client.send_photo(u["telegram_id"],
                                                BufferedInputFile(raw, "elon.jpg"),
                                                caption=_htm.escape(text))
                    fid = s.photo[-1].file_id
            else:
                await client.send_message(u["telegram_id"], _htm.escape(text))
            sent += 1
        except Exception:
            failed += 1
    await q.audit(f"admin:{tg}", "broadcast", None, {"sent": sent, "failed": failed, "text": text[:200]})
    return _json({"ok": True, "sent": sent, "failed": failed, "total": len(users)})


async def api_admin_stats(request):
    """Sozlamalar → Statistika oynasi: umumiy ko'rsatkichlar + filiallar jamlanmasi."""
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    g = await q.general_stats()
    brs = await q.branches_overview()
    return _json({"ok": True,
                  "general": {
                      "users_total": g["users_total"], "users_today": g["users_today"],
                      "users_yesterday": g["users_yesterday"],
                      "users_week": g["users_week"], "users_month": g["users_month"],
                      "orders_total": g["orders_total"], "orders_today": g["orders_today"],
                      "orders_week": g["orders_week"], "orders_new": g["orders_new"],
                      "orders_progress": g["orders_progress"], "orders_done": g["orders_done"],
                      "orders_canceled": g["orders_canceled"],
                      "avg_rating": g["avg_rating"], "rated_count": g["rated_count"],
                      "avg_response_min": g["avg_response_min"], "avg_resolve_min": g["avg_resolve_min"]},
                  "branches": [{"id": b["id"], "name": b["name"], "clients": b["clients"],
                                "total": b["total"], "done": b["done"],
                                "rating": b["rating"] or 0} for b in brs]})


async def api_admin_branch_detail(request):
    """Bitta filial tafsiloti: mijozlar, holatlar, baho, dinamika, top mijozlar."""
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    try:
        bid = int(request.query.get("branch_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    d = await q.branch_detail(bid)
    if not d:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    return _json({"ok": True,
                  "name": d["branch"]["name"], "phone": d["branch"]["phone"] or "",
                  "address": d["branch"]["address"] or "",
                  "clients": d["clients"], "total": d["total"], "new": d["new"],
                  "prog": d["prog"], "done": d["done"], "canceled": d["canceled"],
                  "rating": d["rating"], "rated": d["rated"], "resolve": d["resolve"],
                  "series": [{"d": s["d"], "total": s["total"], "done": s["done"] or 0}
                             for s in d["series"]],
                  "topclients": [{"tg": c["telegram_id"],
                                  "name": c["full_name"] or c["phone"] or "Mijoz",
                                  "phone": c["phone"] or "", "cnt": c["cnt"]}
                                 for c in d["topclients"]]})


async def api_admin_excel(request):
    """Excel hisobotni yaratib, adminning Telegram chatiga yuboradi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    from utils import cbot, STATUS_LABEL
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    period = body.get("period") or "all"
    since = _period_start_str(period) if period != "all" else None
    plabel = {"today": "Bugun", "week": "Joriy hafta", "month": "Joriy oy",
              "year": "Joriy yil", "all": "Barcha davr"}.get(period, "Barcha davr")
    import io as _io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    rows = await q.all_orders_full(since)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Murojaatlar"
    # Sarlavha
    ws.merge_cells("A1:K1")
    t1 = ws["A1"]
    t1.value = f"Gulnora Farm — Murojaatlar hisoboti · {plabel} · {q.now()[:16]}"
    t1.font = Font(bold=True, size=13, color="FFFFFF")
    t1.fill = PatternFill("solid", fgColor="2F6FB4")
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    # Ustun sarlavhalari
    headers = ["ID", "Mijoz", "Telefon", "Filial", "Operator", "Holat",
               "Tur", "Hisob", "Boshlangan", "Yakunlangan", "Baho"]
    hfill = PatternFill("solid", fgColor="3390EC")
    thin = Side(style="thin", color="C9D4E0")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=ci, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = hfill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = bd
    ws.row_dimensions[2].height = 20
    st_color = {"new": "B45309", "in_progress": "1D6FBF", "done": "1F7A35", "canceled": "C22F36"}
    zebra = PatternFill("solid", fgColor="F3F7FB")
    for ri, r in enumerate(rows, 3):
        vals = [r["id"], r["full_name"], r["phone"], r["branch"], r["operator"],
                STATUS_LABEL.get(r["status"], r["status"]), r["content_type"],
                r["bill"], r["created_at"], r["closed_at"],
                ("★" * r["rating"]) if r["rating"] else ""]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = bd
            if ri % 2:
                c.fill = zebra
            if ci == 1:
                c.alignment = Alignment(horizontal="center")
            if ci == 6:
                c.font = Font(bold=True, color=st_color.get(r["status"], "000000"), size=10.5)
    for col, w in zip("ABCDEFGHIJK", (7, 22, 17, 20, 16, 15, 11, 18, 17, 17, 10)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A3"

    # ---- 2-varaq: STATISTIKA + diagrammalar ----
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    ws2 = wb.create_sheet("Statistika")
    ws2.merge_cells("A1:D1")
    h2 = ws2["A1"]
    h2.value = f"Umumiy ko'rsatkichlar · {plabel}"
    h2.font = Font(bold=True, size=13, color="FFFFFF")
    h2.fill = PatternFill("solid", fgColor="2F6FB4")
    h2.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 24
    # Holatlar bo'yicha jadval (diagramma manbasi)
    st_counts = {"new": 0, "in_progress": 0, "done": 0, "canceled": 0}
    for r in rows:
        st_counts[r["status"]] = st_counts.get(r["status"], 0) + 1
    ws2["A3"] = "Holat"; ws2["B3"] = "Soni"
    for c in ("A3", "B3"):
        ws2[c].font = Font(bold=True, color="FFFFFF")
        ws2[c].fill = PatternFill("solid", fgColor="3390EC")
        ws2[c].alignment = Alignment(horizontal="center")
    st_names = [("new", "Yangi"), ("in_progress", "Jarayonda"), ("done", "Yakunlangan"), ("canceled", "Bekor")]
    for i, (k, nm) in enumerate(st_names, 4):
        ws2.cell(row=i, column=1, value=nm)
        ws2.cell(row=i, column=2, value=st_counts.get(k, 0))
    pie = PieChart()
    pie.title = "Murojaatlar holati"
    pie.add_data(Reference(ws2, min_col=2, min_row=3, max_row=7), titles_from_data=True)
    pie.set_categories(Reference(ws2, min_col=1, min_row=4, max_row=7))
    pie.dataLabels = DataLabelList(); pie.dataLabels.showPercent = True
    pie.height, pie.width = 7.5, 11
    ws2.add_chart(pie, "D3")
    # Filiallar bo'yicha (yakunlangan)
    br = await q.branch_counts(since or "0000-01-01 00:00:00")
    start_r = 10
    ws2.cell(row=start_r, column=1, value="Filial").font = Font(bold=True, color="FFFFFF")
    ws2.cell(row=start_r, column=2, value="Yakunlangan").font = Font(bold=True, color="FFFFFF")
    for cc in (1, 2):
        ws2.cell(row=start_r, column=cc).fill = PatternFill("solid", fgColor="2F9E44")
        ws2.cell(row=start_r, column=cc).alignment = Alignment(horizontal="center")
    for i, b in enumerate(br, start_r + 1):
        ws2.cell(row=i, column=1, value=b["name"])
        ws2.cell(row=i, column=2, value=b["cnt"])
    if br:
        bar = BarChart(); bar.type = "bar"; bar.title = "Filiallar kesimi (yakunlangan)"
        bar.add_data(Reference(ws2, min_col=2, min_row=start_r, max_row=start_r + len(br)),
                     titles_from_data=True)
        bar.set_categories(Reference(ws2, min_col=1, min_row=start_r + 1, max_row=start_r + len(br)))
        bar.height, bar.width = max(6, len(br) * 1.2), 12
        bar.legend = None
        ws2.add_chart(bar, "D18")
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 13

    buf = _io.BytesIO()
    wb.save(buf)
    try:
        await client.send_document(
            tg, BufferedInputFile(buf.getvalue(), f"hisobot_{period}.xlsx"),
            caption=f"📥 Murojaatlar hisoboti — {plabel} ({len(rows)} ta yozuv)")
    except Exception:
        return _json({"ok": False, "error": "Botga yuborib bo'lmadi"})
    return _json({"ok": True})


async def api_admin_excel_clients(request):
    """Mijozlar ro'yxatini chiroyli Excel qilib admin botiga yuboradi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    from utils import cbot
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    import io as _io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    rows = await q.clients_full()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mijozlar"
    ws.merge_cells("A1:H1")
    t1 = ws["A1"]
    t1.value = f"Gulnora Farm — Mijozlar ro'yxati · {q.now()[:16]} · {len(rows)} ta"
    t1.font = Font(bold=True, size=13, color="FFFFFF")
    t1.fill = PatternFill("solid", fgColor="2F6FB4")
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    headers = ["№", "Ism", "Telefon", "Filial", "Holat", "Ro'yxatdan", "Murojaatlar", "O'rtacha baho"]
    hfill = PatternFill("solid", fgColor="3390EC")
    thin = Side(style="thin", color="C9D4E0")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=ci, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = hfill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = bd
    zebra = PatternFill("solid", fgColor="F3F7FB")
    for ri, r in enumerate(rows, 3):
        vals = [ri - 2, r["full_name"], r["phone"], r["branch"],
                "Bloklangan" if r["status"] == "blocked" else "Faol",
                (r["registered_at"] or "")[:10], r["cnt"],
                r["avg_r"] if r["avg_r"] else ""]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = bd
            if ri % 2:
                c.fill = zebra
            if ci in (1, 7, 8):
                c.alignment = Alignment(horizontal="center")
            if ci == 5 and r["status"] == "blocked":
                c.font = Font(bold=True, color="C22F36", size=10.5)
    for col, w in zip("ABCDEFGH", (6, 24, 18, 20, 12, 13, 12, 13)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A3"
    buf = _io.BytesIO()
    wb.save(buf)
    try:
        await client.send_document(tg, BufferedInputFile(buf.getvalue(), "mijozlar.xlsx"),
                                   caption=f"📥 Mijozlar ro'yxati ({len(rows)} ta)")
    except Exception:
        return _json({"ok": False, "error": "Botga yuborib bo'lmadi"})
    return _json({"ok": True})


# ================= Admin: ICHKI IZOH / AUDIT / SLA / ROLLAR =================
async def api_admin_inote(request):
    """Admin yozishmaga ichki izoh qoldiradi — operator ko'radi, mijozga yuborilmaydi."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return _json({"ok": False}, 400)
    text = str(body.get("text", "")).strip()[:2000]
    if not text:
        return _json({"ok": False, "error": "Matn bo'sh"})
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    u = await q.get_user(tg)
    author = (u["full_name"] if u and u["full_name"] else "Admin")
    await q.add_internal_note(order_id, "admin", author, text)
    await q.audit(f"admin:{tg}", "internal_note", order_id, {"text": text[:200]})
    # Operatorga bot orqali xabar beramiz
    if order["operator_id"]:
        op = await q.get_operator(order["operator_id"])
        if op and op["telegram_id"]:
            import botreg
            from utils import cbot
            b = (botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else None) or cbot()
            try:
                await b.send_message(op["telegram_id"],
                                     f"🔒 <b>Admin izohi</b> (#{order_id}):\n{_htm.escape(text)}")
            except Exception:
                pass
    return _json({"ok": True})


_AUDIT_LBL = {
    "msg_delete": "Xabar o'chirildi", "msg_edit": "Xabar tahrirlandi", "close": "Yakunlandi",
    "hide_chat": "Chat yashirildi", "reopen": "Qayta ochildi", "transfer": "O'tkazildi",
    "client_block": "Mijoz bloklandi", "client_unblock": "Blokdan ochildi",
    "client_delete": "Mijoz o'chirildi", "op_password": "Operator paroli o'zgardi",
    "op_active": "Operator yoqildi", "op_inactive": "Operator o'chirildi (faolsiz)",
    "op_delete": "Operator o'chirildi", "op_sessions_revoked": "Operator sessiyalari bekor qilindi",
    "review_edit": "Otziv tahrirlandi", "review_delete": "Otziv o'chirildi",
    "close_stale": "Eski murojaatlar yopildi", "broadcast": "Ommaviy xabar",
    "settings": "Sozlamalar o'zgardi", "internal_note": "Ichki izoh", "admin_send": "Admin yozdi",
    "auto_assign": "Avto-taqsimlandi", "pin": "Xabar qadaldi", "unpin": "Qadash olindi",
    "tags": "Teglar", "client_note": "Mijoz izohi", "login_fail": "Noto'g'ri login urinishi",
    "admin_role": "Admin roli", "admin_sessions_revoked": "Admin sessiyalari bekor qilindi",
}


async def _actor_label(actor: str, cache: dict) -> str:
    if actor in cache:
        return cache[actor]
    lbl = actor or "—"
    if actor.startswith("admin:"):
        try:
            aid = int(actor.split(":", 1)[1])
            u = await q.get_user(aid)
            lbl = "Admin · " + ((u["full_name"] if u and u["full_name"] else "") or str(aid))
        except (ValueError, IndexError):
            pass
    elif actor.startswith("op:"):
        lbl = "Operator · " + actor[3:]
    elif actor == "system":
        lbl = "Tizim"
    elif actor.startswith("ip:"):
        lbl = "IP " + actor[3:]
    cache[actor] = lbl
    return lbl


async def api_admin_audit(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    try:
        page = int(request.query.get("page", "0") or 0)
    except ValueError:
        page = 0
    raw = (request.query.get("q") or "").strip()
    oid = int(raw.lstrip("#")) if raw.lstrip("#").isdigit() else None
    rows, total = await q.audit_page(50, page * 50, oid, None if oid else (raw or None))
    cache, items = {}, []
    for r in rows:
        try:
            det = json.loads(r["details"]) if r["details"] else {}
        except Exception:
            det = {}
        items.append({"id": r["id"], "at": r["at"], "actor": await _actor_label(r["actor"] or "", cache),
                      "action": r["action"], "label": _AUDIT_LBL.get(r["action"], r["action"]),
                      "order_id": r["order_id"], "details": det})
    return _json({"ok": True, "items": items, "total": total, "page": page})


def _mins_between(a, b):
    from datetime import datetime as _dt
    try:
        return (_dt.strptime(b[:19], "%Y-%m-%d %H:%M:%S") -
                _dt.strptime(a[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
    except Exception:
        return None


async def api_admin_sla(request):
    """Operatorlar bo'yicha SLA: birinchi javob vaqti, hal qilish vaqti, maqsadga erishish %."""
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    period = request.query.get("period", "week")
    since = _period_start_str(period)
    try:
        target = float(await q.get_setting("sla_target_min", "5") or 5)
    except ValueError:
        target = 5
    per = {}
    tot_first = []
    for r in await q.sla_rows(since):
        if not r["operator_id"]:
            continue
        d = per.setdefault(r["operator_id"], {"name": r["operator"] or "—", "orders": 0, "done": 0,
                                              "first": [], "resol": [], "rated": []})
        d["orders"] += 1
        if r["status"] == "done":
            d["done"] += 1
        if r["first_reply"]:
            m = _mins_between(r["created_at"], r["first_reply"])
            if m is not None and m >= 0:
                d["first"].append(m)
                tot_first.append(m)
        if r["closed_at"]:
            m = _mins_between(r["created_at"], r["closed_at"])
            if m is not None and m >= 0:
                d["resol"].append(max(0, m - (r["paused_total_min"] or 0)))   # pauza vaqti hisoblanmaydi
        if r["rating"]:
            d["rated"].append(r["rating"])
    items = []
    for oid, d in per.items():
        f = d["first"]
        items.append({"id": oid, "name": d["name"], "orders": d["orders"], "done": d["done"],
                      "first_med": q._median(f), "resol_med": q._median(d["resol"]),
                      "in_target": round(100 * sum(1 for x in f if x <= target) / len(f)) if f else None,
                      "rating": round(sum(d["rated"]) / len(d["rated"]), 1) if d["rated"] else None})
    items.sort(key=lambda x: (x["in_target"] is None, -(x["in_target"] or 0)))
    overall = (round(100 * sum(1 for x in tot_first if x <= target) / len(tot_first))
               if tot_first else None)
    return _json({"ok": True, "items": items, "target": target, "overall": overall,
                  "first_med": q._median(tot_first), "period": period})


async def api_admin_admin_role(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    if not await _can_manage_admins(tg):
        return _json({"ok": False, "error": "Sizda bu huquq yo'q"}, 403)
    try:
        tid = int(body.get("telegram_id"))
    except (TypeError, ValueError):
        return _json({"ok": False, "error": "telegram_id"}, 400)
    role = "viewer" if body.get("role") == "viewer" else "admin"
    if tid in ADMIN_IDS or _is_super(tid):
        return _json({"ok": False, "error": ".env adminining rolini o'zgartirib bo'lmaydi"})
    await q.set_admin_role(tid, role)
    await q.audit(f"admin:{tg}", "admin_role", None, {"admin": tid, "role": role})
    return _json({"ok": True, "role": role})


async def api_admin_revoke_sessions(request):
    """Barcha admin sessiyalarini bekor qiladi (keyingi ochilishda Telegram orqali qayta kiradi)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tg = await _auth_admin(request, body)
    if not tg:
        return _json({"ok": False}, 401)
    if not await _can_manage_admins(tg):
        return _json({"ok": False, "error": "Sizda bu huquq yo'q"}, 403)
    await q.set_setting("admin_epoch", str(await _admin_epoch() + 1))
    await q.audit(f"admin:{tg}", "admin_sessions_revoked", None)
    return _json({"ok": True, "token": await _admin_sign(tg)})


async def api_admin_tags(request):
    if not await _auth_admin(request, request.query):
        return _json({"ok": False}, 401)
    period = request.query.get("period", "month")
    since = _period_start_str(period)
    return _json({"ok": True, "preset": await _tag_preset(),
                  "counts": [{"name": n, "cnt": c} for n, c in await q.tag_counts(since)]})


# ================= Operator: chat foni (wallpaper) =================
_WP_PRESETS = {"default", "mint", "ocean", "sunset", "lavender", "night", "sand", "plain"}


async def api_wallpaper_get(request):
    if request.query.get("img"):
        # Rasm URL'ida sessiya tokeni emas — media kaliti (mk)
        if not _check_media_key(request.query.get("mk", "")):
            return web.Response(status=401)
        try:
            oid = int(request.query.get("oid"))
        except (TypeError, ValueError):
            return web.Response(status=400)
        path = os.path.join(AVATAR_DIR, f"wp_{oid}.jpg")
        if os.path.exists(path):
            return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})
        return web.Response(status=404)
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False}, 401)
    raw = await q.get_setting(f"wp_op_{op['id']}", "") or ""
    try:
        cfg = json.loads(raw) if raw else {}
    except Exception:
        cfg = {}
    return _json({"ok": True, "preset": cfg.get("preset", "default"), "custom": bool(cfg.get("custom")),
                  "dim": cfg.get("dim", 0), "blur": cfg.get("blur", 0), "ver": cfg.get("ver", 0)})


async def api_wallpaper_set(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    op, _ = await _auth_op(request, body)
    if not op:
        return _json({"ok": False}, 401)
    raw = await q.get_setting(f"wp_op_{op['id']}", "") or ""
    try:
        cfg = json.loads(raw) if raw else {}
    except Exception:
        cfg = {}
    data = body.get("data")
    if data:
        try:
            img = base64.b64decode(str(data).split(",")[-1])
        except Exception:
            return _json({"ok": False, "error": "Rasm o'qilmadi"})
        if len(img) > 3 * 1024 * 1024:
            return _json({"ok": False, "error": "Rasm juda katta (maks 3 MB)"})
        os.makedirs(AVATAR_DIR, exist_ok=True)
        with open(os.path.join(AVATAR_DIR, f"wp_{op['id']}.jpg"), "wb") as fh:
            fh.write(img)
        cfg["custom"] = True
        cfg["ver"] = int(time.time())
    if body.get("preset") in _WP_PRESETS:
        cfg["preset"] = body["preset"]
        cfg["custom"] = False
    for k in ("dim", "blur"):
        if k in body:
            try:
                cfg[k] = max(0, min(int(body[k]), 80 if k == "dim" else 20))
            except (TypeError, ValueError):
                pass
    await q.set_setting(f"wp_op_{op['id']}", json.dumps(cfg))
    return _json({"ok": True, "preset": cfg.get("preset", "default"), "custom": bool(cfg.get("custom")),
                  "dim": cfg.get("dim", 0), "blur": cfg.get("blur", 0), "ver": cfg.get("ver", 0)})


# ---------------- Umumiy formatlash skripti (operator + admin panel) ----------------
_FMT_JS = os.path.join(os.path.dirname(__file__), "webapp", "fmt.js")


async def fmt_js(request):
    if os.path.exists(_FMT_JS):
        return web.FileResponse(_FMT_JS, headers={"Cache-Control": "no-cache",
                                                  "Content-Type": "application/javascript; charset=utf-8"})
    return web.Response(status=404)


# ---------------- Kesh tozalash (disk to'lmasin) ----------------
async def _cache_cleanup_loop():
    while True:
        try:
            if os.path.isdir(MEDIA_CACHE):
                cutoff = time.time() - 7 * 86400
                for name in os.listdir(MEDIA_CACHE):
                    p = os.path.join(MEDIA_CACHE, name)
                    try:
                        if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                            os.remove(p)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(24 * 3600)


# ---------------- Server ----------------
def build_app() -> web.Application:
    app = web.Application(client_max_size=25 * 1024 * 1024)
    app.router.add_get("/", index)
    app.router.add_get("/operator", index)
    app.router.add_get("/health", health)
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/chats", api_chats)
    app.router.add_get("/api/general_chats", api_general_chats)
    app.router.add_get("/api/messages", api_messages)
    app.router.add_get("/api/file", api_file)
    app.router.add_post("/api/send", api_send)
    app.router.add_post("/api/reopen", api_reopen)
    app.router.add_post("/api/accept", api_accept)
    app.router.add_post("/api/close", api_close)
    app.router.add_post("/api/hide", api_hide)
    app.router.add_get("/api/profile", api_profile)
    app.router.add_post("/api/status", api_status)
    app.router.add_get("/api/avatar", api_avatar)
    app.router.add_post("/api/avatar", api_avatar_upload)
    app.router.add_get("/api/clients", api_clients)
    app.router.add_get("/api/client_open", api_client_open)
    app.router.add_get("/api/branches", api_branches)
    app.router.add_post("/api/cmd", api_cmd)
    app.router.add_get("/api/channel", api_channel)
    app.router.add_post("/api/channel_accept", api_channel_accept)
    app.router.add_get("/api/newcount", api_newcount)
    app.router.add_get("/api/unfinished", api_unfinished)
    app.router.add_get("/api/done", api_done)
    app.router.add_get("/api/my_ratings", api_my_ratings)
    app.router.add_get("/api/rating", api_rating)
    app.router.add_get("/api/stickers", api_stickers)
    app.router.add_post("/api/send_sticker", api_send_sticker)
    app.router.add_get("/api/templates", api_templates)
    app.router.add_get("/api/note", api_note)
    app.router.add_post("/api/note", api_note_save)
    app.router.add_post("/api/msg_del", api_msg_del)
    app.router.add_post("/api/msg_delete_many", api_msg_delete_many)
    app.router.add_post("/api/msg_edit", api_msg_edit)
    app.router.add_post("/api/remind", api_remind)
    app.router.add_get("/api/mystats", api_mystats)
    app.router.add_get("/api/client_info", api_client_info)
    app.router.add_get("/api/sync", api_sync)
    app.router.add_get("/api/notifications", api_notifications)
    app.router.add_post("/api/notifications/read", api_notifications_read)
    app.router.add_get("/api/operator_peers", api_operator_peers)
    app.router.add_get("/api/operator_messages", api_operator_messages)
    app.router.add_post("/api/operator_send", api_operator_send)
    app.router.add_get("/api/done_chats", api_done_chats)
    app.router.add_post("/api/cancel", api_cancel)
    app.router.add_post("/api/reject", api_reject)
    app.router.add_get("/api/media_key", api_media_key)
    app.router.add_post("/api/typing", api_typing)
    app.router.add_post("/api/chat_state", api_chat_state)
    app.router.add_post("/api/pin", api_pin)
    app.router.add_get("/api/tags", api_tags)
    app.router.add_post("/api/order_tags", api_order_tags)
    app.router.add_post("/api/inote", api_inote)
    app.router.add_get("/api/ops_list", api_ops_list)
    app.router.add_post("/api/transfer", api_transfer)
    app.router.add_post("/api/tpl_add", api_tpl_add)
    app.router.add_post("/api/tpl_del", api_tpl_del)
    app.router.add_get("/fmt.js", fmt_js)
    app.router.add_get("/static/{name}", static_file)
    import webapp_extra
    webapp_extra.register(app)
    # Admin mini app
    app.router.add_get("/admin", admin_index)
    app.router.add_get("/view", view_index)
    app.router.add_post("/api/admin/login", api_admin_login)
    app.router.add_get("/api/admin/dash", api_admin_dash)
    app.router.add_get("/api/admin/orders", api_admin_orders)
    app.router.add_get("/api/admin/msgs", api_admin_msgs)
    app.router.add_post("/api/admin/close", api_admin_close)
    app.router.add_get("/api/admin/clients", api_admin_clients)
    app.router.add_get("/api/admin/client", api_admin_client)
    app.router.add_get("/api/admin/branches", api_admin_branches)
    app.router.add_post("/api/admin/branch_save", api_admin_branch_save)
    app.router.add_post("/api/admin/branch_del", api_admin_branch_del)
    app.router.add_get("/api/admin/faqs", api_admin_faqs)
    app.router.add_post("/api/admin/faq_save", api_admin_faq_save)
    app.router.add_post("/api/admin/faq_del", api_admin_faq_del)
    app.router.add_get("/api/admin/tpls", api_admin_tpls)
    app.router.add_post("/api/admin/tpl_add", api_admin_tpl_add)
    app.router.add_post("/api/admin/tpl_del", api_admin_tpl_del)
    app.router.add_get("/api/admin/ops", api_admin_ops)
    app.router.add_post("/api/admin/op_save", api_admin_op_save)
    app.router.add_post("/api/admin/op_toggle", api_admin_op_toggle)
    app.router.add_post("/api/admin/op_del", api_admin_op_del)
    app.router.add_get("/api/admin/op_detail", api_admin_op_detail)
    app.router.add_get("/api/admin/opbots", api_admin_opbots)
    app.router.add_post("/api/admin/opbot_add", api_admin_opbot_add)
    app.router.add_post("/api/admin/opbot_toggle", api_admin_opbot_toggle)
    app.router.add_post("/api/admin/opbot_del", api_admin_opbot_del)
    app.router.add_get("/api/admin/lowratings", api_admin_lowratings)
    app.router.add_get("/api/admin/reviews", api_admin_reviews)
    app.router.add_post("/api/admin/send", api_admin_send)
    app.router.add_post("/api/admin/transfer", api_admin_transfer)
    app.router.add_post("/api/admin/client_block", api_admin_client_block)
    app.router.add_post("/api/admin/client_del", api_admin_client_del)
    app.router.add_post("/api/admin/note_save", api_admin_note_save)
    app.router.add_post("/api/admin/review", api_admin_review)
    app.router.add_post("/api/admin/excel_clients", api_admin_excel_clients)
    app.router.add_post("/api/admin/close_stale", api_admin_close_stale)
    app.router.add_get("/api/admin/bc_pending", api_admin_bc_pending)
    app.router.add_post("/api/admin/bc_cancel", api_admin_bc_cancel)
    app.router.add_get("/api/admin/stats", api_admin_stats)
    app.router.add_get("/api/admin/branch_detail", api_admin_branch_detail)
    app.router.add_get("/api/admin/settings", api_admin_settings)
    app.router.add_post("/api/admin/settings_save", api_admin_settings_save)
    app.router.add_get("/api/admin/admins", api_admin_admins)
    app.router.add_post("/api/admin/admin_add", api_admin_admin_add)
    app.router.add_post("/api/admin/admin_del", api_admin_admin_del)
    app.router.add_post("/api/admin/set_manager", api_admin_set_manager)
    app.router.add_get("/api/admin/notify_list", api_admin_notify_list)
    app.router.add_post("/api/admin/notify_toggle", api_admin_notify_toggle)
    app.router.add_post("/api/admin/broadcast", api_admin_broadcast)
    app.router.add_post("/api/admin/excel", api_admin_excel)
    app.router.add_post("/api/admin/inote", api_admin_inote)
    app.router.add_get("/api/admin/audit", api_admin_audit)
    app.router.add_get("/api/admin/sla", api_admin_sla)
    app.router.add_post("/api/admin/admin_role", api_admin_admin_role)
    app.router.add_post("/api/admin/revoke_sessions", api_admin_revoke_sessions)
    app.router.add_post("/api/admin/op_logout", api_admin_op_logout)
    app.router.add_get("/api/admin/tags", api_admin_tags)
    app.router.add_get("/api/wallpaper", api_wallpaper_get)
    app.router.add_post("/api/wallpaper", api_wallpaper_set)
    return app


async def start(port: int):
    runner = web.AppRunner(build_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    asyncio.create_task(_cache_cleanup_loop())
    import webapp_extra
    webapp_extra.start_background()
    logger.info("🖥 Mini app server: 0.0.0.0:%s  (URL: %s)", port, WEBAPP_URL or "— sozlanmagan")
