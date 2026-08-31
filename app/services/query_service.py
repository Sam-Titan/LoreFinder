import asyncio
import os
from langchain_groq import ChatGroq
from app.core.config import settings
from app.schemas.query_schema import Category
from app.services.embedder import get_embedder
from app.services import retriever
from app.db import firestore
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

def embed_query(query: str) -> list[float]:
    queries = _expand_query(query)
    embedder = get_embedder()
    vectors = embedder.embed(queries)
    # Average embeddings — covers more semantic space than a single vector
    import numpy as np
    return np.mean(vectors, axis=0).tolist()

def _assemble_context(results: list[dict]) -> str:
    parts = []
    for r in results:
        meta = r["metadata"]
        parts.append(
            f"[Chapter {meta.get('chapter_number')}, "
            f"Chunk {meta.get('chunk_index')}]\n{r['document']}"
        )
    return "\n\n".join(parts)

def _generate_answer(query: str, context: str) -> str:
    system_prompt = (
        "You are an expert literary analyst. Answer the question using ONLY the provided excerpts.\n\n"
        "Rules:\n"
        "1. Never use knowledge outside the provided context.\n"
        "2. Write in clear flowing prose. Avoid bullet points unless listing items is essential.\n"
        "3. Cite sources inline as (Ch. X, Chunk Y) after each claim.\n"
        "4. If the context lacks the answer, respond only with: "
        "'The provided excerpts do not contain enough information to answer this question.'\n"
        "5. Be thorough but do not repeat yourself or pad the response."
    )
    human_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    messages = [
        ("system", system_prompt),
        ("human", human_prompt)
    ]

    for attempt in range(3):
        try:
            llm = ChatGroq(model=settings.GROQ_MODEL_NAME, temperature=0.2, max_tokens=2048, timeout=60)
            response = llm.invoke(messages)
            if not response.content.strip():
                return "The AI safety guardrails prevented generating an answer due to the sensitive or graphic nature of the text."
            return response.content
        except Exception as e:
            if "rate" in str(e).lower() and attempt < 2:
                time.sleep(2 ** attempt * 5)
                continue
            raise

async def run_query_pipeline(doc_id: str, query: str) -> dict:
    # Parallel: classify + embed
    loop = asyncio.get_event_loop()
    category, query_vector = await asyncio.gather(
        loop.run_in_executor(None, classify_query_intent, query),
        loop.run_in_executor(None, embed_query, query)
    )

    # Route based on doc type and category
    is_pdf = doc_id.startswith("session_")

    if is_pdf:
        results = retriever.retrieve_temp(doc_id, query_vector)
    elif category and category.category == "broad":
        doc = firestore.get_document(doc_id)
        if doc.get("progress") == "chunks ready, chapter summarization in progress":
            raise ValueError("Chapter summaries are still being processed. Please try a narrow query or wait until fully indexed.")
        chapters = firestore.get_chapters(doc_id)
        all_chapter_numbers = [ch["chapter_number"] for ch in chapters]
        results = retriever.retrieve_broad(doc_id, query_vector, all_chapter_numbers)
    else:
        results = retriever.retrieve_narrow(doc_id, query_vector)

    if not results:
        raise ValueError("No relevant content found for this query.")

    context = _assemble_context(results)
    answer = _generate_answer(query, context)

    citations = [
        {
            "chapter_number": r["metadata"].get("chapter_number"),
            "chapter_title": r["metadata"].get("chapter_title"),
            "chunk_index": r["metadata"].get("chunk_index")
        }
        for r in results
    ]

    return {"answer": answer, "citations": citations}