"""Operator kabineti: login, murojaatlar, javob, hisob-kitob, statistika, reyting."""
import asyncio
from datetime import timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import texts as t
import locales as loc
import botreg
from config import OPERATORS_GROUP_ID, now_local, ADMIN_IDS
from states import OperatorFlow
from database import queries as q
from utils import (
    order_card_text, save_message_from_message, STATUS_LABEL, main_kb, send_content_message,
    update_group_card, post_operator_to_channel, operator_in_hours, cbot, send_raw, send_file_from,
)

router = Router()

AUTO_CLOSE_MIN = 10        # mijoz javob bermasa, necha daqiqada avto-yakunlash
IDLE_LOGOUT_MIN = 30       # operator harakatsizligi (daqiqa) -> avto-logout

# Kanaldan "Qabul qilish" bosib, lekin hali login qilmagan operatorlar uchun kutilayotgan murojaat
_pending_accept: dict[int, int] = {}


def remember_pending_accept(telegram_id: int, order_id: int):
    _pending_accept[telegram_id] = order_id


class IsOperator(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Sessiya bot bo'yicha ajratilgan: shu bot operator faqat o'z operatorini taniydi
        op = await q.get_operator_by_tg_bot(message.from_user.id, botreg.bot_id_of(message.bot))
        return bool(op and op["status"] == "active")


async def _op_of(event):
    """Event (Message/CallbackQuery) kelgan bot uchun operatorni qaytaradi.
    Bitta telegram hisobi bir nechta operator botida bir vaqtda kira oladi —
    shuning uchun operator HAR DOIM event kelgan bot bo'yicha aniqlanadi."""
    return await q.get_operator_by_tg_bot(event.from_user.id, botreg.bot_id_of(event.bot))


async def notify_client(bot: Bot, user_id: int, text: str):
    client = cbot() or bot     # mijozga doim asosiy bot yozadi
    try:
        await client.send_message(user_id, text, reply_markup=await main_kb(user_id))
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


# ---------------- Operator botida /start (faqat operatorlar uchun) ----------------
@router.message(CommandStart())
async def op_bot_start(message: Message, state: FSMContext):
    await state.clear()
    op = await q.get_operator_by_tg_bot(message.from_user.id, botreg.bot_id_of(message.bot))
    if op and op["status"] == "active":
        await _show_cabinet(message.bot, message.from_user.id, op)
    else:
        await message.answer("👋 Bu — <b>operator paneli</b>.\n\nKirish uchun: /operator")


# ---------------- Login ----------------
async def _show_cabinet(bot: Bot, chat_id: int, op):
    cnt = len(await q.orders_by_status("in_progress", op["id"]))
    await bot.send_message(
        chat_id,
        f"✅ Xush kelibsiz, <b>{op['name']}</b>!\n\nSizga biriktirilgan murojaatlar: {cnt}",
        reply_markup=kb.operator_menu(op["availability"]),
    )


async def _notify_admins_login(from_user, op, old_tg):
    """Operator botiga YANGI (boshqa) odam kirganда admin'larga xabar beradi.
    Kirgan foydalanuvchi ismi bosilса profili ochiladi."""
    if op["bot_id"] is None:
        return  # faqat operator botlari uchun
    if old_tg == from_user.id:
        return  # o'sha odam qayta kirdi — bildirmaymiz
    client = cbot()
    if not client:
        return
    brow = await q.get_operator_bot(op["bot_id"])
    bot_title = brow["title"] if brow else "Operator bot"
    name = from_user.full_name or "Foydalanuvchi"
    if from_user.username:
        who = f'<a href="https://t.me/{from_user.username}">{name}</a> (@{from_user.username})'
    else:
        who = f'<a href="tg://user?id={from_user.id}">{name}</a>'
    text = (f"🔓 <b>{bot_title}</b> botiga yangi kirish\n\n"
            f"👤 Operator hisobi: {op['name']}\n"
            f"🙍 Kim kirdi: {who}\n"
            f"🆔 <code>{from_user.id}</code>")
    for aid in ADMIN_IDS:
        try:
            await client.send_message(aid, text, disable_web_page_preview=True)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def _after_login(bot: Bot, tg_id: int, op):
    """Login bo'lgach: kabinet + kutilayotgan murojaat (agar kanaldan kelgan bo'lsa)."""
    await _show_cabinet(bot, tg_id, op)
    pending = _pending_accept.pop(tg_id, None)
    if pending:
        ok, err = await do_accept(bot, op, pending, tg_id)
        if not ok:
            await bot.send_message(tg_id, f"⚠️ {err}")


def _hours_warn(op) -> str:
    _, ws, we = operator_in_hours(op)
    return (f"🕐 Hozir sizning ish vaqtingiz emas.\n"
            f"Ish vaqtingiz: <b>{ws}–{we}</b>. Faqat shu oraliqda kira olasiz.")


@router.message(Command("operator"))
async def operator_cmd(message: Message, state: FSMContext):
    await state.clear()
    bot_id = botreg.bot_id_of(message.bot)
    op = await q.get_operator_by_tg_bot(message.from_user.id, bot_id)
    if op and op["status"] == "active":
        within, ws, we = operator_in_hours(op)
        if not within:
            await q.logout_operator(message.from_user.id, bot_id)
            await message.answer(_hours_warn(op))
            return
        await _show_cabinet(message.bot, message.from_user.id, op)
        return
    # Saqlangan login bo'lsa — tezkor kirish taklif qilamiz (faqat shu botники)
    saved = await q.saved_logins_for(message.from_user.id, bot_id)
    if saved:
        await message.answer(
            "👨‍⚕️ <b>Operator kabineti</b>\n\nQuyidagilardan birini tanlang:",
            reply_markup=kb.quick_login_kb(saved),
        )
        return
    await state.set_state(OperatorFlow.login)
    await message.answer("👨‍⚕️ <b>Operator kabineti</b>\n\n🔑 Login:", reply_markup=kb.REMOVE)


@router.callback_query(F.data.startswith("quicklogin:"))
async def quick_login(call: CallbackQuery, state: FSMContext):
    op_id = int(call.data.split(":")[1])
    op = await q.get_operator(op_id)
    if not op or op["status"] != "active":
        await q.remove_saved_login(call.from_user.id, op_id)
        await call.answer("Bu hisob mavjud emas yoki bloklangan.", show_alert=True)
        return
    if op["bot_id"] != botreg.bot_id_of(call.bot):
        await call.answer("⛔ Bu login boshqa botga tegishli. O'z botingizdan kiring.", show_alert=True)
        return
    within, ws, we = operator_in_hours(op)
    if not within:
        await call.message.answer(_hours_warn(op))
        await call.answer()
        return
    old_tg = op["telegram_id"]
    await q.login_operator(op_id, call.from_user.id)
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await _notify_admins_login(call.from_user, op, old_tg)
    await _after_login(call.bot, call.from_user.id, op)
    await call.answer("✅ Kirildi")


@router.callback_query(F.data.startswith("forgetlogin:"))
async def forget_login(call: CallbackQuery, state: FSMContext):
    op_id = int(call.data.split(":")[1])
    await q.remove_saved_login(call.from_user.id, op_id)
    saved = await q.saved_logins_for(call.from_user.id, botreg.bot_id_of(call.bot))
    if saved:
        try:
            await call.message.edit_reply_markup(reply_markup=kb.quick_login_kb(saved))
        except Exception:
            pass
        await call.answer("Saqlangan login o'chirildi 🗑", show_alert=True)
    else:
        await state.set_state(OperatorFlow.login)
        try:
            await call.message.edit_text("🗑 Saqlangan login o'chirildi.\n\n🔑 Login:")
        except Exception:
            await call.message.answer("🔑 Login:")
        await call.answer("O'chirildi 🗑")


@router.callback_query(F.data == "newlogin")
async def new_login(call: CallbackQuery, state: FSMContext):
    await state.set_state(OperatorFlow.login)
    await call.message.answer("🔑 Login:", reply_markup=kb.REMOVE)
    await call.answer()


@router.message(OperatorFlow.login)
async def op_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text.strip())
    await state.set_state(OperatorFlow.password)
    await message.answer("🔐 Parol:")


