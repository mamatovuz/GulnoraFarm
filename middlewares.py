"""Operator faolligini kuzatuvchi middleware (avto-logout uchun)."""
from aiogram import BaseMiddleware
from aiogram.types import Update

from database import queries as q


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
