import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import newspaper

# --------------------------
# Config
# --------------------------
BASE_URL = "https://edition.cnn.com/politics"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")

# --------------------------
# Functions
# --------------------------

def extract_links(url):
    """Download a page and extract all <a> links as absolute URLs, excluding image links."""
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")

    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Skip links containing image extensions
        if any(ext in href.lower() for ext in IMAGE_EXTENSIONS):
            continue

        # Convert to absolute URL
        full = urljoin(url, href)

        # Keep only CNN URLs
        if "cnn.com" in urlparse(full).netloc:
            links.add(full)

    return list(links)


def is_probable_politics_article(url):
    """
    Filters CNN Politics articles.
    Example article URLs:
    https://edition.cnn.com/2025/11/23/politics/some-article-slug
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")

    # Must have at least: YEAR / MONTH / DAY / politics / slug
    if len(path) >= 5 and path[3] == "politics":
        try:
            # Check first 3 parts are integers (year/month/day)
            int(path[0])
            int(path[1])
            int(path[2])
            return True
        except ValueError:
            return False

    return False


def parse_article(url):
    """Download + parse one article with Newspaper3k."""
    print(f"\n🔎 Parsing: {url}")
    article = newspaper.Article(url)

    article.download()
    article.parse()

    return {
        "title": article.title,
        "text": article.text[:500] + "...",  # show only first 500 chars
        "authors": article.authors,
        "top_image": article.top_image,
        "url": url
    }


# --------------------------
# Run the crawler
# --------------------------

print(f"Fetching links from {BASE_URL}...")
all_links = extract_links(BASE_URL)
print(f"Found {len(all_links)} links on Politics page.")

# Filter to actual Politics article URLs
article_links = [u for u in all_links if is_probable_politics_article(u)]
print(f"Identified {len(article_links)} probable Politics article URLs.")

# Parse first few articles
for url in article_links[:5]:  # change number to parse more
    data = parse_article(url)
    print("\nTitle:", data["title"])
    print("Authors:", data["authors"])
    print("Top image:", data["top_image"])
    print("Text snippet:", data["text"])
    print("-"*80)
