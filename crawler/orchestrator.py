import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetcher import load_sites, extract_links
from parser import is_probable_article, parse_article


# ---------------------------
# Process each site in parallel
# ---------------------------
def process_site(site_name, info, max_articles):
    base_url = info["base_url"]
    pattern = info["pattern"]

    print(f"\n🌐 Crawling {site_name}: {base_url}")

    # STEP 1 – Extract links from the homepage
    all_links = extract_links(base_url)
    print(f"Found {len(all_links)} links on {site_name} page.")

    # STEP 2 – Filter probable articles
    article_links = [u for u in all_links if is_probable_article(u, pattern)]
    article_links = article_links[:max_articles]  # limit
    print(f"Identified {len(article_links)} probable article URLs on {site_name}.")

    if not article_links:
        print(f"No valid article links found for {site_name}.")
        return []

    # STEP 3 – ThreadPool for parsing articles of this site
    print(f"🧵 Launching threads for {site_name} articles...")

    results = []   # store parsed articles

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(parse_article, url) for url in article_links]

        for future in as_completed(futures):
            data = future.result()
            if data:
                results.append(data)

    return results     # return parsed articles for this site


# ---------------------------
# Master orchestrator
# ---------------------------
def run_crawler(sites_json="../data/news_sites.json", max_articles_per_site=5):
    sites = load_sites(sites_json)

    all_results = []   # ← global results storage

    # One thread per site
    print("\n🚀 Launching site-level threads...")

    with ThreadPoolExecutor(max_workers=len(sites)) as executor:
        futures = [
            executor.submit(process_site, site_name, info, max_articles_per_site)
            for site_name, info in sites.items()
        ]

        # Collect all site results
        for f in as_completed(futures):
            site_results = f.result()
            if site_results:
                all_results.extend(site_results)

    # ---------------------------
    # SAVE RESULTS INTO JSON FILE
    # ---------------------------
    with open("../frontend/results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)

    print(f"\n💾 Saved {len(all_results)} articles into ../data/results.json")


if __name__ == "__main__":
    run_crawler()
