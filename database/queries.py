"""Barcha ma'lumotlar bazasi amallari."""
import hashlib
from datetime import timedelta
from config import now_local
from database.db import get_db


def now() -> str:
    return now_local().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str) -> str:
    return hashlib.sha256(("gulnorafarm_salt_" + password).encode()).hexdigest()


def _median(vals) -> float:
    """Median — chetga chiqqan qiymatlar (tunda qolgan, kunlar o'tib yopilgan murojaatlar)
    o'rtachani buzmasligi uchun. Real ko'rsatkich shu."""
    vals = sorted(v for v in vals if v is not None and v >= 0)
    if not vals:
        return 0
    n = len(vals)
    m = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return round(m, 1)


# ============================ USERS ============================
async def get_user(telegram_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    return await cur.fetchone()


async def create_user(telegram_id: int, full_name: str, phone: str):
    """Ism/telefonni saqlaydi. Mavjud foydalanuvchining tili va filiali saqlanib qoladi."""
    db = await get_db()
    await db.execute(
        "INSERT INTO users (telegram_id, full_name, phone, registered_at, status) "
        "VALUES (?, ?, ?, ?, 'active') "
        "ON CONFLICT(telegram_id) DO UPDATE SET "
        "full_name = excluded.full_name, phone = excluded.phone, registered_at = excluded.registered_at",
        (telegram_id, full_name, phone, now()),
    )
    await db.commit()


async def set_user_lang(telegram_id: int, lang: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO users (telegram_id, lang, registered_at, status) "
        "VALUES (?, ?, ?, 'active') "
        "ON CONFLICT(telegram_id) DO UPDATE SET lang = excluded.lang",
        (telegram_id, lang, now()),
    )
    await db.commit()


async def get_lang(telegram_id: int) -> str:
    db = await get_db()
    cur = await db.execute("SELECT lang FROM users WHERE telegram_id = ?", (telegram_id,))
    row = await cur.fetchone()
    return (row["lang"] if row and row["lang"] else "uz")


async def set_user_username(telegram_id: int, username):
    if not username:
        return
    db = await get_db()
    await db.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
    await db.commit()


async def set_user_branch(telegram_id: int, branch_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET branch_id = ? WHERE telegram_id = ?", (branch_id, telegram_id))
    await db.commit()


async def set_user_active_order(telegram_id: int, order_id):
    db = await get_db()
    await db.execute(
        "UPDATE users SET active_order_id = ? WHERE telegram_id = ?", (order_id, telegram_id)
    )
    await db.commit()


async def all_users(branch_id=None, only_active=False):
    db = await get_db()
    q = "SELECT * FROM users WHERE 1=1"
    params = []
    if branch_id:
        q += " AND branch_id = ?"
        params.append(branch_id)
    if only_active:
        q += " AND status = 'active'"
    cur = await db.execute(q, params)
    return await cur.fetchall()


async def set_user_status(telegram_id: int, status: str):
    db = await get_db()
    await db.execute("UPDATE users SET status = ? WHERE telegram_id = ?", (status, telegram_id))
    await db.commit()


# ============================ BRANCHES ============================
async def list_branches():
    db = await get_db()
    cur = await db.execute("SELECT * FROM branches ORDER BY id")
    return await cur.fetchall()


async def get_branch(branch_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM branches WHERE id = ?", (branch_id,))
    return await cur.fetchone()


async def add_branch(name, address, phone, lat=None, lon=None, photo_file_id=None,
                     open_time="08:00", close_time="23:00"):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO branches (name, address, phone, lat, lon, photo_file_id, open_time, close_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, address, phone, lat, lon, photo_file_id, open_time, close_time),
    )
    await db.commit()
    return cur.lastrowid


async def update_branch(branch_id, field, value):
    db = await get_db()
    await db.execute(f"UPDATE branches SET {field} = ? WHERE id = ?", (value, branch_id))
    await db.commit()


async def update_branch_location(branch_id, lat, lon):
    db = await get_db()
    await db.execute("UPDATE branches SET lat = ?, lon = ? WHERE id = ?", (lat, lon, branch_id))
    await db.commit()


async def delete_branch(branch_id):
    db = await get_db()
    await db.execute("DELETE FROM branches WHERE id = ?", (branch_id,))
    # Bu filialni tanlagan foydalanuvchilarni qayta tanlashga majburlaymiz
    await db.execute("UPDATE users SET branch_id = NULL WHERE branch_id = ?", (branch_id,))
    await db.commit()


# ============================ ORDERS ============================
async def create_order(user_id, branch_id, content_type):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO orders (user_id, branch_id, created_at, status, content_type) "
        "VALUES (?, ?, ?, 'new', ?)",
        (user_id, branch_id, now(), content_type),
    )
    await db.commit()
    oid = cur.lastrowid
    await log_status(oid, None, "new", f"client:{user_id}")
    return oid


async def get_order(order_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    return await cur.fetchone()


async def set_order_status(order_id, status, changed_by):
    db = await get_db()
    cur = await db.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    row = await cur.fetchone()
    old = row["status"] if row else None
    closed = now() if status in ("done", "canceled") else None
    if closed:
        await db.execute("UPDATE orders SET status = ?, closed_at = ? WHERE id = ?",
                         (status, closed, order_id))
    else:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    await db.commit()
    await log_status(order_id, old, status, changed_by)


async def assign_order(order_id, operator_id):
    db = await get_db()
    await db.execute("UPDATE orders SET operator_id = ? WHERE id = ?", (operator_id, order_id))
    await db.commit()


async def claim_order(order_id, operator_id):
    """ATOMAR qabul: faqat status='new' bo'lsa operatorga biriktiradi va 'in_progress' qiladi.
    True = shu operator yutdi; False = kimdir oldin olib bo'lgan."""
    db = await get_db()
    cur = await db.execute(
        "UPDATE orders SET status='in_progress', operator_id=? WHERE id=? AND status='new'",
        (operator_id, order_id))
    await db.commit()
    if cur.rowcount and cur.rowcount > 0:
        await log_status(order_id, "new", "in_progress", f"operator:{operator_id}")
        return True
    return False


async def set_order_branch(order_id, branch_id):
    db = await get_db()
    await db.execute("UPDATE orders SET branch_id = ? WHERE id = ?", (branch_id, order_id))
    await db.commit()


async def set_order_group_msg(order_id, msg_id):
    db = await get_db()
    await db.execute("UPDATE orders SET group_msg_id = ? WHERE id = ?", (msg_id, order_id))
    await db.commit()


async def set_order_bill(order_id, bill, bill_photo=None):
    db = await get_db()
    await db.execute("UPDATE orders SET bill = ?, bill_photo = ? WHERE id = ?",
                     (bill, bill_photo, order_id))
    await db.commit()


async def set_order_rating(order_id, rating):
    db = await get_db()
    await db.execute("UPDATE orders SET rating = ? WHERE id = ?", (rating, order_id))
    await db.commit()


async def set_order_feedback(order_id, feedback):
    db = await get_db()
    await db.execute("UPDATE orders SET feedback = ? WHERE id = ?", (feedback, order_id))
    await db.commit()


async def orders_by_user(user_id):
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user_id,)
    )
    return await cur.fetchall()


