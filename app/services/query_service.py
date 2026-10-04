import asyncio
import functools
import os
import re
from langchain_groq import ChatGroq
from app.core.config import settings
from app.schemas.query_schema import Category
from app.services.embedder import get_embedder
from app.services import retriever, reranker, bm25_index, ingest_service
from app.db import firestore, chroma
import time

os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME,
    temperature=0,
    max_tokens=10,
    timeout=30,
    max_retries=2,
)

_BROAD_KEYWORDS = {
    "summarize", "summary", "overview", "throughout", "overall", "theme",
    "themes", "arc", "entire", "whole", "pattern", "compare", "across",
    "journey", "experience", "relationship between", "role of", "significance", "describe"
}

_NARROW_KEYWORDS = {
    "who", "what is", "when", "where", "which", "name", "how many",
    "what color", "what did", "exact", "specifically", "chapter", "quote"
}

# Vector/BM25 search over chunk or chapter-summary *content* has no way to
# answer a positional reference like "the opening chapter" or "chapter 5" —
# embedding similarity matches semantic content, not ordinal position, so a
# query like "Describe the opening chapter" was retrieving whatever chunks
# happened to score highest by coincidence, never actually chapter 1.
# Detecting these explicitly and restricting retrieval to the real chapter
# number sidesteps the problem entirely instead of relying on search to find
# something it structurally can't.
_FIRST_CHAPTER_RE = re.compile(r"\b(opening|first|beginning|starting)\s+chapter\b|\bchapter\s+(one|1st)\b")
_LAST_CHAPTER_RE = re.compile(r"\b(last|final|closing|ending)\s+chapter\b")
_NUMBERED_CHAPTER_RE = re.compile(r"\bchapter\s+(\d+)\b")
_ORDINAL_CHAPTER_WORDS = {
    # Ordinals ("the third chapter") and cardinals ("chapter three") both
    # occur naturally, just in opposite word order relative to "chapter" —
    # _detect_explicit_chapter checks both orders for every word here.
    "second": 2, "two": 2, "third": 3, "three": 3, "fourth": 4, "four": 4,
    "fifth": 5, "five": 5, "sixth": 6, "six": 6, "seventh": 7, "seven": 7,
    "eighth": 8, "eight": 8, "ninth": 9, "nine": 9, "tenth": 10, "ten": 10,
}

def _detect_explicit_chapter(query: str) -> int | None:
    q = query.lower()
    if _FIRST_CHAPTER_RE.search(q):
        return 1
    match = _NUMBERED_CHAPTER_RE.search(q)
    if match:
        return int(match.group(1))
    for word, number in _ORDINAL_CHAPTER_WORDS.items():
        # Natural English puts the ordinal before the noun ("the third
        # chapter") but the cardinal after it ("chapter three") — check both
        # orders rather than assuming one.
        if re.search(rf"\b{word}\s+chapter\b", q) or re.search(rf"\bchapter\s+{word}\b", q):
            return number
    return None

def _is_last_chapter_reference(query: str) -> bool:
    return bool(_LAST_CHAPTER_RE.search(query.lower()))

def _is_positional_first_reference(query: str) -> bool:
    return bool(_FIRST_CHAPTER_RE.search(query.lower()))

_TITLED_CHAPTER_RE = re.compile(r"^chapter\s+0*(\d+)\b")

def _resolve_chapter_number(chapters: list[dict], requested: int) -> int:
    # chapter_number is just a sequential index over every detected section —
    # including front matter like "Letter 1"-"Letter 4" before "Chapter 1" in
    # Frankenstein — so it doesn't line up with the number printed in the
    # chapter's own title once a novel has any such front matter. "Chapter 5"
    # means the section actually titled "Chapter 5", not the 5th section
    # overall, so resolve against chapter_title instead of assuming the two
    # match. Falls back to the raw number when no title match exists (e.g. a
    # novel with no front matter, where they're the same number anyway).
    for ch in chapters:
        title_match = _TITLED_CHAPTER_RE.match((ch.get("chapter_title") or "").strip().lower())
        if title_match and int(title_match.group(1)) == requested:
            return ch["chapter_number"]
    return requested

