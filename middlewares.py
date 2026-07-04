"""Middleware'lar: operator faolligi + mijoz handlerlarini faqat asosiy botda ishlatish."""
from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.dispatcher.event.bases import UNHANDLED

import botreg
from database import queries as q


class ClientBotOnly(BaseMiddleware):
    """Outer middleware: mijozga oid routerlar (registration/admin/menu/order)
    FAQAT asosiy (mijoz) botda ishlasin. Operator botlarida bu routerlar o'tkazib yuboriladi —
    shunda operator botida mijoz menyusi/ro'yxatdan o'tish chiqmaydi, lekin asosiy botda /operator ham ishlaydi.

    MUHIM: o'tkazib yuborishda UNHANDLED qaytariladi — shunda aiogram keyingi routerni (operator)
    sinab ko'radi. None qaytarilsa, aiogram 'ishlandi' deb propagatsiyani to'xtatadi."""

    async def __call__(self, handler, event, data):
        bot = data.get("bot")
        if bot is not None and botreg.bot_id_of(bot) is not None:
            return UNHANDLED  # operator boti — bu routerni o'tkazib, keyingisiga o'tamiz
        return await handler(event, data)


class PendingBranchGate(BaseMiddleware):
    """Majburiy filial tanlash gate'i (faqat asosiy bot, message'lar uchun).

    Operator 'filialtanlatish' bosganda mijozga filial tanlash so'raladi va
    users.pending_branch_order o'rnatiladi. Shundan keyin mijoz FSM oqimida
    bo'lmagan holatda (erkin menyu) HECH QANDAY amal bajara olmaydi — har safar
    'Avval filial tanlang' + filial tanlash oynasi qayta chiqadi. Inline tugmalar
    (callback) va davom etayotgan FSM oqimlari (ro'yxatdan o'tish, eng yaqin filial)
    bloklanmaydi."""

    async def __call__(self, handler, event, data):
        bot = data.get("bot")
        if bot is not None and botreg.bot_id_of(bot) is not None:
            return await handler(event, data)      # operator boti — tegmaymiz
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        # FSM oqimida bo'lsa (ro'yxat/eng yaqin/murojaat) — o'z gate'lari bor, o'tkazamiz
        state = data.get("state")
        if state is not None:
            try:
                if await state.get_state() is not None:
                    return await handler(event, data)
            except Exception:
                pass
        pend = await q.get_pending_branch(user.id)
        if not pend:
            return await handler(event, data)
        po = await q.get_order(pend)
        if not po or po["status"] not in ("new", "in_progress"):
            await q.clear_pending_branch(user.id)  # murojaat yopilgan — gate ochiladi
            return await handler(event, data)
        # Bloklaymiz: filial tanlash oynasini qayta chiqaramiz
        import keyboards as kb
        import locales as loc
        lang = await q.get_lang(user.id)
        regions = await q.list_regions()
        markup = (kb.regions_choose_kb(regions, lang, op_order=pend) if len(regions) > 1
                  else kb.op_ask_branch_kb(await q.list_branches(), pend, lang))
        try:
            await event.answer(loc.t("must_select_branch", lang), reply_markup=markup)
        except Exception:
            pass
        return  # propagatsiya to'xtaydi — boshqa handler ishlamaydi


class ActivityMiddleware(BaseMiddleware):
    """Har bir xabar/tugma bosilishida login qilgan operatorning faollik vaqtini yangilaydi."""

    async def __call__(self, handler, event, data):
        try:
            user = data.get("event_from_user")
            if user is not None:
                await q.touch_operator(user.id)
        except Exception:
            pass
        return await handler(event, data)
