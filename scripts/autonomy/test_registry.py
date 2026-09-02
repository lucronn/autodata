import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(
            (ROOT / ".autodata-agent-registry.json").read_text(encoding="utf-8")
        )
        cls.policy = json.loads(
            (ROOT / ".autodata-autonomy-policy.json").read_text(encoding="utf-8")
        )

    def test_every_registered_agent_has_a_project_prompt(self):
        agents = self.registry["agents"]

        self.assertEqual(len({agent["name"] for agent in agents}), len(agents))
        for agent in agents:
            self.assertTrue((ROOT / agent["prompt"]).is_file(), agent["name"])

    def test_only_release_agent_can_merge(self):
        merge_agents = [agent["name"] for agent in self.registry["agents"] if agent["can_merge"]]

        self.assertEqual(merge_agents, ["autodata-release-agent"])

    def test_production_is_not_an_allowed_deployment_target(self):
        self.assertFalse(self.policy["autonomy"]["production_deployment"])
        self.assertNotIn("production", self.policy["autonomy"]["allowed_deployment_targets"])
        self.assertNotIn("production", self.registry["agents"][-1]["can_deploy"])

    def test_policy_requires_independent_quality_gates(self):
        required = set(self.policy["merge_gate"]["required_decisions"])

        self.assertTrue({"data_quality", "security", "reliability", "independent_review"}.issubset(required))
        self.assertEqual(self.policy["merge_gate"]["max_critical_findings"], 0)
        self.assertEqual(self.policy["merge_gate"]["max_high_findings"], 0)


if __name__ == "__main__":
    unittest.main()
