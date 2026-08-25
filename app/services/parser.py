import pymupdf  # PyMuPDF
import re

# pip install pymupdf unstructured -> Need to install these dependencies
def parse_pdf(file_bytes: bytes) -> str:
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    raw_text = "\n".join(pages)
    return clean_text(raw_text)

def parse_fetched_text(raw_text: str) -> str:
    # Strip HTML tags if present
    text = re.sub(r"<[^>]+>", " ", raw_text)
    return clean_text(text)

def clean_text(text: str) -> str:
    # Normalize whitespace
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def detect_chapters(text: str) -> list[dict]:
    # Matches patterns like: Chapter 1, CHAPTER ONE, Chapter I
    pattern = re.compile(
        r"^((?:chapter|letter)\s+(?:[\d]+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten"
        r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
        r"|twenty(?:-\w+)?|thirty(?:-\w+)?|forty(?:-\w+)?|fifty(?:-\w+)?|sixty|seventy|eighty|ninety|hundred)"
        r"[\s\:\-]*[^\n]*)",
        re.IGNORECASE | re.MULTILINE  # MULTILINE makes ^ match line starts
    )
    
    matches = list(pattern.finditer(text))

    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append({
            "chapter_number": i + 1,
            "chapter_title": match.group(0).strip(),
            "text": text[start:end].strip()
        })

    # If no chapters detected, treat whole text as one chapter
    if not chapters:
        chapters.append({
            "chapter_number": i + 1,
            "chapter_title": match.group(0).strip().split("\n")[0][:60],  # cap at 60 chars
            "text": text[start:end].strip()
        })

    return chapters