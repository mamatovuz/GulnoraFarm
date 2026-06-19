# 📘 Gulnora Farm boti — To'liq ishlash yo'riqnomasi (TZ)

Bu hujjat botning har bir tugmasi va oqimini "buni bossa — bu bo'ladi" tarzida tushuntiradi.

Botda **3 ta rol** bor:
- 👤 **Mijoz** — oddiy foydalanuvchi (retsept/savol yuboradi)
- 👨‍⚕️ **Operator** — murojaatlarga javob beradi
- 👨‍💻 **Admin** — hamma narsani boshqaradi

---

## 1. 👤 MIJOZ QISMI

### 1.1. `/start` — botni boshlash

**Yangi foydalanuvchi `/start` bossa:**
1. Bot **til tanlashni** so'raydi:
   ```
   🇺🇿 Tilni tanlang:
   🇷🇺 Выберите язык:
      [🇺🇿 O'zbekcha]  [🇷🇺 Русский]
   ```
2. Tilni tanlagach → bot tanlangan tilda davom etadi va **ro'yxatdan o'tish** boshlanadi.

**Allaqachon ro'yxatdan o'tgan foydalanuvchi `/start` bossa:**
- Bot avval **majburiy obunani tekshiradi** (1.4-band), so'ng to'g'ridan-to'g'ri **asosiy menyuni** ochadi.

> Tilni keyin o'zgartirish: **`/til`** buyrug'i.

### 1.2. Ism-familiya kiritish
- Bot: *"Iltimos, ism va familiyangizni kiriting."*
- Foydalanuvchi yozadi (faqat harflar). Raqam/bo'sh bo'lsa → qayta so'raydi.

### 1.3. Telefon raqam
- Bot: *"Rahmat, {ism}! Endi telefon raqamingizni yuboring 📱 ..."*
- 2 xil usul:
  - **"📲 Raqamni yuborish"** tugmasi → Telegram raqamini yuboradi
  - Yoki **qo'lda** yozadi (masalan `+998901234567`) — Telegram raqami boshqa bo'lsa
- Noto'g'ri format → qayta so'raydi.

### 1.4. Majburiy obuna (agar admin kanal qo'shgan bo'lsa)
- Bot: *"...kanal(lar)imizga obuna bo'ling 👇"* + kanal havolalari + **"✅ Tekshirish"** tugmasi.
- **"✅ Tekshirish"** bossa:
  - Obuna bo'lmagan bo'lsa → ❌ ro'yxat chiqadi, qayta tekshirishni so'raydi
  - Hammasiga obuna bo'lsa → davom etadi (filial tanlash / asosiy menyu)
- ⚠️ Bu ishlashi uchun **bot kanalda admin bo'lishi shart**.
- Obuna **har `/start` da** tekshiriladi.

### 1.5. Filial tanlash
- Bot filiallar ro'yxatini va eng pastda **"⏭ O'tkazib yuborish"** tugmasini ko'rsatadi.
- **Filialni bossa** → o'sha filial profilга yoziladi
- **"⏭ O'tkazib yuborish" bossa** → filialsiz davom etadi (keyin "📍 Filiallar" dan tanlash mumkin)
- → **Asosiy menyu** ochiladi.

### 1.6. Asosiy menyu (doimiy tugmalar)
```
💊 Retsept yuborish
❓ Ko'p beriladigan savollar    📍 Filiallar
☎️ Bog'lanish
🤝 Jamoamizga qo'shilish
```
> Adminlarda qo'shimcha **👨‍💻 Admin panel**, login qilgan operatorlarda **👨‍⚕️ Operator kabineti** tugmasi ham ko'rinadi.

---

