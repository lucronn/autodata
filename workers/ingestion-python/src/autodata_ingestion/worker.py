"""Deterministic process boundary for the fast-lane worker."""

from __future__ import annotations

import json
import os
import time


def run_once() -> dict[str, str]:
    """Return the idle worker heartbeat until ingestion handlers are implemented."""

    return {"worker": "ingestion", "lane": "fast", "status": "idle"}


def main() -> None:
    interval = float(os.getenv("AUTODATA_WORKER_HEARTBEAT_SECONDS", "30"))
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        print(json.dumps(run_once(), sort_keys=True))
        return
    while True:
        print(json.dumps(run_once(), sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