async def unfinished_orders():
    """Yakunlanmagan (yangi yoki jarayonda) murojaatlar — eng eskisi tepada."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.user_id, o.status, o.created_at, o.operator_id, o.content_type, "
        "u.full_name, u.phone, u.username, b.name AS branch, op.name AS operator "
        "FROM orders o "
        "LEFT JOIN users u ON u.telegram_id = o.user_id "
        "LEFT JOIN branches b ON b.id = o.branch_id "
        "LEFT JOIN operators op ON op.id = o.operator_id "
        "WHERE o.status IN ('new','in_progress') "
        "ORDER BY o.created_at ASC")
    return await cur.fetchall()


async def orders_by_operator(operator_id):
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, u.full_name, o.status, o.created_at, o.rating "
        "FROM orders o LEFT JOIN users u ON u.telegram_id = o.user_id "
        "WHERE o.operator_id = ? ORDER BY o.id DESC", (operator_id,))
    return await cur.fetchall()


async def orders_by_status(status, operator_id=None):
    db = await get_db()
    if operator_id is not None:
        cur = await db.execute(
            "SELECT * FROM orders WHERE status = ? AND operator_id = ? ORDER BY id DESC",
            (status, operator_id),
        )
    else:
        cur = await db.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,))
    return await cur.fetchall()


async def log_status(order_id, old, new, changed_by):
    db = await get_db()
    await db.execute(
        "INSERT INTO status_log (order_id, old_status, new_status, changed_by, changed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (order_id, old, new, changed_by, now()),
    )
    await db.commit()


# ============================ MESSAGES (proxy-chat) ============================
async def add_message(order_id, sender, content_type, text=None, file_id=None, tg_msg_id=None,
                      client_msg_id=None):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO messages (order_id, sender, content_type, text, file_id, tg_msg_id, "
        "client_msg_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (order_id, sender, content_type, text, file_id, tg_msg_id, client_msg_id, now()),
    )
    await db.commit()
    return cur.lastrowid


async def get_message(mid):
    db = await get_db()
    cur = await db.execute("SELECT * FROM messages WHERE id = ?", (mid,))
    return await cur.fetchone()


async def set_message_client_id(mid, client_msg_id):
    db = await get_db()
    await db.execute("UPDATE messages SET client_msg_id = ? WHERE id = ?", (client_msg_id, mid))
    await db.commit()


async def update_message_text(mid, text):
    db = await get_db()
    await db.execute("UPDATE messages SET text = ? WHERE id = ?", (text, mid))
    await db.commit()


async def delete_message_row(mid):
    db = await get_db()
    await db.execute("DELETE FROM messages WHERE id = ?", (mid,))
    await db.commit()


# ============================ ESLATMALAR ============================
async def add_reminder(operator_id, order_id, remind_at, note=""):
    db = await get_db()
    await db.execute(
        "INSERT INTO reminders (operator_id, order_id, remind_at, note) VALUES (?, ?, ?, ?)",
        (operator_id, order_id, remind_at, note))
    await db.commit()


async def due_reminders(now_str):
    db = await get_db()
    cur = await db.execute(
        "SELECT r.*, u.full_name FROM reminders r "
        "LEFT JOIN orders o ON o.id = r.order_id "
        "LEFT JOIN users u ON u.telegram_id = o.user_id "
        "WHERE r.done = 0 AND r.remind_at <= ?", (now_str,))
    return await cur.fetchall()


async def mark_reminder_done(rid):
    db = await get_db()
    await db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))
    await db.commit()


# ============================ MIJOZNI TO'LIQ O'CHIRISH ============================
async def delete_client_full(tg):
    """Mijozning BARCHA ma'lumotlarini o'chiradi: profil, murojaatlar, yozishmalar, izohlar."""
    db = await get_db()
    cur = await db.execute("SELECT id FROM orders WHERE user_id = ?", (tg,))
    oids = [r[0] for r in await cur.fetchall()]
    if oids:
        ph = ",".join("?" * len(oids))
        await db.execute(f"DELETE FROM messages WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM msg_links WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM order_notifs WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM status_log WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM hidden_chats WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM reminders WHERE order_id IN ({ph})", oids)
        await db.execute(f"DELETE FROM orders WHERE id IN ({ph})", oids)
        await db.execute("UPDATE operators SET active_order_id = NULL "
                         f"WHERE active_order_id IN ({ph})", oids)
    await db.execute("DELETE FROM client_notes WHERE user_id = ?", (tg,))
    await db.execute("DELETE FROM users WHERE telegram_id = ?", (tg,))
    await db.commit()
    return len(oids)


async def branch_counts(since):
    """Filial kesimida murojaatlar soni (davr ichida)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT b.name, COUNT(o.id) AS cnt FROM branches b "
        "LEFT JOIN orders o ON o.branch_id = b.id AND o.created_at >= ? "
        "GROUP BY b.id ORDER BY cnt DESC", (since,))
    return await cur.fetchall()


