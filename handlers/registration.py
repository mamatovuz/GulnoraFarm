"""Ro'yxatdan o'tish: /start -> til -> ism -> telefon -> obuna -> filial -> asosiy menyu."""
import re
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import keyboards as kb
import locales as loc
from states import Reg, OperatorFlow
from database import queries as q
from utils import check_subscription, main_kb

router = Router()


async def ask_branch(target: Message, state: FSMContext, lang: str, uid: int):
    branches = await q.list_branches()
    if not branches:
        await target.answer(loc.t("no_branches", lang), reply_markup=await main_kb(uid))
        await state.clear()
        return
    await state.set_state(Reg.branch)
    await target.answer(loc.t("ask_branch", lang), reply_markup=kb.branches_choose_kb(branches, lang=lang))


async def proceed_after_phone(message: Message, state: FSMContext, bot: Bot, lang: str):
    """Telefon olingach: obunani tekshirib, kerak bo'lsa obuna so'raydi, aks holda filialga o'tadi."""
    not_subbed = await check_subscription(bot, message.from_user.id)
    channels = await q.list_channels()
    if channels and not_subbed:
        await state.set_state(Reg.channel)
        await message.answer(loc.t("ask_subscribe", lang), reply_markup=kb.subscribe_kb(not_subbed, lang))
    else:
        await ask_branch(message, state, lang, message.from_user.id)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot, command: CommandObject):
    await state.clear()

    # Operatorlar guruhidagi "Qabul qilish" havolasi: /start accept_<id>
    arg = command.args if command else None
    if arg and arg.startswith("accept_"):
        from handlers.operator import do_accept, remember_pending_accept
        try:
            order_id = int(arg.split("_", 1)[1])
        except (ValueError, IndexError):
            await message.answer("Noto'g'ri havola.")
            return
        op = await q.get_operator_by_tg(message.from_user.id)
        if not op or op["status"] != "active":
            # Hali login qilmagan — eslab qolamiz, login qilgach avtomatik ochiladi
            remember_pending_accept(message.from_user.id, order_id)
            await message.answer(
                "Bu murojaatni qabul qilish uchun avval operator kabinetiga kiring 👇\n"
                "Login qilganingizdan so'ng murojaat avtomatik ochiladi.")
            await state.set_state(OperatorFlow.login)
            await message.answer("👨‍⚕️ <b>Operator kabineti</b>\n\n🔑 Login:", reply_markup=kb.REMOVE)
            return
        ok, err = await do_accept(bot, op, order_id, message.from_user.id)
        if not ok:
            await message.answer(f"⚠️ {err}")
        return

    user = await q.get_user(message.from_user.id)
    if user and user["full_name"] and user["phone"]:
        lang = user["lang"] or "uz"
        # Majburiy obunani HAR /start da tekshiramiz
        channels = await q.list_channels()
        if channels:
            not_subbed = await check_subscription(bot, message.from_user.id)
            if not_subbed:
                await state.set_state(Reg.channel)
                await message.answer(loc.t("ask_subscribe", lang),
                                     reply_markup=kb.subscribe_kb(not_subbed, lang))
                return
        await message.answer(loc.t("welcome_back", lang, name=user["full_name"].split()[0]),
                             reply_markup=await main_kb(message.from_user.id))
        return
    # Avval tilni so'raymiz
    await message.answer(loc.CHOOSE_LANG, reply_markup=kb.lang_kb())


