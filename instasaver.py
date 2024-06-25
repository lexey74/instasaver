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
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID_BOT"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL_BOT")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

async def start(update, context):
    logger.info("Received /start command")
    user_id = update.effective_user.id
    logger.info(f"User ID: {user_id}")
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    await update.message.reply_text("Welcome! Send me an Instagram post URL to download its video and text.")

def clear_temp_directory():
    temp_dir = "temp"
    for f in glob.glob(os.path.join(temp_dir, "*")):
        os.remove(f)
    logger.info("Temp directory cleared.")

async def download_instagram(update, context):
    logger.info("Received Instagram URL or message")
    user_id = update.effective_user.id
    logger.info(f"User ID: {user_id}")
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    url = update.message.text
    logger.info(f"Received message text: {url}")

    if url.startswith("/"):
        logger.info(f"Received command: {url}")
        await start(update, context)
        return

    if not any(segment in url for segment in ["/p/", "/reel/"]):
        await update.message.reply_text("Please send a valid Instagram post URL.")
        return

    try:
        L = Instaloader()

        try:
            L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        except BadCredentialsException:
            logger.error("Bad credentials, please check your username and password.")
            await update.message.reply_text("An error occurred: Bad credentials, please check your username and password.")
            return
        except TwoFactorAuthRequiredException:
            logger.error("Two-factor authentication is required. Please disable it for this account.")
            await update.message.reply_text("An error occurred: Two-factor authentication is required. Please disable it for this account.")
            return
        except Exception as e:
            logger.error(f"An unexpected error occurred during login: {e}")
            await update.message.reply_text(f"An error occurred: {e}")
            return

        post_shortcode = url.split("/")[-2]
        logger.info(f"Post shortcode: {post_shortcode}")
        post = Post.from_shortcode(L.context, post_shortcode)

        # Clear temp directory before download
        clear_temp_directory()

        # Download post
        L.download_post(post, target="temp")

        # Find the video and image files in the temp directory
        media_files = glob.glob(os.path.join("temp", "*.mp4")) + glob.glob(os.path.join("temp", "*.jpg"))
        if not media_files:
            logger.error(f"Media files not found for shortcode: {post_shortcode}")
            await update.message.reply_text(f"An error occurred: Media files not found.")
            return

        # Send video files
        for media_file in media_files:
            if media_file.endswith(".mp4"):
                with open(media_file, "rb") as vf:
                    await update.message.reply_video(vf)
            elif media_file.endswith(".jpg"):
                with open(media_file, "rb") as img:
                    await update.message.reply_photo(img)
            os.remove(media_file)

        # Send post text
        caption = post.caption if post.caption else "No caption available."
        await update.message.reply_text(f"Post caption:\n\n{caption}")

        # Clear temp directory after successful sending
        clear_temp_directory()

    except Exception as e:
        logger.error(f"Error downloading Instagram post: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")
        # Clear temp directory in case of an error
        clear_temp_directory()

async def handle(request):
    logger.info("Received a webhook request")
    try:
        app = request.app['bot_app']
        data = await request.json()
        logger.info(f"Webhook request data: {data}")
        update = telegram.Update.de_json(data, app.bot)
        logger.info(f"Update: {update}")
        await app.process_update(update)
        logger.info("Processed update")
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        return web.Response(status=500)

async def main():
    logger.info("Starting bot...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_instagram))

    await application.initialize()
    await application.start()
    
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    app = web.Application()
    app['bot_app'] = application
    app.router.add_post('/bot1/', handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 5001)
    await site.start()

    logger.info("Server started on http://localhost:5001")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    finally:
        await application.stop()
        await application.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

