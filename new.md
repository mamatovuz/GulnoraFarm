# 💊 Gulnora Farm — Telegram bot tizimi

> Dorixona uchun to'liq mijozlarga xizmat ko'rsatish boti: mijoz murojaat yuboradi → operator javob beradi → admin nazorat qiladi.

---

## 1. Tizim nimadan iborat?

Bu bitta emas, **bir nechta botdan** iborat tizim. Ular bitta umumiy "miya" (server + ma'lumotlar bazasi) orqali bog'langan.

| Bot turi | Kim ishlatadi | Vazifasi |
|----------|---------------|----------|
| 🟢 **Asosiy bot** | Mijozlar va Admin | Mijoz ro'yxatdan o'tadi, retsept/savol yuboradi; admin hammasini boshqaradi |
| 🤖 **Operator botlari** (1–5 ta) | Operatorlar | Har bir operator o'z botiga kirib, mijoz murojaatlariga javob beradi |
| 📢 **Kanal** | Ichki nazorat | Barcha murojaatlar nusxasi shu yerga tushadi (jamoa ko'rib turadi) |

**Asosiy g'oya:** mijoz hech qachon operatorlar bilan to'g'ridan-to'g'ri yozishmaydi. Mijoz faqat asosiy bot bilan gaplashadi, operator esa o'z boti bilan. Tizim ularni o'rtada ko'rinmas tarzda bog'lab turadi.

---

## 2. Botni yaratish (bir martalik sozlash)

### 2.1. Asosiy botni yaratish
1. Telegramda **@BotFather** ni oching.
2. `/newbot` buyrug'ini yuboring.
3. Bot nomini va username'ini bering (masalan, `GulnoraFarm_bot`).
4. BotFather sizga **token** beradi (masalan: `12345:AbCdEf...`).
5. Bu tokenni serverdagi `.env` fayliga `BOT_TOKEN=...` qilib yozasiz.

### 2.2. Adminni belgilash
- O'zingizning Telegram ID raqamingizni (`@userinfobot` dan olasiz) `.env` faylga `ADMIN_IDS=...` qilib yozasiz.
- Bir nechta admin bo'lsa, vergul bilan ajratasiz: `ADMIN_IDS=111,222`.

### 2.3. Kanal ulash
1. Telegramda kanal oching.
2. Asosiy botni va operator botlarini kanalga **admin** qiling.
3. Kanal ID raqamini `.env` ga `OPERATORS_GROUP_ID=...` qilib yozasiz.

### 2.4. Operator botlarini qo'shish (eng muhim qism)
Har bir operator uchun **alohida bot** kerak:
1. **@BotFather** da yana bir bot yarating (masalan `GulnoraOp1_bot`) → token oling.
2. Asosiy botda **Admin → 🤖 Operator botlari → ➕ Bot qo'shish** ni bosing.
3. Bot **tokenini** yuboring.
4. Operatorga **login** bering (masalan `operator1`).
5. **Parol** bering (masalan `1234`).
6. Tayyor — operator boti ishga tushdi. Shu tarzda 4–5 tagacha bot qo'shsa bo'ladi.

> ⚠️ Har bir login faqat **o'z botiga** bog'langan. Ya'ni `operator1` faqat `GulnoraOp1_bot` orqali kira oladi.

---

## 3. Mijoz qanday foydalanadi?

1. Mijoz **asosiy botni** ochib `/start` bosadi.
2. Tilni tanlaydi (O'zbek / Rus).
3. **Ro'yxatdan o'tadi**: ism + telefon raqam + filial (yoki "📍 Eng yaqin filial" — joylashuvini yuborsa, tizim eng yaqinini topadi).
4. Asosiy menyudan kerakli bo'limni tanlaydi:
   - 💊 **Retsept yuborish** — dori nomi, rasm, ovozli xabar yoki hujjat yuboradi.
   - 🏥 **Filiallar** — manzil, telefon, ish vaqti.
   - 📍 **Eng yaqin filial** — joylashuvga ko'ra eng yaqinini topadi.
   - 📂 **Mening murojaatlarim** — oldingi murojaatlar tarixi.
   - ❓ **FAQ** — ko'p so'raladigan savollar.
   - ☎️ **Bog'lanish** — call-markaz ma'lumotlari.
5. Murojaat yuborgach: *"✅ Murojaatingiz qabul qilindi, operator tez orada javob beradi"* degan xabar oladi.
6. Operator javob bersa — mijoz uni **xuddi shu asosiy botda** oladi. Yozishuv oddiy chat kabi davom etadi.
7. Ish tugagach mijozga **baholash** chiqadi (⭐ 1–5 yulduz + izoh).

---

## 4. Murojaat qaysi yo'l bilan operatorga boradi?

Mijoz murojaat yuborganda, bir vaqtning o'zida:

1. 📢 **Kanalga** murojaat kartasi tushadi (jamoa ko'rib turadi).
2. 🤖 **Har bir operator botiga** — faqat **🟢 bo'sh** (band bo'lmagan) va tizimga kirgan operatorlarga — **"✅ Qabul qilish"** tugmasi bilan yuboriladi.

Birinchi bo'lib **"Qabul qilish"** ni bosgan operator murojaatni oladi:
- Boshqa operatorlardagi xabar **avtomatik o'chiriladi** (ikki kishi bitta murojaatni olmaydi).
- Kanaldagi karta **🔵 Jarayonda** ga o'zgaradi va kim qabul qilgani yoziladi.
- Murojaat o'sha operatorning shaxsiy chatida to'liq ochiladi.

---

## 5. Operator qanday ishlaydi?

1. Operator **o'z botini** ochadi (`/start` bossa: *"Bu operator paneli, /operator orqali kiring"*).
2. `/operator` → login va parolni kiritadi.
   - Birinchi kirgandan keyin login/parolni **saqlab qo'yishi** mumkin — keyingi safar bir bosishda kiradi.
   - Saqlangan loginni xohlasa **🗑** tugmasi bilan o'chiradi.
3. Operator kabinetida tugmalar:
   - 📥 **Yangi murojaatlar** — kutib turgan murojaatlar.
   - 📂 **Mening murojaatlarim** — qabul qilganlari.
   - 📌 **Yakunlanmagan murojaatlar** — hali yopilmaganlari.
   - ✅ **Yakunlanganlar** — tugatilganlar.
   - 📊 **Mening statistikam** — nechta qabul qilgan, bahosi.
   - 🏆 **Reyting** — operatorlar o'rtasidagi joyi.
   - 🟢/🔴 **Holatim** — "Bo'sh" yoki "Band". Band qilsa, unga yangi murojaat kelmaydi.
   - 🚪 **Chiqish** — tizimdan chiqadi.
4. Murojaatni qabul qilgach, operator:
   - Mijozga matn / rasm / tayyor javob (shablon) yuboradi.
   - 🧾 **Hisob-kitob** yuboradi.
   - 🏥 Mijozga **filial tanlatadi**.
   - 🔄 Murojaatni **boshqa operatorga uzatadi**.
   - ✅ **Yakunlaydi** — mijozga baholash chiqadi.
5. **Ish vaqti**: har bir operatorning ish vaqti bor (admin belgilaydi). Ish vaqti tugaganda operator avtomatik chiqariladi.

---

## 6. Admin nimani boshqaradi?

Asosiy botda admin uchun maxsus tugma chiqadi. Admin panelida:

- 📊 **Statistika** — foydalanuvchilar, murojaatlar, **o'rtacha javob vaqti**, o'rtacha yakunlash vaqti, baholar, filiallar kesimi.
- 📌 **Yakunlanmagan murojaatlar** — javobsiz qolganlarni ko'rish va **✅ Yakunlash**.
- 📨 **Ommaviy xabar** — barcha mijozlarga (yoki tanlangan filialga) e'lon yuborish.
- 📢 **Kanal boshqaruvi** — majburiy obuna kanallari.
- ❓ **FAQ boshqaruvi** — savol-javoblarni tahrirlash.
- 🏥 **Filiallar** — qo'shish, tahrirlash, joylashuv, ish vaqti.
- 👨‍⚕️ **Operatorlar** — operatorlarni boshqarish, ish vaqtini sozlash.
- 🤖 **Operator botlari** — yangi bot qo'shish, statistikasini ko'rish, o'chirish/o'chirib qo'yish.
- 📝 **Tayyor javoblar** — operatorlar uchun shablonlar (matn/stiker).
- 📁 **Murojaatlar tarixi** — Excel hisobot yuklab olish.
- 🕐 **Ish vaqti** sozlamalari.

---

## 7. Avtomatik imkoniyatlar

- ⚠️ **Eskalatsiya** — agar murojaat **5 daqiqada** hech bir operator tomonidan qabul qilinmasa, **adminga avtomatik eslatma** boradi.
- ⏱ **Avto-yakunlash** — operator "Avto-yakunlash" qo'ysa, mijozga ogohlantirish boradi va 10 daqiqada murojaat avtomatik yopilib, baholash chiqadi.
- 🔕 **Band operator** — "Band" holatdagi operatorga yangi murojaat yuborilmaydi.
- 🔁 **Ikki tomonlama "reply"** — operator mijozning aniq xabariga javob bersa, mijoz ham qaysi savolga javob kelganini ko'radi.

---

## 8. Soddalashtirilgan oqim (sxema)

```
MIJOZ (asosiy bot)
   │  retsept/savol yuboradi
   ▼
TIZIM ──► 📢 Kanalga karta
   │
   ├──► 🤖 Operator bot 1  (Qabul qilish)
   ├──► 🤖 Operator bot 2  (Qabul qilish)
   └──► 🤖 Operator bot 3  (Qabul qilish)
              │
   birinchi bosgan operator oladi
              │
   ├─ boshqalardan xabar o'chadi
   ├─ kanal kartasi "Jarayonda" bo'ladi
   ▼
OPERATOR ◄──────► MIJOZ   (tizim orqali yozishadi)
              │
        ✅ Yakunlash
              ▼
   MIJOZGA BAHOLASH (⭐)
```

---

## 9. Qisqacha afzalliklar

- ✅ Mijoz uchun **oddiy** — bitta bot, oddiy chat.
- ✅ Operatorlar uchun **tartibli** — har biri o'z boti, bir-biriga xalaqit bermaydi.
- ✅ Admin uchun **to'liq nazorat** — statistika, tarix, ommaviy xabar, eskalatsiya.
- ✅ **Ikki kishi bitta murojaatni olmaydi** — avtomatik taqsimlash.
- ✅ **Hech narsa yo'qolmaydi** — javobsiz murojaat adminga eslatiladi.

---

*Gulnora Farm — mijozlarga sifatli va tezkor xizmat uchun.*
