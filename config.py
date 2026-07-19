import os
from dataclasses import dataclass
from dotenv import load_dotenv

def load_env(dotenv_path: str | None = None) -> None:
    load_dotenv(dotenv_path=dotenv_path, override=False)

def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная '{name}'.")
    return value

def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))

def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    yc_folder_id: str
    yc_api_key: str | None
    yc_service_account_key_file: str | None
    yc_assistant_id: str | None
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    knowledge_base_url: str
    telegram_proxy_url: str | None

    chunk_size: int
    chunk_overlap: int
    min_chunk_size: int

    retrieval_top_k: int
    retrieval_max_distance: float

    crawl_max_pages: int
    crawl_max_depth: int
    crawl_request_delay: float

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=_get_required("TELEGRAM_BOT_TOKEN"),
        yc_folder_id=_get_required("YC_FOLDER_ID"),
        yc_api_key=os.getenv("YC_API_KEY"),
        yc_service_account_key_file=os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE"),
        yc_assistant_id=os.getenv("YC_ASSISTANT_ID"),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=_get_required("POSTGRES_DB"),
        postgres_user=_get_required("POSTGRES_USER"),
        postgres_password=_get_required("POSTGRES_PASSWORD"),
        knowledge_base_url=os.getenv("KNOWLEDGE_BASE_URL", "https://apidocs.bitrix24.ru/"),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL") or None,
        chunk_size=_get_int("CHUNK_SIZE", 1200),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 200),
        min_chunk_size=_get_int("MIN_CHUNK_SIZE", 200),
        retrieval_top_k=_get_int("RETRIEVAL_TOP_K", 5),
        retrieval_max_distance=_get_float("RETRIEVAL_MAX_DISTANCE", 0.6),
        crawl_max_pages=_get_int("CRAWL_MAX_PAGES", 2000),
        crawl_max_depth=_get_int("CRAWL_MAX_DEPTH", 6),
        crawl_request_delay=_get_float("CRAWL_REQUEST_DELAY", 0.3),
    )