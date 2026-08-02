"""World Time Zones application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from app_window import TimeZoneWindow
from single_instance import SingleInstance
from timezone_data import (
    REQUIRED_TZDATA_VERSION,
    TimeZoneDatabaseError,
    require_time_zone_database,
)


def time_zone_database_error_message(executable: str | None = None) -> str:
    interpreter = executable or sys.executable
    command = (
        f'"{interpreter}" -m pip install tzdata=={REQUIRED_TZDATA_VERSION}'
    )
    return (
        "This Python installation cannot find the IANA time-zone database, "
        "so country and capital clocks cannot be calculated.\n\n"
        "Install the missing dependency with the same Python interpreter that "
        "launches this app:\n\n"
        f"{command}\n\n"
        "Then restart World Time Zones."
    )


def show_time_zone_database_error(executable: str | None = None) -> None:
    QMessageBox.critical(
        None,
        "Time-zone data required",
        time_zone_database_error_message(executable),
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("World Time Zones")
    app.setOrganizationName("Time Zones")

    try:
        require_time_zone_database()
    except TimeZoneDatabaseError:
        show_time_zone_database_error()
        return 1

    instance = SingleInstance()
    if not instance.is_primary:
        instance.notify_existing()
        instance.close()
        return 0

    instance.listen()
    window = TimeZoneWindow()
    instance.activation_requested.connect(window.show_and_activate)
    app.aboutToQuit.connect(instance.close)
    window.show_after_first_layout()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
