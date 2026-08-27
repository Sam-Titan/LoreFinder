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
    pattern = re.compile(
        r"^((?:chapter|letter)\s+(?:[\d]+|[ivxlcdm]+|one|two|three|four|five|"
        r"six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
        r"sixteen|seventeen|eighteen|nineteen|twenty(?:-\w+)?|thirty(?:-\w+)?|"
        r"forty(?:-\w+)?|fifty(?:-\w+)?)[\s\:\-]*[^\n]*)",
        re.IGNORECASE | re.MULTILINE
    )
    matches = list(pattern.finditer(text))

    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append({
            "chapter_number": i + 1,
            "chapter_title": match.group(0).strip().split("\n")[0][:60],
            "text": text[start:end].strip()
        })

    # Fallback: split by word count if no chapters found or only 1 detected
    if len(chapters) <= 1:
        print("No chapter structure detected — using size-based split.")
        chapters = _split_by_size(text, target_words=3000)

    return chapters

def _split_by_size(text: str, target_words: int = 3000) -> list[dict]:
    words = text.split()
    chapters = []
    total = len(words)
    num_chapters = max(1, total // target_words)
    chunk_size = total // num_chapters

    for i in range(num_chapters):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_chapters - 1 else total
        chapters.append({
            "chapter_number": i + 1,
            "chapter_title": f"Section {i + 1}",
            "text": " ".join(words[start:end])
        })
        
    return chapters