@router.message(OperatorFlow.password)
async def op_password(message: Message, state: FSMContext):
    data = await state.get_data()
    op = await q.get_operator_by_login(data["login"])
    if not op or op["password_hash"] != q.hash_password(message.text.strip()):
        await state.clear()
        await message.answer(t.OP_LOGIN_BAD)
        return
    if op["status"] != "active":
        await state.clear()
        await message.answer("⛔ Hisobingiz bloklangan. Admin bilan bog'laning.")
        return
    import botreg
    if op["bot_id"] != botreg.bot_id_of(message.bot):
        await state.clear()
        await message.answer("⛔ Bu login boshqa botga tegishli. Iltimos, o'z botingizdan kiring.")
        return
    within, ws, we = operator_in_hours(op)
    if not within:
        await state.clear()
        await message.answer(_hours_warn(op))
        return
    old_tg = op["telegram_id"]
    await q.login_operator(op["id"], message.from_user.id)
    await state.clear()
    await _notify_admins_login(message.from_user, op, old_tg)
    await _after_login(message.bot, message.from_user.id, op)
    # Login/parolni saqlash taklifi (agar hali saqlanmagan bo'lsa)
    if not await q.is_login_saved(message.from_user.id, op["id"]):
        await message.answer(
            "💾 Login va parolingizni saqlab qo'yasizmi?\n"
            "Keyingi safar parolsiz, bir bosishda kirasiz.",
            reply_markup=kb.save_login_kb(op["id"]),
        )


@router.callback_query(F.data.startswith("savelogin:"))
async def save_login_cb(call: CallbackQuery):
    op_id = int(call.data.split(":")[1])
    await q.save_login(call.from_user.id, op_id)
    try:
        await call.message.edit_text(
            "✅ Login va parol saqlandi.\nKeyingi safar /operator da bir bosishda kirasiz.")
    except Exception:
        pass
    await call.answer("Saqlandi ✅")


@router.message(IsOperator(), F.text.in_(loc.labels("op_cabinet")))
async def op_open_cabinet(message: Message):
    op = await _op_of(message)
    cnt = len(await q.orders_by_status("in_progress", op["id"]))
    await message.answer(
        f"👨‍⚕️ <b>Operator kabineti</b> — {op['name']}\n\n"
        f"Jarayondagi murojaatlaringiz: {cnt}",
        reply_markup=kb.operator_menu(op["availability"]),
    )


