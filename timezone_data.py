"""Curated location data and DST-aware time-zone calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Iterable
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


Offset = int | float
OFFSET_ORDER: tuple[Offset, ...] = (
    -12,
    -11,
    -10,
    -9.5,
    -9,
    -8,
    -7,
    -6,
    -5,
    -4,
    -3.5,
    -3,
    -2,
    -1,
    0,
    1,
    2,
    3,
    3.5,
    4,
    4.5,
    5,
    5.5,
    5.75,
    6,
    6.5,
    7,
    8,
    8.75,
    9,
    9.5,
    10,
    10.5,
    11,
    12,
    12.75,
    13,
    13.75,
    14,
)
REQUIRED_TZDATA_VERSION = "2025.2"
LOCATION_ORDER_WESTERN = "western"
LOCATION_ORDER_EASTERN = "eastern"


class TimeZoneDatabaseError(RuntimeError):
    """Raised when no IANA time-zone database is available."""


def time_zone_database_available() -> bool:
    """Return whether this interpreter can resolve an IANA DST-aware zone."""
    try:
        ZoneInfo("Europe/London")
    except ZoneInfoNotFoundError:
        return False
    return True


def require_time_zone_database() -> None:
    if not time_zone_database_available():
        raise TimeZoneDatabaseError(
            "No IANA time-zone database is available to this Python interpreter."
        )


@dataclass(frozen=True, slots=True)
class Location:
    country: str
    city: str
    zone_id: str
    priority: int = 100

    @property
    def display_name(self) -> str:
        return f"{self.country} — {self.city}"


@dataclass(frozen=True, slots=True)
class TimeZoneSnapshot:
    offset: Offset
    local_datetime: datetime
    locations: tuple[Location, ...]
    abbreviations: tuple[str, ...]


# This is intentionally a recognizable selection rather than an exhaustive
# geopolitical database. A larger candidate pool lets rows stay useful as
# daylight-saving changes move cities between offsets.
LOCATIONS: tuple[Location, ...] = (
    Location("US Minor Outlying Islands", "Baker Island (uninhabited)", "Etc/GMT+12", 1),
    Location("American Samoa", "Pago Pago", "Pacific/Pago_Pago", 1),
    Location("Niue", "Alofi", "Pacific/Niue", 2),
    Location("United States (Hawaii)", "Honolulu", "Pacific/Honolulu", 1),
    Location("Cook Islands", "Avarua", "Pacific/Rarotonga", 2),
    Location("French Polynesia", "Papeete", "Pacific/Tahiti", 3),
    Location("Gambier Islands", "Rikitea", "Pacific/Gambier", 1),
    Location("United States (Alaska)", "Juneau", "America/Juneau", 2),
    Location("United States (Pacific)", "Los Angeles", "America/Los_Angeles", 1),
    Location("Canada (Pacific)", "Vancouver", "America/Vancouver", 2),
    Location("Pitcairn Islands", "Adamstown", "Pacific/Pitcairn", 3),
    Location("United States (Mountain)", "Denver", "America/Denver", 1),
    Location("United States (Arizona)", "Phoenix", "America/Phoenix", 2),
    Location("Canada (Alberta)", "Edmonton", "America/Edmonton", 3),
    Location("United States (Central)", "Chicago", "America/Chicago", 1),
    Location("Mexico", "Mexico City", "America/Mexico_City", 2),
    Location("Guatemala", "Guatemala City", "America/Guatemala", 3),
    Location("United States (Eastern)", "Washington, D.C.", "America/New_York", 1),
    Location("Peru", "Lima", "America/Lima", 2),
    Location("Colombia", "Bogotá", "America/Bogota", 3),
    Location("Canada (Atlantic)", "Halifax", "America/Halifax", 1),
    Location("Dominican Republic", "Santo Domingo", "America/Santo_Domingo", 2),
    Location("Venezuela", "Caracas", "America/Caracas", 3),
    Location("Brazil", "Brasília", "America/Sao_Paulo", 1),
    Location("Argentina", "Buenos Aires", "America/Argentina/Buenos_Aires", 2),
    Location("Uruguay", "Montevideo", "America/Montevideo", 3),
    Location("Brazil (Fernando de Noronha)", "Vila dos Remédios", "America/Noronha", 1),
    Location("South Georgia", "King Edward Point", "Atlantic/South_Georgia", 2),
    Location("Cabo Verde", "Praia", "Atlantic/Cape_Verde", 1),
    Location("Portugal (Azores)", "Ponta Delgada", "Atlantic/Azores", 2),
    Location("United Kingdom", "London", "Europe/London", 1),
    Location("Ireland", "Dublin", "Europe/Dublin", 2),
    Location("Ghana", "Accra", "Africa/Accra", 3),
    Location("Nigeria", "Abuja", "Africa/Lagos", 1),
    Location("Tunisia", "Tunis", "Africa/Tunis", 2),
    Location("France", "Paris", "Europe/Paris", 3),
    Location("Germany", "Berlin", "Europe/Berlin", 4),
    Location("South Africa", "Pretoria", "Africa/Johannesburg", 1),
    Location("Mozambique", "Maputo", "Africa/Maputo", 2),
    Location("Greece", "Athens", "Europe/Athens", 3),
    Location("Egypt", "Cairo", "Africa/Cairo", 4),
    Location("Russia", "Moscow", "Europe/Moscow", 1),
    Location("Kenya", "Nairobi", "Africa/Nairobi", 2),
    Location("Saudi Arabia", "Riyadh", "Asia/Riyadh", 3),
    Location("United Arab Emirates", "Abu Dhabi", "Asia/Dubai", 1),
    Location("Oman", "Muscat", "Asia/Muscat", 2),
    Location("Mauritius", "Port Louis", "Indian/Mauritius", 3),
    Location("Pakistan", "Islamabad", "Asia/Karachi", 1),
    Location("Uzbekistan", "Tashkent", "Asia/Tashkent", 2),
    Location("Maldives", "Malé", "Indian/Maldives", 3),
    Location("Bangladesh", "Dhaka", "Asia/Dhaka", 1),
    Location("Bhutan", "Thimphu", "Asia/Thimphu", 2),
    Location("Kyrgyzstan", "Bishkek", "Asia/Bishkek", 3),
    Location("Thailand", "Bangkok", "Asia/Bangkok", 1),
    Location("Indonesia", "Jakarta", "Asia/Jakarta", 2),
    Location("Cambodia", "Phnom Penh", "Asia/Phnom_Penh", 3),
    Location("Singapore", "Singapore", "Asia/Singapore", 1),
    Location("China", "Beijing", "Asia/Shanghai", 2),
    Location("Philippines", "Manila", "Asia/Manila", 3),
    Location("Japan", "Tokyo", "Asia/Tokyo", 1),
    Location("South Korea", "Seoul", "Asia/Seoul", 2),
    Location("Timor-Leste", "Dili", "Asia/Dili", 3),
    Location("Australia (Queensland)", "Brisbane", "Australia/Brisbane", 1),
    Location("Papua New Guinea", "Port Moresby", "Pacific/Port_Moresby", 2),
    Location("Guam", "Hagåtña", "Pacific/Guam", 3),
    Location("New Caledonia", "Nouméa", "Pacific/Noumea", 1),
    Location("Solomon Islands", "Honiara", "Pacific/Guadalcanal", 2),
    Location("Micronesia (Pohnpei)", "Palikir", "Pacific/Pohnpei", 3),
    Location("Fiji", "Suva", "Pacific/Fiji", 1),
    Location("Kiribati (Gilbert Islands)", "South Tarawa", "Pacific/Tarawa", 2),
    Location("New Zealand", "Wellington", "Pacific/Auckland", 3),
)

_COUNTRY_ZONE_OVERRIDES = {
    "AQ": "Antarctica/McMurdo",
    "AR": "America/Argentina/Buenos_Aires",
    "AU": "Australia/Sydney",
    "BR": "America/Sao_Paulo",
    "CA": "America/Toronto",
    "CD": "Africa/Kinshasa",
    "CL": "America/Santiago",
    "CN": "Asia/Shanghai",
    "CY": "Asia/Nicosia",
    "DE": "Europe/Berlin",
    "EC": "America/Guayaquil",
    "ES": "Europe/Madrid",
    "FM": "Pacific/Pohnpei",
    "GL": "America/Nuuk",
    "ID": "Asia/Jakarta",
    "KI": "Pacific/Tarawa",
    "KZ": "Asia/Almaty",
    "MH": "Pacific/Majuro",
    "MN": "Asia/Ulaanbaatar",
    "MX": "America/Mexico_City",
    "MY": "Asia/Kuala_Lumpur",
    "NZ": "Pacific/Auckland",
    "PF": "Pacific/Tahiti",
    "PG": "Pacific/Port_Moresby",
    "PS": "Asia/Hebron",
    "PT": "Europe/Lisbon",
    "RU": "Europe/Moscow",
    "UA": "Europe/Kyiv",
    "UM": "Pacific/Wake",
    "US": "America/New_York",
    "UZ": "Asia/Tashkent",
    "BV": "Europe/Oslo",
    "HM": "Indian/Kerguelen",
}


def _load_country_time_zones() -> list[tuple[str, str]]:
    """Load the complete ISO country list with one representative IANA zone."""
    database = files("tzdata.zoneinfo")
    country_names = {
        code: name
        for code, name in (
            line.split("\t", 1)
            for line in (database / "iso3166.tab").read_text(
                encoding="utf-8"
            ).splitlines()
            if line and not line.startswith("#")
        )
    }
    country_zones: dict[str, str] = {}
    for line in (database / "zone.tab").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        code, _coordinates, zone_id, *_comment = line.split("\t")
        country_zones.setdefault(code, zone_id)
    country_zones.update(_COUNTRY_ZONE_OVERRIDES)
    return sorted(
        (
            (country_name, country_zones[country_code])
            for country_code, country_name in country_names.items()
        ),
        key=lambda item: "".join(
            character
            for character in unicodedata.normalize("NFKD", item[0].casefold())
            if not unicodedata.combining(character)
        ),
    )


COUNTRY_TIME_ZONES: list[tuple[str, str]] = _load_country_time_zones()
COUNTRIES: list[str] = [country for country, _zone_id in COUNTRY_TIME_ZONES]
_COUNTRY_ZONE_BY_NAME = {
    country.casefold(): zone_id for country, zone_id in COUNTRY_TIME_ZONES
}


def time_zone_for_country(country: str) -> str | None:
    return _COUNTRY_ZONE_BY_NAME.get(country.strip().casefold())


def regional_display_rank(location: Location, location_order: str) -> int:
    """Return a location's priority group for the selected geographic ordering."""
    western = location.zone_id.startswith(("America/", "Australia/")) or location.zone_id in {
        "Pacific/Auckland",
        "Pacific/Guam",
        "Pacific/Honolulu",
        "Pacific/Pago_Pago",
        "Pacific/Pitcairn",
    }
    european = location.zone_id.startswith("Europe/") or location.zone_id == "Atlantic/Azores"
    eastern = location.zone_id.startswith(("Asia/", "Indian/", "Pacific/"))

    if location_order == LOCATION_ORDER_WESTERN:
        if european or western:
            return 0
        if eastern:
            return 1
        return 2
    if location_order == LOCATION_ORDER_EASTERN:
        if eastern:
            return 0
        if european or western:
            return 1
        return 2
    raise ValueError(f"Unknown location order: {location_order}")


