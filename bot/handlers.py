import logging
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from database import get_or_create_user, get_session, save_question
from rag.knowledge_base import RetrievedChunk, retrieve_relevant_chunks
from rag.speech_to_text import recognize_voice
from rag.yandex_assistant import YandexAssistantRAG

logger = logging.getLogger(__name__)
_assistant_rag = YandexAssistantRAG()

def _format_sources(chunks: list[RetrievedChunk]) -> str:
    unique_sources: dict[str, str] = {}
    for chunk in chunks:
        unique_sources.setdefault(chunk.url, chunk.title)

    if not unique_sources:
        return ""

    lines = [
        f'{i}. <a href="{escape(url)}">{escape(title)}</a>'
        for i, (url, title) in enumerate(unique_sources.items(), start=1)
    ]
    return "📚 Источники:\n" + "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот-помощник по документации API Bitrix24. "
        "Задайте вопрос текстом или голосом, и я найду ответ в документации "
        "(https://apidocs.bitrix24.ru/)."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Просто напишите вопрос по API Bitrix24, например:\n"
        "«Как получить список сделок через метод crm.deal.list?»"
    )


async def _answer_question(update: Update, question_text: str) -> None:
    telegram_user = update.effective_user

    with get_session() as session:
        user = get_or_create_user(session, telegram_user.id, telegram_user.username)
        user_id = user.id

    try:
        context_chunks = retrieve_relevant_chunks(question_text)
        answer_text = await _assistant_rag.ask(question_text, context_chunks)
    except Exception:
        logger.exception("Ошибка при обработке вопроса пользователя %s", telegram_user.id)
        await update.message.reply_text(
            "Произошла ошибка при обращении к базе знаний. Попробуйте ещё раз позже."
        )
        return

    await update.message.reply_text(answer_text)

    sources_text = _format_sources(context_chunks)
    if sources_text:
        await update.message.reply_text(
            sources_text, parse_mode="HTML", disable_web_page_preview=True
        )

    source_doc_ids = ",".join(dict.fromkeys(str(chunk.id) for chunk in context_chunks)) or None

    with get_session() as session:
        save_question(
            session,
            user_id=user_id,
            question_text=question_text,
            answer_text=answer_text,
            source_doc_ids=source_doc_ids,
        )


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(action="typing")
    await _answer_question(update, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(action="typing")

    voice_file = await update.message.voice.get_file()
    audio_bytes = bytes(await voice_file.download_as_bytearray())

    try:
        question_text = recognize_voice(audio_bytes)
    except Exception:
        logger.exception(
            "Ошибка распознавания голоса для пользователя %s", update.effective_user.id
        )
        await update.message.reply_text(
            "Не удалось распознать голосовое сообщение. Попробуйте ещё раз "
            "или напишите вопрос текстом."
        )
        return

    if not question_text.strip():
        await update.message.reply_text(
            "Не удалось разобрать речь в сообщении. Попробуйте ещё раз "
            "или напишите вопрос текстом."
        )
        return

    await update.message.reply_text(f"Распознанный вопрос: «{question_text}»")
    await _answer_question(update, question_text)
