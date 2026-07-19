import logging
from typing import TYPE_CHECKING

from yandex_cloud_ml_sdk import AsyncYCloudML

from config import get_settings

if TYPE_CHECKING:
    from rag.knowledge_base import RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "Ты — ассистент технической поддержки разработчиков, который отвечает "
    "на вопросы по документации API Bitrix24 (https://apidocs.bitrix24.ru/). "
    "Отвечай точно, кратко и по делу, опираясь только на переданный контекст "
    "из документации. Если в контексте нет ответа — честно скажи, что не нашёл "
    "информацию, и предложи посмотреть соответствующий раздел документации. "
    "Ссылки на источники в текст ответа сам не добавляй и не придумывай — "
    "список использованных разделов документации будет прикреплён отдельно."
)


class YandexAssistantRAG:
    def __init__(self) -> None:
        settings = get_settings()
        self._sdk = AsyncYCloudML(folder_id=settings.yc_folder_id, auth=settings.yc_api_key)
        self._assistant = None

    async def _get_assistant(self):
        if self._assistant is None:
            settings = get_settings()
            if settings.yc_assistant_id:
                self._assistant = await self._sdk.assistants.get(settings.yc_assistant_id)
            else:
                self._assistant = await self._sdk.assistants.create(
                    "yandexgpt",
                    instruction=SYSTEM_INSTRUCTION,
                )
                logger.info(
                    "Создан новый Yandex Assistant, id=%s. Чтобы переиспользовать "
                    "его при следующих запусках (а не плодить новых), сохраните "
                    "этот ID в .env как YC_ASSISTANT_ID.",
                    self._assistant.id,
                )
        return self._assistant

    async def ask(self, question: str, context_chunks: list["RetrievedChunk"]) -> str:
        assistant = await self._get_assistant()
        thread = await self._sdk.threads.create()

        if context_chunks:
            context_text = "\n\n---\n\n".join(
                f"Раздел: {chunk.title}"
                + (f" / {chunk.section_title}" if chunk.section_title else "")
                + f"\nСсылка: {chunk.url}\n{chunk.content}"
                for chunk in context_chunks
            )
            await thread.write(
                f"Контекст из документации Bitrix24 API:\n\n{context_text}"
            )

        await thread.write(question)

        run = await assistant.run(thread)
        result = await run
        return result.text
