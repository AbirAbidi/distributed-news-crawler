import json
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from datetime import datetime
import os

from fetcher import load_sites, extract_links
from parser import is_probable_article, parse_article


class CrawlerMetrics:
    #track performance metrics for comparison

    def __init__(self):
        self.sequential_time = 0
        self.parallel_time = 0
        self.multiprocess_time = 0
        self.async_time = 0
        self.articles_fetched = 0
        self.failed_fetches = 0
        self.thread_usage = []
        self.start_time = None
        self.end_time = None


CRAWLER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CRAWLER_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")



# ---------------------------
# Process each site with progress tracking
def process_site_with_tracking(site_name, info, max_articles, mode="threaded", num_threads=5):
    """Process a single site and track progress"""
    base_url = info["base_url"]
    pattern = info["pattern"]

    print(f"\n[*] Crawling {site_name}: {base_url}")

    # STEP 1 – Extract links from the homepage
    all_links = extract_links(base_url)
    print(f"    Found {len(all_links)} total links on {site_name}")

    # STEP 2 – Filter probable articles
    article_links = [u for u in all_links if is_probable_article(u, pattern)]
    article_links = article_links[:max_articles]

    if not article_links:
        print(f"    [!] No valid article links found for {site_name}")
        return []

    # STEP 3 – Parse articles
    #3leh {len(article_links)} w mouch juste max_articles 5atir yajmou ykounou probable_article < max_articles
    print(f"    [>] Parsing {len(article_links)} articles from {site_name}...")
    results = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(parse_article, url): url for url in article_links}

        for i, future in enumerate(as_completed(futures)): #ta3ti les futures ili wfew  w i = num article
            url = futures[future]
            try:
                data = future.result()
                if data:
                    data['site'] = site_name
                    data['crawled_at'] = datetime.now().isoformat()
                    results.append(data)
                    print(f"    [+] [{i + 1}/{len(article_links)}] Parsed: {data['title'][:50]}...")
                else:
                    print(f"    [-] [{i + 1}/{len(article_links)}] Failed: {url}")
            except Exception as e:
                print(f"    [-] [{i + 1}/{len(article_links)}] Error parsing {url}: {e}")

    print(f"    [+] Completed {site_name}: {len(results)}/{len(article_links)} articles successfully parsed")

    return results
# ---------------------------
def sequential_crawl(sites, max_articles):
    print("\n" + "=" * 70)
    print("SEQUENTIAL CRAWLING")
    start_time = time.time()
    all_results = []

    for site_name, info in sites.items():
        site_results = process_site_with_tracking(site_name, info, max_articles, "sequential", num_threads=1)
        all_results.extend(site_results)

    elapsed = time.time() - start_time
    print(f"\n[*] Sequential completed in {elapsed:.2f}s")

    return all_results, elapsed
# ---------------------------
# MULTI-THREADING
def threaded_crawl(sites, max_articles, num_threads=5):
    print("\n" + "=" * 70)
    print(f"MULTI-THREADED CRAWLING ({num_threads} threads per site)")
    start_time = time.time()
    all_results = []

    with ThreadPoolExecutor(max_workers=len(sites)) as site_executor:
        site_futures = {
            site_executor.submit(process_site_with_tracking, site_name, info, max_articles, f"threaded_{num_threads}",
                                 num_threads): site_name
            for site_name, info in sites.items()
        }

        for future in as_completed(site_futures):
            site_name = site_futures[future]
            try:
                site_results = future.result()
                all_results.extend(site_results)
            except Exception as e:
                print(f"[-] Error processing site {site_name}: {e}")

    elapsed = time.time() - start_time
    print(f"\n[*] Multi-threaded ({num_threads}) completed in {elapsed:.2f}s")
    print(f"[*] Total articles collected: {len(all_results)}")

    return all_results, elapsed
