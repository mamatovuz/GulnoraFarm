"""Umumiy yordamchi funksiyalar."""
import asyncio
from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import botreg
from config import ADMIN_IDS, OPERATORS_GROUP_ID
from database import queries as q


def cbot() -> Bot:
    """Mijoz/asosiy bot — kanal va mijozga yozish uchun (cross-bot)."""
    return botreg.client_bot


async def _download_file(src_bot: Bot, file_id):
    """file_id egasi (src_bot) orqali fayl baytlarini yuklab oladi."""
    try:
        f = await src_bot.get_file(file_id)
        buf = await src_bot.download_file(f.file_path)
        return buf.read()
    except Exception:
        return None


async def _send_media_bytes(bot: Bot, chat_id, content_type, raw, caption, kw):
    """Bayt (raw) sifatida media yuboradi — cross-bot uchun (file_id ishlamaganda)."""
    try:
        inp = BufferedInputFile(raw, filename="file")
        if content_type == "photo":
            return await bot.send_photo(chat_id, inp, caption=caption, **kw)
        if content_type == "video":
            return await bot.send_video(chat_id, inp, caption=caption, **kw)
        if content_type == "document":
            return await bot.send_document(chat_id, inp, caption=caption, **kw)
        if content_type == "animation":
            return await bot.send_animation(chat_id, inp, caption=caption, **kw)
        if content_type == "voice":
            return await bot.send_voice(chat_id, inp, **kw)
        if content_type == "audio":
            return await bot.send_audio(chat_id, inp, caption=caption, **kw)
        if content_type == "sticker":
            return await bot.send_sticker(chat_id, inp, **kw)
        return await bot.send_message(chat_id, caption or "—", **kw)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None


async def send_raw(bot: Bot, chat_id, content_type, file_id, caption, markup=None,
                   reply_to=None, raw=None):
    """Kontent turini berib yuboradi. file_id boshqa botniki bo'lsa (cross-bot),
    mijoz boti orqali yuklab, shu bot orqali qayta yuboradi."""
    kw = {"reply_markup": markup}
    if reply_to:
        kw["reply_to_message_id"] = reply_to
        kw["allow_sending_without_reply"] = True
    if content_type == "text" or not file_id:
        try:
            return await bot.send_message(chat_id, caption or "—", **kw)
        except (TelegramBadRequest, TelegramForbiddenError):
            return None
    # Media: agar yuborayotgan bot file_id egasi (mijoz boti) bo'lmasa — yuklab qayta yuboramiz
    client = cbot()
    same_owner = bool(client and bot.id == client.id)
    if not same_owner:
        if raw is None and client:
            raw = await _download_file(client, file_id)
        if raw is not None:
            cap = None if content_type == "sticker" else caption
            return await _send_media_bytes(bot, chat_id, content_type, raw, cap, kw)
        # yuklab bo'lmadi — pastda file_id bilan urinib ko'ramiz (fallback)
    try:
        if content_type == "photo":
            return await bot.send_photo(chat_id, file_id, caption=caption, **kw)
        if content_type == "video":
            return await bot.send_video(chat_id, file_id, caption=caption, **kw)
        if content_type == "document":
            return await bot.send_document(chat_id, file_id, caption=caption, **kw)
        if content_type == "animation":
            return await bot.send_animation(chat_id, file_id, caption=caption, **kw)
        if content_type == "voice":
            return await bot.send_voice(chat_id, file_id, **kw)
        if content_type == "sticker":
            return await bot.send_sticker(chat_id, file_id, **kw)
        return await bot.send_message(chat_id, caption or "—", **kw)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None

STATUS_LABEL = {
    "new": "🟡 Yangi",
    "in_progress": "🔵 Jarayonda",
    "done": "🟢 Yakunlangan",
    "canceled": "🔴 Bekor qilingan",
}


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def _within(start: str, end: str, now_hm: str) -> bool:
    if start <= end:
        return start <= now_hm <= end
    return now_hm >= start or now_hm <= end   # tungi rejim (masalan 22:00–06:00)


async def work_hours():
    """Mijoz uchun umumiy ish vaqti: (ish_vaqtidami, start, end)."""
    from config import now_local
    start = await q.get_setting("work_start", "08:00")
    end = await q.get_setting("work_end", "23:00")
    return _within(start, end, now_local().strftime("%H:%M")), start, end


def operator_in_hours(op):
    """Aniq operatorning shaxsiy ish vaqtida ekanini tekshiradi: (ichidami, start, end)."""
    from config import now_local
    start = op["work_start"] or "08:00"
    end = op["work_end"] or "23:00"
    return _within(start, end, now_local().strftime("%H:%M")), start, end


