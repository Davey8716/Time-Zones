import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
)

from app_window import (
    APP_STYLE,
    EXE_BUILDER_TRAY_ICON_ENV_VAR,
    resolve_build_icon,
    TimeZoneRow,
    TimeZoneWindow,
)
from timezone_data import Location, OFFSET_ORDER, TimeZoneSnapshot, format_gmt_offset
from timezone_config import (
    LOCATION_ORDER_EASTERN,
    LOCATION_ORDER_WESTERN,
    TimeZoneConfig,
)


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "timezone_config.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_window_builds_all_rows_and_refreshes(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            self.assertEqual(window.list_widget.count(), len(OFFSET_ORDER))
            self.assertEqual(tuple(window._rows), OFFSET_ORDER)
            self.assertEqual(
                window._rows[0].offset_label.objectName(), "referenceOffsetLabel"
            )
            self.assertEqual(
                window._rows[0].time_label.objectName(), "referenceTimeLabel"
            )
            self.assertEqual(
                window._rows[-1].offset_label.objectName(), "pastOffsetLabel"
            )
            self.assertEqual(window._rows[-1].time_label.objectName(), "pastTimeLabel")
            self.assertEqual(
                window._rows[1].offset_label.objectName(), "futureOffsetLabel"
            )
            self.assertEqual(window._rows[1].time_label.objectName(), "futureTimeLabel")
            gmt_item = window.list_widget.item(OFFSET_ORDER.index(0))
            gmt_rect = window.list_widget.visualItemRect(gmt_item)
            viewport_center = window.list_widget.viewport().rect().center().y()
            self.assertLessEqual(
                abs(gmt_rect.center().y() - viewport_center),
                gmt_rect.height(),
            )
            row = window._rows[0]
            for label in (
                row.offset_label,
                row.local_zone_label,
                row.time_label,
            ):
                self.assertEqual(label.alignment(), Qt.AlignmentFlag.AlignCenter)
            for cell in row.location_cells:
                self.assertEqual(
                    cell.country_label.alignment(), Qt.AlignmentFlag.AlignCenter
                )
                self.assertEqual(
                    cell.city_label.alignment(), Qt.AlignmentFlag.AlignCenter
                )
            headers = window.findChildren(QLabel, "columnHeader")
            self.assertEqual(len(headers), 3)
            for header in headers:
                self.assertEqual(header.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(headers[0].text(), "")
            self.assertEqual(headers[0].toolTip(), "Offset and local zone")
            self.assertFalse(headers[0].pixmap().isNull())
            self.assertEqual(headers[1].text(), "")
            self.assertEqual(headers[1].toolTip(), "Country / capital or centre")
            self.assertFalse(headers[1].pixmap().isNull())
            self.assertEqual(headers[2].text(), "")
            self.assertEqual(headers[2].toolTip(), "Local date and time")
            self.assertFalse(headers[2].pixmap().isNull())
            title = window.findChild(QLabel, "appTitle")
            subtitle = window.findChild(QLabel, "appSubtitle")
            title_bar = window.findChild(QFrame, "titleBar")
            self.assertEqual(title.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(subtitle.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(title_bar.height(), 80)
            title_bar_center = title_bar.rect().center().x()
            self.assertLessEqual(
                abs(title.mapTo(title_bar, title.rect().center()).x() - title_bar_center),
                1,
            )
            self.assertLessEqual(
                abs(
                    subtitle.mapTo(title_bar, subtitle.rect().center()).x()
                    - title_bar_center
                ),
                1,
            )
            reset_button = window.findChild(QPushButton, "resetButton")
            self.assertEqual(reset_button.toolTip(), "Reset reference to GMT")
            self.assertIs(reset_button.parentWidget(), headers[0].parentWidget())
            self.assertLess(
                reset_button.geometry().right(), headers[0].geometry().left()
            )
            minimize_button = window.findChild(QPushButton, "windowButton")
            close_button = window.findChild(QPushButton, "closeButton")
            self.assertEqual(minimize_button.size(), close_button.size())
            self.assertEqual(minimize_button.iconSize(), close_button.iconSize())
            window.refresh_times()
            self.assertTrue(window._rows[0].time_label.text())
            self.assertFalse(window.findChildren(QLabel, "zoneLabel"))
            for offset, row in window._rows.items():
                self.assertEqual(row.offset_label.text(), format_gmt_offset(offset))
            self.assertEqual(window._rows[-11].local_zone_label.text(), "SST")
            self.assertEqual(window._rows[11].local_zone_label.text(), "")
            self.assertFalse(window._rows[11].local_zone_label.isVisible())
        finally:
            window._timer.stop()
            window.close()

    def test_reference_changes_persist_and_recolour_rows(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            window.set_reference_offset(-6)
            self.assertEqual(window.reference_offset, -6)
            self.assertEqual(
                window._rows[-6].offset_label.objectName(), "referenceOffsetLabel"
            )
            self.assertEqual(
                window._rows[-6].time_label.objectName(), "referenceTimeLabel"
            )
            self.assertEqual(window._rows[-7].offset_label.objectName(), "pastOffsetLabel")
            self.assertEqual(window._rows[-7].time_label.objectName(), "pastTimeLabel")
            self.assertEqual(window._rows[-5].offset_label.objectName(), "futureOffsetLabel")
            self.assertEqual(window._rows[-5].time_label.objectName(), "futureTimeLabel")
            self.assertEqual(TimeZoneConfig(self.config_path).load_reference_offset(), -6)
            self.assertEqual(
                window.reference_action_text(-6), "Set GMT-6 as my reference"
            )
            menu = window._build_row_context_menu(window._rows[-6])
            actions = {action.text(): action for action in menu.actions() if action.text()}
            self.assertTrue(actions["Show Western locations first"].isChecked())
            self.assertFalse(actions["Show Eastern locations first"].isChecked())
            window.set_location_order(LOCATION_ORDER_EASTERN)
            self.assertEqual(window.location_order, LOCATION_ORDER_EASTERN)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_location_order(),
                LOCATION_ORDER_EASTERN,
            )
            eastern_menu = window._build_row_context_menu(window._rows[-6])
            eastern_actions = {
                action.text(): action
                for action in eastern_menu.actions()
                if action.text()
            }
            self.assertTrue(eastern_actions["Show Eastern locations first"].isChecked())
            item = window._items[-6]
            self.assertIs(window._row_at(window.list_widget.visualItemRect(item).center()), window._rows[-6])
            window.list_widget.scrollToItem(
                window._items[-12],
                QListWidget.ScrollHint.PositionAtTop,
            )
            window.findChild(QPushButton, "resetButton").click()
            self.assertEqual(window.reference_offset, 0)
            self.assertEqual(TimeZoneConfig(self.config_path).load_reference_offset(), 0)
            gmt_rect = window.list_widget.visualItemRect(window._items[0])
            viewport_center = window.list_widget.viewport().rect().center().y()
            self.assertLessEqual(
                abs(gmt_rect.center().y() - viewport_center),
                gmt_rect.height(),
            )
        finally:
            window._timer.stop()
            window.close()

    def test_country_search_centres_and_highlights_matching_offset(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            search = window.findChild(QComboBox, "countrySearch")
            search_label = window.findChild(QLabel, "countrySearchLabel")
            self.assertIsNotNone(search)
            self.assertIsNotNone(search_label)
            self.assertEqual(search_label.text(), "World countries list")
            window.show()
            self.app.processEvents()
            self.assertIs(search_label.parentWidget(), search.parentWidget())
            self.assertLess(search_label.geometry().bottom(), search.geometry().top())
            self.assertGreaterEqual(search_label.geometry().left(), 12)
            self.assertGreaterEqual(search.geometry().left(), 12)
            window.search_country("Japan")
            row = window._rows[9]
            self.assertIs(window._highlighted_row, row)
            self.assertTrue(row.property("searchHighlight"))
            self.assertTrue(row.graphicsEffect().isEnabled())
            self.assertEqual(search.toolTip(), "Search for a country")
            self.assertEqual(search.count(), 249)
            self.assertGreaterEqual(
                search.view().minimumWidth(),
                search.fontMetrics().horizontalAdvance(max(
                    (search.itemText(index) for index in range(search.count())),
                    key=len,
                )),
            )
            window.search_country("India")
            self.assertIs(window._highlighted_row, window._rows[5.5])
            self.assertFalse(row.property("searchHighlight"))
        finally:
            window._timer.stop()
            window.close()

    def test_redundant_numeric_zone_labels_are_removed(self):
        self.assertEqual(TimeZoneRow.local_zone_text(("+11",), 11), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("GMT", "+00"), 0), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("PKT", "+05"), 5), "PKT")
        self.assertEqual(TimeZoneRow.local_zone_text(("SST", "-11"), -11), "SST")

    def test_location_pairs_use_equal_columns_and_preserve_pair_data(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            row = window._rows[0]
            locations = (
                Location("United Kingdom", "London", "Europe/London"),
                Location("Portugal", "Lisbon", "Europe/Lisbon"),
                Location("Ghana", "Accra", "Africa/Accra"),
            )
            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=locations,
                    abbreviations=("GMT",),
                )
            )
            self.app.processEvents()
            visible = [cell for cell in row.location_cells if not cell.isHidden()]
            self.assertEqual(len(visible), 3)
            self.assertEqual(
                [(cell.country_label.text(), cell.city_label.text()) for cell in visible],
                [(location.country, location.city) for location in locations],
            )
            self.assertEqual(visible[0].toolTip(), "United Kingdom — London")
            self.assertLessEqual(max(cell.width() for cell in visible) - min(cell.width() for cell in visible), 1)

            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=locations[:1],
                    abbreviations=("GMT",),
                )
            )
            self.assertEqual(
                len([cell for cell in row.location_cells if not cell.isHidden()]), 1
            )
        finally:
            window._timer.stop()
            window.close()

    def test_tooltips_use_the_dark_theme(self):
        self.assertIn("QToolTip", APP_STYLE)
        self.assertIn("background-color: #1a202a", APP_STYLE)
        self.assertIn("color: #dce5ef", APP_STYLE)

    def test_no_builder_icon_uses_the_standard_window_and_tray_icon(self):
        with patch.dict(os.environ, {EXE_BUILDER_TRAY_ICON_ENV_VAR: ""}):
            fallback_icon = resolve_build_icon()
            window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
            try:
                self.assertFalse(fallback_icon.isNull())
                self.assertEqual(
                    window.windowIcon().pixmap(16, 16).toImage(),
                    fallback_icon.pixmap(16, 16).toImage(),
                )
                window._create_tray()
                self.assertFalse(window._tray.icon().isNull())
                self.assertEqual(
                    window._tray.icon().pixmap(16, 16).toImage(),
                    fallback_icon.pixmap(16, 16).toImage(),
                )
            finally:
                window._timer.stop()
                if window._tray is not None:
                    window._tray.hide()
                window._allow_close = True
                window.close()

    def test_builder_icon_is_used_for_window_and_tray(self):
        icon_path = Path(__file__).parent.parent / "Icons" / "world_clock_icon.ico"
        self.assertTrue(icon_path.is_file())
        with patch.dict(
            os.environ,
            {EXE_BUILDER_TRAY_ICON_ENV_VAR: str(icon_path)},
        ):
            fallback_icon = QApplication.style().standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )
            window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
            try:
                self.assertFalse(window.windowIcon().isNull())
                self.assertNotEqual(
                    window.windowIcon().pixmap(16, 16).toImage(),
                    fallback_icon.pixmap(16, 16).toImage(),
                )
                window._create_tray()
                self.assertFalse(window._tray.icon().isNull())
                self.assertEqual(
                    window._tray.icon().pixmap(16, 16).toImage(),
                    window.windowIcon().pixmap(16, 16).toImage(),
                )
            finally:
                window._timer.stop()
                if window._tray is not None:
                    window._tray.hide()
                window._allow_close = True
                window.close()

    def test_tray_double_click_toggles_visibility_and_uses_dark_menu(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window._create_tray()
            window.show()
            self.app.processEvents()

            window._tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
            self.assertFalse(window.isVisible())
            self.assertEqual(window._show_action.text(), "Show")

            window._tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
            self.assertTrue(window.isVisible())
            self.assertEqual(window._show_action.text(), "Hide")

            menu = window._tray.contextMenu()
            self.assertIsNotNone(menu)
            self.assertIn("QMenu", menu.styleSheet())
            self.assertIn("background: #1a202a", menu.styleSheet())
            self.assertIn("QMenu::separator", menu.styleSheet())
            self.assertEqual(
                [action.text() for action in menu.actions() if action.text()],
                ["Hide", "Exit"],
            )
        finally:
            window._timer.stop()
            if window._tray is not None:
                window._tray.hide()
            window._allow_close = True
            window.close()


if __name__ == "__main__":
    unittest.main()
