"""Reply va inline klaviaturalar."""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import locales as loc
try:
    from config import WEBAPP_URL as _WEBAPP_URL
except Exception:
    _WEBAPP_URL = ""

REMOVE = ReplyKeyboardRemove()

# Vakansiyalar boti (jamoaga qo'shilish)
VACANCY_BOT_URL = "https://t.me/Gulnorafarmvacancy_bot"

# Operator kabineti tugmalari (xodimlar uchun, o'zbekcha qoladi)
BTN_OP_BACK = "🔙 Bosh menyu"


def lang_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="setlang:uz"))
    kb.row(InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru"))
    return kb.as_markup()


def main_menu(lang="uz", is_admin: bool = False, is_operator: bool = False,
              show_faq: bool = True) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=loc.btn("order", lang))]]
    # Filiallar | Eng yaqin filial — yonma-yon
    rows.append([KeyboardButton(text=loc.btn("branches", lang)),
                 KeyboardButton(text=loc.btn("nearest", lang))])
    third = []
    if show_faq:
        third.append(KeyboardButton(text=loc.btn("faq", lang)))
    third.append(KeyboardButton(text=loc.btn("my_orders", lang)))
    rows.append(third)
    rows.append([KeyboardButton(text=loc.btn("contact", lang))])
    rows.append([KeyboardButton(text=loc.btn("join_team", lang))])
    if is_operator:
        rows.append([KeyboardButton(text=loc.btn("op_cabinet", lang))])
    if is_admin:
        rows.append([KeyboardButton(text=loc.btn("admin", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def vacancy_kb(lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("open_vacancy", lang), url=VACANCY_BOT_URL))
    return kb.as_markup()


def register_kb(lang="uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=loc.btn("register", lang))]],
        resize_keyboard=True,
    )


def phone_kb(lang="uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=loc.btn("send_phone", lang), request_contact=True)]],
        resize_keyboard=True,
    )


# ---- Inline: obuna tekshirish ----
def subscribe_kb(channels, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        username = ch["chat_id"]
        url = f"https://t.me/{username.lstrip('@')}" if str(username).startswith("@") else None
        if url:
            kb.row(InlineKeyboardButton(text=f"📢 {ch['title']}", url=url))
    kb.row(InlineKeyboardButton(text=loc.btn("check_sub", lang), callback_data="check_sub"))
    return kb.as_markup()


# ---- Inline: filial tanlash (ro'yxatdan o'tishda) ----
def branches_choose_kb(branches, prefix="pickbranch", lang="uz", show_skip=True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in branches:
        kb.row(InlineKeyboardButton(text=b["name"], callback_data=f"{prefix}:{b['id']}"))
    kb.row(InlineKeyboardButton(text=loc.btn("nearest", lang), callback_data="regnear"))
    if show_skip:
        kb.row(InlineKeyboardButton(text=loc.btn("skip", lang), callback_data="branch_skip"))
    return kb.as_markup()


# ---- Inline: filiallar bo'limi ----
def branches_list_kb(branches, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in branches:
        kb.row(InlineKeyboardButton(text=b["name"], callback_data=f"branch_info:{b['id']}"))
    return kb.as_markup()


def client_location_kb(lang="uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=loc.btn("send_location", lang), request_location=True)]],
        resize_keyboard=True,
    )


def my_orders_kb(orders) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    marks = {"new": "🟡", "in_progress": "🔵", "done": "🟢", "canceled": "🔴"}
    for o in orders:
        m = marks.get(o["status"], "•")
        kb.row(InlineKeyboardButton(text=f"{m} #{o['id']} — {o['created_at'][:10]}",
                                    callback_data=f"myorder:{o['id']}"))
    return kb.as_markup()


def my_order_cancel_kb(order_id, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.t("cancel_order_btn", lang),
                                callback_data=f"myordercancel:{order_id}"))
    return kb.as_markup()


def branch_card_kb(branch_id, has_location, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("select_branch", lang),
                                callback_data=f"branch_select:{branch_id}"))
    if has_location:
        kb.row(InlineKeyboardButton(text=loc.btn("map", lang), callback_data=f"branch_map:{branch_id}"))
    kb.row(InlineKeyboardButton(text=loc.btn("branches_back", lang), callback_data="branches_back"))
    return kb.as_markup()


# ---- Inline: FAQ ----
def faq_kb(faqs) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in faqs:
        kb.row(InlineKeyboardButton(text=f["title"], callback_data=f"faq:{f['id']}"))
    return kb.as_markup()


def faq_back_kb(lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("back", lang), callback_data="faq_back"))
    return kb.as_markup()


def cancel_inline(cb="cancel_order", lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("cancel", lang), callback_data=cb))
    return kb.as_markup()


def rating_kb(order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in range(1, 6):
        kb.button(text=f"{n}⭐", callback_data=f"rate:{order_id}:{n}")
    kb.adjust(5)
    return kb.as_markup()


def feedback_skip_kb(order_id, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("skip", lang), callback_data=f"fb_skip:{order_id}"))
    return kb.as_markup()


def contact_confirm_kb(lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=loc.btn("confirm_yes", lang), callback_data="contact_send"),
           InlineKeyboardButton(text=loc.btn("confirm_no", lang), callback_data="contact_cancel"))
    return kb.as_markup()


# ---- Operatorga yangi murojaat (kabinet ichida — callback) ----
def order_accept_kb(order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"op_accept:{order_id}"))
    return kb.as_markup()


