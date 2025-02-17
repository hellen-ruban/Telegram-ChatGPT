import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, Application, CallbackQueryHandler, ContextTypes, CommandHandler, MessageHandler, filters, CallbackContext
from gpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu,
                  default_callback_handler, load_prompt)
import credentials
from credentials import BOT_TOKEN
from openai import OpenAI
from dotenv import load_dotenv
import logging
import httpx
from credentials import GROQ_API_KEY
import random


'''Создаем приложение Telegram'''
chat_gpt = ChatGptService(credentials.ChatGPT_TOKEN)
app = ApplicationBuilder().token(credentials.BOT_TOKEN).build()

'''обработка возможных ошибок телеграмм
Если где-то в коде бота случится ошибка, обработчик error_handler запишет ее в логи и предотвратит падение программы
вместо вывода "No error handlers are registered, logging exception." бот будет логировать ошибки.'''
application = Application.builder().token(credentials.BOT_TOKEN).build()
async def error_handler(update, context: CallbackContext):
    print(f"Ошибка: {context.error}")
application.add_error_handler(error_handler)


'''Создаем кнопку start с наполнением'''
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)
    await show_main_menu(update, context, {
        'start': 'Головне меню',
        'random': 'Дізнатися випадковий цікавий факт 🧠',
        'gpt': 'Задати питання чату GPT 🤖',
        'talk': 'Поговорити з відомою особистістю 👤',
        'quiz': 'Взяти участь у квізі ❓'
        # Додати команду в меню можна так:
        # 'command': 'button text'

    })

'''1.Випадковий факт'''
from openai import RateLimitError  # Импортируем обработку ошибки

async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_message("random")
    await send_image(update, context, "random")
    await send_text(update, context, text)
    prompt = load_prompt("random")

    try:
        content = await chat_gpt.send_question(prompt, "Дай цікавий факт")
        await send_text(update, context, content)
    except RateLimitError:
        await send_text(update, context, "Перевищено ліміт запитів OpenAI. Спробуйте пізніше.")


'''2.ChatGPT інтерфейс'''
async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.replace("/gpt", "").strip()  # Получаем текст сообщения пользователя
    text = load_message("gpt")  # Загружаем приветственное сообщение

    if not user_message:
        await send_image(update, context, "gpt")  # Отправляем изображение
        await send_text(update, context, "Будь ласка, введіть запит після команди /gpt.")
        return

    # Запрос к ChatGPT с обработкой ошибки превышения лимита
    try:
        content = await chat_gpt.send_question(user_message, "Відповідь ChatGPT")
        await send_text(update, context, content)  # Отправляем ответ от ChatGPT
    except RateLimitError:
        await send_text(update, context, "Перевищено ліміт запитів OpenAI. Спробуйте пізніше.")


'''3.Діалог з відомою особистістю'''

personalities = [
    ("Курт Кобейн", 'talk_cobain', 'talk_cobain.jpg'),
    ("Стівен Гокінг", 'talk_hawking', 'talk_hawking.jpg'),
    ("Фрідріх Ніцше", 'talk_nietzsche', 'talk_nietzsche.jpg'),
    ("Королева Єлизавета II", 'talk_queen', 'talk_queen.jpg'),
    ("Дж.Р.Р. Толкін", 'talk_tolkien', 'talk_tolkien.jpg')
]
# Функция для загрузки промта с проверкой пути
def load_prompt(name):
    prompt_path = os.path.join("resources", "prompts", name + ".txt")
    print(f"Попытка открыть файл: {prompt_path}")

    if os.path.exists(prompt_path):
        with open(prompt_path, "r") as file:
            return file.read()
    else:
        print(f"Файл {name}.txt не найден.")
        return None

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=data)] for name, data, _ in personalities]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_image(update, context, 'talk')
    await send_text(update, context, "Оберіть особистість для діалогу:")
    await update.message.reply_text("Оберіть особистість для діалогу:", reply_markup=reply_markup)

