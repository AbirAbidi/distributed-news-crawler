import newspaper


def is_probable_article(url, pattern):
    return pattern in url


def parse_article(url):
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