"""Operator kabineti: login, murojaatlar, javob, hisob-kitob, statistika, reyting."""
import asyncio
from datetime import timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import texts as t
import locales as loc
from config import OPERATORS_GROUP_ID, now_local
from states import OperatorFlow
from database import queries as q
from utils import (
    order_card_text, save_message_from_message, STATUS_LABEL, main_kb, send_content_message,
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
        op = await q.get_operator_by_tg(message.from_user.id)
        return bool(op and op["status"] == "active")


async def notify_client(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text, reply_markup=await main_kb(user_id))
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


# ---------------- Login ----------------
@router.message(Command("operator"))
async def operator_cmd(message: Message, state: FSMContext):
    await state.clear()
    op = await q.get_operator_by_tg(message.from_user.id)
    if op and op["status"] == "active":
        cnt = len(await q.orders_by_status("in_progress", op["id"]))
        await message.answer(
            f"✅ Xush kelibsiz, <b>{op['name']}</b>!\n\nSizga biriktirilgan murojaatlar: {cnt}",
            reply_markup=kb.operator_menu(op["availability"]),
        )
        return
    await state.set_state(OperatorFlow.login)
    await message.answer("👨‍⚕️ <b>Operator kabineti</b>\n\n🔑 Login:", reply_markup=kb.REMOVE)


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
    await q.login_operator(op["id"], message.from_user.id)
    await state.clear()
    cnt = len(await q.orders_by_status("in_progress", op["id"]))
    await message.answer(
        f"✅ Xush kelibsiz, <b>{op['name']}</b>!\n\nSizga biriktirilgan murojaatlar: {cnt}",
        reply_markup=kb.operator_menu(op["availability"]),
    )
    # Kanaldan "Qabul qilish" bosib kelgan bo'lsa — o'sha murojaatni avtomatik ochamiz
    pending = _pending_accept.pop(message.from_user.id, None)
    if pending:
        ok, err = await do_accept(message.bot, op, pending, message.from_user.id)
        if not ok:
            await message.answer(f"⚠️ {err}")


@router.message(IsOperator(), F.text.in_(loc.labels("op_cabinet")))
async def op_open_cabinet(message: Message):
    op = await q.get_operator_by_tg(message.from_user.id)
    cnt = len(await q.orders_by_status("in_progress", op["id"]))
    await message.answer(
        f"👨‍⚕️ <b>Operator kabineti</b> — {op['name']}\n\n"
        f"Jarayondagi murojaatlaringiz: {cnt}",
        reply_markup=kb.operator_menu(op["availability"]),
    )


@router.message(IsOperator(), F.text.in_({"🟢 Holatim: Bo'sh", "🔴 Holatim: Band"}))
async def op_toggle_availability(message: Message):
    op = await q.get_operator_by_tg(message.from_user.id)
    new = "busy" if op["availability"] == "free" else "free"
    await q.set_operator_availability(op["id"], new)
    label = "🟢 Bo'sh — yangi murojaatlarga tayyorsiz" if new == "free" \
        else "🔴 Band — hozircha yangi murojaat olmaysiz"
    await message.answer(f"Holatingiz o'zgartirildi: {label}", reply_markup=kb.operator_menu(new))


@router.message(IsOperator(), F.text == kb.BTN_OP_BACK)
async def op_back_to_main(message: Message):
    await message.answer("🏠 Bosh menyu", reply_markup=await main_kb(message.from_user.id))


@router.message(IsOperator(), F.text == "🚪 Chiqish (logout)")
async def op_logout(message: Message):
    await q.logout_operator(message.from_user.id)
    await message.answer("Kabinetdan chiqdingiz. Qayta kirish: /operator",
                         reply_markup=await main_kb(message.from_user.id))


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


_LABELS = {"photo": "📷 rasm", "video": "🎥 video", "document": "📄 hujjat"}


async def _send_one(bot, chat_id, content_type, file_id, caption, markup=None):
    """Bitta kontentni (media yoki matn) yuboradi, Message qaytaradi."""
    try:
        if content_type == "photo":
            return await bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        if content_type == "video":
            return await bot.send_video(chat_id, file_id, caption=caption, reply_markup=markup)
        if content_type == "document":
            return await bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        return await bot.send_message(chat_id, caption, reply_markup=markup)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None


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

    await q.assign_order(order_id, op["id"])
    await q.set_order_status(order_id, "in_progress", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], order_id)

    # 1) Guruhdagi xabarni YANGILAYMIZ: tugma olib tashlanadi, holat o'zgaradi, kim olgani yoziladi
    if order["group_msg_id"] and OPERATORS_GROUP_ID:
        fresh = await q.get_order(order_id)            # endi holat 🔵 Jarayonda
        info = await order_card_text(fresh)
        msgs = await q.order_messages(order_id)
        note = next((m["text"] for m in msgs if m["sender"] == "client" and m["text"]), "")
        new_caption = (f"{note}\n\n{info}" if note else info) + \
                      f"\n\n✅ <b>Qabul qildi:</b> {op['name']}"
        is_media = (fresh["content_type"] in ("photo", "video", "document"))
        try:
            if is_media:
                await bot.edit_message_caption(chat_id=OPERATORS_GROUP_ID,
                                               message_id=order["group_msg_id"],
                                               caption=new_caption, reply_markup=None)
            else:
                await bot.edit_message_text(chat_id=OPERATORS_GROUP_ID,
                                            message_id=order["group_msg_id"],
                                            text=new_caption, reply_markup=None)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass

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
    op = await q.get_operator_by_tg(call.from_user.id)
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
    op = await q.get_operator_by_tg(message.from_user.id)
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
    op = await q.get_operator_by_tg(call.from_user.id)
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


