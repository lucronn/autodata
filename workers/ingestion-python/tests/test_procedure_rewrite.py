from __future__ import annotations

import sys
from copy import deepcopy

import pytest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.procedure_rewrite import (  # noqa: E402
    REWRITE_STATUS_FAILED,
    REWRITE_STATUS_REWRITTEN,
    REWRITE_STATUS_SKIPPED,
    _validate_phrase_only_rewrite,
    rewrite_procedure_article,
    rewrite_steps_for_diy,
)


BASELINE = [
    {
        "action": "Remove the oil pump.",
        "instructions": ["Discard the gasket."],
        "phase": "removal",
        "components": ["oil_pump"],
        "source_article_ids": ["a1"],
        "evidence_ids": ["e1"],
        "images": [{"image_id": "img-1", "storage_key": "procedure-images/abc"}],
    },
    {
        "action": "Install the oil pump.",
        "instructions": ["Torque bolts to 10 Nm."],
        "phase": "installation",
        "components": ["oil_pump"],
        "source_article_ids": ["a1"],
        "evidence_ids": ["e2"],
        "images": [],
    },
]


class FakeMercury:
    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, prompt):  # noqa: ARG002
        return self.payload


def test_validate_accepts_phrase_only_diffs():
    payload = {
        "steps": [
            {"index": 0, "action": "Take off the oil pump.", "instructions": ["Toss the gasket."]},
            {"index": 1, "action": "Fit the oil pump.", "instructions": ["Torque bolts to 10 Nm."]},
        ]
    }
    rewritten = _validate_phrase_only_rewrite(BASELINE, payload)
    assert rewritten[0]["action"] == "Take off the oil pump."
    assert rewritten[0]["images"][0]["image_id"] == "img-1"
    assert rewritten[0]["phase"] == "removal"
    assert rewritten[1]["source_article_ids"] == ["a1"]


