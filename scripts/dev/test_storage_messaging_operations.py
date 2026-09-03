import unittest


from nats_health import normalize_stream_info
from replay_outbox import replay_target


class StorageMessagingOperationsTests(unittest.TestCase):
    def test_stream_info_is_reduced_to_safe_operational_fields(self):
        normalized = normalize_stream_info({
            "config": {
                "name": "AUTODATA",
                "subjects": ["dataset.>"],
                "retention": "limits",
            },
            "state": {"messages": 7, "bytes": 512, "first_seq": 10, "last_seq": 16},
        })

        self.assertEqual(normalized, {
            "name": "AUTODATA",
            "subjects": ["dataset.>"],
            "retention": "limits",
            "messages": 7,
            "bytes": 512,
            "first_seq": 10,
            "last_seq": 16,
        })

    def test_replay_requires_exactly_one_target(self):
        self.assertEqual(replay_target("event-1", None), ("event", "event-1"))
        self.assertEqual(replay_target(None, "job-1"), ("job", "job-1"))
        with self.assertRaises(ValueError):
            replay_target(None, None)
        with self.assertRaises(ValueError):
            replay_target("event-1", "job-1")


if __name__ == "__main__":
    unittest.main()
