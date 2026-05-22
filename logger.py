import logging
import json
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


API_LOG_FILE = os.path.join(LOG_DIR, "api_calls.jsonl")


def log_api_call(
    page: str,
    query_summary: str,
    rag_docs_count: int,
    duration_sec: float,
    input_tokens: int,
    output_tokens: int,
    error: str | None = None,
):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "page": page,
        "query_summary": query_summary[:200],
        "rag_docs_count": rag_docs_count,
        "duration_sec": round(duration_sec, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "error": error,
    }
    with open(API_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_api_logs(limit: int = 200) -> list[dict]:
    if not os.path.exists(API_LOG_FILE):
        return []
    entries = []
    with open(API_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


def read_error_logs(limit: int = 100) -> list[str]:
    log_file = os.path.join(LOG_DIR, "app.log")
    if not os.path.exists(log_file):
        return []
    errors = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if "[ERROR]" in line or "[CRITICAL]" in line:
                errors.append(line.rstrip())
    return errors[-limit:]
