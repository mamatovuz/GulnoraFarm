"""Telegram Mini App (CRM) — operator chat paneli uchun web server (aiohttp).

Bot bilan bitta jarayonda ishlaydi, bitta bazaga ulanadi. Operator mini app'da:
login/parol -> chat ro'yxati -> yozishma -> mijozga yuborish (bot orqali) -> chatni o'chirish.
"""
import os
import json
import hmac
import base64
import hashlib
import logging
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram.types import BufferedInputFile

from config import BOT_TOKEN, WEBAPP_URL, AVATAR_DIR
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
            "own": m["sender"] == "operator",
            "type": m["content_type"] or "text",
            "text": m["text"] or "",
            "file_id": m["file_id"] or "",
            "time": (m["created_at"] or "")[11:16],
        })
    uname = user["username"] if user and "username" in user.keys() else ""
    return _json({"ok": True, "order_id": order_id, "status": order["status"],
                  "client": {"name": user["full_name"] if user else "—",
                             "phone": user["phone"] if user else "",
                             "username": uname or ""},
                  "messages": out})


# ---------------- API: media (rasm/ovoz) ko'rsatish ----------------
async def api_file(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return web.Response(status=401, text="auth")
    fid = request.query.get("fid", "")
    kind = request.query.get("kind", "")
    if not fid:
        return web.Response(status=400)
    from utils import cbot
    client = cbot()
    if not client:
        return web.Response(status=503)
    try:
        f = await client.get_file(fid)
        buf = await client.download_file(f.file_path)
        raw = buf.read()
    except Exception:
        return web.Response(status=404, text="not found")
    ctype = {"voice": "audio/ogg", "audio": "audio/ogg", "video": "video/mp4",
             "sticker": "image/webp", "document": "application/octet-stream"}.get(kind, "image/jpeg")
    return web.Response(body=raw, content_type=ctype,
                        headers={"Cache-Control": "public, max-age=86400"})


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
    media_kind = body.get("media_kind")          # 'photo' | 'voice' | None
    media_data = body.get("media_data")          # base64 (dataURL bo'lishi mumkin)
    if not text and not (media_kind and media_data):
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
    uid = order["user_id"]
    clang = await q.get_lang(uid)
    try:
        if media_kind and media_data:
            raw = base64.b64decode(str(media_data).split(",")[-1])
            cap = f"👨‍⚕️ {op['name']}" + (f": {text}" if text else "")
            if media_kind == "photo":
                sent = await client.send_photo(uid, BufferedInputFile(raw, "photo.jpg"), caption=cap)
                fid = sent.photo[-1].file_id
                await q.add_message(order_id, "operator", "photo", text or None, fid, None)
                await post_operator_to_channel(client, order, op["name"], content_type="photo",
                                               file_id=fid, src_bot=client, text=text or "")
            else:  # voice — voice -> audio -> document zanjiri (Telegram formatga qarab)
                mime = str(body.get("media_mime", "")).lower()
                ext = "ogg" if "ogg" in mime else ("webm" if "webm" in mime else
                                                   ("mp4" if "mp4" in mime else "audio"))
                fid, ctype = None, "voice"
                for kind in ("voice", "audio", "document"):
                    try:
                        if kind == "voice":
                            snt = await client.send_voice(uid, BufferedInputFile(raw, "voice.ogg"))
                            fid, ctype = snt.voice.file_id, "voice"
                        elif kind == "audio":
                            snt = await client.send_audio(uid, BufferedInputFile(raw, "audio." + ext))
                            fid, ctype = snt.audio.file_id, "audio"
                        else:
                            snt = await client.send_document(uid, BufferedInputFile(raw, "voice." + ext),
                                                             caption="🎤 ovozli xabar")
                            fid, ctype = snt.document.file_id, "document"
                        break
                    except Exception:
                        continue
                if not fid:
                    return _json({"ok": False, "error": "ovoz yuborilmadi (format qo'llanmadi)"}, 200)
                await q.add_message(order_id, "operator", ctype, None, fid, None)
                await post_operator_to_channel(client, order, op["name"], content_type=ctype,
                                               file_id=fid, src_bot=client, text="🎤 ovozli xabar")
        else:
            await q.add_message(order_id, "operator", "text", text, None, None)
            await client.send_message(uid, loc.t("operator_reply", clang, name=op["name"], text=text))
            await post_operator_to_channel(client, order, op["name"], text=text)
    except Exception:
        return _json({"ok": False, "error": "mijozga yuborilmadi (bloklagan bo'lishi mumkin)"}, 200)
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


# ---------------- API: profil ----------------
async def api_profile(request):
    op, _ = await _auth_op(request, request.query)
    if not op:
        return _json({"ok": False, "error": "auth"}, 401)
    s = await q.operator_stats(op["id"])
    incoming = await q.new_count()
    return _json({"ok": True, "name": op["name"], "login": op["login"],
                  "availability": op["availability"], "incoming": incoming,
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
    rows, total = await q.users_page(50, 0, search)
    out = [{"tg": r["telegram_id"], "name": r["full_name"] or "—",
            "phone": r["phone"] or "", "cnt": r["cnt"]} for r in rows]
    return _json({"ok": True, "total": total, "clients": out})


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
    return _json({"ok": True, "branches": [{"id": b["id"], "name": b["name"]} for b in bs]})


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
            "branch": r["branch"] or "", "time": (r["created_at"] or "")[11:16],
            "text": r["first_text"] or "", "file_id": r["first_file"] or "",
            "ftype": r["first_ct"] or ""})
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
    order = await q.get_order(order_id)
    if not order:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    from utils import cbot, post_operator_to_channel
    import keyboards as kb
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"}, 200)
    uid = order["user_id"]
    clang = await q.get_lang(uid)
    try:
        if cmd == "autoclose":
            import asyncio
            from handlers.operator import _auto_close_task, AUTO_CLOSE_MIN
            asyncio.create_task(_auto_close_task(client, order_id, q.now(), op["telegram_id"] or 0))
            await client.send_message(uid, loc.t("auto_close_warning", clang, min=AUTO_CLOSE_MIN))
            return _json({"ok": True, "info": f"{AUTO_CLOSE_MIN} daqiqada avto-yakunlash yoqildi"})

        if cmd == "askbranch":
            branches = await q.list_branches()
            await client.send_message(uid, loc.t("op_ask_branch", clang),
                                      reply_markup=kb.op_ask_branch_kb(branches, order_id, clang))
            return _json({"ok": True, "info": "Mijozga filial tanlash so'rovi yuborildi"})

        if cmd == "sendbranch":
            b = await q.get_branch(int(arg))
            if not b:
                return _json({"ok": False, "error": "filial topilmadi"})
            text = (f"🏥 <b>{b['name']}</b>\n📍 {b['address'] or '—'}\n"
                    f"📞 {b['phone'] or '—'}\n🕐 Ish vaqti: {b['open_time']}–{b['close_time']}")
            has = b["lat"] is not None and b["lon"] is not None
            markup = kb.branch_directions_kb(b["lat"], b["lon"]) if has else None
            if b["photo_file_id"]:
                await client.send_photo(uid, b["photo_file_id"], caption=text, reply_markup=markup)
            else:
                await client.send_message(uid, text, reply_markup=markup)
            if has:
                await client.send_venue(uid, latitude=b["lat"], longitude=b["lon"],
                                        title=b["name"], address=b["address"] or "")
            return _json({"ok": True, "info": "Filial ma'lumoti yuborildi"})

        if cmd == "bill":
            billtext = str(arg or "").strip()
            await q.set_order_bill(order_id, billtext, None)
            await client.send_message(uid, loc.t("bill_to_client", clang, id=order_id, bill=billtext))
            await q.add_message(order_id, "operator", "text", f"🧾 Hisob-kitob: {billtext}", None, None)
            await post_operator_to_channel(client, order, op["name"], text=f"🧾 Hisob-kitob: {billtext}")
            return _json({"ok": True, "info": "Hisob-kitob yuborildi"})
    except Exception:
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
    rows = await q.orders_by_status("done", op["id"])
    items = []
    for r in rows[:50]:
        u = await q.get_user(r["user_id"])
        items.append({"order_id": r["id"], "name": u["full_name"] if u else "—",
                      "time": (r["closed_at"] or r["created_at"] or "")[:16], "rating": r["rating"] or 0})
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
    order = await q.get_order(order_id)
    tpl = await q.get_template(tid)
    if not order or not tpl or not tpl["sticker"]:
        return _json({"ok": False, "error": "topilmadi"}, 404)
    if order["status"] not in ("new", "in_progress"):
        return _json({"ok": False, "error": "yopilgan"})
    if order["status"] == "new" and not order["operator_id"]:
        if await q.claim_order(order_id, op["id"]):
            await q.set_operator_availability(op["id"], "busy")
    await q.set_operator_active_order(op["id"], order_id)
    from utils import cbot, post_operator_to_channel
    client = cbot()
    if not client:
        return _json({"ok": False, "error": "bot tayyor emas"})
    try:
        await client.send_sticker(order["user_id"], tpl["sticker"])
        await q.add_message(order_id, "operator", "sticker", None, tpl["sticker"], None)
        await post_operator_to_channel(client, order, op["name"],
                                       content_type="sticker", file_id=tpl["sticker"], src_bot=client)
    except Exception:
        return _json({"ok": False, "error": "yuborilmadi"})
    return _json({"ok": True})


# ---------------- Server ----------------
def build_app() -> web.Application:
    app = web.Application(client_max_size=25 * 1024 * 1024)
    app.router.add_get("/", index)
    app.router.add_get("/operator", index)
    app.router.add_get("/health", health)
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/chats", api_chats)
    app.router.add_get("/api/messages", api_messages)
    app.router.add_get("/api/file", api_file)
    app.router.add_post("/api/send", api_send)
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
    app.router.add_get("/api/rating", api_rating)
    app.router.add_get("/api/stickers", api_stickers)
    app.router.add_post("/api/send_sticker", api_send_sticker)
    return app


async def start(port: int):
    runner = web.AppRunner(build_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🖥 Mini app server: 0.0.0.0:%s  (URL: %s)", port, WEBAPP_URL or "— sozlanmagan")
