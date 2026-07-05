"""Gulnora Farm — Telegram boti. Kirish nuqtasi."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, WEBAPP_PORT, WEBAPP_URL
from database.db import init_db
from database import queries as q
import keyboards as kb
import botreg
from handlers import registration, admin, operator, menu, order, unfinished, reports
from middlewares import ClientBotOnly, PendingBranchGate

logging.basicConfig(level=logging.INFO, format="%(message)s")
# aiogram ichki loglarini o'chiramiz — terminal toza bo'lsin
for name in ("aiogram", "aiogram.event", "aiogram.dispatcher", "aiogram.middlewares",
             "aiohttp", "asyncio"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
logger = logging.getLogger("bot")


async def backup_loop(bot):
    """Har kuni (03:00 dan keyin) bazani admin botiga yuboradi — eng katta sug'urta."""
    from aiogram.types import FSInputFile
    from config import DB_PATH, ADMIN_IDS, now_local
    while True:
        await asyncio.sleep(1800)
        try:
            n = now_local()
            today = n.strftime("%Y-%m-%d")
            if n.hour >= 3 and (await q.get_setting("last_backup", "")) != today:
                await q.checkpoint_wal()   # WAL'ni faylga o'tkazamiz — to'liq nusxa
                f = FSInputFile(DB_PATH, filename=f"zaxira_{n.strftime('%Y%m%d')}.db")
                for aid in ADMIN_IDS:
                    try:
                        await bot.send_document(
                            aid, f, caption=f"🗄 Kunlik baza zaxirasi — {today}\n"
                                            f"Bu faylni saqlab qo'ying: baza buzilsa shu orqali tiklanadi.")
                    except Exception:
                        pass
                await q.set_setting("last_backup", today)
        except Exception:
            pass


