import os
import logging
from aiohttp import web
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Читаем переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Проверка переменных окружения
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо указать переменные окружения BOT_TOKEN и WEBHOOK_URL!")

# Создаем бота и приложение
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()
logger.info("Application created successfully")

# Инициализация приложения и бота
async def init_application():
    await bot.initialize()          # Инициализация Bot
    await application.initialize()  # Инициализация Application
    logger.info("Bot and Application initialized successfully")

# Обработчик команд
async def start(update: Update, context):
    logger.info("Processing /start command")
    await update.message.reply_text("Привет! Я бот.")

# Обработчик кнопок
async def button(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Вы нажали кнопку!")

# Вебхук для получения обновлений
async def on_update(request):
    try:
        json_str = await request.json()
        logger.info(f"Received update: {json_str}")
        update = Update.de_json(json_str, bot)
        if update:
            logger.info(f"Update object: {update}")
            await application.process_update(update)
            logger.info("Update processed successfully")
        else:
            logger.warning("Failed to parse update")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
    return web.Response()
  
async def health_check(request):
    return web.Response(text="Server is running")
app.router.add_get("/health", health_check)

# Добавляем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))

# Устанавливаем вебхук
async def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    await bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

# Остановка приложения и бота
async def stop_application():
    await application.stop()
    await bot.stop()
    logger.info("Application and Bot stopped successfully")

# Создаем веб-сервер
app = web.Application()
app.router.add_post(f"/{TOKEN}", on_update)

# Добавляем обработку запуска и остановки сервера
async def on_startup(_):
    await init_application()
    await set_webhook()

async def on_shutdown(_):
    await stop_application()

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Запускаем приложение
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