async def talk_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Определение кода личности, выбранной пользователем
    selected_code = f"talk_{query.data.split('_')[1]}"
    selected_name, _, image_filename = next((name, code, img) for name, code, img in personalities if code == selected_code)

    print(f"Обраний персонаж:  {selected_name} ({selected_code})")

    # Путь к изображению
    image_path = os.path.join(os.getcwd(), "resources", "images", image_filename)

    # Загрузка промта
    prompt = load_prompt(selected_code)

    if prompt is None:
        await query.edit_message_text(text=f"Промт для {selected_name} не знайдено.")
        return
        # Отправляем изображение и название личности
    if os.path.exists(image_path):
         with open(image_path, 'rb') as image_file:
            await query.message.reply_photo(photo=image_file, caption=f"Ви вибрали {selected_name}. Задавайте питання.")
    else:
         await query.message.reply_text(text=f"Ви вибрали {selected_name}. Задавайте питання.")

    context.user_data['selected_person'] = prompt

    # Отправляем сообщение с кнопкой "Закінчити"
    end_button = InlineKeyboardMarkup([[InlineKeyboardButton("Закінчити", callback_data="end_talk")]])
    await query.edit_message_text(text=f"Ви вибрали {selected_name}. Задавайте питання.", reply_markup=end_button)

    # await query.edit_message_text(text=f"Ви вибрали {selected_name}. Задавайте питання.")
    context.user_data['selected_person'] = prompt
# Ответить пользователю, что он может задавать вопросы
    await send_text(update, context, "Задайте питання і я передам його ChatGPT.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()
    if not user_message:
        return

    prompt = context.user_data.get('selected_person', None)
    if not prompt:
        await send_text(update, context, "Будь ласка, спочатку виберіть особистість через команду /talk.")
        return

    # Формируем запрос в ChatGPT
    gpt_request = f"Ти відповідаєш у стилі наступного опису:\n\n{prompt}\n\nКористувач питає: {user_message}"
    content = await chat_gpt.send_question(gpt_request, "Відповідь ChatGPT")
    # await send_text(update, context, content)

# Добавляем кнопку "Закінчити" к ответу ChatGPT
    end_button = InlineKeyboardMarkup([[InlineKeyboardButton("Закінчити", callback_data="end_talk")]])
    await update.message.reply_text(content, reply_markup=end_button)

async def end_talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Закінчити' – возвращает пользователя в главное меню."""
    query = update.callback_query
    await query.answer()

    # Очищаем контекст выбранной личности
    context.user_data.pop('selected_person', None)

    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)
    await show_main_menu(update, context, {
        'start': 'Головне меню',
        'random': 'Дізнатися випадковий цікавий факт 🧠',
        'gpt': 'Задати питання чату GPT 🤖',
        'talk': 'Поговорити з відомою особистістю 👤',
        'quiz': 'Взяти участь у квізі ❓'
    })

'''4.Квіз'''

# Загрузка переменных окружения
load_dotenv()
CHATGPT_TOKEN = os.getenv("YOUR_OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
from credentials import YOUR_OPENAI_API_KEY
CHATGPT_TOKEN = YOUR_OPENAI_API_KEY
client = OpenAI(api_key=CHATGPT_TOKEN)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Темы квиза
QUIZ_TOPICS = {
    "quiz_prog": "Програмування",
    "quiz_math": "Математика",
    "quiz_biology": "Біологія"
}

# Хранение состояния пользователей
user_states = {}
user_scores = {}


# Функция для отправки изображений
async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE, image_name: str):
    image_path = os.path.join("resources", "images", f"{image_name}.jpg")
    if os.path.exists(image_path):
        with open(image_path, "rb") as img:
            await update.message.reply_photo(photo=img)
    else:
        logging.warning(f"Изображение {image_path} не найдено")


# Функция загрузки промпта
def load_prompt():
    prompt_path = os.path.join("resources", "prompts", "quiz.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as file:
            return file.read()
    logging.warning("Файл с промптом не найден!")
    return ""


# Запрос к ChatGPT
async def ask_chatgpt(prompt: str, user_input: str):
    client = OpenAI(api_key=CHATGPT_TOKEN)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{prompt}\n{user_input}"}],
        max_tokens=50
    )

    return response.choices[0].text.strip()