@router.message(IsOperator(), F.text.in_({"🟢 Holatim: Bo'sh", "🔴 Holatim: Band"}))
async def op_toggle_availability(message: Message):
    op = await _op_of(message)
    new = "busy" if op["availability"] == "free" else "free"
    await q.set_operator_availability(op["id"], new)
    label = "🟢 Bo'sh — yangi murojaatlarga tayyorsiz" if new == "free" \
        else "🔴 Band — hozircha yangi murojaat olmaysiz"
    await message.answer(f"Holatingiz o'zgartirildi: {label}", reply_markup=kb.operator_menu(new))


@router.message(IsOperator(), F.text == kb.BTN_OP_BACK)
async def op_back_to_main(message: Message):
    op = await _op_of(message)
    await _show_cabinet(message.bot, message.from_user.id, op)


@router.message(IsOperator(), F.text == "📌 Yakunlanmagan murojaatlar")
async def op_unfinished(message: Message):
    from handlers.unfinished import open_for_message
    await open_for_message(message)


@router.message(IsOperator(), F.text == "🚪 Chiqish (logout)")
async def op_logout(message: Message):
    await q.logout_operator(message.from_user.id, botreg.bot_id_of(message.bot))
    await message.answer("Kabinetdan chiqdingiz. Qayta kirish: /operator", reply_markup=kb.REMOVE)


# ---------------- Yangi murojaatlar ----------------
@router.message(IsOperator(), F.text == "📥 Yangi murojaatlar")
async def op_new_orders(message: Message):
    orders = await q.orders_by_status("new")
    if not orders:
        await message.answer("📥 Hozircha yangi (biriktirilmagan) murojaatlar yo'q.")
        return
    lines = [f"📥 Biriktirilmagan murojaatlar: {len(orders)}\n"]
    for o in orders:
        u = await q.get_user(o["user_id"])
        name = u["full_name"] if u else "—"
        lines.append(f"#{o['id']} — {name} — {o['created_at']}")
    await message.answer("\n".join(lines), reply_markup=kb.op_orders_list_kb(orders, "opnew"))


@router.callback_query(F.data.startswith("opnew:"))
async def op_view_new(call: CallbackQuery):
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    if not order:
        await call.answer("Topilmadi", show_alert=True)
        return
    await _send_order_single(call.bot, call.from_user.id, order_id,
                             "Ushbu murojaatni qabul qilasizmi?", kb.order_accept_kb(order_id))
    await call.answer()


_LABELS = {"photo": "📷 rasm", "video": "🎥 video", "document": "📄 hujjat",
           "sticker": "🎭 stiker", "animation": "🎞 GIF", "voice": "🎤 ovozli xabar"}


async def _send_one(bot, chat_id, content_type, file_id, caption, markup=None):
    """Bitta kontentni (media yoki matn) yuboradi, Message qaytaradi.
    send_raw cross-bot (operator boti mijoz file_id'sini) avtomatik hal qiladi."""
    if content_type == "sticker" and caption:
        # stiker captionsiz — avval izoh, keyin stiker
        try:
            await bot.send_message(chat_id, caption)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        return await send_raw(bot, chat_id, "sticker", file_id, None, markup=markup)
    return await send_raw(bot, chat_id, content_type, file_id, caption, markup=markup)


async def _send_order_single(bot, chat_id, order_id, extra_text, markup):
    """Murojaatni BITTA xabar qilib yuboradi:
    [mijoz yozgan matn/izoh] + murojaat kartasi + [extra_text] + inline tugmalar.
    Mijozning asl xabarini 'Reply' uchun bog'laydi."""
    order = await q.get_order(order_id)
    info = await order_card_text(order)
    msgs = await q.order_messages(order_id)
    client_msgs = [m for m in msgs if m["sender"] == "client"]
    main = client_msgs[0] if client_msgs else None

    parts = []
    if main and main["text"]:
        parts.append(main["text"])
    elif main and main["content_type"] in _LABELS:
        parts.append(f"📎 Mijoz {_LABELS[main['content_type']]} yubordi")
    parts.append(info)
    if extra_text:
        parts.append(extra_text)
    caption = "\n\n".join(parts)

    ct = main["content_type"] if main else "text"
    fid = main["file_id"] if main else None
    sent = await _send_one(bot, chat_id, ct, fid, caption, markup)

    if main and main["tg_msg_id"] and sent:
        await q.add_link(order_id, main["tg_msg_id"], sent.message_id, chat_id)

    # Qo'shimcha mijoz xabarlari bo'lsa (kam uchraydi) — alohida ko'rsatamiz va bog'laymiz
    for m in client_msgs[1:]:
        if m["text"]:
            cap = f"👤 Mijoz: {m['text']}"
        elif m["content_type"] in _LABELS:
            cap = f"👤 Mijoz {_LABELS[m['content_type']]} yubordi:"
        else:
            cap = "👤 Mijoz:"
        s2 = await _send_one(bot, chat_id, m["content_type"], m["file_id"], cap)
        if s2 and m["tg_msg_id"]:
            await q.add_link(order_id, m["tg_msg_id"], s2.message_id, chat_id)
    return sent


