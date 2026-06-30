"""Asosiy menyu bo'limlari: FAQ, Filiallar, Bog'lanish."""
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import locales as loc
import botreg
from config import OPERATORS_GROUP_ID
from states import ContactFlow, NearestFlow
from database import queries as q
from utils import (main_kb, extract_content, deliver_order_to_operators, haversine_km, work_hours,
                   update_group_card)

router = Router()


# ---------------- Kanaldagi "pinned a message" xizmat xabarlarini avtomatik o'chirish ----------------
async def _delete_pin_service(message: Message):
    if OPERATORS_GROUP_ID and message.chat.id == OPERATORS_GROUP_ID:
        try:
            await message.delete()
        except Exception:
            pass


@router.message(F.pinned_message)
async def remove_pin_service_msg(message: Message):
    await _delete_pin_service(message)


@router.channel_post(F.pinned_message)
async def remove_pin_service_channel(message: Message):
    await _delete_pin_service(message)


def _branches_header(lang):
    return loc.t("branches_header", lang)


# ---------------- Eng yaqin filial (asosiy menyu tugmasi) ----------------
@router.message(F.text.in_(loc.labels("nearest")))
async def nearest_ask(message: Message, state: FSMContext):
    await state.clear()
    lang = await q.get_lang(message.from_user.id)
    await state.set_state(NearestFlow.waiting_location)
    await message.answer(loc.t("nearest_ask", lang), reply_markup=kb.client_location_kb(lang))


async def _select_branch_for_order(bot, user_id, order_id, branch_id):
    """Operator so'rovi bo'yicha tanlangan filialni murojaatga va profilga yozadi.
    Filial oldin bo'lgan bo'lsa ham, har doim yangisiga o'zgaradi."""
    await q.set_order_branch(order_id, branch_id)
    await q.set_user_branch(user_id, branch_id)   # har doim yangisiga almashadi
    await update_group_card(bot, order_id)
    order = await q.get_order(order_id)
    op = await q.get_operator(order["operator_id"]) if order and order["operator_id"] else None
    b = await q.get_branch(branch_id)
    if op and op["telegram_id"]:
        ob = botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else bot
        ob = ob or bot
        try:
            await ob.send_message(op["telegram_id"],
                                  f"🏥 Mijoz #{order_id} uchun filial tanladi: <b>{b['name']}</b>")
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


@router.message(NearestFlow.waiting_location, F.location)
async def nearest_result(message: Message, state: FSMContext, bot: Bot):
    lang = await q.get_lang(message.from_user.id)
    data = await state.get_data()
    branch_order = data.get("branch_order")
    await state.clear()
    branches = [b for b in await q.list_branches() if b["lat"] is not None and b["lon"] is not None]
    if not branches:
        await message.answer(loc.t("nearest_none", lang), reply_markup=await main_kb(message.from_user.id))
        return
    ulat, ulon = message.location.latitude, message.location.longitude
    nearest = min(branches, key=lambda b: haversine_km(ulat, ulon, b["lat"], b["lon"]))
    km = haversine_km(ulat, ulon, nearest["lat"], nearest["lon"])
    # Operator so'rovi bo'yicha — eng yaqinni murojaatga tanlaymiz
    if branch_order:
        await _select_branch_for_order(bot, message.from_user.id, branch_order, nearest["id"])
        await message.answer(loc.t("op_branch_chosen", lang, branch=nearest["name"]),
                             reply_markup=await main_kb(message.from_user.id))
        return
    hours = f"{nearest['open_time'] or '08:00'} — {nearest['close_time'] or '23:00'}"
    caption = loc.t("nearest_result", lang, km=km) + "\n\n" + loc.t(
        "branch_card", lang, name=nearest["name"],
        address=nearest["address"] or "—", phone=nearest["phone"] or "—", hours=hours)
    await message.answer(caption, reply_markup=await main_kb(message.from_user.id))
    await message.answer_location(latitude=nearest["lat"], longitude=nearest["lon"])


# ---------------- Operator so'rovi bo'yicha filial tanlash ----------------
@router.callback_query(F.data.startswith("opbr:"))
async def op_branch_pick(call: CallbackQuery, bot: Bot):
    _, oid, bid = call.data.split(":")
    oid, bid = int(oid), int(bid)
    lang = await q.get_lang(call.from_user.id)
    b = await q.get_branch(bid)
    order = await q.get_order(oid)
    if not b or not order:
        await call.answer("Topilmadi", show_alert=True)
        return
    await _select_branch_for_order(bot, call.from_user.id, oid, bid)
    try:
        await call.message.edit_text(loc.t("op_branch_chosen", lang, branch=b["name"]))
    except Exception:
        pass
    await call.answer("✅")


