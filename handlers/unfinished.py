"""Yakunlanmagan murojaatlar — admin va operator uchun umumiy bo'lim."""
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import now_local
from database import queries as q
from utils import STATUS_LABEL, fmt_dt, is_admin

router = Router()

PAGE_SIZE = 8
MARK = {"new": "🟡", "in_progress": "🔵"}


def _wait_str(created_at: str) -> str:
    """created_at dan hozirgacha qancha kutganini matn qiladi."""
    try:
        start = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"
    mins = int((now_local() - start).total_seconds() // 60)
    if mins < 1:
        return "hozir"
    if mins < 60:
        return f"{mins} daqiqa"
    h, m = divmod(mins, 60)
    if h < 24:
        return f"{h} soat {m} daqiqa"
    d, h = divmod(h, 24)
    return f"{d} kun {h} soat"


def _name_link(o) -> str:
    name = o["full_name"] or "—"
    if o["username"]:
        return f'<a href="https://t.me/{o["username"]}">{name}</a>'
    return f'<a href="tg://user?id={o["user_id"]}">{name}</a>'


def _list_kb(orders, page: int):
    total = len(orders)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = orders[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    kb = InlineKeyboardBuilder()
    for o in chunk:
        mark = MARK.get(o["status"], "•")
        op = o["operator"] or "biriktirilmagan"
        kb.row(InlineKeyboardButton(
            text=f"{mark} #{o['id']} — {o['full_name'] or '—'} — {op}",
            callback_data=f"unford:{o['id']}:{page}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"unfin:{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"unfin:{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"unfin:{page}"))
    return kb.as_markup(), page, pages


_EMPTY = "✅ Yakunlanmagan murojaatlar yo'q. Hammasi yopilgan! 👏"


async def _render():
    orders = await q.unfinished_orders()
    return orders


def _list_text(orders, page, pages):
    new_cnt = sum(1 for o in orders if o["status"] == "new")
    prog_cnt = sum(1 for o in orders if o["status"] == "in_progress")
    return (f"📌 <b>Yakunlanmagan murojaatlar: {len(orders)} ta</b>\n"
            f"🟡 Yangi: {new_cnt}   🔵 Jarayonda: {prog_cnt}\n"
            f"<i>Sahifa {page+1}/{pages} — eng eskisi tepada</i>")


async def show_list(call: CallbackQuery, page: int = 0):
    orders = await q.unfinished_orders()
    if not orders:
        try:
            await call.message.edit_text(_EMPTY)
        except Exception:
            await call.message.answer(_EMPTY)
        await call.answer()
        return
    markup, page, pages = _list_kb(orders, page)
    try:
        await call.message.edit_text(_list_text(orders, page, pages), reply_markup=markup)
    except Exception:
        await call.message.answer(_list_text(orders, page, pages), reply_markup=markup)
    await call.answer()


async def open_for_message(message):
    """Reply-tugma (operator) orqali kirish — yangi xabar yuboradi."""
    orders = await q.unfinished_orders()
    if not orders:
        await message.answer(_EMPTY)
        return
    markup, page, pages = _list_kb(orders, 0)
    await message.answer(_list_text(orders, page, pages), reply_markup=markup)


# ---- Admin paneldan kirish ----
@router.callback_query(F.data == "adm:unfin")
async def adm_unfin(call: CallbackQuery):
    await show_list(call, 0)


# ---- Sahifalash ----
@router.callback_query(F.data.startswith("unfin:"))
async def unfin_page(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    await show_list(call, page)


# ---- Murojaat tafsiloti ----
@router.callback_query(F.data.startswith("unford:"))
async def unfin_detail(call: CallbackQuery):
    _, oid, page = call.data.split(":")
    oid, page = int(oid), int(page)
    order = await q.get_order(oid)
    if not order:
        await call.answer("Topilmadi yoki o'chirilgan", show_alert=True)
        return
    # to'liq ma'lumot uchun unfinished ro'yxatidan topamiz (username/operator nomi bilan)
    row = next((o for o in await q.unfinished_orders() if o["id"] == oid), None)
    if not row:
        await call.answer("Bu murojaat allaqachon yakunlangan.", show_alert=True)
        await show_list(call, page)
        return

    msgs = await q.order_messages(oid)
    first = next((m for m in msgs if m["sender"] == "client"), None)
    if first and first["text"]:
        preview = f"\n\n📝 <b>Mijoz:</b> {first['text'][:300]}"
    elif first:
        preview = f"\n\n📎 Mijoz {first['content_type']} yubordi"
    else:
        preview = ""

    text = (f"📋 <b>Murojaat #{row['id']}</b>\n\n"
            f"👤 Mijoz: {_name_link(row)}\n"
            f"📞 Telefon: {row['phone'] or '—'}\n"
            f"🏥 Filial: {row['branch'] or '—'}\n"
            f"👨‍⚕️ Operator: {row['operator'] or 'biriktirilmagan'}\n"
            f"🕐 Sana: {fmt_dt(row['created_at'])}\n"
            f"⏳ Kutyapti: {_wait_str(row['created_at'])}\n"
            f"Holat: {STATUS_LABEL.get(row['status'], row['status'])}"
            f"{preview}")

    kb = InlineKeyboardBuilder()
    # Operator bo'lsa — amal tugmalari
    op = await q.get_operator_by_tg(call.from_user.id)
    if op and op["status"] == "active":
        if not row["operator_id"]:
            kb.row(InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"op_accept:{oid}"))
        elif row["operator_id"] == op["id"]:
            kb.row(InlineKeyboardButton(text="💬 Ochish", callback_data=f"opmine:{oid}"))
    kb.row(InlineKeyboardButton(text="🔙 Ro'yxatga", callback_data=f"unfin:{page}"))
    try:
        await call.message.edit_text(text, reply_markup=kb.as_markup(), disable_web_page_preview=True)
    except Exception:
        await call.message.answer(text, reply_markup=kb.as_markup(), disable_web_page_preview=True)
    await call.answer()