# ---------------- Qabul qilish ----------------
async def do_accept(bot: Bot, op, order_id: int, op_chat: int):
    """Murojaatni operatorga biriktiradi va hamma ishni operatorning shaxsiy chatiga o'tkazadi.
    (ok, xato_matni) qaytaradi."""
    order = await q.get_order(order_id)
    if not order:
        return False, "Murojaat topilmadi."
    if order["status"] != "new":
        return False, f"Murojaat #{order_id} allaqachon qabul qilingan yoki yopilgan."

    # ATOMAR qabul: parallel ishlovда faqat bitta operator yutadi
    if not await q.claim_order(order_id, op["id"]):
        return False, f"Murojaat #{order_id} allaqachon qabul qilingan yoki yopilgan."
    await q.set_operator_active_order(op["id"], order_id)
    # Qabul qilgач operator avtomatik "Band" bo'ladi — yangi murojaat push qilinmaydi
    # (shunda javob doim shu bitta mijozga to'g'ri ketadi)
    await q.set_operator_availability(op["id"], "busy")

    # 0) Boshqa operator botlaridagi bu murojaat bildirishnomasini o'chiramiz
    import botreg
    for n in await q.order_notifs(order_id):
        nb = botreg.get_operator_bot(n["bot_id"])
        if nb:
            try:
                await nb.delete_message(n["chat_id"], n["message_id"])
            except Exception:
                pass
    await q.clear_order_notifs(order_id)

    # 1) Kanaldagi xabarni YANGILAYMIZ (asosiy bot orqali): pin yechiladi, holat 🔵 Jarayonda
    client = cbot() or bot
    if order["group_msg_id"] and OPERATORS_GROUP_ID and client:
        try:
            await client.unpin_chat_message(OPERATORS_GROUP_ID, message_id=order["group_msg_id"])
        except Exception:
            pass
        await update_group_card(bot, order_id)

    # 2) Butun ish operatorning SHAXSIY chatiga — BITTA xabar bilan
    assign_text = (f"🔵 Murojaat #{order_id} sizga biriktirildi.\n"
                   f"Endi shu yerga yozgan har bir xabaringiz to'g'ridan-to'g'ri mijozga yetib boradi.")
    await _send_order_single(bot, op_chat, order_id, assign_text, kb.op_order_actions_kb(order_id))

    # 3) Mijozga xabar
    clang = await q.get_lang(order["user_id"])
    await notify_client(bot, order["user_id"], loc.t("accept_notify", clang))
    return True, None