async def clients_full():
    """Excel uchun: barcha mijozlar + murojaat statistikasi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT u.telegram_id, u.full_name, u.phone, u.status, u.registered_at, "
        "b.name AS branch, "
        "(SELECT COUNT(*) FROM orders o WHERE o.user_id=u.telegram_id) AS cnt, "
        "(SELECT MAX(created_at) FROM orders o WHERE o.user_id=u.telegram_id) AS last_at, "
        "(SELECT ROUND(AVG(rating),1) FROM orders o WHERE o.user_id=u.telegram_id "
        " AND rating IS NOT NULL) AS avg_r "
        "FROM users u LEFT JOIN branches b ON b.id=u.branch_id ORDER BY u.registered_at DESC")
    return await cur.fetchall()


async def my_daily_done(operator_id, days=7):
    """Operatorning so'nggi N kunlik yakunlari (kun kesimida)."""
    db = await get_db()
    since = (now_local() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    cur = await db.execute(
        "SELECT date(closed_at) AS d, COUNT(*) AS c FROM orders "
        "WHERE operator_id=? AND status='done' AND closed_at>=? GROUP BY d", (operator_id, since))
    return {r["d"]: r["c"] for r in await cur.fetchall()}


async def order_messages(order_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM messages WHERE order_id = ? ORDER BY id", (order_id,))
    return await cur.fetchall()


async def last_client_tg_msg(order_id):
    """Mijozning oxirgi xabarining (mijoz chatidagi) message_id sini qaytaradi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT tg_msg_id FROM messages WHERE order_id = ? AND sender = 'client' "
        "AND tg_msg_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    row = await cur.fetchone()
    return row["tg_msg_id"] if row else None


async def last_client_msg_time(order_id):
    """Mijozning oxirgi xabari vaqtini (created_at) qaytaradi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT created_at FROM messages WHERE order_id = ? AND sender = 'client' "
        "ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    row = await cur.fetchone()
    return row["created_at"] if row else None


async def last_operator_tg_msg(order_id):
    """Operatorning oxirgi xabarining (operator chatidagi) message_id sini qaytaradi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT tg_msg_id FROM messages WHERE order_id = ? AND sender = 'operator' "
        "AND tg_msg_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (order_id,),
    )
    row = await cur.fetchone()
    return row["tg_msg_id"] if row else None


# ---- Xabarlarni "Reply" uchun bog'lash (mijoz chati <-> operator chati) ----
async def add_link(order_id, client_msg_id, operator_msg_id, operator_tg):
    db = await get_db()
    await db.execute(
        "INSERT INTO msg_links (order_id, client_msg_id, operator_msg_id, operator_tg) "
        "VALUES (?, ?, ?, ?)",
        (order_id, client_msg_id, operator_msg_id, operator_tg),
    )
    await db.commit()


async def link_by_operator_msg(operator_msg_id, operator_tg):
    """Operator chatidagi message_id bo'yicha mos mijoz xabarini topadi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM msg_links WHERE operator_msg_id = ? AND operator_tg = ? "
        "ORDER BY id DESC LIMIT 1",
        (operator_msg_id, operator_tg),
    )
    return await cur.fetchone()


async def link_by_client_msg(client_msg_id, order_id):
    """Mijoz chatidagi message_id bo'yicha mos operator xabarini topadi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM msg_links WHERE client_msg_id = ? AND order_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (client_msg_id, order_id),
    )
    return await cur.fetchone()


# ============================ OPERATORS ============================
async def add_operator(name, login, password, bot_id=None):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO operators (name, login, password_hash, status, bot_id) "
        "VALUES (?, ?, ?, 'active', ?)",
        (name, login, hash_password(password), bot_id),
    )
    await db.commit()
    return cur.lastrowid


async def operators_by_bot(bot_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators WHERE bot_id = ? ORDER BY id", (bot_id,))
    return await cur.fetchall()


# ============================ OPERATOR BOTLARI ============================
async def add_operator_bot(token, username, title):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO operator_bots (token, username, title, enabled, created_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (token, username, title, now()),
    )
    await db.commit()
    return cur.lastrowid


async def list_operator_bots(only_enabled=False):
    db = await get_db()
    q_ = "SELECT * FROM operator_bots"
    if only_enabled:
        q_ += " WHERE enabled = 1"
    q_ += " ORDER BY id"
    cur = await db.execute(q_)
    return await cur.fetchall()


async def get_operator_bot(bot_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operator_bots WHERE id = ?", (bot_id,))
    return await cur.fetchone()


async def get_operator_bot_by_token(token):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operator_bots WHERE token = ?", (token,))
    return await cur.fetchone()


async def set_operator_bot_enabled(bot_id, enabled):
    db = await get_db()
    await db.execute("UPDATE operator_bots SET enabled = ? WHERE id = ?",
                     (1 if enabled else 0, bot_id))
    await db.commit()


async def delete_operator_bot(bot_id):
    db = await get_db()
    await db.execute("DELETE FROM operator_bots WHERE id = ?", (bot_id,))
    # Botga biriktirilgan operatorlarni ham o'chiramiz
    await db.execute("DELETE FROM operators WHERE bot_id = ?", (bot_id,))
    await db.commit()


# ============================ BILDIRISHNOMALAR ============================
async def add_order_notif(order_id, bot_id, chat_id, message_id):
    db = await get_db()
    await db.execute(
        "INSERT INTO order_notifs (order_id, bot_id, chat_id, message_id) VALUES (?, ?, ?, ?)",
        (order_id, bot_id, chat_id, message_id))
    await db.commit()


async def order_notifs(order_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM order_notifs WHERE order_id = ?", (order_id,))
    return await cur.fetchall()


async def clear_order_notifs(order_id):
    db = await get_db()
    await db.execute("DELETE FROM order_notifs WHERE order_id = ?", (order_id,))
    await db.commit()


async def list_operators():
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators ORDER BY id")
    return await cur.fetchall()


async def get_operator(operator_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators WHERE id = ?", (operator_id,))
    return await cur.fetchone()


async def get_operator_by_login(login):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators WHERE login = ?", (login,))
    return await cur.fetchone()


async def get_operator_by_tg(telegram_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators WHERE telegram_id = ?", (telegram_id,))
    return await cur.fetchone()


async def get_operator_by_tg_bot(telegram_id, bot_id):
    """Faqat shu botga tegishli operator (sessiya bot bo'yicha ajratilgan)."""
    db = await get_db()
    if bot_id is None:
        cur = await db.execute(
            "SELECT * FROM operators WHERE telegram_id = ? AND bot_id IS NULL", (telegram_id,))
    else:
        cur = await db.execute(
            "SELECT * FROM operators WHERE telegram_id = ? AND bot_id = ?", (telegram_id, bot_id))
    return await cur.fetchone()


async def login_operator(operator_id, telegram_id):
    db = await get_db()
    # operatorning boti
    cur = await db.execute("SELECT bot_id FROM operators WHERE id = ?", (operator_id,))
    row = await cur.fetchone()
    bot_id = row["bot_id"] if row else None
    # Bitta telegram FAQAT SHU BOT ichida bitta operatorga bog'lansin.
    # (Boshqa botlardagi sessiyalar saqlanadi — 1 hisob bilan bir nechta botga kirsa bo'ladi.)
    if bot_id is None:
        await db.execute("UPDATE operators SET telegram_id = NULL "
                         "WHERE telegram_id = ? AND bot_id IS NULL", (telegram_id,))
    else:
        await db.execute("UPDATE operators SET telegram_id = NULL "
                         "WHERE telegram_id = ? AND bot_id = ?", (telegram_id, bot_id))
    await db.execute("UPDATE operators SET telegram_id = ?, last_active = ? WHERE id = ?",
                     (telegram_id, now(), operator_id))
    await db.commit()


async def touch_operator(telegram_id):
    """Operatorning oxirgi faollik vaqtini yangilaydi (faqat login qilganlar uchun)."""
    db = await get_db()
    await db.execute("UPDATE operators SET last_active = ? WHERE telegram_id = ?",
                     (now(), telegram_id))
    await db.commit()


async def logged_in_operators():
    """Hozir tizimga kirgan (telegram_id bog'langan) operatorlar."""
    db = await get_db()
    cur = await db.execute("SELECT * FROM operators WHERE telegram_id IS NOT NULL")
    return await cur.fetchall()


async def idle_operators(threshold: str):
    """last_active berilgan vaqtdan eski bo'lgan (harakatsiz) login operatorlarni qaytaradi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM operators WHERE telegram_id IS NOT NULL "
        "AND (last_active IS NULL OR last_active < ?)",
        (threshold,),
    )
    return await cur.fetchall()


async def logout_operator(telegram_id, bot_id="__all__"):
    """bot_id berilsa — faqat o'sha botdan chiqaradi (boshqa botlardagi sessiya qoladi)."""
    db = await get_db()
    if bot_id == "__all__":
        await db.execute(
            "UPDATE operators SET telegram_id = NULL, active_order_id = NULL WHERE telegram_id = ?",
            (telegram_id,))
    elif bot_id is None:
        await db.execute(
            "UPDATE operators SET telegram_id = NULL, active_order_id = NULL "
            "WHERE telegram_id = ? AND bot_id IS NULL", (telegram_id,))
    else:
        await db.execute(
            "UPDATE operators SET telegram_id = NULL, active_order_id = NULL "
            "WHERE telegram_id = ? AND bot_id = ?", (telegram_id, bot_id))
    await db.commit()


async def set_operator_active_order(operator_id, order_id):
    db = await get_db()
    await db.execute("UPDATE operators SET active_order_id = ? WHERE id = ?", (order_id, operator_id))
    await db.commit()


async def update_operator(operator_id, field, value):
    db = await get_db()
    await db.execute(f"UPDATE operators SET {field} = ? WHERE id = ?", (value, operator_id))
    await db.commit()


async def delete_operator(operator_id):
    db = await get_db()
    await db.execute("DELETE FROM operators WHERE id = ?", (operator_id,))
    await db.commit()


async def update_operator_password(operator_id, password):
    db = await get_db()
    await db.execute("UPDATE operators SET password_hash = ? WHERE id = ?",
                     (hash_password(password), operator_id))
    await db.commit()


async def clear_operator_session(operator_id):
    """Login/parol o'zgartirilganda: operatorni tizimdan chiqaradi va
    saqlangan (tezkor) loginlarini o'chiradi — eski egasi kira olmaydi."""
    db = await get_db()
    await db.execute(
        "UPDATE operators SET telegram_id = NULL, active_order_id = NULL WHERE id = ?", (operator_id,))
    await db.execute("DELETE FROM saved_logins WHERE operator_id = ?", (operator_id,))
    await db.commit()


async def set_operator_availability(operator_id, availability):
    db = await get_db()
    await db.execute("UPDATE operators SET availability = ? WHERE id = ?", (availability, operator_id))
    await db.commit()


async def save_login(telegram_id, operator_id):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO saved_logins (telegram_id, operator_id) VALUES (?, ?)",
                     (telegram_id, operator_id))
    await db.commit()


async def saved_logins_for(telegram_id, bot_id="__all__"):
    """Shu telegram uchun saqlangan (faol) operator hisoblari.
    bot_id berilsa — faqat o'sha botga tegishli hisoblar (sessiya ajratish uchun)."""
    db = await get_db()
    if bot_id == "__all__":
        cur = await db.execute(
            "SELECT o.id, o.name FROM saved_logins s JOIN operators o ON o.id = s.operator_id "
            "WHERE s.telegram_id = ? AND o.status = 'active'", (telegram_id,))
    elif bot_id is None:
        cur = await db.execute(
            "SELECT o.id, o.name FROM saved_logins s JOIN operators o ON o.id = s.operator_id "
            "WHERE s.telegram_id = ? AND o.status = 'active' AND o.bot_id IS NULL", (telegram_id,))
    else:
        cur = await db.execute(
            "SELECT o.id, o.name FROM saved_logins s JOIN operators o ON o.id = s.operator_id "
            "WHERE s.telegram_id = ? AND o.status = 'active' AND o.bot_id = ?", (telegram_id, bot_id))
    return await cur.fetchall()


async def is_login_saved(telegram_id, operator_id):
    db = await get_db()
    cur = await db.execute("SELECT 1 FROM saved_logins WHERE telegram_id = ? AND operator_id = ?",
                           (telegram_id, operator_id))
    return (await cur.fetchone()) is not None


async def remove_saved_login(telegram_id, operator_id):
    db = await get_db()
    await db.execute("DELETE FROM saved_logins WHERE telegram_id = ? AND operator_id = ?",
                     (telegram_id, operator_id))
    await db.commit()


async def active_operators(exclude_id=None):
    """Faol (status=active) operatorlar ro'yxati — uzatish uchun."""
    db = await get_db()
    if exclude_id:
        cur = await db.execute(
            "SELECT * FROM operators WHERE status='active' AND id != ? ORDER BY name", (exclude_id,))
    else:
        cur = await db.execute("SELECT * FROM operators WHERE status='active' ORDER BY name")
    return await cur.fetchall()


# ============================ TEMPLATES (tayyor javoblar) ============================
async def list_templates():
    db = await get_db()
    cur = await db.execute("SELECT * FROM templates ORDER BY id")
    return await cur.fetchall()


async def get_template(template_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    return await cur.fetchone()


async def add_template(text, sticker=None):
    db = await get_db()
    await db.execute("INSERT INTO templates (text, sticker) VALUES (?, ?)", (text, sticker))
    await db.commit()


async def delete_template(template_id):
    db = await get_db()
    await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    await db.commit()


async def operator_stats(operator_id):
    db = await get_db()
    today = now_local().strftime("%Y-%m-%d")
    month = now_local().strftime("%Y-%m")
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE operator_id = ?", (operator_id,)
    )
    accepted = (await cur.fetchone())[0]
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND status = 'done'", (operator_id,)
    )
    done = (await cur.fetchone())[0]
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND bill IS NOT NULL", (operator_id,)
    )
    billed = (await cur.fetchone())[0]
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND status = 'done' AND closed_at LIKE ?",
        (operator_id, today + "%"),
    )
    today_done = (await cur.fetchone())[0]
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND status = 'done' AND closed_at LIKE ?",
        (operator_id, month + "%"),
    )
    month_done = (await cur.fetchone())[0]
    cur = await db.execute(
        "SELECT AVG(rating), COUNT(rating) FROM orders WHERE operator_id = ? AND rating IS NOT NULL",
        (operator_id,),
    )
    row = await cur.fetchone()
    avg_rating = round(row[0], 1) if row[0] else 0
    rated_count = row[1] or 0
    return {
        "accepted": accepted, "done": done, "billed": billed,
        "today_done": today_done, "month_done": month_done,
        "avg_rating": avg_rating, "rated_count": rated_count,
    }


