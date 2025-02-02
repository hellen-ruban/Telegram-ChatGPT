# Telegram ChatGPT Bot
Це бот для Telegram, який використовує ChatGPT для обробки запитів користувачів.

## Опис проекту
Цей проект створений для інтеграції бота в Telegram з використанням ChatGPT. Бот підтримує кілька функцій:
- Отримання випадкових цікавих фактів.
- Спілкування з відомими особистостями.
- Взаємодія з ChatGPT для отримання відповідей на питання користувачів.

## Установка
1. Клонуйте репозиторій:
git clone https://github.com/hellen-ruban/-Telegram-ChatGPT-.git

2. Перейдіть до директорії проекту:
cd -Telegram-ChatGPT-

3. Створіть віртуальне середовище та активуйте його:
- Для Windows:
  ```
  python -m venv .venv
  .\.venv\Scripts\activate
  ```
- Для macOS/Linux:
  ```
  python3 -m venv .venv
  source .venv/bin/activate
  ```

4. Встановіть залежності:
  pip install -r requirements.txt

5. Створіть файл `credentials.py` і додайте ваші токени:
```python
    BOT_TOKEN = 'your-telegram-bot-token'
    ChatGPT_TOKEN = 'your-chatgpt-api-token'

6. Запустіть бота:
   python bot.py

Використання:
/start - Почати роботу з ботом та побачити головне меню.
/gpt - Задати питання ChatGPT.
/talk - Спілкування з відомими особистостями.
/random - Отримати випадковий цікавий факт.

Ліцензія:
Цей проект має відкриту ліцензію, будь ласка, перевірте ліцензійні умови в файлі LICENSE.

Якщо у вас є питання або пропозиції, ви можете звертатися до мене через GitHub або за допомогою електронної пошти dominga5000b.c@gmail.com.

