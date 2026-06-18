"""Admin panel: statistika, broadcast, kanal/FAQ/filial/operator boshqaruvi, tarix."""
import os
import secrets
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import keyboards as kb
import texts as t
import locales as loc
from states import AdminFlow
from database import queries as q
from utils import is_admin, STATUS_LABEL, order_card_text

router = Router()


def admin_only(func):
    return func


# ---------------- Kirish ----------------
@router.message(F.text.in_(loc.labels("admin")))
async def admin_button(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return  # admin bo'lmaganlar uchun bu tugma yo'q — javob bermaymiz
    await state.clear()
    await message.answer(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())


@router.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext):
    # Zaxira yo'l (asosiy kirish — "👨‍💻 Admin panel" tugmasi orqali)
    if not is_admin(message.from_user.id):
        await message.answer(t.NO_ADMIN)
        return
    await state.clear()
    await message.answer(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def admin_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer(t.NO_ADMIN, show_alert=True)
        return
    await state.clear()
    try:
        await call.message.edit_text(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())
    except TelegramBadRequest:
        await call.message.answer(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())
    await call.answer()


# ---------------- Statistika ----------------
@router.callback_query(F.data == "adm:stats")
async def admin_stats(call: CallbackQuery):
    s = await q.general_stats()
    branch_lines = "\n".join(f"— {b['name']}: {b['cnt']} murojaat" for b in s["branches"]) or "—"
    text = (
        "📊 <b>Umumiy statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {s['users_total']}\n"
        f"🆕 Bugungi yangi: {s['users_today']}\n"
        f"📅 Haftalik yangi: {s['users_week']}\n"
        f"📆 Oylik yangi: {s['users_month']}\n\n"
        f"💊 Jami murojaatlar: {s['orders_total']}\n"
        f"🟡 Yangi: {s['orders_new']}   🔵 Jarayonda: {s['orders_progress']}\n"
        f"🟢 Yakunlangan: {s['orders_done']}   🔴 Bekor: {s['orders_canceled']}\n\n"
        f"⭐ O'rtacha baho: {s['avg_rating']} ({s['rated_count']} ta baho)\n\n"
        f"🏥 <b>Filiallar kesimida:</b>\n{branch_lines}"
    )
    await call.message.edit_text(text, reply_markup=kb.stats_kb())
    await call.answer()


@router.callback_query(F.data == "adm:excel")
async def admin_excel(call: CallbackQuery):
    import openpyxl
    rows = await q.all_orders_full()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Murojaatlar"
    headers = ["ID", "Mijoz", "Telefon", "Filial", "Operator", "Holat",
               "Tur", "Hisob", "Boshlangan", "Yakunlangan"]
    ws.append(headers)
    for r in rows:
        ws.append([
            r["id"], r["full_name"], r["phone"], r["branch"], r["operator"],
            STATUS_LABEL.get(r["status"], r["status"]), r["content_type"],
            r["bill"], r["created_at"], r["closed_at"],
        ])
    os.makedirs("reports", exist_ok=True)
    path = os.path.join("reports", "hisobot.xlsx")
    wb.save(path)
    await call.message.answer_document(FSInputFile(path), caption="📥 Murojaatlar hisoboti")
    await call.answer()


# ---------------- Broadcast ----------------
@router.callback_query(F.data == "adm:bc")
async def bc_start(call: CallbackQuery):
    await call.message.edit_text(
        "📨 <b>Ommaviy xabar</b>\n\nYubormoqchi bo'lgan xabar turini tanlang:",
        reply_markup=kb.bc_type_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("bc_type:"))
async def bc_type(call: CallbackQuery, state: FSMContext):
    bc_type = call.data.split(":")[1]
    await state.set_state(AdminFlow.bc_content)
    await state.update_data(bc_type=bc_type)
    label = {"text": "matnni", "photo": "rasmni", "video": "videoni", "document": "hujjatni"}[bc_type]
    await call.message.edit_text(f"Yubormoqchi bo'lgan {label} yuboring:")
    await call.answer()


@router.message(AdminFlow.bc_content)
async def bc_content(message: Message, state: FSMContext):
    data = await state.get_data()
    bc_type = data["bc_type"]
    file_id, caption, text = None, None, None
    if bc_type == "text":
        if not message.text:
            await message.answer("Iltimos, matn yuboring.")
            return
        text = message.text
    elif bc_type == "photo" and message.photo:
        file_id, caption = message.photo[-1].file_id, message.caption or ""
    elif bc_type == "video" and message.video:
        file_id, caption = message.video.file_id, message.caption or ""
    elif bc_type == "document" and message.document:
        file_id, caption = message.document.file_id, message.caption or ""
    else:
        await message.answer("Tanlangan turga mos kontent yuboring.")
        return
    await state.update_data(bc_file_id=file_id, bc_caption=caption, bc_text=text)
    await state.set_state(AdminFlow.bc_target_branch)
    await message.answer("✅ Xabar tayyor. Endi kimga yuborishni tanlang:",
                         reply_markup=kb.bc_target_kb())


@router.callback_query(AdminFlow.bc_target_branch, F.data.startswith("bc_t:"))
async def bc_target(call: CallbackQuery, state: FSMContext):
    target = call.data.split(":")[1]
    if target == "branch":
        branches = await q.list_branches()
        await call.message.edit_text("Qaysi filial?", reply_markup=kb.branch_pick_kb(branches, "bc_br"))
        await call.answer()
        return
    await state.update_data(bc_target=target, bc_branch=None)
    await _bc_confirm(call.message, state)
    await call.answer()


@router.callback_query(AdminFlow.bc_target_branch, F.data.startswith("bc_br:"))
async def bc_branch(call: CallbackQuery, state: FSMContext):
    branch_id = int(call.data.split(":")[1])
    await state.update_data(bc_target="branch", bc_branch=branch_id)
    await _bc_confirm(call.message, state)
    await call.answer()


async def _bc_targets(data):
    if data["bc_target"] == "all":
        return await q.all_users()
    if data["bc_target"] == "active":
        return await q.all_users(only_active=True)
    return await q.all_users(branch_id=data["bc_branch"])


async def _bc_confirm(message, state):
    data = await state.get_data()
    users = await _bc_targets(data)
    label = {"all": "Barchaga", "active": "Faol foydalanuvchilarga", "branch": "Tanlangan filialga"}[
        data["bc_target"]]
    preview = data.get("bc_text") or data.get("bc_caption") or "(media)"
    await message.answer(
        f"⚠️ <b>Tasdiqlang</b>\n\nKimga: {label}\nQabul qiluvchilar soni: {len(users)}\n\n"
        f"Xabar:\n{preview}\n\nYuborilsinmi?",
        reply_markup=kb.confirm_kb("bc_send"),
    )


@router.callback_query(F.data == "bc_send")
async def bc_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    users = await _bc_targets(data)
    await call.message.edit_text("📤 Yuborilmoqda...")
    sent, failed = 0, 0
    for u in users:
        try:
            if data["bc_type"] == "text":
                await bot.send_message(u["telegram_id"], data["bc_text"])
            elif data["bc_type"] == "photo":
                await bot.send_photo(u["telegram_id"], data["bc_file_id"], caption=data["bc_caption"])
            elif data["bc_type"] == "video":
                await bot.send_video(u["telegram_id"], data["bc_file_id"], caption=data["bc_caption"])
            elif data["bc_type"] == "document":
                await bot.send_document(u["telegram_id"], data["bc_file_id"], caption=data["bc_caption"])
            sent += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            failed += 1
    await state.clear()
    await call.message.answer(
        f"✅ Xabar yuborildi!\n\n📤 Yuborildi: {sent}\n❌ Yetkazilmadi: {failed}",
        reply_markup=kb.admin_back_kb(),
    )
    await call.answer()


# ---------------- Kanal boshqaruvi ----------------
@router.callback_query(F.data == "adm:ch")
async def ch_menu(call: CallbackQuery):
    channels = await q.list_channels()
    if channels:
        lst = "\n".join(f"{i+1}. {c['chat_id']}" for i, c in enumerate(channels))
    else:
        lst = "(hozircha kanal yo'q)"
    await call.message.edit_text(
        f"📢 <b>Majburiy obuna kanallari</b>\n\n{lst}\n\nAmalni tanlang:",
        reply_markup=kb.channels_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "ch_add")
async def ch_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.ch_add)
    await call.message.edit_text(
        "Kanal username yoki ID raqamini yuboring.\n\nMasalan: <code>@gulnora_farm</code>\n\n"
        "⚠️ Bot ushbu kanalda admin bo'lishi shart!"
    )
    await call.answer()


