from app.db import chroma

def expand_chapter_margin(
    chapter_numbers: list[int],
    all_chapter_numbers: list[int],
    margin: int = 1
) -> list[int]:
    expanded = set()
    for num in chapter_numbers:
        for offset in range(-margin, margin + 1):
            neighbor = num + offset
            if neighbor in all_chapter_numbers:
                expanded.add(neighbor)
    return sorted(expanded)

def retrieve_narrow(
    doc_id: str,
    query_vector: list[float],
    top_k: int = 5
) -> list[dict]:
    return chroma.search_chunks(
        doc_id=doc_id,
        query_vector=query_vector,
        top_k=top_k
    )

def retrieve_broad(
    doc_id: str,
    query_vector: list[float],
    all_chapter_numbers: list[int],
    top_n: int = 3,
    top_k: int = 5
) -> list[dict]:
    # Stage 1: search chapter summaries
    chapter_results = chroma.search_chapters(
        doc_id=doc_id,
        query_vector=query_vector,
        top_n=top_n
    )

    matched_chapters = [
        r["metadata"]["chapter_number"]
        for r in chapter_results
        if r["metadata"].get("chapter_number") is not None
    ]

    if not matched_chapters:
        # Graceful degradation: fall back to narrow search
        return retrieve_narrow(doc_id, query_vector, top_k)

    # Stage 2: expand ±1 chapter margin
    expanded_chapters = expand_chapter_margin(
        matched_chapters,
        all_chapter_numbers,
        margin=1
    )

    # Stage 3: search chunks restricted to expanded chapter set
    return chroma.search_chunks(
        doc_id=doc_id,
        query_vector=query_vector,
        top_k=top_k,
        chapter_numbers=expanded_chapters
    )

def retrieve_temp(
    session_id: str,
    query_vector: list[float],
    top_k: int = 5
) -> list[dict]:
    return chroma.search_temp(
        session_id=session_id,
        query_vector=query_vector,
        top_k=top_k
    )