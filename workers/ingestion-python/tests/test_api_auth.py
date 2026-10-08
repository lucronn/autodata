from __future__ import annotations

import unittest
from unittest.mock import patch
from io import BytesIO

from autodata_ingestion.api_auth import api_key_headers
from autodata_ingestion.autoapi_connector import AutoAPIConnector
from autodata_ingestion.autoapitwo_catalog import AutoAPITwoCatalogConnector
from autodata_ingestion.autoapitwo_connector import AutoAPITwoConnector


class _Response(BytesIO):
    status = 200
    code = 200

    def __init__(self, url: str, body: bytes):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class ApiKeyHeadersTests(unittest.TestCase):
    def test_returns_distinct_service_scoped_server_headers(self):
        with patch.dict(
            "os.environ",
            {
                "AUTODATA_BANKONE_API_KEY": "adk_bankone_" + "a" * 43,
                "AUTODATA_BANKTWO_API_KEY": "adk_banktwo_" + "b" * 43,
            },
        ):
            bankone = api_key_headers("bankone")
            banktwo = api_key_headers("banktwo")
        self.assertEqual(bankone, {"Authorization": "Bearer adk_bankone_" + "a" * 43})
        self.assertEqual(banktwo, {"Authorization": "Bearer adk_banktwo_" + "b" * 43})
        self.assertNotEqual(bankone, banktwo)

    def test_missing_key_is_empty_and_wrong_service_key_is_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(api_key_headers("bankone"), {})
        with patch.dict("os.environ", {"AUTODATA_BANKTWO_API_KEY": "adk_bankone_" + "a" * 43}):
            with self.assertRaisesRegex(ValueError, "invalid format"):
                api_key_headers("banktwo")

    def test_unsupported_service_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            api_key_headers("other")

    def test_bankone_client_sends_its_secret_server_side(self):
        seen = []
        token = "adk_bankone_" + "a" * 43

        def opener(request, timeout):
            seen.append(request.get_header("Authorization"))
            return _Response(request.full_url, b'{"header":{},"body":[]}')

        with patch.dict("os.environ", {"AUTODATA_BANKONE_API_KEY": token}):
            client = AutoAPIConnector("https://bankone.test", opener=opener)
            client._get_json_once("/v1/api/years")
        self.assertEqual(seen, [f"Bearer {token}"])

    def test_bankt_two_catalog_and_article_clients_send_their_key(self):
        seen = []
        token = "adk_banktwo_" + "b" * 43

        def opener(request, timeout):
            seen.append(request.get_header("Authorization"))
            return _Response(request.full_url, b'{"years":["2024"]}')

        with patch.dict("os.environ", {"AUTODATA_BANKTWO_API_KEY": token}):
            AutoAPITwoCatalogConnector("https://banktwo.test", opener=opener)._read("/api/v1/fleet/years")
            AutoAPITwoConnector("https://banktwo.test", opener=opener).read("/api/v1/fleet/carids/123")
        self.assertEqual(seen, [f"Bearer {token}", f"Bearer {token}"])


if __name__ == "__main__":
    unittest.main()
