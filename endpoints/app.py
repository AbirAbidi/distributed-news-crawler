from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CrawlRequest(BaseModel):
    mode: str
    threadCount: int | None = None
    articlesPerSite: int

def estimate_wait_time(mode: str, articles_per_site: int, threads: int | None = None) -> str:
    """
    Return approximate waiting time as a string.
    Simple heuristic:
    - sequential: 5s per article
    - parallel: 2s per article divided by number of threads
    - comparison: add 20% overhead
    """
    if mode == "sequential":
        approx_seconds = articles_per_site * 5
    elif mode == "parallel":
        thread_count = threads if threads and threads > 0 else 1
        approx_seconds = (articles_per_site * 5) / thread_count
    else:  # comparison
        approx_seconds = articles_per_site * 5 * 1.2

    if approx_seconds < 60:
        return f"{int(approx_seconds)}s"
    else:
        minutes = int(approx_seconds // 60)
        seconds = int(approx_seconds % 60)
        return f"{minutes}m {seconds}s"

@app.post("/start-crawler")
def start_crawler(req: CrawlRequest):


    if req.mode == "sequential":
        command = ["python", "../crawler/orchestrator.py", "sequential", str(req.articlesPerSite)]
    elif req.mode == "parallel":
        command = ["python", "../crawler/orchestrator.py", "threaded", str(req.articlesPerSite), str(req.threadCount or 1)]
    else:
        command = ["python", "../crawler/orchestrator.py", "comparison", str(req.articlesPerSite)]

    # Estimate waiting time
    approx_time = estimate_wait_time(req.mode, req.articlesPerSite, req.threadCount)

    # Run the crawler
    result = subprocess.run(command, capture_output=True, text=True)

    # Filter out separator lines (like ========)
    stdout_clean = "\n".join(line for line in result.stdout.splitlines() if not line.startswith("="))

    return {
        "executed_command": " ".join(command),
        "stdout": stdout_clean.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
        "approx_wait_time": approx_time
    }