@router.message(AdminFlow.ch_add)
async def ch_add_save(message: Message, state: FSMContext, bot: Bot):
    raw = message.text.strip()
    # Kanalni tekshiramiz: bot kira oladimi?
    try:
        chat = await bot.get_chat(raw)
    except (TelegramBadRequest, TelegramForbiddenError):
        await message.answer(
            "⚠️ Kanal topilmadi yoki bot unga kira olmadi.\n\n"
            "1) Avval botni kanalga <b>ADMIN</b> qiling.\n"
            "2) Keyin kanal <code>@username</code> yoki ID (-100...) ni yuboring.",
        )
        return
    # Bot kanalda admin ekanini tekshiramiz
    try:
        me = await bot.get_me()
        mem = await bot.get_chat_member(chat.id, me.id)
        bot_is_admin = mem.status in ("administrator", "creator")
    except (TelegramBadRequest, TelegramForbiddenError):
        bot_is_admin = False

    # @username bo'lsa o'shani saqlaymiz (havola tugmasi ishlashi uchun), aks holda ID
    stored = f"@{chat.username}" if chat.username else str(chat.id)
    await q.add_channel(stored, chat.title or stored)
    await state.clear()

    warn = ("" if bot_is_admin else
            "\n\n⚠️ <b>DIQQAT:</b> bot bu kanalda ADMIN emas — obunani tekshira olmaydi! "
            "Botni kanalga admin qiling.")
    await message.answer(
        f"✅ Kanal qo'shildi: <b>{chat.title}</b> ({stored}){warn}",
        reply_markup=kb.admin_back_kb("adm:ch"),
    )


