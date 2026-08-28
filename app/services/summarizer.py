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

async def _summarize_one(chapter: dict) -> dict:
    prompt = _PROMPT.format(text=chapter["text"][:8000])
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.GEMINI_MODEL_NAME,
            contents=prompt
        )
        chapter["summary"] = response.text.strip()
        chapter["status"] = "complete"
    except Exception as e:
        print(f"Chapter {chapter['chapter_number']} summarization failed: {e}")
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
    if len(failed) == len(results):
        raise RuntimeError("All chapter summarizations failed.")
    return results