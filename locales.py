"""Ko'p tillilik (i18n): O'zbekcha / Ruscha.

t(key, lang, **kw)  -> tarjima qilingan matn
btn(key, lang)      -> tugma yozuvi
labels(*keys)       -> berilgan tugmalarning barcha tillardagi yozuvlari (to'plam)
"""

LANGUAGES = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский"}
DEFAULT_LANG = "uz"

CHOOSE_LANG = "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:"

# ============================ TUGMALAR ============================
B = {
    "register":    {"uz": "✅ Ro'yxatdan o'tish",            "ru": "✅ Регистрация"},
    "send_phone":  {"uz": "📲 Raqamni yuborish",             "ru": "📲 Отправить номер"},
    "order":       {"uz": "💊 Retsept yuborish",             "ru": "💊 Отправить рецепт"},
    "faq":         {"uz": "❓ Ko'p beriladigan savollar",     "ru": "❓ Частые вопросы"},
    "branches":    {"uz": "📍 Filiallar",                    "ru": "📍 Филиалы"},
    "contact":     {"uz": "☎️ Bog'lanish",                   "ru": "☎️ Связаться"},
    "admin":       {"uz": "👨‍💻 Admin panel",                 "ru": "👨‍💻 Админ-панель"},
    "op_cabinet":  {"uz": "👨‍⚕️ Operator kabineti",           "ru": "👨‍⚕️ Кабинет оператора"},
    "join_team":   {"uz": "🤝 Jamoamizga qo'shilish",         "ru": "🤝 Присоединиться к команде"},
    "open_vacancy":{"uz": "👉 Vakansiyalar botiga o'tish",    "ru": "👉 Перейти в бот вакансий"},
    "check_sub":   {"uz": "✅ Tekshirish",                   "ru": "✅ Проверить"},
    "map":         {"uz": "🗺 Xaritada ko'rish",             "ru": "🗺 Показать на карте"},
    "branches_back": {"uz": "🔙 Filiallar ro'yxatiga qaytish", "ru": "🔙 К списку филиалов"},
    "back":        {"uz": "🔙 Orqaga",                       "ru": "🔙 Назад"},
    "cancel":      {"uz": "🔙 Bekor qilish",                 "ru": "🔙 Отмена"},
    "confirm_yes": {"uz": "✅ Tasdiqlash",                   "ru": "✅ Подтвердить"},
    "confirm_no":  {"uz": "❌ Bekor qilish",                 "ru": "❌ Отмена"},
    "skip":        {"uz": "⏭ O'tkazib yuborish",            "ru": "⏭ Пропустить"},
}


def btn(key: str, lang: str = DEFAULT_LANG) -> str:
    item = B.get(key, {})
    return item.get(lang) or item.get(DEFAULT_LANG) or key


def labels(*keys) -> set:
    """Berilgan tugma kalitlari uchun barcha tillardagi yozuvlar to'plami."""
    out = set()
    for k in keys:
        out.update(B.get(k, {}).values())
    return out


