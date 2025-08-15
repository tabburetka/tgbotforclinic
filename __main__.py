import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from settings import TOKEN, ADMIN
from questions import questions
import re


bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния для FSM (добавляем состояние для фото)
class Form(StatesGroup):
    waiting_for_fio = State()
    waiting_for_phone = State()
    waiting_for_photo = State()

# Словарь для хранения ответов и времени последней активности
user_sessions = {}  # {user_id: {'answers': list, 'last_activity': datetime}}

# Клавиатуры для работы с фото
photo_selection_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📷 Приложить фото", callback_data="with_photo")],
    [InlineKeyboardButton(text="➡️ Без фото", callback_data="without_photo")]
])

cancel_photo_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отменить отправку фото", callback_data="cancel_photo")]
])

async def cleanup_sessions():
    """Очистка неактивных сессий"""
    while True:
        now = datetime.now()
        expired_users = [
            user_id for user_id, session in user_sessions.items()
            if now - session['last_activity'] > timedelta(minutes=30)
        ]
        for user_id in expired_users:
            del user_sessions[user_id]
        await asyncio.sleep(60 * 5)  # Проверка каждые 5 минут

def update_user_activity(user_id: int):
    """Обновляем время активности пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'answers': [], 'last_activity': datetime.now()}
    else:
        user_sessions[user_id]['last_activity'] = datetime.now()

# Главное меню (без изменений)
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Пройти тест", callback_data="test_button"),
        InlineKeyboardButton(text="Записаться к врачу", callback_data="scenario_selection")
    ],
])

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """Обработчик команды /start"""
    update_user_activity(message.from_user.id)
    name = message.from_user.first_name
    await message.reply(f"""{name}, здравствуйте! 🌿

Вас приветствует виртуальный помощник «Файбер Клиник» — ваш надежный консультант в вопросах здоровья вен. Здесь вы можете записаться на прием к флебологу, а также пройти тест относительно диагностики, лечения варикозного расширения вен и сосудистых звездочек.

Будем рады проконсультировать вас онлайн и организовать очный прием врача-флеболога!

Ваш комфорт и здоровье — наша главная забота.""",
    reply_markup=main_keyboard)

def pluralize_answers(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} положительный ответ"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return f"{count} положительных ответа"
    else:
        return f"{count} положительных ответов"

async def send_question(user_id: int, message: types.Message, question_num: int = 0):
    """Отправляет вопрос с кнопками ответов (без изменений)"""
    update_user_activity(user_id)
    
    after_the_test_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Записаться к врачу", callback_data="scenario_selection"),
            InlineKeyboardButton(text="В главное меню", callback_data="main_menu")
        ],
    ])
    
    if question_num >= len(questions):
        answers = user_sessions.get(user_id, {}).get('answers', [])
        count_yes = answers.count(0)  # Считаем положительные ответы (0,1 - индекс "Да")
        count_yes += answers.count(1)
        
        if count_yes == 0:
            text = "Вы ответили на все вопросы отрицательно, поздравляем - у Вас здоровые ноги! Если Вас все еще что-то беспокоит, Вы можете записаться на консультацию к флебологу"
        else:
            text = f"У вас {pluralize_answers(count_yes)}, рекомендуем обратиться к флебологу за консультацией"
        
        await message.edit_text(text, reply_markup=after_the_test_keyboard)
        
        # Очищаем сессию после завершения теста
        if user_id in user_sessions:
            del user_sessions[user_id]
        return
    
    question_data = questions[question_num]
    question_text = f"Вопрос №{question_num + 1}\n\n" + question_data[1][0]
    
    buttons = []
    for i, answer in enumerate(question_data[2:]):
        buttons.append([InlineKeyboardButton(
            text=answer[0],
            callback_data=f"answer_{question_num}_{i}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if question_num == 0:
        await message.answer(question_text, reply_markup=keyboard)
    else:
        await message.edit_text(question_text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "test_button")
async def start_test(callback: types.CallbackQuery):
    """Начало теста (без изменений)"""
    await callback.message.delete()
    user_id = callback.from_user.id
    user_sessions[user_id] = {'answers': [], 'last_activity': datetime.now()}
    await send_question(user_id, callback.message)

@dp.callback_query(lambda c: c.data.startswith("answer_"))
async def process_answer(callback: types.CallbackQuery):
    """Обработка выбора ответа (без изменений)"""
    user_id = callback.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'answers': [], 'last_activity': datetime.now()}
    
    parts = callback.data.split('_')
    question_num = int(parts[1])
    answer_num = int(parts[2])
    
    user_sessions[user_id]['answers'].append(answer_num)
    user_sessions[user_id]['last_activity'] = datetime.now()
    await send_question(user_id, callback.message, question_num + 1)

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возврат в главное меню (без изменений)"""
    
    user_id = callback.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]  # Очищаем сессию при возврате в меню
    await send_welcome(callback.message)
    await callback.message.delete()

