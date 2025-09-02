import os
import logging
import random
import requests
import firebase_admin
from firebase_admin import credentials, db
from aiohttp import web
import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.ext import MessageHandler, filters
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram import Update
from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import json
import cloudinary
import cloudinary.uploader
# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо установить BOT_TOKEN и WEBHOOK_URL!")

# Создаём бота и приложение
application = Application.builder().token(TOKEN).build()
logger.info("Application created successfully")


def update_image_clicks(image_url):
    # Создаём безопасный ключ, убирая или заменяя недопустимые символы
    safe_key = image_url.replace(':', '_').replace('.', '_').replace('/', '_').replace('https', '').replace('http', '')
    ref = db.reference(f"image_clicks/{safe_key}")
    clicks = ref.get().get("clicks", 0) if ref.get() else 0
    ref.set({"clicks": clicks + 1})

ADMIN_ID = 6932848487  # замени на свой Telegram user_id

# Инициализация Cloudinary
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

async def send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Нет доступа.")

    if not context.args or len(context.args) < 2:
        return await update.message.reply_text("❗ Формат: /send <user_id> <текст и ссылка>")

    try:
        user_id = int(context.args[0])
        message_parts = context.args[1:]

        # Ищем ссылку на изображение
        image_url = None
        for part in message_parts:
            if part.startswith("http") and any(part.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                image_url = part
                break

        if not image_url:
            return await update.message.reply_text("❗ Не найдена ссылка на изображение (.jpg/.png/.gif/.webp)")

        # Удаляем ссылку из текста и собираем остальное в caption
        message_parts.remove(image_url)
        caption = ' '.join(message_parts).strip()

        await context.bot.send_photo(chat_id=user_id, photo=image_url, caption=caption or None)
        await update.message.reply_text(f"✅ Отправлено пользователю {user_id}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка Firebase

import json

firebase_credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if not firebase_credentials_json:
    raise ValueError("Не найдена переменная окружения GOOGLE_APPLICATION_CREDENTIALS_JSON!")

cred_info = json.loads(firebase_credentials_json)
cred = credentials.Certificate(cred_info)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://botchoiseimage-default-rtdb.europe-west1.firebasedatabase.app/'
})



def get_images_from_google_sheets(user_id, sheet_number):
    sheet_name = str(sheet_number).zfill(3)  # "000", "001", "002"
    url = f"https://script.google.com/macros/s/AKfycbwEHVw_Ywb-oJY6NbZkZzxMUjeNypKg_vCXVxxbn1vlEjnEZCh92-U1E2YXEiikETjn/exec?userId={user_id}&sheetName={sheet_name}"
    logger.info(f"Запрос к Google Sheets: {url}")
    response = requests.get(url)
    data = response.json()
    logger.info(f"Полученные данные: {data}")
    return data

def save_to_firebase(user_id, choice, is_correct, image_url):
    ref = db.reference(f"user_choices/{user_id}")
    user_data = ref.get() or {}

    correct = user_data.get("correct", 0)
    wrong = user_data.get("wrong", 0)

    if is_correct:
        correct += 1
    else:
        wrong += 1

    ref.set({"correct": correct, "wrong": wrong})
    update_image_clicks(image_url)  # Добавлено для записи кликов

def get_user_stats(user_id):
    ref = db.reference(f"user_choices/{user_id}")
    user_data = ref.get() or {}
    return user_data.get("correct", 0), user_data.get("wrong", 0)

async def menu(update: Update, context: CallbackContext) -> None:
    # Кнопки меню с ссылками на веб-страницы
    menu_keyboard = [
        [KeyboardButton("Competition rules", web_app={"url": "https://letomaneteo.github.io/myweb/rulesAIAdealBotIN.html"})],
        [KeyboardButton("Правила конкурса, подробности теста", web_app={"url": "https://letomaneteo.github.io/myweb/rulesAIIdealBot.html"})],
        [KeyboardButton("Exciting random game/Игра (ru)", web_app={"url": "https://letomaneteo.github.io/myweb/newpage.html"})]
    ]

    # Создание клавиатуры с кнопками
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True, one_time_keyboard=False)

    # Отправка сообщения с кнопками
    await update.message.reply_text("Read the instructions", reply_markup=reply_markup)

