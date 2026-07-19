from __future__ import annotations
from dataclasses import dataclass
from bs4 import BeautifulSoup

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
BLOCK_TAGS = ("p", "li", "pre", "blockquote", "td", "th", "dd", "dt")
_ALL_TAGS = list(HEADING_TAGS) + list(BLOCK_TAGS)


@dataclass
class Chunk:
    content: str
    section_title: str | None


def _extract_content_lines(main) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = []
    for el in main.find_all(_ALL_TAGS):
        if el.find_parent(BLOCK_TAGS):
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        lines.append((text, el.name in HEADING_TAGS))
    return lines


def _pack_lines_into_chunks(
    lines: list[tuple[str, bool]],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int,
) -> list[Chunk]:
    raw_chunks: list[str] = []
    chunk_headings: list[str | None] = []

    current = ""
    current_heading: str | None = None
    last_heading: str | None = None

    def flush() -> None:
        nonlocal current, current_heading
        if current.strip():
            raw_chunks.append(current.strip())
            chunk_headings.append(current_heading)
        current = ""
        current_heading = None

    for text, is_heading in lines:
        if is_heading:
            last_heading = text

        candidate = f"{current}\n{text}".strip() if current else text
        if len(candidate) <= chunk_size:
            current = candidate
            if current_heading is None:
                current_heading = last_heading
            continue

        flush()
        if len(text) <= chunk_size:
            current = text
            current_heading = last_heading
        else:
            start = 0
            while start < len(text):
                end = start + chunk_size
                raw_chunks.append(text[start:end].strip())
                chunk_headings.append(last_heading)
                start = end - chunk_overlap if end - chunk_overlap > start else end
            current = ""
            current_heading = None

    flush()

    if not raw_chunks:
        return []
    merged_chunks: list[str] = []
    merged_headings: list[str | None] = []
    i = 0
    while i < len(raw_chunks):
        text, heading = raw_chunks[i], chunk_headings[i]
        if len(text) < min_chunk_size and i + 1 < len(raw_chunks):
            raw_chunks[i + 1] = f"{text}\n{raw_chunks[i + 1]}"
            chunk_headings[i + 1] = heading or chunk_headings[i + 1]
        elif len(text) < min_chunk_size and merged_chunks:
            merged_chunks[-1] = f"{merged_chunks[-1]}\n{text}"
        else:
            merged_chunks.append(text)
            merged_headings.append(heading)
        i += 1
    raw_chunks, chunk_headings = merged_chunks, merged_headings

    if chunk_overlap <= 0 or len(raw_chunks) <= 1:
        return [Chunk(content=c, section_title=h) for c, h in zip(raw_chunks, chunk_headings)]
    overlapped: list[Chunk] = [Chunk(content=raw_chunks[0], section_title=chunk_headings[0])]
    for i in range(1, len(raw_chunks)):
        tail = raw_chunks[i - 1][-chunk_overlap:]
        overlapped.append(
            Chunk(content=f"{tail}\n{raw_chunks[i]}", section_title=chunk_headings[i])
        )
    return overlapped


def split_html_into_chunks(
    html: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    min_chunk_size: int = 200,
) -> list[Chunk]:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("article") or soup.find("main") or soup.body
    if main is None:
        return []
    lines = _extract_content_lines(main)
    return _pack_lines_into_chunks(lines, chunk_size, chunk_overlap, min_chunk_size)