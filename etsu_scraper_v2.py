"""
etsu_scraper_v2.py
------------------
Improved ETSU web scraper with smarter content extraction.
Handles both etsu.edu and catalog.etsu.edu page structures.

HOW TO RUN:
1. Make sure Docker is running (docker compose up)
2. pip install requests beautifulsoup4 chromadb openai tqdm
3. export OPENAI_API_KEY=your_key_here
4. python etsu_scraper_v2.py

This version CLEARS the existing collection and rebuilds from scratch
to fix the navigation text issue from the first scrape.
"""

import os
import re
import time
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

# ── CONFIG ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
CHROMA_HOST     = "localhost"
CHROMA_PORT     = 8001
COLLECTION_NAME = "web_information"
EMBEDDING_MODEL = "text-embedding-3-large"
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50
DELAY_SECONDS   = 0.5
MAX_PAGES       = 6000
BASE_DOMAINS    = ["etsu.edu", "catalog.etsu.edu"]

SKIP_PATTERNS = [
    "/brand/", "/giving/", "/alumni/", "/_resources", "/wp-content/",
    "/wp-admin/", "/feed/", "/tag/", "/author/",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".mp3",
    "javascript:", "mailto:", "tel:",
    "/search?", "/print/", "?print", "?format=",
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "youtube.com",
]

SEED_URLS = [
    # Main site
    "https://www.etsu.edu/",
    "https://www.etsu.edu/admissions/",
    "https://www.etsu.edu/admissions/undergraduate/",
    "https://www.etsu.edu/admissions/freshman/",
    "https://www.etsu.edu/admissions/transfer/",
    "https://www.etsu.edu/admissions/graduate/",
    "https://www.etsu.edu/admissions/international/",
    "https://www.etsu.edu/gradschool/",
    "https://www.etsu.edu/gradschool/admissions/",
    "https://www.etsu.edu/ehome/majors/",
    "https://www.etsu.edu/ehome/majors/bachelors/",
    "https://www.etsu.edu/ehome/majors/graduate/",
    "https://www.etsu.edu/students/",
    "https://www.etsu.edu/financial-aid/",
    "https://www.etsu.edu/paying-for-college/",
    "https://www.etsu.edu/housing/",
    "https://www.etsu.edu/dining/",
    "https://www.etsu.edu/its/",
    "https://www.etsu.edu/library/",
    "https://www.etsu.edu/health/",
    "https://www.etsu.edu/cas/",
    "https://www.etsu.edu/cbat/",
    "https://www.etsu.edu/coe/",
    "https://www.etsu.edu/nursing/",
    "https://www.etsu.edu/com/",
    "https://www.etsu.edu/pharmacy/",
    "https://www.etsu.edu/online/",
    "https://www.etsu.edu/registrar/",
    "https://www.etsu.edu/bursar/",
    "https://www.etsu.edu/career/",
    "https://www.etsu.edu/diversity/",
    "https://www.etsu.edu/international/",
    "https://www.etsu.edu/veterans/",
    "https://www.etsu.edu/disability/",
    "https://www.etsu.edu/counseling/",
    "https://www.etsu.edu/recreation/",
    "https://www.etsu.edu/parking/",
    "https://www.etsu.edu/safety/",
    "https://www.etsu.edu/research/",
    "https://www.etsu.edu/honors/",
    "https://www.etsu.edu/graduate/",
    "https://www.etsu.edu/athletics/",
    # Catalog
    "https://catalog.etsu.edu/",
    "https://catalog.etsu.edu/index.php?catoid=61",
    "https://catalog.etsu.edu/content.php?catoid=61&navoid=3935",
    "https://catalog.etsu.edu/content.php?catoid=61&navoid=3936",
]


# ── CONTENT EXTRACTION ────────────────────────────────────────────────────────

def extract_text(soup, url):
    """
    Extract clean content using site-specific selectors.
    Tries multiple selectors in order of specificity.
    """
    # Remove boilerplate elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "aside", "form", "noscript", "iframe",
                      "button", "input", "select"]):
        tag.decompose()

    # Get title
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    # Try selectors in order — most specific first
    # catalog.etsu.edu uses 'block_content' td
    # etsu.edu uses various main content divs
    selectors = [
        ("td", {"class": "block_content"}),          # ETSU catalog pages
        ("div", {"id": "acalog-content"}),            # catalog detail pages
        ("div", {"class": "acalog-content"}),
        ("div", {"id": "main-content"}),
        ("div", {"class": "main-content"}),
        ("div", {"id": "content"}),
        ("div", {"class": "content"}),
        ("div", {"role": "main"}),
        ("main", {}),
        ("article", {}),
        ("div", {"id": "main"}),
        ("div", {"class": "page-content"}),
        ("div", {"class": "entry-content"}),
    ]

    content = None
    for tag, attrs in selectors:
        found = soup.find(tag, attrs) if attrs else soup.find(tag)
        if found:
            text = found.get_text(separator=" ", strip=True)
            # Only use if it has meaningful content (not just nav links)
            if len(text.split()) > 50:
                content = text
                break

    # Last resort — full page text
    if not content:
        content = soup.get_text(separator=" ", strip=True)

    # Clean up whitespace
    content = re.sub(r'\s+', ' ', content).strip()

    return title, content


