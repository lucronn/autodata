"""Run one bounded PostgreSQL publication outbox relay batch."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/enrichment-python/src"))
for venv_site in (ROOT / "workers").glob("*/.venv/lib/python*/site-packages"):
    if str(venv_site) not in sys.path:
        sys.path.append(str(venv_site))

from autodata_enrichment.outbox import relay_pending_events  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        default=(os.getenv("AUTODATA_OUTBOX_ONCE") == "1"),
        help="Run relay once and exit",
    )
    parser.add_argument(
        "--limit",
        "--batch-size",
        dest="limit",
        type=int,
        default=int(os.getenv("AUTODATA_OUTBOX_BATCH_SIZE", "50")),
        help="Maximum outbox events to relay in one batch",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=int(os.getenv("AUTODATA_OUTBOX_MAX_ATTEMPTS", "3")),
        help="Maximum delivery attempts before marking dead letter",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("AUTODATA_OUTBOX_POLL_SECONDS", "5")),
        help="Polling interval in seconds between batches",
    )
    args = parser.parse_args(argv)

    while True:
        result = asyncio.run(
            relay_pending_events(
                limit=args.limit,
                max_attempts=args.max_attempts,
            )
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