# ---------------------------
# MULTI-PROCESSING
def multiprocess_crawl(sites, max_articles, num_processes=None):
    if num_processes is None:
        num_processes = min(cpu_count(), len(sites))

    print("\n" + "=" * 70)
    print(f"MULTI-PROCESSING CRAWLING ({num_processes} processes)")
    start_time = time.time()
    all_results = []

    all_urls = []
    for site_name, info in sites.items():
        base_url = info["base_url"]
        pattern = info["pattern"]
        print(f"\n[*] Scanning {site_name}...")
        all_links = extract_links(base_url)
        article_links = [u for u in all_links if is_probable_article(u, pattern)][:max_articles]
        print(f"    Found {len(article_links)} article URLs")
        all_urls.extend([(url, site_name) for url in article_links])

    print(f"\n[>] Processing {len(all_urls)} total URLs across {num_processes} processes...")

    # Parse articles in parallel processes
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        futures = {executor.submit(parse_article, url): (url, site) for url, site in all_urls}

        completed = 0
        for future in as_completed(futures):
            url, site_name = futures[future]
            try:
                data = future.result()
                if data:
                    data['site'] = site_name
                    data['crawled_at'] = datetime.now().isoformat()
                    all_results.append(data)
                completed += 1
                if completed % 5 == 0: #maj kol 5 urls
                    print(f"    Progress: {completed}/{len(all_urls)} articles processed")
            except Exception as e:
                print(f"    [-] Error parsing {url}: {e}")

    elapsed = time.time() - start_time
    print(f"\n[*] Multi-processing completed in {elapsed:.2f}s")
    print(f"[*] Total articles collected: {len(all_results)}")

    return all_results, elapsed
# ---------------------------
# ASYNCIO
async def async_parse_article(url, site_name):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, parse_article, url)
    if data:
        data['site'] = site_name
        data['crawled_at'] = datetime.now().isoformat()
    return data
async def async_crawl(sites, max_articles):
    print("\n" + "=" * 70)
    print("ASYNCIO CRAWLING")
    start_time = time.time()

    tasks = []
    for site_name, info in sites.items():
        base_url = info["base_url"]
        pattern = info["pattern"]

        print(f"\n[*] Scanning {site_name}...")
        all_links = extract_links(base_url)
        article_links = [u for u in all_links if is_probable_article(u, pattern)][:max_articles]
        print(f"    Found {len(article_links)} article URLs")

        for url in article_links:
            tasks.append(async_parse_article(url, site_name))

    print(f"\n[>] Processing {len(tasks)} articles asynchronously...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in results if r and not isinstance(r, Exception)]

    elapsed = time.time() - start_time
    print(f"\n[*] Asyncio completed in {elapsed:.2f}s")
    print(f"[*] Total articles collected: {len(results)}")

    return results, elapsed
# ---------------------------
# HYBRID APPROACH (Combining technique)
def hybrid_crawl(sites, max_articles, num_processes=2, num_threads=5):
    """Hybrid: multiprocessing for sites, threading for articles within each site"""
    print("\n" + "=" * 70)
    print(f"HYBRID CRAWLING ({num_processes} processes x {num_threads} threads)")
    start_time = time.time()

    def process_site(site_data):
        site_name, info = site_data
        return process_site_with_tracking(site_name, info, max_articles, "hybrid", num_threads)

    all_results = []
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        futures = [executor.submit(process_site, site) for site in sites.items()]
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as e:
                print(f"[-] Error in hybrid processing: {e}")

    elapsed = time.time() - start_time
    print(f"\n[*] Hybrid completed in {elapsed:.2f}s")
    print(f"[*] Total articles collected: {len(all_results)}")

    return all_results, elapsed
# ---------------------------
# PARALLEL vs SEQUENTIAL COMPARISON
def run_parallel_vs_sequential_comparison(sites_json, max_articles, num_threads):
    sites = load_sites(sites_json)

    print("\n" + "=" * 70)
    print("PARALLEL vs SEQUENTIAL COMPARISON")

    results_comparison = {}

    # 1. Sequential
    print("\n[1/2] Running Sequential...")
    seq_results, seq_time = sequential_crawl(sites, max_articles)
    results_comparison['sequential'] = {
        'time': seq_time,
        'articles': len(seq_results),
        'speedup': 1.0
    }
    final_results = seq_results

    # 2. Threaded
    print(f"\n[2/2] Running Parallel ({num_threads} threads)...")
    parallel_results, parallel_time = threaded_crawl(sites, max_articles, num_threads)
    results_comparison[f'threaded_{num_threads}'] = {
        'time': parallel_time,
        'articles': len(parallel_results),
        'speedup': seq_time / parallel_time if parallel_time > 0 else 0
    }

    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    # Find best method
    best_method = min(results_comparison.items(), key=lambda x: x[1]['time'])

    # Save results
    results_file = os.path.join(FRONTEND_DIR, "results.json")
    metrics_file = os.path.join(FRONTEND_DIR, "performance_metrics.json")

    print(f"\n[*] Saving results...")
    try:
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=4, ensure_ascii=False)
        print(f"    [+] Articles saved to {results_file}")
    except Exception as e:
        print(f"    [-] Error saving results: {e}")

    try:
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(results_comparison, f, indent=4)
        print(f"    [+] Metrics saved to {metrics_file}")
    except Exception as e:
        print(f"    [-] Error saving metrics: {e}")

    return results_comparison
