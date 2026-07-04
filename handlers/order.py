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
    from handlers.menu import ensure_branch
    if await ensure_branch(message, message.from_user.id, lang):
        return   # filial tanlanmagan -> avval filialni tanlaydi
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
    await q.set_user_username(message.from_user.id, message.from_user.username)
    user = await q.get_user(message.from_user.id)
    items = data["items"]
    first_ct = items[0][0]
    order_id = await q.create_order(message.from_user.id, user["branch_id"], first_ct)
    for (ct, fid, cap, mid) in items:
        await q.add_message(order_id, "client", ct, cap, fid, mid)
    await q.set_user_active_order(message.from_user.id, order_id)
    await state.clear()
    await message.answer(
        loc.t(OK_KEYS.get(first_ct, "order_ok_photo"), lang, id=order_id) + await _hours_suffix(lang),
        reply_markup=await main_kb(message.from_user.id))
    await deliver_order_to_operators(bot, order_id, items[0][0], items[0][1], items[0][2])


@router.message(OrderFlow.waiting_content, F.text)
async def order_text(message: Message, state: FSMContext, bot: Bot):
    await _create_order(message, state, bot, "text")


@router.message(OrderFlow.waiting_content)
async def order_bad(message: Message):
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("order_bad_format", lang),
                         reply_markup=kb.cancel_inline("cancel_order", lang))


async def _hours_suffix(lang: str) -> str:
    within, ws, we = await work_hours()
    return "" if within else "\n\n" + loc.t("out_of_hours", lang, start=ws, end=we)


# Tungi avto-javob: har mijozga kuniga 1 marta
_night_notified: dict[int, str] = {}


async def _night_autoreply(message, lang):
    try:
        within, ws, we = await work_hours()
        if within:
            return
        from config import now_local
        today = now_local().strftime("%Y-%m-%d")
        if _night_notified.get(message.from_user.id) == today:
            return
        _night_notified[message.from_user.id] = today
        await message.answer("🌙 " + loc.t("out_of_hours", lang, start=ws, end=we))
    except Exception:
        pass


async def _pending_branch_blocked(message, lang) -> bool:
    """Majburiy filial tanlash: operator so'ragan bo'lsa, mijoz filial tanlamaguncha
    boshqa amal bajarilmaydi — har safar filial tanlash oynasi qayta chiqadi."""
    uid = message.from_user.id
    pend = await q.get_pending_branch(uid)
    if not pend:
        return False
    po = await q.get_order(pend)
    if not po or po["status"] not in ("new", "in_progress"):
        await q.clear_pending_branch(uid)   # murojaat yopilgan — gate ochiladi
        return False
    regions = await q.list_regions()
    if len(regions) > 1:
        markup = kb.regions_choose_kb(regions, lang, op_order=pend)
    else:
        markup = kb.op_ask_branch_kb(await q.list_branches(), pend, lang)
    await message.answer(loc.t("must_select_branch", lang), reply_markup=markup)
    return True


FLOOD_LIMIT = 5          # soatiga eng ko'p yangi murojaat
FLOOD_WINDOW_MIN = 60


