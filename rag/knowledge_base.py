import logging
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from config import get_settings
from database import get_session, search_similar_documents, replace_document_chunks
from rag.chunking import split_html_into_chunks
from rag.embeddings import embed_document, embed_query

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    url: str
    title: str
    content: str


def _build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "--user-agent=Bitrix24-RAG-Bot/1.0 (+https://apidocs.bitrix24.ru/)"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def fetch_page(driver: webdriver.Chrome, url: str, timeout: float = 15.0) -> str:
    driver.get(url)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    return driver.page_source


def parse_page(url: str, html: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else url

    main = soup.find("article") or soup.find("main") or soup.body
    content = main.get_text(separator="\n", strip=True) if main else ""

    return ParsedPage(url=url, title=title, content=content)


def save_document(page: ParsedPage, html: str) -> int:
    settings = get_settings()
    chunks = split_html_into_chunks(
        html,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        min_chunk_size=settings.min_chunk_size,
    )

    if not chunks:
        chunks = [type("_Fallback", (), {"content": page.content, "section_title": None})()]

    chunk_records = []
    for index, chunk in enumerate(chunks):
        if not chunk.content.strip():
            continue
        embedding = embed_document(chunk.content)
        chunk_records.append(
            {
                "chunk_index": index,
                "content": chunk.content,
                "section_title": chunk.section_title,
                "embedding": embedding,
            }
        )

    with get_session() as session:
        replace_document_chunks(session, url=page.url, title=page.title, chunks=chunk_records)

    return len(chunk_records)


def _extract_links(base_url: str, html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    base_netloc = urlparse(base_url).netloc

    links: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        absolute_url = urljoin(base_url, a_tag["href"])
        parsed = urlparse(absolute_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc != base_netloc:
            continue

        clean_url = parsed._replace(fragment="", query="").geturl()
        links.add(clean_url)

    return links


def crawl(
    seed_urls: list[str],
    max_pages: int | None = None,
    max_depth: int | None = None,
    request_delay: float | None = None,
) -> None:
    settings = get_settings()
    max_pages = settings.crawl_max_pages if max_pages is None else max_pages
    max_depth = settings.crawl_max_depth if max_depth is None else max_depth
    request_delay = settings.crawl_request_delay if request_delay is None else request_delay

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque((url, 0) for url in seed_urls)
    processed = 0

    driver = _build_driver()
    try:
        while queue and processed < max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            try:
                html = fetch_page(driver, url)
            except WebDriverException as exc:
                logger.warning("Не удалось загрузить %s: %s", url, exc)
                continue

            page = parse_page(url, html)
            if len(page.content) > 100:
                chunks_saved = save_document(page, html)
                processed += 1
                logger.info(
                    "[%d/%d] Обработана страница: %s (чанков: %d)",
                    processed,
                    max_pages,
                    url,
                    chunks_saved,
                )

            if depth < max_depth:
                for link in _extract_links(url, html):
                    if link not in visited:
                        queue.append((link, depth + 1))

            time.sleep(request_delay)
    finally:
        driver.quit()

    logger.info("Обход завершён: обработано страниц — %d", processed)


@dataclass
class RetrievedChunk:
    id: int
    url: str
    title: str
    section_title: str | None
    content: str
    distance: float


def retrieve_relevant_chunks(
    query: str, top_k: int | None = None, max_distance: float | None = None
) -> list[RetrievedChunk]:
    settings = get_settings()
    top_k = settings.retrieval_top_k if top_k is None else top_k
    max_distance = settings.retrieval_max_distance if max_distance is None else max_distance

    query_embedding = embed_query(query)

    with get_session() as session:
        results = search_similar_documents(
            session, query_embedding, top_k=top_k, max_distance=max_distance
        )
        return [
            RetrievedChunk(
                id=doc.id,
                url=doc.url,
                title=doc.title,
                section_title=doc.section_title,
                content=doc.content,
                distance=distance,
            )
            for doc, distance in results
        ]


if __name__ == "__main__":
    settings = get_settings()
    crawl([settings.knowledge_base_url])
