"""Asosiy menyu bo'limlari: FAQ, Filiallar, Bog'lanish."""
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import keyboards as kb
import locales as loc
from states import ContactFlow
from database import queries as q
from utils import main_kb, extract_content, deliver_order_to_operators

router = Router()


def _branches_header(lang):
    return loc.t("branches_header", lang)


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
    await message.answer(_branches_header(lang), reply_markup=kb.branches_list_kb(branches))


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


@router.callback_query(F.data == "branches_back")
async def branches_back(call: CallbackQuery):
    lang = await q.get_lang(call.from_user.id)
    branches = await q.list_branches()
    await call.message.answer(_branches_header(lang), reply_markup=kb.branches_list_kb(branches))
    await call.answer()


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
    data = await state.get_data()
    user = await q.get_user(call.from_user.id)
    if not user or not user["branch_id"]:
        await state.clear()
        await call.message.edit_text(loc.t("need_register", lang))
        await call.answer()
        return
    order_id = await q.create_order(call.from_user.id, user["branch_id"], data["c_type"])
    await q.add_message(order_id, "client", data["c_type"], data["c_text"],
                        data["c_file"], data["c_msgid"])
    await q.set_user_active_order(call.from_user.id, order_id)
    await state.clear()
    await call.message.edit_text(loc.t("contact_sent", lang, id=order_id))
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
