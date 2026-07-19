import logging

from config import load_env

load_env()

from bot.telegram_bot import build_application
from database.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)1.1s %(asctime)s %(name)s:%(lineno)d] %(message)s",
)


def main() -> None:
    init_db()
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