def classify_query_intent(query: str) -> Category:
    q_lower = query.lower()

    # Keyword pre-filter — fast and free
    broad_hits = sum(1 for kw in _BROAD_KEYWORDS if kw in q_lower)
    narrow_hits = sum(1 for kw in _NARROW_KEYWORDS if kw in q_lower)

    if broad_hits > narrow_hits:
        return Category(category="broad")
    if narrow_hits > broad_hits:
        return Category(category="narrow")

    # Ambiguous — fall back to LLM
    try:
        llm = ChatGroq(
            model=settings.GROQ_MODEL_NAME,
            temperature=0,
            max_tokens=5
        )
        system_prompt = (
            "Reply with ONE word only: 'broad' or 'narrow'.\n"
            "broad = summary, themes, patterns, multiple events or characters.\n"
            "narrow = one specific fact, name, event, or detail."
        )
        response = llm.invoke([("system", system_prompt), ("human", query)])
        word = response.content.strip().lower()
        if "broad" in word:
            return Category(category="broad")
        return Category(category="narrow")
    except Exception as e:
        print(f"Classifier failed: {e}. Defaulting to narrow.")
        return Category(category="narrow")
    
def _expand_query(query: str) -> list[str]:
    try:
        llm = ChatGroq(model=settings.GROQ_MODEL_NAME, temperature=0.2, max_tokens=120)
        prompt = (
            "Rephrase this question in 2 different ways to improve search results.\n"
            "Do NOT answer it. Just rephrase.\n"
            "Output exactly 2 lines, one rephrasing per line.\n\n"
            f"Question: {query}"
        )
        response = llm.invoke([("human", prompt)])
        rephrases = [
            q.strip().lstrip("123.-) ")
            for q in response.content.strip().split("\n")
            if q.strip()
        ]
        return [query] + rephrases[:2]
    except Exception:
        return [query]

def embed_query(query: str) -> list[list[float]]:
    queries = _expand_query(query)
    embedder = get_embedder()
    # Return one vector per phrasing — searched and merged separately downstream
    # instead of averaged, so no single phrasing's signal gets diluted.
    # task="retrieval.query": these are search inputs, not indexed content —
    # must differ from the "retrieval.passage" task used at ingest time.
    return embedder.embed(queries, task="retrieval.query")

def _assemble_context(results: list[dict]) -> str:
    parts = []
    for r in results:
        meta = r["metadata"]
        label = meta.get("chapter_title") or f"Chapter {meta.get('chapter_number')}"
        parts.append(
            f"[{label}, Chunk {meta.get('chunk_index')}]\n{r['document']}"
        )
    return "\n\n".join(parts)

def _generate_answer(query: str, context: str) -> str:
    system_prompt = (
        "You are a literary analyst specializing in classic and contemporary fiction. "
        "You are analyzing published, publicly available novels for academic and educational purposes. "
        "Answer the user's question using only the provided excerpts from the text. "
        "Always cite the chapter/letter number and chunk index when referencing content. "
        "If the answer is not in the context, say so clearly."
    )
    human_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    messages = [
        ("system", system_prompt),
        ("human", human_prompt)
    ]

    for attempt in range(3):
        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL_NAME,
                temperature=0.2,
                max_tokens=4096,
                reasoning_effort="low",
                timeout=60,
            )
            response = llm.invoke(messages)
            if not response.content.strip():
                return (
                    "This passage contains content that couldn't be summarized directly. "
                    "Try asking about a specific character, event, or theme from this section."
                )
            return response.content
        except Exception as e:
            if "rate" in str(e).lower() and attempt < 2:
                time.sleep(2 ** attempt * 5)
                continue
            raise

_CANDIDATE_K = 15  # wide candidate pool per query variant — cheap, vector-DB only
_BM25_K = 10         # lexical candidates added alongside the vector pool
_FINAL_K = 5          # narrowed down by the reranker before reaching the LLM

def _union_by_id(*groups: list[dict]) -> list[dict]:
    # No score-scale reconciliation needed — the reranker independently re-scores
    # every candidate against the raw query, regardless of which source found it.
    seen = {}
    for group in groups:
        for item in group:
            seen.setdefault(item["id"], item)
    return list(seen.values())