async def rate_remind_loop(bot):
    """Yakunlangandan 24 soat o'tib baholanmagan murojaatlar uchun bir marta eslatma."""
    import keyboards as kb2
    import locales as loc2
    from datetime import timedelta
    from config import now_local
    while True:
        await asyncio.sleep(1800)
        try:
            n = now_local()
            lo = (n - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            hi = (n - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            for r in await q.rate_remind_candidates(lo, hi):
                await q.mark_rate_reminded(r["id"])
                clang = await q.get_lang(r["user_id"])
                try:
                    await bot.send_message(
                        r["user_id"],
                        ("⭐ Murojaatingiz (#%d) bo'yicha xizmatni baholab qo'ysangiz — "
                         "biz uchun juda muhim!" % r["id"]) if clang != "ru" else
                        ("⭐ Пожалуйста, оцените обслуживание по обращению #%d — "
                         "это важно для нас!" % r["id"]),
                        reply_markup=kb2.rating_kb(r["id"]))
                except Exception:
                    pass
        except Exception:
            pass


async def sched_bc_loop(bot):
    """Rejalashtirilgan ommaviy xabarlarni vaqti kelganda yuboradi."""
    import base64
    import html as _h
    from aiogram.types import BufferedInputFile
    from config import ADMIN_IDS
    while True:
        await asyncio.sleep(60)
        try:
            for b in await q.due_sched_bc(q.now()):
                media = b["media"]
                await q.mark_sched_bc_done(b["id"])
                if b["target"] == "active":
                    users = await q.all_users(only_active=True)
                elif b["target"] == "branch" and b["branch_id"]:
                    users = await q.all_users(branch_id=b["branch_id"])
                else:
                    users = await q.all_users()
                raw = None
                if media:
                    try:
                        raw = base64.b64decode(str(media).split(",")[-1])
                    except Exception:
                        raw = None
                sent = failed = 0
                fid = None
                for u in users:
                    try:
                        if raw:
                            if fid:
                                await bot.send_photo(u["telegram_id"], fid,
                                                     caption=_h.escape(b["text"] or ""))
                            else:
                                m = await bot.send_photo(u["telegram_id"],
                                                         BufferedInputFile(raw, "elon.jpg"),
                                                         caption=_h.escape(b["text"] or ""))
                                fid = m.photo[-1].file_id
                        else:
                            await bot.send_message(u["telegram_id"], _h.escape(b["text"] or ""))
                        sent += 1
                    except Exception:
                        failed += 1
                for aid in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            aid, f"📣 Rejalashtirilgan e'lon yuborildi ({b['send_at'][:16]})\n"
                                 f"✅ {sent} ta · ❌ {failed} ta")
                    except Exception:
                        pass
        except Exception:
            pass


async def monthly_op_report_loop(bot):
    """Har oy 1-sanasida (09:00 dan keyin) har bir operatorga o'tgan oy natijalarini yuboradi."""
    from datetime import timedelta
    from config import now_local
    months = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
              "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
    while True:
        await asyncio.sleep(1800)
        try:
            n = now_local()
            key = n.strftime("%Y-%m")
            if n.day == 1 and n.hour >= 9 and (await q.get_setting("last_monthly_op", "")) != key:
                b_end = n.replace(day=1).strftime("%Y-%m-%d 00:00:00")
                prev = (n.replace(day=1) - timedelta(days=1))
                a_start = prev.replace(day=1).strftime("%Y-%m-%d 00:00:00")
                rows = await q.monthly_op_stats(a_start, b_end)
                total_ops = len(rows)
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for i, r in enumerate(rows, 1):
                    if not r["telegram_id"]:
                        continue
                    ob = (botreg.get_operator_bot(r["bot_id"]) if r["bot_id"] else bot) or bot
                    place = medals.get(i, f"{i}-o'rin")
                    text = (f"📊 <b>Oylik natijangiz — {months[prev.month]}</b>\n\n"
                            f"🟢 Yakunlangan murojaatlar: <b>{r['done'] or 0}</b>\n"
                            f"⭐ O'rtacha baho: {r['rating'] or '—'}\n"
                            f"🏆 Reyting: {place} ({total_ops} operator ichida)\n\n"
                            f"Yangi oyda omad, {r['name']}! 💪")
                    try:
                        await ob.send_message(r["telegram_id"], text)
                    except Exception:
                        pass
                await q.set_setting("last_monthly_op", key)
        except Exception:
            pass


async def reminders_loop(bot):
    """Operator eslatmalari: vaqti kelganda operatorga (o'z boti orqali) xabar beradi."""
    while True:
        await asyncio.sleep(60)
        try:
            for r in await q.due_reminders(q.now()):
                await q.mark_reminder_done(r["id"])
                op = await q.get_operator(r["operator_id"])
                if not op or not op["telegram_id"]:
                    continue
                ob = (botreg.get_operator_bot(op["bot_id"]) if op["bot_id"] else bot) or bot
                text = (f"⏰ <b>Eslatma</b> — murojaat #{r['order_id']}"
                        f" ({r['full_name'] or 'mijoz'})"
                        + (f"\n📝 {r['note']}" if r["note"] else ""))
                try:
                    await ob.send_message(op["telegram_id"], text)
                except Exception:
                    pass
        except Exception:
            pass


async def weekly_report_loop(bot):
    """Har dushanba 09:00 da adminlarga o'tgan hafta hisobotini yuboradi."""
    from datetime import timedelta
    from config import now_local, ADMIN_IDS
    while True:
        try:
            n = now_local()
            if n.weekday() == 0 and n.hour >= 9:
                wk = f"{n.isocalendar()[0]}-{n.isocalendar()[1]}"
                if await q.get_setting("last_weekly_report", "") != wk:
                    since = (n - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
                    r = await q.period_report(since)
                    ops = await q.operators_report(since)
                    ops.sort(key=lambda x: x["done"], reverse=True)
                    medals = ["🥇", "🥈", "🥉", "4.", "5."]
                    top = "\n".join(f"{medals[i]} {o['name']} — {o['done']} yakun"
                                    for i, o in enumerate(ops[:5]) if o["done"])
                    text = ("📬 <b>Haftalik hisobot</b> (o'tgan 7 kun)\n\n"
                            f"💊 Jami murojaatlar: <b>{r['total']}</b>\n"
                            f"🟢 Yakunlangan: {r['done']}   🔴 Bekor: {r['canceled']}\n"
                            f"⏱ O'rtacha javob: {round(r['resp'])} daqiqa\n\n"
                            f"<b>Top operatorlar:</b>\n{top or '—'}")
                    for aid in ADMIN_IDS:
                        try:
                            await bot.send_message(aid, text)
                        except Exception:
                            pass
                    await q.set_setting("last_weekly_report", wk)
        except Exception:
            pass
        await asyncio.sleep(1800)


async def main():
    await init_db()

    # CRM'dan qo'shilgan adminlarni keshga yuklaymiz
    from utils import refresh_admins
    await refresh_admins()

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
    for r in (registration.router, admin.router, reports.router, menu.router, order.router):
        r.message.outer_middleware(ClientBotOnly())
        r.callback_query.outer_middleware(ClientBotOnly())
        r.channel_post.outer_middleware(ClientBotOnly())

    # Majburiy filial tanlash gate'i (faqat asosiy bot message'lariga, FSM tashqarisida)
    dp.message.outer_middleware(PendingBranchGate())

    # Tartib muhim: /start -> registration (mijoz), /operator -> operator
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(reports.router)
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
    # Haftalik avto-hisobot (dushanba 09:00)
    asyncio.create_task(weekly_report_loop(bot))
    # Operator eslatmalari
    asyncio.create_task(reminders_loop(bot))
    # Kunlik baza zaxirasi (admin botiga)
    asyncio.create_task(backup_loop(bot))
    # Baholash eslatmasi (24 soatdan keyin, bir marta)
    asyncio.create_task(rate_remind_loop(bot))
    # Oylik operator hisoboti (har oy 1-sanasida)
    asyncio.create_task(monthly_op_report_loop(bot))
    # Rejalashtirilgan ommaviy xabarlar
    asyncio.create_task(sched_bc_loop(bot))
    # Mini app (CRM) web serveri — bot bilan bir jarayonda
    try:
        import webapp
        asyncio.create_task(webapp.start(WEBAPP_PORT))
    except Exception as e:
        logger.info("Mini app serverini ishga tushirishda xato: %s", e)
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("🛑 Bot to'xtatildi.")
