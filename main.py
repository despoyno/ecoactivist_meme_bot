import asyncio
import logging
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from TOKEN import API_TOKEN

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)

# --- База данных (в виде словарей для простоты) ---
# В реальном приложении здесь должна быть интеграция с базой данных (SQLite, PostgreSQL и т.д.)
users_data = {}  # {user_id: {'points': int, 'level': int, 'completed_tasks': set()}}
user_tasks = {}  # {user_id: {'task_id': int, 'message_id': int}}

# "Таблица" с заданиями
TASKS = {
    1: {"text": "♻️ Сегодня отсортируйте мусор: отделите пластик, бумагу и стекло.", "points": 15,
        "category": "Сортировка"},
    2: {"text": "👜 Возьмите с собой в магазин многоразовую сумку (шоппер) вместо покупки пластикового пакета.",
        "points": 10, "category": "Пластик"},
    3: {"text": "💡 Выключайте свет, выходя из комнаты, даже если на минутку.", "points": 5, "category": "Энергия"},
    4: {"text": "💧 Примите душ на 2 минуты быстрее обычного, чтобы сэкономить воду.", "points": 10, "category": "Вода"},
    5: {"text": "☕ Используйте многоразовую кружку для кофе или чая навынос.", "points": 15, "category": "Пластик"},
    6: {"text": "🔌 Отключите все неиспользуемые электроприборы из розеток перед сном.", "points": 10,
        "category": "Энергия"},
    7: {"text": "📝 Составьте список покупок перед походом в магазин, чтобы избежать импульсивных и ненужных покупок.",
        "points": 5, "category": "Потребление"},
    8: {"text": "🚲 Пройдитесь пешком или поезжайте на велосипеде вместо короткой поездки на машине или автобусе.",
        "points": 20, "category": "Транспорт"},
}

# "Таблица" с эко-советами
TIPS = {
    "Энергия": [
        "Замените лампы накаливания на светодиодные (LED) — они потребляют до 85% меньше энергии.",
        "При покупке новой техники обращайте внимание на класс энергоэффективности (A, A+, A++).",
        "Не оставляйте зарядные устройства в розетке после полной зарядки гаджета."
    ],
    "Вода": [
        "Закрывайте кран во время чистки зубов. Это может сэкономить до 10 литров воды.",
        "Собирайте дождевую воду для полива комнатных растений.",
        "Используйте посудомоечную машину при полной загрузке — это экономнее, чем мыть посуду вручную под проточной водой."
    ],
    "Пластик": [
        "Откажитесь от одноразовой посуды. Носите с собой многоразовый ланч-бокс и столовые приборы.",
        "Покупайте напитки в стеклянной или алюминиевой таре, которую легче переработать.",
        "Выбирайте товары без лишней пластиковой упаковки, например, овощи и фрукты на развес."
    ]
}


# --- Машина состояний (FSM) для настроек ---
class Settings(StatesGroup):
    choosing_category = State()


