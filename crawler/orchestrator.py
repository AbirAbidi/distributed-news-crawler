import json
import time
import socket
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import threading
from datetime import datetime

from fetcher import load_sites, extract_links
from parser import is_probable_article, parse_article


class CrawlerMetrics:
    """Track performance metrics for comparison"""

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


# ---------------------------
# SOCKET SERVER for Real-time Updates
# ---------------------------
class CrawlerSocketServer:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.clients = []
        self.server = None

    def start(self):
        """Start socket server in separate thread"""
        thread = threading.Thread(target=self._run_server, daemon=True)
        thread.start()

    def _run_server(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(5)
            print(f"🔌 Socket server listening on {self.host}:{self.port}")

            while True:
                try:
                    client, addr = self.server.accept()
                    self.clients.append(client)
                    print(f"✅ Client connected: {addr}")
                except Exception as e:
                    print(f"Socket error: {e}")
                    break
        except Exception as e:
            print(f"⚠️  Could not start socket server: {e}")

    def broadcast(self, message):
        """Send update to all connected clients"""
        try:
            data = json.dumps(message).encode('utf-8')
            for client in self.clients[:]:
                try:
                    client.send(data + b'\n')
                except:
                    self.clients.remove(client)
        except:
            pass


# Global socket server instance
socket_server = CrawlerSocketServer()


# ---------------------------
# Process each site with progress tracking
# ---------------------------
def process_site_with_tracking(site_name, info, max_articles, mode="threaded", num_threads=5):
    """Process a single site and track progress"""
    base_url = info["base_url"]
    pattern = info["pattern"]

    print(f"\n🌐 Crawling {site_name}: {base_url}")
    socket_server.broadcast({
        'type': 'site_start',
        'site': site_name,
        'mode': mode
    })

    # STEP 1 – Extract links from the homepage
    all_links = extract_links(base_url)
    print(f"   Found {len(all_links)} total links on {site_name}")

    # STEP 2 – Filter probable articles
    article_links = [u for u in all_links if is_probable_article(u, pattern)]
    article_links = article_links[:max_articles]
    print(f"   Identified {len(article_links)} probable article URLs")

    if not article_links:
        print(f"   ⚠️  No valid article links found for {site_name}")
        socket_server.broadcast({
            'type': 'site_complete',
            'site': site_name,
            'articles': 0
        })
        return []

    # STEP 3 – Parse articles
    print(f"   🧵 Parsing {len(article_links)} articles from {site_name}...")
    results = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(parse_article, url): url for url in article_links}

        for i, future in enumerate(as_completed(futures)):
            url = futures[future]
            try:
                data = future.result()
                if data:
                    data['site'] = site_name  # Add site name to article data
                    data['crawled_at'] = datetime.now().isoformat()
                    results.append(data)
                    print(f"   ✅ [{i + 1}/{len(article_links)}] Parsed: {data['title'][:50]}...")
                else:
                    print(f"   ❌ [{i + 1}/{len(article_links)}] Failed: {url}")
            except Exception as e:
                print(f"   ❌ [{i + 1}/{len(article_links)}] Error parsing {url}: {e}")

            # Send progress update
            socket_server.broadcast({
                'type': 'article_parsed',
                'site': site_name,
                'progress': (i + 1) / len(article_links) * 100,
                'total': len(results)
            })

    print(f"   ✅ Completed {site_name}: {len(results)}/{len(article_links)} articles successfully parsed")
    socket_server.broadcast({
        'type': 'site_complete',
        'site': site_name,
        'articles': len(results)
    })

    return results


# ---------------------------
# SEQUENTIAL CRAWLING (Baseline)
# ---------------------------
def sequential_crawl(sites, max_articles):
    """Traditional sequential approach - one site and article at a time"""
    print("\n" + "=" * 70)
    print("🐌 SEQUENTIAL CRAWLING (Baseline)")
    print("=" * 70)
    start_time = time.time()
    all_results = []

    socket_server.broadcast({
        'type': 'crawl_start',
        'mode': 'sequential',
        'sites': len(sites)
    })

    for site_name, info in sites.items():
        site_results = process_site_with_tracking(site_name, info, max_articles, "sequential", num_threads=1)
        all_results.extend(site_results)

    elapsed = time.time() - start_time
    print(f"\n⏱️  Sequential completed in {elapsed:.2f}s")
    print(f"📊 Total articles collected: {len(all_results)}")

    socket_server.broadcast({
        'type': 'crawl_complete',
        'mode': 'sequential',
        'time': elapsed,
        'articles': len(all_results)
    })

    return all_results, elapsed


