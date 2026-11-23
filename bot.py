import json
import urllib.request
import asyncio
import logging
import sqlite3
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
)

# --- НАСТРОЙКИ ---
TOKEN = ""
ADMIN_ID = 1832950996
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw_zUV_ZinG2IKrZEc_QQC3z6sE2NRj72e3zO31aB5lF4UURrQkxq_YvADNH7m-wQgv/exec"


# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect('contacts.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        name TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()


# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    consent = State()
    meeting = State()
    phone = State()


# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- КЛАВИАТУРА КОНТАКТА ---
def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="Оставить контакт",
                request_contact=True
            )],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# --- ФУНКЦИЯ ОТПРАВКИ В GOOGLE ТАБЛИЦУ ---
async def send_to_google_sheets(payload: dict):
    def _post():
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            GOOGLE_SCRIPT_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status

    try:
        status = await asyncio.to_thread(_post)

        if status == 200:
            logging.info("✅ Данные успешно улетели в Google Таблицу!")
        else:
            logging.error(
                f"❌ Ошибка Google Таблицы: статус {status}"
            )

    except Exception as e:
        logging.error(
            f"❌ Не удалось отправить данные в Google Таблицу: {e}"
        )


# =========================================================
# 1. СТАРТ
# =========================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    start_text = (
        "Привет, рада тебя видеть! 🦋\n"
        "Ты в боте Woman Wings — сообщества женщин, которые хотят начать своё дело или вырастить то, что уже есть. "
        "У нас есть офлайн- и онлайн-встречи, лекции, мастер-классы и, главное, круг девушек, которые поддерживают друг друга.\n"
        "Чтобы начать на нашем корнере, давай познакомимся. Это займёт меньше минуты"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Начать",
                    callback_data="start_bot"
                )
            ]
        ]
    )

    # КАРТИНКУ НЕ МЕНЯЕМ
    try:
        photo = FSInputFile("welcome.png")

        await message.answer_photo(
            photo=photo,
            caption=start_text,
            reply_markup=keyboard
        )

    except Exception:
        await message.answer(
            text=start_text,
            reply_markup=keyboard
        )


# =========================================================
# 2. НАЖАТИЕ "НАЧАТЬ"
#    Сначала сообщение, потом документы
# =========================================================

@dp.callback_query(lambda c: c.data == "start_bot")
async def process_start_button(
    callback: types.CallbackQuery,
    state: FSMContext
):
    await callback.answer()

    # Убираем кнопку "Начать"
    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    # СНАЧАЛА ТЕКСТ
    consent_text = (
        "Ура, рада, что ты здесь! 💫\n\n"
        "Перед знакомством одна формальность: мне нужно твоё согласие "
        "на обработку персональных данных.\n\n"
        "Эти данные нужны, чтобы зарегистрировать тебя на корнере "
        "и приглашать на встречи Woman Wings.\n\n"
        "Мы не передаём их посторонним и не рассылаем спам 🤍\n\n"
        "Нажимая «Согласна», ты подтверждаешь, что прочитала документы "
        "и даёшь согласие."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Согласна",
                    callback_data="agree"
                )
            ]
        ]
    )

    await callback.message.answer(
        consent_text,
        reply_markup=keyboard
    )

    # ПОТОМ ДОКУМЕНТЫ
    try:
        consent = FSInputFile(
            "WW_Согласие_на_обработку_персональных_данных.pdf"
        )

        policy = FSInputFile(
            "WW_Политика_обработки_персональных_данных.pdf"
        )

        await callback.message.answer_document(
            document=consent,
            caption="📄 Согласие на обработку персональных данных"
        )

        await callback.message.answer_document(
            document=policy,
            caption="📄 Политика обработки персональных данных"
        )

    except Exception as e:
        print(f"Документы не найдены: {e}")

    await state.set_state(Form.consent)


# =========================================================
# 3. "СОГЛАСНА"
# =========================================================

@dp.callback_query(lambda c: c.data == "agree")
async def process_consent(
    callback: types.CallbackQuery,
    state: FSMContext
):
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Познакомиться",
                    callback_data="meet"
                )
            ]
        ]
    )

    await callback.message.answer(
        "Хорошо, остался один шаг",
        reply_markup=keyboard
    )

    await state.set_state(Form.meeting)


# =========================================================
# 4. "ПОЗНАКОМИТЬСЯ"
# =========================================================

@dp.callback_query(lambda c: c.data == "meet")
async def process_meet(
    callback: types.CallbackQuery,
    state: FSMContext
):
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.message.answer(
        "Оставь свой контакт, чтобы продолжить 🤍",
        reply_markup=get_contact_keyboard()
    )

    await state.set_state(Form.phone)


# =========================================================
# 5. ПОЛУЧИЛИ КОНТАКТ
# =========================================================

@dp.message(Form.phone, F.contact)
async def process_contact(
    message: types.Message,
    state: FSMContext
):
    phone_number = message.contact.phone_number

    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    # Имя теперь берём автоматически из Telegram
    name = message.from_user.first_name or ""

    username_str = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "нет"
    )

    # -----------------------------------------------------
    # Сообщение + голосовое
    # -----------------------------------------------------

    await message.answer(
    "Послание для тебя от основателя женского сообщества и форума Woman Wings ❤️",
    reply_markup=types.ReplyKeyboardRemove()
)

    try:
        voice = FSInputFile("voice.ogg")

        await message.answer_voice(
            voice=voice
        )

    except Exception as e:
        print(f"Голосовое не найдено: {e}")


    # -----------------------------------------------------
    # Сохраняем в БД
    # -----------------------------------------------------

    cursor.execute('''
        INSERT INTO contacts (
            user_id,
            username,
            name,
            phone
        )
        VALUES (?, ?, ?, ?)
    ''', (
        message.from_user.id,
        message.from_user.username,
        name,
        phone_number
    ))

    conn.commit()


    # -----------------------------------------------------
    # Google Таблица
    # -----------------------------------------------------

    await send_to_google_sheets({
        "name": name,
        "phone": f"'{phone_number}",
        "email": "",
        "comment": "Согласна (152-ФЗ)",
        "username": username_str,
        "user_id": str(message.from_user.id)
    })


    # -----------------------------------------------------
    # Уведомление админу
    # -----------------------------------------------------

    await bot.send_message(
        ADMIN_ID,
        f"📩 Новая участница Woman Wings!\n"
        f"Имя: {name}\n"
        f"Телефон: {phone_number}\n"
        f"Username: {username_str}\n"
        f"ID: {message.from_user.id}"
    )

    await state.clear()


# =========================================================
# Если вместо кнопки контакта написали текст
# =========================================================

@dp.message(Form.phone)
async def process_phone_text(
    message: types.Message,
    state: FSMContext
):
    if message.text == "Отмена":
        await state.clear()

        await message.answer(
            "Хорошо, отменил. Если что — пиши /start",
            reply_markup=types.ReplyKeyboardRemove()
        )

        return

    await message.answer(
        "Пожалуйста, нажми на кнопку «Оставить контакт» "
        "внизу экрана 👇",
        reply_markup=get_contact_keyboard()
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())