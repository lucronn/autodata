import unittest

from autodata_ingestion.catalog_sync import _resume_after_year, _scope_key


class CatalogSyncResumeTests(unittest.TestCase):
    def test_scope_key_is_stable(self):
        self.assertEqual(
            _scope_key(
                {
                    "year": 1997,
                    "make": "Toyota",
                    "model": "RAV4",
                    "engine": "L4-2.0L",
                    "autoapitwo_vehicle_id": "41218",
                }
            ),
            "1997:Toyota:RAV4:L4-2.0L:41218",
        )

    def test_resume_skips_years_before_latest_completed_year(self):
        keys = {
            "1977:Ford:F 150:V8:1",
            "1978:Ford:F 150:V8:2",
            "1978:Chevy:C10:V8:3",
        }
        self.assertEqual(_resume_after_year(keys), 1978)
        self.assertIsNone(_resume_after_year(set()))


if __name__ == "__main__":
    unittest.main()