@router.callback_query(F.data == "ch_del")
async def ch_del_list(call: CallbackQuery):
    channels = await q.list_channels()
    if not channels:
        await call.answer("Kanal yo'q", show_alert=True)
        return
    await call.message.edit_text("O'chiriladigan kanalni tanlang:",
                                 reply_markup=kb.list_delete_kb(channels, "chdel", "adm:ch"))
    await call.answer()


@router.callback_query(F.data.startswith("chdel:"))
async def ch_del(call: CallbackQuery):
    cid = int(call.data.split(":")[1])
    await q.delete_channel(cid)
    await call.message.edit_text("🗑 Kanal o'chirildi.", reply_markup=kb.admin_back_kb("adm:ch"))
    await call.answer()


# ---------------- FAQ boshqaruvi ----------------
@router.callback_query(F.data == "adm:faq")
async def faq_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    faqs = await q.list_faqs()
    enabled = (await q.get_setting("faq_enabled", "1")) != "0"
    status = "🟢 Yoqilgan (menyuda ko'rinadi)" if enabled else "🔴 O'chirilgan (menyuda yo'q)"
    lst = "\n".join(f"{i+1}. {f['title']}" for i, f in enumerate(faqs)) or "(yo'q)"
    await call.message.edit_text(
        f"❓ <b>FAQ boshqaruvi</b>\n\nHolat: {status}\n\n{lst}\n\nAmalni tanlang:",
        reply_markup=kb.faq_admin_kb(enabled),
    )
    await call.answer()


@router.callback_query(F.data == "faq_toggle")
async def faq_toggle(call: CallbackQuery, state: FSMContext):
    enabled = (await q.get_setting("faq_enabled", "1")) != "0"
    await q.set_setting("faq_enabled", "0" if enabled else "1")
    if enabled:
        await call.answer("🔕 FAQ bo'limi o'chirildi — menyudan yashirildi", show_alert=True)
    else:
        await call.answer("🔔 FAQ bo'limi yoqildi — menyuda ko'rinadi", show_alert=True)
    await faq_admin(call, state)


@router.callback_query(F.data == "faq_add")
async def faq_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.faq_title)
    await call.message.edit_text("Yangi savol sarlavhasini kiriting:")
    await call.answer()


@router.message(AdminFlow.faq_title)
async def faq_title(message: Message, state: FSMContext):
    await state.update_data(faq_title=message.text)
    await state.set_state(AdminFlow.faq_answer)
    await message.answer("Endi shu savolga javob matnini kiriting:")


