from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import json
import threading
from datetime import datetime

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CrawlerRequest(BaseModel):
    mode: str
    threadCount: int
    articlesPerSite: int


# Store current crawler status
crawler_status = {
    "running": False,
    "progress": 0,
    "current_site": "",
    "estimated_time": 0,
    "start_time": None,
    "message": ""
}


@app.get("/")
async def root():
    return {"message": "News Crawler API is running"}


@app.get("/status")
async def get_status():
    """Get current crawler status"""
    return crawler_status


@app.post("/start-crawler")
async def start_crawler(request: CrawlerRequest):
    """Start the crawler with specified parameters"""

    if crawler_status["running"]:
        raise HTTPException(status_code=400, detail="Crawler is already running")

    # Update status
    crawler_status["running"] = True
    crawler_status["progress"] = 0
    crawler_status["start_time"] = datetime.now().isoformat()
    crawler_status["message"] = "Starting crawler..."

    # Estimate time based on mode and articles
    sites_count = 5
    base_time = request.articlesPerSite * sites_count * 2  # ~2 seconds per article

    if request.mode == "sequential":
        crawler_status["estimated_time"] = base_time
    elif request.mode == "parallel":
        # For parallel mode: run sequential + parallel, so roughly 2x base time divided by threadCount
        crawler_status["estimated_time"] = (base_time + base_time / request.threadCount)
    else:  # comparison
        crawler_status["estimated_time"] = base_time * 7  # All modes

    # Build command
    mode_map = {
        "sequential": "sequential",
        "parallel": "threaded",
        "comparison": "comparison"
    }

    python_mode = mode_map.get(request.mode, "comparison")

    # Get paths based on your structure
    endpoints_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(endpoints_dir)
    crawler_dir = os.path.join(project_root, "crawler")

    print(f"\n{'=' * 70}")
    print(f"[DEBUG] Endpoints directory: {endpoints_dir}")
    print(f"[DEBUG] Project root: {project_root}")
    print(f"[DEBUG] Crawler directory: {crawler_dir}")
    print(f"[DEBUG] Mode: {python_mode}")
    print(f"[DEBUG] Articles: {request.articlesPerSite}")
    if request.mode == "parallel":
        print(f"[DEBUG] Threads: {request.threadCount}")
    print(f"{'=' * 70}\n")

    cmd = [
        "python",
        "orchestrator.py",
        python_mode,
        str(request.articlesPerSite)
    ]

    # For parallel mode, add thread count as third argument
    if request.mode == "parallel":
        cmd.append(str(request.threadCount))

    # Run crawler in background thread
    def run_crawler_sync():
        try:
            crawler_status["message"] = "Running crawler..."

            print(f"[*] Executing command: {' '.join(cmd)}")
            print(f"[*] Working directory: {crawler_dir}")

            # Run the subprocess from crawler directory
            process = subprocess.Popen(
                cmd,
                cwd=crawler_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for completion and capture output
            stdout, stderr = process.communicate()

            # Print output for debugging
            print(f"\n{'=' * 70}")
            print("[CRAWLER STDOUT]")
            print(stdout)
            if stderr:
                print("\n[CRAWLER STDERR]")
                print(stderr)
            print(f"{'=' * 70}\n")

            # Update status
            if process.returncode == 0:
                crawler_status["running"] = False
                crawler_status["progress"] = 100
                crawler_status["message"] = "Completed successfully"
                print("[+] Crawler completed successfully")
            else:
                crawler_status["running"] = False
                crawler_status["progress"] = 0
                crawler_status["message"] = f"Error: {stderr[:200]}"
                print(f"[-] Crawler failed with return code {process.returncode}")

        except Exception as e:
            crawler_status["running"] = False
            crawler_status["progress"] = 0
            crawler_status["message"] = f"Exception: {str(e)}"
            print(f"[-] Exception in crawler: {e}")
            import traceback
            traceback.print_exc()

    # Start in background thread
    thread = threading.Thread(target=run_crawler_sync, daemon=True)
    thread.start()

    return {
        "message": "Crawler started",
        "mode": request.mode,
        "estimated_time": crawler_status["estimated_time"],
        "command": " '.join(cmd)",
        "working_dir": crawler_dir
    }


if __name__ == "__main__":
    import uvicorn

    # Print startup info
    print("\n" + "=" * 70)
    print("NEWS CRAWLER API SERVER")
    print("=" * 70)
    print(f"Current directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")

    endpoints_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(endpoints_dir)

    print(f"Project root: {project_root}")
    print(f"Crawler directory: {os.path.join(project_root, 'crawler')}")
    print(f"Frontend directory: {os.path.join(project_root, 'frontend')}")
    print(f"Data directory: {os.path.join(project_root, 'data')}")
    print("=" * 70 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)