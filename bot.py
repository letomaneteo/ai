import os
import logging
from aiohttp import web
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")  # Берем токен из переменной окружения
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Убедись, что добавил URL в переменные окружения Render

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
    await query.answer()  # Ответ на нажатие кнопки
    await query.edit_message_text(text="Вы нажали кнопку!")

# Вебхук для получения обновлений
async def on_update(request):
    json_str = await request.json()  # Получаем запрос от Telegram
    update = Update.de_json(json_str, bot)
    dispatcher.process_update(update)  # Передаем в dispatcher
    return web.Response()  # Возвращаем ответ

# Создаем диспетчер и добавляем обработчики
dispatcher = Dispatcher(bot, update_queue=None)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))

# Устанавливаем вебхук для Telegram
bot.set_webhook(url=WEBHOOK_URL)  # Убедись, что передаешь правильный URL

# Создаем веб-сервер с aiohttp
app = web.Application()
app.router.add_post(f"/{TOKEN}", on_update)

# Запускаем веб-приложение
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Порт на Render
    web.run_app(app, host="0.0.0.0", port=port)
