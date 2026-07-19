from __future__ import annotations
from sqlalchemy.orm import Session
from database.models import KnowledgeDocument, Question, User

def get_or_create_user(session: Session, telegram_id: int, username: str | None) -> User:
    user = session.query(User).filter(User.telegram_id == telegram_id).one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        session.flush()
    return user


def save_question(
    session: Session,
    user_id: int,
    question_text: str,
    answer_text: str | None,
    source_doc_ids: str | None = None,
) -> Question:
    question = Question(
        user_id=user_id,
        question_text=question_text,
        answer_text=answer_text,
        source_doc_ids=source_doc_ids,
    )
    session.add(question)
    session.flush()
    return question


def replace_document_chunks(
    session: Session,
    url: str,
    title: str,
    chunks: list[dict],
) -> list[KnowledgeDocument]:
    session.query(KnowledgeDocument).filter(KnowledgeDocument.url == url).delete(
        synchronize_session=False
    )

    documents = [
        KnowledgeDocument(
            url=url,
            title=title,
            chunk_index=chunk["chunk_index"],
            section_title=chunk.get("section_title"),
            content=chunk["content"],
            embedding=chunk.get("embedding"),
        )
        for chunk in chunks
    ]
    session.add_all(documents)
    session.flush()
    return documents


def search_similar_documents(
    session: Session,
    query_embedding: list[float],
    top_k: int = 5,
    max_distance: float = 0.6,
) -> list[tuple[KnowledgeDocument, float]]:
    results = (
        session.query(
            KnowledgeDocument,
            KnowledgeDocument.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .filter(KnowledgeDocument.embedding.is_not(None))
        .order_by("distance")
        .limit(top_k)
        .all()
    )
    return [(doc, distance) for doc, distance in results if distance <= max_distance]