@router.message(Command("til", "lang", "language"))
async def cmd_lang(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(loc.CHOOSE_LANG, reply_markup=kb.lang_kb())


@router.callback_query(F.data.startswith("setlang:"))
async def set_lang(call: CallbackQuery, state: FSMContext):
    lang = call.data.split(":")[1]
    await q.set_user_lang(call.from_user.id, lang)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    user = await q.get_user(call.from_user.id)
    if user and user["full_name"] and user["phone"]:
        # Allaqachon ro'yxatdan o'tgan — faqat til o'zgardi
        await call.message.answer(loc.t("welcome_back", lang, name=user["full_name"].split()[0]),
                                  reply_markup=await main_kb(call.from_user.id))
    else:
        await call.message.answer(loc.t("welcome_new", lang), reply_markup=kb.register_kb(lang))


@router.message(F.text.in_(loc.labels("register")))
async def start_register(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    await state.set_state(Reg.full_name)
    await message.answer(loc.t("ask_name", lang), reply_markup=kb.REMOVE)


@router.message(Reg.full_name)
async def reg_name(message: Message, state: FSMContext):
    lang = await q.get_lang(message.from_user.id)
    text = (message.text or "").strip()
    if not text or not re.fullmatch(r"[A-Za-zÀ-ÿА-Яа-яЎўҚқҒғҲҳ'ʼ`\- ]{3,60}", text) or text.isdigit():
        await message.answer(loc.t("bad_name", lang))
        return
    await state.update_data(full_name=text)
    await state.set_state(Reg.phone)
    await message.answer(loc.t("ask_phone", lang, name=text.split()[0]), reply_markup=kb.phone_kb(lang))


def normalize_phone(raw: str) -> str | None:
    """Telefon raqamni tozalab, normallashtiradi. Noto'g'ri bo'lsa None qaytaradi."""
    digits = re.sub(r"[ \-()]", "", raw.strip())
    if not re.fullmatch(r"\+?\d{7,15}", digits):
        return None
    if digits.startswith("+"):
        return digits
    if digits.startswith("998"):
        return "+" + digits
    if len(digits) == 9:                 # mahalliy mobil raqam: 901234567
        return "+998" + digits
    return "+" + digits


async def _save_phone(message: Message, state: FSMContext, bot: Bot, phone: str, lang: str):
    data = await state.get_data()
    name = data["full_name"]
    await q.create_user(message.from_user.id, name, phone)
    await message.answer(loc.t("phone_ok", lang, name=name, phone=phone), reply_markup=kb.REMOVE)
    await proceed_after_phone(message, state, bot, lang)


@router.message(Reg.phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext, bot: Bot):
    lang = await q.get_lang(message.from_user.id)
    phone = normalize_phone(message.contact.phone_number) or message.contact.phone_number
    await _save_phone(message, state, bot, phone, lang)


@router.message(Reg.phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext, bot: Bot):
    lang = await q.get_lang(message.from_user.id)
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer(loc.t("bad_phone", lang), reply_markup=kb.phone_kb(lang))
        return
    await _save_phone(message, state, bot, phone, lang)


@router.message(Reg.phone)
async def reg_phone_bad(message: Message):
    lang = await q.get_lang(message.from_user.id)
    await message.answer(loc.t("bad_phone", lang), reply_markup=kb.phone_kb(lang))


@router.callback_query(Reg.channel, F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await q.get_lang(call.from_user.id)
    not_subbed = await check_subscription(bot, call.from_user.id)
    if not_subbed:
        names = "\n".join(f"📢 {c['title']}" for c in not_subbed)
        await call.message.answer(loc.t("not_subscribed", lang, channels=names),
                                  reply_markup=kb.subscribe_kb(not_subbed, lang))
        await call.answer("❌")
        return
    await call.answer("✅")
    user = await q.get_user(call.from_user.id)
    if user and user["full_name"] and user["phone"]:
        # Qaytgan (ro'yxatdan o'tgan) foydalanuvchi — to'g'ri menyuga
        await state.clear()
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await call.message.answer(loc.t("welcome_back", lang, name=user["full_name"].split()[0]),
                                  reply_markup=await main_kb(call.from_user.id))
    else:
        await ask_branch(call.message, state, lang, call.from_user.id)


@router.callback_query(Reg.branch, F.data.startswith("pickbranch:"))
async def pick_branch_cb(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    branch_id = int(call.data.split(":")[1])
    branch = await q.get_branch(branch_id)
    if not branch:
        await call.answer("Filial topilmadi", show_alert=True)
        return
    await q.set_user_branch(call.from_user.id, branch_id)
    await call.message.edit_text(loc.t("branch_selected", lang, branch=branch["name"]))
    await state.clear()
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await call.answer()


@router.callback_query(Reg.branch, F.data == "branch_skip")
async def skip_branch_cb(call: CallbackQuery, state: FSMContext):
    lang = await q.get_lang(call.from_user.id)
    await state.clear()
    try:
        await call.message.edit_text(loc.t("branch_skipped", lang))
    except Exception:
        pass
    await call.message.answer(loc.t("main_menu", lang), reply_markup=await main_kb(call.from_user.id))
    await call.answer()
