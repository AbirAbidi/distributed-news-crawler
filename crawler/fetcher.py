import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


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
    parsed_base = urlparse(url).netloc #traja3 base url https://www.bbc.com/news, netloc = "www.bbc.com"

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if any(ext in href.lower() for ext in IMAGE_EXTENSIONS):
            continue

        full = urljoin(url, href)

        if parsed_base in urlparse(full).netloc:
            links.add(full)

    return list(links)