def fmt_dt(s: str) -> str:
    """'2026-06-20 15:37:13' -> '20.06.2026 15:37'."""
    if not s:
        return "—"
    try:
        from datetime import datetime
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except Exception:
        return s


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Ikki nuqta orasidagi masofa (km)."""
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(2 * 6371 * asin(sqrt(a)), 1)


async def main_kb(telegram_id: int):
    """Mijoz/asosiy bot menyusi. Operatorlar alohida botda ishlaydi —
    shuning uchun asosiy botda operator tugmasi ko'rsatilmaydi (bot_id IS NULL)."""
    op = await q.get_operator_by_tg_bot(telegram_id, None)
    is_op = bool(op and op["status"] == "active")
    lang = await q.get_lang(telegram_id)
    faq_on = (await q.get_setting("faq_enabled", "1")) != "0"
    return kb.main_menu(lang=lang, is_admin=is_admin(telegram_id), is_operator=is_op, show_faq=faq_on)


async def check_subscription(bot: Bot, telegram_id: int):
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi (bo'sh bo'lsa — hammasiga obuna)."""
    channels = await q.list_channels()
    not_subbed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["chat_id"], telegram_id)
            if member.status in ("left", "kicked"):
                not_subbed.append(ch)
        except (TelegramBadRequest, TelegramForbiddenError):
            # bot kanalda admin emas yoki kanal topilmadi — tekshira olmaymiz, o'tkazib yuboramiz
            continue
    return not_subbed


async def order_card_text(order) -> str:
    user = await q.get_user(order["user_id"])
    branch = await q.get_branch(order["branch_id"]) if order["branch_id"] else None
    name = user["full_name"] if user else "—"
    phone = user["phone"] if user else "—"
    branch_name = branch["name"] if branch else "—"
    header = "🆕" if order["status"] == "new" else "📋"
    # Mijoz ismini bosiladigan qilamiz: @username bo'lsa undan (ishonchli), aks holda tg://user
    uname = user["username"] if user and "username" in user.keys() else None
    if uname:
        name_link = f'<a href="https://t.me/{uname}">{name}</a>'
    else:
        name_link = f'<a href="tg://user?id={order["user_id"]}">{name}</a>'
    return (
        f"{header} <b>Murojaat — #{order['id']}</b>\n\n"
        f"👤 Mijoz: {name_link}\n"
        f"📞 Telefon: {phone}\n"
        f"🏥 Filial: {branch_name}\n"
        f"🕐 Sana: {fmt_dt(order['created_at'])}\n\n"
        f"Holat: {STATUS_LABEL.get(order['status'], order['status'])}"
    )


async def send_content_message(bot: Bot, chat_id, message, caption: str, markup=None,
                               reply_to=None):
    """Mijoz/operator kontentini (rasm/video/hujjat/stiker/GIF/matn) yuboradi.
    file_id boshqa botniki bo'lsa (cross-bot), xabar kelgan bot orqali yuklab qayta yuboradi.
    Yuborilgan Message obyektini qaytaradi (xato bo'lsa None)."""
    kwargs = {"reply_markup": markup}
    if reply_to:
        kwargs["reply_to_message_id"] = reply_to
        kwargs["allow_sending_without_reply"] = True
    ct, fid, _ = extract_content(message)
    if ct == "text" or not fid:
        try:
            return await bot.send_message(chat_id, caption or "—", **kwargs)
        except (TelegramBadRequest, TelegramForbiddenError):
            return None
    # cross-bot: yuborayotgan bot xabar egasi emas -> yuklab qayta yuboramiz
    src = message.bot
    if src and src.id != bot.id:
        raw = await _download_file(src, fid)
        if raw is not None:
            if ct == "sticker" and caption:
                try:
                    await bot.send_message(chat_id, caption)
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
            cap = None if ct == "sticker" else caption
            return await _send_media_bytes(bot, chat_id, ct, raw, cap, kwargs)
    # same-bot — to'g'ridan-to'g'ri file_id bilan
    try:
        if message.photo:
            return await bot.send_photo(chat_id, message.photo[-1].file_id, caption=caption, **kwargs)
        if message.video:
            return await bot.send_video(chat_id, message.video.file_id, caption=caption, **kwargs)
        if message.animation:
            return await bot.send_animation(chat_id, message.animation.file_id, caption=caption, **kwargs)
        if message.sticker:
            return await bot.send_sticker(chat_id, message.sticker.file_id, **kwargs)
        if message.voice:
            return await bot.send_voice(chat_id, message.voice.file_id, **kwargs)
        if message.document:
            return await bot.send_document(chat_id, message.document.file_id, caption=caption, **kwargs)
        return await bot.send_message(chat_id, caption or "—", **kwargs)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None


def _client_note(message) -> str:
    return (message.caption or message.text or "").strip()


def extract_content(message):
    """Xabardan (content_type, file_id, matn) ni ajratib oladi."""
    if message.photo:
        return "photo", message.photo[-1].file_id, message.caption
    if message.video:
        return "video", message.video.file_id, message.caption
    if message.animation:
        return "animation", message.animation.file_id, message.caption
    if message.sticker:
        return "sticker", message.sticker.file_id, None
    if message.voice:
        return "voice", message.voice.file_id, message.caption
    if message.document:
        return "document", message.document.file_id, message.caption
    return "text", None, message.text


_bot_username = None


async def get_bot_username(bot: Bot) -> str:
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return _bot_username


async def deliver_order_to_operators(bot: Bot, order_id, content_type, file_id, text):
    """Kanalga (tugmasiz) joylaydi + pin qiladi, hamda har bir operator botiga
    (Qabul qilish tugmasi bilan) push qiladi."""
    order = await q.get_order(order_id)
    info = await order_card_text(order)
    note = (text or "").strip()
    caption = f"{note}\n\n{info}" if note else info
    # 1) Kanalga — TUGMASIZ + pin (mijoz/asosiy bot orqali)
    client = cbot() or bot
    if OPERATORS_GROUP_ID and client:
        sent = await send_raw(client, OPERATORS_GROUP_ID, content_type, file_id, caption)
        if sent:
            await q.set_order_group_msg(order_id, sent.message_id)
            try:
                await client.pin_chat_message(OPERATORS_GROUP_ID, message_id=sent.message_id,
                                              disable_notification=True)
            except Exception:
                pass
    # 2) Har bir operator botiga push (bo'sh, login qilgan operatorlarga)
    await push_to_operator_bots(order_id, content_type, file_id, caption)
    # 3) Eskalatsiya: belgilangan vaqtda qabul qilinmasa — admin'ga eslatma
    schedule_escalation(order_id)


# ---------------- Eskalatsiya: javobsiz murojaatni admin'ga eslatish ----------------
async def _escalation_watch(order_id):
    try:
        mins = int(await q.get_setting("escalate_min", "5") or "5")
    except (TypeError, ValueError):
        mins = 5
    if mins <= 0:
        return
    await asyncio.sleep(mins * 60)
    order = await q.get_order(order_id)
    if not order or order["status"] != "new":
        return  # allaqachon qabul qilingan yoki yopilgan
    client = cbot()
    if not client:
        return
    info = await order_card_text(order)
    text = (f"⚠️ <b>Javobsiz murojaat!</b>\n\n"
            f"#{order_id} — {mins} daqiqada hech bir operator qabul qilmadi.\n\n{info}\n\n"
            f"📌 «Yakunlanmagan murojaatlar» bo'limidan ko'rishingiz mumkin.")
    for aid in ADMIN_IDS:
        try:
            await client.send_message(aid, text, disable_web_page_preview=True)
        except Exception:
            pass


def schedule_escalation(order_id):
    """Murojaat uchun fon kuzatuvchini ishga tushiradi (javobsiz qolsa admin'ga eslatadi)."""
    try:
        asyncio.create_task(_escalation_watch(order_id))
    except RuntimeError:
        pass  # event loop yo'q (masalan test)


async def push_to_operator_bots(order_id, content_type, file_id, caption):
    """Operator botlaridagi 🟢 bo'sh, login qilgan operatorlarga Qabul tugmasi bilan yuboradi.
    Media file_id boshqa botniki bo'lgani uchun bir marta yuklab olamiz va qayta yuboramiz."""
    raw = None
    if content_type != "text" and file_id:
        client = cbot()
        if client:
            raw = await _download_file(client, file_id)
    for brow in await q.list_operator_bots(only_enabled=True):
        opbot = botreg.get_operator_bot(brow["id"])
        if not opbot:
            continue
        for op in await q.operators_by_bot(brow["id"]):
            if op["telegram_id"] and op["status"] == "active" and op["availability"] == "free":
                sent = await send_raw(opbot, op["telegram_id"], content_type, file_id, caption,
                                      markup=kb.order_accept_kb(order_id), raw=raw)
                if sent:
                    await q.add_order_notif(order_id, brow["id"], op["telegram_id"], sent.message_id)


async def send_first_content_to_operators(bot: Bot, order_id: int, message):
    """Yangi murojaatni (message obyektidan) operatorlar guruhiga yuboradi."""
    ct, fid, txt = extract_content(message)
    await deliver_order_to_operators(bot, order_id, ct, fid, txt)


async def forward_client_to_operator(bot: Bot, order, message):
    """Mijoz xabarini biriktirilgan operatorga BITTA xabar qilib uzatadi.
    Agar mijoz operatorning aniq xabariga 'reply' qilgan bo'lsa, operator chatida ham
    o'sha xabarga tirkalib yuboriladi."""
    operator = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    note = _client_note(message)
    caption = f"💬 Mijoz (#{order['id']}):\n{note}" if note else f"💬 Mijoz (#{order['id']})"

    if operator and operator["telegram_id"]:
        op_tg = operator["telegram_id"]
        # Operatorga UNING O'Z BOTI orqali yuboramiz
        op_bot = botreg.get_operator_bot(operator["bot_id"]) if operator["bot_id"] else (cbot() or bot)
        if not op_bot:
            op_bot = cbot() or bot
        reply_to = None
        if message.reply_to_message:
            link = await q.link_by_client_msg(message.reply_to_message.message_id, order["id"])
            if link:
                reply_to = link["operator_msg_id"]
        if reply_to is None:
            reply_to = await q.last_operator_tg_msg(order["id"])
        sent = await send_content_message(op_bot, op_tg, message, caption, reply_to=reply_to)
        if sent:
            await q.add_link(order["id"], message.message_id, sent.message_id, op_tg)
        # Kanalga ham reply qilib joylaymiz (mijoz/asosiy bot orqali)
        await post_client_to_channel(bot, order, message)
    # Aks holda (murojaat hali qabul qilinmagan) — kanalga yubormaymiz.
    # Xabar saqlanadi va operator qabul qilganda hammasi ko'rsatiladi.


# Kanaldagi yozishma uchun: order_id -> oxirgi mijoz savoli xabarining kanal message_id si
_channel_thread: dict[int, int] = {}


async def post_client_to_channel(bot: Bot, order, message):
    """Mijoz xabarini kanalga murojaat kartasiga reply qilib joylaydi (asosiy bot orqali)."""
    client = cbot() or bot
    if not (OPERATORS_GROUP_ID and order["group_msg_id"] and client):
        return
    note = _client_note(message) or "📎 (media)"
    sent = await send_content_message(client, OPERATORS_GROUP_ID, message,
                                      f"💬 Mijoz: {note}", reply_to=order["group_msg_id"])
    if sent:
        _channel_thread[order["id"]] = sent.message_id


async def post_operator_to_channel(bot: Bot, order, op_name, message=None, text=None):
    """Operator javobini kanalga mijozning oxirgi savoliga reply qilib joylaydi (asosiy bot orqali)."""
    client = cbot() or bot
    if not (OPERATORS_GROUP_ID and order["group_msg_id"] and client):
        return
    reply_to = _channel_thread.get(order["id"], order["group_msg_id"])
    if message is not None:
        note = (message.caption or message.text or "")
        await send_content_message(client, OPERATORS_GROUP_ID, message,
                                   f"👨‍⚕️ {op_name}: {note}", reply_to=reply_to)
    else:
        try:
            await client.send_message(OPERATORS_GROUP_ID, f"👨‍⚕️ {op_name}: {text}",
                                      reply_to_message_id=reply_to, allow_sending_without_reply=True)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def update_group_card(bot: Bot, order_id):
    """Kanaldagi murojaat kartasini joriy holatga ko'ra yangilaydi (asosiy bot orqali)."""
    bot = cbot() or bot
    order = await q.get_order(order_id)
    if not (OPERATORS_GROUP_ID and order and order["group_msg_id"] and bot):
        return
    info = await order_card_text(order)
    msgs = await q.order_messages(order_id)
    note = next((m["text"] for m in msgs if m["sender"] == "client" and m["text"]), "")
    op = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    extra = f"\n\n✅ <b>Qabul qildi:</b> {op['name']}" if op else ""
    caption = (f"{note}\n\n{info}" if note else info) + extra
    is_media = order["content_type"] in ("photo", "video", "document")
    try:
        if is_media:
            await bot.edit_message_caption(chat_id=OPERATORS_GROUP_ID, message_id=order["group_msg_id"],
                                           caption=caption, reply_markup=None)
        else:
            await bot.edit_message_text(chat_id=OPERATORS_GROUP_ID, message_id=order["group_msg_id"],
                                        text=caption, reply_markup=None)
    except Exception:
        pass


async def save_message_from_message(order_id, sender, message):
    ct, fid, txt = extract_content(message)
    await q.add_message(order_id, sender, ct, txt, fid, message.message_id)
