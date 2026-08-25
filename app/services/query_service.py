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

def classify_query_intent(query: str) -> Category | None:
    llm = ChatGroq(model=settings.GROQ_MODEL_NAME, temperature=0, max_tokens=5)
    system_prompt = """Classify the query as exactly one word: 'broad' or 'narrow'.
- broad: overview, themes, multiple characters or events, whole book
- narrow: specific fact, character, event, chapter, or detail
Reply with only the word. Nothing else."""
    messages = [("system", system_prompt), ("human", query)]
    try:
        response = llm.invoke(messages)
        word = response.content.strip().lower()
        if "broad" in word:
            return Category(category="broad")
        return Category(category="narrow")
    except Exception as e:
        print(f"Classifier failed: {e}")
        return None

def embed_query(query: str) -> list[float]:
    embedder = get_embedder()
    return embedder.embed([query])[0]

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
    prompt = f"""You are a literary assistant. Answer the user's question using only the provided context.
    Always cite the chapter number and chunk index when referencing content.
    If the answer is not in the context, say so clearly.
    
    Context:
    {context}
    
    Question: {query}
    
    Answer:"""
    for attempt in range(3):
        try:
            llm = ChatGroq(model=settings.GROQ_MODEL_NAME, temperature=0.2, max_tokens=1000, timeout=30)
            response = llm.invoke(prompt)
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