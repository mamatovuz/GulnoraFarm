"""Middleware'lar: operator faolligi + mijoz handlerlarini faqat asosiy botda ishlatish."""
from aiogram import BaseMiddleware
from aiogram.types import Update

import botreg
from database import queries as q


class ClientBotOnly(BaseMiddleware):
    """Outer middleware: mijozga oid routerlar (registration/admin/menu/order)
    FAQAT asosiy (mijoz) botda ishlasin. Operator botlarida bu routerlar o'tkazib yuboriladi —
    shunda operator botida mijoz menyusi/ro'yxatdan o'tish chiqmaydi, lekin asosiy botda /operator ham ishlaydi."""

    async def __call__(self, handler, event, data):
        bot = data.get("bot")
        if bot is not None and botreg.bot_id_of(bot) is not None:
            return  # operator boti — bu routerni o'tkazib yuboramiz (keyingi router sinaydi)
        return await handler(event, data)


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
