from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from timezone_data import (
    COUNTRIES,
    COUNTRY_ZONE_OPTIONS,
    OFFSET_ORDER,
    Location,
    format_gmt_offset,
    offset_for,
    time_zone_database_available,
    snapshots,
    time_zone_for_country,
)


class TimeZoneDataTests(unittest.TestCase):
    def test_offset_order_covers_world_quarter_hour_offsets(self):
        self.assertEqual(OFFSET_ORDER[0], -12)
        self.assertEqual(OFFSET_ORDER[-1], 14)
        self.assertIn(5.5, OFFSET_ORDER)
        self.assertIn(5.75, OFFSET_ORDER)
        self.assertIn(-2.5, OFFSET_ORDER)
        self.assertIn(12.75, OFFSET_ORDER)

    def test_gmt_offset_formatting(self):
        self.assertEqual(format_gmt_offset(0), "GMT")
        self.assertEqual(format_gmt_offset(7), "GMT+7")
        self.assertEqual(format_gmt_offset(-12), "GMT-12")
        self.assertEqual(format_gmt_offset(-2.5), "GMT-2:30")
        self.assertEqual(format_gmt_offset(5.5), "GMT+5:30")
        self.assertEqual(format_gmt_offset(5.75), "GMT+5:45")
        self.assertEqual(format_gmt_offset(12.75), "GMT+12:45")

    def test_london_moves_rows_for_daylight_saving(self):
        london = Location("United Kingdom", "London", "Europe/London")
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        self.assertEqual(offset_for(london, winter), (0, "GMT"))
        self.assertEqual(offset_for(london, summer), (1, "BST"))

    def test_fractional_and_dateline_offsets_are_supported(self):
        at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        kolkata = Location("India", "New Delhi", "Asia/Kolkata")
        kiritimati = Location("Kiribati", "Kiritimati", "Pacific/Kiritimati")
        self.assertEqual(offset_for(kolkata, at_utc), (5.5, "IST"))
        self.assertEqual(offset_for(kiritimati, at_utc), (14, "+14"))

    def test_fractional_and_dateline_rows_have_real_locations(self):
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        winter_rows = {row.offset: row for row in snapshots(winter)}
        summer_rows = {row.offset: row for row in snapshots(summer)}

        self.assertEqual(
            winter_rows[-9.5].locations[0].country,
            "French Polynesia (Marquesas Islands)",
        )
        gambier = next(
            location
            for location in winter_rows[-9].locations
            if location.zone_id == "Pacific/Gambier"
        )
        self.assertEqual(gambier.country, "French Polynesia (Gambier Islands)")
        self.assertEqual(gambier.city, "Rikitea")
        self.assertEqual(winter_rows[5.5].locations[0].country, "India")
        self.assertEqual(winter_rows[5.75].locations[0].country, "Nepal")
        self.assertEqual(winter_rows[5.75].locations[0].city, "Kathmandu")
        self.assertEqual(winter_rows[-3.5].locations[0].city, "St. John's")
        self.assertEqual(summer_rows[-2.5].locations[0].city, "St. John's")
        self.assertEqual(winter_rows[10.5].locations[0].city, "Adelaide")
        self.assertEqual(summer_rows[9.5].locations[0].city, "Adelaide")
        self.assertEqual(winter_rows[13.75].locations[0].city, "Waitangi")
        self.assertEqual(summer_rows[12.75].locations[0].city, "Waitangi")
        for rows, expected_offset in (
            (winter_rows, 13.75),
            (summer_rows, 12.75),
        ):
            chatham_offsets = [
                offset
                for offset, row in rows.items()
                for location in row.locations
                if location.zone_id == "Pacific/Chatham"
            ]
            self.assertEqual(chatham_offsets, [expected_offset])
        self.assertEqual(
            {location.country for location in summer_rows[13].locations},
            {"Samoa", "Tonga"},
        )
        self.assertEqual(summer_rows[14].locations[0].city, "Kiritimati")

    def test_every_current_world_offset_has_a_curated_location(self):
        for at_utc in (
            datetime(2026, 1, 15, 12, tzinfo=timezone.utc),
            datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        ):
            actual_offsets = {
                result[0]
                for country, zone_id in COUNTRY_ZONE_OPTIONS
                if (result := offset_for(Location(country, "", zone_id), at_utc))
                is not None
            }
            populated_offsets = {
                row.offset for row in snapshots(at_utc) if row.locations
            }
            self.assertTrue(actual_offsets.issubset(populated_offsets))

    def test_country_catalogue_is_complete_and_alphabetical(self):
        self.assertEqual(len(COUNTRIES), 268)
        self.assertEqual(len(COUNTRIES), len(set(COUNTRIES)))
        self.assertEqual(COUNTRIES[:3], ["Afghanistan", "Åland Islands", "Albania"])
        self.assertLess(
            COUNTRIES.index("United States (Mountain)"),
            COUNTRIES.index("United States (Pacific)"),
        )
        self.assertEqual(time_zone_for_country("India"), "Asia/Kolkata")
        self.assertIsNone(time_zone_for_country("united states"))
        self.assertEqual(
            time_zone_for_country("United States (Mountain)"),
            "America/Denver",
        )
        self.assertEqual(
            time_zone_for_country("United States (Eastern)"),
            "America/New_York",
        )
        self.assertEqual(
            time_zone_for_country("Canada (Newfoundland)"),
            "America/St_Johns",
        )
        self.assertEqual(
            time_zone_for_country("Australia (South Australia)"),
            "Australia/Adelaide",
        )
        self.assertEqual(
            time_zone_for_country("Portugal (Mainland)"),
            "Europe/Lisbon",
        )
        self.assertNotIn("Portugal", COUNTRIES)
        self.assertNotIn("United States", COUNTRIES)
        self.assertIn("Portugal (Azores)", COUNTRIES)
        self.assertEqual(
            time_zone_for_country("French Polynesia (Marquesas Islands)"),
            "Pacific/Marquesas",
        )
        self.assertEqual(
            time_zone_for_country("New Zealand (Chatham Islands)"),
            "Pacific/Chatham",
        )
        self.assertIn(("Australia", "Australia/Eucla"), COUNTRY_ZONE_OPTIONS)
        self.assertIn(("New Zealand", "Pacific/Chatham"), COUNTRY_ZONE_OPTIONS)

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
