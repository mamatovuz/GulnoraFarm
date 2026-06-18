"""Bot xabarlari matnlari (ssenariy 11-bandi)."""

WELCOME_NEW = (
    "Assalomu alaykum! 👋\n\n"
    "<b>\"Gulnora Farm\"</b> botiga xush kelibsiz!\n\n"
    "Bu bot orqali siz:\n"
    "💊 Retsept yoki dori nomini yuborib maxsulot haqida bilishingiz\n"
    "📍 Filiallarimiz bilan tanishishingiz\n"
    "☎️ Operatorlarimiz bilan bog'lanishingiz mumkin\n\n"
    "Davom etish uchun, iltimos, ro'yxatdan o'ting."
)

WELCOME_BACK = (
    "Assalomu alaykum, <b>{name}</b>! 👋\n\n"
    "Botimizga qaytganingizdan xursandmiz.\n"
    "Quyidagi menyudan kerakli bo'limni tanlang 👇"
)

ASK_NAME = "Iltimos, ism va familiyangizni kiriting.\n\nMisol: <i>Aliyev Vali</i>"
BAD_NAME = "⚠️ Iltimos, to'g'ri ism-familiya kiriting (faqat harflardan iborat)."

ASK_PHONE = (
    "Rahmat, <b>{name}</b>!\n\n"
    "Endi bog'lanish uchun telefon raqamingizni <b>qo'lda kiriting</b> 📱\n\n"
    "Masalan: <code>+998901234567</code>\n\n"
    "(Telegram raqamingiz boshqa bo'lsa, mobil raqamingizni yozing. "
    "Yoki pastdagi tugma orqali Telegram raqamingizni yuborishingiz ham mumkin.)"
)
BAD_PHONE = (
    "⚠️ Telefon raqam noto'g'ri kiritildi.\n\n"
    "Iltimos, raqamni to'liq kiriting. Masalan: <code>+998901234567</code>"
)
PHONE_OK = "✅ Ma'lumotlaringiz qabul qilindi!\n\nIsm: <b>{name}</b>\nTelefon: <b>{phone}</b>"

ASK_SUBSCRIBE = "Botdan to'liq foydalanish uchun rasmiy kanal(lar)imizga obuna bo'ling 👇"
NOT_SUBSCRIBED = (
    "❌ Quyidagi kanal(lar)ga hali obuna bo'lmagansiz:\n\n{channels}\n\n"
    "Barcha kanallarga obuna bo'lib, qayta \"✅ Tekshirish\" tugmasini bosing."
)
SUBSCRIBED_OK = "✅ Rahmat! Obuna tasdiqlandi.\n\nEndi filialingizni tanlang 👇"

ASK_BRANCH = "Sizga qaysi filial qulayroq? Iltimos, filialni tanlang:"
BRANCH_SELECTED = (
    "✅ Siz <b>\"{branch}\"</b> filialini tanladingiz.\n\n"
    "Buni istalgan vaqtda \"📍 Filiallar\" bo'limidan o'zgartirishingiz mumkin."
)
NO_BRANCHES = "⚠️ Hozircha filiallar qo'shilmagan. Iltimos, keyinroq urinib ko'ring."

MAIN_MENU = "🏠 <b>Asosiy menyu</b>\n\nKerakli bo'limni tanlang:"

# Retsept
ORDER_ASK = (
    "Retsept rasmi, hujjat (PDF) yoki dori nomini matn ko'rinishida yuboring 📝\n\n"
    "Masalan:\n"
    "— Retsept rasmini yuborishingiz mumkin\n"
    "— PDF hujjat yuborishingiz mumkin\n"
    "— Yoki shunchaki kerakli dori nomini yozishingiz mumkin"
)
ORDER_OK_TEXT = (
    "✅ So'rovingiz qabul qilindi!\n\n"
    "Sizning murojaatingiz operatorlarimizga yuborildi.\n"
    "Tez orada javob beramiz ⏳\n\n"
    "Murojaat raqami: <b>#{id}</b>\n\n"
    "Endi shu yerga qo'shimcha savol yoki ma'lumot yozsangiz, "
    "to'g'ridan-to'g'ri operatorga yetib boradi."
)
ORDER_OK_PHOTO = (
    "✅ Retsept rasmi qabul qilindi!\n\n"
    "Operatorlarimiz tez orada ko'rib chiqib, siz bilan bog'lanadi ⏳\n\n"
    "Murojaat raqami: <b>#{id}</b>"
)
ORDER_OK_DOC = (
    "✅ Hujjat qabul qilindi!\n\n"
    "Operatorlarimiz tez orada ko'rib chiqadi ⏳\n\n"
    "Murojaat raqami: <b>#{id}</b>"
)
ORDER_OK_VIDEO = (
    "✅ Video qabul qilindi!\n\n"
    "Operatorlarimiz tez orada ko'rib chiqadi ⏳\n\n"
    "Murojaat raqami: <b>#{id}</b>"
)
ORDER_BAD_FORMAT = (
    "⚠️ Afsuski, bu formatni qabul qila olmaymiz.\n\n"
    "Iltimos, matn, rasm yoki PDF hujjat ko'rinishida yuboring."
)
ORDER_DONE_CLIENT = (
    "✅ Murojaatingiz <b>#{id}</b> yakunlandi.\n\n"
    "Xizmatimizdan foydalanganingiz uchun rahmat!\n"
    "Savolingiz bo'lsa, istalgan vaqtda yozishingiz mumkin 😊"
)
ORDER_CANCELED_CLIENT = (
    "❌ Murojaatingiz <b>#{id}</b> bekor qilindi.\n\n"
    "Agar bu xato bo'lsa yoki qayta urinib ko'rmoqchi bo'lsangiz, "
    "\"💊 Retsept yuborish\" tugmasini bosing."
)
OPERATOR_REPLY_TO_CLIENT = "👨‍⚕️ <b>Operator javobi:</b>\n\n{text}"

RATE_ASK = "\n\n⭐ Iltimos, ko'rsatilgan xizmatni baholang:"
RATE_THANKS = "Bahoyingiz uchun rahmat! 🙏\n\nSizning bahoyingiz: {stars}"

# FAQ
FAQ_MENU = "❓ <b>Ko'p beriladigan savollar</b>\n\nQuyidagi mavzulardan birini tanlang:"

# Bog'lanish (sozlamalardan o'qiladi)

# Admin
NO_ADMIN = "⛔ Sizda admin huquqi yo'q."
ADMIN_MENU = "👨‍💻 <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:"

# Operator
OP_LOGIN_BAD = "❌ Login yoki parol xato. Qayta urinib ko'ring."
