"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    full_name = State()
    phone = State()
    channel = State()
    branch = State()


class OrderFlow(StatesGroup):
    waiting_content = State()   # birinchi kontent -> murojaat yaratiladi
    feedback = State()          # baho sababini (izoh) kutish


class ContactFlow(StatesGroup):
    waiting_message = State()   # bog'lanishdan keyin foydalanuvchi yozadi
    confirm = State()           # yuborishni tasdiqlash


class NearestFlow(StatesGroup):
    waiting_location = State()   # eng yaqin filial uchun lokatsiya kutilmoqda


class AdminTpl(StatesGroup):
    add_text = State()           # tayyor javob shabloni matni


class AdminFlow(StatesGroup):
    # broadcast
    bc_content = State()
    bc_target_branch = State()
    # kanal
    ch_add = State()
    # faq
    faq_title = State()
    faq_answer = State()
    faq_edit_title = State()
    faq_edit_answer = State()
    # filial qo'shish
    br_name = State()
    br_address = State()
    br_phone = State()
    br_hours = State()
    br_location = State()
    br_photo = State()
    # filial tahrirlash
    br_edit_value = State()
    # operator
    op_name = State()
    op_login = State()
    op_password = State()
    # murojaat tarixi qidiruv
    search_value = State()
    # kontakt matnini tahrirlash
    contact_edit = State()


class OperatorFlow(StatesGroup):
    login = State()
    password = State()
    reply_text = State()    # mijozga javob yozish
    bill_text = State()     # dori hisoblash