@router.callback_query(F.data.startswith("opbrnear:"))
async def op_branch_near(call: CallbackQuery, state: FSMContext):
    oid = int(call.data.split(":")[1])
    lang = await q.get_lang(call.from_user.id)
    await state.set_state(NearestFlow.waiting_location)
    await state.update_data(branch_order=oid)
    await call.message.answer(loc.t("nearest_ask", lang), reply_markup=kb.client_location_kb(lang))
    await call.answer()


# ---------------- Mening murojaatlarim ----------------
@router.message(F.text.in_(loc.labels("my_orders")))
async def my_orders(message: Message, state: FSMContext):
    await state.clear()
    lang = await q.get_lang(message.from_user.id)
    orders = await q.orders_by_user(message.from_user.id)
    if not orders:
        await message.answer(loc.t("my_orders_empty", lang))
        return
    await message.answer(loc.t("my_orders_header", lang), reply_markup=kb.my_orders_kb(orders))


@router.callback_query(F.data.startswith("myorder:"))
async def my_order_detail(call: CallbackQuery):
    from utils import fmt_dt
    lang = await q.get_lang(call.from_user.id)
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    if not order or order["user_id"] != call.from_user.id:
        await call.answer("Topilmadi", show_alert=True)
        return
    rating = loc.t("rating_line", lang, r=order["rating"]) if order["rating"] else ""
    text = loc.t("my_order_detail", lang, id=order_id, date=fmt_dt(order["created_at"]),
                 status=loc.status_label(order["status"], lang), rating=rating)
    markup = kb.my_order_cancel_kb(order_id, lang) if order["status"] in ("new", "in_progress") else None
    await call.message.answer(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("myordercancel:"))
async def my_order_cancel(call: CallbackQuery, bot: Bot):
    lang = await q.get_lang(call.from_user.id)
    order_id = int(call.data.split(":")[1])
    order = await q.get_order(order_id)
    if not order or order["user_id"] != call.from_user.id:
        await call.answer("Topilmadi", show_alert=True)
        return
    if order["status"] not in ("new", "in_progress"):
        await call.answer("Bu murojaat allaqachon yopilgan.", show_alert=True)
        return
    await q.set_order_status(order_id, "canceled", f"client:{call.from_user.id}")
    await q.set_user_active_order(call.from_user.id, None)
    # Kanalda pin turgan bo'lsa — yechamiz
    if order["group_msg_id"] and OPERATORS_GROUP_ID:
        try:
            await bot.unpin_chat_message(OPERATORS_GROUP_ID, message_id=order["group_msg_id"])
        except Exception:
            pass
    # operatorni/guruhni xabardor qilamiz
    note = f"🔴 Murojaat #{order_id} ni mijoz o'zi bekor qildi."
    op = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    if op:
        await q.set_operator_active_order(op["id"], None)
    # operatorga — uning boti orqali
    if op and op["telegram_id"]:
        ob = botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else bot
        try:
            await (ob or bot).send_message(op["telegram_id"], note)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    # kanalga — asosiy bot orqali
    if OPERATORS_GROUP_ID:
        try:
            await bot.send_message(OPERATORS_GROUP_ID, note)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    # bekor qilingach kanaldagi kartani yangilaymiz
    await update_group_card(bot, order_id)
    try:
        await call.message.edit_text(loc.t("order_canceled_by_user", lang, id=order_id))
    except Exception:
        pass
    await call.answer("Bekor qilindi")


# ---------------- FAQ ----------------
@router.message(F.text.in_(loc.labels("faq")))
async def faq_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await q.get_lang(message.from_user.id)
    enabled = (await q.get_setting("faq_enabled", "1")) != "0"
    faqs = await q.list_faqs()
    if not enabled or not faqs:
        # Bo'lim o'chirilgan yoki savol yo'q — menyuni yangilaymiz (tugma yo'qoladi)
        await message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(message.from_user.id))
        return
    await message.answer(loc.t("faq_menu", lang), reply_markup=kb.faq_kb(faqs))


