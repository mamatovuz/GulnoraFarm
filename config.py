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

# Bosh admin (super-admin) — o'zgarmas. Faqat u «asosiy admin»ni tanlaydi va uni
# adminlikdan olib bo'lmaydi. Kunlik baza zaxirasini bildirishnoma o'chiq bo'lsa ham
# doim shu admin oladi (eng katta sug'urta).
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "7903688837") or "7903688837")
if SUPER_ADMIN_ID and SUPER_ADMIN_ID not in ADMIN_IDS:
    ADMIN_IDS.append(SUPER_ADMIN_ID)

_group = os.getenv("OPERATORS_GROUP_ID", "").strip()
OPERATORS_GROUP_ID = int(_group) if _group and _group.lstrip("-").isdigit() else None

# Ma'lumotlar bazasi yo'li.
# Railway'da /data volume ulangan bo'lsa, baza o'sha yerda (doimiy) saqlanadi.
# DB_PATH muhit o'zgaruvchisi orqali ham belgilash mumkin.
_default_db = "/data/gulnora_farm.db" if os.path.isdir("/data") else "gulnora_farm.db"
DB_PATH = os.getenv("DB_PATH", _default_db)

# Telegram Mini App (CRM web panel)
# WEBAPP_URL — Railway public domeni, masalan: https://gulnora-farm.up.railway.app
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
# Railway PORT ni beradi; bo'lmasa 8080
WEBAPP_PORT = int(os.getenv("PORT", "8080"))
# Operator profil rasmlari (mini app) — baza papkasida saqlanadi (Railway /data volume'da doimiy)
AVATAR_DIR = os.path.join(os.path.dirname(DB_PATH) or ".", "avatars")
# Media kesh: mini app'da rasm/ovoz har safar Telegram'dan qayta yuklanmasin (egress tejash)
MEDIA_CACHE = os.path.join(os.path.dirname(DB_PATH) or ".", "mediacache")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! .env faylini yarating (.env.example dan nusxa oling) "
        "va BOT_TOKEN qiymatini kiriting."
    )
