"""Read the authored maintenance schedule from a retained Banktwo body."""
import json


SCHEDULES = ("Normal Service", "Severe Service")


def banktwo_service_schedule(payload: bytes) -> str | None:
    try:
        envelope = json.loads(payload)
    except (ValueError, RecursionError):
        return None
    if not isinstance(envelope, dict):
        return None
    embedded = envelope.get("_embedded")
    ancestors = embedded.get("ancestors") if isinstance(embedded, dict) else None
    if not isinstance(ancestors, list) or len(ancestors) < 3:
        return None
    branch = ancestors[-3:]
    if not all(isinstance(node, dict) for node in branch):
        return None
    context = [(node.get("type"), node.get("title")) for node in branch]
    kind, label = context[-1]
    if (context[:2] == [("Component", "Maintenance"), ("InformationType", "Service Intervals")]
            and kind == "InformationType" and label in SCHEDULES):
        return label
    return None
