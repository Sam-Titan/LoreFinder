from datetime import datetime, timezone
from app.db import firestore, chroma
from app.services import acquisition, parser, chunker, summarizer
from app.services.embedder import get_embedder

MAX_SUMMARY_CHAPTERS = 100

async def check_duplicate(title: str, author: str) -> str | None:
    return firestore.check_exists(title, author)

async def run_novel_ingestion(doc_id: str, title: str, author: str):
    try:
        doc = firestore.get_document(doc_id)
        phase = doc.get("phase", "start")
        embedder = get_embedder()

        if phase == "start":
            firestore.update_status(doc_id, "processing")

            # Phase 1: Acquire, parse, chunk, embed, write
            existing_source = doc.get("source")
            if existing_source:
                # Retrying after a prior partial attempt — the source was already
                # found, so re-fetch directly instead of re-running the agent search.
                raw_text = acquisition.fetch_url(existing_source)
                source_url = existing_source
            else:
                raw_text, source_url = acquisition.fetch_novel(title, author)

            if len(raw_text.strip()) < 5000:
                raise ValueError(f"Fetched content too short for '{title}'.")
            if len(raw_text) > 10_000_000:
                raw_text = raw_text[:10_000_000]
                print(f"Warning: '{title}' truncated to 10MB.")

            firestore.update_field(doc_id, "source", source_url)

            clean = parser.parse_fetched_text(raw_text, source_url=source_url)
            chapters = parser.detect_chapters(clean)
            chunks = chunker.chunk_text(chapters)

            chunk_vectors = embedder.embed([c["chunk_text"] for c in chunks])
            for chunk in chunks:
                chunk["doc_id"] = doc_id
                # Deterministic id — a retry overwrites the same chunk in place
                # (via upsert) instead of creating an orphaned duplicate.
                cn, ci = chunk["chapter_number"], chunk["chunk_index"]
                chunk["chunk_id"] = f"chunk_{doc_id}_{cn}_{ci}"
                firestore.write_chunk(doc_id, chunk)
            chroma.write_chunk_embeddings(doc_id, chunks, chunk_vectors)

            # Store chapter count for resume reference
            firestore.update_field(doc_id, "chapter_count", len(chapters))
            firestore.update_field(doc_id, "phase", "chunks_complete")
            firestore.update_status(doc_id, "ready")
            firestore.update_field(doc_id, "progress",
                                   "chunks ready, chapter summarization in progress")
            phase = "chunks_complete"

        if phase == "chunks_complete":
            # Find which chapters are already summarized
            existing_chapters = firestore.get_chapters(doc_id)
            done_numbers = {
                ch["chapter_number"] for ch in existing_chapters
                if ch.get("status") == "complete"
            }

            chapter_count = firestore.get_document(doc_id).get("chapter_count", 0)

            # Cap summarization to stay within free tier daily limits
            chapters_to_summarize = min(chapter_count, MAX_SUMMARY_CHAPTERS)

            if chapter_count > MAX_SUMMARY_CHAPTERS:
                print(
                    f"Novel has {chapter_count} chapters — "
                    f"summarizing first {MAX_SUMMARY_CHAPTERS} only."
                )

            pending_numbers = [
                n for n in range(1, chapters_to_summarize + 1)
                if n not in done_numbers
            ]

            if not pending_numbers:
                phase = "summarization_complete"
            else:
                # Reconstruct chapter text from stored chunks — no re-fetch needed
                pending_chapters = []
                for num in pending_numbers:
                    chunk_docs = firestore.get_chunks_by_chapter(doc_id, num)
                    if not chunk_docs:
                        continue
                    sorted_chunks = sorted(chunk_docs, key=lambda x: x["chunk_index"])
                    pending_chapters.append({
                        "chapter_number": num,
                        "chapter_title": sorted_chunks[0].get("chapter_title",
                                                               f"Chapter {num}"),
                        "text": " ".join(c["chunk_text"] for c in sorted_chunks),
                        "status": "pending"
                    })

                # Per-chapter checkpoint — saves immediately after each summary
                async def save_chapter(ch: dict):
                    chunk_docs = firestore.get_chunks_by_chapter(doc_id, ch["chapter_number"])
                    chapter_record = {
                        # Deterministic id — a retry overwrites the same chapter in
                        # place (via upsert) instead of creating an orphaned duplicate.
                        "chapter_id": f"ch_{doc_id}_{ch['chapter_number']}",
                        "doc_id": doc_id,
                        "chapter_number": ch["chapter_number"],
                        "chapter_title": ch["chapter_title"],
                        "summary": ch["summary"],
                        "chunk_indexes": [c["chunk_id"] for c in chunk_docs],
                        "status": "complete",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    firestore.write_chapter(doc_id, chapter_record)
                    vector = embedder.embed([ch["summary"]])[0]
                    chroma.write_chapter_embeddings(doc_id, [chapter_record], [vector])

                await summarizer.summarize_chapters(pending_chapters,
                                                   on_complete=save_chapter)
                phase = "summarization_complete"

        if phase in ("summarization_complete", "chunks_complete"):
            firestore.update_field(doc_id, "phase", "complete")
            firestore.update_field(doc_id, "progress", "fully indexed")

    except ValueError as e:
        firestore.update_status(doc_id, "failed")
        raise
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
        vectors = embedder.embed([c["chunk_text"] for c in chunks])
        chroma.write_temp_embeddings(session_id, chunks, vectors)

    except Exception as e:
        # Clean up temp collection if it was partially written
        try:
            chroma.delete_temp_collection(session_id)
        except Exception:
            pass
        raise e