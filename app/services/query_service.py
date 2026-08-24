import asyncio
import os
from langchain_groq import ChatGroq
from app.core.config import settings
from app.schemas.query_schema import Category
from app.services.embedder import get_embedder
from app.services import retriever
from app.db import firestore

os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME,
    temperature=0,
    max_tokens=10,
    timeout=30,
    max_retries=2,
)

def classify_query_intent(query: str) -> Category | None:
    model = _llm.with_structured_output(Category)
    system_prompt = """You are a query-intent classifier for a novel knowledge system.
Classify the user's query into exactly one category:

- broad: requires overview, summary, multiple concepts, characters, or spans a large portion of the novel.
- narrow: asks about one specific fact, character, event, chapter, or detail.
"""
    messages = [("system", system_prompt), ("human", query)]
    try:
        return model.invoke(messages)
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
    llm = ChatGroq(
        model=settings.GROQ_MODEL_NAME,
        temperature=0.2,
        max_tokens=1000,
        timeout=30,
    )
    prompt = f"""You are a literary assistant. Answer the user's question using only the provided context.
Always cite the chapter number and chunk index when referencing content.
If the answer is not in the context, say so clearly.

Context:
{context}

Question: {query}

Answer:"""
    response = llm.invoke(prompt)
    return response.content

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