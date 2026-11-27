"""Explicit country qualifiers in supplier model labels."""

import re

# Keep this qualifier in sync with the public catalog's nonUSModelQualifier.
NON_US_MODEL_QUALIFIER = r"(?i)(\s(Canada|Mexico)|\((Canada|Mexico)\))\s*$"


def explicit_source_region(region):
    market = str(region or "").strip().upper()
    return market if re.fullmatch(r"[A-Z]{2}", market) and market not in {"NA", "EU", "ZZ"} else ""


def model_visible_in_market(item, requested_region):
    source_region = explicit_source_region(item.get("region"))
    if source_region:
        return source_region == requested_region
    return requested_region != "US" or not re.search(NON_US_MODEL_QUALIFIER, str(item.get("model", "")))
