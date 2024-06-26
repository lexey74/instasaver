import os
import glob
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from instaloader import Instaloader, Post, LoginRequiredException, BadCredentialsException, TwoFactorAuthRequiredException
from dotenv import load_dotenv
import logging
import asyncio
from aiohttp import web
import telegram

# Enable logging to file only
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Replace with your own values loaded from .env
TELEGRAM_BOT_TOKEN = os.getenv("INSTA_TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL_BOT")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS").split(",")

# Convert user IDs to integers
ALLOWED_USER_IDS = [int(user_id.strip()) for user_id in ALLOWED_USER_IDS]

# Dictionary to store last processed URL for each user
last_processed_url = {}

async def start(update, context):
    logger.info("Получена команда /start")
    user_id = update.effective_user.id
    logger.info(f"ID пользователя: {user_id}")
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Извините, вы не авторизованы для использования этого бота.")
        return
    await update.message.reply_text("Добро пожаловать! Отправьте мне URL-адрес поста Instagram, чтобы загрузить его видео и текст. Получить URL можно с помощью кнопки Отправить - Копировать ссылку.")

def clear_temp_directory():
    temp_dir = "temp"
    for f in glob.glob(os.path.join(temp_dir, "*")):
        os.remove(f)
    logger.info("Временная директория очищена.")

async def download_instagram(update, context):
    logger.info("Получен URL или сообщение Instagram")
    user_id = update.effective_user.id
    logger.info(f"ID пользователя: {user_id}")
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Извините, вы не авторизованы для использования этого бота.")
        return

    url = update.message.text
    logger.info(f"Получен текст сообщения: {url}")

    if url.startswith("/"):
        logger.info(f"Получена команда: {url}")
        await start(update, context)
        return

    if not any(segment in url for segment in ["/p/", "/reel/"]):
        await update.message.reply_text("Пожалуйста, отправьте действительный URL-адрес поста Instagram.")
        return

    # Check if the URL was processed before
    if last_processed_url.get(user_id) == url:
        await update.message.reply_text("Этот пост уже был обработан ранее. Попробуйте повторно скопировать ссылку на пост, возможно, она не скопировалась.")
        return

    try:

        L = Instaloader()
        await update.message.reply_text("Авторизуюсь в Instagram...")

        try:
            L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        except BadCredentialsException:
            logger.error("Неправильные учетные данные, пожалуйста, проверьте ваше имя пользователя и пароль.")
            await update.message.reply_text("Произошла ошибка: Неправильные учетные данные, пожалуйста, проверьте ваше имя пользователя и пароль.")
            return
        except TwoFactorAuthRequiredException:
            logger.error("Требуется двухфакторная аутентификация. Пожалуйста, отключите её для этой учетной записи.")
            await update.message.reply_text("Произошла ошибка: Требуется двухфакторная аутентификация. Пожалуйста, отключите её для этой учетной записи.")
            return
        except Exception as e:
            logger.error(f"Произошла неожиданная ошибка во время входа: {e}")
            await update.message.reply_text(f"Произошла ошибка: {e}")
            return

        post_shortcode = url.split("/")[-2]
        logger.info(f"Короткий код поста: {post_shortcode}")
        post = Post.from_shortcode(L.context, post_shortcode)

        # Clear temp directory before download
        clear_temp_directory()

        await update.message.reply_text("Скачиваю пост....")
        # Download post
        L.download_post(post, target="temp")

        # Find the video and image files in the temp directory
        media_files = glob.glob(os.path.join("temp", "*.mp4")) + glob.glob(os.path.join("temp", "*.jpg"))
        if not media_files:
            logger.error(f"Медиафайлы не найдены для короткого кода: {post_shortcode}")
            await update.message.reply_text(f"Произошла ошибка: Медиафайлы не найдены.")
            return

        # Send video and image files
        for media_file in media_files:
            if media_file.endswith(".mp4"):
                with open(media_file, "rb") as vf:
                    await update.message.reply_video(vf)
            elif media_file.endswith(".jpg"):
                with open(media_file, "rb") as img:
                    await update.message.reply_photo(img)
            os.remove(media_file)

        # Send post text
        caption = post.caption if post.caption else "Подпись отсутствует."
        await update.message.reply_text(f"Подпись поста:\n\n{caption}")

        # Store the processed URL
        last_processed_url[user_id] = url

        # Clear temp directory after successful sending
        clear_temp_directory()

    except Exception as e:
        logger.error(f"Ошибка при загрузке поста Instagram: {e}")
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
        # Clear temp directory in case of an error
        clear_temp_directory()

async def handle(request):
    logger.info("Получен запрос вебхука")
    try:
        app = request.app['bot_app']
        data = await request.json()
        logger.info(f"Данные запроса вебхука: {data}")
        update = telegram.Update.de_json(data, app.bot)
        logger.info(f"Обновление: {update}")
        await app.process_update(update)
        logger.info("Обновление обработано")
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        return web.Response(status=500)

async def main():
    logger.info("Запуск бота...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_instagram))

    await application.initialize()
    await application.start()
    
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Вебхук установлен на {WEBHOOK_URL}")

    app = web.Application()
    app['bot_app'] = application
    app.router.add_post('/bot1/', handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 5001)
    await site.start()

    logger.info("Сервер запущен на http://localhost:5001")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем")
    finally:
        await application.stop()
        await application.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