async def run_query_pipeline(doc_id: str, query: str) -> dict:
    # Every call below is blocking (Firestore/Chroma I/O, CPU-bound BM25/rerank
    # scoring, a synchronous Groq request). Each is run via run_in_executor so it
    # can't stall the event loop for other concurrent requests while it runs.
    loop = asyncio.get_event_loop()

    def run(func, *args, **kwargs):
        return loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    # Parallel: classify + embed
    category, query_vectors = await asyncio.gather(
        run(classify_query_intent, query),
        run(embed_query, query)
    )

    # Route based on doc type and category
    is_pdf = doc_id.startswith("session_")

    async def do_retrieval():
        try:
            if is_pdf:
                return await run(retriever.retrieve_temp, doc_id, query_vectors, top_k=_CANDIDATE_K)
            elif category and category.category == "broad":
                doc = await run(firestore.get_document, doc_id)
                if doc.get("progress") == "chunks ready, chapter summarization in progress":
                    raise ValueError("Chapter summaries are still being processed. Please try a narrow query or wait until fully indexed.")

                chapters = await run(firestore.get_chapters, doc_id)

                chapter_ref = _detect_explicit_chapter(query)
                if chapter_ref is None and _is_last_chapter_reference(query):
                    chapter_ref = doc.get("chapter_count")
                elif chapter_ref is not None and not _is_positional_first_reference(query):
                    chapter_ref = _resolve_chapter_number(chapters, chapter_ref)

                if chapter_ref:
                    # A specific chapter was named directly — chapter-summary
                    # matching has the same ordinal-blindness problem as plain
                    # chunk search, so skip straight to that chapter's chunks
                    # instead of trying to "find" it semantically.
                    vector_candidates, lexical_candidates = await asyncio.gather(
                        run(retriever.retrieve_narrow, doc_id, query_vectors, top_k=_CANDIDATE_K, chapter_numbers=[chapter_ref]),
                        run(bm25_index.search_chunks, doc_id, query, top_k=_BM25_K, chapter_numbers=[chapter_ref])
                    )
                    return _union_by_id(vector_candidates, lexical_candidates)

                all_chapter_numbers = [ch["chapter_number"] for ch in chapters]
                vector_candidates, lexical_candidates = await asyncio.gather(
                    run(
                        retriever.retrieve_broad, doc_id, query_vectors,
                        all_chapter_numbers, top_k=_CANDIDATE_K
                    ),
                    run(bm25_index.search_chunks, doc_id, query, top_k=_BM25_K)
                )
                return _union_by_id(vector_candidates, lexical_candidates)
            else:
                chapter_ref = _detect_explicit_chapter(query)
                if chapter_ref is None and _is_last_chapter_reference(query):
                    doc = await run(firestore.get_document, doc_id)
                    chapter_ref = doc.get("chapter_count") if doc else None
                elif chapter_ref is not None and not _is_positional_first_reference(query):
                    chapters = await run(firestore.get_chapters, doc_id)
                    chapter_ref = _resolve_chapter_number(chapters, chapter_ref)

                vector_candidates, lexical_candidates = await asyncio.gather(
                    run(retriever.retrieve_narrow, doc_id, query_vectors, top_k=_CANDIDATE_K,
                        chapter_numbers=[chapter_ref] if chapter_ref else None),
                    run(bm25_index.search_chunks, doc_id, query, top_k=_BM25_K,
                        chapter_numbers=[chapter_ref] if chapter_ref else None)
                )
                return _union_by_id(vector_candidates, lexical_candidates)
        except ValueError:
            raise  # a real, expected error (e.g. summaries still in progress) — not a storage fault
        except Exception as e:
            # A Chroma client left over from before local storage was wiped
            # out from under an already-running process (rather than a real
            # restart) can throw here instead of just returning empty
            # results — e.g. "attempt to write a readonly database". Reset
            # the cached client so the next attempt gets a fresh one, and
            # treat this the same as "no data yet" so the rebuild-from-
            # Firestore path below gets a chance to run instead of the
            # whole query failing outright.
            print(f"Retrieval failed for doc_id={doc_id!r}, resetting Chroma client: {e}")
            chroma.reset_client()
            return []

    candidates = await do_retrieval()

    if not candidates and not is_pdf:
        # Almost certainly not a genuine "nothing relevant" miss — Chroma's
        # top-k search returns its nearest neighbors regardless of match
        # quality whenever the collection actually has data, so empty
        # candidates for an indexed novel usually means the vector index
        # itself is empty (e.g. wiped by a host restart on a non-persistent
        # disk). Firestore is a separate, durable store that still has the
        # chunk text, so try rebuilding from it before giving up.
        rebuilt = await run(ingest_service.rebuild_chroma_if_missing, doc_id)
        if rebuilt:
            candidates = await do_retrieval()

    if not candidates:
        raise ValueError("No relevant content found for this query.")

    # Cross-encoder reranks the wide candidate pool against the raw query text,
    # then only the top _FINAL_K reach the LLM — context size to the model is unchanged.
    results = await run(reranker.rerank, query, candidates, top_k=_FINAL_K)

    context = _assemble_context(results)
    answer = await run(_generate_answer, query, context)

    citations = [
        {
            "chapter_number": r["metadata"].get("chapter_number"),
            "chapter_title": r["metadata"].get("chapter_title"),
            "chunk_index": r["metadata"].get("chunk_index")
        }
        for r in results
    ]

    return {"answer": answer, "citations": citations}