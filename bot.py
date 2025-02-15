import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, Application, CallbackQueryHandler, ContextTypes, CommandHandler, MessageHandler, filters, CallbackContext
from gpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu,
                  default_callback_handler, load_prompt)
import credentials
import httpx
from credentials import GROQ_API_KEY
from credentials import BOT_TOKEN

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
    await send_image(update, context, "gpt")  # Отправляем изображение
    await send_text(update, context, text)  # Отправляем текстовое сообщение

    if not user_message:
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
    ("Курт Кобейн", 'talk_cobain'),
    ("Стівен Гокінг", 'talk_hawking'),
    ("Фрідріх Ніцше", 'talk_nietzsche'),
    ("Королева Єлизавета II", 'talk_queen'),
    ("Дж.Р.Р. Толкін", 'talk_tolkien')
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
    keyboard = [[InlineKeyboardButton(name, callback_data=data)] for name, data in personalities]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_image(update, context, 'talk')
    await send_text(update, context, "Оберіть особистість для діалогу:")
    await update.message.reply_text("Оберіть особистість для діалогу:", reply_markup=reply_markup)

async def talk_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_code = f"talk_{query.data.split('_')[1]}"
    selected_name = next((name for name, code in personalities if code == selected_code), selected_code)
    print(f"Обраний персонаж:  {selected_name} ({selected_code})")
    prompt = load_prompt(selected_code)
    if prompt is None:
        await query.edit_message_text(text=f"Промт для {selected_name} не знайдено.")
        return
    await query.edit_message_text(text=f"Ви вибрали {selected_name}. Задавайте питання.")
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
    await send_text(update, context, content)

'''4.Квіз'''

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
app.add_handler(CommandHandler("quiz", quiz))
# app.add_handler(CallbackQueryHandler(button, pattern='^(menu_|other_)'))  # Обрабатывает только свои кнопки (если они создаются)
app.add_handler(CallbackQueryHandler(talk_button, pattern='^talk_'))  # Для общения с личностью
app.add_handler(CallbackQueryHandler(quiz_button, pattern='^(quiz_|next_question|change_topic|end_quiz)'))  # Для квиза

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_message))  # Обрабатываем текстовые сообщения

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

app.add_handler(CallbackQueryHandler(default_callback_handler, pattern='^talk_*'))
#app.run_polling()
#print(f"GROQ_API_KEY загружен: {GROQ_API_KEY[:5]}********")
