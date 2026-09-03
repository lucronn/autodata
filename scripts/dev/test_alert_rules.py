import re
import unittest
from pathlib import Path


RULES = Path(__file__).parents[2] / "infra/observability/prometheus-alerts.yaml"


class AlertRulesTests(unittest.TestCase):
    def test_rules_cover_each_operational_failure_class(self):
        content = RULES.read_text()
        expected_rules = {
            "AutoDataFastLaneViewabilitySLO",
            "AutoDataQueueStale",
            "AutoDataDeadLetterPresent",
            "AutoDataHumanReviewStale",
            "AutoDataFulfillmentStalled",
            "AutoDataSourceWatermarkStale",
            "AutoDataAccessDeniedSpike",
        }

        self.assertEqual(set(re.findall(r"^      - alert: (\S+)$", content, re.MULTILINE)), expected_rules)
        self.assertNotRegex(content, r"\b(TBD|TODO|CHANGE_ME)\b")

    def test_rules_use_emitted_metric_names_and_have_runbook_links(self):
        content = RULES.read_text()
        for metric in (
            "autodata_payment_to_viewable_seconds",
            "autodata_queue_oldest_age_seconds",
            "autodata_dead_letter_count",
            "autodata_human_review_oldest_age_seconds",
            "autodata_entitlement_fulfillment_pending",
            "autodata_source_watermark_age_seconds",
            "autodata_api_access_denied_total",
        ):
            self.assertIn(metric, content)
        self.assertGreaterEqual(content.count("runbook_url:"), len(expected := expected_rules(content)))


def expected_rules(content: str) -> set[str]:
    return set(re.findall(r"^      - alert: (\S+)$", content, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
