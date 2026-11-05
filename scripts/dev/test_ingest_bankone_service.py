"""Offline regressions for the Bankone ingestion CLI constructor contract."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "ingest_bankone_service", Path(__file__).with_name("ingest_bankone_service.py")
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class BankoneServiceCLITests(unittest.TestCase):
    def setUp(self):
        self.argv = [
            "--base-url", "http://127.0.0.1:9999", "--year", "2012",
            "--make", "Toyota", "--limit", "10", "--persist",
        ]
        self.batch = object()
        self.fetch = self.enterContext(patch.object(
            cli, "fetch_bankone_batches",
            return_value=([self.batch], [], {"traversal_error_count": 0}),
        ))
        self.execute = self.enterContext(patch.object(
            cli, "execute_bank_batch", return_value={"status": "ok"},
        ))
        self.enterContext(patch.object(cli, "source_connector_token", return_value=None))

    def assert_successful_timeout(self, extra_args, timeout):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cli.main(self.argv + extra_args)

        self.fetch.assert_called_once()
        connector = self.fetch.call_args.args[0]
        self.assertIsInstance(connector, cli.SourceConnectorClient)
        self.assertEqual(connector.timeout, timeout)
        self.assertEqual(connector.provider, "bankone")
        self.assertEqual(connector.base_url, "http://127.0.0.1:9999")
        self.assertEqual(self.fetch.call_args.kwargs["target_year"], 2012)
        self.assertEqual(self.fetch.call_args.kwargs["target_make"], "Toyota")
        self.assertEqual(self.fetch.call_args.kwargs["limit"], 10)
        self.execute.assert_called_once()
        self.assertEqual(self.execute.call_args.args, ([self.batch],))
        self.assertIs(self.execute.call_args.kwargs["persist"], True)
        self.assertEqual(self.execute.call_args.kwargs["adapter_name"], "bankone")
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")

    def test_default_timeout_reaches_real_connector(self):
        self.assert_successful_timeout([], 30.0)

    def test_custom_timeout_reaches_real_connector(self):
        self.assert_successful_timeout(["--timeout-seconds", "7.5"], 7.5)

    def test_zero_timeout_is_rejected_before_traversal_or_persistence(self):
        with self.assertRaises(ValueError):
            cli.main(self.argv + ["--timeout-seconds", "0"])
        self.fetch.assert_not_called()
        self.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
