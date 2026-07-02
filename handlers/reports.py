"""Admin hisobotlari: murojaatlar tarixi (yozishma), mijozlar, operator reytingi,
soatlik yuklanma, davr hisoboti."""
from datetime import timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import now_local
from database import queries as q
from utils import is_admin
from states import AdminFlow

router = Router()
PAGE = 8

_CT = {"photo": "📷 rasm", "video": "🎥 video", "document": "📄 hujjat", "voice": "🎤 ovoz",
       "sticker": "🎭 stiker", "animation": "🎞 GIF", "location": "📍 lokatsiya"}
_ST = {"new": "🟡", "in_progress": "🔵", "done": "🟢", "canceled": "🔴"}
_ST_FULL = {"new": "🟡 Yangi", "in_progress": "🔵 Jarayonda", "done": "🟢 Yakunlangan",
            "canceled": "🔴 Bekor"}

# qidiruv matni (admin id -> matn)
_conv_search: dict[int, str] = {}
_client_search: dict[int, str] = {}


def _period_start(period: str) -> str:
    n = now_local()
    if period == "today":
        return n.strftime("%Y-%m-%d 00:00:00")
    if period == "week":
        return (n - timedelta(days=n.weekday())).strftime("%Y-%m-%d 00:00:00")
    if period == "month":
        return n.strftime("%Y-%m-01 00:00:00")
    if period == "year":
        return n.strftime("%Y-01-01 00:00:00")
    return "0000-01-01 00:00:00"


_PLABEL = {"today": "Bugun", "week": "Joriy hafta", "month": "Joriy oy", "year": "Joriy yil"}


def _hm(dt) -> str:
    return (dt or "")[11:16]


def _dur(m) -> str:
    m = m or 0
    if m <= 0:
        return "—"
    if m < 1:
        return f"{round(m * 60)} soniya"
    if m < 60:
        return f"{round(m)} daqiqa"
    return f"{int(m // 60)} soat {round(m % 60)} daq"


def _name_link(name, uname, tg) -> str:
    name = name or "—"
    if uname:
        return f'<a href="https://t.me/{uname}">{name}</a>'
    return f'<a href="tg://user?id={tg}">{name}</a>'


async def _edit(call: CallbackQuery, text: str, markup):
    try:
        await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        await call.message.answer(text, reply_markup=markup, disable_web_page_preview=True)


def _period_row(base: str, active: str):
    out = []
    for p, t in (("today", "Bugun"), ("week", "Hafta"), ("month", "Oy"), ("year", "Yil")):
        out.append(InlineKeyboardButton(text=("• " + t if p == active else t),
                                        callback_data=f"{base}:{p}"))
    return out


# ==================== HISOBOTLAR MENYUSI ====================
@router.callback_query(F.data == "adm:reports")
async def reports_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🕘 Murojaatlar tarixi (yozishma)", callback_data="rep:conv:0"))
    b.row(InlineKeyboardButton(text="👥 Mijozlar ro'yxati", callback_data="rep:clients:0"))
    b.row(InlineKeyboardButton(text="👨‍⚕️ Operatorlar reytingi", callback_data="rep:ops:week"))
    b.row(InlineKeyboardButton(text="⏰ Soatlik yuklanma", callback_data="rep:hourly:week"))
    b.row(InlineKeyboardButton(text="📈 Davr hisoboti", callback_data="rep:period:week"))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    await _edit(call, "📚 <b>Hisobotlar</b>\n\nKerakli bo'limni tanlang:", b.as_markup())
    await call.answer()


# ==================== 1) MUROJAATLAR TARIXI ====================
@router.callback_query(F.data.startswith("rep:conv:"))
async def conv_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    await _show_conv(call, int(call.data.split(":")[2]))


async def _show_conv(call: CallbackQuery, page: int):
    search = _conv_search.get(call.from_user.id)
    rows, total = await q.orders_page(PAGE, page * PAGE, search)
    pages = max(1, (total + PAGE - 1) // PAGE)
    head = f"🕘 <b>Murojaatlar tarixi</b> — {total} ta"
    if search:
        head += f"\n🔍 Qidiruv: <code>{search}</code>"
    head += f"\n\nSahifa {page + 1}/{pages}. Yozishmani ko'rish uchun tanlang:"
    b = InlineKeyboardBuilder()
    for o in rows:
        nm = (o["full_name"] or "—")[:20]
        b.row(InlineKeyboardButton(
            text=f"{_ST.get(o['status'], '')} #{o['id']} · {nm} · {_hm(o['created_at'])}",
            callback_data=f"rep:cv:{o['id']}:{page}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"rep:conv:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"rep:conv:{page + 1}"))
    if nav:
        b.row(*nav)
    sr = [InlineKeyboardButton(text="🔍 Qidiruv", callback_data="rep:convsearch")]
    if search:
        sr.append(InlineKeyboardButton(text="❌ Tozalash", callback_data="rep:convclear"))
    b.row(*sr)
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, head, b.as_markup())
    await call.answer()


