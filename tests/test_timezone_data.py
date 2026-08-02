from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from timezone_data import (
    COUNTRIES,
    COUNTRY_DROPDOWN_LABELS,
    COUNTRY_TIME_ZONES,
    COUNTRY_ZONE_OPTIONS,
    LOCATIONS,
    OFFSET_ORDER,
    Location,
    country_for_dropdown_text,
    display_location_for_country,
    dropdown_label_for_country,
    format_gmt_offset,
    next_offset_transition,
    offset_for,
    region_for_zone,
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
        self.assertEqual(format_gmt_offset(0), "UTC")
        self.assertEqual(format_gmt_offset(7), "UTC+7")
        self.assertEqual(format_gmt_offset(-12), "UTC-12")
        self.assertEqual(format_gmt_offset(-2.5), "UTC-2:30")
        self.assertEqual(format_gmt_offset(5.5), "UTC+5:30")
        self.assertEqual(format_gmt_offset(5.75), "UTC+5:45")
        self.assertEqual(format_gmt_offset(12.75), "UTC+12:45")

    def test_london_moves_rows_for_daylight_saving(self):
        london = Location("United Kingdom", "London", "Europe/London")
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        self.assertEqual(offset_for(london, winter), (0, "GMT"))
        self.assertEqual(offset_for(london, summer), (1, "BST"))

    def test_next_offset_transition_finds_hour_and_half_hour_changes(self):
        at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        london = next_offset_transition("Europe/London", at_utc)
        lord_howe = next_offset_transition("Australia/Lord_Howe", at_utc)

        self.assertIsNotNone(london)
        self.assertEqual(
            london.at_utc,
            datetime(2026, 3, 29, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(london.offset, 1)
        self.assertIsNotNone(lord_howe)
        self.assertEqual(
            lord_howe.at_utc,
            datetime(2026, 4, 4, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(lord_howe.offset, 10.5)

    def test_next_offset_transition_returns_none_for_fixed_zone(self):
        at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        self.assertIsNone(next_offset_transition("Asia/Kolkata", at_utc))

    def test_display_location_prefers_exact_region_then_zone_city(self):
        self.assertEqual(
            display_location_for_country("United States (Eastern)"),
            Location(
                "United States (Eastern)",
                "Washington, D.C.",
                "America/New_York",
            ),
        )
        self.assertEqual(
            display_location_for_country("Australia (Western Australia)"),
            Location(
                "Australia (Western Australia)",
                "Perth",
                "Australia/Perth",
            ),
        )
        self.assertIsNone(display_location_for_country("Not a country"))

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
        self.assertEqual(summer_rows[13].locations[0].country, "Samoa")
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
        self.assertEqual(len(COUNTRIES), 308)
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

    def test_russian_dropdown_regions_cover_all_eleven_time_zones(self):
        expected_zones = {
            "Russia (Kaliningrad)": "Europe/Kaliningrad",
            "Russia (Moscow)": "Europe/Moscow",
            "Russia (Samara)": "Europe/Samara",
            "Russia (Yekaterinburg)": "Asia/Yekaterinburg",
            "Russia (Omsk)": "Asia/Omsk",
            "Russia (Krasnoyarsk)": "Asia/Krasnoyarsk",
            "Russia (Irkutsk)": "Asia/Irkutsk",
            "Russia (Yakutsk)": "Asia/Yakutsk",
            "Russia (Vladivostok)": "Asia/Vladivostok",
            "Russia (Magadan)": "Asia/Magadan",
            "Russia (Kamchatka)": "Asia/Kamchatka",
        }
        russian_entries = [
            country for country in COUNTRIES if country.startswith("Russia")
        ]
        self.assertEqual(russian_entries, sorted(expected_zones))
        self.assertNotIn("Russia", COUNTRIES)
        at_utc = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)
        actual_offsets = []
        for country, zone_id in expected_zones.items():
            self.assertEqual(time_zone_for_country(country), zone_id)
            result = offset_for(Location(country, "", zone_id), at_utc)
            self.assertIsNotNone(result)
            actual_offsets.append(result[0])
        self.assertEqual(sorted(actual_offsets), list(range(2, 13)))
        self.assertEqual(
            [location for location in LOCATIONS if location.country == "Russia"],
            [Location("Russia", "Moscow", "Europe/Moscow", 1)],
        )

    def test_multizone_dropdown_catalogue_covers_dst_rule_groups(self):
        expected_new_entries = {
            "Australia (New South Wales)": "Australia/Sydney",
            "Australia (Western Australia)": "Australia/Perth",
            "Brazil (Acre)": "America/Rio_Branco",
            "Brazil (Amazon)": "America/Manaus",
            "Brazil (Brasília Time)": "America/Sao_Paulo",
            "Canada (Atlantic Standard)": "America/Blanc-Sablon",
            "Canada (Central)": "America/Winnipeg",
            "Canada (Eastern)": "America/Toronto",
            "Canada (Eastern Standard)": "America/Atikokan",
            "Canada (Saskatchewan)": "America/Regina",
            "Canada (Yukon)": "America/Whitehorse",
            "Chile (Easter Island)": "Pacific/Easter",
            "Chile (Magallanes)": "America/Punta_Arenas",
            "Chile (Mainland)": "America/Santiago",
            "China (Beijing Time)": "Asia/Shanghai",
            "China (Xinjiang)": "Asia/Urumqi",
            "Congo (Dem. Rep. — Eastern)": "Africa/Lubumbashi",
            "Congo (Dem. Rep. — Western)": "Africa/Kinshasa",
            "Ecuador (Galápagos Islands)": "Pacific/Galapagos",
            "Ecuador (Mainland)": "America/Guayaquil",
            "Greenland (Danmarkshavn)": "America/Danmarkshavn",
            "Greenland (Nuuk)": "America/Nuuk",
            "Greenland (Pituffik)": "America/Thule",
            "Indonesia (Central)": "Asia/Makassar",
            "Indonesia (Eastern)": "Asia/Jayapura",
            "Indonesia (Western)": "Asia/Jakarta",
            "Kiribati (Phoenix Islands)": "Pacific/Kanton",
            "Mexico (Baja California)": "America/Tijuana",
            "Mexico (Central)": "America/Mexico_City",
            "Mexico (Ciudad Juárez)": "America/Ciudad_Juarez",
            "Mexico (Northern Border)": "America/Matamoros",
            "Mexico (Quintana Roo)": "America/Cancun",
            "Mexico (Sonora)": "America/Hermosillo",
            "Micronesia (Chuuk)": "Pacific/Chuuk",
            "Mongolia (Hovd)": "Asia/Hovd",
            "Mongolia (Ulaanbaatar)": "Asia/Ulaanbaatar",
            "Papua New Guinea (Bougainville)": "Pacific/Bougainville",
            "Papua New Guinea (Mainland)": "Pacific/Port_Moresby",
            "Spain (Canary Islands)": "Atlantic/Canary",
            "Spain (Mainland)": "Europe/Madrid",
            "United States (Aleutian Islands)": "America/Adak",
        }
        for country, zone_id in expected_new_entries.items():
            self.assertEqual(time_zone_for_country(country), zone_id)

        ambiguous_names = {
            "Brazil",
            "Chile",
            "China",
            "Congo (Dem. Rep.)",
            "Ecuador",
            "Greenland",
            "Indonesia",
            "Mexico",
            "Mongolia",
            "Papua New Guinea",
            "Spain",
        }
        self.assertTrue(ambiguous_names.isdisjoint(COUNTRIES))

        countries = {
            "Australia",
            "Brazil",
            "Canada",
            "Chile",
            "China",
            "Congo (Dem. Rep.)",
            "Ecuador",
            "Greenland",
            "Indonesia",
            "Kiribati",
            "Mexico",
            "Micronesia",
            "Mongolia",
            "Papua New Guinea",
            "Spain",
            "United States",
        }
        dates = (
            datetime(2026, 1, 15, 12, tzinfo=timezone.utc),
            datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        )

        def signature(zone_id):
            return tuple(
                offset_for(Location("", "", zone_id), at_utc)[0]
                for at_utc in dates
            )

        for country in countries:
            all_signatures = {
                signature(zone_id)
                for candidate, zone_id in COUNTRY_ZONE_OPTIONS
                if candidate == country
            }
            prefix = (
                "Congo (Dem. Rep. — "
                if country == "Congo (Dem. Rep.)"
                else f"{country} ("
            )
            dropdown_signatures = {
                signature(zone_id)
                for label, zone_id in COUNTRY_TIME_ZONES
                if label.startswith(prefix)
            }
            self.assertEqual(dropdown_signatures, all_signatures, country)

        self.assertEqual(len(LOCATIONS), 87)

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

    def test_rows_use_one_deterministic_hard_coded_representative(self):
        at_utc = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
        rows = {row.offset: row for row in snapshots(at_utc)}
        self.assertEqual(rows[0].locations[0].country, "Ghana")
        self.assertEqual(rows[1].locations[0].country, "United Kingdom")
        self.assertEqual(rows[2].locations[0].country, "South Africa")
        self.assertTrue(all(len(row.locations) <= 1 for row in rows.values()))

    def test_dropdown_labels_include_country_city_and_region(self):
        label = "France — Paris — Europe"
        self.assertEqual(dropdown_label_for_country("France"), label)
        self.assertIn(label, COUNTRY_DROPDOWN_LABELS)
        self.assertEqual(country_for_dropdown_text(label), "France")
        self.assertEqual(country_for_dropdown_text("France"), "France")
        self.assertEqual(region_for_zone("Asia/Tokyo"), "Asia")
        self.assertEqual(region_for_zone("America/New_York"), "Americas")

    def test_date_rollover_is_visible(self):
        at_utc = datetime(2026, 1, 1, 18, 30, tzinfo=timezone.utc)
        plus_twelve = next(row for row in snapshots(at_utc) if row.offset == 12)
        self.assertEqual(plus_twelve.local_datetime.date().isoformat(), "2026-01-02")
        self.assertEqual(plus_twelve.local_datetime.strftime("%H:%M"), "06:30")


if __name__ == "__main__":
    unittest.main()