def get_last_updated(soup, response_headers):
    """Extract last updated date from page or headers."""
    text_patterns = [
        r'last\s+updated[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'last\s+modified[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'updated[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(\b(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},\s+\d{4}\b)',
    ]
    page_text = soup.get_text(separator=" ")
    for pattern in text_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            parsed = parse_date_string(match.group(1).strip())
            if parsed:
                return parsed, "page_text"

    last_modified = response_headers.get("Last-Modified", "")
    if last_modified:
        parsed = parse_date_string(last_modified)
        if parsed:
            return parsed, "http_header"

    return datetime.today().strftime("%Y-%m-%d"), "scrape_date"


def parse_date_string(raw):
    formats = [
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%m/%d/%Y",
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %Z",
    ]
    raw = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return None


def should_skip(url):
    url_lower = url.lower()
    for pattern in SKIP_PATTERNS:
        if pattern in url_lower:
            return True
    parsed = urlparse(url)
    if not any(domain in parsed.netloc for domain in BASE_DOMAINS):
        return True
    return False


def get_links(soup, base_url):
    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        clean = parsed._replace(fragment="").geturl().rstrip("/")
        if not should_skip(clean):
            links.add(clean)
    return links


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 100:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def make_id(url, chunk_index):
    return hashlib.md5(f"{url}__v2__{chunk_index}".encode()).hexdigest()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def scrape_and_embed():
    print("\n🚀 ETSU Scraper v2 — Improved Content Extraction")
    print(f"   Max pages: {MAX_PAGES} | Chunk size: {CHUNK_SIZE} words\n")

    print("Connecting to ChromaDB...")
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(allow_reset=True, anonymized_telemetry=False)
    )

    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=EMBEDDING_MODEL
    )

    # Delete and recreate collection for a clean rebuild
    print("Clearing old collection for clean rebuild...")
    try:
        client.delete_collection(COLLECTION_NAME)
        print("Old collection deleted.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=openai_ef,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"Fresh collection created.\n")

    visited = set()
    queue = list(SEED_URLS)
    scraped_pages = []
    total_chunks = 0
    failed_pages = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ETSUBucBuddyBot/2.0)"
    })

    with tqdm(total=MAX_PAGES, desc="Scraping") as pbar:
        while queue and len(visited) < MAX_PAGES:
            url = queue.pop(0)

            if url in visited or should_skip(url):
                continue
            visited.add(url)

            try:
                resp = session.get(url, timeout=12)
                if resp.status_code != 200:
                    continue
                if "text/html" not in resp.headers.get("Content-Type", ""):
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                title, text = extract_text(soup, url)

                # Skip if too little content
                if len(text.split()) < 80:
                    continue

                last_updated, date_source = get_last_updated(soup, resp.headers)

                # Collect new links
                for link in get_links(soup, url):
                    if link not in visited:
                        queue.append(link)

                # Chunk and embed
                chunks = chunk_text(text)
                if not chunks:
                    continue

                ids = [make_id(url, i) for i in range(len(chunks))]
                metadatas = [
                    {
                        "document_title": title or url,
                        "document_link": url,
                        "chunk_index": i,
                        "last_updated": last_updated,
                        "date_source": date_source,
                        "scraped_at": datetime.today().strftime("%Y-%m-%d"),
                        "source": "etsu_scraper_v2"
                    }
                    for i in range(len(chunks))
                ]

                # Add in batches
                for i in range(0, len(chunks), 10):
                    try:
                        collection.add(
                            documents=chunks[i:i+10],
                            ids=ids[i:i+10],
                            metadatas=metadatas[i:i+10]
                        )
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            raise e

                total_chunks += len(chunks)
                scraped_pages.append({
                    "url": url,
                    "title": title,
                    "chunks": len(chunks),
                    "words": len(text.split()),
                    "last_updated": last_updated,
                })

                pbar.update(1)
                pbar.set_postfix({"chunks": total_chunks, "queue": len(queue)})
                time.sleep(DELAY_SECONDS)

            except requests.exceptions.Timeout:
                failed_pages.append({"url": url, "reason": "timeout"})
            except Exception as e:
                failed_pages.append({"url": url, "reason": str(e)[:100]})

    # Summary
    print(f"\n✅ Done!")
    print(f"   Pages scraped:   {len(scraped_pages)}")
    print(f"   Chunks embedded: {total_chunks}")
    print(f"   Failed pages:    {len(failed_pages)}")
    print(f"   ChromaDB total:  {collection.count()}")

    with open("scraped_pages_v2.txt", "w") as f:
        f.write(f"ETSU Scraper v2 Log — {datetime.today().strftime('%Y-%m-%d')}\n")
        f.write(f"Pages: {len(scraped_pages)} | Chunks: {total_chunks}\n\n")
        for page in scraped_pages:
            f.write(f"URL:   {page['url']}\n")
            f.write(f"Title: {page['title']}\n")
            f.write(f"Date:  {page['last_updated']} | "
                    f"Chunks: {page['chunks']} | Words: {page['words']}\n")
            f.write("-" * 60 + "\n")

    if failed_pages:
        with open("failed_pages_v2.txt", "w") as f:
            for p in failed_pages:
                f.write(f"{p['url']} — {p['reason']}\n")

    print(f"\n📄 Log saved to scraped_pages_v2.txt\n")


if __name__ == "__main__":
    if not OPENAI_API_KEY:
        print("❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY=your_key")
        exit(1)
    scrape_and_embed()
