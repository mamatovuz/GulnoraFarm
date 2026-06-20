"""Bot konfiguratsiyasi — .env faylidan o'qiladi."""
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Vaqt zonasi (Toshkent = UTC+5). Server UTC bo'lsa ham to'g'ri ishlaydi.
TZ_OFFSET = int(os.getenv("TZ_OFFSET", "5"))


def now_local() -> datetime:
    """Mahalliy (Toshkent) vaqt — server vaqt zonasidan qat'i nazar."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=TZ_OFFSET)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()
]

_group = os.getenv("OPERATORS_GROUP_ID", "").strip()
OPERATORS_GROUP_ID = int(_group) if _group and _group.lstrip("-").isdigit() else None

# Ma'lumotlar bazasi yo'li.
# Railway'da /data volume ulangan bo'lsa, baza o'sha yerda (doimiy) saqlanadi.
# DB_PATH muhit o'zgaruvchisi orqali ham belgilash mumkin.
_default_db = "/data/gulnora_farm.db" if os.path.isdir("/data") else "gulnora_farm.db"
DB_PATH = os.getenv("DB_PATH", _default_db)

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! .env faylini yarating (.env.example dan nusxa oling) "
        "va BOT_TOKEN qiymatini kiriting."
    )
