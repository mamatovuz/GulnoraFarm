"""Umumiy yordamchi funksiyalar."""
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
from config import ADMIN_IDS, OPERATORS_GROUP_ID
from database import queries as q

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
    """Rolga va tilga mos asosiy menyu: admin va/yoki operator tugmalari bilan."""
    op = await q.get_operator_by_tg(telegram_id)
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
    # Mijoz ismini bosiladigan (lichkasiga olib o'tadigan) qilamiz
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
    """Mijoz kontentini (rasm/video/hujjat/matn) BITTA xabar qilib yuboradi.
    Yuborilgan Message obyektini qaytaradi (xato bo'lsa None)."""
    kwargs = {"reply_markup": markup}
    if reply_to:
        kwargs["reply_to_message_id"] = reply_to
        kwargs["allow_sending_without_reply"] = True
    try:
        if message.photo:
            return await bot.send_photo(chat_id, message.photo[-1].file_id, caption=caption, **kwargs)
        if message.video:
            return await bot.send_video(chat_id, message.video.file_id, caption=caption, **kwargs)
        if message.document:
            return await bot.send_document(chat_id, message.document.file_id, caption=caption, **kwargs)
        return await bot.send_message(chat_id, caption, **kwargs)
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
    """Murojaatni operatorlar guruhiga BITTA xabar (kontent + caption + Qabul havolasi) qilib yuboradi."""
    if not OPERATORS_GROUP_ID:
        return
    order = await q.get_order(order_id)
    info = await order_card_text(order)
    note = (text or "").strip()
    caption = f"{note}\n\n{info}" if note else info
    username = await get_bot_username(bot)
    markup = kb.order_accept_link_kb(order_id, username)
    sent = None
    try:
        if content_type == "photo":
            sent = await bot.send_photo(OPERATORS_GROUP_ID, file_id, caption=caption, reply_markup=markup)
        elif content_type == "video":
            sent = await bot.send_video(OPERATORS_GROUP_ID, file_id, caption=caption, reply_markup=markup)
        elif content_type == "document":
            sent = await bot.send_document(OPERATORS_GROUP_ID, file_id, caption=caption, reply_markup=markup)
        else:
            sent = await bot.send_message(OPERATORS_GROUP_ID, caption, reply_markup=markup)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    if sent:
        await q.set_order_group_msg(order_id, sent.message_id)
        # Qabul qilinmagan murojaat kanalda pin (qadab) qo'yiladi. Xato bo'lsa ham jarayon to'xtamaydi.
        try:
            await bot.pin_chat_message(OPERATORS_GROUP_ID, message_id=sent.message_id,
                                       disable_notification=True)
        except Exception:
            pass


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
        # 1) mijoz biror xabarga reply qilganmi? -> operator chatidagi mos xabarni topamiz
        reply_to = None
        if message.reply_to_message:
            link = await q.link_by_client_msg(message.reply_to_message.message_id, order["id"])
            if link:
                reply_to = link["operator_msg_id"]
        # 2) aks holda operatorning oxirgi xabariga avtomatik tirkaymiz (kontekst uchun)
        if reply_to is None:
            reply_to = await q.last_operator_tg_msg(order["id"])
        sent = await send_content_message(bot, op_tg, message, caption, reply_to=reply_to)
        if sent:
            await q.add_link(order["id"], message.message_id, sent.message_id, op_tg)
        # Kanalga ham reply qilib joylaymiz (yozishma kanalda ko'rinib tursin)
        await post_client_to_channel(bot, order, message)
    # Aks holda (murojaat hali qabul qilinmagan) — kanalga yubormaymiz.
    # Xabar saqlanadi va operator qabul qilganda hammasi ko'rsatiladi.


# Kanaldagi yozishma uchun: order_id -> oxirgi mijoz savoli xabarining kanal message_id si
_channel_thread: dict[int, int] = {}


async def post_client_to_channel(bot: Bot, order, message):
    """Mijoz xabarini kanalga murojaat kartasiga reply qilib joylaydi."""
    if not (OPERATORS_GROUP_ID and order["group_msg_id"]):
        return
    note = _client_note(message) or "📎 (media)"
    sent = await send_content_message(bot, OPERATORS_GROUP_ID, message,
                                      f"💬 Mijoz: {note}", reply_to=order["group_msg_id"])
    if sent:
        _channel_thread[order["id"]] = sent.message_id


async def post_operator_to_channel(bot: Bot, order, op_name, message=None, text=None):
    """Operator javobini kanalga mijozning oxirgi savoliga reply qilib joylaydi."""
    if not (OPERATORS_GROUP_ID and order["group_msg_id"]):
        return
    reply_to = _channel_thread.get(order["id"], order["group_msg_id"])
    if message is not None:
        note = (message.caption or message.text or "")
        await send_content_message(bot, OPERATORS_GROUP_ID, message,
                                   f"👨‍⚕️ {op_name}: {note}", reply_to=reply_to)
    else:
        try:
            await bot.send_message(OPERATORS_GROUP_ID, f"👨‍⚕️ {op_name}: {text}",
                                   reply_to_message_id=reply_to, allow_sending_without_reply=True)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def update_group_card(bot: Bot, order_id):
    """Kanaldagi murojaat kartasini joriy holatga ko'ra yangilaydi (Yangi/Jarayonda/Yakunlangan...)."""
    order = await q.get_order(order_id)
    if not (OPERATORS_GROUP_ID and order and order["group_msg_id"]):
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
    tg_id = message.message_id
    if message.photo:
        await q.add_message(order_id, sender, "photo", message.caption,
                            message.photo[-1].file_id, tg_id)
    elif message.video:
        await q.add_message(order_id, sender, "video", message.caption, message.video.file_id, tg_id)
    elif message.document:
        await q.add_message(order_id, sender, "document", message.caption,
                            message.document.file_id, tg_id)
    else:
        await q.add_message(order_id, sender, "text", message.text, None, tg_id)
