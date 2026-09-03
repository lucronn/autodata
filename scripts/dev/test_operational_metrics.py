import unittest


from operational_metrics import Metric, confidence_histogram, render_metrics


class OperationalMetricsTests(unittest.TestCase):
    def test_render_metrics_escapes_labels_and_orders_them(self):
        output = render_metrics([
            Metric("autodata_test", 2, {"z": "line\nvalue", "a": 'quoted"value'}),
        ])

        self.assertEqual(
            output,
            '# TYPE autodata_test gauge\n'
            'autodata_test{a="quoted\\"value",z="line\\nvalue"} 2\n',
        )

    def test_confidence_histogram_is_cumulative_and_ignores_nulls(self):
        histogram = confidence_histogram([0.49, 0.7, 0.91, 1.0, None])

        self.assertEqual(histogram, [(0.5, 1), (0.7, 2), (0.8, 2), (0.9, 2), (0.95, 3), (1.0, 4)])

    def test_histogram_type_is_declared_on_the_base_family(self):
        output = render_metrics([
            Metric(
                "autodata_confidence_bucket",
                3,
                {"le": "+Inf"},
                kind="histogram",
                family_name="autodata_confidence",
            ),
            Metric(
                "autodata_confidence_count",
                3,
                kind="histogram",
                family_name="autodata_confidence",
            ),
        ])

        self.assertEqual(
            output,
            '# TYPE autodata_confidence histogram\n'
            'autodata_confidence_bucket{le="+Inf"} 3\n'
            'autodata_confidence_count 3\n',
        )


if __name__ == "__main__":
    unittest.main()