@router.callback_query(F.data.startswith("faq:"))
async def faq_show(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    faq_id = int(call.data.split(":")[1])
    faq = await q.get_faq(faq_id)
    if not faq:
        await call.answer("Topilmadi", show_alert=True)
        return
    await call.message.edit_text(
        f"<b>{faq['title']}</b>\n\n{faq['answer']}", reply_markup=kb.faq_back_kb(lang)
    )
    await call.answer()


@router.callback_query(F.data == "faq_back")
async def faq_back(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    faqs = await q.list_faqs()
    await call.message.edit_text(loc.t("faq_menu", lang), reply_markup=kb.faq_kb(faqs))
    await call.answer()


# ---------------- Filiallar ----------------
@router.message(F.text.in_(loc.labels("branches")))
async def branches_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await q.get_lang(message.from_user.id)
    branches = await q.list_branches()
    if not branches:
        await message.answer(loc.t("no_branches", lang))
        return
    await message.answer(_branches_header(lang), reply_markup=kb.branches_list_kb(branches, lang))


@router.callback_query(F.data.startswith("branch_info:"))
async def branch_info(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    branch_id = int(call.data.split(":")[1])
    b = await q.get_branch(branch_id)
    if not b:
        await call.answer("Filial topilmadi", show_alert=True)
        return
    hours = f"{b['open_time'] or '08:00'} — {b['close_time'] or '23:00'}"
    caption = loc.t("branch_card", lang, name=b["name"],
                    address=b["address"] or "—", phone=b["phone"] or "—", hours=hours)
    has_loc = b["lat"] is not None and b["lon"] is not None
    markup = kb.branch_card_kb(branch_id, has_loc, lang)
    if b["photo_file_id"]:
        await call.message.answer_photo(b["photo_file_id"], caption=caption, reply_markup=markup)
    else:
        await call.message.answer(caption, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("branch_map:"))
async def branch_map(call: CallbackQuery):
    branch_id = int(call.data.split(":")[1])
    b = await q.get_branch(branch_id)
    if b and b["lat"] is not None and b["lon"] is not None:
        await call.message.answer_location(latitude=b["lat"], longitude=b["lon"])
    await call.answer()


@router.callback_query(F.data.startswith("branch_select:"))
async def branch_select(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    branch_id = int(call.data.split(":")[1])
    b = await q.get_branch(branch_id)
    if not b:
        await call.answer("Filial topilmadi", show_alert=True)
        return
    await q.set_user_branch(call.from_user.id, branch_id)
    await call.answer("✅", show_alert=False)
    await call.message.answer(loc.t("branch_selected", lang, branch=b["name"]),
                              reply_markup=await main_kb(call.from_user.id))


@router.callback_query(F.data == "branches_back")
async def branches_back(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    branches = await q.list_branches()
    await call.message.answer(_branches_header(lang), reply_markup=kb.branches_list_kb(branches, lang))
    await call.answer()


# ---------------- Jamoaga qo'shilish (vakansiya boti) ----------------
@router.message(F.text.in_(loc.labels("join_team")))
async def join_team(message: Message, state: FSMContext):
    await state.clear()
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("join_team_text", lang), reply_markup=kb.vacancy_kb(lang))


# ---------------- Bog'lanish ----------------
@router.message(F.text.in_(loc.labels("contact")))
async def contact_section(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    text = await q.get_setting("contact_text")
    await state.set_state(ContactFlow.waiting_message)
    await message.answer(
        text + loc.t("contact_prompt", lang),
        reply_markup=kb.cancel_inline("contact_cancel", lang),
        disable_web_page_preview=True,
    )


@router.message(ContactFlow.waiting_message, ~F.text.in_(kb.ALL_MENU_BUTTONS),
                F.content_type.in_({"text", "photo", "document", "video"}))
async def contact_got_message(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    ct, fid, txt = extract_content(message)
    await state.update_data(c_type=ct, c_file=fid, c_text=txt, c_msgid=message.message_id)
    await state.set_state(ContactFlow.confirm)
    preview = txt if txt else f"({ct})"
    await message.answer(loc.t("contact_preview", lang, preview=preview),
                         reply_markup=kb.contact_confirm_kb(lang))


@router.message(ContactFlow.waiting_message, ~F.text.in_(kb.ALL_MENU_BUTTONS))
async def contact_bad_format(message: Message):
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("contact_bad", lang))


@router.callback_query(ContactFlow.confirm, F.data == "contact_send")
async def contact_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await q.get_lang(call.from_user.id)
    await q.set_user_username(call.from_user.id, call.from_user.username)
    data = await state.get_data()
    user = await q.get_user(call.from_user.id)
    if not user or not user["phone"]:
        await state.clear()
        await call.message.edit_text(loc.t("need_register", lang))
        await call.answer()
        return
    order_id = await q.create_order(call.from_user.id, user["branch_id"], data["c_type"])
    await q.add_message(order_id, "client", data["c_type"], data["c_text"],
                        data["c_file"], data["c_msgid"])
    await q.set_user_active_order(call.from_user.id, order_id)
    await state.clear()
    within, ws, we = await work_hours()
    suffix = "" if within else "\n\n" + loc.t("out_of_hours", lang, start=ws, end=we)
    await call.message.edit_text(loc.t("contact_sent", lang, id=order_id) + suffix)
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await deliver_order_to_operators(bot, order_id, data["c_type"], data["c_file"], data["c_text"])
    await call.answer()


@router.callback_query(F.data == "contact_cancel")
async def contact_cancel(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    await state.clear()
    try:
        await call.message.edit_text(loc.t("contact_canceled", lang))
    except Exception:
        pass
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await call.answer()
