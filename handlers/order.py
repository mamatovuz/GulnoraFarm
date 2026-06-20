"""Retsept/murojaat yuborish va mijoz<->operator proxy-chat."""
import asyncio
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import locales as loc
from config import OPERATORS_GROUP_ID
from states import OrderFlow
from database import queries as q
from utils import (
    send_first_content_to_operators, forward_client_to_operator, save_message_from_message,
    main_kb, extract_content, deliver_order_to_operators, work_hours,
)

router = Router()

# Albom (bir nechta rasm/hujjat birga) yig'gich
_albums: dict[str, dict] = {}

OK_KEYS = {"photo": "order_ok_photo", "document": "order_ok_document",
           "video": "order_ok_video", "text": "order_ok_text"}


@router.message(F.chat.type == "private", F.text.in_(loc.labels("order")))
async def ask_order(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    user = await q.get_user(message.from_user.id)
    if not user or not user["phone"]:
        await message.answer(loc.t("need_register", lang))
        return
    await state.set_state(OrderFlow.waiting_content)
    await message.answer(loc.t("order_ask", lang), reply_markup=kb.cancel_inline("cancel_order", lang))


async def _notify_operators_rating(bot, order_id, rating, feedback):
    """Operator va guruhga baho + izohni yuboradi."""
    order = await q.get_order(order_id)
    if not order:
        return
    text = f"⭐ Murojaat #{order_id} baholandi: {'⭐' * int(rating or 0)} ({rating}/5)"
    if feedback:
        text += f"\n💬 Mijoz izohi: {feedback}"
    op = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    targets = []
    if op and op["telegram_id"]:
        targets.append(op["telegram_id"])
    if OPERATORS_GROUP_ID:
        targets.append(OPERATORS_GROUP_ID)
    for chat_id in targets:
        try:
            await bot.send_message(chat_id, text)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


@router.callback_query(F.data.startswith("rate:"))
async def rate_order(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    _, oid, stars = call.data.split(":")
    n = int(stars)
    await q.set_order_rating(int(oid), n)
    await state.set_state(OrderFlow.feedback)
    await state.update_data(fb_order=int(oid), fb_rating=n)
    try:
        await call.message.edit_text(loc.t("rate_reason", lang, n=n, stars="⭐" * n),
                                     reply_markup=kb.feedback_skip_kb(int(oid), lang))
    except Exception:
        pass
    await call.answer("✅")


@router.message(OrderFlow.feedback, ~F.text.in_(kb.ALL_MENU_BUTTONS), F.text)
async def feedback_text(message: Message, state: FSMContext, bot: Bot):
    lang = await q.get_lang(message.from_user.id)
    data = await state.get_data()
    oid, rating = data.get("fb_order"), data.get("fb_rating")
    await state.clear()
    if oid:
        await q.set_order_feedback(oid, message.text)
    await message.answer(loc.t("feedback_thanks", lang), reply_markup=await main_kb(message.from_user.id))
    if oid:
        await _notify_operators_rating(bot, oid, rating, message.text)


@router.callback_query(F.data.startswith("fb_skip:"))
async def fb_skip(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    data = await state.get_data()
    oid = data.get("fb_order") or int(call.data.split(":")[1])
    rating = data.get("fb_rating")
    await state.clear()
    try:
        await call.message.edit_text(loc.t("feedback_thanks", lang))
    except Exception:
        pass
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await _notify_operators_rating(call.bot, oid, rating, None)
    await call.answer()


@router.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    await state.clear()
    await call.message.edit_text(loc.t("cancel_done", lang))
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await call.answer()


@router.message(OrderFlow.waiting_content, F.photo)
async def order_photo(message: Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        await _collect_album(message, state, bot)
        return
    await _create_order(message, state, bot, "photo")


@router.message(OrderFlow.waiting_content, F.document)
async def order_document(message: Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        await _collect_album(message, state, bot)
        return
    await _create_order(message, state, bot, "document")


@router.message(OrderFlow.waiting_content, F.video)
async def order_video(message: Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        await _collect_album(message, state, bot)
        return
    await _create_order(message, state, bot, "video")


async def _collect_album(message: Message, state: FSMContext, bot: Bot):
    """Albomdagi har bir element yig'iladi; 1.5s jimlikdan so'ng bitta murojaat yaratiladi."""
    gid = message.media_group_id
    ct, fid, caption = extract_content(message)
    data = _albums.setdefault(gid, {"items": [], "task": None})
    data["items"].append((ct, fid, caption, message.message_id))
    if data["task"]:
        data["task"].cancel()
    data["task"] = asyncio.create_task(_finalize_album(gid, message, state, bot))


async def _finalize_album(gid, message: Message, state: FSMContext, bot: Bot):
    try:
        await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        return
    data = _albums.pop(gid, None)
    if not data or not data["items"]:
        return
    lang = await q.get_lang(message.from_user.id)
    user = await q.get_user(message.from_user.id)
    items = data["items"]
    first_ct = items[0][0]
    order_id = await q.create_order(message.from_user.id, user["branch_id"], first_ct)
    for (ct, fid, cap, mid) in items:
        await q.add_message(order_id, "client", ct, cap, fid, mid)
    await q.set_user_active_order(message.from_user.id, order_id)
    await state.clear()
    await message.answer(loc.t(OK_KEYS.get(first_ct, "order_ok_photo"), lang, id=order_id),
                         reply_markup=await main_kb(message.from_user.id))
    await deliver_order_to_operators(bot, order_id, items[0][0], items[0][1], items[0][2])
    await _out_of_hours_note(message, lang)


@router.message(OrderFlow.waiting_content, F.text)
async def order_text(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "text")


@router.message(OrderFlow.waiting_content)
async def order_bad(message: Message):
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("order_bad_format", lang),
                         reply_markup=kb.cancel_inline("cancel_order", lang))


async def _out_of_hours_note(message: Message, lang: str):
    within, ws, we = await work_hours()
    if not within:
        await message.answer(loc.t("out_of_hours", lang, start=ws, end=we))


async def _create_order(message, state, bot, content_type):
    lang = await q.get_lang(message.from_user.id)
    user = await q.get_user(message.from_user.id)
    order_id = await q.create_order(message.from_user.id, user["branch_id"], content_type)
    await save_message_from_message(order_id, "client", message)
    await q.set_user_active_order(message.from_user.id, order_id)
    await state.clear()
    await message.answer(loc.t(OK_KEYS[content_type], lang, id=order_id),
                         reply_markup=await main_kb(message.from_user.id))
    await send_first_content_to_operators(bot, order_id, message)
    await _out_of_hours_note(message, lang)


# -------- Proxy-chat: ochiq murojaati bor mijozning erkin xabari operatorga ketadi --------
@router.message(F.chat.type == "private", F.content_type.in_({"text", "photo", "document", "video"}))
async def client_proxy(message: Message, state: FSMContext, bot: Bot):
    # FSM holatda bo'lsa, bu handlerga tushmaydi (yuqoridagilar ushlaydi)
    user = await q.get_user(message.from_user.id)
    if not user:
        await message.answer("/start")
        return
    lang = user["lang"] or "uz"
    active = user["active_order_id"]
    if active:
        order = await q.get_order(active)
        if order and order["status"] in ("new", "in_progress"):
            await save_message_from_message(active, "client", message)
            await forward_client_to_operator(bot, order, message)
            await message.answer(loc.t("proxy_sent", lang))
            return
    # ochiq murojaat yo'q
    await message.answer(loc.t("use_menu", lang), reply_markup=await main_kb(message.from_user.id))
