"""Contract-level checks for the chat-first quote and procedure flow."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(ROOT / "scripts/contracts"))

from autodata_contracts import contracts  # noqa: E402
from generate import load_contract  # noqa: E402


def test_chat_answer_exposes_procedure_quote_and_progress() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    answer = contract["chat_answer"]
    assert {
        "answer_status",
        "data_state",
        "procedure",
        "quote",
        "worker_stream",
    } <= set(answer["properties"])
    assert "source_unnormalized" in contract["data_state"]
    assert hasattr(contracts, "ChatAnswer")


def test_quote_separates_required_and_recommended_labor() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    quote = contract["chat_quote"]
    assert {
        "required_hours",
        "recommended_hours",
        "total_hours",
        "overlap_hours_removed",
    } <= set(quote["properties"])
    assert hasattr(contracts, "ChatQuote")


def test_price_snapshot_has_priced_at_and_no_markup_contract() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    price = contract["price_snapshot"]
    assert {
        "amount",
        "currency",
        "priced_at",
        "freshness",
        "refresh_status",
    } <= set(price["properties"])
    assert price["properties"]["markup_applied"] == {"type": "boolean", "const": False}
    assert hasattr(contracts, "PriceSnapshot")


def test_chat_event_subjects_are_versioned() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    expected = {
        "chat.answer.updated",
        "chat.vehicle.options",
        "chat.worker.progress",
        "chat.price.refresh.requested",
        "chat.procedure.published",
        "chat.visual.published",
    }
    assert expected <= set(contract["event_subjects"])
    assert expected <= set(contracts.EVENT_SUBJECTS)

