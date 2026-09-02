import unittest


from release_controller import build_release_plan, validate_release_inputs


class ReleaseControllerTests(unittest.TestCase):
    def test_release_requires_exact_sha_and_allows_only_dev_targets(self):
        policy = {
            "autonomy": {"production_deployment": False, "allowed_deployment_targets": ["dev"]}
        }
        registry = {
            "agents": [
                {"name": "autodata-release-agent", "can_merge": True, "can_deploy": ["dev"]}
            ]
        }
        manifest = {
            "run_id": "run-1",
            "task_id": "task-1",
            "agent": "autodata-orchestrator",
            "base_sha": "a" * 40,
            "implementation_sha": "b" * 40,
            "decision": "pass",
            "deployment_target": "production",
        }

        failures = validate_release_inputs(manifest, policy, registry, current_head_sha="c" * 40)

        self.assertIn("implementation SHA does not match checked-out HEAD", failures)
        self.assertIn("production deployment is disabled by policy", failures)

    def test_release_plan_pins_merge_to_implementation_sha(self):
        manifest = {
            "run_id": "run-1",
            "task_id": "task-1",
            "implementation_sha": "b" * 40,
            "repository": "lucronn/autodata",
        }

        plan = build_release_plan(
            manifest,
            head_branch="codex/task-1",
            project_number=7,
            pr_number=12,
        )

        self.assertEqual(plan["implementation_sha"], "b" * 40)
        self.assertTrue(any("--match-head-commit" in command for command in plan["commands"]))
        self.assertTrue(any("project item-add" in command for command in plan["commands"]))


if __name__ == "__main__":
    unittest.main()