@dp.callback_query(lambda c: c.data == "scenario_selection")
async def select(callback: types.CallbackQuery):
    """Выбор сценария записи (без изменений)"""
    update_user_activity(callback.from_user.id)
    scenario_selection_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Телеграм заявка", callback_data="sign_up_to_doctor_tg"),
            InlineKeyboardButton(text="Сайт", url="https://booking.medflex.ru/?user=80ba62d9fd0740c0e6c147cef0ff6b60&isRoundWidget=true&filial=8995&type=doctors")
        ],
    ])
    await callback.message.answer(
        "Отлично! Выберите, где вам удобнее записаться.",
        reply_markup=scenario_selection_keyboard
    )

@dp.callback_query(lambda c: c.data == "sign_up_to_doctor_tg")
async def leave_a_request(callback: types.CallbackQuery, state: FSMContext):
    """Начало заявки (без изменений)"""
    personal_data_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Я согласен(на)", callback_data = "agreement"),
            InlineKeyboardButton(text="Политика персональных данных", url="https://18470-o-fayber.lp5.s1dev.ru/soglasie-na-obrabotku-personalnykh-dannykh")
        ],
    ])
    await callback.message.answer(
        "Для записи укажите, пожалуйста, ваши данные*:\n\n"
        "1. ФИО\n"
        "2. Контактный номер телефона\n"
        "3. Фото проблемной зоны (при необходимости)\n\n"
        "*Для продолжения примите, пожалуйста, политику конфиденциальности*",
        reply_markup=personal_data_keyboard
    )

@dp.callback_query(lambda c: c.data == "agreement")
async def agreement_button_check(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_for_fio)
    await callback.message.answer("Спасибо за ваше согласие!\nТеперь введите ваши ФИО")


@dp.message(Form.waiting_for_fio)
async def process_fio(message: types.Message, state: FSMContext):
    """Обработка ФИО (без изменений)"""
    normalized_fio = ' '.join(message.text.split())
    
    if is_valid_fullname(normalized_fio):
        await state.update_data(full_name=normalized_fio)
        await message.answer(
            "Отлично! Теперь введите ваш контактный номер телефона в формате:\n\n"
            "+7XXX XXX XX XX\n"
            "или\n"
            "8XXX XXX XX XX"
        )
        await state.set_state(Form.waiting_for_phone)
    else:
        await message.answer(
            "Некорректный формат ФИО. Пожалуйста, введите:\n\n"
            "• Фамили, имя, отчество (обязательно)\n"
            "• Каждое слово с заглавной буквы\n"
            "• Только русские буквы и дефисы\n\n"
            "Пример: Иванов Иван или Петрова Анна-Мария Ивановна"
        )

