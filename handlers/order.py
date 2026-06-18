"""Retsept/murojaat yuborish va mijoz<->operator proxy-chat."""
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import keyboards as kb
import locales as loc
from states import OrderFlow
from database import queries as q
from utils import (
    send_first_content_to_operators, forward_client_to_operator, save_message_from_message,
    main_kb,
)

router = Router()

OK_KEYS = {"photo": "order_ok_photo", "document": "order_ok_document",
           "video": "order_ok_video", "text": "order_ok_text"}


@router.message(F.chat.type == "private", F.text.in_(loc.labels("order")))
async def ask_order(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    user = await q.get_user(message.from_user.id)
    if not user or not user["branch_id"]:
        await message.answer(loc.t("need_register", lang))
        return
    await state.set_state(OrderFlow.waiting_content)
    await message.answer(loc.t("order_ask", lang), reply_markup=kb.cancel_inline("cancel_order", lang))


@router.callback_query(F.data.startswith("rate:"))
async def rate_order(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    _, oid, stars = call.data.split(":")
    await q.set_order_rating(int(oid), int(stars))
    try:
        await call.message.edit_text(loc.t("rate_thanks", lang, stars="⭐" * int(stars)))
    except Exception:
        pass
    await call.answer("✅")


@router.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    await state.clear()
    await call.message.edit_text(loc.t("cancel_done", lang))
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await call.answer()


@router.message(OrderFlow.waiting_content, F.photo)
async def order_photo(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "photo")


@router.message(OrderFlow.waiting_content, F.document)
async def order_document(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "document")


@router.message(OrderFlow.waiting_content, F.video)
async def order_video(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "video")


@router.message(OrderFlow.waiting_content, F.text)
async def order_text(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "text")


@router.message(OrderFlow.waiting_content)
async def order_bad(message: Message):
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("order_bad_format", lang),
                         reply_markup=kb.cancel_inline("cancel_order", lang))


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