# --- Клавиатуры ---
def get_main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✅ Новое задание", callback_data="get_task")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton(text="💡 Эко-совет", callback_data="get_tip")],
        # [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")], # Заглушка для добавления настроек
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_task_keyboard(task_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="✔️ Выполнено", callback_data=f"task_done_{task_id}"),
            InlineKeyboardButton(text="➡️ Пропустить", callback_data=f"task_skip_{task_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tips_category_keyboard():
    buttons = [
        [InlineKeyboardButton(text="💡 Энергия", callback_data="tip_cat_Энергия")],
        [InlineKeyboardButton(text="💧 Вода", callback_data="tip_cat_Вода")],
        [InlineKeyboardButton(text="♻️ Пластик", callback_data="tip_cat_Пластик")],
        [InlineKeyboardButton(text="↩️ Назад в меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Инициализация бота и диспетчера ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- Хэндлеры (Обработчики команд и сообщений) ---
@dp.message(CommandStart())
async def send_welcome(message: Message):
    """
    Этот хэндлер будет вызван, когда пользователь отправит команду /start
    """
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    # Добавляем пользователя в нашу "базу данных", если его там нет
    if user_id not in users_data:
        users_data[user_id] = {'points': 0, 'level': 1, 'completed_tasks': set()}

    welcome_text = (
        f"Привет, {user_name}! 👋\n\n"
        "Я — ваш **Эко-Трекер**, помошник по формированию полезных эко-привычек.\n\n"
        "Давайте вместе сделаем мир чище! Каждый день я буду предлагать вам небольшое задание. "
        "Выполняя их, вы будете зарабатывать баллы, повышать свой уровень и, самое главное, "
        "вносить реальный вклад в защиту нашей планеты. 🌍\n\n"
        "Используйте меню ниже, чтобы начать."
    )

    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())


@dp.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возвращает пользователя в главное меню"""
    await callback.message.edit_text(
        "Вы в главном меню. Что хотите сделать?",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


# --- Логика заданий ---

@dp.callback_query(F.data == "get_task")
async def get_new_task(callback: CallbackQuery):
    """Выдает пользователю новое случайное задание"""
    user_id = callback.from_user.id

    # Проверяем, есть ли уже активное задание
    if user_id in user_tasks and user_tasks[user_id]:
        await callback.answer("У вас уже есть активное задание. Сначала завершите его.", show_alert=True)
        return

    # Выбираем случайное задание, которое пользователь еще не выполнял
    available_tasks = list(set(TASKS.keys()) - users_data.get(user_id, {}).get('completed_tasks', set()))

    # Если все задания выполнены, сбрасываем прогресс
    if not available_tasks:
        users_data[user_id]['completed_tasks'] = set()
        available_tasks = list(TASKS.keys())
        await callback.answer("Вы выполнили все задания! Начинаем новый круг.", show_alert=True)

    random_task_id = random.choice(available_tasks)
    task = TASKS[random_task_id]

    msg = await callback.message.edit_text(
        f"Новое задание для вас:\n\n**{task['text']}**\n\n🏅 **Награда:** {task['points']} очков.",
        parse_mode="Markdown",
        reply_markup=get_task_keyboard(random_task_id)
    )

    # Сохраняем информацию о выданном задании
    user_tasks[user_id] = {'task_id': random_task_id, 'message_id': msg.message_id}
    await callback.answer()


@dp.callback_query(F.data.startswith("task_done_"))
async def process_task_done(callback: CallbackQuery):
    """Обработка выполнения задания"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split("_")[-1])

    if user_id not in user_tasks or user_tasks[user_id]['task_id'] != task_id:
        await callback.answer("Это задание уже неактивно.", show_alert=True)
        return

    task_info = TASKS[task_id]
    points_earned = task_info['points']

    # Обновляем данные пользователя
    users_data[user_id]['points'] += points_earned
    users_data[user_id]['completed_tasks'].add(task_id)

    # Логика повышения уровня (например, каждые 100 очков)
    new_level = (users_data[user_id]['points'] // 100) + 1
    level_up_message = ""
    if new_level > users_data[user_id]['level']:
        users_data[user_id]['level'] = new_level
        level_up_message = f"🎉 **Поздравляем! Вы достигли {new_level} уровня!** 🎉\n\n"

    # Очищаем активное задание
    del user_tasks[user_id]

    await callback.message.edit_text(
        f"{level_up_message}"
        f"Отличная работа! ✅\n\n"
        f"Вы выполнили задание: «{task_info['text']}»\n"
        f"И заработали **+{points_earned}** очков.\n"
        f"Ваш текущий баланс: **{users_data[user_id]['points']}** очков.",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()  # Возвращаем в меню
    )
    await callback.answer("Задание выполнено!")


@dp.callback_query(F.data.startswith("task_skip_"))
async def process_task_skip(callback: CallbackQuery):
    """Обработка пропуска задания"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split("_")[-1])

    if user_id not in user_tasks or user_tasks[user_id]['task_id'] != task_id:
        await callback.answer("Это задание уже неактивно.", show_alert=True)
        return

    # Очищаем активное задание
    del user_tasks[user_id]

    await callback.message.edit_text(
        "Понятно. Вы пропустили это задание.\n\n"
        "Вы всегда можете взять новое из главного меню.",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer("Задание пропущено.")


# --- Логика прогресса, советов и информации ---

@dp.callback_query(F.data == "my_progress")
async def show_my_progress(callback: CallbackQuery):
    """Показывает статистику пользователя"""
    user_id = callback.from_user.id

    if user_id not in users_data:
        await callback.answer("Сначала начните работу с ботом командой /start", show_alert=True)
        return

    data = users_data[user_id]
    progress_text = (
        f"📊 **Ваш Эко-Прогресс** 📊\n\n"
        f"⭐ **Уровень:** {data['level']}\n"
        f"🏅 **Очки:** {data['points']}\n"
        f"✅ **Выполнено заданий:** {len(data['completed_tasks'])}\n\n"
        "Продолжайте в том же духе! Каждое маленькое действие имеет большое значение."
    )

    await callback.message.edit_text(progress_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "get_tip")
async def ask_for_tip_category(callback: CallbackQuery):
    """Предлагает выбрать категорию совета"""
    await callback.message.edit_text("О чём вы хотели бы получить совет?", reply_markup=get_tips_category_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("tip_cat_"))
async def send_random_tip(callback: CallbackQuery):
    """Отправляет случайный совет из выбранной категории"""
    category = callback.data.split("_")[-1]
    tip = random.choice(TIPS[category])

    await callback.message.edit_text(
        f"**💡 Эко-совет ({category}):**\n\n{tip}",
        parse_mode="Markdown",
        reply_markup=get_tips_category_keyboard()  # Оставляем меню советов
    )
    await callback.answer()


@dp.callback_query(F.data == "about")
async def show_about_info(callback: CallbackQuery):
    """Показывает информацию о боте"""
    about_text = (
        "**🤖 О боте «Эко-Трекер»**\n\n"
        "Этот бот создан, чтобы помочь вам легко и играючи внедрить в свою жизнь "
        "экологичные привычки.\n\n"
        "**Как это работает?**\n"
        "1. Берите **новое задание**.\n"
        "2. Отмечайте его **выполнение** и получайте очки.\n"
        "3. Повышайте свой **уровень** и отслеживайте **прогресс**.\n"
        "4. Читайте **эко-советы**, чтобы узнать больше нового.\n\n"
        "Даже маленькие шаги ведут к большим переменам! 💚"
    )
    await callback.message.edit_text(about_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())
    await callback.answer()


# --- Основная функция для запуска бота ---
async def main():
    """Главная функция для запуска бота"""
    # Для реального проекта рекомендуется использовать Webhooks вместо polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())