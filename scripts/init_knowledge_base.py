import argparse

from config import load_env

load_env()

from config import get_settings
from database.db import init_db
from rag.knowledge_base import crawl

SEED_URLS = [
    "https://apidocs.bitrix24.ru/",
]


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Наполнение базы знаний Bitrix24 API")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=settings.crawl_max_pages,
        help=f"Максимальное число страниц для обхода (по умолчанию берётся из "
        f"CRAWL_MAX_PAGES в .env, сейчас {settings.crawl_max_pages}; "
        "для быстрого теста укажите небольшое значение, например 10)",
    )
    args = parser.parse_args()

    init_db()
    crawl(SEED_URLS or [settings.knowledge_base_url], max_pages=args.max_pages)
    print("Готово: база знаний обновлена.")


if __name__ == "__main__":
    main()
