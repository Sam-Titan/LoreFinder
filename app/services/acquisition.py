from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
import time

def _safe_get(url: str, timeout: int = 30, retries: int = 3) -> requests.Response:
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429:
                wait = 2 ** attempt * 5  # exponential backoff: 5, 10, 20s
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            return response
        except requests.Timeout:
            if attempt == retries - 1:
                raise
            time.sleep(2)
    raise RuntimeError(f"Failed after {retries} retries: {url}")

# --- Tools (URL discovery only) ---

# pip install langchain langchain-core requests beautifulsoup4 -> Need to install these dependencies
@tool
def search_gutenberg(query: str) -> str:
    """Search Project Gutenberg for a novel. Returns a plain text download URL if found."""
    url = f"https://gutendex.com/books/?search={query}"
    response = _safe_get(url)
    data = response.json()
    if not data["results"]:
        return "Not found on Project Gutenberg."
    book = data["results"][0]
    formats = book.get("formats", {})
    text_url = (
        formats.get("text/plain; charset=utf-8") or
        formats.get("text/plain")
    )
    if text_url:
        return f"URL: {text_url}"
    return "Found but no plain text format available."

@tool
def search_standard_ebooks(query: str) -> str:
    """Search Standard Ebooks for a novel. Returns a page URL if found."""
    url = f"https://standardebooks.org/ebooks?query={query}"
    response = _safe_get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    result = soup.find("article", class_="ebook")
    if not result:
        return "Not found on Standard Ebooks."
    link = result.find("a")
    if link:
        return f"URL: https://standardebooks.org{link['href']}"
    return "Found but no link available."

@tool
def search_archive_org(query: str) -> str:
    """Search Archive.org for a novel. Returns a plain text download URL if found."""
    url = (
        f"https://archive.org/advancedsearch.php"
        f"?q={query}&fl[]=identifier&rows=1&output=json&mediatype=texts"
    )
    response = _safe_get(url)
    data = response.json()
    docs = data.get("response", {}).get("docs", [])
    if not docs:
        return "Not found on Archive.org."
    identifier = docs[0]["identifier"]
    return f"URL: https://archive.org/download/{identifier}/{identifier}_djvu.txt"

# --- Internal fetch (outside agent loop) ---

def fetch_url(url: str) -> str:
    # Stream large files instead of loading into memory at once
    response = requests.get(url, timeout=120, stream=True)
    content_type = response.headers.get("Content-Type", "")

    chunks = []
    for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
        if chunk:
            chunks.append(chunk)
    raw = "".join(chunks)

    if "text/plain" in content_type:
        return raw

    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text(separator="\n")

# --- Source allowlist (SSRF guard) ---

_ALLOWED_HOSTS = {"gutenberg.org", "gutendex.com", "standardebooks.org", "archive.org"}

def _is_allowed_source(url: str) -> bool:
    # The agent's final answer is LLM-generated text, not a guaranteed tool
    # result — a crafted title/author could coerce it into returning an
    # arbitrary URL. Never fetch anything outside the sources we actually
    # searched, so the LLM can't be used to make this server request
    # attacker-chosen (including internal/private) hosts.
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS)

# --- Agent ---

def fetch_novel(title: str, author: str) -> tuple[str, str]:
    """
    Finds and fetches a public domain novel.
    Returns (raw_text, source_url).
    """
    tools = [search_gutenberg, search_standard_ebooks, search_archive_org]

    llm = ChatGroq(
        model=settings.GROQ_MODEL_NAME,
        temperature=0,
        api_key=settings.GROQ_API_KEY
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an assistant that locates public domain novels.
Search Project Gutenberg first, then Standard Ebooks, then Archive.org.
Return only the raw download URL. Nothing else."""),
        ("human", "Find the novel '{title}' by '{author}'."),
        ("placeholder", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6
    )

    result = executor.invoke({"title": title, "author": author})
    source_url = result.get("output", "").strip()

    if not source_url or "not found" in source_url.lower():
        raise ValueError(f"Could not locate '{title}' by {author} on any source.")

    if not _is_allowed_source(source_url):
        raise ValueError(f"Refusing to fetch from an untrusted source: {source_url}")

    # Fetch text directly — not through the agent
    raw_text = fetch_url(source_url)

    if not raw_text.strip():
        raise ValueError(f"Fetched empty content from {source_url}.")

    return raw_text, source_url