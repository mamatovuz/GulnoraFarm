"""Gulnora Farm — Telegram boti. Kirish nuqtasi."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from database import queries as q
import keyboards as kb
import botreg
from handlers import registration, admin, operator, menu, order, unfinished
from middlewares import ActivityMiddleware, ClientBotOnly

logging.basicConfig(level=logging.INFO, format="%(message)s")
# aiogram ichki loglarini o'chiramiz — terminal toza bo'lsin
for name in ("aiogram", "aiogram.event", "aiogram.dispatcher", "aiogram.middlewares",
             "aiohttp", "asyncio"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
logger = logging.getLogger("bot")


async def main():
    await init_db()

    # Operator tugmalari matnini bazadan yuklaymiz (admin o'zgartirgan bo'lsa)
    overrides = {}
    for key in list(kb.OP_BTN.keys()):
        val = await q.get_setting(f"opbtn_{key}", "")
        if val:
            overrides[key] = val
    kb.apply_op_buttons(overrides)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Bitta dispatcher: asosiy bot ham, operator botlari ham shu yerga uzatadi.
    dp = Dispatcher(storage=MemoryStorage())

    # Mijozga oid routerlar FAQAT asosiy botda ishlasin (operator botlarida o'tkazib yuboriladi).
    # Shunda: asosiy botda /operator ham ishlaydi, operator botida esa mijoz menyusi chiqmaydi.
    for r in (registration.router, admin.router, menu.router, order.router):
        r.message.outer_middleware(ClientBotOnly())
        r.callback_query.outer_middleware(ClientBotOnly())
        r.channel_post.outer_middleware(ClientBotOnly())

    # Operator faolligini kuzatish
    dp.message.middleware(ActivityMiddleware())
    dp.callback_query.middleware(ActivityMiddleware())

    # Tartib muhim: /start -> registration (mijoz), /operator -> operator
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(operator.router)
    dp.include_router(unfinished.build_router())
    dp.include_router(menu.router)
    dp.include_router(order.router)

    me = await bot.get_me()
    logger.info("✅ Bot ishga tushdi: @%s", me.username)
    await bot.delete_webhook(drop_pending_updates=True)

    # Registr: mijoz boti + operator botlari shu dispatcherga uzatadi
    botreg.set_client_bot(bot)
    botreg.set_operator_dp(dp)
    try:
        await botreg.load_all(await q.list_operator_bots())
    except Exception as e:
        logger.info("Operator botlarini yuklashda xato: %s", e)

    # Operator ish vaqti tugaganda avtomatik chiqaruvchi fon vazifasi
    asyncio.create_task(operator.op_workhours_loop(bot))
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("🛑 Bot to'xtatildi.")
