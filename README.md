
# Telegram-бот на базе Yandex Assistant для ответов по документации API Bitrix24

Чат-бот отвечает на вопросы разработчиков по документации [Bitrix24 API](https://apidocs.bitrix24.ru/),
используя RAG (поиск релевантных фрагментов документации через векторный поиск в PostgreSQL/pgvector)
и Yandex Assistant (Yandex GPT) для формирования ответа. Поддерживает как текстовые, так и голосовые вопросы
(распознавание речи через Yandex SpeechKit).

При индексации каждая страница документации делится на смысловые фрагменты (чанки) с учётом заголовков
раздела, а не сохраняется одним большим документом — это даёт более точный поиск. В ответе пользователю
найденный фрагмент передаётся целиком (без обрезания), а под ответом прикладываются кликабельные ссылки
на использованные разделы документации.

## Архитектура

- `bot/` — интеграция с Telegram (`python-telegram-bot`): обработка команд и сообщений.
- `database/` — интеграция с PostgreSQL через SQLAlchemy: пользователи, история вопросов/ответов (с id использованных источников), база знаний с векторными эмбеддингами (pgvector), хранящая документацию поразрядно — чанками, а не целыми страницами.
- `rag/` — обход и парсинг документации (`knowledge_base.py`), деление страниц на смысловые фрагменты (`chunking.py`), эмбеддинги (`embeddings.py`) и интеграция с Yandex Assistant (`yandex_assistant.py`).
- `scripts/` — вспомогательные скрипты, в т.ч. первичное наполнение базы знаний.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Понадобится PostgreSQL с установленным расширением `pgvector`.

## Настройка `.env`

Скопируйте пример ниже в файл `.env` в корне проекта и заполните своими значениями.
Все секретные данные (токены, ключи, пароли) передаются **только** через `.env` -
он указан в `.gitignore` и не должен попадать в репозиторий.

| Переменная | Обязательна | Описание |
| :--- | :---: | ---: |
| `TELEGRAM_BOT_TOKEN` | да | Токен Telegram-бота, полученный у [@BotFather](https://t.me/BotFather). |
| `YC_FOLDER_ID` | да | ID папки (folder) в Yandex Cloud, где включены Foundation Models. |
| `YC_API_KEY` | нет* | Статический API-ключ сервисного аккаунта Yandex Cloud (не протухает). Рекомендуемый способ авторизации. |
| `YC_SERVICE_ACCOUNT_KEY_FILE` | нет* | Путь к JSON-файлу авторизованного ключа сервисного аккаунта (используется, если `YC_API_KEY` не задан; получаемый IAM-токен живёт до 12 часов). |
| `YC_ASSISTANT_ID` | нет | ID уже созданного Yandex Assistant. Если не задан — при первом запуске ассистент будет создан автоматически, а его ID стоит сохранить сюда, чтобы не плодить новых ассистентов при перезапусках. |
| `TELEGRAM_PROXY_URL` | нет | URL SOCKS5/HTTP-прокси для доступа к Telegram API (например, `socks5://127.0.0.1:10808`). Если не задан — бот подключается напрямую. |
| `POSTGRES_HOST` | нет | Хост PostgreSQL. По умолчанию `localhost`. |
| `POSTGRES_PORT` | нет | Порт PostgreSQL. По умолчанию `5432`. |
| `POSTGRES_DB` | да | Имя базы данных PostgreSQL. |
| `POSTGRES_USER` | да | Пользователь PostgreSQL. |
| `POSTGRES_PASSWORD` | да | Пароль пользователя PostgreSQL. |
| `KNOWLEDGE_BASE_URL` | нет | URL, с которого начинается обход документации. По умолчанию `https://apidocs.bitrix24.ru/`. |
| `CHUNK_SIZE` | нет | Максимальный размер смыслового фрагмента (чанка) в символах при индексации страницы. По умолчанию `1200`. |
| `CHUNK_OVERLAP` | нет | Перекрытие (в символах) между соседними чанками одной страницы, чтобы не терять контекст на стыке. По умолчанию `200`. |
| `MIN_CHUNK_SIZE` | нет | Минимальный размер чанка — более мелкие фрагменты склеиваются с соседними. По умолчанию `200`. |
| `RETRIEVAL_TOP_K` | нет | Сколько наиболее релевантных чанков подмешивать в контекст ответа. По умолчанию `5`. |
| `RETRIEVAL_MAX_DISTANCE` | нет | Порог косинусного расстояния — чанки менее релевантные, чем этот порог, отбрасываются. По умолчанию `0.6`. |
| `CRAWL_MAX_PAGES` | нет | Максимальное число страниц за один обход документации. По умолчанию `2000`. |
| `CRAWL_MAX_DEPTH` | нет | Максимальная глубина перехода по ссылкам от стартовой страницы. По умолчанию `6`. |
| `CRAWL_REQUEST_DELAY` | нет | Пауза (в секундах) между запросами страниц при обходе. По умолчанию `0.3`. |

\* Нужен хотя бы один из `YC_API_KEY` / `YC_SERVICE_ACCOUNT_KEY_FILE`.

### Пример `.env`

```env
TELEGRAM_BOT_TOKEN=123456789:AAExampleTelegramBotTokenHere
TELEGRAM_PROXY_URL=socks5://127.0.0.1:10808

YC_FOLDER_ID=b1gExampleFolderId000000
YC_API_KEY=AQVNExampleApiKeyxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Альтернатива YC_API_KEY (заполнять одно из двух):
# YC_SERVICE_ACCOUNT_KEY_FILE=key.json
YC_ASSISTANT_ID=fvtExampleAssistantId000

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bitrix24_rag
POSTGRES_USER=bitrix24_rag
POSTGRES_PASSWORD=change_me

KNOWLEDGE_BASE_URL=https://apidocs.bitrix24.ru/

CHUNK_SIZE=1200
CHUNK_OVERLAP=200
MIN_CHUNK_SIZE=200

RETRIEVAL_TOP_K=5
RETRIEVAL_MAX_DISTANCE=0.6

CRAWL_MAX_PAGES=2000
CRAWL_MAX_DEPTH=6
CRAWL_REQUEST_DELAY=0.3
```

## Запуск

Наполнение базы знаний (обход документации Bitrix24 API):

```bash
python -m scripts.init_knowledge_base --max-pages 50
python -m scripts.init_knowledge_base    
```

Запуск бота:

```bash
python main.py
```
