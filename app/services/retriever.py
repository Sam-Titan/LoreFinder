from app.db import chroma

def _merge_dedupe(results_lists: list[list[dict]], top_k: int) -> list[dict]:
    # Chroma distances: lower is more similar. Keep the best (lowest) score per chunk
    # across all query variants, then take the overall top_k.
    best_by_id = {}
    for results in results_lists:
        for r in results:
            rid = r["id"]
            existing = best_by_id.get(rid)
            is_better = (
                existing is None
                or (r["score"] is not None
                    and (existing["score"] is None or r["score"] < existing["score"]))
            )
            if is_better:
                best_by_id[rid] = r
    merged = sorted(
        best_by_id.values(),
        key=lambda r: r["score"] if r["score"] is not None else float("inf")
    )
    return merged[:top_k]

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
    query_vectors: list[list[float]],
    top_k: int = 5
) -> list[dict]:
    results_lists = chroma.search_chunks(
        doc_id=doc_id,
        query_vectors=query_vectors,
        top_k=top_k
    )
    return _merge_dedupe(results_lists, top_k)

def retrieve_broad(
    doc_id: str,
    query_vectors: list[list[float]],
    all_chapter_numbers: list[int],
    top_n: int = 3,
    top_k: int = 5
) -> list[dict]:
    # Stage 1: search chapter summaries
    chapter_results_lists = chroma.search_chapters(
        doc_id=doc_id,
        query_vectors=query_vectors,
        top_n=top_n
    )
    chapter_results = _merge_dedupe(chapter_results_lists, top_n)

    matched_chapters = [
        r["metadata"]["chapter_number"]
        for r in chapter_results
        if r["metadata"].get("chapter_number") is not None
    ]

    if not matched_chapters:
        # Graceful degradation: fall back to narrow search
        return retrieve_narrow(doc_id, query_vectors, top_k)

    # Stage 2: expand ±1 chapter margin
    expanded_chapters = expand_chapter_margin(
        matched_chapters,
        all_chapter_numbers,
        margin=1
    )

    # Stage 3: search chunks restricted to expanded chapter set
    results_lists = chroma.search_chunks(
        doc_id=doc_id,
        query_vectors=query_vectors,
        top_k=top_k,
        chapter_numbers=expanded_chapters
    )
    return _merge_dedupe(results_lists, top_k)

def retrieve_temp(
    session_id: str,
    query_vectors: list[list[float]],
    top_k: int = 5
) -> list[dict]:
    results_lists = chroma.search_temp(
        session_id=session_id,
        query_vectors=query_vectors,
        top_k=top_k
    )
    return _merge_dedupe(results_lists, top_k)