"""Local development: run the bot in polling mode (no webhook needed)."""
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.config import settings
from app.bot.commands import (
    start_command,
    help_command,
    language_command,
    language_callback,
    disease_command,
    price_command,
    weather_command,
    feedback_command,
)
from app.bot.handlers import (
    handle_photo,
    handle_voice,
    handle_text,
    crop_selection_callback,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("disease", disease_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("feedback", feedback_command))

    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(crop_selection_callback, pattern="^crop_"))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    print("🌾 KhedutSathi bot starting in polling mode...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
