from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers import handle_question, handle_voice, help_command, start_command
from config import get_settings


def build_application() -> Application:
    settings = get_settings()

    builder = ApplicationBuilder().token(settings.telegram_bot_token)

    if settings.telegram_proxy_url:
        request = HTTPXRequest(
            proxy=settings.telegram_proxy_url,
            connect_timeout=20.0,
            read_timeout=20.0,
        )
        builder = builder.request(request)

    application = builder.build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)
    )

    return application
