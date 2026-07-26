from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from timezone_data import (
    OFFSET_ORDER,
    Location,
    format_gmt_offset,
    offset_for,
    time_zone_database_available,
    snapshots,
)


class TimeZoneDataTests(unittest.TestCase):
    def test_offset_order_has_all_25_rows_in_requested_order(self):
        self.assertEqual(OFFSET_ORDER, tuple(range(-12, 13)))
        self.assertEqual(len(OFFSET_ORDER), 25)

    def test_gmt_offset_formatting(self):
        self.assertEqual(format_gmt_offset(0), "GMT")
        self.assertEqual(format_gmt_offset(7), "GMT+7")
        self.assertEqual(format_gmt_offset(-12), "GMT-12")

    def test_london_moves_rows_for_daylight_saving(self):
        london = Location("United Kingdom", "London", "Europe/London")
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        self.assertEqual(offset_for(london, winter), (0, "GMT"))
        self.assertEqual(offset_for(london, summer), (1, "BST"))

    def test_non_integer_and_out_of_range_offsets_are_excluded(self):
        at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        kolkata = Location("India", "New Delhi", "Asia/Kolkata")
        kiritimati = Location("Kiribati", "Kiritimati", "Pacific/Kiritimati")
        self.assertIsNone(offset_for(kolkata, at_utc))
        self.assertIsNone(offset_for(kiritimati, at_utc))

    def test_missing_database_is_detected(self):
        with patch(
            "timezone_data.ZoneInfo",
            side_effect=ZoneInfoNotFoundError("missing"),
        ):
            self.assertFalse(time_zone_database_available())

    def test_snapshots_keep_empty_rows_and_limit_curated_places(self):
        at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        many = tuple(
            Location(f"Country {i}", f"City {i}", "Etc/GMT-1", i)
            for i in range(5)
        )
        result = snapshots(at_utc, many, max_locations=3)
        self.assertEqual(tuple(row.offset for row in result), OFFSET_ORDER)
        plus_one = next(row for row in result if row.offset == 1)
        self.assertEqual(len(plus_one.locations), 3)
        self.assertTrue(
            any(not row.locations for row in result),
            "Offsets with no matching curated location must remain visible",
        )

    def test_european_and_western_locations_are_prioritized(self):
        at_utc = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
        rows = {row.offset: row for row in snapshots(at_utc)}
        self.assertEqual(
            [location.country for location in rows[0].locations],
            ["Portugal (Azores)", "Ghana"],
        )
        self.assertEqual(
            [location.country for location in rows[1].locations],
            ["United Kingdom", "Ireland", "Nigeria"],
        )
        self.assertEqual(
            [location.country for location in rows[2].locations],
            ["France", "Germany", "South Africa"],
        )

    def test_eastern_order_prioritizes_pacific_locations(self):
        at_utc = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
        rows = {row.offset: row for row in snapshots(at_utc, location_order="eastern")}
        self.assertEqual(rows[-8].locations[0].country, "Pitcairn Islands")

    def test_date_rollover_is_visible(self):
        at_utc = datetime(2026, 1, 1, 18, 30, tzinfo=timezone.utc)
        plus_twelve = next(row for row in snapshots(at_utc) if row.offset == 12)
        self.assertEqual(plus_twelve.local_datetime.date().isoformat(), "2026-01-02")
        self.assertEqual(plus_twelve.local_datetime.strftime("%H:%M"), "06:30")


if __name__ == "__main__":
    unittest.main()
