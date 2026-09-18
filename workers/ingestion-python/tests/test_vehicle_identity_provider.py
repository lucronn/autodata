import unittest

from autodata_ingestion.vehicle_identity_provider import (
    normalize_autoapitwo_candidate,
    resolve_autoapitwo_vehicle,
)


SILVERADO = {
    "year": "1999",
    "make": "Chevy Truck",
    "model": "C 1500 Truck 2WD",
    "engine": "V8-5.3L VIN T",
    "acesVehicleNames": [
        "148378: 1999 Chevrolet Silverado 1500 CAN",
        "7630: 1999 Chevrolet Silverado 1500 LT USA",
        "7620: 1999 Chevrolet Silverado 1500 USA",
    ],
    "acesEngineConfigNames": ["7910: V8-5.3L 5328cc OHV MFI VIN T (LM7)"],
    "description": "1999 Chevy Truck C 1500 Truck 2WD V8-5.3L VIN T",
    "id": "34218",
}


class VehicleIdentityProviderTests(unittest.TestCase):
    def test_normalizes_provider_labels_and_retains_typed_aces_mappings(self):
        candidate = normalize_autoapitwo_candidate(SILVERADO)

        self.assertEqual(candidate["provider_car_id"], "34218")
        self.assertEqual(
            candidate["observation"].to_dict() | {"aliases": []},
            {
                "year": 1999,
                "make": "Chevrolet",
                "model": "Silverado 1500",
                "region": "US",
                "body_style": None,
                "trim": None,
                "drivetrain": "2WD",
                "engine_displacement_l": 5.3,
                "aliases": [],
            },
        )
        self.assertEqual(
            {(item["entity_type"], item["provider_id"]) for item in candidate["provider_mappings"]},
            {
                ("car", "34218"),
                ("aces_vehicle", "148378"),
                ("aces_vehicle", "7630"),
                ("aces_vehicle", "7620"),
                ("aces_engine", "7910"),
            },
        )

    def test_resolves_exact_silverado_and_equivalent_aliases(self):
        result = resolve_autoapitwo_vehicle(
            "99 Silverado 1500 2WD 5.3L",
            [SILVERADO],
        )

        self.assertEqual(result.status, "matched")
        self.assertEqual(result.selected["provider_car_id"], "34218")
        self.assertGreaterEqual(result.selected["score"], 90)

    def test_different_drive_or_engine_does_not_silently_match(self):
        result = resolve_autoapitwo_vehicle(
            "1999 Chevrolet Silverado 1500 4WD 5.7L",
            [SILVERADO],
        )

        self.assertEqual(result.status, "unmatched")
        self.assertIsNone(result.selected)

    def test_shared_aces_engine_id_is_not_a_unique_vehicle_match(self):
        other = {
            **SILVERADO,
            "id": "34219",
            "model": "K 1500 Truck 4WD",
            "description": "1999 Chevy Truck K 1500 Truck 4WD V8-5.3L VIN T",
        }

        result = resolve_autoapitwo_vehicle("1999 Chevrolet Silverado 1500 5.3L", [SILVERADO, other])

        self.assertEqual(result.status, "ambiguous")
        self.assertIsNone(result.selected)
        self.assertEqual(
            {mapping["provider_id"] for candidate in result.candidates for mapping in candidate["provider_mappings"] if mapping["entity_type"] == "aces_engine"},
            {"7910"},
        )