async def operators_rating():
    """Shu oydagi reyting: yakunlangan + hisoblangan."""
    db = await get_db()
    month = now_local().strftime("%Y-%m")
    cur = await db.execute("SELECT id, name FROM operators ORDER BY id")
    ops = await cur.fetchall()
    result = []
    for op in ops:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND status='done' AND closed_at LIKE ?",
            (op["id"], month + "%"),
        )
        done = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE operator_id = ? AND bill IS NOT NULL AND created_at LIKE ?",
            (op["id"], month + "%"),
        )
        billed = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT AVG(rating) FROM orders WHERE operator_id = ? AND rating IS NOT NULL",
            (op["id"],),
        )
        avg = (await cur.fetchone())[0]
        avg_rating = round(avg, 1) if avg else 0
        result.append({"name": op["name"], "score": done + billed, "done": done,
                       "billed": billed, "avg_rating": avg_rating})
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


# ============================ FAQ ============================
async def list_faqs():
    db = await get_db()
    cur = await db.execute("SELECT * FROM faqs ORDER BY id")
    return await cur.fetchall()


async def get_faq(faq_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,))
    return await cur.fetchone()


async def add_faq(title, answer):
    db = await get_db()
    await db.execute("INSERT INTO faqs (title, answer) VALUES (?, ?)", (title, answer))
    await db.commit()