# Обработчик команды /quiz
async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"state": "choosing_topic", "score": 0}

    await send_image(update, context, "quiz")

    keyboard = [[InlineKeyboardButton(topic, callback_data=code)] for code, topic in QUIZ_TOPICS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Оберіть тему для квізу:", reply_markup=reply_markup)


# Обработчик выбора темы
async def handle_topic_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    topic_code = query.data
    user_states[user_id] = {"state": "answering", "topic": topic_code, "score": 0}

    prompt = load_prompt()
    question = await ask_chatgpt(prompt, topic_code)
    user_states[user_id]["question"] = question

    await query.edit_message_text(
        f"Тема: {QUIZ_TOPICS[topic_code]}\n\nПитання: {question}\n\nВведіть вашу відповідь текстовим повідомленням.")


# Обработчик ответа пользователя
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answer = update.message.text

    if user_id not in user_states or user_states[user_id]["state"] != "answering":
        await update.message.reply_text("Будь ласка, почніть квіз командою /quiz")
        return

    topic_code = user_states[user_id]["topic"]
    question = user_states[user_id]["question"]

    prompt = load_prompt()
    check_response = await ask_chatgpt(prompt, f"{question}\nВідповідь: {user_answer}")

    if "Правильно!" in check_response:
        user_states[user_id]["score"] += 1

    keyboard = [
        [InlineKeyboardButton("Ще питання", callback_data="quiz_more")],
        [InlineKeyboardButton("Закінчити", callback_data="end_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{check_response}\n\nВаш рахунок: {user_states[user_id]['score']}\n\nЩо далі?",
        reply_markup=reply_markup
    )


# Обработчик дополнительных действий
async def handle_next_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action = query.data

    if action == "quiz_more":
        topic_code = user_states[user_id]["topic"]
        prompt = load_prompt()
        question = await ask_chatgpt(prompt, topic_code)
        user_states[user_id]["question"] = question

        await query.edit_message_text(
            f"Наступне питання: {question}\n\nВведіть вашу відповідь текстовим повідомленням.")

    elif action == "end_quiz":
        score = user_states[user_id]["score"]
        del user_states[user_id]
        await query.edit_message_text(f"Квіз завершено! Ваш фінальний рахунок: {score}")


    # if action == "quiz_more":
    #     # Получение нового вопроса
    #     question = await chat_gpt.send_question(load_prompt, user_states[user_id]["topic"])
    #     user_states[user_id]["current_question"] = question
    #     await query.edit_message_text(f"Наступне питання: {question}")
    # elif action == "change_topic":
    #     # Возврат к выбору темы
    #     await quiz_command(update, context)
    # elif action == "end_quiz":
    #     # Завершение квиза
    #     final_score = user_scores[user_id]
    #     del user_states[user_id]
    #     del user_scores[user_id]
    #     await query.edit_message_text(f"Квіз завершен. Ваш фінальний рахунок: {final_score}")


# Основная функция для запуска бота
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    '''# Запуск приложения
    await app.run_polling()'''


# if __name__ == '__main__':
#     import asyncio
#
#     asyncio.run(main())

'''Зареєструвати обробник команди можна так:'''
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('random', random))
app.add_handler(CommandHandler("gpt", gpt))
app.add_handler(CommandHandler('talk', talk))
app.add_handler(CommandHandler("quiz", quiz_command))
# app.add_handler(CallbackQueryHandler(button, pattern='^(menu_|other_)'))  # Обрабатывает только свои кнопки (если они создаются)
app.add_handler(CallbackQueryHandler(talk_button, pattern='^talk_'))  # Для общения с личностью
app.add_handler(CallbackQueryHandler(end_talk, pattern="^end_talk$"))
app.add_handler(CallbackQueryHandler(handle_topic_selection, pattern="^quiz_"))
app.add_handler(CallbackQueryHandler(handle_next_action, pattern="^(quiz_more|end_quiz)$")) # для квиза
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))  # Обрабатываем текстовые сообщения


'''Запуск bot-приложения'''
app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())


'''(По желанию) код обрабатывает любое текстовое сообщение как запрос к ChatGPT, 
что позволяет пользователям просто писать текст в бота, а не только через команду /gpt."""

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text.strip()
        if not user_message:
            return
        content = await chat_gpt.send_question(user_message, "Відповідь ChatGPT")  # Отправляем текст в ChatGPT
        await send_text(update, context, content)
        
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))'''


# Зареєструвати обробник колбеку можна так:
# app.add_handler(CallbackQueryHandler(app_button, pattern='^app_.*'))

# app.add_handler(CallbackQueryHandler(default_callback_handler, pattern='^talk_*'))
#app.run_polling()
#print(f"GROQ_API_KEY загружен: {GROQ_API_KEY[:5]}********")




