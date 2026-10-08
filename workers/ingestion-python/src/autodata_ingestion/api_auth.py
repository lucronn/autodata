"""Build server-only credentials for the Bankone and Banktwo clients."""

from __future__ import annotations

import os
import re

_KEY_PATTERNS = {
    "bankone": re.compile(r"^adk_bankone_[A-Za-z0-9_-]{43}$"),
    "banktwo": re.compile(r"^adk_banktwo_[A-Za-z0-9_-]{43}$"),
}


def api_key_headers(service: str) -> dict[str, str]:
    """Return the bearer header for a configured service key, or no header."""

    if service not in _KEY_PATTERNS:
        raise ValueError("unsupported API key service")
    value = os.getenv(f"AUTODATA_{service.upper()}_API_KEY", "").strip()
    if not value:
        return {}
    if not _KEY_PATTERNS[service].fullmatch(value):
        raise ValueError(f"AUTODATA_{service.upper()}_API_KEY has an invalid format")
    return {"Authorization": f"Bearer {value}"}