# ---- Operatorlar guruhi uchun — havola (bosilsa avtomatik botga o'tadi) ----
def order_accept_link_kb(order_id, bot_username) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    url = f"https://t.me/{bot_username}?start=accept_{order_id}"
    kb.row(InlineKeyboardButton(text="✅ Qabul qilish (botda ochish)", url=url))
    return kb.as_markup()


# ========================= ADMIN =========================
def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"))
    kb.row(InlineKeyboardButton(text="🔴 Real vaqt", callback_data="adm:live"))
    kb.row(InlineKeyboardButton(text="📚 Hisobotlar", callback_data="adm:reports"))
    kb.row(InlineKeyboardButton(text="📌 Yakunlanmagan murojaatlar", callback_data="adm:unfin"))
    kb.row(InlineKeyboardButton(text="📨 Ommaviy xabar", callback_data="adm:bc"))
    kb.row(InlineKeyboardButton(text="📢 Kanal boshqaruvi", callback_data="adm:ch"))
    kb.row(InlineKeyboardButton(text="❓ FAQ boshqaruvi", callback_data="adm:faq"))
    kb.row(InlineKeyboardButton(text="🏥 Filiallar", callback_data="adm:br"))
    kb.row(InlineKeyboardButton(text="👨‍⚕️ Operatorlar", callback_data="adm:op"))
    kb.row(InlineKeyboardButton(text="🤖 Operator botlari", callback_data="adm:bots"))
    kb.row(InlineKeyboardButton(text="📝 Tayyor javoblar", callback_data="adm:tpl"))
    kb.row(InlineKeyboardButton(text="📁 Murojaatlar tarixi", callback_data="adm:hist"))
    kb.row(InlineKeyboardButton(text="🕐 Umumiy ish vaqti", callback_data="adm:workhours"))
    kb.row(InlineKeyboardButton(text="🔤 Operator tugmalari matni", callback_data="adm:opbtn"))
    kb.row(InlineKeyboardButton(text="✏️ Bog'lanish matnini tahrirlash", callback_data="adm:contact"))
    return kb.as_markup()


def templates_admin_kb(templates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Matn shablon", callback_data="tpl_add"),
           InlineKeyboardButton(text="🎭 Stiker shablon", callback_data="tpl_add_sticker"))
    for tpl in templates:
        kb.row(InlineKeyboardButton(text=f"🗑 {_tpl_label(tpl)}", callback_data=f"tpldel:{tpl['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def admin_back_kb(cb="adm:menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=cb))
    return kb.as_markup()