### 1.7. 💊 Retsept yuborish
1. Tugmani bossa → bot: *"Retsept rasmi, hujjat (PDF), video yoki dori nomini yuboring 📝"* + **"🔙 Bekor qilish"**.
2. Foydalanuvchi yuboradi (matn / rasm / PDF / video):
   - ✅ *"So'rovingiz qabul qilindi! Murojaat raqami: #N"*
   - Murojaat **operatorlar guruhiga** boradi (agar sozlangan bo'lsa).
3. Shundan keyin foydalanuvchi shu yerga yozsa — **to'g'ridan-to'g'ri operatorga** boradi (proxy-chat).
4. **Reply (javob):** operator aniq bir xabarga javob bersa, mijozga o'sha xabarga **tirkalgan** holda keladi — qaysi savolga javob ekani ko'rinadi.

### 1.8. ❓ Ko'p beriladigan savollar (FAQ)
- Savollar ro'yxati chiqadi → savolni bossa → javob + **"🔙 Orqaga"**.
- Admin bu bo'limni **o'chirib qo'ysa**, bu tugma menyuda umuman ko'rinmaydi.

### 1.9. 📍 Filiallar
- Filiallar ro'yxati → filialni bossa → **rasm + ma'lumot** chiqadi:
  ```
  🏥 Chilonzor filiali
  📍 Manzil: ...
  ☎️ Telefon: ...
  🕐 Ish vaqti: 09:00 — 21:00   (har filialning o'z vaqti)
     [🗺 Xaritada ko'rish]
     [🔙 Filiallar ro'yxatiga qaytish]
  ```
- **"🗺 Xaritada ko'rish"** → lokatsiya (xarita) yuboradi.

### 1.10. ☎️ Bog'lanish
1. Tugmani bossa → kontakt ma'lumotlari chiqadi + *"So'rovingizni shu yerga yozing..."*
2. Foydalanuvchi xohlagan narsasini yozadi (matn/rasm/video/hujjat)
3. Bot tasdiqlashni so'raydi:
   ```
   📝 Siz yozgan ma'lumot: ...
   Shu ma'lumotni operatorga yuboraylikmi?
      [✅ Tasdiqlash]  [❌ Bekor qilish]
   ```
   - **✅ Tasdiqlash** → operatorlar kanaliga **murojaat** sifatida boradi (retsept kabi davom etadi)
   - **❌ Bekor qilish** → hech narsa yuborilmaydi, asosiy menyuga qaytadi

### 1.11. 🤝 Jamoamizga qo'shilish
- Tugmani bossa → *"Bizning jamoamizga qo'shiling!"* + **"👉 Vakansiyalar botiga o'tish"** havola tugmasi.
- Havolani bossa → **@Gulnorafarmvacancy_bot** ochiladi.

### 1.12. Baholash (murojaat yakunlangach)
1. Operator murojaatni yakunlagach, mijozga:
   ```
   ✅ Murojaatingiz #N yakunlandi.
   ⭐ Iltimos, ko'rsatilgan xizmatni baholang:
      [1⭐] [2⭐] [3⭐] [4⭐] [5⭐]
   ```
2. Mijoz baho beradi → bot **"Nima sababdan {N} ta yulduz qo'ydingiz?"** deb so'raydi + **"⏭ O'tkazib yuborish"**.
3. Mijoz izoh yozadi (masalan *"sekin javob berildi"*) → *"Fikringiz uchun rahmat!"*
   - Baho + izoh **operatorga** va **operatorlar guruhiga** boradi, **admin tarixida** ko'rinadi.

---

## 2. 👨‍⚕️ OPERATOR QISMI

### 2.1. `/operator` — kabinetga kirish
- Bot login va parolni so'raydi (admin bergan).
- To'g'ri → operator kabineti ochiladi. Login bir marta — keyin asosiy menyuda **👨‍⚕️ Operator kabineti** tugmasi paydo bo'ladi.

### 2.2. Operator kabineti menyusi
```
📥 Yangi murojaatlar      📂 Mening murojaatlarim
✅ Yakunlanganlar         📊 Mening statistikam
🏆 Reyting                🚪 Chiqish (logout)
🔙 Bosh menyu
```

### 2.3. Yangi murojaatni qabul qilish (2 usul)

**A) Operatorlar kanali orqali (asosiy usul):**
1. Yangi murojaat kanalga **bitta xabar** bo'lib tushadi: mijoz yuborgan rasm/matn + ma'lumot kartasi + **"✅ Qabul qilish (botda ochish)"** havola tugmasi.
2. Operator tugmani bossa → **avtomatik bot ochiladi**, murojaatning to'liq ma'lumotlari va amal tugmalari operatorning shaxsiy chatida chiqadi.
3. Kanaldagi tugma o'chadi va *"✅ Murojaat #N ni {operator} qabul qildi"* deb belgilanadi.

**B) Kabinet orqali:**
- **"📥 Yangi murojaatlar"** → ro'yxat → murojaatni bossa → ma'lumot + **"✅ Qabul qilish"**.

### 2.4. Murojaat ustida ishlash (qabul qilingach)
Murojaat ochilganda amal tugmalari:
```
💬 Javob yozish            💊 Dori/retsept hisoblash
✅ Yakunlash               ❌ Bekor qilish
```
- **Oddiy yozsa ham** — har bir xabar mijozga boradi (va mijozning oxirgi xabariga avtomatik tirkaladi).
- **💬 Javob yozish** — javob rejimini eslatadi.
- **💊 Dori/retsept hisoblash** → summa/dorilarni kiritadi → mijozga yuborish yoki faqat saqlash.
- **✅ Yakunlash** → murojaat yopiladi, mijozga baholash so'rovi boradi.
- **❌ Bekor qilish** → murojaat bekor qilinadi, mijozga xabar boradi.

