"""Run one bounded PostgreSQL publication outbox relay batch."""

from __future__ import annotations

import asyncio
import json
import os
import time

from autodata_enrichment.outbox import relay_pending_events


def main() -> None:
    while True:
        result = asyncio.run(
            relay_pending_events(
                limit=int(os.getenv("AUTODATA_OUTBOX_BATCH_SIZE", "50")),
                max_attempts=int(os.getenv("AUTODATA_OUTBOX_MAX_ATTEMPTS", "3")),
            )
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        if os.getenv("AUTODATA_OUTBOX_ONCE") == "1":
            return
        time.sleep(float(os.getenv("AUTODATA_OUTBOX_POLL_SECONDS", "5")))


if __name__ == "__main__":
    main()
