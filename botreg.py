"""Operator botlari registri va dinamik polling (bir nechta operator boti bitta jarayonda)."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError

logger = logging.getLogger("bot")

client_bot: Bot | None = None          # asosiy (mijoz) bot — kanal va mijozga yozish uchun
operator_dp: Dispatcher | None = None  # barcha operator botlari uchun umumiy dispatcher
_op_bots: dict[int, Bot] = {}          # bot_id -> Bot
_tasks: dict[int, asyncio.Task] = {}   # bot_id -> polling task


def set_client_bot(bot: Bot):
    global client_bot
    client_bot = bot


def set_operator_dp(dp: Dispatcher):
    global operator_dp
    operator_dp = dp


def get_operator_bot(bot_id):
    return _op_bots.get(bot_id)


def bot_id_of(bot: Bot):
    """Berilgan Bot obyekti qaysi operator botiga tegishli (None = asosiy/mijoz bot)."""
    if client_bot and bot.id == client_bot.id:
        return None
    for bid, b in _op_bots.items():
        if b.id == bot.id:
            return bid
    return None


def all_operator_bots() -> dict:
    return dict(_op_bots)


def make_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _poll(bot: Bot, bot_id: int):
    """Bitta operator boti uchun polling — umumiy operator_dp ga uzatadi."""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    allowed = operator_dp.resolve_used_update_types() if operator_dp else None
    offset = None
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=25, allowed_updates=allowed)
            for u in updates:
                offset = u.update_id + 1
                if operator_dp:
                    await operator_dp.feed_update(bot, u)
        except asyncio.CancelledError:
            break
        except TelegramConflictError:
            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(3)


async def start_operator_bot(bot_id: int, token: str):
    """Operator botini ishga tushiradi (avval to'xtatib, qaytadan)."""
    await stop_operator_bot(bot_id)
    bot = make_bot(token)
    _op_bots[bot_id] = bot
    _tasks[bot_id] = asyncio.create_task(_poll(bot, bot_id))
    logger.info("🤖 Operator boti ulandi: id=%s", bot_id)


async def stop_operator_bot(bot_id: int):
    task = _tasks.pop(bot_id, None)
    if task:
        task.cancel()
    bot = _op_bots.pop(bot_id, None)
    if bot:
        try:
            await bot.session.close()
        except Exception:
            pass


async def load_all(rows):
    """Bazadagi barcha yoqilgan operator botlarini ishga tushiradi."""
    for r in rows:
        if r["enabled"]:
            await start_operator_bot(r["id"], r["token"])
