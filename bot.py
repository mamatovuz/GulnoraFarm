"""Gulnora Farm — Telegram boti. Kirish nuqtasi."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from handlers import registration, admin, operator, menu, order

logging.basicConfig(level=logging.INFO, format="%(message)s")
# aiogram ichki loglarini o'chiramiz — terminal toza bo'lsin
for name in ("aiogram", "aiogram.event", "aiogram.dispatcher", "aiogram.middlewares",
             "aiohttp", "asyncio"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
logger = logging.getLogger("bot")


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Routerlar tartibi muhim: avval aniqroq (FSM/rol asosidagi) handlerlar
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(operator.router)
    dp.include_router(menu.router)
    dp.include_router(order.router)

    me = await bot.get_me()
    logger.info("✅ Bot ishga tushdi: @%s", me.username)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("🛑 Bot to'xtatildi.")
