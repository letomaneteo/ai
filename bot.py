import os
import logging
from aiohttp import web
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext import Application

TOKEN = os.getenv("BOT_TOKEN")  # Добавьте свой токен через переменную окружения
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL для вебхука (например, https://your-app-name.onrender.com/)

bot = Bot(token=TOKEN)

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Обработчик команд
async def start(update: Update, context):
    await update.message.reply_text("Привет! Я бот.")

# Обработчик кнопок
async def button(update: Update, context):
    query = update.callback_query
    await query.answer()  # Это подтверждение, чтобы кнопка не блокировалась
    # Логика нажатия на кнопку
    await query.edit_message_text(text="Вы нажали кнопку!")

# Вебхук для получения обновлений
async def on_update(request):
    json_str = await request.json()
    update = Update.de_json(json_str, bot)
    dispatcher.process_update(update)
    return web.Response()

# Создаём диспетчер и добавляем обработчики
dispatcher = Dispatcher(bot, update_queue=None)

# Добавляем обработчики команд и кнопок
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))

# Создаем веб-сервер с aiohttp
app = web.Application()
app.router.add_post(f"/{TOKEN}", on_update)

# Запускаем веб-приложение на порту 8080
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