"""4.2 Квiз через Groq:

async def send_groq_request(message: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama3-8b-8192",  # Или "gemma-7b-it"
        "messages": [
           # {"role": "system", "content": "You are a helpful assistant."},
                     {"role": "user", "content": message + " українською"}],
        "max_tokens": 50
    }

    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
        data = response.json()

    print("Ответ API:", data)  # Вывод ответа в консоль для отладки
    return data


# Функция для генерации вопроса через Groq API
async def generate_quiz_question(topic: str) -> str:
    prompt_map = {
        'quiz_prog': 'Задай питання на тему програмування мовою python.',
        'quiz_math': 'Задай питання на тему математичних теорій.',
        'quiz_biology': 'Задай питання на тему біології.'
    }
    prompt = prompt_map.get(topic, "Потрібна тема не знайдена.")

    data = await send_groq_request(prompt)
     # headers = {
    #     "Authorization": f"Bearer {GROQ_API_KEY}",
    #     "Content-Type": "application/json",
    # }

    # payload = {
    #     "model": "llama3-8b-8192",  # Или "gemma-7b-it"
    #     "messages": [
    #        # {"role": "system", "content": "You are a helpful assistant."},
    #                  {"role": "user", "content": prompt + " українською"}],
    #     "max_tokens": 50
    # }
    #
    # async with httpx.AsyncClient() as client:
    #     response = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
    #     data = response.json()
    #
    # print("Ответ API:", data)  # Вывод ответа в консоль для отладки

    # Проверка, есть ли в ответе ключ 'choices'
    # if "choices" in data and data["choices"]:
    #     return data["choices"][0]["message"]["content"]
    # elif "error" in data:
    #     return f"Помилка від API: {data['error']['message']}"
    # else:
    #     return "Не вдалося отримати питання. Спробуйте ще раз."
    #
    # async with httpx.AsyncClient() as client:
    #     response = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
    #     data = response.json()

    return data["choices"][0]["message"]["content"]

# Функция для обработки команды /quiz
async def quiz(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Програмування", callback_data='quiz_prog')],
        [InlineKeyboardButton("Математика", callback_data='quiz_math')],
        [InlineKeyboardButton("Біологія", callback_data='quiz_biology')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Оберіть тему для квізу:', reply_markup=reply_markup)


# Обработка выбора темы
async def quiz_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    topic = query.data
    question = await generate_quiz_question(topic)
    context.user_data['current_topic'] = topic
    context.user_data['current_question'] = question
    # context.user_data['correct_answer'] = question  # Заглушка, здесь должен быть правильный ответ
    await query.edit_message_text(text=f"Тема: {topic.capitalize()}\nПитання: {question}\nВаш варіант відповіді?")

# Функция для обработки ответов
async def handle_answer(update: Update, context: CallbackContext) -> None:
    user_answer = update.message.text.lower()
    # correct_answer = context.user_data.get('correct_answer', "").lower()
    #
    #
    # if user_answer == correct_answer:
    #     response = "Правильно!"
    # else:
    #     response = f"Неправильно! Правильна відповідь - {correct_answer}"

    data = await send_groq_request('Чи правильна наступна відповідь?' + user_answer)
    response = data["choices"][0]["message"]["content"]
    # if "choices" in data and data["choices"]:
    #     response = data["choices"][0]["message"]["content"]
    # elif "error" in data:
    #     response = f"Помилка від API: {data['error']['message']}"
    # else
    #     response = "Не вдалося отримати питання. Спробуйте ще раз."

    keyboard = [
        [InlineKeyboardButton("Наступне питання", callback_data='next_question')],
        [InlineKeyboardButton("Змінити тему", callback_data='change_topic')],
        [InlineKeyboardButton("Закінчити квіз", callback_data='end_quiz')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(response, reply_markup=reply_markup)

async def handler_message(update: Update, context: CallbackContext) -> None:
    if (context.user_data.get('current_question') != None):
        await handle_answer(update, context)
        context.user_data['current_question'] = None
    else:
        await handle_text(update, context)
        
        app.add_handler(CallbackQueryHandler(quiz_button, pattern='^(quiz_|next_question|change_topic|end_quiz)'))  # Для квиза
    """