async def _flood_blocked(message, lang) -> bool:
    """Anti-spam: bir mijoz qisqa vaqtda juda ko'p murojaat ochsa cheklaydi."""
    from datetime import timedelta
    from config import now_local
    since = (now_local() - timedelta(minutes=FLOOD_WINDOW_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    cnt = await q.recent_orders_count(message.from_user.id, since)
    if cnt >= FLOOD_LIMIT:
        await message.answer(
            "⚠️ Qisqa vaqtda juda ko'p murojaat ochdingiz.\n"
            "Ochiq murojaatingizga yozishingiz mumkin — yangi murojaatni birozdan keyin oching."
            if lang != "ru" else
            "⚠️ Слишком много обращений за короткое время.\n"
            "Вы можете писать в открытое обращение — новое откройте чуть позже.")
        return True
    return False


@router.callback_query(F.data.startswith("resume:"))
async def client_resume(call: CallbackQuery, bot: Bot):
    """Mijoz avto-yakunlangan murojaatni «Qayta boshlash» tugmasi orqali tiklaydi.
    Murojaat oldingi operatorga qayta biriktiriladi, operator va adminlarga xabar boradi."""
    import botreg
    from config import ADMIN_IDS
    order_id = int(call.data.split(":")[1])
    lang = await q.get_lang(call.from_user.id)
    order = await q.get_order(order_id)
    if not order or order["user_id"] != call.from_user.id:
        await call.answer("Murojaat topilmadi", show_alert=True)
        return
    if order["status"] in ("new", "in_progress"):
        await call.answer("Suhbat allaqachon faol — savolingizni yozing.", show_alert=True)
        return
    # Boshqa ochiq murojaati bo'lsa — konflikt bo'lmasin
    user = await q.get_user(call.from_user.id)
    if user and user["active_order_id"] and user["active_order_id"] != order_id:
        act = await q.get_order(user["active_order_id"])
        if act and act["status"] in ("new", "in_progress"):
            await call.answer("Sizda boshqa ochiq murojaat bor.", show_alert=True)
            return

    prev_op = order["operator_id"]
    if prev_op:
        await q.reopen_order(order_id, prev_op)
        await q.set_operator_availability(prev_op, "busy")
        await q.set_operator_active_order(prev_op, order_id)
    else:
        # Operator bo'lmasa — yangi murojaat sifatida kanalga qaytadi
        await q.set_order_status(order_id, "new", f"client:{call.from_user.id}:resume")
    await q.set_user_active_order(call.from_user.id, order_id)
    await q.add_message(order_id, "client", "text", "🔄 Mijoz suhbatni qayta boshladi", None, None)

    try:
        await call.message.edit_text(loc.t("resume_done", lang, id=order_id))
    except Exception:
        try:
            await call.message.answer(loc.t("resume_done", lang, id=order_id))
        except Exception:
            pass

    # Oldingi operatorga o'z boti orqali xabar + CRM ochish tugmasi
    if prev_op:
        op = await q.get_operator(prev_op)
        if op and op["telegram_id"]:
            ob = (botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else bot) or bot
            try:
                await ob.send_message(
                    op["telegram_id"],
                    f"🔄 Mijoz <b>#{order_id}</b> murojaatini qayta tikladi.\n"
                    f"CRM'dan chatni ochib davom eting.",
                    reply_markup=kb.open_crm_kb("operator"))
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
    # Adminlarga xabar (asosiy bot)
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid, f"🔄 Murojaat <b>#{order_id}</b> mijoz tomonidan qayta tiklandi. "
                     f"Chatni ochib ko'ring.",
                reply_markup=kb.open_crm_kb("admin"))
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    await call.answer("✅")


async def _create_order(message, state, bot, content_type):
    lang = await q.get_lang(message.from_user.id)
    await q.set_user_username(message.from_user.id, message.from_user.username)
    user = await q.get_user(message.from_user.id)
    if user and user["status"] == "blocked":
        await message.answer("⛔ Siz botdan foydalanishdan cheklangansiz.")
        return
    if await _pending_branch_blocked(message, lang):
        return
    if await _flood_blocked(message, lang):
        return
    order_id = await q.create_order(message.from_user.id, user["branch_id"], content_type)
    await save_message_from_message(order_id, "client", message)
    await q.set_user_active_order(message.from_user.id, order_id)
    await state.clear()
    await message.answer(loc.t(OK_KEYS[content_type], lang, id=order_id) + await _hours_suffix(lang),
                         reply_markup=await main_kb(message.from_user.id))
    await send_first_content_to_operators(bot, order_id, message)


# -------- Proxy-chat: ochiq murojaati bor mijozning erkin xabari operatorga ketadi --------
@router.message(F.chat.type == "private",
                F.content_type.in_({"text", "photo", "document", "video", "voice", "location"}))
async def client_proxy(message: Message, state: FSMContext, bot: Bot):
    # FSM holatda bo'lsa, bu handlerga tushmaydi (yuqoridagilar ushlaydi)
    user = await q.get_user(message.from_user.id)
    if user and user["status"] == "blocked":
        await message.answer("⛔ Siz botdan foydalanishdan cheklangansiz.")
        return
    if not user:
        await message.answer("/start")
        return
    lang = user["lang"] or "uz"
    # Majburiy filial tanlash — operator so'ragan bo'lsa, tanlamaguncha bloklanadi
    if await _pending_branch_blocked(message, lang):
        return
    active = user["active_order_id"]
    if active:
        order = await q.get_order(active)
        if order and order["status"] in ("new", "in_progress"):
            await save_message_from_message(active, "client", message)
            await forward_client_to_operator(bot, order, message)
            await message.answer(loc.t("proxy_sent", lang))
            # Ish vaqtidan tashqarida — kuniga bir marta avto-javob
            await _night_autoreply(message, lang)
            return
    # ochiq murojaat yo'q
    await message.answer(loc.t("use_menu", lang), reply_markup=await main_kb(message.from_user.id))