# Модифицируем обработчик телефона для предложения фото
@dp.message(Form.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if is_russian_phone_number(message.text):
        await state.update_data(phone=message.text)
        await message.answer(
            "Хотите приложить фото проблемной зоны?",
            reply_markup=photo_selection_keyboard
        )
        await state.set_state(Form.waiting_for_photo)
    else:
        await message.answer(
            "Некорректный номер телефона. Пожалуйста, введите российский номер в формате:\n\n"
            "+7XXX XXX XX XX\n"
            "или\n"
            "8XXX XXX XX XX\n\n"
            "Допускаются скобки и дефисы: +7 (XXX) XXX-XX-XX"
        )

# Обработчики для работы с фото
@dp.callback_query(Form.waiting_for_photo, lambda c: c.data == "with_photo")
async def request_photo(callback: types.CallbackQuery):
    await callback.message.answer(
        "Пожалуйста, отправьте фото проблемной зоны:",
        reply_markup=cancel_photo_keyboard
    )
    await callback.answer()

@dp.callback_query(Form.waiting_for_photo, lambda c: c.data == "without_photo")
async def continue_without_photo(callback: types.CallbackQuery, state: FSMContext):
    
    await complete_application(callback.message, state)
    await callback.answer()

@dp.callback_query(Form.waiting_for_photo, lambda c: c.data == "cancel_photo")
async def cancel_photo_upload(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправка фото отменена.\nВаша заявка отправленна без фото!")
    await complete_application(callback.message, state)
    await callback.answer()

@dp.message(Form.waiting_for_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    if message.photo[-1].file_size > 10 * 1024 * 1024:  # 10MB limit
        await message.answer(
            "Фото слишком большое (максимум 10МБ). Попробуйте отправить другой файл:",
            reply_markup=cancel_photo_keyboard
        )
        return
    
    await state.update_data(photo=message.photo[-1].file_id)
    await complete_application(message, state)

@dp.message(Form.waiting_for_photo)
async def handle_invalid_content(message: types.Message):
    await message.answer(
        "Пожалуйста, отправьте фото проблемной зоны или выберите действие:",
        reply_markup=photo_selection_keyboard
    )

async def complete_application(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = (
        f"🔔 Новая заявка на запись!\n\n"
        f"👤 Клиент: {data['full_name']}\n"
        f"📞 Телефон: {data['phone']}\n\n"
        f"🆔 ID пользователя: {message.from_user.id}"
    )
    
    if 'photo' in data:
        await bot.send_photo(
            ADMIN,
            photo=data['photo'],
            caption=text,
            reply_markup=сheck_done_keyboard
        )
    else:
        await bot.send_message(
            ADMIN,
            text=f"{text}\n\n📷 Фото не приложено",
            reply_markup=сheck_done_keyboard
        )
    
    await message.answer(
        "✅ Ваша заявка успешно отправлена!\n\n"
        "Наш администратор свяжется с вами в ближайшее время."
    )
    await state.clear()

# Остальные функции без изменений
сheck_done_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌Пометить как выполненный❌", callback_data="check_done")],
])

done_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅Помеченно как выполненное✅", callback_data="reverb_done_button")],
])

@dp.callback_query(lambda c: c.data == "check_done")
async def Check_done_F(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=done_keyboard)

@dp.callback_query(lambda c: c.data == "reverb_done_button")
async def Reverb_check_done_F(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=сheck_done_keyboard)

def is_valid_fullname(name):
    """Проверяет ФИО с учетом множественных пробелов"""
    cleaned_name = ' '.join(name.split())  # Нормализуем пробелы
    pattern = r'^[А-ЯЁ][а-яё\-]{1,}(?:\s[А-ЯЁ][а-яё\-]{1,}){1,2}$'
    return bool(re.fullmatch(pattern, cleaned_name))

def is_russian_phone_number(phone):
    """Проверяет российский номер телефона"""
    pattern = r'^(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$'
    return bool(re.fullmatch(pattern, phone))

async def main():
    # Запускаем фоновую задачу очистки
    asyncio.create_task(cleanup_sessions())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
