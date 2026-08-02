"""Per-user persistence for the selected reference time-zone location."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from timezone_data import OFFSET_ORDER, Offset


MIN_OFFSET = -12
MAX_OFFSET = 14
DEFAULT_REFERENCE_OFFSET = 0
LOCATION_ORDER_WESTERN = "western"
LOCATION_ORDER_EASTERN = "eastern"
DEFAULT_LOCATION_ORDER = LOCATION_ORDER_WESTERN


def default_config_path() -> Path:
    app_data = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(app_data) / "timezone_config.json"


def is_valid_reference_offset(value: object) -> bool:
    return type(value) in {int, float} and value in OFFSET_ORDER


def is_valid_location_order(value: object) -> bool:
    return value in {LOCATION_ORDER_WESTERN, LOCATION_ORDER_EASTERN}


def is_valid_reference_country(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class TimeZoneConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def _load_data(self) -> dict[str, object]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _normalised_data(self) -> dict[str, object]:
        data = self._load_data()
        reference_offset = data.get("reference_offset")
        reference_country = data.get("reference_country")
        location_order = data.get("location_order")
        return {
            "reference_offset": (
                reference_offset
                if is_valid_reference_offset(reference_offset)
                else DEFAULT_REFERENCE_OFFSET
            ),
            "reference_country": (
                reference_country.strip()
                if is_valid_reference_country(reference_country)
                else None
            ),
            "location_order": (
                location_order
                if is_valid_location_order(location_order)
                else DEFAULT_LOCATION_ORDER
            ),
        }

    def load_reference_offset(self) -> Offset:
        return self._normalised_data()["reference_offset"]  # type: ignore[return-value]

    def load_reference_country(self) -> str | None:
        country = self._normalised_data()["reference_country"]
        return country if isinstance(country, str) else None

    def load_location_order(self) -> str:
        return self._normalised_data()["location_order"]  # type: ignore[return-value]

    def _save_data(self, data: dict[str, object]) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError:
            return False
        return True

    def save_reference_offset(self, offset: Offset) -> bool:
        if not is_valid_reference_offset(offset):
            raise ValueError(f"Invalid reference offset: {offset}")
        data = self._normalised_data()
        data["reference_offset"] = offset
        data["reference_country"] = None
        return self._save_data(data)

    def save_reference(self, offset: Offset, country: str) -> bool:
        if not is_valid_reference_offset(offset):
            raise ValueError(f"Invalid reference offset: {offset}")
        if not is_valid_reference_country(country):
            raise ValueError("Reference country must not be blank")
        data = self._normalised_data()
        data["reference_offset"] = offset
        data["reference_country"] = country.strip()
        return self._save_data(data)

    def save_location_order(self, location_order: str) -> bool:
        if not is_valid_location_order(location_order):
            raise ValueError(f"Invalid location order: {location_order}")
        data = self._normalised_data()
        data["location_order"] = location_order
        return self._save_data(data)