def live_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm:live"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def stats_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📥 Excel hisoboti", callback_data="adm:excel"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def bc_type_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📝 Matn", callback_data="bc_type:text"),
           InlineKeyboardButton(text="🖼 Rasm", callback_data="bc_type:photo"))
    kb.row(InlineKeyboardButton(text="🎥 Video", callback_data="bc_type:video"),
           InlineKeyboardButton(text="📄 Hujjat", callback_data="bc_type:document"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def bc_target_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👥 Barcha foydalanuvchilarga", callback_data="bc_t:all"))
    kb.row(InlineKeyboardButton(text="🏥 Faqat ma'lum filialga", callback_data="bc_t:branch"))
    kb.row(InlineKeyboardButton(text="🟢 Faqat faol foydalanuvchilarga", callback_data="bc_t:active"))
    kb.row(InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="adm:menu"))
    return kb.as_markup()


def confirm_kb(yes_cb, no_cb="adm:menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Ha", callback_data=yes_cb),
           InlineKeyboardButton(text="❌ Yo'q", callback_data=no_cb))
    return kb.as_markup()


def channels_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch_add"))
    kb.row(InlineKeyboardButton(text="🗑 Kanalni o'chirish", callback_data="ch_del"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def list_delete_kb(items, prefix, back="adm:menu") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for it in items:
        title = it["title"] if "title" in it.keys() else it["name"]
        kb.row(InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"{prefix}:{it['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=back))
    return kb.as_markup()


def faq_admin_kb(enabled: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Savol qo'shish", callback_data="faq_add"))
    kb.row(InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="faq_edit_list"))
    kb.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data="faq_del_list"))
    if enabled:
        kb.row(InlineKeyboardButton(text="🔕 Bo'limni o'chirish (menyudan yashirish)",
                                    callback_data="faq_toggle"))
    else:
        kb.row(InlineKeyboardButton(text="🔔 Bo'limni yoqish (menyuda ko'rsatish)",
                                    callback_data="faq_toggle"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def faq_pick_kb(faqs, action) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in faqs:
        kb.row(InlineKeyboardButton(text=f["title"], callback_data=f"{action}:{f['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:faq"))
    return kb.as_markup()


def branch_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Filial qo'shish", callback_data="br_add"))
    kb.row(InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="br_edit_list"))
    kb.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data="br_del_list"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def branch_pick_kb(branches, action) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in branches:
        kb.row(InlineKeyboardButton(text=b["name"], callback_data=f"{action}:{b['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:br"))
    return kb.as_markup()


def branch_edit_fields_kb(branch_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Nomi", callback_data=f"bredit:name:{branch_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Manzili", callback_data=f"bredit:address:{branch_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Telefon", callback_data=f"bredit:phone:{branch_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Lokatsiya", callback_data=f"bredit:location:{branch_id}"))
    kb.row(InlineKeyboardButton(text="🕐 Ish vaqti", callback_data=f"bredit:hours:{branch_id}"))
    kb.row(InlineKeyboardButton(text="🖼 Rasm", callback_data=f"bredit:photo:{branch_id}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="br_edit_list"))
    return kb.as_markup()


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish")]],
        resize_keyboard=True,
    )


def location_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiya yuborish", request_location=True)]],
        resize_keyboard=True,
    )


def operators_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Operator qo'shish", callback_data="op_add"))
    kb.row(InlineKeyboardButton(text="✏️ Tahrirlash (ism/login/parol)", callback_data="op_edit_list"))
    kb.row(InlineKeyboardButton(text="⛔ Bloklash / Faollashtirish", callback_data="op_toggle_list"))
    kb.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data="op_del_list"))
    kb.row(InlineKeyboardButton(text="📊 Operator statistikasi", callback_data="op_stat_list"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def operator_edit_fields_kb(op_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Ismi", callback_data=f"opedit:name:{op_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Login", callback_data=f"opedit:login:{op_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Parol", callback_data=f"opedit:password:{op_id}"))
    kb.row(InlineKeyboardButton(text="🕐 Ish vaqti", callback_data=f"opedit:hours:{op_id}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="op_edit_list"))
    return kb.as_markup()


def operator_pick_kb(operators, action, back="adm:op") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in operators:
        mark = "🟢" if o["status"] == "active" else "🔴"
        kb.row(InlineKeyboardButton(text=f"{mark} {o['name']}", callback_data=f"{action}:{o['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=back))
    return kb.as_markup()


def history_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔎 Murojaat raqami bo'yicha", callback_data="hist:id"))
    kb.row(InlineKeyboardButton(text="👤 Foydalanuvchi bo'yicha", callback_data="hist:user"))
    kb.row(InlineKeyboardButton(text="🏥 Filial bo'yicha", callback_data="hist:branch"))
    kb.row(InlineKeyboardButton(text="👨‍⚕️ Operator bo'yicha", callback_data="hist:operator"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


# ========================= OPERATOR KABINETI =========================
def operator_menu(availability="free") -> ReplyKeyboardMarkup:
    status_btn = "🟢 Holatim: Bo'sh" if availability == "free" else "🔴 Holatim: Band"
    rows = []
    # Mini app (CRM) tugmasi — WEBAPP_URL sozlangan bo'lsa
    if _WEBAPP_URL:
        rows.append([KeyboardButton(text="🖥 Mini app (CRM)",
                                    web_app=WebAppInfo(url=_WEBAPP_URL + "/operator"))])
    rows += [
        [KeyboardButton(text="📥 Yangi murojaatlar"), KeyboardButton(text="📂 Mening murojaatlarim")],
        [KeyboardButton(text="📌 Yakunlanmagan murojaatlar")],
        [KeyboardButton(text="✅ Yakunlanganlar"), KeyboardButton(text="📊 Mening statistikam")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text=status_btn)],
        [KeyboardButton(text="🚪 Chiqish (logout)"), KeyboardButton(text=BTN_OP_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# Bot taniydigan barcha menyu tugmalari (proxy-chat ularni yutib yubormasligi uchun)
OPERATOR_MENU_BUTTONS = {
    "📥 Yangi murojaatlar", "📂 Mening murojaatlarim", "📌 Yakunlanmagan murojaatlar",
    "✅ Yakunlanganlar", "📊 Mening statistikam", "🏆 Reyting",
    "🚪 Chiqish (logout)", BTN_OP_BACK,
}
ALL_MENU_BUTTONS = (
    loc.labels("order", "faq", "branches", "contact", "admin", "op_cabinet", "register",
               "join_team", "my_orders", "nearest", "send_location")
    | OPERATOR_MENU_BUTTONS
    | {"🟢 Holatim: Bo'sh", "🔴 Holatim: Band"}
)


# Operator amal tugmalari matnlari (admin paneldan o'zgartirilishi mumkin)
OP_BTN = {
    "reply": "💬 Javob",
    "tpl": "📝 Tayyor javob",
    "bill": "💊 Hisoblash",
    "transfer": "🔄 Uzatish",
    "sendbranch": "📍 Filial ma'lumoti",
    "askbranch": "🏥 Filialni tanlatish",
    "autoclose": "⏱ 10 daqiqada avto-yakunlash",
    "done": "✅ Yakunlash",
    "cancel": "❌ Bekor",
}

# Tugma kalitlari uchun chiroyli nomlar (admin ko'rishi uchun)
OP_BTN_TITLES = {
    "reply": "Javob yozish", "tpl": "Tayyor javob", "bill": "Hisoblash",
    "transfer": "Uzatish", "sendbranch": "Filial ma'lumoti yuborish",
    "askbranch": "Filialni tanlatish",
    "autoclose": "10 daqiqada avto-yakunlash", "done": "Yakunlash", "cancel": "Bekor qilish",
}


def apply_op_buttons(overrides: dict):
    """settings dan kelgan matnlarni OP_BTN ga qo'llaydi."""
    for k, v in overrides.items():
        if k in OP_BTN and v:
            OP_BTN[k] = v


def op_order_actions_kb(order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=OP_BTN["reply"], callback_data=f"opc:reply:{order_id}"),
           InlineKeyboardButton(text=OP_BTN["tpl"], callback_data=f"opc:tpl:{order_id}"))
    kb.row(InlineKeyboardButton(text=OP_BTN["bill"], callback_data=f"opc:bill:{order_id}"),
           InlineKeyboardButton(text=OP_BTN["transfer"], callback_data=f"opc:transfer:{order_id}"))
    kb.row(InlineKeyboardButton(text=OP_BTN["sendbranch"], callback_data=f"opc:sendbranch:{order_id}"))
    kb.row(InlineKeyboardButton(text=OP_BTN["askbranch"], callback_data=f"opc:askbranch:{order_id}"))
    kb.row(InlineKeyboardButton(text=OP_BTN["autoclose"], callback_data=f"opc:autoclose:{order_id}"))
    kb.row(InlineKeyboardButton(text=OP_BTN["done"], callback_data=f"opc:done:{order_id}"),
           InlineKeyboardButton(text=OP_BTN["cancel"], callback_data=f"opc:cancel:{order_id}"))
    return kb.as_markup()


def operator_bots_admin_kb(bots) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Operator bot qo'shish", callback_data="bot_add"))
    for b in bots:
        mark = "🟢" if b["enabled"] else "🔴"
        kb.row(InlineKeyboardButton(text=f"{mark} {b['title']} (@{b['username']})",
                                    callback_data=f"botinfo:{b['id']}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def bot_info_kb(bot_id, enabled) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if enabled:
        kb.row(InlineKeyboardButton(text="🔕 O'chirib qo'yish", callback_data=f"bottoggle:{bot_id}"))
    else:
        kb.row(InlineKeyboardButton(text="🔔 Yoqish", callback_data=f"bottoggle:{bot_id}"))
    kb.row(InlineKeyboardButton(text="📊 Statistika", callback_data=f"botstat:{bot_id}"))
    kb.row(InlineKeyboardButton(text="🔑 Login/parolni o'zgartirish", callback_data=f"botcred:{bot_id}"))
    kb.row(InlineKeyboardButton(text="🗑 Botni o'chirish", callback_data=f"botdel:{bot_id}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:bots"))
    return kb.as_markup()


def op_buttons_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for k, title in OP_BTN_TITLES.items():
        kb.row(InlineKeyboardButton(text=f"{title} → {OP_BTN[k]}", callback_data=f"opbtn:{k}"))
    kb.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return kb.as_markup()


def op_ask_branch_kb(branches, order_id, lang="uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in branches:
        kb.row(InlineKeyboardButton(text=b["name"], callback_data=f"opbr:{order_id}:{b['id']}"))
    kb.row(InlineKeyboardButton(text=loc.btn("nearest", lang), callback_data=f"opbrnear:{order_id}"))
    return kb.as_markup()


def op_send_branch_kb(branches, order_id) -> InlineKeyboardMarkup:
    """Operator mijozga qaysi filial ma'lumotini yuborishni tanlaydi."""
    kb = InlineKeyboardBuilder()
    for b in branches:
        kb.row(InlineKeyboardButton(text=b["name"], callback_data=f"opsendbr:{order_id}:{b['id']}"))
    return kb.as_markup()


def branch_directions_kb(lat, lon, lang="uz") -> InlineKeyboardMarkup:
    """Filialga xaritada yo'l ko'rsatish (Google Maps)."""
    url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🧭 Yo'l ko'rsatish (xarita)", url=url))
    return kb.as_markup()


def _tpl_label(tpl) -> str:
    if tpl["sticker"]:
        return "🎭 Stiker"
    txt = tpl["text"] or "—"
    return (txt[:40] + "…") if len(txt) > 40 else txt


def templates_pick_kb(templates, order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tpl in templates:
        kb.row(InlineKeyboardButton(text=_tpl_label(tpl), callback_data=f"tplsend:{order_id}:{tpl['id']}"))
    return kb.as_markup()


def transfer_pick_kb(operators, order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in operators:
        mark = "🟢" if o["availability"] == "free" else "🔴"
        kb.row(InlineKeyboardButton(text=f"{mark} {o['name']}",
                                    callback_data=f"dotransfer:{order_id}:{o['id']}"))
    return kb.as_markup()


def op_orders_list_kb(orders, action) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.row(InlineKeyboardButton(text=f"#{o['id']}", callback_data=f"{action}:{o['id']}"))
    return kb.as_markup()


def save_login_kb(operator_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💾 Login va parolni saqlash",
                                callback_data=f"savelogin:{operator_id}"))
    return kb.as_markup()


def quick_login_kb(saved) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for op in saved:
        kb.row(
            InlineKeyboardButton(text=f"🔑 {op['name']} (saqlangan)",
                                 callback_data=f"quicklogin:{op['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"forgetlogin:{op['id']}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Boshqa hisob bilan kirish", callback_data="newlogin"))
    return kb.as_markup()


def bill_send_kb(order_id) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Ha, yuborish", callback_data=f"bill_send:{order_id}"),
           InlineKeyboardButton(text="❌ Yo'q, faqat saqlash", callback_data=f"bill_save:{order_id}"))
    return kb.as_markup()