async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Блокируем повторный запуск игры, если она уже идет
    if context.user_data.get("game_active", False):
        await update.message.reply_text(
            '⏳The bot cannot be restarted between rounds. It restarts automatically only after elimination during the test. Meanwhile, the countdown keeps going.😓If you couldn’t start the bot, please contact <a href="https://t.me/Gordaniele">technical support</a>.',
            parse_mode="HTML"
        )
        return

    context.user_data["game_active"] = True  # Флаг активности игры

    name = update.message.from_user.first_name

    # Отправляем GIF баннер перед приветствием
    gif_url = "https://res.cloudinary.com/dkkq2bacn/video/upload/v1743234126/output_wmx9hc.mp4"
    await update.message.reply_animation(animation=gif_url)

    # Получаем статистику
    total_correct, total_wrong = get_user_stats(user_id)
    total_games = total_correct + total_wrong

    stats_text = f"Your general statistics:\n✅ Correct: {total_correct}\n❌ Incorrect: {total_wrong}"
    if total_games > 0:
        accuracy = round(total_correct / total_games * 100, 2)
        stats_text += f"\n🎯 Accuracy: {accuracy}%"
    else:
        stats_text += "\nYou haven't played yet!"

    keyboard = [[InlineKeyboardButton("Start the test", callback_data="start_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
    f"✅ Great, {name}!\n\n"
    "The test is starting. Choose the picture taken by a real photographer, NOT generated by AI.\n"
    "⏳ Time to choose: ⚠️15 seconds⚠️.\n\n"
    "🎁 You can win a prize!\n"
    "ℹ️ More information is available in the blue Menu button. ⬇"
    "— — — — — — — — — — — — — — — — — — — —\n\n"
    f"✅ Отлично, {name}!\n\n" "Начинаем тест. Выберите картинку, которая сделана фотографом, а НЕ сгенерирована нейросетью.\n" "⏳ Время выбора: ⚠️15 секунд⚠️.\n\n" "🎁 Вы можете выиграть приз!\n" "Дополнительная информация находится в синей кнопке Меню. ⬇"
    f"{stats_text}",
    reply_markup=reply_markup
)



async def send_images(chat_id, context: CallbackContext) -> None:
    if context.user_data["rounds"] >= 10:
        await show_results(chat_id, context)
        return

    if not context.user_data["current_images"]:
        context.user_data["current_images"] = get_images_from_google_sheets()

    images = context.user_data["current_images"]

    correct_images = [img for img in images if img["is_correct"] == 1 and img["image_url"] not in context.user_data["used_images"]]
    wrong_images = [img for img in images if img["is_correct"] == 0 and img["image_url"] not in context.user_data["used_images"]]

    if not correct_images or not wrong_images:
        await context.bot.send_message(chat_id, "🚨You missed a choice in this place, which reduces the number of points. Be careful!🚨")
        await show_results(chat_id, context)
        return

    correct_image = random.choice(correct_images)
    wrong_image = random.choice(wrong_images)

    image_list = [correct_image, wrong_image]
    random.shuffle(image_list)

    context.user_data["used_images"].add(correct_image["image_url"])
    context.user_data["used_images"].add(wrong_image["image_url"])
    context.user_data["current_image_urls"] = [image_list[0]["image_url"], image_list[1]["image_url"]]

    keyboard1 = [[InlineKeyboardButton("Choose", callback_data=f"choose_1_{image_list[0]['is_correct']}")]]
    keyboard2 = [[InlineKeyboardButton("Choose", callback_data=f"choose_2_{image_list[1]['is_correct']}")]]

    reply_markup1 = InlineKeyboardMarkup(keyboard1)
    reply_markup2 = InlineKeyboardMarkup(keyboard2)

    msg1 = await context.bot.send_photo(chat_id=chat_id, photo=image_list[0]["image_url"], reply_markup=reply_markup1)
    msg2 = await context.bot.send_photo(chat_id=chat_id, photo=image_list[1]["image_url"], reply_markup=reply_markup2)

    context.user_data["messages"] = [msg1.message_id, msg2.message_id]

    # Сбрасываем флаг "ответил" перед новой парой картинок
    context.user_data["answered"] = False

    # Запускаем таймер на удаление кнопок
    if "timer_task" in context.user_data and not context.user_data["timer_task"].done():
        context.user_data["timer_task"].cancel()  # Отменяем предыдущий таймер

    context.user_data["timer_task"] = asyncio.create_task(remove_buttons_after_timeout(chat_id, context, [msg1.message_id, msg2.message_id]))


async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    await query.answer()

    # Удаляем кнопки из сообщения, на которое нажали (например, "Начать тест" или "Продолжить")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Не удалось удалить reply_markup: {e}")

    if query.data in ["start_game", "continue_game"]:
        ref = db.reference(f"user_progress/{user_id}")
        progress = ref.get() or {"completed_sheets": []}

        max_sheets = 3  # Установи лимит листов
        if len(progress["completed_sheets"]) >= max_sheets:
            await show_results(chat_id, context)
            return

        # Определяем следующий номер листа (начиная с 0)
        sheet_number = len(progress["completed_sheets"])  # 0, 1, 2
        sheet_name = str(sheet_number).zfill(3)  # "000", "001", "002"

        if sheet_name not in progress["completed_sheets"]:
            progress["completed_sheets"].append(sheet_name)
            ref.set(progress)

        # Загружаем данные для текущего листа
        images = get_images_from_google_sheets(user_id, sheet_number)

        # Проверяем, вернул ли Apps Script сообщение о завершении
        if isinstance(images, dict) and "message" in images:
            await show_results(chat_id, context)
            return

        # Сбрасываем данные пользователя для нового листа
        context.user_data["rounds"] = 0
        context.user_data["correct"] = 0
        context.user_data["wrong"] = 0
        context.user_data["used_images"] = set()
        context.user_data["current_images"] = images
        await context.bot.send_message(chat_id, f"Let's start the set {sheet_name}")  # Отладка
        await send_images(chat_id, context)
        return

    # Обработка выбора изображения (без изменений)
    data = query.data.split('_')
    choice = int(data[1])
    is_correct = int(data[2])
    user_id = query.from_user.id

    # Удаляем кнопки с предыдущих изображений
    for msg_id in context.user_data.get("messages", []):
        try:
            await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.warning(f"Error while deleting buttons: {e}")

    # Отменяем таймер, если он был запущен
    if "timer_task" in context.user_data and not context.user_data["timer_task"].done():
        context.user_data["timer_task"].cancel()
        del context.user_data["timer_task"]

    # Сохраняем выбор пользователя
    save_to_firebase(user_id, choice, is_correct, context.user_data["current_image_urls"][choice - 1])

    context.user_data["rounds"] += 1
    context.user_data["correct"] += 1 if is_correct else 0
    context.user_data["wrong"] += 0 if is_correct else 1

    response_text = f"You have selected the option {choice}: {'✅ Right!' if is_correct else '❌ Wrong!'}"
    await query.message.reply_text(response_text)

    context.user_data["answered"] = True

    # Отправляем следующую пару изображений
    await send_images(chat_id, context)

async def remove_buttons_after_timeout(chat_id, context: CallbackContext, message_ids):
    await asyncio.sleep(15)

    # Если пользователь уже ответил, не удаляем кнопки
    if context.user_data.get("answered", False):
        return

    for msg_id in message_ids:
        try:
            await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
        except Exception as e:
            if "Message is not modified" not in str(e):  # Игнорируем ошибку, если кнопок уже нет
                logger.warning(f"Ошибка при удалении кнопок: {e}")

    await context.bot.send_message(chat_id, "⏳ 15 seconds have expired, answer not counted.")
    await send_images(chat_id, context)

async def show_results(chat_id, context: CallbackContext) -> None:
    correct = context.user_data.get("correct", 0)
    wrong = context.user_data.get("wrong", 0)
    total = correct + wrong

    result_text = f"""🏁 *Test completed!*
You did it {total} elections.
✅ Correct: {correct}
❌ Incorrect: {wrong}
🎯 Accuracy: {round(correct / total * 100, 2) if total > 0 else 0}%"""

    # Проверяем прогресс пользователя
    user_id = context._user_id or chat_id
    ref = db.reference(f"user_progress/{user_id}")
    progress = ref.get() or {"completed_sheets": []}
    max_sheets = 3  # Лимит листов


    # Добавляем кнопку "Продолжить" в любом случае
    keyboard = [[InlineKeyboardButton("Continue", callback_data="continue_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Если лимит достигнут, добавляем примечание
    if len(progress["completed_sheets"]) >= max_sheets:
        result_text += f"\n\nYou have completed all sets ({max_sheets}/{max_sheets}). The 'Continue' button is inactive."

    await context.bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=reply_markup)

import cloudinary.uploader
import datetime

async def handle_media(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    ref = db.reference(f"user_uploads/{user_id}")

    try:
        user_data = ref.get() or {"count": 0}
    except Exception:
        await update.message.reply_text("Database error. Try again later.")
        return

    if user_data["count"] >= 7:
        await update.message.reply_text("You have already uploaded 7 files. Further uploads are unavailable.")
        return

    caption = update.message.caption or ""
    if update.message.photo:
        file = update.message.photo[-1].file_id
        resource_type = "image"
    elif update.message.video:
        file = update.message.video.file_id
        resource_type = "video"
    elif update.message.document:
        file = update.message.document.file_id
        resource_type = "auto"
    else:
        await update.message.reply_text("I only accept photos, videos and documents.")
        return

    try:
        file_obj = await context.bot.get_file(file)
        file_url = file_obj.file_path

        # Создаем уникальный public_id с user_id и датой
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        public_id = f"{user_id}_{timestamp}"

        # Загружаем напрямую в Cloudinary по URL
        upload_result = cloudinary.uploader.upload(
            file_url,
            resource_type=resource_type,
            folder=f"user_uploads/{user_id}",
            public_id=public_id
        )

        # Сохраняем информацию о файле и подпись в Firebase
        ref.child(f"files/{user_data['count'] + 1}").set({
            "cloudinary_url": upload_result["secure_url"],
            "caption": caption,
            "public_id": public_id,
            "upload_time": timestamp
        })
        ref.update({"count": user_data["count"] + 1})

        reply_text = f"Thank you! File saved. ({user_data['count'] + 1}/7)."
        if caption:
            reply_text += f"\nПодпись: {caption}"
        await update.message.reply_text(reply_text)

    except Exception as e:
        print(e)
        await update.message.reply_text("Error uploading file.")
# === Импорты твоих функций из старого файла ===
# (сюда вставим start, button, menu, send_to_user, handle_media, и все вспомогательные)

# Пример:
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     ...

# Добавляем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("menu", menu))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
application.add_handler(CommandHandler("send", send_to_user))

# === Вебхуки и сервер ===

async def on_update(request):
    try:
        json_str = await request.json()
        update = Update.de_json(json_str, application.bot)
        if update:
            await application.process_update(update)
        return web.Response()
    except Exception as e:
        logger.error(f"Error handling update: {e}")
        return web.Response(status=500)

async def health_check(request):
    return web.Response(text="Server is running")

# Устанавливаем вебхук
async def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")

# Инициализация на старте
async def on_startup(app):
    await application.initialize()
    await set_webhook()

# Остановка при выключении
async def on_shutdown(app):
    await application.stop()
    await application.bot.session.close()
    logger.info("Application and Bot остановлены")

# Создаём веб-приложение
app = web.Application()
app.router.add_post(f"/{TOKEN}", on_update)
app.router.add_get("/health", health_check)
app.router.add_get("/", health_check)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