# ---------------------------
# MULTI-THREADING (Current approach)
# ---------------------------
def threaded_crawl(sites, max_articles, num_threads=5):
    """Multi-threading approach with configurable thread pool"""
    print("\n" + "=" * 70)
    print(f"🧵 MULTI-THREADED CRAWLING ({num_threads} threads per site)")
    print("=" * 70)
    start_time = time.time()
    all_results = []

    socket_server.broadcast({
        'type': 'crawl_start',
        'mode': f'threaded_{num_threads}',
        'sites': len(sites),
        'threads': num_threads
    })

    # Process sites in parallel
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
                print(f"❌ Error processing site {site_name}: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Multi-threaded ({num_threads}) completed in {elapsed:.2f}s")
    print(f"📊 Total articles collected: {len(all_results)}")

    socket_server.broadcast({
        'type': 'crawl_complete',
        'mode': f'threaded_{num_threads}',
        'time': elapsed,
        'articles': len(all_results)
    })

    return all_results, elapsed


# ---------------------------
# MULTI-PROCESSING (CPU-intensive tasks)
# ---------------------------
def multiprocess_crawl(sites, max_articles, num_processes=None):
    """Multi-processing for CPU-bound parsing operations"""
    if num_processes is None:
        num_processes = min(cpu_count(), len(sites))

    print("\n" + "=" * 70)
    print(f"⚡ MULTI-PROCESSING CRAWLING ({num_processes} processes)")
    print("=" * 70)
    start_time = time.time()
    all_results = []

    socket_server.broadcast({
        'type': 'crawl_start',
        'mode': 'multiprocess',
        'sites': len(sites),
        'processes': num_processes
    })

    # Collect all URLs first
    all_urls = []
    for site_name, info in sites.items():
        base_url = info["base_url"]
        pattern = info["pattern"]
        print(f"\n🌐 Scanning {site_name}...")
        all_links = extract_links(base_url)
        article_links = [u for u in all_links if is_probable_article(u, pattern)][:max_articles]
        print(f"   Found {len(article_links)} article URLs")
        all_urls.extend([(url, site_name) for url in article_links])

    print(f"\n🔄 Processing {len(all_urls)} total URLs across {num_processes} processes...")

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
                if completed % 5 == 0:
                    print(f"   Progress: {completed}/{len(all_urls)} articles processed")
            except Exception as e:
                print(f"   ❌ Error parsing {url}: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Multi-processing completed in {elapsed:.2f}s")
    print(f"📊 Total articles collected: {len(all_results)}")

    socket_server.broadcast({
        'type': 'crawl_complete',
        'mode': 'multiprocess',
        'time': elapsed,
        'articles': len(all_results)
    })

    return all_results, elapsed


# ---------------------------
# ASYNCIO (I/O-bound operations)
# ---------------------------
async def async_parse_article(url, site_name):
    """Async version of article parsing"""
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, parse_article, url)
    if data:
        data['site'] = site_name
        data['crawled_at'] = datetime.now().isoformat()
    return data


