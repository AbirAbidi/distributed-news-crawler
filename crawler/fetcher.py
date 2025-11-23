import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import newspaper


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".pdf",".mp3")


def load_sites(json_file="../data/news_sites.json"):
    with open(json_file, "r") as f:
        return json.load(f)


def extract_links(url):
    """Download a page and extract all <a> links as absolute URLs, excluding image/video/pdf links."""
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    links = set()
    parsed_base = urlparse(url).netloc

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Skip links containing non-article extensions
        if any(ext in href.lower() for ext in IMAGE_EXTENSIONS):
            continue

        # Convert to absolute URL
        full = urljoin(url, href)

        # Keep only links from the same domain
        if parsed_base in urlparse(full).netloc:
            links.add(full)

    return list(links)


def is_probable_article(url, pattern):
    """Check if a URL matches the site's article pattern."""
    return pattern in url


def parse_article(url):
    """Download + parse one article with Newspaper3k."""
    print(f"\n🔎 Parsing: {url}")
    article = newspaper.Article(url)
    try:
        article.download()
        article.parse()
    except Exception as e:
        print(f"Failed to parse {url}: {e}")
        return None

    return {
        "title": article.title,
        "text": article.text[:500] + "...",  # first 500 chars
        "authors": article.authors,
        "top_image": article.top_image,
        "url": url
    }


# --------------------------
# Main crawler
# --------------------------

def run_crawler(sites_json="../data/news_sites.json", max_articles_per_site=5):
    sites = load_sites(sites_json)

    for site_name, info in sites.items():
        base_url = info["base_url"]
        pattern = info["pattern"]
        print(f"\n🌐 Crawling {site_name}: {base_url}")

        all_links = extract_links(base_url)
        print(f"Found {len(all_links)} links on {site_name} page.")

        # Filter probable articles
        article_links = [u for u in all_links if is_probable_article(u, pattern)]
        print(f"Identified {len(article_links)} probable article URLs on {site_name}.")

        # Parse articles
        for url in article_links[:max_articles_per_site]:
            data = parse_article(url)
            if data:
                print("\nTitle:", data["title"])
                print("Authors:", data["authors"])
                print("Top image:", data["top_image"])
                print("Text snippet:", data["text"])
                print("-"*80)


if __name__ == "__main__":
    run_crawler()