# ---------------------------
# FULL COMPARISON RUNNER (All 7 methods)
def run_comparison(sites_json, max_articles=5):
    """Run all approaches and compare performance"""
    sites = load_sites(sites_json)

    print("\n" + "=" * 70)
    print("CRAWLING PERFORMANCE COMPARISON (All 7 Methods)")
    print("=" * 70)
    print(f"[*] News sources: {', '.join(sites.keys())}")
    print(f"[*] Articles per site: {max_articles}")
    print("=" * 70)

    results_comparison = {}
    final_results = None

    # 1. Sequential
    print("\n[1/7] Running Sequential...")
    seq_results, seq_time = sequential_crawl(sites, max_articles)
    results_comparison['sequential'] = {
        'time': seq_time,
        'articles': len(seq_results),
        'speedup': 1.0
    }
    final_results = seq_results

    # 2. Multi-threading (various thread counts)
    for num_threads in [2, 4, 8]:
        print(f"\n[{list([2, 4, 8]).index(num_threads) + 2}/7] Running Multi-threaded ({num_threads} threads)...")
        thread_results, thread_time = threaded_crawl(sites, max_articles, num_threads)
        results_comparison[f'threaded_{num_threads}'] = {
            'time': thread_time,
            'articles': len(thread_results),
            'speedup': seq_time / thread_time if thread_time > 0 else 0
        }

    # 3. Multi-processing
    print(f"\n[5/7] Running Multi-processing...")
    mp_results, mp_time = multiprocess_crawl(sites, max_articles)
    results_comparison['multiprocess'] = {
        'time': mp_time,
        'articles': len(mp_results),
        'speedup': seq_time / mp_time if mp_time > 0 else 0
    }

    # 4. Asyncio
    print(f"\n[6/7] Running Asyncio...")
    async_results, async_time = asyncio.run(async_crawl(sites, max_articles))
    results_comparison['asyncio'] = {
        'time': async_time,
        'articles': len(async_results),
        'speedup': seq_time / async_time if async_time > 0 else 0
    }

    # 5. Hybrid
    print(f"\n[7/7] Running Hybrid...")
    hybrid_results, hybrid_time = hybrid_crawl(sites, max_articles)
    results_comparison['hybrid'] = {
        'time': hybrid_time,
        'articles': len(hybrid_results),
        'speedup': seq_time / hybrid_time if hybrid_time > 0 else 0
    }

    # Print results table
    print("\n" + "=" * 70)
    print("PERFORMANCE COMPARISON RESULTS")
    # Find best method
    best_method = min(results_comparison.items(), key=lambda x: x[1]['time'])

    results_file = os.path.join(FRONTEND_DIR, "results.json")
    metrics_file = os.path.join(FRONTEND_DIR, "performance_metrics.json")

    print(f"\n[*] Saving results...")
    try:
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=4, ensure_ascii=False)
        print(f"    [+] Articles saved to {results_file}")
    except Exception as e:
        print(f"    [-] Error saving results: {e}")

    try:
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(results_comparison, f, indent=4)
        print(f"    [+] Metrics saved to {metrics_file}")
    except Exception as e:
        print(f"    [-] Error saving metrics: {e}")

    return results_comparison



if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "comparison"
    max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    sites_json = os.path.join(DATA_DIR, "news_sites.json")
    sites = load_sites(sites_json)

    results_file = os.path.join(FRONTEND_DIR, "results.json")

    if mode == "sequential":
        print("\n[*] Running SEQUENTIAL ONLY...")
        results, _ = sequential_crawl(sites, max_articles)
        try:
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            print(f"[+] Results saved to {results_file}")
        except Exception as e:
            print(f"[-] Error saving results: {e}")

    elif mode == "threaded":
        num_threads = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        print(f"\n[*] Running PARALLEL vs SEQUENTIAL COMPARISON (threads={num_threads})...")
        run_parallel_vs_sequential_comparison(sites_json, max_articles, num_threads)

    elif mode == "comparison":
        print("\n[*] Running FULL COMPARISON (All 7 methods)...")
        run_comparison(sites_json, max_articles)

    else:
        print(f"[-] Unknown mode: {mode}")
