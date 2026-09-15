from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_consumer_agent_is_registered_with_report_only_capability():
    registry = json.loads((ROOT / ".autodata-agent-registry.json").read_text())
    matches = [agent for agent in registry["agents"] if agent["name"] == "autodata-consumer-agent"]

    assert len(matches) == 1
    agent = matches[0]
    assert (ROOT / agent["prompt"]).is_file()
    assert agent["can_merge"] is False
    assert agent["can_deploy"] == []
    assert "reports" in " ".join(agent["can_write"])