### 2.5. Boshqa tugmalar
- **📂 Mening murojaatlarim** — jarayondagi murojaatlar.
- **✅ Yakunlanganlar** — yopilgan murojaatlar ro'yxati.
- **📊 Mening statistikam** — qabul qilingan/yakunlangan/hisoblangan soni + **⭐ o'rtacha baho**.
- **🏆 Reyting** — operatorlar reytingi (yakunlangan + hisoblangan + baho).
- **🔙 Bosh menyu** — asosiy menyuga qaytadi (operator tizimda qoladi).
- **🚪 Chiqish (logout)** — tizimdan chiqadi (tugma yo'qoladi).

---

## 3. 👨‍💻 ADMIN QISMI

### 3.1. Kirish
- Asosiy menyudagi **👨‍💻 Admin panel** tugmasi (faqat `.env` dagi `ADMIN_IDS` ga ko'rinadi).

### 3.2. Admin panel bo'limlari
```
📊 Statistika
📨 Ommaviy xabar
📢 Kanal boshqaruvi
❓ FAQ boshqaruvi
🏥 Filiallar
👨‍⚕️ Operatorlar
📁 Murojaatlar tarixi
✏️ Bog'lanish matnini tahrirlash
```

### 3.3. 📊 Statistika
- Foydalanuvchilar (jami/bugun/hafta/oy), murojaatlar (holatlar bo'yicha), o'rtacha baho, filiallar kesimi.
- **📥 Excel hisoboti** — barcha murojaatlar `.xlsx` faylda.

### 3.4. 📨 Ommaviy xabar (broadcast)
1. Tur tanlanadi: matn / rasm / video / hujjat
2. Kontent yuboriladi
3. Kimga: **barchaga / faqat filialga / faqat faollarga**
4. Tasdiqlash → yuboriladi (yetkazildi/yetkazilmadi soni ko'rsatiladi).

### 3.5. 📢 Kanal boshqaruvi (majburiy obuna)
- **➕ Kanal qo'shish** → `@username` yoki ID yuboriladi.
  - Bot avtomatik tekshiradi: kanalni topadimi va o'zi **admin'mi**.
  - Admin emas bo'lsa → ⚠️ ogohlantiradi (obuna ishlamaydi).
- **🗑 Kanalni o'chirish** → ro'yxatdan tanlab o'chiradi.

### 3.6. ❓ FAQ boshqaruvi
- **➕ Savol qo'shish** (sarlavha + javob), **✏️ Tahrirlash**, **🗑 O'chirish**.
- **🔕 Bo'limni o'chirish / 🔔 Bo'limni yoqish** — FAQ ni menyudan yashirish/ko'rsatish.

### 3.7. 🏥 Filiallar
- **➕ Filial qo'shish**: nom → manzil → telefon → **🕐 ish vaqti** (masalan `09:00-21:00`) → lokatsiya → rasm (yoki ⏭ o'tkazish).
- **✏️ Tahrirlash** → filialni tanlab, har bir maydonni alohida o'zgartirish: nom / manzil / telefon / lokatsiya / **🕐 ish vaqti** / rasm.
- **🗑 O'chirish** — tasdiqlash bilan.

### 3.8. 👨‍⚕️ Operatorlar
- **➕ Operator qo'shish**: ism → login → parol (yoki `avto`). Login ma'lumotlari operatorga beriladi.
- **⛔ Bloklash/Faollashtirish**, **🗑 O'chirish**, **📊 Operator statistikasi**.

### 3.9. 📁 Murojaatlar tarixi
- Qidiruv: **raqam / foydalanuvchi / filial** bo'yicha.
- Raqam bo'yicha → to'liq karta: mijoz, operator, holat, **baho + izoh**, to'liq yozishma.

### 3.10. ✏️ Bog'lanish matnini tahrirlash
- "☎️ Bog'lanish" bo'limida chiqadigan matnni o'zgartiradi.

---

## 4. MUROJAAT HOLATLARI
| Holat | Belgi | Tavsif |
|---|---|---|
| Yangi | 🟡 | Yuborilgan, operator olmagan |
| Jarayonda | 🔵 | Operator qabul qilgan |
| Yakunlangan | 🟢 | Operator yopgan, baho so'ralgan |
| Bekor qilingan | 🔴 | Bekor qilingan |

---

## 5. TO'LIQ OQIM (qisqacha)
```
MIJOZ: /start → til → ism → telefon → obuna → filial(yoki skip) → MENYU
   💊 Retsept → operatorlar kanali → operator "Qabul qilish" havolasini bosadi
      → bot ochiladi → operator javob yozadi (mijozga reply bo'lib boradi)
      → ✅ Yakunlash → mijoz ⭐ baho + izoh beradi
   ☎️ Bog'lanish → yozadi → tasdiqlaydi → operatorlar kanaliga boradi
   🤝 Jamoaga qo'shilish → @Gulnorafarmvacancy_bot

OPERATOR: /operator → login → murojaat qabul qiladi → javob/hisob → yakunlaydi
ADMIN: 👨‍💻 Admin panel → statistika / broadcast / kanal / FAQ / filial / operator / tarix
```
