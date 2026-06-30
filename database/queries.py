"""Barcha ma'lumotlar bazasi amallari."""
import hashlib
from datetime import timedelta
from config import now_local
from database.db import get_db


def now() -> str:
    return now_local().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str) -> str:
    return hashlib.sha256(("gulnorafarm_salt_" + password).encode()).hexdigest()


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
async def add_message(order_id, sender, content_type, text=None, file_id=None, tg_msg_id=None):
    db = await get_db()
    await db.execute(
        "INSERT INTO messages (order_id, sender, content_type, text, file_id, tg_msg_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (order_id, sender, content_type, text, file_id, tg_msg_id, now()),
    )
    await db.commit()


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


async def login_operator(operator_id, telegram_id):
    db = await get_db()
    # bitta telegram bitta operatorga bog'lansin
    await db.execute("UPDATE operators SET telegram_id = NULL WHERE telegram_id = ?", (telegram_id,))
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


async def logout_operator(telegram_id):
    db = await get_db()
    await db.execute(
        "UPDATE operators SET telegram_id = NULL, active_order_id = NULL WHERE telegram_id = ?",
        (telegram_id,),
    )
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


async def set_operator_availability(operator_id, availability):
    db = await get_db()
    await db.execute("UPDATE operators SET availability = ? WHERE id = ?", (availability, operator_id))
    await db.commit()


async def save_login(telegram_id, operator_id):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO saved_logins (telegram_id, operator_id) VALUES (?, ?)",
                     (telegram_id, operator_id))
    await db.commit()


async def saved_logins_for(telegram_id):
    """Shu telegram uchun saqlangan (faol) operator hisoblari."""
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, o.name FROM saved_logins s JOIN operators o ON o.id = s.operator_id "
        "WHERE s.telegram_id = ? AND o.status = 'active'", (telegram_id,))
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

    # filiallar kesimida
    cur = await db.execute(
        "SELECT b.name, COUNT(o.id) AS cnt FROM branches b "
        "LEFT JOIN orders o ON o.branch_id = b.id GROUP BY b.id ORDER BY b.id"
    )
    stats["branches"] = await cur.fetchall()
    return stats


# ============================ EXCEL HISOBOT UCHUN ============================
async def all_orders_full():
    db = await get_db()
    cur = await db.execute(
        "SELECT o.id, u.full_name, u.phone, b.name AS branch, op.name AS operator, "
        "o.status, o.content_type, o.bill, o.created_at, o.closed_at, o.rating, o.feedback "
        "FROM orders o "
        "LEFT JOIN users u ON u.telegram_id = o.user_id "
        "LEFT JOIN branches b ON b.id = o.branch_id "
        "LEFT JOIN operators op ON op.id = o.operator_id "
        "ORDER BY o.id"
    )
    return await cur.fetchall()