# ---------------- Javob / Hisoblash / Yakunlash / Bekor ----------------
@router.callback_query(F.data.startswith("opc:reply:"))
async def op_reply_btn(call: CallbackQuery):
    op = await q.get_operator_by_tg(call.from_user.id)
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
        "Hisoblangan summa va dorilar ro'yxatini kiriting:\n\n"
        "Masalan:\nParacetamol — 2 quti — 24 000 so'm\nJami: 24 000 so'm"
    )
    await call.answer()


@router.message(OperatorFlow.bill_text)
async def op_bill_save(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["bill_order"]
    await q.set_order_bill(order_id, message.text)
    await state.clear()
    await message.answer("✅ Hisob-kitob saqlandi.\n\nMijozga yuborishni xohlaysizmi?",
                         reply_markup=kb.bill_send_kb(order_id))


@router.callback_query(F.data.startswith("bill_send:"))
async def bill_send(call: CallbackQuery):
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    clang = await q.get_lang(order["user_id"])
    await notify_client(call.bot, order["user_id"],
                        loc.t("bill_to_client", clang, id=order_id, bill=order["bill"]))
    await call.message.edit_text("✅ Hisob-kitob mijozga yuborildi.")
    await call.answer()


@router.callback_query(F.data.startswith("bill_save:"))
async def bill_save(call: CallbackQuery):
    await call.message.edit_text("✅ Hisob-kitob saqlandi (mijozga yuborilmadi).")
    await call.answer()


@router.callback_query(F.data.startswith("opc:done:"))
async def op_done(call: CallbackQuery):
    op = await q.get_operator_by_tg(call.from_user.id)
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    await q.set_order_status(order_id, "done", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], None)
    await q.set_user_active_order(order["user_id"], None)
    # Mijozga yakunlash xabari + baholash tugmalari (mijoz tilida)
    clang = await q.get_lang(order["user_id"])
    try:
        await call.bot.send_message(
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
    op = await q.get_operator_by_tg(call.from_user.id)
    order_id = int(call.data.split(":")[2])
    order = await q.get_order(order_id)
    await q.set_order_status(order_id, "canceled", f"operator:{op['id']}")
    await q.set_operator_active_order(op["id"], None)
    await q.set_user_active_order(order["user_id"], None)
    clang = await q.get_lang(order["user_id"])
    await notify_client(call.bot, order["user_id"], loc.t("order_canceled", clang, id=order_id))
    await call.message.answer(f"🔴 Murojaat #{order_id} bekor qilindi.")
    await call.answer("Bekor qilindi")


# ---------------- Tayyor javob shablonlari ----------------
@router.callback_query(F.data.startswith("opc:tpl:"))
async def op_templates(call: CallbackQuery):
    op = await q.get_operator_by_tg(call.from_user.id)
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
    if not order or not tpl:
        await call.answer("Topilmadi", show_alert=True)
        return
    await q.add_message(order_id, "operator", "text", tpl["text"], None, None)
    clang = await q.get_lang(order["user_id"])
    reply_to = await q.last_client_tg_msg(order_id)
    try:
        await bot.send_message(order["user_id"], loc.t("operator_reply", clang, text=tpl["text"]),
                               reply_to_message_id=reply_to, allow_sending_without_reply=True)
        await call.answer("✅ Mijozga yuborildi")
    except (TelegramBadRequest, TelegramForbiddenError):
        await call.answer("Yuborib bo'lmadi", show_alert=True)


# ---------------- Murojaatni boshqa operatorga uzatish ----------------
@router.callback_query(F.data.startswith("opc:transfer:"))
async def op_transfer(call: CallbackQuery):
    op = await q.get_operator_by_tg(call.from_user.id)
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
    cur_op = await q.get_operator_by_tg(call.from_user.id)
    new_op = await q.get_operator(newop_id)
    if not order or not new_op:
        await call.answer("Topilmadi", show_alert=True)
        return
    await q.assign_order(order_id, newop_id)
    if cur_op:
        await q.set_operator_active_order(cur_op["id"], None)
    await q.set_operator_active_order(newop_id, order_id)
    await call.message.edit_text(f"✅ Murojaat #{order_id} → {new_op['name']} ga uzatildi.")
    if new_op["telegram_id"]:
        try:
            await bot.send_message(
                new_op["telegram_id"],
                f"🔄 Sizga murojaat #{order_id} uzatildi"
                + (f" ({cur_op['name']} dan)." if cur_op else "."))
            await _send_order_single(bot, new_op["telegram_id"], order_id,
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
    await q.set_user_active_order(order["user_id"], None)
    clang = await q.get_lang(order["user_id"])
    try:
        await bot.send_message(
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
    op = await q.get_operator_by_tg(call.from_user.id)
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
    await call.answer(
        f"⏱ Yoqildi! Agar mijoz {AUTO_CLOSE_MIN} daqiqa ichida javob bermasa, "
        f"murojaat avtomatik yakunlanadi.",
        show_alert=True,
    )


# ---------------- Operatorlarni avto-logout (30 daqiqa harakatsizlik) ----------------
async def auto_logout_loop(bot: Bot):
    """Har daqiqada tekshiradi: 30 daqiqa harakatsiz operatorlarni tizimdan chiqaradi."""
    while True:
        await asyncio.sleep(60)
        try:
            threshold = (now_local() - timedelta(minutes=IDLE_LOGOUT_MIN)).strftime("%Y-%m-%d %H:%M:%S")
            for op in await q.idle_operators(threshold):
                tg = op["telegram_id"]
                await q.logout_operator(tg)
                try:
                    await bot.send_message(
                        tg,
                        f"⏱ {IDLE_LOGOUT_MIN} daqiqa harakatsizlik tufayli tizimdan chiqdingiz.\n"
                        f"Qayta kirish: /operator",
                        reply_markup=await main_kb(tg),
                    )
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
        except Exception:
            pass


# ---------------- Yakunlanganlar ----------------
@router.message(IsOperator(), F.text == "✅ Yakunlanganlar")
async def op_done_list(message: Message):
    op = await q.get_operator_by_tg(message.from_user.id)
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
    op = await q.get_operator_by_tg(message.from_user.id)
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
                F.content_type.in_({"text", "photo", "document", "video"}),
                ~F.text.in_(kb.ALL_MENU_BUTTONS))
async def operator_proxy(message: Message, bot: Bot):
    op = await q.get_operator_by_tg(message.from_user.id)
    active = op["active_order_id"]
    if not active:
        await message.answer("Avval \"📂 Mening murojaatlarim\" dan murojaat tanlang yoki qabul qiling.")
        return
    order = await q.get_order(active)
    if not order or order["status"] not in ("new", "in_progress"):
        await q.set_operator_active_order(op["id"], None)
        await message.answer("Faol murojaat yopilgan. Boshqa murojaat tanlang.")
        return
    await save_message_from_message(active, "operator", message)
    clang = await q.get_lang(order["user_id"])
    caption = loc.t("operator_reply", clang, text=message.caption or message.text or "")

    # 1) Operator aniq bir xabarga 'reply' qilgan bo'lsa -> o'sha mijoz xabariga tirkaymiz
    reply_to = None
    if message.reply_to_message:
        link = await q.link_by_operator_msg(message.reply_to_message.message_id, message.from_user.id)
        if link:
            reply_to = link["client_msg_id"]
    # 2) Aks holda AVTOMATIK ravishda mijozning oxirgi xabariga tirkaymiz
    #    (shunda javob aynan qaysi xabarga ekani mijozga ko'rinadi)
    if reply_to is None:
        reply_to = await q.last_client_tg_msg(active)

    sent = await send_content_message(bot, order["user_id"], message, caption, reply_to=reply_to)
    if sent:
        # operatorning bu xabarini bog'laymiz: mijoz keyin shunga reply qilsa ishlasin
        await q.add_link(active, sent.message_id, message.message_id, message.from_user.id)
        await message.answer(f"✅ Mijozga yuborildi (#{active}).")
    else:
        await message.answer("⚠️ Mijozga yuborib bo'lmadi (botni bloklagan bo'lishi mumkin).")
