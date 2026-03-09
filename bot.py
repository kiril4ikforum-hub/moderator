import telebot

# Вставьте сюда ваш токен, который вы получили от BotFather
TOKEN = "8594010470:AAEF5eeIfVlPNdsqZbH9fQM2Yc1iHhHOQ7U"

# Создаем экземпляр бота
bot = telebot.TeleBot(TOKEN)

# Обработчик команд /start и /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Эта функция будет вызвана, когда пользователь отправит команды /start или /help.
    """
    bot.reply_to(message, "Привет! Я простой бот. Я умею отвечать на /start, /help и повторять за тобой любые сообщения.")

# Обработчик всех текстовых сообщений
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """
    Эта функция будет вызвана для любого текстового сообщения.
    Она просто повторяет (отвечает) текст сообщения пользователя.
    """
    bot.reply_to(message, message.text)

# Запускаем бота
print("Бот запущен и готов к работе...")
bot.infinity_polling()
