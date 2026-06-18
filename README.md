# 💊 Gulnora Farm — Telegram boti

Retsept/buyurtma qabul qiluvchi to'liq Telegram bot: foydalanuvchi qismi, operator
kabineti va admin panel bilan. `aiogram 3` + `SQLite` asosida qurilgan.

## Imkoniyatlar

**Foydalanuvchi:**
- Ro'yxatdan o'tish (ism + telefon raqam)
- Majburiy kanal(lar)ga obuna tekshiruvi
- Filial tanlash
- Retsept yuborish (matn / rasm / PDF) → operator bilan ikki tomonlama chat
- FAQ, Filiallar (rasm + xarita), Bog'lanish bo'limlari

**Operator (`/operator`):**
- Login/parol bilan kirish
- Yangi murojaatlarni qabul qilish, mijoz bilan chat
- Dori/retsept hisoblash, yakunlash/bekor qilish
- Shaxsiy statistika va reyting

**Admin (`/admin`):**
- Statistika + Excel hisobot
- Ommaviy xabar (matn/rasm/video/hujjat)
- Kanal, FAQ, Filial (rasm yuklash bilan), Operator boshqaruvi
- Murojaatlar tarixi (raqam/foydalanuvchi/filial bo'yicha qidiruv)
- Bog'lanish matnini tahrirlash

## O'rnatish

1. **Kutubxonalarni o'rnating:**
   ```bash
   pip install -r requirements.txt
   ```

2. **`.env` faylini sozlang** (`.env.example` dan nusxa oling):
   ```
   BOT_TOKEN=BotFather_dan_olingan_token
   ADMIN_IDS=123456789            # o'z Telegram ID'ingiz (@userinfobot dan)
   OPERATORS_GROUP_ID=            # ixtiyoriy: operatorlar guruhi ID (masalan -1001234567890)
   ```
   > ⚠️ `ADMIN_IDS` ni to'ldiring — aks holda `/admin` paneli ochilmaydi.

3. **Botni ishga tushiring:**
   ```bash
   python bot.py
   ```

## Foydalanish tartibi

1. Admin `/admin` → **Filiallar** qo'shadi (rasm, lokatsiya bilan).
2. Admin **Operatorlar** → operator qo'shadi (login/parol oladi).
3. Admin (ixtiyoriy) **Kanal boshqaruvi** → majburiy obuna kanallarini qo'shadi.
   Bot o'sha kanallarda **admin** bo'lishi shart.
4. Operator `/operator` → login/parol bilan kiradi. Yangi murojaat kelganda
   "Qabul qilish" → mijoz bilan yozishadi.
5. Mijoz `/start` → ro'yxatdan o'tib, retsept yuboradi.

> **Operatorlar guruhi:** `OPERATORS_GROUP_ID` ni sozlasangiz, har bir yangi murojaat
> o'sha guruhga "Qabul qilish" tugmasi bilan tushadi. Botni guruhga admin qiling.

## 🚀 Railway'ga deploy qilish

1. **GitHub'ga yuklang** — loyihani GitHub repozitoriyasiga push qiling
   (`.env` va `*.db` `.gitignore`da — ular yuklanmaydi).

2. **Railway'da loyiha yarating**: New Project → Deploy from GitHub repo → repoyingizni tanlang.
   Railway `requirements.txt` ni topib, avtomatik o'rnatadi va `python bot.py` ni ishga tushiradi.

3. **Volume qo'shing** (ma'lumotlar saqlanishi uchun):
   - Service → **Variables** yonidagi **Volumes** → **New Volume**
   - Mount path: **`/data`**
   - Bot avtomatik bazani `/data/gulnora_farm.db` ga yozadi (`/data` aniqlansa).
     Xohlasangiz, qo'lda `DB_PATH=/data/gulnora_farm.db` o'zgaruvchisini ham qo'shing.

4. **Muhit o'zgaruvchilarini qo'shing** (Variables bo'limida):
   ```
   BOT_TOKEN=<BotFather_token>
   ADMIN_IDS=123456789
   OPERATORS_GROUP_ID=-1001234567890
   DB_PATH=/data/gulnora_farm.db
   ```
   > ⚠️ Tokenni Railway Variables'ga qo'ying, koddagi `.env.example`ga emas.

5. Railway avtomatik deploy qiladi. Loglarda `✅ Bot ishga tushdi: @...` ko'rinsa — tayyor.
   Volume tufayli yangi deploy/restartlarda ham foydalanuvchilar, murojaatlar va
   sozlamalar saqlanib qoladi.

> **Eslatma:** bir vaqtning o'zida bot faqat bitta joyda (yo lokal, yo Railway) ishlashi kerak —
> aks holda Telegram `Conflict` xatosi chiqadi. Railway'ga o'tkazsangiz, lokalni to'xtating.

## Loyiha tuzilmasi

```
bot.py              — kirish nuqtasi (routerlarni ulaydi)
config.py           — .env dan sozlamalar
states.py           — FSM holatlari
texts.py            — xabar matnlari
keyboards.py        — barcha tugmalar
utils.py            — yordamchi funksiyalar (obuna, proxy-chat)
database/
  db.py             — sxema va boshlang'ich ma'lumot
  queries.py        — barcha DB amallari
handlers/
  registration.py   — /start, ro'yxatdan o'tish, obuna, filial
  menu.py           — FAQ, Filiallar, Bog'lanish
  order.py          — retsept yuborish + mijoz proxy-chat
  operator.py       — operator kabineti
  admin.py          — admin panel
```

## Ma'lumotlar bazasi

`gulnora_farm.db` (SQLite) avtomatik yaratiladi. Jadvallar: `users`, `branches`,
`orders`, `messages`, `operators`, `faqs`, `channels`, `settings`, `status_log`.
# GulnoraFarm