@router.callback_query(F.data == "rep:convsearch")
async def conv_search_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.rep_search_conv)
    await call.message.answer("🔍 Ism, telefon yoki #raqam yuboring:")
    await call.answer()


@router.callback_query(F.data == "rep:convclear")
async def conv_search_clear(call: CallbackQuery):
    _conv_search.pop(call.from_user.id, None)
    await _show_conv(call, 0)
    await call.answer("Tozalandi")


@router.message(AdminFlow.rep_search_conv)
async def conv_search_apply(message: Message, state: FSMContext):
    _conv_search[message.from_user.id] = message.text.strip()
    await state.clear()
    rows, total = await q.orders_page(PAGE, 0, message.text.strip())
    b = InlineKeyboardBuilder()
    for o in rows:
        nm = (o["full_name"] or "—")[:20]
        b.row(InlineKeyboardButton(
            text=f"{_ST.get(o['status'], '')} #{o['id']} · {nm} · {_hm(o['created_at'])}",
            callback_data=f"rep:cv:{o['id']}:0"))
    b.row(InlineKeyboardButton(text="❌ Tozalash", callback_data="rep:convclear"))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await message.answer(f"🔍 Natija: {total} ta topildi.", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("rep:cv:"))
async def conv_transcript(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    parts = call.data.split(":")
    oid, page = int(parts[2]), parts[3]
    back_tg = parts[4] if len(parts) > 4 else None
    order = await q.get_order(oid)
    if not order:
        await call.answer("Topilmadi", show_alert=True)
        return
    user = await q.get_user(order["user_id"])
    op = await q.get_operator(order["operator_id"]) if order["operator_id"] else None
    op_name = op["name"] if op else "Operator"
    uname = user["username"] if user and "username" in user.keys() else None

    header = (f"📋 <b>Murojaat #{oid}</b>\n"
              f"👤 {_name_link(user['full_name'] if user else '—', uname, order['user_id'])}"
              f" · {user['phone'] if user else '—'}\n"
              f"👨‍⚕️ Operator: {op_name if op else 'biriktirilmagan'}\n"
              f"🕐 {_hm(order['created_at'])}"
              + (f" → {_hm(order['closed_at'])}" if order['closed_at'] else "")
              + f" · Holat: {_ST_FULL.get(order['status'], order['status'])}")
    if order["rating"]:
        header += f"\n⭐ Baho: {order['rating']}"
        if order["feedback"]:
            header += f" — «{order['feedback']}»"

    msgs = await q.order_messages(oid)
    lines = []
    for m in msgs[-60:]:
        who = "👤 Mijoz" if m["sender"] == "client" else f"👨‍⚕️ {op_name}"
        body = m["text"] if m["text"] else _CT.get(m["content_type"], m["content_type"] or "—")
        lines.append(f"{_hm(m['created_at'])}  {who}: {body}")
    convo = "\n".join(lines) if lines else "(yozishma yo'q)"
    text = header + "\n\n──────── Yozishma ────────\n" + convo
    if len(text) > 3900:
        text = header + "\n\n──────── Yozishma (oxirgi qism) ────────\n" + convo[-3500:]

    b = InlineKeyboardBuilder()
    if back_tg:
        b.row(InlineKeyboardButton(text="🔙 Mijozga", callback_data=f"rep:cl:{back_tg}:0"))
    else:
        b.row(InlineKeyboardButton(text="🔙 Ro'yxatga", callback_data=f"rep:conv:{page}"))
    await _edit(call, text, b.as_markup())
    await call.answer()


# ==================== 2) MIJOZLAR RO'YXATI ====================
@router.callback_query(F.data.startswith("rep:clients:"))
async def clients_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    await _show_clients(call, int(call.data.split(":")[2]))


async def _show_clients(call: CallbackQuery, page: int):
    search = _client_search.get(call.from_user.id)
    rows, total = await q.users_page(PAGE, page * PAGE, search)
    pages = max(1, (total + PAGE - 1) // PAGE)
    head = f"👥 <b>Mijozlar</b> — {total} ta"
    if search:
        head += f"\n🔍 Qidiruv: <code>{search}</code>"
    head += f"\n\nSahifa {page + 1}/{pages}:"
    b = InlineKeyboardBuilder()
    for u in rows:
        nm = (u["full_name"] or "—")[:22]
        b.row(InlineKeyboardButton(text=f"{nm} · {u['cnt']} murojaat",
                                   callback_data=f"rep:cl:{u['telegram_id']}:{page}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"rep:clients:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"rep:clients:{page + 1}"))
    if nav:
        b.row(*nav)
    sr = [InlineKeyboardButton(text="🔍 Qidiruv", callback_data="rep:clsearch")]
    if search:
        sr.append(InlineKeyboardButton(text="❌ Tozalash", callback_data="rep:clclear"))
    b.row(*sr)
    _add_client_periods(b, "all")
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, head, b.as_markup())
    await call.answer()


def _add_client_periods(b: InlineKeyboardBuilder, active: str):
    b.row(InlineKeyboardButton(text=("• Barchasi" if active == "all" else "Barchasi"),
                               callback_data="rep:clients:0"))
    b.row(*[InlineKeyboardButton(text=("• " + t if p == active else t),
                                 callback_data=f"rep:cltop:{p}:0")
            for p, t in (("today", "Bugun"), ("week", "Hafta"), ("month", "Oy"), ("year", "Yil"))])


@router.callback_query(F.data.startswith("rep:cltop:"))
async def top_clients_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    _, _, period, page = call.data.split(":")
    page = int(page)
    rows, total = await q.top_clients(_period_start(period), PAGE, page * PAGE)
    pages = max(1, (total + PAGE - 1) // PAGE)
    head = (f"👥 <b>Eng ko'p murojaat qilganlar</b> — {_PLABEL[period]}\n"
            f"Jami mijoz: {total} · Sahifa {page + 1}/{pages}")
    b = InlineKeyboardBuilder()
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(rows):
        rank = medals[i] if page == 0 and i < 3 else f"{page * PAGE + i + 1}."
        nm = (u["full_name"] or "—")[:20]
        b.row(InlineKeyboardButton(text=f"{rank} {nm} · {u['cnt']} murojaat",
                                   callback_data=f"rep:cl:{u['telegram_id']}:0"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"rep:cltop:{period}:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"rep:cltop:{period}:{page + 1}"))
    if nav:
        b.row(*nav)
    _add_client_periods(b, period)
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, head, b.as_markup())
    await call.answer()


@router.callback_query(F.data == "rep:clsearch")
async def cl_search_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.rep_search_clients)
    await call.message.answer("🔍 Mijoz ismi yoki telefonini yuboring:")
    await call.answer()


@router.callback_query(F.data == "rep:clclear")
async def cl_search_clear(call: CallbackQuery):
    _client_search.pop(call.from_user.id, None)
    await _show_clients(call, 0)
    await call.answer("Tozalandi")


@router.message(AdminFlow.rep_search_clients)
async def cl_search_apply(message: Message, state: FSMContext):
    _client_search[message.from_user.id] = message.text.strip()
    await state.clear()
    rows, total = await q.users_page(PAGE, 0, message.text.strip())
    b = InlineKeyboardBuilder()
    for u in rows:
        nm = (u["full_name"] or "—")[:22]
        b.row(InlineKeyboardButton(text=f"{nm} · {u['cnt']} murojaat",
                                   callback_data=f"rep:cl:{u['telegram_id']}:0"))
    b.row(InlineKeyboardButton(text="❌ Tozalash", callback_data="rep:clclear"))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await message.answer(f"🔍 Natija: {total} ta topildi.", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("rep:cl:"))
async def client_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    parts = call.data.split(":")
    tg, page = int(parts[2]), parts[3]
    u = await q.user_full(tg)
    if not u:
        await call.answer("Topilmadi", show_alert=True)
        return
    uname = u["username"] if "username" in u.keys() else None
    orders = await q.orders_by_user(tg)
    done = sum(1 for o in orders if o["status"] == "done")
    text = (f"👤 <b>{_name_link(u['full_name'], uname, tg)}</b>\n"
            f"📞 {u['phone'] or '—'}\n"
            f"🏥 Filial: {u['branch'] or '—'}\n"
            f"🗓 Ro'yxatdan: {(u['registered_at'] or '—')[:10]}\n"
            f"💊 Murojaatlar: {len(orders)} (🟢 {done} yakunlangan)\n\n"
            f"Murojaatni tanlang — yozishmasi ochiladi:")
    b = InlineKeyboardBuilder()
    for o in orders[:20]:
        b.row(InlineKeyboardButton(
            text=f"{_ST.get(o['status'], '')} #{o['id']} · {(o['created_at'] or '')[:10]}",
            callback_data=f"rep:cv:{o['id']}:0:{tg}"))
    b.row(InlineKeyboardButton(text="🔙 Ro'yxatga", callback_data=f"rep:clients:{page}"))
    await _edit(call, text, b.as_markup())
    await call.answer()


# ==================== 3) OPERATORLAR REYTINGI ====================
@router.callback_query(F.data.startswith("rep:ops:"))
async def ops_report(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    parts = call.data.split(":")           # rep:ops:{period}[:{sort}]
    period = parts[2]
    sort = parts[3] if len(parts) > 3 else "done"
    rows = await q.operators_report(_period_start(period))
    _SORTERS = {
        "done": (lambda x: x["done"], True),
        "accepted": (lambda x: x["accepted"], True),
        "rating": (lambda x: x["rating"], True),
        "resp": (lambda x: x["resp"] if x["resp"] > 0 else 1e9, False),  # tez javob = kichik
    }
    keyf, rev = _SORTERS.get(sort, _SORTERS["done"])
    rows.sort(key=keyf, reverse=rev)
    slabel = {"done": "ko'p yakun", "accepted": "ko'p qabul",
              "rating": "yuqori baho", "resp": "tez javob"}[sort]
    lines = [f"👨‍⚕️ <b>Operatorlar reytingi</b> — {_PLABEL[period]}",
             f"<i>Saralash: {slabel}</i>\n"]
    if not any(r["accepted"] or r["done"] for r in rows):
        lines.append("(bu davrda ma'lumot yo'q)")
    medals = ["🥇", "🥈", "🥉"]
    i = 0
    for r in rows:
        if not (r["accepted"] or r["done"]):
            continue
        i += 1
        place = medals[i - 1] if i <= 3 else f"{i}."
        star = f" ⭐{r['rating']}" if r["rating"] else ""
        lines.append(f"{place} <b>{r['name']}</b>{star}\n"
                     f"    📥 {r['accepted']} qabul · 🟢 {r['done']} yakun\n"
                     f"    ⏱ javob {_dur(r['resp'])} · ✅ yakunlash {_dur(r['resol'])}")
    b = InlineKeyboardBuilder()
    # davr (saralashni saqlaydi)
    b.row(*[InlineKeyboardButton(text=("• " + t if p == period else t),
                                 callback_data=f"rep:ops:{p}:{sort}")
            for p, t in (("today", "Bugun"), ("week", "Hafta"), ("month", "Oy"), ("year", "Yil"))])
    # saralash (davrni saqlaydi)
    b.row(*[InlineKeyboardButton(text=("• " + t if s == sort else t),
                                 callback_data=f"rep:ops:{period}:{s}")
            for s, t in (("done", "Ko'p yakun"), ("accepted", "Ko'p qabul"),
                         ("rating", "Baho"), ("resp", "Tez javob"))])
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, "\n".join(lines), b.as_markup())
    await call.answer()


# ==================== 4) SOATLIK YUKLANMA ====================
@router.callback_query(F.data.startswith("rep:hourly:"))
async def hourly_report(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    period = call.data.split(":")[2]
    data = await q.hourly_load(_period_start(period))
    plabel = _PLABEL[period]
    mx = max(data.values()) if data else 0
    lines = [f"⏰ <b>Soatlik yuklanma</b> — {plabel}\n"]
    if mx == 0:
        lines.append("(bu davrda ma'lumot yo'q)")
    else:
        peak = max(data, key=data.get)
        for h in range(24):
            c = data.get(h, 0)
            bar = "█" * round((c / mx) * 12) if c else ""
            mark = " ⬅️ eng band" if h == peak else ""
            if c or (6 <= h <= 23):
                lines.append(f"{h:02d}:00 {bar} {c}{mark}")
    b = InlineKeyboardBuilder()
    b.row(*_period_row("rep:hourly", period))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, "\n".join(lines), b.as_markup())
    await call.answer()


# ==================== 5) DAVR HISOBOTI ====================
@router.callback_query(F.data.startswith("rep:period:"))
async def period_report(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    period = call.data.split(":")[2]
    r = await q.period_report(_period_start(period))
    plabel = _PLABEL[period]
    lines = [
        f"📈 <b>Davr hisoboti</b> — {plabel}\n",
        f"Jami murojaatlar: <b>{r['total']}</b>",
        f"🟡 Yangi: {r['new']}   🔵 Jarayonda: {r['prog']}",
        f"🟢 Yakunlangan: {r['done']}   🔴 Bekor: {r['canceled']}",
        f"⏱ O'rtacha javob: {_dur(r['resp'])}   ✅ Yakunlash: {_dur(r['resol'])}\n",
        "<b>Kunlar bo'yicha:</b>",
    ]
    if r["days"]:
        for d in r["days"]:
            lines.append(f"{d[0]}: {d[1]} ta · 🟢 {d[2]}")
    else:
        lines.append("(ma'lumot yo'q)")
    b = InlineKeyboardBuilder()
    b.row(*_period_row("rep:period", period))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:reports"))
    await _edit(call, "\n".join(lines), b.as_markup())
    await call.answer()