async def update_faq(faq_id, title, answer):
    db = await get_db()
    await db.execute("UPDATE faqs SET title = ?, answer = ? WHERE id = ?", (title, answer, faq_id))
    await db.commit()


async def delete_faq(faq_id):
    db = await get_db()
    await db.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    await db.commit()


# ============================ CHANNELS ============================
async def list_channels():
    db = await get_db()
    cur = await db.execute("SELECT * FROM channels ORDER BY id")
    return await cur.fetchall()


async def add_channel(chat_id, title):
    db = await get_db()
    await db.execute("INSERT INTO channels (chat_id, title) VALUES (?, ?)", (chat_id, title))
    await db.commit()


async def delete_channel(channel_id):
    db = await get_db()
    await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    await db.commit()


# ============================ SETTINGS ============================
async def get_setting(key, default=""):
    db = await get_db()
    cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default


async def set_setting(key, value):
    db = await get_db()
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


# ============================ STATISTIKA ============================
async def general_stats():
    db = await get_db()
    today = now_local().strftime("%Y-%m-%d")
    week_ago = (now_local() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month = now_local().strftime("%Y-%m")

    async def count(q, p=()):
        cur = await db.execute(q, p)
        return (await cur.fetchone())[0]

    stats = {
        "users_total": await count("SELECT COUNT(*) FROM users"),
        "users_today": await count("SELECT COUNT(*) FROM users WHERE registered_at LIKE ?", (today + "%",)),
        "users_week": await count("SELECT COUNT(*) FROM users WHERE registered_at >= ?", (week_ago,)),
        "users_month": await count("SELECT COUNT(*) FROM users WHERE registered_at LIKE ?", (month + "%",)),
        "orders_total": await count("SELECT COUNT(*) FROM orders"),
        "orders_today": await count("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (today + "%",)),
        "orders_week": await count("SELECT COUNT(*) FROM orders WHERE created_at >= ?", (week_ago,)),
        "orders_new": await count("SELECT COUNT(*) FROM orders WHERE status = 'new'"),
        "orders_progress": await count("SELECT COUNT(*) FROM orders WHERE status = 'in_progress'"),
        "orders_done": await count("SELECT COUNT(*) FROM orders WHERE status = 'done'"),
        "orders_canceled": await count("SELECT COUNT(*) FROM orders WHERE status = 'canceled'"),
    }
    # umumiy o'rtacha baho
    cur = await db.execute("SELECT AVG(rating), COUNT(rating) FROM orders WHERE rating IS NOT NULL")
    row = await cur.fetchone()
    stats["avg_rating"] = round(row[0], 1) if row[0] else 0
    stats["rated_count"] = row[1] or 0

    # javob/yakunlash vaqti — MEDIAN (chetga chiqqanlar buzmasin, real bo'lsin)
    cur = await db.execute(
        "SELECT (julianday(MIN(sl.changed_at)) - julianday(o.created_at)) * 1440 "
        "FROM orders o JOIN status_log sl ON sl.order_id = o.id "
        "WHERE sl.new_status = 'in_progress' GROUP BY o.id")
    stats["avg_response_min"] = _median([r[0] for r in await cur.fetchall()])
    cur = await db.execute(
        "SELECT (julianday(closed_at) - julianday(created_at)) * 1440 "
        "FROM orders WHERE status = 'done' AND closed_at IS NOT NULL")
    stats["avg_resolve_min"] = _median([r[0] for r in await cur.fetchall()])

    # filiallar kesimida
    cur = await db.execute(
        "SELECT b.name, COUNT(o.id) AS cnt FROM branches b "
        "LEFT JOIN orders o ON o.branch_id = b.id GROUP BY b.id ORDER BY b.id"
    )
    stats["branches"] = await cur.fetchall()
    return stats


async def live_stats():
    """Real vaqt holati: yangi/jarayonda/bugun yakunlangan + operatorlar kesimi."""
    db = await get_db()
    today = now_local().strftime("%Y-%m-%d")

    async def c(q_, p=()):
        cur = await db.execute(q_, p)
        return (await cur.fetchone())[0]

    new = await c("SELECT COUNT(*) FROM orders WHERE status='new'")
    prog = await c("SELECT COUNT(*) FROM orders WHERE status='in_progress'")
    today_new = await c("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (today + "%",))
    today_done = await c("SELECT COUNT(*) FROM orders WHERE status='done' AND closed_at LIKE ?",
                         (today + "%",))
    online = await c("SELECT COUNT(*) FROM operators WHERE telegram_id IS NOT NULL")
    # operatorlar kesimi: hozir jarayonda nechta, online/holat
    cur = await db.execute(
        "SELECT op.id, op.name, op.availability, op.telegram_id, "
        "(SELECT COUNT(*) FROM orders o WHERE o.operator_id=op.id AND o.status='in_progress') AS cnt, "
        "(SELECT COUNT(*) FROM orders o WHERE o.operator_id=op.id AND o.status='done' "
        " AND o.closed_at LIKE ?) AS done_today "
        "FROM operators op WHERE op.status='active' ORDER BY cnt DESC, done_today DESC",
        (today + "%",))
    per_op = await cur.fetchall()
    return {"new": new, "prog": prog, "today_new": today_new, "today_done": today_done,
            "online": online, "per_op": per_op}


# ============================ MINI APP (CRM) ============================
async def op_chats(operator_id):
    """Operator chatlari: o'ziga biriktirilgan jarayondagilar + yangi (kelayotgan) murojaatlar.
    Yashirilganlar chiqmaydi. Har birida oxirgi xabar ko'rinadi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.status, o.user_id, o.operator_id, o.created_at, o.rating, "
        "u.full_name, u.phone, u.username, "
        "(SELECT text FROM messages m WHERE m.order_id=o.id ORDER BY m.id DESC LIMIT 1) AS last_text, "
        "(SELECT content_type FROM messages m WHERE m.order_id=o.id ORDER BY m.id DESC LIMIT 1) AS last_ct, "
        "(SELECT created_at FROM messages m WHERE m.order_id=o.id ORDER BY m.id DESC LIMIT 1) AS last_at, "
        "(SELECT sender FROM messages m WHERE m.order_id=o.id ORDER BY m.id DESC LIMIT 1) AS last_sender "
        "FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
        "WHERE o.status='in_progress' AND o.operator_id=? "
        "AND o.id NOT IN (SELECT order_id FROM hidden_chats WHERE operator_id=?) "
        "ORDER BY COALESCE(last_at, o.created_at) DESC LIMIT 100",
        (operator_id, operator_id))
    return await cur.fetchall()


async def new_count():
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    return (await cur.fetchone())[0]


async def my_clients(operator_id, search=None):
    """Operator qabul qilgan (o'ziga biriktirilgan) mijozlar — har biri bo'yicha oxirgi murojaat."""
    db = await get_db()
    where = "WHERE o.operator_id = ?"
    params = [operator_id]
    if search:
        s = search.strip()
        where += " AND (u.full_name LIKE ? OR u.phone LIKE ?)"
        params += [f"%{s}%", f"%{s}%"]
    cur = await db.execute(
        f"SELECT u.telegram_id, u.full_name, u.phone, u.username, "
        f"COUNT(o.id) AS cnt, MAX(o.id) AS last_order, MAX(o.created_at) AS last_at "
        f"FROM orders o JOIN users u ON u.telegram_id = o.user_id {where} "
        f"GROUP BY u.telegram_id ORDER BY last_at DESC LIMIT 100", params)
    return await cur.fetchall()


async def channel_feed():
    """CRM kanali: yangi (kutayotgan) murojaatlar — mijoz ma'lumoti + birinchi kontent bilan."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.created_at, o.content_type, u.full_name, u.phone, u.username, b.name AS branch, "
        "(SELECT text FROM messages m WHERE m.order_id=o.id AND m.sender='client' ORDER BY m.id LIMIT 1) AS first_text, "
        "(SELECT content_type FROM messages m WHERE m.order_id=o.id AND m.sender='client' ORDER BY m.id LIMIT 1) AS first_ct, "
        "(SELECT file_id FROM messages m WHERE m.order_id=o.id AND m.sender='client' ORDER BY m.id LIMIT 1) AS first_file "
        "FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
        "LEFT JOIN branches b ON b.id=o.branch_id "
        "WHERE o.status='new' ORDER BY o.created_at DESC LIMIT 50")
    return await cur.fetchall()


async def get_client_note(user_id):
    db = await get_db()
    cur = await db.execute("SELECT note FROM client_notes WHERE user_id = ?", (user_id,))
    r = await cur.fetchone()
    return r["note"] if r and r["note"] else ""


async def set_client_note(user_id, note):
    db = await get_db()
    await db.execute(
        "INSERT INTO client_notes (user_id, note, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
        (user_id, note, now()))
    await db.commit()


async def last_order_of(tg):
    db = await get_db()
    cur = await db.execute("SELECT id FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1", (tg,))
    r = await cur.fetchone()
    return r["id"] if r else None


async def hide_chat(operator_id, order_id):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO hidden_chats (operator_id, order_id) VALUES (?, ?)",
                     (operator_id, order_id))
    await db.commit()


# ============================ HISOBOTLAR (admin) ============================
async def orders_page(limit, offset, search=None, status=None, since=None):
    """Murojaatlar ro'yxati (sahifalab) + umumiy soni. search: ism/telefon/#id;
    status: new/in_progress/done/canceled; since: sana filtri."""
    db = await get_db()
    conds, params = [], []
    if search:
        s = search.strip().lstrip("#")
        if s.isdigit():
            conds.append("(o.id = ? OR u.phone LIKE ?)")
            params += [int(s), f"%{s}%"]
        else:
            conds.append("(u.full_name LIKE ? OR u.phone LIKE ?)")
            params += [f"%{s}%", f"%{s}%"]
    if status:
        conds.append("o.status = ?")
        params.append(status)
    if since:
        conds.append("o.created_at >= ?")
        params.append(since)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    cur = await db.execute(
        f"SELECT o.id, o.status, o.created_at, o.closed_at, o.rating, o.content_type, "
        f"u.full_name, u.phone, op.name AS operator "
        f"FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
        f"LEFT JOIN operators op ON op.id=o.operator_id {where} "
        f"ORDER BY o.id DESC LIMIT ? OFFSET ?", (*params, limit, offset))
    rows = await cur.fetchall()
    cur = await db.execute(
        f"SELECT COUNT(*) FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id {where}", params)
    total = (await cur.fetchone())[0]
    return rows, total


async def low_rated_orders(limit=40):
    """Sifat nazorati: past (1-3★) baholangan murojaatlar, izohlari bilan."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.rating, o.feedback, o.closed_at, u.full_name, op.name AS operator "
        "FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
        "LEFT JOIN operators op ON op.id=o.operator_id "
        "WHERE o.rating IS NOT NULL AND o.rating <= 3 "
        "ORDER BY o.id DESC LIMIT ?", (limit,))
    return await cur.fetchall()


async def waiting_orders():
    """Hozir kutayotgan (yangi) murojaatlar — eng eskisi birinchi."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.created_at, u.full_name FROM orders o "
        "LEFT JOIN users u ON u.telegram_id=o.user_id "
        "WHERE o.status='new' ORDER BY o.created_at ASC LIMIT 10")
    return await cur.fetchall()


async def users_page(limit, offset, search=None):
    """Mijozlar ro'yxati (sahifalab) + umumiy soni."""
    db = await get_db()
    where, params = "", []
    if search:
        s = search.strip()
        where = "WHERE u.full_name LIKE ? OR u.phone LIKE ?"
        params = [f"%{s}%", f"%{s}%"]
    cur = await db.execute(
        f"SELECT u.telegram_id, u.full_name, u.phone, u.username, b.name AS branch, "
        f"(SELECT COUNT(*) FROM orders o WHERE o.user_id=u.telegram_id) AS cnt, "
        f"(SELECT MAX(created_at) FROM orders o WHERE o.user_id=u.telegram_id) AS last_at "
        f"FROM users u LEFT JOIN branches b ON b.id=u.branch_id {where} "
        f"ORDER BY u.registered_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))
    rows = await cur.fetchall()
    cur = await db.execute(f"SELECT COUNT(*) FROM users u {where}", params)
    total = (await cur.fetchone())[0]
    return rows, total


async def top_clients(since, limit, offset):
    """Davr ichida eng ko'p murojaat yuborgan mijozlar (kamayish tartibida)."""
    db = await get_db()
    cur = await db.execute(
        "SELECT u.telegram_id, u.full_name, u.phone, u.username, b.name AS branch, "
        "COUNT(o.id) AS cnt "
        "FROM users u JOIN orders o ON o.user_id=u.telegram_id AND o.created_at>=? "
        "LEFT JOIN branches b ON b.id=u.branch_id "
        "GROUP BY u.telegram_id ORDER BY cnt DESC, MAX(o.created_at) DESC LIMIT ? OFFSET ?",
        (since, limit, offset))
    rows = await cur.fetchall()
    cur = await db.execute(
        "SELECT COUNT(*) FROM (SELECT o.user_id FROM orders o WHERE o.created_at>=? "
        "GROUP BY o.user_id)", (since,))
    total = (await cur.fetchone())[0]
    return rows, total


async def user_full(tg):
    db = await get_db()
    cur = await db.execute(
        "SELECT u.*, b.name AS branch FROM users u LEFT JOIN branches b ON b.id=u.branch_id "
        "WHERE u.telegram_id=?", (tg,))
    return await cur.fetchone()


async def operators_report(since):
    """Har operator kesimi (berilgan sanadan beri): qabul, yakun, javob/yakunlash vaqti, reyting."""
    db = await get_db()
    cur = await db.execute("SELECT id, name FROM operators WHERE status='active' ORDER BY id")
    ops = await cur.fetchall()

    async def val(q_, p):
        cur = await db.execute(q_, p)
        return (await cur.fetchone())[0]

    res = []
    for op in ops:
        oid = op["id"]
        accepted = await val("SELECT COUNT(*) FROM orders WHERE operator_id=? AND created_at>=?",
                             (oid, since))
        done = await val("SELECT COUNT(*) FROM orders WHERE operator_id=? AND status='done' "
                         "AND closed_at>=?", (oid, since))
        cur = await db.execute(
            "SELECT (julianday(MIN(sl.changed_at))-julianday(o.created_at))*1440 "
            "FROM orders o JOIN status_log sl ON sl.order_id=o.id "
            "WHERE sl.new_status='in_progress' AND sl.changed_by=? AND o.created_at>=? GROUP BY o.id",
            (f"operator:{oid}", since))
        resp = _median([r[0] for r in await cur.fetchall()])
        cur = await db.execute(
            "SELECT (julianday(closed_at)-julianday(created_at))*1440 FROM orders "
            "WHERE operator_id=? AND status='done' AND closed_at>=?", (oid, since))
        resol = _median([r[0] for r in await cur.fetchall()])
        rat = await val("SELECT AVG(rating) FROM orders WHERE operator_id=? AND rating IS NOT NULL",
                        (oid,))
        res.append({"name": op["name"], "accepted": accepted, "done": done,
                    "resp": resp, "resol": resol,
                    "rating": round(rat, 1) if rat else 0})
    return res


async def hourly_load(since):
    """Soat kesimida (0-23) murojaatlar soni."""
    db = await get_db()
    cur = await db.execute(
        "SELECT CAST(strftime('%H', created_at) AS INTEGER) AS hr, COUNT(*) "
        "FROM orders WHERE created_at>=? GROUP BY hr", (since,))
    return {r[0]: r[1] for r in await cur.fetchall()}


async def period_report(since):
    """Davr bo'yicha umumiy + kunlar kesimi."""
    db = await get_db()

    async def val(q_, p=()):
        cur = await db.execute(q_, p)
        return (await cur.fetchone())[0]

    total = await val("SELECT COUNT(*) FROM orders WHERE created_at>=?", (since,))
    new = await val("SELECT COUNT(*) FROM orders WHERE status='new' AND created_at>=?", (since,))
    prog = await val("SELECT COUNT(*) FROM orders WHERE status='in_progress' AND created_at>=?", (since,))
    done = await val("SELECT COUNT(*) FROM orders WHERE status='done' AND created_at>=?", (since,))
    canceled = await val("SELECT COUNT(*) FROM orders WHERE status='canceled' AND created_at>=?", (since,))
    # MEDIAN — tunda javobsiz qolgan/kunlar o'tib yopilganlar o'rtachani buzmasin (real ko'rsatkich)
    cur = await db.execute(
        "SELECT (julianday(MIN(sl.changed_at))-julianday(o.created_at))*1440 "
        "FROM orders o JOIN status_log sl ON sl.order_id=o.id "
        "WHERE sl.new_status='in_progress' AND o.created_at>=? GROUP BY o.id", (since,))
    resp = _median([r[0] for r in await cur.fetchall()])
    cur = await db.execute(
        "SELECT (julianday(closed_at)-julianday(created_at))*1440 FROM orders "
        "WHERE status='done' AND closed_at>=? AND closed_at IS NOT NULL", (since,))
    resol = _median([r[0] for r in await cur.fetchall()])
    cur = await db.execute(
        "SELECT date(created_at) AS d, COUNT(*), "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) "
        "FROM orders WHERE created_at>=? GROUP BY d ORDER BY d DESC LIMIT 14", (since,))
    days = await cur.fetchall()
    return {"total": total, "new": new, "prog": prog, "done": done, "canceled": canceled,
            "resp": round(resp, 1) if resp else 0, "resol": round(resol, 1) if resol else 0,
            "days": days}


async def series_counts(since, by="day"):
    """Vaqt seriyasi: kun (yoki oy) kesimida jami va yakunlangan murojaatlar (ASC)."""
    fmt = "%Y-%m" if by == "month" else "%Y-%m-%d"
    db = await get_db()
    cur = await db.execute(
        "SELECT strftime(?, created_at) AS d, COUNT(*) AS total, "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
        "FROM orders WHERE created_at >= ? GROUP BY d ORDER BY d ASC", (fmt, since))
    return await cur.fetchall()


async def period_rating(since):
    db = await get_db()
    cur = await db.execute(
        "SELECT AVG(rating), COUNT(rating) FROM orders WHERE rating IS NOT NULL AND created_at>=?",
        (since,))
    row = await cur.fetchone()
    return (round(row[0], 1) if row[0] else 0, row[1] or 0)


# ============================ EXCEL HISOBOT UCHUN ============================
async def all_orders_full(since=None):
    db = await get_db()
    where = "WHERE o.created_at >= ?" if since else ""
    params = (since,) if since else ()
    cur = await db.execute(
        "SELECT o.id, u.full_name, u.phone, b.name AS branch, op.name AS operator, "
        "o.status, o.content_type, o.bill, o.created_at, o.closed_at, o.rating, o.feedback "
        "FROM orders o "
        "LEFT JOIN users u ON u.telegram_id = o.user_id "
        "LEFT JOIN branches b ON b.id = o.branch_id "
        "LEFT JOIN operators op ON op.id = o.operator_id "
        f"{where} ORDER BY o.id", params)
    return await cur.fetchall()
