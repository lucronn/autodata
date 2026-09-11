"""Contract-level checks for the chat-first quote and procedure flow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import get_type_hints


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
    assert "stale" in contract["data_state"]
    assert hasattr(contracts, "ChatAnswer")
    assert "stale" in contracts.DATA_STATE_VALUES


def test_quote_separates_required_and_recommended_labor() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    quote = contract["chat_quote"]
    assert {
        "required_hours",
        "recommended_hours",
        "required_operations",
        "recommended_operations",
        "total_hours",
        "overlap_hours_removed",
    } <= set(quote["properties"])
    assert hasattr(contracts, "ChatQuote")
    assert {"required_operations", "recommended_operations"} <= set(
        contracts.ChatQuote.__annotations__
    )


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


def test_visual_artifact_requires_source_and_processor_metadata() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    visual = contract["visual_artifact"]
    assert {
        "artifact_id",
        "source_artifact_id",
        "source_artifact_key",
        "derived_artifact_key",
        "processor",
        "processor_version",
        "review_state",
    } <= set(visual["required"])
    assert visual["properties"]["published_at"] == {
        "type": "string",
        "nullable": True,
        "optional": True,
    }
    assert "source_artifact_id" in contracts.VisualArtifact.__annotations__
    visual_hints = get_type_hints(contracts.VisualArtifact)
    assert visual_hints["processor"] is str
    assert visual_hints["processor_version"] is str


def test_worker_progress_event_contains_the_complete_event_envelope() -> None:
    contract = load_contract(ROOT / "packages/contracts/contract.json")
    event = contract["worker_progress_event"]
    assert {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer",
        "request_id",
        "projection_id",
        "revision_id",
        "correlation_id",
        "idempotency_key",
        "payload",
    } <= set(event["required"])
    assert {
        "producer",
        "request_id",
        "projection_id",
        "revision_id",
        "correlation_id",
    } <= set(contracts.WorkerProgressEvent.__annotations__)


def test_python_package_exports_chat_contract_bindings() -> None:
    from autodata_contracts import (  # noqa: PLC0415
        ChatAnswer,
        ChatQuery,
        ChatQuote,
        ChatSelection,
        DATA_STATE_VALUES,
        PriceSnapshot,
        ProcedureStep,
        VisualArtifact,
        WorkerProgressEvent,
    )

    assert ChatAnswer is contracts.ChatAnswer
    assert ChatQuery is contracts.ChatQuery
    assert ChatQuote is contracts.ChatQuote
    assert ChatSelection is contracts.ChatSelection
    assert PriceSnapshot is contracts.PriceSnapshot
    assert ProcedureStep is contracts.ProcedureStep
    assert VisualArtifact is contracts.VisualArtifact
    assert WorkerProgressEvent is contracts.WorkerProgressEvent
    assert DATA_STATE_VALUES == tuple(load_contract(ROOT / "packages/contracts/contract.json")["data_state"])


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