def format_gmt_offset(offset: Offset) -> str:
    if offset == 0:
        return "GMT"
    total_minutes = round(offset * 60)
    sign = "+" if total_minutes > 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    if minutes == 0:
        return f"GMT{sign}{hours}"
    return f"GMT{sign}{hours}:{minutes:02d}"


def offset_for(location: Location, at_utc: datetime) -> tuple[Offset, str] | None:
    """Return a live supported offset and abbreviation, or None if excluded."""
    if at_utc.tzinfo is None:
        at_utc = at_utc.replace(tzinfo=timezone.utc)
    else:
        at_utc = at_utc.astimezone(timezone.utc)

    try:
        local = at_utc.astimezone(ZoneInfo(location.zone_id))
    except ZoneInfoNotFoundError:
        return None

    delta = local.utcoffset()
    if delta is None:
        return None
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes % 15:
        return None
    offset: Offset = total_minutes / 60
    if offset.is_integer():
        offset = int(offset)
    if offset not in OFFSET_ORDER:
        return None
    return offset, local.tzname() or format_gmt_offset(offset)


def snapshots(
    at_utc: datetime | None = None,
    locations: Iterable[Location] = LOCATIONS,
    max_locations: int = 3,
    location_order: str = LOCATION_ORDER_WESTERN,
) -> tuple[TimeZoneSnapshot, ...]:
    """Create the fixed ordered rows, dynamically regrouping locations by DST."""
    now = at_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    grouped: dict[Offset, list[tuple[Location, str]]] = {
        offset: [] for offset in OFFSET_ORDER
    }
    for location in locations:
        result = offset_for(location, now)
        if result is not None:
            offset, abbreviation = result
            grouped[offset].append((location, abbreviation))

    result_rows: list[TimeZoneSnapshot] = []
    for offset in OFFSET_ORDER:
        selected = sorted(
            grouped[offset],
            key=lambda item: (
                regional_display_rank(item[0], location_order),
                item[0].priority,
                item[0].country,
                item[0].city,
            ),
        )[:max_locations]
        abbreviations = tuple(dict.fromkeys(item[1] for item in selected))
        result_rows.append(
            TimeZoneSnapshot(
                offset=offset,
                local_datetime=now.astimezone(
                    timezone(timedelta(hours=offset), format_gmt_offset(offset))
                ),
                locations=tuple(item[0] for item in selected),
                abbreviations=abbreviations,
            )
        )
    return tuple(result_rows)