# ============================ MATNLAR ============================
T = {
    "welcome_new": {
        "uz": ("Assalomu alaykum! 👋\n\n<b>\"Gulnora Farm\"</b> botiga xush kelibsiz!\n\n"
               "Bu bot orqali siz:\n💊 Retsept yoki dori nomini yuborib mahsulot haqida bilishingiz\n"
               "📍 Filiallarimiz bilan tanishishingiz\n☎️ Operatorlarimiz bilan bog'lanishingiz mumkin\n\n"
               "Davom etish uchun, iltimos, ro'yxatdan o'ting."),
        "ru": ("Здравствуйте! 👋\n\nДобро пожаловать в бот <b>«Gulnora Farm»</b>!\n\n"
               "Через этот бот вы можете:\n💊 Отправить рецепт или название лекарства и узнать о товаре\n"
               "📍 Ознакомиться с нашими филиалами\n☎️ Связаться с нашими операторами\n\n"
               "Для продолжения, пожалуйста, зарегистрируйтесь."),
    },
    "welcome_back": {
        "uz": "Assalomu alaykum, <b>{name}</b>! 👋\n\nBotimizga qaytganingizdan xursandmiz.\n"
              "Quyidagi menyudan kerakli bo'limni tanlang 👇",
        "ru": "Здравствуйте, <b>{name}</b>! 👋\n\nРады видеть вас снова.\n"
              "Выберите нужный раздел из меню 👇",
    },
    "ask_name": {
        "uz": "Iltimos, ism va familiyangizni kiriting.\n\nMisol: <i>Aliyev Vali</i>",
        "ru": "Пожалуйста, введите имя и фамилию.\n\nНапример: <i>Иван Петров</i>",
    },
    "bad_name": {
        "uz": "⚠️ Iltimos, to'g'ri ism-familiya kiriting (faqat harflardan iborat).",
        "ru": "⚠️ Пожалуйста, введите корректное имя и фамилию (только буквы).",
    },
    "ask_phone": {
        "uz": ("Rahmat, <b>{name}</b>! 😊\n\n"
               "Endi bog'lanish uchun telefon raqamingizni yuboring 📱\n\n"
               "Misol: <code>+998901234567</code>\n\n"
               "Agar Telegram raqamingiz va mobil raqamingiz bir xil bo'lsa, "
               "pastdagi \"📲 Raqamni yuborish\" tugmasini bosing.\n\n"
               "Agar boshqa raqam ishlatsangiz, uni qo'lda kiriting."),
        "ru": ("Спасибо, <b>{name}</b>! 😊\n\n"
               "Теперь для связи отправьте свой номер телефона 📱\n\n"
               "Пример: <code>+998901234567</code>\n\n"
               "Если ваш номер Telegram совпадает с мобильным, нажмите кнопку "
               "\"📲 Отправить номер\" ниже.\n\n"
               "Если используете другой номер, введите его вручную."),
    },
    "bad_phone": {
        "uz": "⚠️ Telefon raqam noto'g'ri kiritildi.\n\nIltimos, raqamni to'liq kiriting. "
              "Masalan: <code>+998901234567</code>",
        "ru": "⚠️ Номер введён неверно.\n\nПожалуйста, введите номер полностью. "
              "Например: <code>+998901234567</code>",
    },
    "phone_ok": {
        "uz": "✅ Ma'lumotlaringiz qabul qilindi!\n\nIsm: <b>{name}</b>\nTelefon: <b>{phone}</b>",
        "ru": "✅ Ваши данные приняты!\n\nИмя: <b>{name}</b>\nТелефон: <b>{phone}</b>",
    },
    "ask_subscribe": {
        "uz": "Botdan to'liq foydalanish uchun rasmiy kanal(lar)imizga obuna bo'ling 👇",
        "ru": "Для полноценного использования бота подпишитесь на наш(и) канал(ы) 👇",
    },
    "not_subscribed": {
        "uz": "❌ Quyidagi kanal(lar)ga hali obuna bo'lmagansiz:\n\n{channels}\n\n"
              "Barcha kanallarga obuna bo'lib, qayta \"✅ Tekshirish\" tugmasini bosing.",
        "ru": "❌ Вы ещё не подписаны на следующие канал(ы):\n\n{channels}\n\n"
              "Подпишитесь на все каналы и снова нажмите «✅ Проверить».",
    },
    "subscribed_ok": {
        "uz": "✅ Rahmat! Obuna tasdiqlandi.\n\nEndi filialingizni tanlang 👇",
        "ru": "✅ Спасибо! Подписка подтверждена.\n\nТеперь выберите филиал 👇",
    },
    "ask_branch": {
        "uz": "Sizga qaysi filial qulayroq? Iltimos, filialni tanlang:",
        "ru": "Какой филиал вам удобнее? Пожалуйста, выберите филиал:",
    },
    "branch_selected": {
        "uz": "✅ Siz <b>\"{branch}\"</b> filialini tanladingiz.\n\n"
              "Buni istalgan vaqtda \"📍 Filiallar\" bo'limidan o'zgartirishingiz mumkin.",
        "ru": "✅ Вы выбрали филиал <b>«{branch}»</b>.\n\n"
              "Изменить его можно в любое время в разделе «📍 Филиалы».",
    },
    "branch_skipped": {
        "uz": "✅ Yaxshi, filialsiz davom etamiz.\n\n"
              "Filialni keyin \"📍 Filiallar\" bo'limidan tanlashingiz mumkin.",
        "ru": "✅ Хорошо, продолжим без филиала.\n\n"
              "Вы можете выбрать филиал позже в разделе «📍 Филиалы».",
    },
    "no_branches": {
        "uz": "⚠️ Hozircha filiallar qo'shilmagan. Iltimos, keyinroq urinib ko'ring.",
        "ru": "⚠️ Филиалы пока не добавлены. Пожалуйста, попробуйте позже.",
    },
    "main_menu": {
        "uz": "🏠 <b>Asosiy menyu</b>\n\nKerakli bo'limni tanlang:",
        "ru": "🏠 <b>Главное меню</b>\n\nВыберите нужный раздел:",
    },
    "order_ask": {
        "uz": ("Retsept rasmi, hujjat (PDF) yoki dori nomini matn ko'rinishida yuboring 📝\n\n"
               "Masalan:\n— Retsept rasmini yuborishingiz mumkin\n— PDF hujjat yuborishingiz mumkin\n"
               "— Yoki shunchaki kerakli dori nomini yozishingiz mumkin"),
        "ru": ("Отправьте фото рецепта, документ (PDF) или название лекарства текстом 📝\n\n"
               "Например:\n— Можете отправить фото рецепта\n— Можете отправить PDF-документ\n"
               "— Или просто напишите название нужного лекарства"),
    },
    "order_ok_text": {
        "uz": ("✅ So'rovingiz qabul qilindi!\n\nSizning murojaatingiz operatorlarimizga yuborildi.\n"
               "Tez orada javob beramiz ⏳\n\nMurojaat raqami: <b>#{id}</b>\n\n"
               "Endi shu yerga qo'shimcha savol yoki ma'lumot yozsangiz, to'g'ridan-to'g'ri operatorga yetib boradi."),
        "ru": ("✅ Ваш запрос принят!\n\nВаше обращение отправлено нашим операторам.\n"
               "Скоро ответим ⏳\n\nНомер обращения: <b>#{id}</b>\n\n"
               "Теперь, если напишете сюда дополнительный вопрос, он напрямую попадёт оператору."),
    },
    "order_ok_photo": {
        "uz": "✅ Retsept rasmi qabul qilindi!\n\nOperatorlarimiz tez orada ko'rib chiqib, "
              "siz bilan bog'lanadi ⏳\n\nMurojaat raqami: <b>#{id}</b>",
        "ru": "✅ Фото рецепта принято!\n\nНаши операторы скоро рассмотрят и свяжутся с вами ⏳\n\n"
              "Номер обращения: <b>#{id}</b>",
    },
    "order_ok_document": {
        "uz": "✅ Hujjat qabul qilindi!\n\nOperatorlarimiz tez orada ko'rib chiqadi ⏳\n\n"
              "Murojaat raqami: <b>#{id}</b>",
        "ru": "✅ Документ принят!\n\nНаши операторы скоро рассмотрят ⏳\n\nНомер обращения: <b>#{id}</b>",
    },
    "order_ok_video": {
        "uz": "✅ Video qabul qilindi!\n\nOperatorlarimiz tez orada ko'rib chiqadi ⏳\n\n"
              "Murojaat raqami: <b>#{id}</b>",
        "ru": "✅ Видео принято!\n\nНаши операторы скоро рассмотрят ⏳\n\nНомер обращения: <b>#{id}</b>",
    },
    "order_bad_format": {
        "uz": "⚠️ Afsuski, bu formatni qabul qila olmaymiz.\n\n"
              "Iltimos, matn, rasm yoki PDF hujjat ko'rinishida yuboring.",
        "ru": "⚠️ К сожалению, этот формат мы не можем принять.\n\n"
              "Пожалуйста, отправьте текст, фото или PDF-документ.",
    },
    "order_done": {
        "uz": "✅ Murojaatingiz <b>#{id}</b> yakunlandi.\n\nXizmatimizdan foydalanganingiz uchun rahmat!\n"
              "Savolingiz bo'lsa, istalgan vaqtda yozishingiz mumkin 😊",
        "ru": "✅ Ваше обращение <b>#{id}</b> завершено.\n\nСпасибо, что воспользовались нашим сервисом!\n"
              "Если есть вопросы, пишите в любое время 😊",
    },
    "order_canceled": {
        "uz": "❌ Murojaatingiz <b>#{id}</b> bekor qilindi.\n\nAgar bu xato bo'lsa yoki qayta urinib "
              "ko'rmoqchi bo'lsangiz, \"💊 Retsept yuborish\" tugmasini bosing.",
        "ru": "❌ Ваше обращение <b>#{id}</b> отменено.\n\nЕсли это ошибка или хотите попробовать снова, "
              "нажмите «💊 Отправить рецепт».",
    },
    "operator_reply": {
        "uz": "👨‍⚕️ <b>Operator javobi:</b>\n\n{text}",
        "ru": "👨‍⚕️ <b>Ответ оператора:</b>\n\n{text}",
    },
    "rate_ask": {
        "uz": "\n\n⭐ Iltimos, ko'rsatilgan xizmatni baholang:",
        "ru": "\n\n⭐ Пожалуйста, оцените оказанную услугу:",
    },
    "rate_reason": {
        "uz": "Siz xizmatimizni <b>{n} ta yulduz</b> bilan baholadingiz: {stars}\n\n"
              "Nima sababdan shunday baho berdingiz? Fikr-mulohazangizni yozib qoldiring 👇\n\n"
              "<i>(Yoki «O'tkazib yuborish» tugmasini bosing.)</i>",
        "ru": "Вы оценили наш сервис на <b>{n} звёзд(ы)</b>: {stars}\n\n"
              "Почему вы поставили такую оценку? Напишите, пожалуйста, ваш отзыв 👇\n\n"
              "<i>(Или нажмите «Пропустить».)</i>",
    },
    "feedback_thanks": {
        "uz": "Fikringiz uchun rahmat! 🙏\nXizmatimizni yaxshilash uchun harakat qilamiz.",
        "ru": "Спасибо за ваш отзыв! 🙏\nМы постараемся улучшить наш сервис.",
    },
    "faq_menu": {
        "uz": "❓ <b>Ko'p beriladigan savollar</b>\n\nQuyidagi mavzulardan birini tanlang:",
        "ru": "❓ <b>Частые вопросы</b>\n\nВыберите одну из тем:",
    },
    "join_team_text": {
        "uz": "🤝 <b>Bizning jamoamizga qo'shiling!</b>\n\n"
              "Gulnora Farm jamoasida ishlashni xohlaysizmi? Quyidagi tugma orqali "
              "vakansiyalar botiga o'ting va ariza qoldiring 👇",
        "ru": "🤝 <b>Присоединяйтесь к нашей команде!</b>\n\n"
              "Хотите работать в команде Gulnora Farm? Нажмите кнопку ниже, чтобы перейти "
              "в бот вакансий и оставить заявку 👇",
    },
    "branches_header": {
        "uz": "📍 <b>Bizning filiallarimiz</b>\n\nQuyidagi ro'yxatdan filialni tanlang:",
        "ru": "📍 <b>Наши филиалы</b>\n\nВыберите филиал из списка:",
    },
    "branch_card": {
        "uz": "🏥 <b>{name}</b>\n\n📍 Manzil: {address}\n☎️ Telefon: {phone}\n🕐 Ish vaqti: {hours}",
        "ru": "🏥 <b>{name}</b>\n\n📍 Адрес: {address}\n☎️ Телефон: {phone}\n🕐 Время работы: {hours}",
    },
    "contact_prompt": {
        "uz": "\n\n➡️ <i>So'rovingiz yoki savolingizni shu yerga yozing — "
              "biz uni operatorlarimizga yetkazamiz.</i>",
        "ru": "\n\n➡️ <i>Напишите свой запрос или вопрос сюда — мы передадим его нашим операторам.</i>",
    },
    "contact_preview": {
        "uz": "📝 Siz yozgan ma'lumot:\n\n{preview}\n\nShu ma'lumotni operatorga yuboraylikmi?",
        "ru": "📝 Ваше сообщение:\n\n{preview}\n\nОтправить это сообщение оператору?",
    },
    "contact_bad": {
        "uz": "Iltimos, matn, rasm, video yoki hujjat yuboring.",
        "ru": "Пожалуйста, отправьте текст, фото, видео или документ.",
    },
    "contact_sent": {
        "uz": "✅ So'rovingiz qabul qilindi!\n\nMurojaat raqami: <b>#{id}</b>\n"
              "Operatorlarimiz tez orada javob beradi ⏳",
        "ru": "✅ Ваш запрос принят!\n\nНомер обращения: <b>#{id}</b>\nНаши операторы скоро ответят ⏳",
    },
    "contact_canceled": {
        "uz": "❌ Bekor qilindi. Ma'lumot yuborilmadi.",
        "ru": "❌ Отменено. Сообщение не отправлено.",
    },
    "proxy_sent": {
        "uz": "✅ Xabaringiz operatorga yuborildi.",
        "ru": "✅ Ваше сообщение отправлено оператору.",
    },
    "cancel_done": {
        "uz": "Bekor qilindi.",
        "ru": "Отменено.",
    },
    "use_menu": {
        "uz": "Buyurtma berish uchun \"💊 Retsept yuborish\" tugmasini bosing yoki menyudan foydalaning.",
        "ru": "Чтобы оформить запрос, нажмите «💊 Отправить рецепт» или воспользуйтесь меню.",
    },
    "need_register": {
        "uz": "Iltimos, avval /start orqali ro'yxatdan o'ting va filial tanlang.",
        "ru": "Пожалуйста, сначала зарегистрируйтесь через /start и выберите филиал.",
    },
    "accept_notify": {
        "uz": "👨‍⚕️ Operatorimiz murojaatingizni qabul qildi. Tez orada javob beradi.",
        "ru": "👨‍⚕️ Наш оператор принял ваше обращение. Скоро ответит.",
    },
    "bill_to_client": {
        "uz": "💊 <b>Hisob-kitob (#{id}):</b>\n\n{bill}",
        "ru": "💊 <b>Расчёт (#{id}):</b>\n\n{bill}",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    item = T.get(key, {})
    text = item.get(lang) or item.get(DEFAULT_LANG) or key
    return text.format(**kw) if kw else text