async def async_crawl(sites, max_articles):
    """Asyncio approach for I/O-bound network requests"""
    print("\n" + "=" * 70)
    print("🔄 ASYNCIO CRAWLING")
    print("=" * 70)
    start_time = time.time()

    socket_server.broadcast({
        'type': 'crawl_start',
        'mode': 'asyncio',
        'sites': len(sites)
    })

    tasks = []
    for site_name, info in sites.items():
        base_url = info["base_url"]
        pattern = info["pattern"]

        print(f"\n🌐 Scanning {site_name}...")
        all_links = extract_links(base_url)
        article_links = [u for u in all_links if is_probable_article(u, pattern)][:max_articles]
        print(f"   Found {len(article_links)} article URLs")

        for url in article_links:
            tasks.append(async_parse_article(url, site_name))

    print(f"\n🔄 Processing {len(tasks)} articles asynchronously...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in results if r and not isinstance(r, Exception)]

    elapsed = time.time() - start_time
    print(f"\n⏱️  Asyncio completed in {elapsed:.2f}s")
    print(f"📊 Total articles collected: {len(results)}")

    socket_server.broadcast({
        'type': 'crawl_complete',
        'mode': 'asyncio',
        'time': elapsed,
        'articles': len(results)
    })

    return results, elapsed


# ---------------------------
# HYBRID APPROACH (Combining techniques)
# ---------------------------
def hybrid_crawl(sites, max_articles, num_processes=2, num_threads=5):
    """Hybrid: multiprocessing for sites, threading for articles within each site"""
    print("\n" + "=" * 70)
    print(f"🚀 HYBRID CRAWLING ({num_processes} processes × {num_threads} threads)")
    print("=" * 70)
    start_time = time.time()

    socket_server.broadcast({
        'type': 'crawl_start',
        'mode': 'hybrid',
        'sites': len(sites),
        'processes': num_processes,
        'threads': num_threads
    })

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
                print(f"❌ Error in hybrid processing: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Hybrid completed in {elapsed:.2f}s")
    print(f"📊 Total articles collected: {len(all_results)}")

    socket_server.broadcast({
        'type': 'crawl_complete',
        'mode': 'hybrid',
        'time': elapsed,
        'articles': len(all_results)
    })

    return all_results, elapsed


# ---------------------------
# COMPARISON RUNNER
# ---------------------------
def run_comparison(sites_json="../data/news_sites.json", max_articles=5):
    """Run all approaches and compare performance"""
    sites = load_sites(sites_json)

    # Start socket server
    socket_server.start()
    time.sleep(0.5)  # Give server time to start

    print("\n" + "=" * 70)
    print("🏁 CRAWLING PERFORMANCE COMPARISON")
    print("=" * 70)
    print(f"📰 News sources: {', '.join(sites.keys())}")
    print(f"📊 Articles per site: {max_articles}")
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
    final_results = seq_results  # Use sequential results as final output

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
    print("📊 PERFORMANCE COMPARISON RESULTS")
    print("=" * 70)
    print(f"{'Method':<25} {'Time (s)':<12} {'Articles':<10} {'Speedup':<10}")
    print("-" * 70)
    for method, data in results_comparison.items():
        print(f"{method:<25} {data['time']:>10.2f}s  {data['articles']:>8}  {data['speedup']:>8.2f}x")
    print("=" * 70)

    # Find best method
    best_method = min(results_comparison.items(), key=lambda x: x[1]['time'])
    print(f"\n🏆 WINNER: {best_method[0].upper()}")
    print(f"   Time: {best_method[1]['time']:.2f}s")
    print(f"   Speedup: {best_method[1]['speedup']:.2f}x over sequential")

    # Save results
    print(f"\n💾 Saving results...")
    with open("../frontend/results.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=4, ensure_ascii=False)
    print(f"   ✅ Articles saved to ../data/results.json")

    with open("../frontend/performance_metrics.json", "w", encoding="utf-8") as f:
        json.dump(results_comparison, f, indent=4)
    print(f"   ✅ Metrics saved to ../data/performance_metrics.json")

    print("\n✨ All done! Open frontend/index.html to view results in dashboard.")

    return results_comparison


# ---------------------------
# MAIN ENTRY POINT
# ---------------------------
if __name__ == "__main__":
    import sys

    # Start socket server for all modes
    socket_server.start()
    time.sleep(0.5)

    mode = sys.argv[1] if len(sys.argv) > 1 else "comparison"
    max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    sites = load_sites("../data/news_sites.json")

    if mode == "sequential":
        results, _ = sequential_crawl(sites, max_articles)
        with open("../frontend/results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    elif mode == "threaded":
        num_threads = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        results, _ = threaded_crawl(sites, max_articles, num_threads)
        with open("../frontend/results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    elif mode == "multiprocess":
        results, _ = multiprocess_crawl(sites, max_articles)
        with open("../frontend/results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    elif mode == "async":
        results, _ = asyncio.run(async_crawl(sites, max_articles))
        with open("../frontend/results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    elif mode == "hybrid":
        results, _ = hybrid_crawl(sites, max_articles)
        with open("../frontend/results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

    else:
        run_comparison("../data/news_sites.json", max_articles)