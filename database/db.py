import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker, Session

from config import get_settings
from database.models import Base

logger = logging.getLogger(__name__)

_settings = get_settings()

engine = create_engine(_settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_knowledge_documents_to_chunks() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE knowledge_documents "
                "ADD COLUMN IF NOT EXISTS chunk_index INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE knowledge_documents "
                "ADD COLUMN IF NOT EXISTS section_title VARCHAR(512)"
            )
        )

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'uq_knowledge_documents_url_chunk'
                        ) THEN
                            ALTER TABLE knowledge_documents
                            ADD CONSTRAINT uq_knowledge_documents_url_chunk
                            UNIQUE (url, chunk_index);
                        END IF;
                    END $$;
                    """
                )
            )
    except DBAPIError:
        logger.warning(
            "Не удалось добавить ограничение уникальности (url, chunk_index) "
            "на knowledge_documents — вероятно, есть дублирующиеся строки от "
            "старой схемы. Запустите `python -m scripts.init_knowledge_base`, "
            "чтобы переиндексировать базу знаний чанками.",
            exc_info=True,
        )


def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    _migrate_knowledge_documents_to_chunks()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS knowledge_documents_embedding_hnsw_idx "
                "ON knowledge_documents USING hnsw (embedding vector_cosine_ops)"
            )
        )


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
