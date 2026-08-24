import uuid
from app.core.config import settings

def chunk_text(chapters: list[dict]) -> list[dict]:
    chunks = []
    chunk_size = settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP

    for chapter in chapters:
        text = chapter["text"]
        chapter_number = chapter["chapter_number"]
        chapter_title = chapter["chapter_title"]

        words = text.split()
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunks.append({
                "chunk_id": f"chunk_{uuid.uuid4().hex[:12]}",
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text
            })

            chunk_index += 1
            start += chunk_size - overlap

    return chunks