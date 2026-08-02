"""Per-user persistence for the selected reference time-zone location."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from timezone_data import OFFSET_ORDER, Offset


MIN_OFFSET = -12
MAX_OFFSET = 14
DEFAULT_REFERENCE_OFFSET = 0


def default_config_path() -> Path:
    app_data = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(app_data) / "timezone_config.json"


def is_valid_reference_offset(value: object) -> bool:
    return type(value) in {int, float} and value in OFFSET_ORDER


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
        normalised_reference_country = (
            reference_country.strip()
            if is_valid_reference_country(reference_country)
            else None
        )
        return {
            "reference_offset": (
                reference_offset
                if is_valid_reference_offset(reference_offset)
                else DEFAULT_REFERENCE_OFFSET
            ),
            "reference_country": normalised_reference_country,
        }

    def load_reference_offset(self) -> Offset:
        return self._normalised_data()["reference_offset"]  # type: ignore[return-value]

    def load_reference_country(self) -> str | None:
        country = self._normalised_data()["reference_country"]
        return country if isinstance(country, str) else None

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
        country_name = country.strip()
        data["reference_country"] = country_name
        return self._save_data(data)
