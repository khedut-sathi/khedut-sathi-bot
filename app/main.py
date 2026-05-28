import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.config import settings
from app.bot.commands import (
    start_command, help_command, language_command, language_callback,
    disease_command, price_command, weather_command, feedback_command,
)
from app.bot.handlers import handle_photo, handle_voice, handle_text, crop_selection_callback
from app.bot.onboarding import handle_onboarding_callback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

telegram_app: Application = None


def create_telegram_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("disease", disease_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("feedback", feedback_command))

    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern="^ob_"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(crop_selection_callback, pattern="^crop_"))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    telegram_app = create_telegram_app()
    await telegram_app.initialize()
    await telegram_app.start()

    if settings.webhook_url:
        webhook_url = f"{settings.webhook_url}/webhook"
        await telegram_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")

    yield

    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(title="KhedutSathi Bot", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "bot": "KhedutSathi"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=200)
