import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation, QPoint, Qt
from PySide6.QtTest import QTest
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
from timezone_data import (
    COUNTRIES,
    Location,
    OFFSET_ORDER,
    TimeZoneSnapshot,
    format_gmt_offset,
)
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
                row.hemisphere_label,
                row.time_label,
            ):
                self.assertEqual(label.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(row.hemisphere_label.objectName(), "hemisphereLabel")
            self.assertEqual(window.minimumSize().height(), 500)
            self.assertEqual(window.height(), 800)
            for offset, item in window._items.items():
                self.assertEqual(item.sizeHint().height(), 90)
                hemisphere = window._rows[offset].hemisphere_label
                expected = (
                    "Western hemisphere"
                    if offset < 0
                    else "Eastern hemisphere" if offset > 0 else ""
                )
                self.assertEqual(hemisphere.text(), expected)
                self.assertEqual(hemisphere.isVisible(), bool(expected))
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
            western_row = window._rows[-11]
            self.assertLess(
                western_row.local_zone_label.geometry().bottom(),
                western_row.hemisphere_label.geometry().top(),
            )
            eastern_row = window._rows[11]
            self.assertLess(
                eastern_row.offset_label.geometry().bottom(),
                eastern_row.hemisphere_label.geometry().top(),
            )
            for tagged_row in (western_row, eastern_row):
                self.assertLessEqual(
                    tagged_row.hemisphere_label.geometry().bottom(),
                    tagged_row.offset_slot.rect().bottom(),
                )
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
            self.assertIs(window._highlighted_row, window._rows[-6])
            self.assertTrue(window._rows[-6].property("searchHighlight"))
            self.assertTrue(window._rows[-6]._search_glow.isEnabled())
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
            window.list_widget.scrollToItem(
                window._items[-12],
                QListWidget.ScrollHint.PositionAtTop,
            )
            window.findChild(QPushButton, "resetButton").click()
            self.assertEqual(window.reference_offset, 0)
            self.assertEqual(TimeZoneConfig(self.config_path).load_reference_offset(), 0)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(),
                "Portugal (Mainland)",
            )
            search = window.findChild(QComboBox, "countrySearch")
            self.assertEqual(
                search.currentText(),
                window._gmt_country(datetime.now(timezone.utc)),
            )
            gmt_row = window._rows[0]
            self.assertIs(window._highlighted_row, gmt_row)
            self.assertTrue(gmt_row.property("searchHighlight"))
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Running
            )
            window.findChild(QPushButton, "resetButton").click()
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Running
            )
            QTest.qWait(gmt_row._search_flash.duration() + 200)
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Stopped
            )
            self.assertEqual(gmt_row._search_glow.blurRadius(), 16)
            self.assertTrue(gmt_row._search_glow.isEnabled())
            gmt_rect = window.list_widget.visualItemRect(window._items[0])
            viewport_center = window.list_widget.viewport().rect().center().y()
            self.assertLessEqual(
                abs(gmt_rect.center().y() - viewport_center),
                gmt_rect.height(),
            )
        finally:
            window._timer.stop()
            window.close()

    def test_default_reference_is_saved_selected_highlighted_and_centred(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            config = TimeZoneConfig(self.config_path)
            self.assertEqual(window.reference_offset, 0)
            self.assertEqual(window.reference_country, "Portugal (Mainland)")
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "Portugal (Mainland)",
            )
            self.assertEqual(config.load_reference_offset(), 0)
            self.assertEqual(
                config.load_reference_country(), "Portugal (Mainland)"
            )
            self.assertIs(window._highlighted_row, window._rows[0])
            gmt_rect = window.list_widget.visualItemRect(window._items[0])
            self.assertLessEqual(
                abs(
                    gmt_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                gmt_rect.height(),
            )
        finally:
            window._timer.stop()
            window.close()

    def test_saved_country_restores_exactly_and_controls_dst_offset(self):
        config = TimeZoneConfig(self.config_path)
        config.save_reference(-7, "United States (Arizona)")
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            self.assertEqual(window.reference_offset, -7)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "United States (Arizona)",
            )
            reference_rect = window.list_widget.visualItemRect(window._items[-7])
            self.assertLessEqual(
                abs(
                    reference_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                reference_rect.height(),
            )

            window.reference_offset = -5
            window.reference_country = "United States (Eastern)"
            summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
            window._restore_reference(summer)
            self.app.processEvents()
            self.assertEqual(window.reference_offset, -4)
            self.assertEqual(config.load_reference_offset(), -4)
            self.assertEqual(
                config.load_reference_country(), "United States (Eastern)"
            )

            window.reference_offset = 0
            window.reference_country = "Portugal (Mainland)"
            window._restore_reference(summer)
            self.assertEqual(window.reference_offset, 0)
            self.assertEqual(config.load_reference_offset(), 0)
        finally:
            window._timer.stop()
            window.close()

    def test_legacy_offset_only_reference_is_migrated_to_a_country(self):
        TimeZoneConfig(self.config_path).save_reference_offset(5.5)
        self.assertIsNone(
            TimeZoneConfig(self.config_path).load_reference_country()
        )
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            country = window.title_bar.country_search.currentText()
            self.assertTrue(country)
            self.assertEqual(window.reference_offset, 5.5)
            self.assertEqual(window.reference_country, country)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), country
            )
        finally:
            window._timer.stop()
            window.close()

    def test_removed_saved_country_falls_back_to_the_saved_offset(self):
        config = TimeZoneConfig(self.config_path)
        config.save_reference(5.5, "Removed Country")
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            country = window.title_bar.country_search.currentText()
            self.assertNotEqual(country, "Removed Country")
            self.assertTrue(country)
            self.assertEqual(window.reference_offset, 5.5)
            self.assertEqual(window.reference_country, country)
            self.assertEqual(config.load_reference_country(), country)
        finally:
            window._timer.stop()
            window.close()

    def test_gmt_reset_country_is_always_portugal(self):
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        self.assertEqual(TimeZoneWindow._gmt_country(winter), "Portugal (Mainland)")
        self.assertEqual(TimeZoneWindow._gmt_country(summer), "Portugal (Mainland)")

    def test_header_arrows_control_and_persist_location_order(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            western = window.findChild(QPushButton, "westernOrderButton")
            eastern = window.findChild(QPushButton, "easternOrderButton")
            globe = next(
                label
                for label in window.findChildren(QLabel, "columnHeader")
                if label.toolTip() == "Country / capital or centre"
            )
            self.assertEqual(western.text(), "<")
            self.assertEqual(eastern.text(), ">")
            self.assertEqual(western.toolTip(), "Show Western locations first")
            self.assertEqual(eastern.toolTip(), "Show Eastern locations first")
            self.assertIs(globe.parentWidget(), western.parentWidget())
            self.assertIs(globe.parentWidget(), eastern.parentWidget())
            self.assertLess(western.geometry().right(), globe.geometry().left())
            self.assertLess(globe.geometry().right(), eastern.geometry().left())
            self.assertEqual(western.size(), eastern.size())
            self.assertEqual(western.size().width(), 26)
            self.assertEqual(western.size().height(), 26)
            self.assertEqual(
                western.geometry().center().y(), eastern.geometry().center().y()
            )
            self.assertLessEqual(
                abs(
                    western.geometry().center().y()
                    - globe.geometry().center().y()
                ),
                1,
            )
            self.assertIn("padding: 0", APP_STYLE)
            self.assertIn("text-align: center", APP_STYLE)
            self.assertIn("background: #1b2b3a", APP_STYLE)
            self.assertIn("border-color: #35506b", APP_STYLE)
            self.assertTrue(western.isChecked())
            self.assertFalse(eastern.isChecked())

            eastern.click()
            self.assertEqual(window.location_order, LOCATION_ORDER_EASTERN)
            self.assertFalse(western.isChecked())
            self.assertTrue(eastern.isChecked())
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_location_order(),
                LOCATION_ORDER_EASTERN,
            )

            western.click()
            self.assertEqual(window.location_order, LOCATION_ORDER_WESTERN)
            self.assertTrue(western.isChecked())
            self.assertFalse(eastern.isChecked())
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_location_order(),
                LOCATION_ORDER_WESTERN,
            )
        finally:
            window._timer.stop()
            window.close()

    def test_row_context_menu_sets_reference_only(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            self.assertEqual(
                window.list_widget.contextMenuPolicy(),
                Qt.ContextMenuPolicy.CustomContextMenu,
            )
            menu = window._build_reference_menu(window._rows[-5])
            self.assertEqual(len(menu.actions()), 1)
            self.assertEqual(
                menu.actions()[0].text(), "Set GMT-5 as my reference"
            )
            self.assertEqual(
                window.reference_action_text(5.5),
                "Set GMT+5:30 as my reference",
            )
            expected_country = window._country_for_offset(
                -5, datetime.now(timezone.utc)
            )
            menu.actions()[0].trigger()
            self.assertEqual(window.reference_offset, -5)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_offset(), -5
            )
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(),
                expected_country,
            )
            self.assertIs(window._highlighted_row, window._rows[-5])
            self.assertTrue(window._rows[-5].property("searchHighlight"))
            self.assertEqual(
                window.title_bar.country_search.currentText(), expected_country
            )
            self.app.processEvents()
            reference_rect = window.list_widget.visualItemRect(window._items[-5])
            self.assertLessEqual(
                abs(
                    reference_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                reference_rect.height(),
            )

            with patch.object(window, "_build_reference_menu") as build_menu:
                window._show_reference_menu(QPoint(-1, -1))
                build_menu.assert_not_called()
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
            search.activated.emit(search.findText("Japan"))
            self.app.processEvents()
            row = window._rows[9]
            self.assertEqual(window.reference_offset, 9)
            self.assertEqual(search.currentText(), "Japan")
            self.assertEqual(TimeZoneConfig(self.config_path).load_reference_offset(), 9)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), "Japan"
            )
            self.assertIs(window._highlighted_row, row)
            self.assertTrue(row.property("searchHighlight"))
            self.assertTrue(row.graphicsEffect().isEnabled())
            reference_rect = window.list_widget.visualItemRect(window._items[9])
            self.assertLessEqual(
                abs(
                    reference_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                reference_rect.height(),
            )
            self.assertEqual(search.toolTip(), "Search for a country")
            self.assertEqual(search.count(), len(COUNTRIES))
            self.assertGreaterEqual(
                search.view().minimumWidth(),
                search.fontMetrics().horizontalAdvance(max(
                    (search.itemText(index) for index in range(search.count())),
                    key=len,
                )),
            )
            search.setEditText("India")
            search.lineEdit().returnPressed.emit()
            self.assertEqual(window.reference_offset, 5.5)
            self.assertEqual(search.currentText(), "India")
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_offset(), 5.5
            )
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), "India"
            )
            self.assertIs(window._highlighted_row, window._rows[5.5])
            self.assertFalse(row.property("searchHighlight"))
            mountain_index = search.findText("United States (Mountain)")
            self.assertGreaterEqual(mountain_index, 0)
            search.activated.emit(mountain_index)
            self.assertEqual(search.currentText(), "United States (Mountain)")
            mountain_offset = window.reference_offset
            window.search_country("")
            window.search_country("Not a country")
            self.assertEqual(window.reference_offset, mountain_offset)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_offset(),
                mountain_offset,
            )
        finally:
            window._timer.stop()
            window.close()

    def test_manual_reference_prefers_visible_and_multizone_countries(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
            window.refresh_times(winter)
            window.set_reference_offset(13.75, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "New Zealand (Chatham Islands)",
            )
            window.set_reference_offset(-9.5, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "French Polynesia (Marquesas Islands)",
            )
            window.set_reference_offset(3, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "Russia (Moscow)",
            )

            mountain_row = window._rows[-7]
            mountain_row.update_snapshot(
                TimeZoneSnapshot(
                    offset=-7,
                    local_datetime=winter,
                    locations=(
                        Location(
                            "United States (Mountain)",
                            "Denver",
                            "America/Denver",
                        ),
                    ),
                    abbreviations=("MST",),
                )
            )
            window.set_reference_offset(-7, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "United States (Mountain)",
            )

            window._rows[8.75].locations = ()
            window.set_reference_offset(8.75, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentText(), "Australia (Eucla)"
            )

            summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
            window._rows[-3.5].locations = ()
            window.set_reference_offset(-3.5, at_utc=summer)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "Canada (Newfoundland)",
            )
            window._rows[13.75].locations = ()
            window.set_reference_offset(13.75, at_utc=summer)
            self.assertEqual(
                window.title_bar.country_search.currentText(),
                "New Zealand (Chatham Islands)",
            )
        finally:
            window._timer.stop()
            window.close()

    def test_russian_regions_select_persist_and_restore_existing_rows(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        selections = (
            ("Russia (Kaliningrad)", 2),
            ("Russia (Moscow)", 3),
            ("Russia (Vladivostok)", 10),
            ("Russia (Kamchatka)", 12),
        )
        try:
            window.show()
            self.app.processEvents()
            search = window.title_bar.country_search
            for country, offset in selections:
                country_index = search.findText(country)
                self.assertGreaterEqual(country_index, 0)
                search.activated.emit(country_index)
                self.app.processEvents()
                self.assertEqual(window.reference_offset, offset)
                self.assertEqual(search.currentText(), country)
                self.assertIs(window._highlighted_row, window._rows[offset])
                reference_rect = window.list_widget.visualItemRect(
                    window._items[offset]
                )
                self.assertLessEqual(
                    abs(
                        reference_rect.center().y()
                        - window.list_widget.viewport().rect().center().y()
                    ),
                    reference_rect.height(),
                )
                config = TimeZoneConfig(self.config_path)
                self.assertEqual(config.load_reference_offset(), offset)
                self.assertEqual(config.load_reference_country(), country)
        finally:
            window._timer.stop()
            window.close()

        restored = TimeZoneWindow(
            enable_tray=False, config_path=self.config_path
        )
        try:
            self.assertEqual(restored.reference_offset, 12)
            self.assertEqual(
                restored.title_bar.country_search.currentText(),
                "Russia (Kamchatka)",
            )
        finally:
            restored._timer.stop()
            restored.close()

    def test_dropdown_only_multizone_regions_use_existing_rows(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        selections = (
            ("Ecuador (Galápagos Islands)", -6),
            ("Australia (Western Australia)", 8),
            ("Indonesia (Eastern)", 9),
            ("Papua New Guinea (Bougainville)", 11),
        )
        try:
            window.show()
            self.app.processEvents()
            search = window.title_bar.country_search
            for country, offset in selections:
                country_index = search.findText(country)
                self.assertGreaterEqual(country_index, 0)
                search.activated.emit(country_index)
                self.app.processEvents()
                self.assertEqual(window.reference_offset, offset)
                self.assertEqual(search.currentText(), country)
                self.assertIs(window._highlighted_row, window._rows[offset])
                reference_rect = window.list_widget.visualItemRect(
                    window._items[offset]
                )
                self.assertLessEqual(
                    abs(
                        reference_rect.center().y()
                        - window.list_widget.viewport().rect().center().y()
                    ),
                    reference_rect.height(),
                )
                config = TimeZoneConfig(self.config_path)
                self.assertEqual(config.load_reference_offset(), offset)
                self.assertEqual(config.load_reference_country(), country)

            at_utc = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
            card_mappings = (
                (-6, Location("Mexico", "Mexico City", "America/Mexico_City"),
                 "Mexico (Central)"),
                (-3, Location("Brazil", "Brasília", "America/Sao_Paulo"),
                 "Brazil (Brasília Time)"),
                (7, Location("Indonesia", "Jakarta", "Asia/Jakarta"),
                 "Indonesia (Western)"),
                (8, Location("China", "Beijing", "Asia/Shanghai"),
                 "China (Beijing Time)"),
                (10, Location("Papua New Guinea", "Port Moresby",
                              "Pacific/Port_Moresby"),
                 "Papua New Guinea (Mainland)"),
            )
            for offset, location, expected_country in card_mappings:
                window._rows[offset].locations = (location,)
                window.set_reference_offset(offset, at_utc=at_utc)
                self.assertEqual(search.currentText(), expected_country)
        finally:
            window._timer.stop()
            window.close()

        TimeZoneConfig(self.config_path).save_reference(
            11, "Papua New Guinea (Bougainville)"
        )
        restored = TimeZoneWindow(
            enable_tray=False, config_path=self.config_path
        )
        try:
            self.assertEqual(restored.reference_offset, 11)
            self.assertEqual(
                restored.title_bar.country_search.currentText(),
                "Papua New Guinea (Bougainville)",
            )
        finally:
            restored._timer.stop()
            restored.close()

    def test_location_order_controls_visible_country_preference(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            summer = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
            window.set_location_order(LOCATION_ORDER_WESTERN)
            window.refresh_times(summer)
            self.assertEqual(
                window._country_for_offset(-8, summer), "United States (Alaska)"
            )

            window.set_location_order(LOCATION_ORDER_EASTERN)
            window.refresh_times(summer)
            self.assertEqual(window._country_for_offset(-8, summer), "Pitcairn")
        finally:
            window._timer.stop()
            window.close()

    def test_redundant_numeric_zone_labels_are_removed(self):
        self.assertEqual(TimeZoneRow.local_zone_text(("+11",), 11), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("GMT", "+00"), 0), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("PKT", "+05"), 5), "PKT")
        self.assertEqual(TimeZoneRow.local_zone_text(("SST", "-11"), -11), "SST")

    def test_inactive_chatham_dst_row_explains_switchover(self):
        row = TimeZoneRow(13.75)
        row.update_snapshot(
            TimeZoneSnapshot(
                offset=13.75,
                local_datetime=datetime(2026, 8, 3, tzinfo=timezone.utc),
                locations=(),
                abbreviations=(),
            )
        )
        self.assertEqual(
            row.location_cells[0].country_label.text(),
            "No major country or capital represented "
            "(this will change during the DST switchover)",
        )

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
            self.assertLessEqual(
                max(cell.width() for cell in visible)
                - min(cell.width() for cell in visible),
                1,
            )
            three_column_centres = tuple(
                cell.geometry().center().x() for cell in visible
            )

            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=locations[:2],
                    abbreviations=("GMT",),
                )
            )
            self.app.processEvents()
            visible = [cell for cell in row.location_cells if not cell.isHidden()]
            self.assertEqual(len(visible), 2)
            for actual, expected in zip(
                (cell.geometry().center().x() for cell in visible),
                (three_column_centres[0], three_column_centres[2]),
            ):
                self.assertAlmostEqual(actual, expected, delta=1)

            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=locations[:1],
                    abbreviations=("GMT",),
                )
            )
            self.app.processEvents()
            visible = [cell for cell in row.location_cells if not cell.isHidden()]
            self.assertEqual(len(visible), 1)
            self.assertAlmostEqual(
                visible[0].geometry().center().x(),
                three_column_centres[0],
                delta=1,
            )

            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=(),
                    abbreviations=("GMT",),
                )
            )
            self.app.processEvents()
            fallback = row.location_cells[0]
            self.assertEqual(
                fallback.geometry().center().x(),
                row.locations_slot.rect().center().x(),
            )
            self.assertGreaterEqual(
                fallback.width(), row.locations_slot.width() - 1
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

    def test_tray_click_restores_window_and_uses_dark_menu(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window._create_tray()
            window.show()
            self.app.processEvents()

            window.toggle_visibility()
            self.assertFalse(window.isVisible())
            self.assertEqual(window._show_action.text(), "Show")

            window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            self.assertTrue(window.isVisible())
            self.assertEqual(window._show_action.text(), "Hide")

            window.showMinimized()
            self.app.processEvents()
            window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            self.assertTrue(window.isVisible())
            self.assertFalse(window.isMinimized())

            window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            self.assertTrue(window.isVisible())
            window._tray_activated(QSystemTrayIcon.ActivationReason.Context)
            self.assertTrue(window.isVisible())

            window.toggle_visibility()
            self.assertFalse(window.isVisible())
            window._tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
            self.assertTrue(window.isVisible())

            window._show_action.trigger()
            self.assertFalse(window.isVisible())
            self.assertEqual(window._show_action.text(), "Show")
            window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            self.assertTrue(window.isVisible())

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
