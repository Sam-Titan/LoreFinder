import pymupdf  # PyMuPDF
import re
import fitz

# pip install pymupdf unstructured -> Need to install these dependencies
def parse_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    return clean_text("\n".join(pages))

def parse_gutenberg(raw_text: str) -> str:
    # Strip Gutenberg header + footer boilerplate
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "***START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "***END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
    ]
    text = raw_text

    for marker in start_markers:
        idx = text.upper().find(marker.upper())
        if idx != -1:
            # Move past the marker line
            text = text[idx:]
            text = text[text.find("\n") + 1:]
            break

    for marker in end_markers:
        idx = text.upper().find(marker.upper())
        if idx != -1:
            text = text[:idx]
            break

    return clean_text(text)

def parse_standard_ebooks(raw_html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "html.parser")
    # Remove nav, header, footer elements
    for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
        tag.decompose()
    return clean_text(soup.get_text(separator="\n"))

def parse_archive_org(raw_text: str) -> str:
    # Archive.org djvu text often has page markers like <Page N>
    text = re.sub(r"<Page \d+>", "\n", raw_text)
    return clean_text(text)

def parse_fetched_text(raw_text: str, source_url: str = "") -> str:
    url = source_url.lower()
    if "gutenberg.org" in url or "gutendex.com" in url:
        return parse_gutenberg(raw_text)
    if "standardebooks.org" in url:
        return parse_standard_ebooks(raw_text)
    if "archive.org" in url:
        return parse_archive_org(raw_text)
    # Generic fallback
    text = re.sub(r"<[^>]+>", " ", raw_text)
    return clean_text(text)

def clean_text(text: str) -> str:
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def detect_chapters(text: str) -> list[dict]:
    pattern = re.compile(
        r"^[ \t]*((?:chapter|letter)\s+(?:[\d]+|[ivxlcdm]+|one|two|three|four|five|"
        r"six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
        r"sixteen|seventeen|eighteen|nineteen|twenty(?:-\w+)?|thirty(?:-\w+)?|"
        r"forty(?:-\w+)?|fifty(?:-\w+)?)\b[\s\:\-\.]*[^\n]*)",  # added \. here
        re.IGNORECASE | re.MULTILINE
    )
    matches = list(pattern.finditer(text))

    raw_chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapter_text = text[start:end].strip()
        raw_chapters.append({
            "title": match.group(0).strip().split("\n")[0][:60],
            "text": chapter_text
        })

    # Filter TOC entries — real chapters have substantial text
    chapters = []
    for ch in raw_chapters:
        if len(ch["text"].split()) < 150:
            continue  # skip TOC entries and false positives
        chapters.append({
            "chapter_number": len(chapters) + 1,  # renumber after filtering
            "chapter_title": ch["title"],
            "text": ch["text"]
        })

    if len(chapters) <= 1:
        print("No chapter structure found — using size-based split.")
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