def test_validate_rejects_dropped_or_reordered_steps():
    try:
        _validate_phrase_only_rewrite(
            BASELINE,
            {"steps": [{"index": 0, "action": "Only one", "instructions": ["x"]}]},
        )
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        _validate_phrase_only_rewrite(
            BASELINE,
            {
                "steps": [
                    {"index": 1, "action": "Install first", "instructions": ["a"]},
                    {"index": 0, "action": "Remove second", "instructions": ["b"]},
                ]
            },
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_rewrite_steps_for_diy_returns_rewritten_on_success(monkeypatch):
    monkeypatch.delenv("AUTODATA_PROCEDURE_DIY_REWRITE", raising=False)
    client = FakeMercury(
        {
            "steps": [
                {"index": 0, "action": "Lift off the oil pump.", "instructions": ["Discard the gasket."]},
                {"index": 1, "action": "Seat the oil pump.", "instructions": ["Torque bolts to 10 Nm."]},
            ]
        }
    )
    steps, status = rewrite_steps_for_diy(BASELINE, client=client)
    assert status == REWRITE_STATUS_REWRITTEN
    assert steps[0]["action"] == "Lift off the oil pump."
    assert steps[0]["images"][0]["storage_key"] == "procedure-images/abc"


def test_rewrite_steps_for_diy_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("AUTODATA_PROCEDURE_DIY_REWRITE", "0")
    steps, status = rewrite_steps_for_diy(BASELINE, client=FakeMercury({"steps": []}))
    assert status == REWRITE_STATUS_SKIPPED
    assert steps[0]["action"] == "Remove the oil pump."


def test_rewrite_steps_for_diy_fails_closed_on_bad_payload():
    client = FakeMercury({"steps": [{"index": 0, "action": "broken", "instructions": []}]})
    steps, status = rewrite_steps_for_diy(BASELINE, client=client)
    assert status == REWRITE_STATUS_FAILED
    assert steps[0]["action"] == "Remove the oil pump."


def _unchanged_payload():
    return {"steps": [
        {"index": i, "action": s["action"], "instructions": list(s["instructions"])}
        for i, s in enumerate(BASELINE)
    ]}


@pytest.mark.parametrize("payload", [None, [], "{}", {"steps": None}])
def test_non_object_model_output_falls_back(payload):
    result, status = rewrite_steps_for_diy(BASELINE, client=FakeMercury(payload))
    assert status == REWRITE_STATUS_FAILED
    assert result == BASELINE


@pytest.mark.parametrize("index", [None, True, 0.0, "0", [], {}])
def test_invalid_index_falls_back(index):
    payload = _unchanged_payload()
    payload["steps"][0]["index"] = index
    result, status = rewrite_steps_for_diy(BASELINE, client=FakeMercury(payload))
    assert (result, status) == (BASELINE, REWRITE_STATUS_FAILED)


@pytest.mark.parametrize("mutation", [
    "missing_index", "metadata", "non_string_action", "non_string_instruction",
    "torque_value", "torque_unit", "opposite_action", "renumbered_swap",
    "new_tool", "different_component",
])
def test_unsafe_rewrite_retains_complete_normalized_source(mutation):
    payload = _unchanged_payload()
    first, second = payload["steps"]
    if mutation == "missing_index":
        del first["index"]
    elif mutation == "metadata":
        first["images"] = []
    elif mutation == "non_string_action":
        first["action"] = {"text": "Remove the oil pump."}
    elif mutation == "non_string_instruction":
        first["instructions"] = [42]
    elif mutation == "torque_value":
        second["instructions"] = ["Torque bolts to 100 Nm."]
    elif mutation == "torque_unit":
        second["instructions"] = ["Torque bolts to 10 lb-ft."]
    elif mutation == "opposite_action":
        first["action"] = "Install the oil pump."
    elif mutation == "renumbered_swap":
        first["action"], second["action"] = second["action"], first["action"]
    elif mutation == "new_tool":
        first["action"] = "Remove the oil pump using a hammer."
    else:
        first["action"] = "Remove the water pump."
    original = deepcopy(BASELINE)
    result, status = rewrite_steps_for_diy(BASELINE, client=FakeMercury(payload))
    assert (result, status) == (original, REWRITE_STATUS_FAILED)
    assert BASELINE == original


@pytest.mark.parametrize("changed", [
    "Warning: Start the engine with the cover removed.",
    "Do not start the engine with the cover removed.",
    "Warning: Do not start the engine with the cover installed.",
])
def test_warning_cannot_be_dropped_or_changed(changed):
    source = [{"action": "Remove the cover.", "instructions": [
        "Warning: Do not start the engine with the cover removed."
    ]}]
    payload = {"steps": [{"index": 0, "action": "Take off the cover.", "instructions": [changed]}]}
    result, status = rewrite_steps_for_diy(source, client=FakeMercury(payload))
    assert (result, status) == (source, REWRITE_STATUS_FAILED)


def test_transport_failure_returns_detached_source():
    class BrokenMercury:
        def complete_json(self, prompt):
            raise TimeoutError("timeout")
    source = deepcopy(BASELINE)
    result, status = rewrite_steps_for_diy(source, client=BrokenMercury())
    assert (result, status) == (BASELINE, REWRITE_STATUS_FAILED)
    result[0]["images"][0]["storage_key"] = "changed"
    assert source == BASELINE


def test_article_rewrite_keeps_document_order_images_and_source_original():
    from autodata_ingestion.article_document import build_ordered_document

    article = {
        "title": "Oil pump removal",
        "source_original": {"payload": {"body": "Original provider words"}},
        "steps": [
            {"action": "Remove the oil pump.", "instructions": ["Discard the old gasket."], "images": []},
            {"action": "Install the oil pump.", "instructions": ["Fit the new gasket."], "images": []},
        ],
        "normalized_document": build_ordered_document({}, [
            {"kind": "text", "text": "1. Remove the oil pump."},
            {"kind": "text", "text": "Discard the old gasket."},
            {"kind": "image", "url": "local://pump-figure", "alt": "Pump"},
            {"kind": "text", "text": "2. Install the oil pump."},
            {"kind": "text", "text": "Fit the new gasket."},
        ]),
    }
    before_document = deepcopy(article["normalized_document"])
    before_orders = [block["source_order"] for block in before_document["blocks"]]
    client = FakeMercury({"steps": [
        {"index": 0, "action": "Take off the oil pump.", "instructions": ["Toss the old gasket."]},
        {"index": 1, "action": "Fit the oil pump.", "instructions": ["Fit the new gasket."]},
    ]})

    result = rewrite_procedure_article(article, vehicle={"year": 2012}, client=client)

    assert result["rewrite_status"] == REWRITE_STATUS_REWRITTEN
    assert [step["action"] for step in result["steps"]] == ["Take off the oil pump.", "Fit the oil pump."]
    assert result["body"] == "Take off the oil pump.\nToss the old gasket.\nFit the oil pump.\nFit the new gasket."
    blocks = result["normalized_document"]["blocks"]
    assert [block["source_order"] for block in blocks] == before_orders
    assert [block.get("text") for block in blocks if block["type"] != "image"] == [
        "Take off the oil pump.", "Toss the old gasket.", "Fit the oil pump.", "Fit the new gasket."
    ]
    assert blocks[2] == before_document["blocks"][2]
    assert result["source_original"] == article["source_original"]
    assert article["steps"][0]["action"] == "Remove the oil pump."