@router.callback_query(F.data.startswith("op_accept:"))
async def op_accept(call: CallbackQuery):
    op = await _op_of(call)
    if not op or op["status"] != "active":
        await call.answer("Avval /operator orqali kabinetga kiring.", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    ok, err = await do_accept(call.bot, op, order_id, op["telegram_id"] or call.from_user.id)
    if not ok:
        await call.answer(err, show_alert=True)
        return
    await call.answer("Qabul qilindi ✅ — botga o'ting", show_alert=True)


# ---------------- Mening murojaatlarim ----------------
@router.message(IsOperator(), F.text == "📂 Mening murojaatlarim")
async def op_my_orders(message: Message):
    op = await _op_of(message)
    orders = await q.orders_by_status("in_progress", op["id"])
    if not orders:
        await message.answer("📂 Jarayondagi murojaatlaringiz yo'q.")
        return
    lines = [f"📂 Jarayondagi murojaatlaringiz: {len(orders)}\n"]
    for o in orders:
        u = await q.get_user(o["user_id"])
        lines.append(f"#{o['id']} — {u['full_name'] if u else '—'} — 🔵 Jarayonda")
    await message.answer("\n".join(lines), reply_markup=kb.op_orders_list_kb(orders, "opmine"))


@router.callback_query(F.data.startswith("opmine:"))
async def op_view_mine(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    if not order or order["operator_id"] != op["id"]:
        await call.answer("Topilmadi", show_alert=True)
        return
    await q.set_operator_active_order(op["id"], order_id)
    await _send_order_single(call.bot, call.from_user.id, order_id,
                             f"Murojaat #{order_id} — amalni tanlang:",
                             kb.op_order_actions_kb(order_id))
    await call.answer()


# ---------------- O'zimga o'tkazib olish (boshqa operatordan ham) ----------------
@router.callback_query(F.data.startswith("optake:"))
async def op_takeover(call: CallbackQuery):
    op = await _op_of(call)
    if not op or op["status"] != "active":
        await call.answer("Avval /operator orqali kabinetga kiring.", show_alert=True)
        return
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    if not order or order["status"] not in ("new", "in_progress"):
        await call.answer("Bu murojaat faol emas (yopilgan).", show_alert=True)
        return
    prev_op_id = order["operator_id"]
    if prev_op_id == op["id"]:
        # allaqachon o'ziniki — shunchaki ochamiz
        await q.set_operator_active_order(op["id"], order_id)
        await _send_order_single(call.bot, call.from_user.id, order_id,
                                 f"Murojaat #{order_id} — amalni tanlang:",
                                 kb.op_order_actions_kb(order_id))
        await call.answer("Ochildi")
        return
    # o'zimga o'tkazib olamiz
    await q.assign_order(order_id, op["id"])
    if order["status"] == "new":
        await q.set_order_status(order_id, "in_progress", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], order_id)
    await q.set_operator_availability(op["id"], "busy")
    # eski operatorni bo'shatamiz + xabar beramiz (uning o'z boti orqali)
    if prev_op_id:
        prev = await q.get_operator(prev_op_id)
        await q.set_operator_active_order(prev_op_id, None)
        await q.set_operator_availability(prev_op_id, "free")
        if prev and prev["telegram_id"]:
            import botreg
            pb = botreg.get_operator_bot(prev["bot_id"]) if prev["bot_id"] else (cbot() or call.bot)
            try:
                await (pb or call.bot).send_message(
                    prev["telegram_id"],
                    f"ℹ️ Murojaat #{order_id} <b>{op['name']}</b> tomonidan o'ziga o'tkazib olindi.")
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
    await update_group_card(call.bot, order_id)
    await _send_order_single(call.bot, call.from_user.id, order_id,
                             f"🔄 Murojaat #{order_id} sizga o'tkazildi. Endi siz javob berasiz.",
                             kb.op_order_actions_kb(order_id))
    await call.answer("✅ O'zingizga o'tkazildi", show_alert=True)


# ---------------- Javob / Hisoblash / Yakunlash / Bekor ----------------
@router.callback_query(F.data.startswith("opc:reply:"))
async def op_reply_btn(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[2])
    await q.set_operator_active_order(op["id"], order_id)
    await call.message.answer(
        f"✍️ Murojaat #{order_id}: xabaringizni yozing — mijozga yetib boradi."
    )
    await call.answer()


@router.callback_query(F.data.startswith("opc:bill:"))
async def op_bill_btn(call: CallbackQuery, state: FSMContext):
    order_id = int(call.data.split(":")[2])
    await state.set_state(OperatorFlow.bill_text)
    await state.update_data(bill_order=order_id)
    await call.message.answer(
        "Hisob-kitobni <b>matn</b> yoki <b>rasm</b> ko'rinishida yuboring 📋\n\n"
        "Masalan:\nParacetamol — 2 quti — 24 000 so'm\nJami: 24 000 so'm\n\n"
        "(Yoki hisob-kitob/chek rasmini yuborishingiz mumkin.)"
    )
    await call.answer()


@router.message(OperatorFlow.bill_text, F.photo)
async def op_bill_save_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["bill_order"]
    await q.set_order_bill(order_id, message.caption or "", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Hisob-kitob (rasm) saqlandi.\n\nMijozga yuborishni xohlaysizmi?",
                         reply_markup=kb.bill_send_kb(order_id))


@router.message(OperatorFlow.bill_text, F.text)
async def op_bill_save(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["bill_order"]
    await q.set_order_bill(order_id, message.text, None)
    await state.clear()
    await message.answer("✅ Hisob-kitob saqlandi.\n\nMijozga yuborishni xohlaysizmi?",
                         reply_markup=kb.bill_send_kb(order_id))


@router.message(OperatorFlow.bill_text)
async def op_bill_save_bad(message: Message):
    await message.answer("Iltimos, hisob-kitobni matn yoki rasm ko'rinishida yuboring.")


@router.callback_query(F.data.startswith("bill_send:"))
async def bill_send(call: CallbackQuery):
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    clang = await q.get_lang(order["user_id"])
    caption = loc.t("bill_to_client", clang, id=order_id, bill=order["bill"] or "")
    client = cbot() or call.bot
    try:
        if order["bill_photo"]:
            # bill_photo'ni operator boti (call.bot) olgan — asosiy bot orqali yuborish uchun cross-bot
            await send_file_from(client, order["user_id"], "photo", order["bill_photo"],
                                 call.bot, caption=caption)
        else:
            await client.send_message(order["user_id"], caption)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    await call.message.edit_text("✅ Hisob-kitob mijozga yuborildi.")
    await call.answer()


@router.callback_query(F.data.startswith("bill_save:"))
async def bill_save(call: CallbackQuery):
    await call.message.edit_text("✅ Hisob-kitob saqlandi (mijozga yuborilmadi).")
    await call.answer()


@router.callback_query(F.data.startswith("opc:done:"))
async def op_done(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    await q.set_order_status(order_id, "done", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], None)
    await q.set_operator_availability(op["id"], "free")   # yana bo'sh — yangi murojaat oladi
    await q.set_user_active_order(order["user_id"], None)
    await update_group_card(call.bot, order_id)   # kanalda 🟢 Yakunlangan bo'ladi
    # Mijozga yakunlash xabari + baholash tugmalari (asosiy bot orqali, mijoz tilida)
    clang = await q.get_lang(order["user_id"])
    client = cbot() or call.bot
    try:
        await client.send_message(
            order["user_id"],
            loc.t("order_done", clang, id=order_id) + loc.t("rate_ask", clang),
            reply_markup=kb.rating_kb(order_id),
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    await call.message.answer(f"🟢 Murojaat #{order_id} yakunlandi.")
    await call.answer("Yakunlandi ✅")


@router.callback_query(F.data.startswith("opc:cancel:"))
async def op_cancel(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    await q.set_order_status(order_id, "canceled", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], None)
    await q.set_user_active_order(order["user_id"], None)
    await update_group_card(call.bot, order_id)   # kanalda 🔴 Bekor qilingan bo'ladi
    clang = await q.get_lang(order["user_id"])
    await notify_client(call.bot, order["user_id"], loc.t("order_canceled", clang, id=order_id))
    await call.message.answer(f"🔴 Murojaat #{order_id} bekor qilindi.")
    await call.answer("Bekor qilindi")


# ---------------- Tayyor javob shablonlari ----------------
@router.callback_query(F.data.startswith("opc:tpl:"))
async def op_templates(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[2])
    if op:
        await q.set_operator_active_order(op["id"], order_id)
    tpls = await q.list_templates()
    if not tpls:
        await call.answer("Shablonlar yo'q. Admin qo'shishi kerak.", show_alert=True)
        return
    await call.message.answer("📝 Tayyor javobni tanlang:",
                              reply_markup=kb.templates_pick_kb(tpls, order_id))
    await call.answer()


@router.callback_query(F.data.startswith("tplsend:"))
async def op_template_send(call: CallbackQuery, bot: Bot):
    _, order_id, tpl_id = call.data.split(":")
    order_id, tpl_id = int(order_id), int(tpl_id)
    order = await q.get_order(order_id)
    tpl = await q.get_template(tpl_id)
    op = await _op_of(call)
    if not order or not tpl or not op:
        await call.answer("Topilmadi", show_alert=True)
        return
    clang = await q.get_lang(order["user_id"])
    reply_to = await q.last_client_tg_msg(order_id)
    client = cbot() or bot
    try:
        if tpl["sticker"]:
            await q.add_message(order_id, "operator", "sticker", None, tpl["sticker"], None)
            await client.send_sticker(order["user_id"], tpl["sticker"],
                                      reply_to_message_id=reply_to, allow_sending_without_reply=True)
            if OPERATORS_GROUP_ID and order["group_msg_id"]:
                try:
                    await client.send_sticker(OPERATORS_GROUP_ID, tpl["sticker"],
                                              reply_to_message_id=order["group_msg_id"],
                                              allow_sending_without_reply=True)
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
        else:
            await q.add_message(order_id, "operator", "text", tpl["text"], None, None)
            await client.send_message(order["user_id"],
                                      loc.t("operator_reply", clang, name=op["name"], text=tpl["text"]),
                                      reply_to_message_id=reply_to, allow_sending_without_reply=True)
            await post_operator_to_channel(bot, order, op["name"], text=tpl["text"])
        await call.answer("✅ Mijozga yuborildi")
    except (TelegramBadRequest, TelegramForbiddenError):
        await call.answer("Yuborib bo'lmadi", show_alert=True)


# ---------------- Mijozga filial ma'lumoti (rasm + ish vaqti + lokatsiya) yuborish ----------------
@router.callback_query(F.data.startswith("opc:sendbranch:"))
async def op_sendbranch_btn(call: CallbackQuery):
    order_id = int(call.data.split(":")[2])
    branches = await q.list_branches()
    if not branches:
        await call.answer("Filiallar qo'shilmagan", show_alert=True)
        return
    await call.message.answer("📍 Qaysi filial ma'lumotini mijozga yuboramiz?",
                              reply_markup=kb.op_send_branch_kb(branches, order_id))
    await call.answer()


@router.callback_query(F.data.startswith("opsendbr:"))
async def op_sendbranch_pick(call: CallbackQuery, bot: Bot):
    _, order_id, branch_id = call.data.split(":")
    order = await q.get_order(int(order_id))
    b = await q.get_branch(int(branch_id))
    if not order or not b:
        await call.answer("Topilmadi", show_alert=True)
        return
    client = cbot() or bot
    text = (f"🏥 <b>{b['name']}</b>\n"
            f"📍 {b['address'] or '—'}\n"
            f"📞 {b['phone'] or '—'}\n"
            f"🕐 Ish vaqti: {b['open_time']}–{b['close_time']}")
    has_loc = b["lat"] is not None and b["lon"] is not None
    markup = kb.branch_directions_kb(b["lat"], b["lon"]) if has_loc else None
    try:
        # 1) rasm + ma'lumot + "Yo'l ko'rsatish" tugmasi (rasm asosiy botniki — cross-bot kerak emas)
        if b["photo_file_id"]:
            await client.send_photo(order["user_id"], b["photo_file_id"], caption=text,
                                    reply_markup=markup)
        else:
            await client.send_message(order["user_id"], text, reply_markup=markup)
        # 2) lokatsiya — xaritada nuqta (Telegram o'zi yo'l ko'rsatishni beradi)
        if has_loc:
            await client.send_venue(order["user_id"], latitude=b["lat"], longitude=b["lon"],
                                    title=b["name"], address=b["address"] or "")
        await call.answer("✅ Filial ma'lumoti mijozga yuborildi", show_alert=True)
        try:
            await call.message.edit_text(f"✅ <b>{b['name']}</b> ma'lumoti mijozga yuborildi.")
        except Exception:
            pass
    except (TelegramBadRequest, TelegramForbiddenError):
        await call.answer("Mijozga yuborib bo'lmadi", show_alert=True)


# ---------------- Mijozdan filial tanlashni so'rash ----------------
@router.callback_query(F.data.startswith("opc:askbranch:"))
async def op_ask_branch(call: CallbackQuery, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    if not order:
        await call.answer("Murojaat topilmadi", show_alert=True)
        return
    branches = await q.list_branches()
    if not branches:
        await call.answer("Filiallar qo'shilmagan", show_alert=True)
        return
    clang = await q.get_lang(order["user_id"])
    client = cbot() or bot
    try:
        await client.send_message(order["user_id"], loc.t("op_ask_branch", clang),
                                  reply_markup=kb.op_ask_branch_kb(branches, order_id, clang))
        await call.answer("✅ Mijozga filial tanlash so'rovi yuborildi", show_alert=True)
    except (TelegramBadRequest, TelegramForbiddenError):
        await call.answer("Mijozga yuborib bo'lmadi", show_alert=True)


# ---------------- Murojaatni boshqa operatorga uzatish ----------------
@router.callback_query(F.data.startswith("opc:transfer:"))
async def op_transfer(call: CallbackQuery):
    op = await _op_of(call)
    order_id = int(call.data.split(":")[2])
    ops = await q.active_operators(exclude_id=op["id"] if op else None)
    if not ops:
        await call.answer("Uzatish uchun boshqa operator yo'q.", show_alert=True)
        return
    await call.message.answer("🔄 Qaysi operatorga uzatamiz?",
                              reply_markup=kb.transfer_pick_kb(ops, order_id))
    await call.answer()


@router.callback_query(F.data.startswith("dotransfer:"))
async def op_do_transfer(call: CallbackQuery, bot: Bot):
    _, order_id, newop_id = call.data.split(":")
    order_id, newop_id = int(order_id), int(newop_id)
    order = await q.get_order(order_id)
    cur_op = await _op_of(call)
    new_op = await q.get_operator(newop_id)
    if not order or not new_op:
        await call.answer("Topilmadi", show_alert=True)
        return
    await q.assign_order(order_id, newop_id)
    if cur_op:
        await q.set_operator_active_order(cur_op["id"], None)
        await q.set_operator_availability(cur_op["id"], "free")
    await q.set_operator_active_order(newop_id, order_id)
    await q.set_operator_availability(newop_id, "busy")
    await call.message.edit_text(f"✅ Murojaat #{order_id} → {new_op['name']} ga uzatildi.")
    await update_group_card(bot, order_id)
    if new_op["telegram_id"]:
        # Yangi operatorga UNING O'Z BOTI orqali yuboramiz
        import botreg
        nb = botreg.get_operator_bot(new_op["bot_id"]) if new_op["bot_id"] else (cbot() or bot)
        nb = nb or (cbot() or bot)
        try:
            await nb.send_message(
                new_op["telegram_id"],
                f"🔄 Sizga murojaat #{order_id} uzatildi"
                + (f" ({cur_op['name']} dan)." if cur_op else "."))
            await _send_order_single(nb, new_op["telegram_id"], order_id,
                                     f"Murojaat #{order_id} — amalni tanlang:",
                                     kb.op_order_actions_kb(order_id))
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    await call.answer("Uzatildi ✅")


# ---------------- 10 daqiqada avto-yakunlash ----------------
async def _finish_with_rating(bot: Bot, order_id: int, by: str):
    """Murojaatni yakunlaydi va mijozga baholash so'rovini yuboradi."""
    order = await q.get_order(order_id)
    await q.set_order_status(order_id, "done", by)
    if order["operator_id"]:
        await q.set_operator_active_order(order["operator_id"], None)
        await q.set_operator_availability(order["operator_id"], "free")
    await q.set_user_active_order(order["user_id"], None)
    await update_group_card(bot, order_id)
    clang = await q.get_lang(order["user_id"])
    client = cbot() or bot
    try:
        await client.send_message(
            order["user_id"],
            loc.t("order_done", clang, id=order_id) + loc.t("rate_ask", clang),
            reply_markup=kb.rating_kb(order_id),
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


async def _auto_close_task(bot: Bot, order_id: int, armed_at: str, operator_tg: int):
    await asyncio.sleep(AUTO_CLOSE_MIN * 60)
    order = await q.get_order(order_id)
    if not order or order["status"] != "in_progress":
        return  # allaqachon yopilgan/bekor qilingan
    last_client = await q.last_client_msg_time(order_id)
    if last_client and last_client > armed_at:
        return  # mijoz javob berdi -> avto-yakunlash bekor
    await _finish_with_rating(bot, order_id, "auto")
    try:
        await bot.send_message(
            operator_tg,
            f"⏱ Murojaat #{order_id} mijoz {AUTO_CLOSE_MIN} daqiqa javob bermagani uchun "
            f"avtomatik yakunlandi.",
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


@router.callback_query(F.data.startswith("opc:autoclose:"))
async def op_autoclose(call: CallbackQuery):
    op = await _op_of(call)
    if not op:
        await call.answer("Avval /operator orqali kiring.", show_alert=True)
        return
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    if not order or order["status"] != "in_progress":
        await call.answer("Bu murojaat faol emas.", show_alert=True)
        return
    armed_at = q.now()
    asyncio.create_task(_auto_close_task(call.bot, order_id, armed_at, call.from_user.id))
    # Mijozni darhol ogohlantiramiz (uning tilida, asosiy bot orqali)
    clang = await q.get_lang(order["user_id"])
    client = cbot() or call.bot
    try:
        await client.send_message(order["user_id"],
                                  loc.t("auto_close_warning", clang, min=AUTO_CLOSE_MIN))
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    await call.answer(
        f"⏱ Yoqildi! Mijozga ogohlantirish yuborildi. "
        f"Agar {AUTO_CLOSE_MIN} daqiqa ichida javob bermasa, murojaat avtomatik yakunlanadi.",
        show_alert=True,
    )


# ---------------- Har operatorni o'z ish vaqti tugaganda avto-logout ----------------
async def op_workhours_loop(bot: Bot):
    """Har daqiqada tekshiradi: kimning ish vaqti tugagan bo'lsa, o'shani chiqaradi."""
    while True:
        await asyncio.sleep(60)
        try:
            import botreg
            for op in await q.logged_in_operators():
                within, ws, we = operator_in_hours(op)
                if within:
                    continue
                tg = op["telegram_id"]
                await q.logout_operator(tg, op["bot_id"])
                ob = botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else bot
                try:
                    await (ob or bot).send_message(
                        tg,
                        f"🕐 Ish vaqtingiz tugadi ({ws}–{we}).\n"
                        f"Tizimdan chiqdingiz. Ish vaqti boshlanganda /operator orqali qayta kiring.",
                        reply_markup=kb.REMOVE,
                    )
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
        except Exception:
            pass


# ---------------- Yakunlanganlar ----------------
@router.message(IsOperator(), F.text == "✅ Yakunlanganlar")
async def op_done_list(message: Message):
    op = await _op_of(message)
    orders = await q.orders_by_status("done", op["id"])
    if not orders:
        await message.answer("Yakunlangan murojaatlaringiz yo'q.")
        return
    lines = [f"✅ Yakunlangan murojaatlar: {len(orders)}\n"]
    for o in orders[:30]:
        u = await q.get_user(o["user_id"])
        lines.append(f"#{o['id']} — {u['full_name'] if u else '—'} — {o['closed_at'] or ''}")
    await message.answer("\n".join(lines))


# ---------------- Statistika ----------------
@router.message(IsOperator(), F.text == "📊 Mening statistikam")
async def op_my_stats(message: Message):
    op = await _op_of(message)
    s = await q.operator_stats(op["id"])
    await message.answer(
        "📊 <b>Statistikangiz</b>\n\n"
        f"📥 Qabul qilingan murojaatlar: {s['accepted']}\n"
        f"✅ Yakunlangan murojaatlar: {s['done']}\n"
        f"💊 Hisoblangan retseptlar: {s['billed']}\n\n"
        f"📅 Bugungi natija: {s['today_done']} murojaat yakunlandi\n"
        f"📆 Oylik natija: {s['month_done']} murojaat yakunlandi\n\n"
        f"⭐ O'rtacha baho: {s['avg_rating']} ({s['rated_count']} ta baho)"
    )


# ---------------- Reyting ----------------
@router.message(IsOperator(), F.text == "🏆 Reyting")
async def op_rating(message: Message):
    rating = await q.operators_rating()
    medals = ["🥇 1-o'rin", "🥈 2-o'rin", "🥉 3-o'rin"]
    lines = ["🏆 <b>Operatorlar reytingi (shu oy)</b>\n"]
    for i, r in enumerate(rating[:10]):
        place = medals[i] if i < 3 else f"{i+1}."
        star = f" • ⭐{r['avg_rating']}" if r["avg_rating"] else ""
        lines.append(f"{place} — {r['name']} — {r['score']} ball{star}")
    lines.append("\nReyting: yakunlangan murojaatlar + hisoblangan retseptlar asosida.")
    await message.answer("\n".join(lines))


# ---------------- Operator proxy: erkin xabar -> mijozga ----------------
@router.message(IsOperator(), F.chat.type == "private",
                F.content_type.in_({"text", "photo", "document", "video", "sticker", "animation", "voice"}),
                ~F.text.in_(kb.ALL_MENU_BUTTONS))
async def operator_proxy(message: Message, bot: Bot):
    op = await _op_of(message)

    # MANZILNI ANIQLAYMIZ:
    # 1) Operator biror mijoz xabariga 'reply' qilgan bo'lsa -> javob AYNAN o'sha murojaatga ketadi
    #    (active_order_id emas — shuning uchun #169 ga reply qilsa #172 ga ketib qolmaydi)
    reply_to = None
    target = None
    if message.reply_to_message:
        link = await q.link_by_operator_msg(message.reply_to_message.message_id, message.from_user.id)
        if link:
            target = link["order_id"]
            reply_to = link["client_msg_id"]
    # 2) Reply qilinmagan bo'lsa -> joriy faol murojaat
    if target is None:
        target = op["active_order_id"]
    if not target:
        await message.answer("Avval \"📂 Mening murojaatlarim\" dan murojaat tanlang yoki qabul qiling.")
        return
    order = await q.get_order(target)
    if not order or order["status"] not in ("new", "in_progress"):
        if target == op["active_order_id"]:
            await q.set_operator_active_order(op["id"], None)
        await message.answer("Bu murojaat yopilgan. Boshqa murojaat tanlang.")
        return
    # reply orqali boshqa murojaatga javob berildi -> faol murojaatni o'shanga o'tkazamiz
    if target != op["active_order_id"]:
        await q.set_operator_active_order(op["id"], target)
    active = target
    await save_message_from_message(active, "operator", message)
    clang = await q.get_lang(order["user_id"])
    caption = loc.t("operator_reply", clang, name=op["name"],
                    text=message.caption or message.text or "")

    # tirkash: reply bo'lmasa mijozning oxirgi xabariga
    if reply_to is None:
        reply_to = await q.last_client_tg_msg(active)

    client = cbot() or bot
    sent = await send_content_message(client, order["user_id"], message, caption, reply_to=reply_to)
    if sent:
        # operatorning bu xabarini bog'laymiz: mijoz keyin shunga reply qilsa ishlasin
        await q.add_link(active, sent.message_id, message.message_id, message.from_user.id)
        # Kanalga ham reply qilib joylaymiz (mijozning savoliga javob sifatida)
        await post_operator_to_channel(bot, order, op["name"], message=message)
        await message.answer(f"✅ Mijozga yuborildi (#{active}).")
    else:
        await message.answer("⚠️ Mijozga yuborib bo'lmadi (botni bloklagan bo'lishi mumkin).")
