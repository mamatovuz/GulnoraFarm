"""Ma'lumotlar bazasi ulanishi va boshlang'ich sxema."""
import os
import aiosqlite
from config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        # Baza papkasi mavjud bo'lmasa yaratamiz (masalan Railway /data volume)
        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA foreign_keys = ON;")
    return _db


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id   INTEGER PRIMARY KEY,
    full_name     TEXT,
    phone         TEXT,
    branch_id     INTEGER,
    registered_at TEXT,
    status        TEXT DEFAULT 'active',      -- active | blocked
    active_order_id INTEGER,                   -- ochiq murojaat (proxy-chat uchun)
    lang          TEXT DEFAULT 'uz'            -- til: uz | ru
);

CREATE TABLE IF NOT EXISTS branches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    address       TEXT,
    phone         TEXT,
    lat           REAL,
    lon           REAL,
    photo_file_id TEXT,
    open_time     TEXT DEFAULT '08:00',
    close_time    TEXT DEFAULT '23:00'
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    operator_id  INTEGER,
    branch_id    INTEGER,
    created_at   TEXT,
    closed_at    TEXT,
    status       TEXT DEFAULT 'new',          -- new | in_progress | done | canceled
    content_type TEXT,                         -- text | photo | document | video
    bill         TEXT,
    rating       INTEGER                        -- mijoz bahosi (1-5)
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    sender       TEXT,                          -- client | operator
    content_type TEXT,                          -- text | photo | document | video | location
    text         TEXT,
    file_id      TEXT,
    tg_msg_id    INTEGER,                        -- jo'natuvchi chatdagi Telegram message_id
    created_at   TEXT
);

-- Ikki chat (mijoz <-> operator) orasidagi xabarlarni "Reply" uchun bog'lash
CREATE TABLE IF NOT EXISTS msg_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER,
    client_msg_id   INTEGER,    -- mijoz chatidagi message_id
    operator_msg_id INTEGER,    -- operator chatidagi message_id
    operator_tg     INTEGER     -- operatorning telegram id si
);

CREATE TABLE IF NOT EXISTS operators (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    login         TEXT UNIQUE,
    password_hash TEXT,
    telegram_id   INTEGER,
    status        TEXT DEFAULT 'active',        -- active | inactive
    active_order_id INTEGER
);

CREATE TABLE IF NOT EXISTS faqs (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title  TEXT,
    answer TEXT
);

CREATE TABLE IF NOT EXISTS channels (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    title   TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS status_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER,
    old_status TEXT,
    new_status TEXT,
    changed_by TEXT,
    changed_at TEXT
);
"""

DEFAULT_FAQS = [
    ("🕐 Ish vaqti", "Gulnora Farm filiallari har kuni 08:00 dan 23:00 gacha ishlaydi."),
    ("🚚 Yetkazib berish xizmati", "Shahar ichida buyurtmalarni 1-2 soat ichida yetkazib beramiz. "
                                   "Yetkazib berish narxi masofaga qarab belgilanadi."),
    ("💳 To'lov usullari", "To'lovni naqd pul, plastik karta (UzCard/Humo) yoki "
                           "Payme/Click orqali amalga oshirishingiz mumkin."),
    ("🔍 Dori mavjudligini tekshirish", "Kerakli dori nomini '💊 Retsept yuborish' bo'limi orqali yuboring — "
                                        "operatorlarimiz mavjudligini tekshirib, javob beradi."),
]

DEFAULT_BRANCHES = [
    ("🏥 Chilonzor filiali", "Chilonzor tumani, Bunyodkor shoh ko'chasi, 12-uy", "+998 71 200 00 01"),
    ("🏥 Yunusobod filiali", "Yunusobod tumani, Amir Temur ko'chasi, 108-uy", "+998 71 200 00 02"),
    ("🏥 Sergeli filiali", "Sergeli tumani, Yangi Sergeli ko'chasi, 7-uy", "+998 71 200 00 03"),
]

DEFAULT_SETTINGS = {
    "contact_text": (
        "☎️ <b>Gulnora Farm bilan bog'lanish</b>\n\n"
        "📞 Call-markaz: +998 71 200 00 00\n"
        "✉️ Email: info@gulnorafarm.uz\n"
        "🌐 Veb-sayt: www.gulnorafarm.uz\n\n"
        "Ish vaqti: 08:00 — 23:00 (har kuni)\n\n"
        "Savolingiz bo'lsa, shu yerga yozishingiz ham mumkin — "
        "operatorimiz tez orada javob beradi."
    ),
}


async def init_db():
    db = await get_db()
    await db.executescript(SCHEMA)
    await db.commit()

    # Migratsiya: eski bazada tg_msg_id ustuni bo'lmasa qo'shamiz
    cur = await db.execute("PRAGMA table_info(messages)")
    cols = [row[1] for row in await cur.fetchall()]
    if "tg_msg_id" not in cols:
        await db.execute("ALTER TABLE messages ADD COLUMN tg_msg_id INTEGER")
        await db.commit()

    # Migratsiya: orders.rating ustuni
    cur = await db.execute("PRAGMA table_info(orders)")
    ocols = [row[1] for row in await cur.fetchall()]
    if "rating" not in ocols:
        await db.execute("ALTER TABLE orders ADD COLUMN rating INTEGER")
        await db.commit()

    # Migratsiya: users.lang ustuni
    cur = await db.execute("PRAGMA table_info(users)")
    ucols = [row[1] for row in await cur.fetchall()]
    if "lang" not in ucols:
        await db.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'")
        await db.commit()

    # Migratsiya: branches ish vaqti ustunlari
    cur = await db.execute("PRAGMA table_info(branches)")
    bcols = [row[1] for row in await cur.fetchall()]
    if "open_time" not in bcols:
        await db.execute("ALTER TABLE branches ADD COLUMN open_time TEXT DEFAULT '08:00'")
        await db.commit()
    if "close_time" not in bcols:
        await db.execute("ALTER TABLE branches ADD COLUMN close_time TEXT DEFAULT '23:00'")
        await db.commit()

    # Boshlang'ich FAQ
    cur = await db.execute("SELECT COUNT(*) FROM faqs")
    if (await cur.fetchone())[0] == 0:
        await db.executemany("INSERT INTO faqs (title, answer) VALUES (?, ?)", DEFAULT_FAQS)

    # Boshlang'ich filiallar
    cur = await db.execute("SELECT COUNT(*) FROM branches")
    if (await cur.fetchone())[0] == 0:
        await db.executemany(
            "INSERT INTO branches (name, address, phone) VALUES (?, ?, ?)", DEFAULT_BRANCHES
        )

    # Boshlang'ich sozlamalar
    for key, value in DEFAULT_SETTINGS.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )

    await db.commit()
