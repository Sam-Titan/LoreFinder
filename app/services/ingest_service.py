import uuid
from datetime import datetime, timezone
from app.db import firestore, chroma
from app.services import acquisition, parser, chunker, summarizer
from app.services.embedder import get_embedder

async def check_duplicate(title: str, author: str) -> str | None:
    return firestore.check_exists(title, author)

async def run_novel_ingestion(doc_id: str, title: str, author: str):
    try:
        # 1. Update status to processing
        firestore.update_status(doc_id, "processing")

        # 2. Acquire raw text
        raw_text, source_url = acquisition.fetch_novel(title, author)
        firestore.get_client().collection("documents").document(doc_id).update({
            "source": source_url
        })
        
        # 3. Parse + detect chapters
        clean = parser.parse_fetched_text(raw_text)
        chapters = parser.detect_chapters(clean)

        # 4. Chunk
        chunks = chunker.chunk_text(chapters)

        # 5. Embed chunks
        embedder = get_embedder()
        chunk_texts = [c["chunk_text"] for c in chunks]
        chunk_vectors = embedder.embed(chunk_texts)

        # 6. Write chunks to Firestore + Chroma
        for chunk in chunks:
            chunk["doc_id"] = doc_id
            firestore.write_chunk(doc_id, chunk)
        chroma.write_chunk_embeddings(doc_id, chunks, chunk_vectors)

        # 7. Mark document ready (chunks done — chapters async)
        firestore.update_status(doc_id, "ready")
        firestore.get_client().collection("documents").document(doc_id).update({
            "progress": "chunks ready, chapter summarization in progress"
        })

        # 8. Summarize chapters (async batch — non-blocking for queries)
        chapters_with_text = chapters  # already have text field
        summarized = await summarizer.summarize_chapters(chapters_with_text)

        # 9. Write chapter summaries to Firestore + embed to Chroma
        chapter_summaries = []
        chapter_vectors = []

        for ch in summarized:
            if ch["status"] != "complete":
                continue
            chapter_record = {
                "chapter_id": f"ch_{uuid.uuid4().hex[:10]}",
                "doc_id": doc_id,
                "chapter_number": ch["chapter_number"],
                "chapter_title": ch["chapter_title"],
                "summary": ch["summary"],
                "chunk_indexes": [
                    c["chunk_id"] for c in chunks  # store chunk_ids, not chunk_index
                    if c["chapter_number"] == ch["chapter_number"]
                ],
                "status": "complete",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            firestore.write_chapter(doc_id, chapter_record)
            chapter_summaries.append(chapter_record)

        if chapter_summaries:
            summary_texts = [ch["summary"] for ch in chapter_summaries]
            chapter_vectors = embedder.embed(summary_texts)
            chroma.write_chapter_embeddings(doc_id, chapter_summaries, chapter_vectors)
            firestore.get_client().collection("documents").document(doc_id).update({
                "progress": "fully indexed"
            })

    except Exception as e:
        firestore.update_status(doc_id, "failed")
        raise e

async def run_pdf_ingestion(session_id: str, file_bytes: bytes):
    try:
        # 1. Parse PDF
        clean = parser.parse_pdf(file_bytes)
        chapters = parser.detect_chapters(clean)

        # 2. Chunk
        chunks = chunker.chunk_text(chapters)

        # 3. Embed + write to temp Chroma only (no Firestore)
        embedder = get_embedder()
        chunk_texts = [c["chunk_text"] for c in chunks]
        vectors = embedder.embed(chunk_texts)
        chroma.write_temp_embeddings(session_id, chunks, vectors)

    except Exception as e:
        # Clean up temp collection if it was partially written
        try:
            chroma.delete_temp_collection(session_id)
        except Exception:
            pass
        raise e