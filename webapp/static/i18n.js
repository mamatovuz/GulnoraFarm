/* Gulnora Farm operator paneli — til (O'zbekcha / Русский).
 *
 * Kod ichidagi matnlar o'zbekcha yoziladi. Til ruscha bo'lsa:
 *   • T("matn", {o'zgaruvchi}) — JS ichidagi matnni tarjima qiladi;
 *   • sahifaga qo'shilgan har bir matn/placeholder avtomatik tarjima qilinadi (MutationObserver),
 *     shuning uchun ro'yxatlar, menyular, oynalar ham ruscha chiqadi.
 * Mijoz yozgan matnlar (xabarlar, ismlar, fayl nomlari) tarjima qilinmaydi.
 */
(function(){
"use strict";
const tgw = (window.Telegram && window.Telegram.WebApp) || {};
function lsGet(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
let LANG = lsGet("op_lang");
if(LANG !== "uz" && LANG !== "ru"){
  const lc = ((tgw.initDataUnsafe && tgw.initDataUnsafe.user && tgw.initDataUnsafe.user.language_code) || navigator.language || "uz").toLowerCase();
  LANG = lc.startsWith("ru") ? "ru" : "uz";
}
document.documentElement.lang = LANG;

const RU = {
  // umumiy
  "Chatlar":"Чаты","Mijozlarim":"Мои клиенты","Profil":"Профиль","Qidiruv":"Поиск","Menyu":"Меню",
  "Hammasi":"Все","Javobsiz":"Без ответа","Yakunlangan":"Завершённые","Arxiv":"Архив","Pauza":"Пауза",
  "Saqlash":"Сохранить","Bekor":"Отмена","Tayyor":"Готово","Xatolik":"Ошибка","O'chirish":"Удалить",
  "Yuborish":"Отправить","Kirish":"Войти","Login":"Логин","Parol":"Пароль","Chiqish":"Выйти",
  "Operator paneli":"Панель оператора","Gulnora Farm CRM":"Gulnora Farm CRM",
  "Boshqa hisob bilan kirish":"Войти с другим аккаунтом","Saqlangan hisobni o'chirish":"Удалить сохранённый аккаунт",
  "Login va parolni kiriting":"Введите логин и пароль","Login yoki parol xato":"Неверный логин или пароль",
  "Internet aloqasi yo'q":"Нет подключения к интернету","Hisob bloklangan":"Аккаунт заблокирован",
  "Sessiya tugagan — parol bilan kiring.":"Сессия истекла — войдите с паролем.",
  "Sessiya tugadi yoki ish vaqti tugadi. Qayta kiring.":"Сессия или рабочее время закончились. Войдите снова.",
  "Hisobdan chiqasizmi?":"Выйти из аккаунта?","Ulanmoqda...":"Соединение...",
  "Server javobi noto'g'ri":"Неверный ответ сервера",
  // chatlar ro'yxati
  "Qidiruv: ism, telefon yoki matn":"Поиск: имя, телефон или текст","Yangi murojaatlar":"Новые обращения",
  "Yangi murojaatlar shu yerda paydo bo'ladi":"Новые обращения появятся здесь",
  "Qoralama:":"Черновик:","Siz:":"Вы:","Siz":"Вы","Qadash":"Закрепить","Olib tashlash":"Открепить",
  "O'qilgan":"Прочитано","O'qilmagan":"Непрочитано","Arxivdan":"Из архива",
  "Yakunlangan suhbatlar yo'q":"Нет завершённых диалогов","Arxiv bo'sh.":"Архив пуст.",
  "Chatni chapga surib «Arxiv»ni bosing.":"Смахните чат влево и нажмите «Архив».",
  "Hamma mijozlarga javob berilgan":"Всем клиентам ответили","Pauzadagi suhbat yo'q":"Нет диалогов на паузе",
  "Faol suhbat yo'q.":"Нет активных диалогов.","Yangi murojaatlar yuqoridagi bo'limda.":"Новые обращения — в разделе выше.",
  "Ochish":"Открыть","Qadashni olib tashlash":"Открепить","O'qilgan deb belgilash":"Отметить прочитанным",
  "O'qilmagan deb belgilash":"Отметить непрочитанным","Arxivlash":"В архив","Arxivdan chiqarish":"Вернуть из архива",
  "Yakunlash":"Завершить","Chatni o'chirish":"Удалить чат","Arxivga o'tkazildi":"Перемещено в архив",
  "Saqlanmadi":"Не сохранено","Mijozlar":"Клиенты","Pauzada":"На паузе","Ism yoki telefon":"Имя или телефон",
  "Siz qabul qilgan mijozlar shu yerda ko'rinadi":"Здесь появятся принятые вами клиенты",
  "Chatni tanlang":"Выберите чат",
  "Chap tomondagi ro'yxatdan suhbatni oching yoki yangi murojaatni qabul qiling":"Откройте диалог из списка слева или примите новое обращение",
  "Du":"Пн","Se":"Вт","Ch":"Ср","Pa":"Чт","Ju":"Пт","Sh":"Сб","Ya":"Вс",
  // chat
  "Xabar":"Сообщение","Yozishmadan qidirish":"Поиск по переписке","Bugun":"Сегодня","Kecha":"Вчера",
  "O'qilmagan xabarlar":"Непрочитанные сообщения","Oldingi xabarlar yuklanmoqda...":"Загрузка предыдущих сообщений...",
  "Hali xabar yo'q":"Сообщений пока нет","tahrirlangan":"изменено","Yuborilmadi":"Не отправлено",
  "yuklanmoqda...":"загрузка...","yakunlangan":"завершено","bekor qilingan":"отменено",
  "Yuklab bo'lmadi.":"Не удалось загрузить.","Qayta urinish":"Повторить",
  "🚚 Yetkazib berish":"🚚 Доставка","🏃 Olib ketish":"🏃 Самовывоз","Yetkazib berish":"Доставка",
  "📌 Qadalgan xabar":"📌 Закреплённое сообщение","Mijoz haqida izoh":"Заметка о клиенте","Javob":"Ответ",
  "Tahrirlash":"Редактирование","Javob berish":"Ответить","Nusxa olish":"Копировать","Qadash ":"Закрепить",
  "Ochish / yuklab olish":"Открыть / скачать","Yuklab olish":"Скачать","O'chirish (mijozda ham)":"Удалить (и у клиента)",
  "Nusxa olindi":"Скопировано","Xabar qadaldi":"Сообщение закреплено","Qadash olib tashlandi":"Сообщение откреплено",
  "Xabar mijozda ham o'chiriladi. O'chirasizmi?":"Сообщение удалится и у клиента. Удалить?","O'chirilmadi":"Не удалено",
  "Xabar eskiroq — yuqoriga aylantiring":"Сообщение старее — прокрутите вверх","Bajarilmadi":"Не выполнено",
  "Bu murojaat yakunlangan":"Это обращение завершено","Bu murojaat bekor qilingan":"Это обращение отменено",
  "Yozishni davom ettirish":"Продолжить переписку","Ochilmadi":"Не удалось открыть",
  "Yuborilmadi — internetni tekshiring":"Не отправлено — проверьте интернет",
  "Saqlanmadi, qaytadan urinib ko'ring":"Не сохранено, попробуйте ещё раз",
  "Lokatsiya · xaritada ochish":"Локация · открыть на карте","ochish":"открыть",
  "Ichki izoh":"Внутренняя заметка","mijoz ko'rmaydi":"клиент не видит","Admin":"Админ","Operator":"Оператор",
  "📷 Rasm":"📷 Фото","🎥 Video":"🎥 Видео","📄 Hujjat":"📄 Документ","🎤 Ovozli xabar":"🎤 Голосовое",
  "🎵 Audio":"🎵 Аудио","🎭 Stiker":"🎭 Стикер","🎞 GIF":"🎞 GIF","📍 Lokatsiya":"📍 Локация","👤 Kontakt":"👤 Контакт",
  "📹 Video-xabar":"📹 Видеосообщение","📎 Fayl":"📎 Файл","Mijoz":"Клиент","Xabar":"Сообщение",
  // menyular
  "Mijoz kartasi":"Карточка клиента","Teglar":"Теги","Ichki izoh (mijoz ko'rmaydi)":"Внутренняя заметка (клиент не видит)",
  "Eslatma qo'yish":"Поставить напоминание","Boshqa operatorga o'tkazish":"Передать другому оператору",
  "Pauzaga qo'yish":"Поставить на паузу","Pauzadan chiqarish":"Снять с паузы","Dori katalogi":"Каталог лекарств",
  "Hisob-kitob yaratish":"Создать счёт",
  "Murojaatni yakunlaysizmi? Mijozga baholash yuboriladi.":"Завершить обращение? Клиенту отправится оценка.",
  "Yakunlab bo'lmadi. Internetni tekshiring.":"Не удалось завершить. Проверьте интернет.",
  "Murojaat yakunlandi ✓":"Обращение завершено ✓","Chat ro'yxatdan o'chirilsinmi?":"Удалить чат из списка?",
  // biriktirish
  "Biriktirish":"Прикрепить","Rasm":"Фото","Bir nechta tanlash mumkin (albom)":"Можно выбрать несколько (альбом)",
  "Fayl / PDF":"Файл / PDF","Hujjat, PDF, video (maks 15 MB)":"Документ, PDF, видео (до 15 МБ)",
  "Tayyor javob":"Готовый ответ","Filial ma'lumoti":"Информация о филиале","Hisob-kitob":"Счёт",
  "Narx va mavjudlik · kelganda xabar berish":"Цена и наличие · уведомить о поступлении",
  "Ro'yxat × soni = jami, chiroyli karta":"Список × кол-во = итог, красивая карточка",
  "Hisob-kitob (erkin matn / rasm / ovoz)":"Счёт (свободный текст / фото / голос)",
  "Fayl juda katta (maks 15 MB)":"Файл слишком большой (до 15 МБ)","Yuborildi ✓":"Отправлено ✓",
  "Rasm yuborish":"Отправить фото","Izoh qo'shing...":"Добавьте подпись...","Yuborilmoqda...":"Отправка...",
  "Filialni tanlang":"Выберите филиал",
  // buyruqlar
  "10 daqiqada avto-yakunlash":"Автозавершение через 10 минут","Mijozga filial tanlatish":"Попросить клиента выбрать филиал",
  "Filial ma'lumotini yuborish":"Отправить информацию о филиале","Hisob-kitob yuborish":"Отправить счёт",
  "Bunday buyruq yo'q. Ro'yxat uchun / yozing":"Такой команды нет. Наберите / для списка",
  "Hisob-kitob: matn yozing yoki rasm/ovoz/stiker yuboring":"Счёт: напишите текст или отправьте фото/голос/стикер",
  "Hisob-kitob rejimi":"Режим счёта","Hisob-kitob yuborildi":"Счёт отправлен",
  // tayyor javoblar / stikerlar
  "Tayyor javoblar":"Готовые ответы","Stikerlar":"Стикеры","MENIKI":"МОЁ","Darhol yuborish":"Отправить сразу",
  "Yangi shablon qo'shish":"Добавить шаблон","Yangi tayyor javob":"Новый готовый ответ","Shablon qo'shildi":"Шаблон добавлен",
  "Shablon o'chirilsinmi?":"Удалить шаблон?","Tayyor javoblarim":"Мои готовые ответы","Shaxsiy shablonlar":"Личные шаблоны",
  "Hali shaxsiy shablon yo'q":"Личных шаблонов пока нет","+ Shablon qo'shish":"+ Добавить шаблон",
  "Stiker yo'q. Admin panel → Tayyor javoblar → stiker qo'shing.":"Стикеров нет. Админ-панель → Готовые ответы → добавьте стикер.",
  // teglar / izoh / o'tkazish
  "Murojaat teglari":"Теги обращения","+ Yangi":"+ Новый","Yangi teg":"Новый тег","Teglar saqlandi":"Теги сохранены",
  "Ichki izoh (mijoz ko'rmaydi) ":"Внутренняя заметка (клиент не видит)","Izoh qo'shildi":"Заметка добавлена",
  "Kimga o'tkazamiz?":"Кому передать?","Boshqa faol operator yo'q":"Других активных операторов нет",
  "bo'sh":"свободен","band":"занят","oflayn":"офлайн","Ro'yxat yuklanmadi":"Список не загрузился","O'tkazildi":"Передано",
  "Izoh (ixtiyoriy): nima kelishildi":"Комментарий (необязательно): о чём договорились",
  // mijoz kartasi
  "Ma'lumot topilmadi":"Данные не найдены","Filial tanlanmagan":"Филиал не выбран","Qo'ng'iroq qilish":"Позвонить",
  "Izoh":"Заметка","Murojaatlari":"Обращения","Murojaat yo'q":"Обращений нет","Yangi":"Новое","Jarayonda":"В работе",
  "Yakunlangan ":"Завершено","Mijoz Telegram username qo'ymagan":"У клиента нет username в Telegram",
  "Masalan: doimiy mijoz, diabetik, faqat naqd to'laydi":"Например: постоянный клиент, диабетик, платит только наличными",
  "Saqlandi":"Сохранено","Izoh (ixtiyoriy): masalan, narxni aytish":"Комментарий (необязательно): например, сообщить цену",
  "15 daqiqadan keyin":"Через 15 минут","1 soatdan keyin":"Через 1 час","3 soatdan keyin":"Через 3 часа","Ertaga 09:00 da":"Завтра в 09:00",
  // ovoz
  "‹ Bekor qilish uchun chapga suring":"‹ Смахните влево для отмены","Bosib turing — ovoz yozish":"Удерживайте — запись голоса",
  "Mikrofon mavjud emas":"Микрофон недоступен","Mikrofonga ruxsat berilmadi":"Нет доступа к микрофону",
  "Bu qurilma ovoz yozishni qo'llamaydi":"Устройство не поддерживает запись голоса","Ovoz yozib bo'lmadi":"Не удалось записать голос",
  "Ovoz juda qisqa":"Голосовое слишком короткое","✖ ijro etilmadi":"✖ не воспроизводится",
  // kanal
  "Qabul qilish":"Принять","Qabul qilinmoqda...":"Принимаем...","Qabul qilinmadi":"Не принято",
  "Hozircha yangi murojaat yo'q":"Новых обращений пока нет","Boshqa operator qabul qildi":"Другой оператор уже принял",
  // profil
  "Qabul":"Принято","Yakun":"Завершено","Baho":"Оценка","Holatim":"Мой статус","Ovoz":"Звук","Baland":"Громко","Past":"Тихо",
  "O'chiq":"Выкл","Mavzu":"Тема","Avto":"Авто","Yorug'":"Светлая","Tungi":"Тёмная","Til":"Язык",
  "Chat foni":"Фон чата","Tayyor fonlar yoki o'z rasmingiz":"Готовые фоны или своё фото",
  "Mening haftam":"Моя неделя","kunlik yakunlar":"завершения по дням",
  "Bu hafta hali yakunlangan murojaat yo'q.":"На этой неделе ещё нет завершённых обращений.","Birinchisini yakunlang 💪":"Завершите первое 💪",
  "Yakunlanmagan murojaatlar":"Незавершённые обращения","Suhbatlar tarixi":"История диалогов","So'nggi baholarim":"Мои последние оценки",
  "Reyting (operatorlar)":"Рейтинг (операторы)","Reyting":"Рейтинг","Hali baho yo'q":"Оценок пока нет","Bo'sh":"Пусто",
  "Bo'sh — yangi murojaatlar keladi":"Свободен — новые обращения поступают","Band — yangi murojaat kelmaydi":"Занят — новые обращения не поступают",
  "Qidiruv (ism, telefon yoki #raqam)":"Поиск (имя, телефон или #номер)","siznikida":"у вас","🔴 Bekor · ":"🔴 Отменено · ","🟢 Yakun · ":"🟢 Завершено · ",
  "(siz)":"(вы)","Bugungi maqsad":"Цель на сегодня","Barakalla! Maqsad bajarildi 🎉":"Отлично! Цель выполнена 🎉",
  // fon
  "Xiralashtirish":"Размытие","Qorong'ilik":"Затемнение","O'z rasmingiz":"Своё фото","Fon saqlandi":"Фон сохранён",
  "Yuklanmoqda...":"Загрузка...","Rasm o'rnatildi":"Фото установлено","Yuklanmadi":"Не загрузилось",
  "Assalomu alaykum! Dori bormi?":"Здравствуйте! Лекарство есть?","Ha, bor. Narxi 45 000 so'm 💊":"Да, есть. Цена 45 000 сум 💊",
  "Gulnora":"Gulnora","Yalpiz":"Мята","Okean":"Океан","Shafaq":"Закат","Lavanda":"Лаванда","Qum":"Песок","Tun":"Ночь","Oddiy":"Простой",
  // formatlash (fmt.js)
  "Formatlash":"Форматирование","Formatlash uchun matnni belgilang":"Выделите текст для форматирования","Qalin":"Жирный",
  "Kursiv":"Курсив","Tagiga chizilgan":"Подчёркнутый","Ustidan chizilgan":"Зачёркнутый","Monospace":"Моноширинный",
  "Spoiler (yashirin)":"Спойлер (скрытый)","Iqtibos":"Цитата","Havola qo'shish":"Добавить ссылку","Oddiy matn":"Обычный текст",
  "Kesish":"Вырезать","Qo'yish":"Вставить","Hammasini belgilash":"Выделить всё","Havola":"Ссылка","Matn":"Текст",
  // pauza
  "Suhbatni pauzaga qo'yish":"Поставить диалог на паузу",
  "Chat yopilmaydi. Pauzada o'tgan vaqt javob va yakunlash statistikasiga kirmaydi. Mijoz yozsa yoki vaqt tugasa — pauza o'zi tugaydi.":
    "Чат не закрывается. Время на паузе не учитывается в статистике ответа и завершения. Если клиент напишет или время выйдет — пауза снимется сама.",
  "Sabab":"Причина","Qachongacha":"До какого времени","Mijoz keyinroq yozadi":"Клиент напишет позже","Mijoz ertaga yozadi":"Клиент напишет завтра",
  "Dori kutilmoqda":"Ожидаем лекарство","Mijoz o'ylab ko'radi":"Клиент подумает","To'lov kutilmoqda":"Ожидаем оплату","Narx aniqlanmoqda":"Уточняем цену",
  "+ Boshqa":"+ Другое","1 soat":"1 час","3 soat":"3 часа","Ertaga 09:00":"Завтра 09:00","Muddatsiz":"Без срока",
  "Mijozga «suhbat vaqtincha to'xtatildi» deb xabar berish":"Сообщить клиенту «диалог временно приостановлен»",
  "Pauza sababi":"Причина паузы","Masalan: shifokor bilan maslahatlashadi":"Например: посоветуется с врачом",
  "Suhbat pauzaga qo'yildi — bu vaqt statistikaga kirmaydi":"Диалог на паузе — это время не учитывается в статистике",
  "Suhbat davom ettirildi":"Диалог продолжен","davom etmoqda":"продолжается","⏸ Pauza":"⏸ Пауза",
  "⏸ Suhbat pauzada — vaqt statistikaga kirmaydi":"⏸ Диалог на паузе — время не учитывается","▶ Davom ettirish":"▶ Продолжить",
  "Murojaat yopilgan":"Обращение закрыто","Bu sizning suhbatingiz emas":"Это не ваш диалог",
  // katalog / hisob-kitob
  "Dori nomi (lotin yoki kirill)":"Название лекарства (латиница или кириллица)","Topilmadi":"Не найдено","bor":"есть","yo'q":"нет",
  "Katalog bo'sh. Admin panel → Sozlamalar → Dori katalogi orqali Excel yuklang.":"Каталог пуст. Загрузите Excel: Админ-панель → Настройки → Каталог лекарств.",
  "Matnga qo'shish":"Вставить в текст","Hisobga qo'shish":"Добавить в счёт","Kelganda xabar berish":"Уведомить о поступлении",
  "Hisob-kitobga qaytish":"Вернуться к счёту","hozircha yo'q":"пока нет в наличии","so'm":"сум",
  "Dori kelganda mijozga xabar boradi":"Клиент получит уведомление о поступлении",
  "Dori nomi":"Название","narx":"цена","Ro'yxat bo'sh — katalogdan qo'shing":"Список пуст — добавьте из каталога",
  "Katalogdan":"Из каталога","Qo'lda":"Вручную","Izoh (ixtiyoriy): masalan, 30 daqiqada tayyor":"Комментарий (необязательно): например, готово через 30 минут",
  "Jami":"Итого","Mijozga yuborish":"Отправить клиенту","Tozalash":"Очистить","Hisob-kitob tozalansinmi?":"Очистить счёт?",
  "Ro'yxat bo'sh":"Список пуст",
  // server xabarlari
  "Murojaat topilmadi":"Обращение не найдено","Bu murojaat allaqachon yopilgan":"Обращение уже закрыто",
  "Yakunlab bo'lmadi, qayta urinib ko'ring":"Не удалось завершить, попробуйте ещё раз","mijozga yuborilmadi (bloklagan bo'lishi mumkin)":"не отправлено клиенту (возможно, заблокировал бота)",
  "bot tayyor emas":"бот не готов","Matn bo'sh":"Текст пустой","Xabar topilmadi":"Сообщение не найдено",
  "Faqat o'zingizning shabloningizni o'chira olasiz":"Можно удалять только свои шаблоны",
  "Mijozda o'chirib bo'lmadi (48 soatdan oshgan)":"Не удалось удалить у клиента (прошло более 48 часов)",
  "Tahrirlab bo'lmadi (48 soatdan oshgan)":"Не удалось изменить (прошло более 48 часов)",
  "Bu xabarni o'chirib bo'lmaydi":"Это сообщение нельзя удалить","Faqat o'z matnli xabaringizni tahrirlash mumkin":"Можно редактировать только свои текстовые сообщения",
  "Mijozga filial tanlash so'rovi yuborildi":"Клиенту отправлен запрос выбрать филиал","Filial ma'lumoti yuborildi":"Информация о филиале отправлена",
  "Hisob-kitob matni bo'sh":"Текст счёта пустой","ovoz yuborilmadi (format qo'llanmadi)":"голосовое не отправлено (формат не поддерживается)",
  "Juda ko'p noto'g'ri urinish.":"Слишком много неверных попыток.","topilmadi":"не найдено","yopilgan":"закрыто",
  "🚚 Yetkazib berish belgilandi":"🚚 Отмечена доставка","🏃 Olib ketish belgilandi":"🏃 Отмечен самовывоз","Belgi olib tashlandi":"Отметка снята",
  "Chiqarildi ✅":"Выполнено ✅",
  "Bekor qilingan":"Отменённые","🚫 Otkaz":"🚫 Отказ","Otkaz":"Отказ","Bekor qilingan murojaatlar yo'q":"Нет отменённых обращений",
  "Otkaz qilingan murojaatlar yo'q":"Нет обращений с отказом","Otkaz (kanalga, chat ochiq qoladi)":"Отказ (в канал, чат остаётся открытым)",
  "Bekor qilish":"Отменить обращение","Murojaat bekor qilinsinmi? Mijozga «bekor qilindi» xabari boradi.":"Отменить обращение? Клиент получит сообщение об отмене.",
  "Murojaat bekor qilindi":"Обращение отменено","Bekor qilindi":"Отменено",
  "Отказ: murojaat Отказ kanaliga joylanadi. Chat ochiq qoladi — davom ettirishingiz mumkin. Davom etamizmi?":"Отказ: обращение будет отправлено в канал отказов. Чат останется открытым — можно продолжить. Продолжить?",
  "Отказ belgilandi — chat ochiq qoladi":"Отказ отмечен — чат остаётся открытым",
  "Eslatma (faqat ish vaqtimda)":"Напоминание (только в моё рабочее время)","har 30 daqiqa":"каждые 30 мин","har 1 soat":"каждый час",
  "har 2 soat":"каждые 2 часа","har 1 kun":"раз в день","kerak emas":"не нужно","har {t}":"каждые {t}","{n} kun":"{n} дн","{n} soat":"{n} ч",
  "O'chirish (mijozdan ham)":"Удалить (и у клиента)","O'chirish (faqat yozishmadan)":"Удалить (только из переписки)",
  "Bu xabar mijoz chatida topilmadi — faqat yozishmadan o'chiriladi. O'chirasizmi?":"Это сообщение не найдено в чате клиента — удалится только из переписки. Удалить?",
  "Xabar mijozdan ham o'chirildi":"Сообщение удалено и у клиента","Xabar yozishmadan o'chirildi":"Сообщение удалено из переписки","O'chirildi":"Удалено",
  "⏸ Suhbat pauzada":"⏸ Диалог на паузе","mijoz yozdi":"клиент написал","operator davom ettirdi":"оператор продолжил",
  "vaqt tugadi":"время вышло","yakunlandi":"завершено","ro'yxatdan":"регистрация","Filial tanlanmagan":"Филиал не выбран",
  "Bosing — maydonga qo'yiladi · ➤ — darhol yuboriladi ·":"Нажмите — вставится в поле · ➤ — отправится сразу ·",
  "o'zgaruvchilari ishlaydi":"— переменные подставляются","Chatda ⚡ tugmasi orqali ishlatiladi.":"Используются в чате через кнопку ⚡.",
  "— avtomatik almashtiriladi.":"— подставляются автоматически.","O'zbekcha":"O'zbekcha","Pauza":"Пауза","Rasmni yuklab bo'lmadi":"Не удалось загрузить фото","Rasm topilmadi":"Фото не найдено",
};
// o'zgaruvchili / qolipli matnlar
const RX = [
  [/^(\d+) ta yangi$/, "$1 новых"],
  [/^(\d+) ta murojaat qabul qilinishini kutyapti$/, "$1 обращ. ожидают принятия"],
  [/^Javob: (.+)$/, "Ответ: $1"],
  [/^(\d+) ta rasm$/, "$1 фото"],
  [/^(\d+) ta rasm yuborilmoqda\.\.\.$/, "Отправка $1 фото..."],
  [/^(.*) · (\d+) murojaat$/, "$1 · обращений: $2"],
  [/^(\d+) ta ochiq suhbat$/, "открытых диалогов: $1"],
  [/^ro'yxatdan: (.*)$/, "регистрация: $1"],
  [/^Yuborilmoqda: (.*)$/, "Отправка: $1"],
  [/^(\d+) yakun · (\d+) ball(.*)$/, "$1 заверш. · $2 балл.$3"],
  [/^@(\S+) · ish vaqti (.*)$/, "@$1 · рабочее время $2"],
  [/^(.+) ga o'tkazish$/, "Передать: $1"],
  [/^#(\d+) → (.+) ga o'tkazildi$/, "#$1 → передано: $2"],
  [/^Eslatma qo'yildi — (\d+) daqiqadan keyin botda xabar keladi$/, "Напоминание поставлено — через $1 мин придёт сообщение в боте"],
  [/^Eslatma qo'yildi — (\d+) soatdan keyin botda xabar keladi$/, "Напоминание поставлено — через $1 ч придёт сообщение в боте"],
  [/^(\d+) daqiqada avto-yakunlash yoqildi$/, "Автозавершение через $1 мин включено"],
  [/^Hozir ish vaqtingiz emas\.\nIsh vaqtingiz: (.*)\. Faqat shu oraliqda kira olasiz\.$/, "Сейчас не ваше рабочее время.\nВаше время: $1. Войти можно только в этот период."],
  [/^Juda ko'p noto'g'ri urinish\. (\d+) daqiqadan keyin qayta urining\.$/, "Слишком много неверных попыток. Повторите через $1 мин."],
];
// T() bilan ishlatiladigan qoliplar ({n} kabi o'zgaruvchilar)
Object.assign(RU, {
  "{t} gacha":"до {t}","{n} daq":"{n} мин","{h} soat {m} daq":"{h} ч {m} мин",
  "Hisobga qo'shildi: {n}":"Добавлено в счёт: {n}","«{n}» kelganda mijozga avtomatik xabar yuborilsinmi?":"Отправить клиенту уведомление, когда «{n}» поступит?",
  "Mijozga {s} so'mlik hisob-kitob yuborilsinmi?":"Отправить клиенту счёт на {s} сум?","{n} ta dori qo'shildi":"Добавлено лекарств: {n}",
  "Yana {n} ta murojaat yakunlang":"Осталось завершить: {n}",
});

function core(s){
  const m = /^([^\p{L}\d#@+]*)([\s\S]*?)([^\p{L}\d)%»"]*)$/u.exec(s);
  return m ? [m[1], m[2], m[3]] : ["", s, ""];
}
function tr(s){
  if(LANG !== "ru" || !s) return s;
  if(Object.prototype.hasOwnProperty.call(RU, s)) return RU[s];
  const t = s.trim();
  if(Object.prototype.hasOwnProperty.call(RU, t)) return s.replace(t, RU[t]);
  const [a, b, c] = core(t);
  if(b && Object.prototype.hasOwnProperty.call(RU, b)) return s.replace(t, a + RU[b] + c);
  for(const [re, rep] of RX){ if(re.test(t)) return s.replace(t, t.replace(re, rep)); }
  return s;
}
function T(s, vars){
  let r = tr(String(s == null ? "" : s));
  if(vars) r = r.replace(/\{(\w+)\}/g, (m, k) => (vars[k] != null ? vars[k] : m));
  return r;
}

/* ---- DOM'ni avtomatik tarjima qilish ---- */
const SKIP = ".txt,.tgf-ed,.emoj,.bl,.btot,.cbody,.nm,.pn,.dn,#c-name,#p-name,.rqt,#pin-text,#note-text-b,.vcap,.bub .tgf-q,.s-name,#rb-text,.prow .ps,.pz-keep";
const ATTRS = ["placeholder", "title", "data-ph", "aria-label"];
function skip(node){ const el = node.nodeType === 1 ? node : node.parentElement; return !el || !!el.closest(SKIP) || el.closest("script,style"); }
function trText(n){
  if(skip(n)) return;
  const v = n.nodeValue; if(!v || !/\p{L}/u.test(v)) return;
  const t = tr(v); if(t !== v) n.nodeValue = t;
}
function trAttrs(el){
  if(el.nodeType !== 1 || skip(el)) return;
  for(const a of ATTRS){ const v = el.getAttribute(a); if(v){ const t = tr(v); if(t !== v) el.setAttribute(a, t); } }
}
function translate(root){
  if(LANG !== "ru" || !root) return;
  if(root.nodeType === 3) return trText(root);
  if(root.nodeType !== 1 && root.nodeType !== 11) return;
  if(root.nodeType === 1) trAttrs(root);
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n; while((n = w.nextNode())){ n.nodeType === 3 ? trText(n) : trAttrs(n); }
}
if(LANG === "ru"){
  const obs = new MutationObserver(list=>{
    for(const m of list){
      if(m.type === "childList") m.addedNodes.forEach(translate);
      else if(m.type === "characterData") trText(m.target);
      else if(m.type === "attributes") trAttrs(m.target);
    }
  });
  const start = ()=>{ translate(document.body); obs.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS }); };
  if(document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  document.title = "Gulnora Farm — Оператор";
}
function setLang(l){
  try{ localStorage.setItem("op_lang", l); }catch(e){}
  try{ if(tgw.CloudStorage && tgw.isVersionAtLeast && tgw.isVersionAtLeast("6.9")) tgw.CloudStorage.setItem("op_lang", l); }catch(e){}
  location.reload();
}
// Boshqa qurilmada tanlangan til (Telegram CloudStorage) — birinchi ochilishda
try{
  if(!lsGet("op_lang") && tgw.CloudStorage && tgw.isVersionAtLeast && tgw.isVersionAtLeast("6.9")){
    tgw.CloudStorage.getItem("op_lang", (e, v)=>{ if(!e && (v === "ru" || v === "uz") && v !== LANG){ try{ localStorage.setItem("op_lang", v); }catch(_){} location.reload(); } });
  }
}catch(e){}

window.LANG = LANG; window.T = T; window.I18N = { setLang, translate, tr };
})();
