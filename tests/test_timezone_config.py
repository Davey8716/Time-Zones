import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from timezone_config import (
    DEFAULT_LOCATION_ORDER,
    DEFAULT_REFERENCE_OFFSET,
    LOCATION_ORDER_EASTERN,
    LOCATION_ORDER_WESTERN,
    TimeZoneConfig,
)


class TimeZoneConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "timezone_config.json"
        self.config = TimeZoneConfig(self.path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_missing_malformed_and_invalid_files_default_to_gmt(self):
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"reference_offset": 14.25}', encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"reference_offset": true}', encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"location_order": "invalid"}', encoding="utf-8")
        self.assertEqual(self.config.load_location_order(), DEFAULT_LOCATION_ORDER)

    def test_valid_reference_offset_is_saved_and_restored(self):
        self.assertTrue(self.config.save_reference_offset(-6))
        self.assertEqual(self.config.load_reference_offset(), -6)
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {
                "reference_offset": -6,
                "location_order": LOCATION_ORDER_WESTERN,
            },
        )

    def test_fractional_reference_offset_is_saved_and_restored(self):
        self.assertTrue(self.config.save_reference_offset(5.5))
        self.assertEqual(self.config.load_reference_offset(), 5.5)
        self.assertTrue(self.config.save_reference_offset(-2.5))
        self.assertEqual(self.config.load_reference_offset(), -2.5)

    def test_reference_and_location_order_are_preserved_together(self):
        self.config.save_reference_offset(-6)
        self.config.save_location_order(LOCATION_ORDER_EASTERN)
        self.assertEqual(self.config.load_reference_offset(), -6)
        self.assertEqual(self.config.load_location_order(), LOCATION_ORDER_EASTERN)
        self.config.save_location_order(LOCATION_ORDER_WESTERN)
        self.assertEqual(self.config.load_reference_offset(), -6)


if __name__ == "__main__":
    unittest.main()
