import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from timezone_config import (
    DEFAULT_REFERENCE_OFFSET,
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
        self.assertIsNone(self.config.load_reference_country())
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"reference_offset": 14.25}', encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"reference_offset": true}', encoding="utf-8")
        self.assertEqual(self.config.load_reference_offset(), DEFAULT_REFERENCE_OFFSET)
        self.path.write_text('{"reference_country": 42}', encoding="utf-8")
        self.assertIsNone(self.config.load_reference_country())

    def test_valid_reference_offset_is_saved_and_restored(self):
        self.assertTrue(self.config.save_reference_offset(-6))
        self.assertEqual(self.config.load_reference_offset(), -6)
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {
                "reference_offset": -6,
                "reference_country": None,
            },
        )

    def test_reference_country_is_saved_atomically_with_offset(self):
        self.assertTrue(
            self.config.save_reference(-7, "United States (Mountain)")
        )
        self.assertEqual(self.config.load_reference_offset(), -7)
        self.assertEqual(
            self.config.load_reference_country(), "United States (Mountain)"
        )
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {
                "reference_offset": -7,
                "reference_country": "United States (Mountain)",
            },
        )

    def test_fractional_reference_offset_is_saved_and_restored(self):
        self.assertTrue(self.config.save_reference_offset(5.5))
        self.assertEqual(self.config.load_reference_offset(), 5.5)
        self.assertTrue(self.config.save_reference_offset(-2.5))
        self.assertEqual(self.config.load_reference_offset(), -2.5)

if __name__ == "__main__":
    unittest.main()