@router.message(AdminFlow.faq_answer)
async def faq_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    await q.add_faq(data["faq_title"], message.text)
    await state.clear()
    await message.answer(f"✅ Yangi FAQ band qo'shildi:\n\n❓ {data['faq_title']}",
                         reply_markup=kb.admin_back_kb("adm:faq"))


@router.callback_query(F.data == "faq_edit_list")
async def faq_edit_list(call: CallbackQuery):
    faqs = await q.list_faqs()
    if not faqs:
        await call.answer("FAQ yo'q", show_alert=True)
        return
    await call.message.edit_text("Tahrirlanadigan savolni tanlang:",
                                 reply_markup=kb.faq_pick_kb(faqs, "faqedit"))
    await call.answer()


@router.callback_query(F.data.startswith("faqedit:"))
async def faq_edit_pick(call: CallbackQuery, state: FSMContext):
    faq_id = int(call.data.split(":")[1])
    await state.set_state(AdminFlow.faq_edit_title)
    await state.update_data(faq_id=faq_id)
    await call.message.edit_text("Yangi sarlavhani kiriting:")
    await call.answer()


@router.message(AdminFlow.faq_edit_title)
async def faq_edit_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text)
    await state.set_state(AdminFlow.faq_edit_answer)
    await message.answer("Endi yangi javob matnini kiriting:")


@router.message(AdminFlow.faq_edit_answer)
async def faq_edit_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    await q.update_faq(data["faq_id"], data["new_title"], message.text)
    await state.clear()
    await message.answer("✅ FAQ band tahrirlandi.", reply_markup=kb.admin_back_kb("adm:faq"))


@router.callback_query(F.data == "faq_del_list")
async def faq_del_list(call: CallbackQuery):
    faqs = await q.list_faqs()
    if not faqs:
        await call.answer("FAQ yo'q", show_alert=True)
        return
    await call.message.edit_text("O'chiriladigan savolni tanlang:",
                                 reply_markup=kb.faq_pick_kb(faqs, "faqdel"))
    await call.answer()


@router.callback_query(F.data.startswith("faqdel:"))
async def faq_del(call: CallbackQuery):
    faq_id = int(call.data.split(":")[1])
    await q.delete_faq(faq_id)
    await call.message.edit_text("🗑 FAQ band o'chirildi.", reply_markup=kb.admin_back_kb("adm:faq"))
    await call.answer()


# ---------------- Filiallarni boshqarish ----------------
@router.callback_query(F.data == "adm:br")
async def br_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    branches = await q.list_branches()
    lst = "\n".join(b["name"] for b in branches) or "(yo'q)"
    await call.message.edit_text(f"🏥 <b>Filiallarni boshqarish</b>\n\n{lst}\n\nAmalni tanlang:",
                                 reply_markup=kb.branch_admin_kb())
    await call.answer()


@router.callback_query(F.data == "br_add")
async def br_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.br_name)
    await call.message.edit_text("Yangi filial nomini kiriting:\n\nMasalan: 🏥 Mirzo Ulug'bek filiali")
    await call.answer()


@router.message(AdminFlow.br_name)
async def br_name(message: Message, state: FSMContext):
    await state.update_data(br_name=message.text)
    await state.set_state(AdminFlow.br_address)
    await message.answer("Filial manzilini kiriting:")


@router.message(AdminFlow.br_address)
async def br_address(message: Message, state: FSMContext):
    await state.update_data(br_address=message.text)
    await state.set_state(AdminFlow.br_phone)
    await message.answer("Filial telefon raqamini kiriting:\n\nMasalan: +998712000005")


def parse_hours(text: str):
    """Matndan ish vaqtini ajratadi. '08:00-23:00' -> ('08:00','23:00'). Aks holda None."""
    import re
    found = re.findall(r"\b(\d{1,2}:\d{2})\b", text or "")
    if len(found) >= 2:
        return found[0], found[1]
    return None


@router.message(AdminFlow.br_phone)
async def br_phone(message: Message, state: FSMContext):
    await state.update_data(br_phone=message.text)
    await state.set_state(AdminFlow.br_hours)
    await message.answer(
        "Filialning ish vaqtini kiriting (boshlanish va tugash):\n\n"
        "Masalan: <code>08:00-23:00</code>\n\n"
        "(Bo'sh qoldirish uchun <code>-</code> yuboring — 08:00-23:00 qabul qilinadi.)"
    )


