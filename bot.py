import os
import logging
from aiohttp import web
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# Читаем переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Проверка переменных окружения
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо указать переменные окружения BOT_TOKEN и WEBHOOK_URL!")

# Создаем бота и приложение
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()
logger.info("Application initialized successfully")

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
    await query.answer()
    await query.edit_message_text(text="Вы нажали кнопку!")

# Вебхук для получения обновлений
async def on_update(request):
    json_str = await request.json()
    logger.info(f"Received update: {json_str}")
    update = Update.de_json(json_str, bot)
    if update:
        await application.process_update(update)
    else:
        logger.warning("Failed to parse update")
    return web.Response()

# Добавляем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))

# Устанавливаем вебхук
async def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    await bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

if WEBHOOK_URL:
    import asyncio
    asyncio.run(set_webhook())

# Создаем веб-сервер
app = web.Application()
app.router.add_post(f"/{TOKEN}", on_update)

# Запускаем приложение
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
