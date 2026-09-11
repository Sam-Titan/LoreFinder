from google import genai
from google.genai import types
from app.core.config import settings
import asyncio

client = genai.Client(api_key=settings.GEMINI_API_KEY)

_PROMPT = """You are a literary analyst. Summarize the following chapter concisely.
Focus on: key events, character actions, important revelations, and themes introduced.
Keep the summary under 200 words.

Chapter text:
{text}
"""

async def _summarize_one(chapter: dict, max_attempts: int = 3) -> dict:
    prompt = _PROMPT.format(text=chapter["text"][:8000])
    last_error = None
    for attempt in range(max_attempts):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.GEMINI_MODEL_NAME,
                contents=prompt
            )
            chapter["summary"] = response.text.strip()
            chapter["status"] = "complete"
            return chapter
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt * 5)  # 5s, 10s

    print(
        f"Chapter {chapter['chapter_number']} summarization failed after "
        f"{max_attempts} attempts: {last_error}"
    )
    chapter["summary"] = ""
    chapter["status"] = "failed"
    return chapter

async def summarize_chapters(chapters: list[dict], on_complete=None) -> list[dict]:
    results = []
    batch_size = 5
    for i in range(0, len(chapters), batch_size):
        batch = chapters[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[_summarize_one(ch) for ch in batch]
        )
        for ch in batch_results:
            if ch["status"] == "complete" and on_complete:
                await on_complete(ch)  # save immediately after each chapter
        results.extend(batch_results)
        if i + batch_size < len(chapters):
            await asyncio.sleep(20)

    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        # Raise on ANY leftover failure (not just total failure) — the caller's
        # exception propagates up to the Celery task, which retries the whole
        # ingestion. The existing phase/resumability logic then only reprocesses
        # chapters still not marked "complete", so successful ones aren't redone.
        failed_numbers = [r["chapter_number"] for r in failed]
        raise RuntimeError(
            f"Chapter summarization failed for chapters {failed_numbers} "
            f"after retries ({len(failed)}/{len(results)})."
        )
    return results