@router.message(AdminFlow.br_hours)
async def br_hours(message: Message, state: FSMContext):
    hours = parse_hours(message.text)
    if hours:
        await state.update_data(open_time=hours[0], close_time=hours[1])
    else:
        # Standart vaqt
        await state.update_data(open_time="08:00", close_time="23:00")
    await state.set_state(AdminFlow.br_location)
    await message.answer(
        "Filial lokatsiyasini yuboring 📍\n\nTugmadan foydalaning yoki "
        "koordinatalarni <code>41.31,69.24</code> ko'rinishida matn qilib yuboring.",
        reply_markup=kb.location_request_kb(),
    )


@router.message(AdminFlow.br_location, F.location)
async def br_location_geo(message: Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await _ask_branch_photo(message, state)


@router.message(AdminFlow.br_location, F.text)
async def br_location_text(message: Message, state: FSMContext):
    try:
        lat, lon = map(float, message.text.replace(" ", "").split(","))
        await state.update_data(lat=lat, lon=lon)
    except (ValueError, TypeError):
        await state.update_data(lat=None, lon=None)
        await message.answer("⚠️ Koordinata noto'g'ri, lokatsiyasiz davom etamiz.")
    await _ask_branch_photo(message, state)


async def _ask_branch_photo(message, state):
    await state.set_state(AdminFlow.br_photo)
    await message.answer(
        "Endi filial rasmini yuboring 📷\n\nYoki \"⏭ O'tkazib yuborish\" tugmasini bosing.",
        reply_markup=kb.skip_kb(),
    )


@router.message(AdminFlow.br_photo, F.photo)
async def br_photo(message: Message, state: FSMContext):
    await _save_branch(message, state, message.photo[-1].file_id)


@router.message(AdminFlow.br_photo, F.text == "⏭ O'tkazib yuborish")
async def br_photo_skip(message: Message, state: FSMContext):
    await _save_branch(message, state, None)


@router.message(AdminFlow.br_photo)
async def br_photo_bad(message: Message):
    await message.answer("Rasm yuboring yoki \"⏭ O'tkazib yuborish\" tugmasini bosing.")


async def _save_branch(message, state, photo_id):
    d = await state.get_data()
    open_t = d.get("open_time", "08:00")
    close_t = d.get("close_time", "23:00")
    await q.add_branch(d["br_name"], d["br_address"], d["br_phone"],
                       d.get("lat"), d.get("lon"), photo_id, open_t, close_t)
    await state.clear()
    await message.answer(
        "✅ <b>Yangi filial qo'shildi!</b>\n\n"
        f"🏥 Nomi: {d['br_name']}\n📍 Manzil: {d['br_address']}\n☎️ Telefon: {d['br_phone']}\n"
        f"🕐 Ish vaqti: {open_t} — {close_t}\n"
        f"🗺 Lokatsiya: {'qabul qilindi' if d.get('lat') else 'berilmadi'}\n"
        f"📷 Rasm: {'yuklandi' if photo_id else 'yuklanmadi'}",
        reply_markup=kb.REMOVE,
    )
    await message.answer(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())


# --- Filial tahrirlash ---
@router.callback_query(F.data == "br_edit_list")
async def br_edit_list(call: CallbackQuery):
    branches = await q.list_branches()
    if not branches:
        await call.answer("Filial yo'q", show_alert=True)
        return
    await call.message.edit_text("Tahrirlanadigan filialni tanlang:",
                                 reply_markup=kb.branch_pick_kb(branches, "bredit_pick"))
    await call.answer()


@router.callback_query(F.data.startswith("bredit_pick:"))
async def br_edit_pick(call: CallbackQuery):
    branch_id = int(call.data.split(":")[1])
    b = await q.get_branch(branch_id)
    await call.message.edit_text(f"🏥 <b>{b['name']}</b>\n\nQaysi maydonni tahrirlamoqchisiz?",
                                 reply_markup=kb.branch_edit_fields_kb(branch_id))
    await call.answer()


@router.callback_query(F.data.startswith("bredit:"))
async def br_edit_field(call: CallbackQuery, state: FSMContext):
    _, field, branch_id = call.data.split(":")
    branch_id = int(branch_id)
    await state.update_data(edit_branch=branch_id, edit_field=field)
    if field == "photo":
        await state.set_state(AdminFlow.br_edit_value)
        await call.message.answer("Yangi rasmni yuboring (eskisini almashtiradi):")
    elif field == "location":
        await state.set_state(AdminFlow.br_edit_value)
        await call.message.answer("Yangi lokatsiyani yuboring 📍 yoki <code>lat,lon</code> matn qilib yuboring.",
                                  reply_markup=kb.location_request_kb())
    elif field == "hours":
        await state.set_state(AdminFlow.br_edit_value)
        await call.message.answer("Yangi ish vaqtini kiriting:\n\nMasalan: <code>09:00-21:00</code>")
    else:
        labels = {"name": "nom", "address": "manzil", "phone": "telefon"}
        await state.set_state(AdminFlow.br_edit_value)
        await call.message.answer(f"Yangi {labels[field]}ni kiriting:")
    await call.answer()


@router.message(AdminFlow.br_edit_value)
async def br_edit_value(message: Message, state: FSMContext):
    d = await state.get_data()
    branch_id, field = d["edit_branch"], d["edit_field"]
    if field == "photo":
        if not message.photo:
            await message.answer("Iltimos, rasm yuboring.")
            return
        await q.update_branch(branch_id, "photo_file_id", message.photo[-1].file_id)
        msg = "✅ Filial rasmi yangilandi."
    elif field == "location":
        if message.location:
            await q.update_branch_location(branch_id, message.location.latitude,
                                           message.location.longitude)
        else:
            try:
                lat, lon = map(float, message.text.replace(" ", "").split(","))
                await q.update_branch_location(branch_id, lat, lon)
            except (ValueError, TypeError):
                await message.answer("⚠️ Koordinata noto'g'ri.")
                return
        msg = "✅ Filial lokatsiyasi yangilandi."
    elif field == "hours":
        hours = parse_hours(message.text)
        if not hours:
            await message.answer("⚠️ Ish vaqti noto'g'ri. Masalan: <code>09:00-21:00</code>")
            return
        await q.update_branch(branch_id, "open_time", hours[0])
        await q.update_branch(branch_id, "close_time", hours[1])
        msg = f"✅ Ish vaqti yangilandi: {hours[0]} — {hours[1]}"
    else:
        await q.update_branch(branch_id, field, message.text)
        msg = "✅ Filial ma'lumoti yangilandi."
    await state.clear()
    await message.answer(msg, reply_markup=kb.REMOVE)
    await message.answer(t.ADMIN_MENU, reply_markup=kb.admin_menu_kb())


# --- Filial o'chirish ---
@router.callback_query(F.data == "br_del_list")
async def br_del_list(call: CallbackQuery):
    branches = await q.list_branches()
    if not branches:
        await call.answer("Filial yo'q", show_alert=True)
        return
    await call.message.edit_text("O'chiriladigan filialni tanlang:",
                                 reply_markup=kb.branch_pick_kb(branches, "brdel"))
    await call.answer()


@router.callback_query(F.data.startswith("brdel:"))
async def br_del_confirm(call: CallbackQuery):
    branch_id = int(call.data.split(":")[1])
    b = await q.get_branch(branch_id)
    await call.message.edit_text(
        f"❗ \"{b['name']}\" filialini o'chirishni tasdiqlaysizmi?",
        reply_markup=kb.confirm_kb(f"brdel_ok:{branch_id}", "adm:br"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("brdel_ok:"))
async def br_del_ok(call: CallbackQuery):
    branch_id = int(call.data.split(":")[1])
    await q.delete_branch(branch_id)
    await call.message.edit_text("🗑 Filial o'chirildi.", reply_markup=kb.admin_back_kb("adm:br"))
    await call.answer()


# ---------------- Operatorlar boshqaruvi ----------------
@router.callback_query(F.data == "adm:op")
async def op_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    ops = await q.list_operators()
    if ops:
        lines = []
        for i, o in enumerate(ops):
            mark = "🟢 Faol" if o["status"] == "active" else "🔴 Faol emas"
            lines.append(f"{i+1}. {o['name']} — {o['login']} — {mark}")
        lst = "\n".join(lines)
    else:
        lst = "(operator yo'q)"
    await call.message.edit_text(f"👨‍⚕️ <b>Operatorlar ro'yxati</b>\n\n{lst}\n\nAmalni tanlang:",
                                 reply_markup=kb.operators_admin_kb())
    await call.answer()


@router.callback_query(F.data == "op_add")
async def op_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.op_name)
    await call.message.edit_text("Yangi operator ismini kiriting:")
    await call.answer()


@router.message(AdminFlow.op_name)
async def op_name(message: Message, state: FSMContext):
    await state.update_data(op_name=message.text)
    await state.set_state(AdminFlow.op_login)
    await message.answer("Operator uchun login (foydalanuvchi nomi) kiriting:")


@router.message(AdminFlow.op_login)
async def op_login_step(message: Message, state: FSMContext):
    login = message.text.strip()
    if await q.get_operator_by_login(login):
        await message.answer("⚠️ Bu login band. Boshqa login kiriting:")
        return
    await state.update_data(op_login=login)
    await state.set_state(AdminFlow.op_password)
    await message.answer("Operator uchun parol kiriting (yoki <code>avto</code> deb yozsangiz, "
                         "bot avtomatik yaratadi):")


@router.message(AdminFlow.op_password)
async def op_password_step(message: Message, state: FSMContext):
    d = await state.get_data()
    pwd = message.text.strip()
    if pwd.lower() == "avto":
        pwd = secrets.token_urlsafe(6)
    await q.add_operator(d["op_name"], d["op_login"], pwd)
    await state.clear()
    await message.answer(
        "✅ <b>Yangi operator qo'shildi!</b>\n\n"
        f"👨‍⚕️ Ism: {d['op_name']}\n🔑 Login: <code>{d['op_login']}</code>\n"
        f"🔐 Parol: <code>{pwd}</code>\n\n"
        "Bu ma'lumotlarni operatorga xavfsiz yetkazing. Operator /operator orqali kiradi.",
        reply_markup=kb.admin_back_kb("adm:op"),
    )


@router.callback_query(F.data == "op_toggle_list")
async def op_toggle_list(call: CallbackQuery):
    ops = await q.list_operators()
    if not ops:
        await call.answer("Operator yo'q", show_alert=True)
        return
    await call.message.edit_text("Holatini o'zgartirish uchun operatorni tanlang:",
                                 reply_markup=kb.operator_pick_kb(ops, "optoggle"))
    await call.answer()


@router.callback_query(F.data.startswith("optoggle:"))
async def op_toggle(call: CallbackQuery):
    op_id = int(call.data.split(":")[1])
    op = await q.get_operator(op_id)
    new_status = "inactive" if op["status"] == "active" else "active"
    await q.update_operator(op_id, "status", new_status)
    if new_status == "inactive":
        await q.logout_operator(op["telegram_id"]) if op["telegram_id"] else None
    label = "faollashtirildi 🟢" if new_status == "active" else "bloklandi 🔴"
    await call.message.edit_text(f"✅ {op['name']} {label}.", reply_markup=kb.admin_back_kb("adm:op"))
    await call.answer()


@router.callback_query(F.data == "op_del_list")
async def op_del_list(call: CallbackQuery):
    ops = await q.list_operators()
    if not ops:
        await call.answer("Operator yo'q", show_alert=True)
        return
    await call.message.edit_text("O'chiriladigan operatorni tanlang:",
                                 reply_markup=kb.operator_pick_kb(ops, "opdel"))
    await call.answer()


@router.callback_query(F.data.startswith("opdel:"))
async def op_del(call: CallbackQuery):
    op_id = int(call.data.split(":")[1])
    await q.delete_operator(op_id)
    await call.message.edit_text("🗑 Operator o'chirildi.", reply_markup=kb.admin_back_kb("adm:op"))
    await call.answer()


@router.callback_query(F.data == "op_stat_list")
async def op_stat_list(call: CallbackQuery):
    ops = await q.list_operators()
    if not ops:
        await call.answer("Operator yo'q", show_alert=True)
        return
    await call.message.edit_text("Statistikasini ko'rish uchun operatorni tanlang:",
                                 reply_markup=kb.operator_pick_kb(ops, "opstat"))
    await call.answer()


@router.callback_query(F.data.startswith("opstat:"))
async def op_stat(call: CallbackQuery):
    op_id = int(call.data.split(":")[1])
    op = await q.get_operator(op_id)
    s = await q.operator_stats(op_id)
    await call.message.edit_text(
        f"📊 <b>{op['name']}</b> statistikasi\n\n"
        f"📥 Qabul qilingan: {s['accepted']}\n✅ Yakunlangan: {s['done']}\n"
        f"💊 Hisoblangan: {s['billed']}\n📅 Bugun: {s['today_done']}\n📆 Oylik: {s['month_done']}\n"
        f"⭐ O'rtacha baho: {s['avg_rating']} ({s['rated_count']} ta)",
        reply_markup=kb.admin_back_kb("adm:op"),
    )
    await call.answer()


# ---------------- Murojaatlar tarixi ----------------
@router.callback_query(F.data == "adm:hist")
async def hist_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("📁 <b>Murojaatlar tarixi</b>\n\nFiltrni tanlang:",
                                 reply_markup=kb.history_kb())
    await call.answer()


@router.callback_query(F.data.startswith("hist:"))
async def hist_pick(call: CallbackQuery, state: FSMContext):
    mode = call.data.split(":")[1]
    await state.set_state(AdminFlow.search_value)
    await state.update_data(hist_mode=mode)
    prompts = {
        "id": "🔎 Murojaat raqamini kiriting (masalan: 1234):",
        "user": "👤 Foydalanuvchi ismi yoki telefon raqamini kiriting:",
        "branch": "🏥 Filial nomini (yoki bir qismini) kiriting:",
    }
    await call.message.edit_text(prompts[mode])
    await call.answer()


@router.message(AdminFlow.search_value)
async def hist_search(message: Message, state: FSMContext):
    d = await state.get_data()
    mode = d["hist_mode"]
    val = message.text.strip().lstrip("#")
    await state.clear()
    rows = await q.all_orders_full()
    if mode == "id":
        rows = [r for r in rows if str(r["id"]) == val]
    elif mode == "user":
        rows = [r for r in rows if (r["full_name"] and val.lower() in r["full_name"].lower())
                or (r["phone"] and val in r["phone"])]
    else:
        rows = [r for r in rows if r["branch"] and val.lower() in r["branch"].lower()]

    if not rows:
        await message.answer("Hech narsa topilmadi.", reply_markup=kb.admin_back_kb("adm:hist"))
        return

    if mode == "id":
        r = rows[0]
        msgs = await q.order_messages(r["id"])
        chat = "\n".join(
            f"[{'mijoz' if m['sender']=='client' else 'operator'}]: "
            f"{m['text'] or '('+m['content_type']+')'}" for m in msgs
        ) or "(yozishma yo'q)"
        rating_line = (f"⭐ Baho: {'⭐' * int(r['rating'])} ({r['rating']}/5)\n"
                       if r["rating"] else "⭐ Baho: —\n")
        feedback_line = f"💬 Mijoz izohi: {r['feedback']}\n" if r["feedback"] else ""
        await message.answer(
            f"📋 <b>Murojaat #{r['id']}</b>\n\n"
            f"👤 Mijoz: {r['full_name']}, {r['phone']}\n"
            f"🏥 Filial: {r['branch']}\n👨‍⚕️ Operator: {r['operator'] or '—'}\n"
            f"🕐 Boshlangan: {r['created_at']}\n🕐 Yakunlangan: {r['closed_at'] or '—'}\n"
            f"Holat: {STATUS_LABEL.get(r['status'], r['status'])}\n"
            f"{rating_line}{feedback_line}\n"
            f"💬 <b>Yozishma:</b>\n{chat}",
            reply_markup=kb.admin_back_kb("adm:hist"),
        )
    else:
        lines = [f"Topildi: {len(rows)} ta\n"]
        for r in rows[:25]:
            lines.append(f"#{r['id']} — {r['full_name']} — {STATUS_LABEL.get(r['status'], r['status'])}")
        await message.answer("\n".join(lines), reply_markup=kb.admin_back_kb("adm:hist"))


# ---------------- Bog'lanish matnini tahrirlash ----------------
@router.callback_query(F.data == "adm:contact")
async def contact_edit_start(call: CallbackQuery, state: FSMContext):
    cur = await q.get_setting("contact_text")
    await state.set_state(AdminFlow.contact_edit)
    await call.message.edit_text(f"Hozirgi matn:\n\n{cur}\n\n➡️ Yangi matnni yuboring:")
    await call.answer()


@router.message(AdminFlow.contact_edit)
async def contact_edit_save(message: Message, state: FSMContext):
    await q.set_setting("contact_text", message.html_text)
    await state.clear()
    await message.answer("✅ Bog'lanish matni yangilandi.", reply_markup=kb.admin_back_kb())
