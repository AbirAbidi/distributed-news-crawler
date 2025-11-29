import newspaper


def is_probable_article(url, pattern):
    """Check if a URL matches the site's article pattern."""
    return pattern in url
def parse_article(url):
    """Download + parse one article with Newspaper3k."""
    print(f"\n Parsing: {url}")
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