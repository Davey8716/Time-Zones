import os
from datetime import date, datetime, timezone
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
    COUNTRY_DROPDOWN_LABELS,
    Location,
    OFFSET_ORDER,
    TimeZoneSnapshot,
    format_gmt_offset,
    offset_for,
)
from timezone_config import TimeZoneConfig


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "timezone_config.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_first_show_primes_paint_before_single_native_show(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        events = []
        original_show = window.show
        original_render = window.render

        def record_show():
            events.append("show")
            original_show()

        def record_render(*args, **kwargs):
            events.append("render")
            original_render(*args, **kwargs)

        try:
            with (
                patch.object(window, "render", side_effect=record_render),
                patch.object(window, "show", side_effect=record_show),
            ):
                window.show_after_first_layout()
            self.app.processEvents()
            self.assertEqual(events, ["render", "show"])
            self.assertTrue(window.isVisible())
            self.assertFalse(
                window.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            )
        finally:
            window.close()

    def test_row_widgets_have_parents_before_becoming_visible(self):
        row = TimeZoneRow(1)
        try:
            self.assertIs(row.offset_label.parentWidget(), row.offset_slot)
            self.assertIs(row.local_zone_label.parentWidget(), row.offset_slot)
            self.assertIs(row.hemisphere_label.parentWidget(), row.offset_slot)
            self.assertIs(row.time_transition_label.parentWidget(), row.time_slot)
            self.assertFalse(row.hemisphere_label.isVisibleTo(row))
            for cell in row.location_cells:
                self.assertIs(cell.parentWidget(), row.locations_slot)
        finally:
            row.close()

    def test_window_builds_all_rows_and_refreshes(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            self.assertEqual(window.list_widget.count(), len(OFFSET_ORDER))
            self.assertEqual(tuple(window._rows), OFFSET_ORDER)
            reference_offset = window.reference_offset
            reference_index = OFFSET_ORDER.index(reference_offset)
            past_offset = OFFSET_ORDER[reference_index - 1]
            future_offset = OFFSET_ORDER[reference_index + 1]
            self.assertEqual(
                window._rows[reference_offset].offset_label.objectName(),
                "referenceOffsetLabel",
            )
            self.assertEqual(
                window._rows[reference_offset].time_label.objectName(),
                "referenceTimeLabel",
            )
            self.assertEqual(
                window._rows[past_offset].offset_label.objectName(), "pastOffsetLabel"
            )
            self.assertEqual(
                window._rows[past_offset].time_label.objectName(), "pastTimeLabel"
            )
            self.assertEqual(
                window._rows[future_offset].offset_label.objectName(),
                "futureOffsetLabel",
            )
            self.assertEqual(
                window._rows[future_offset].time_label.objectName(),
                "futureTimeLabel",
            )
            reference_item = window.list_widget.item(reference_index)
            reference_rect = window.list_widget.visualItemRect(reference_item)
            viewport_center = window.list_widget.viewport().rect().center().y()
            self.assertLessEqual(
                abs(reference_rect.center().y() - viewport_center),
                reference_rect.height(),
            )
            row = window._rows[reference_offset]
            for label in (
                row.offset_label,
                row.local_zone_label,
                row.hemisphere_label,
                row.time_label,
            ):
                self.assertEqual(label.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(row.hemisphere_label.objectName(), "hemisphereLabel")
            self.assertEqual(window.minimumSize().height(), 500)
            self.assertEqual(window.width(), 1000)
            self.assertEqual(window.height(), 800)
            self.assertEqual(row.time_slot.width(), 215)
            time_center = row.time_label.mapTo(
                row, row.time_label.rect().center()
            ).y()
            offset_center = row.offset_label.mapTo(
                row, row.offset_label.rect().center()
            ).y()
            self.assertLessEqual(abs(time_center - offset_center), 1)
            self.assertGreater(
                row.period_label.mapTo(row, row.period_label.rect().topLeft()).y(),
                row.time_label.mapTo(row, row.time_label.rect().bottomLeft()).y(),
            )
            self.assertEqual(row.period_label.objectName(), "timePeriodLabel")
            self.assertEqual(row.period_label.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(
                row.time_transition_label.objectName(), "timeTransitionLabel"
            )
            self.assertEqual(
                row.time_transition_label.alignment(), Qt.AlignmentFlag.AlignCenter
            )
            for offset, item in window._items.items():
                self.assertEqual(item.sizeHint().height(), 90)
                hemisphere = window._rows[offset].hemisphere_label
                self.assertEqual(hemisphere.text(), "")
                self.assertFalse(hemisphere.isVisible())
                location_cell = window._rows[offset].location_cells[0]
                if not location_cell.isHidden():
                    self.assertTrue(location_cell.country_label.text())
                    self.assertTrue(location_cell.city_label.text())
                    self.assertTrue(location_cell.region_label.text())
                    self.assertTrue(window._rows[offset].time_transition_label.text())
            for cell in row.location_cells:
                self.assertEqual(
                    cell.country_label.alignment(), Qt.AlignmentFlag.AlignCenter
                )
                self.assertEqual(
                    cell.city_label.alignment(), Qt.AlignmentFlag.AlignCenter
                )
                self.assertEqual(
                    cell.region_label.alignment(), Qt.AlignmentFlag.AlignCenter
                )
            headers = window.findChildren(QLabel, "columnHeader")
            self.assertEqual(len(headers), 3)
            for header in headers:
                self.assertEqual(header.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertEqual(headers[0].text(), "")
            self.assertEqual(headers[0].toolTip(), "Offset and local zone")
            self.assertFalse(headers[0].pixmap().isNull())
            self.assertEqual(headers[1].text(), "")
            self.assertEqual(
                headers[1].toolTip(),
                "Country / capital / region",
            )
            self.assertFalse(headers[1].pixmap().isNull())
            self.assertEqual(headers[2].text(), "")
            self.assertEqual(
                headers[2].toolTip(), "Local date, time, and clock change"
            )
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
            self.assertEqual(reset_button.toolTip(), "Reset reference")
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
            for row in window._rows.values():
                self.assertEqual(row.hemisphere_label.text(), "")
                self.assertFalse(row.hemisphere_label.isVisible())
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
            self.assertTrue(window._rows[-6].offset_slot.property("searchHighlight"))
            self.assertTrue(window._rows[-6].time_slot.property("searchHighlight"))
            self.assertIsNone(window._rows[-6].locations_slot.graphicsEffect())
            self.assertTrue(
                all(glow.isEnabled() for glow in window._rows[-6]._search_glows)
            )
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
            search = window.findChild(QComboBox, "countrySearch")
            self.assertEqual(window.reference_country, "Ghana")
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), "Ghana"
            )
            self.assertEqual(search.currentData(), "Ghana")
            self.assertEqual(search.currentText(), "Ghana — Accra — Africa")
            gmt_row = window._rows[0]
            self.assertIs(window._highlighted_row, gmt_row)
            self.assertTrue(gmt_row.property("searchHighlight"))
            self.assertTrue(gmt_row.offset_slot.property("searchHighlight"))
            self.assertTrue(gmt_row.time_slot.property("searchHighlight"))
            self.assertIsNone(gmt_row.locations_slot.graphicsEffect())
            self.assertFalse(gmt_row.location_cells[0].isHidden())
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Running
            )
            window.findChild(QPushButton, "resetButton").click()
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Running
            )
            QTest.qWait(gmt_row._search_flash.duration() + 700)
            self.assertEqual(
                gmt_row._search_flash.state(), QAbstractAnimation.State.Stopped
            )
            self.assertTrue(
                all(glow.blurRadius() == 16 for glow in gmt_row._search_glows)
            )
            self.assertTrue(all(glow.isEnabled() for glow in gmt_row._search_glows))
            gmt_rect = window.list_widget.visualItemRect(window._items[0])
            viewport_center = window.list_widget.viewport().rect().center().y()
            self.assertLessEqual(
                abs(gmt_rect.center().y() - viewport_center),
                gmt_rect.height(),
            )
        finally:
            window._timer.stop()
            window.close()

    def test_default_reference_is_fixed_utc_with_hard_coded_row_content(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            config = TimeZoneConfig(self.config_path)
            self.assertEqual(window.reference_offset, 0)
            self.assertIsNone(window.reference_country)
            self.assertEqual(window.title_bar.country_search.currentText(), "")
            self.assertEqual(config.load_reference_offset(), 0)
            self.assertIsNone(config.load_reference_country())
            self.assertGreater(
                sum(
                    not cell.isHidden()
                    for row in window._rows.values()
                    for cell in row.location_cells
                ),
                30,
            )
            self.assertIs(window._highlighted_row, window._rows[0])
            reference_rect = window.list_widget.visualItemRect(
                window._items[0]
            )
            self.assertLessEqual(
                abs(
                    reference_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                reference_rect.height(),
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
                "United States (Arizona) — Phoenix — Americas",
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
            self.assertEqual(window.reference_offset, 1)
            self.assertEqual(config.load_reference_offset(), 1)
        finally:
            window._timer.stop()
            window.close()

    def test_legacy_offset_only_reference_stays_blank_and_fixed(self):
        TimeZoneConfig(self.config_path).save_reference_offset(5.5)
        self.assertIsNone(
            TimeZoneConfig(self.config_path).load_reference_country()
        )
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            country = window.title_bar.country_search.currentText()
            self.assertEqual(country, "")
            self.assertEqual(window.reference_offset, 5.5)
            self.assertIsNone(window.reference_country)
            self.assertIsNone(
                TimeZoneConfig(self.config_path).load_reference_country()
            )
            self.assertEqual(
                window._rows[5.5].location_cells[0].country_label.text(), "India"
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
            self.assertEqual(country, "")
            self.assertEqual(window.reference_offset, 5.5)
            self.assertIsNone(window.reference_country)
            self.assertIsNone(config.load_reference_country())
        finally:
            window._timer.stop()
            window.close()

    def test_reference_country_offset_updates_during_refresh(self):
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        selections = (
            (None, "United States (Eastern)"),
            ("United States (Eastern)", "United States (Eastern)"),
        )

        for country, expected_country in selections:
            with self.subTest(country=country):
                config_path = self.config_path.with_name(
                    f"reference-{country or 'manual'}.json"
                )
                window = TimeZoneWindow(enable_tray=False, config_path=config_path)
                try:
                    window.refresh_times(winter)
                    window.set_reference_offset(-5, country=country, at_utc=winter)
                    window.refresh_times(winter)
                    self.assertEqual(window.reference_country, expected_country)
                    winter_cell = window._rows[-5].location_cells[0]
                    self.assertFalse(winter_cell.isHidden())
                    self.assertEqual(
                        winter_cell.country_label.text(), expected_country
                    )
                    self.assertEqual(
                        winter_cell.city_label.text(), "Washington, D.C."
                    )
                    self.assertEqual(
                        window._rows[-5].time_transition_label.text(),
                        "Moves to UTC-4 on 08 Mar",
                    )

                    window.refresh_times(summer)

                    self.assertEqual(window.reference_offset, -4)
                    self.assertEqual(window.reference_country, expected_country)
                    config = TimeZoneConfig(config_path)
                    self.assertEqual(config.load_reference_offset(), -4)
                    self.assertEqual(
                        config.load_reference_country(), expected_country
                    )
                    self.assertEqual(
                        window.title_bar.country_search.currentText(),
                        "United States (Eastern) — Washington, D.C. — Americas",
                    )
                    self.assertEqual(
                        window._rows[-5].location_cells[0].country_label.text(),
                        "United States (Central)",
                    )
                    summer_cell = window._rows[-4].location_cells[0]
                    self.assertFalse(summer_cell.isHidden())
                    self.assertEqual(
                        summer_cell.country_label.text(), expected_country
                    )
                    self.assertEqual(
                        window._rows[-4].time_transition_label.text(),
                        "Moves to UTC-5 on 01 Nov",
                    )
                finally:
                    window._timer.stop()
                    window.close()

    def test_country_header_has_no_location_order_arrows(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            window.show()
            self.app.processEvents()
            western = window.findChild(QPushButton, "westernOrderButton")
            eastern = window.findChild(QPushButton, "easternOrderButton")
            globe = next(
                label
                for label in window.findChildren(QLabel, "columnHeader")
                if label.toolTip()
                == "Country / capital / region"
            )
            self.assertIsNone(western)
            self.assertIsNone(eastern)
            self.assertIsNotNone(globe)
        finally:
            window._timer.stop()
            window.close()

    def test_row_context_menu_sets_reference_without_changing_row_content(self):
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
                menu.actions()[0].text(), "Set UTC-5 as my reference"
            )
            self.assertEqual(
                window.reference_action_text(5.5),
                "Set UTC+5:30 as my reference",
            )
            expected_country = window._country_for_offset(
                -5, datetime.now(timezone.utc)
            )
            displayed_country = window._rows[-5].location_cells[0].country_label.text()
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
                window.title_bar.country_search.currentData(), expected_country
            )
            selected_cell = window._rows[-5].location_cells[0]
            self.assertFalse(selected_cell.isHidden())
            self.assertEqual(selected_cell.country_label.text(), displayed_country)
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

    def test_country_selection_does_not_change_hard_coded_row_content(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        try:
            before = {
                offset: row.location_cells[0].country_label.text()
                for offset, row in window._rows.items()
            }
            window.search_country("France")
            after = {
                offset: row.location_cells[0].country_label.text()
                for offset, row in window._rows.items()
            }
            self.assertEqual(after, before)
            self.assertEqual(window.reference_country, "France")
            self.assertIs(window._highlighted_row, window._rows[window.reference_offset])
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
            search.activated.emit(search.findData("Japan"))
            self.app.processEvents()
            row = window._rows[9]
            self.assertEqual(window.reference_offset, 9)
            self.assertEqual(search.currentText(), "Japan — Tokyo — Asia")
            self.assertEqual(search.currentData(), "Japan")
            self.assertEqual(TimeZoneConfig(self.config_path).load_reference_offset(), 9)
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), "Japan"
            )
            self.assertIs(window._highlighted_row, row)
            self.assertTrue(row.property("searchHighlight"))
            self.assertTrue(row.offset_slot.property("searchHighlight"))
            self.assertTrue(row.time_slot.property("searchHighlight"))
            self.assertIsNone(row.locations_slot.graphicsEffect())
            self.assertTrue(all(glow.isEnabled() for glow in row._search_glows))
            reference_rect = window.list_widget.visualItemRect(window._items[9])
            self.assertLessEqual(
                abs(
                    reference_rect.center().y()
                    - window.list_widget.viewport().rect().center().y()
                ),
                reference_rect.height(),
            )
            self.assertFalse(search.isEditable())
            self.assertIsNone(search.lineEdit())
            self.assertEqual(search.toolTip(), "Select a country")
            self.assertEqual(search.count(), len(COUNTRIES))
            self.assertEqual(
                [search.itemText(index) for index in range(search.count())],
                COUNTRY_DROPDOWN_LABELS,
            )
            longest_label_width = max(
                search.fontMetrics().horizontalAdvance(label)
                for label in COUNTRY_DROPDOWN_LABELS
            )
            required_popup_width = (
                longest_label_width
                + search.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
                + 36
            )
            self.assertGreater(search.view().minimumWidth(), search.width())
            self.assertGreaterEqual(
                search.view().minimumWidth(), required_popup_width
            )
            india_index = search.findData("India")
            self.assertGreaterEqual(india_index, 0)
            search.activated.emit(india_index)
            self.assertEqual(window.reference_offset, 5.5)
            self.assertEqual(search.currentText(), "India — New Delhi — Asia")
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_offset(), 5.5
            )
            self.assertEqual(
                TimeZoneConfig(self.config_path).load_reference_country(), "India"
            )
            self.assertIs(window._highlighted_row, window._rows[5.5])
            self.assertFalse(row.property("searchHighlight"))
            mountain_index = search.findData("United States (Mountain)")
            self.assertGreaterEqual(mountain_index, 0)
            search.activated.emit(mountain_index)
            self.assertEqual(search.currentData(), "United States (Mountain)")
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
                window.title_bar.country_search.currentData(),
                "New Zealand (Chatham Islands)",
            )
            window.set_reference_offset(-9.5, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentData(),
                "French Polynesia (Marquesas Islands)",
            )
            window.set_reference_offset(3, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentData(),
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
                window.title_bar.country_search.currentData(),
                "United States (Mountain)",
            )

            window._rows[8.75].locations = ()
            window.set_reference_offset(8.75, at_utc=winter)
            self.assertEqual(
                window.title_bar.country_search.currentData(), "Australia (Eucla)"
            )

            summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
            window._rows[-3.5].locations = ()
            window.set_reference_offset(-3.5, at_utc=summer)
            self.assertEqual(
                window.title_bar.country_search.currentData(),
                "Canada (Newfoundland)",
            )
            window._rows[13.75].locations = ()
            window.set_reference_offset(13.75, at_utc=summer)
            self.assertEqual(
                window.title_bar.country_search.currentData(),
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
                country_index = search.findData(country)
                self.assertGreaterEqual(country_index, 0)
                search.activated.emit(country_index)
                self.app.processEvents()
                self.assertEqual(window.reference_offset, offset)
                self.assertEqual(search.currentData(), country)
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
                restored.title_bar.country_search.currentData(),
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
                country_index = search.findData(country)
                self.assertGreaterEqual(country_index, 0)
                search.activated.emit(country_index)
                self.app.processEvents()
                self.assertEqual(window.reference_offset, offset)
                self.assertEqual(search.currentData(), country)
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
                self.assertEqual(search.currentData(), expected_country)
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
                restored.title_bar.country_search.currentData(),
                "Papua New Guinea (Bougainville)",
            )
        finally:
            restored._timer.stop()
            restored.close()

    def test_redundant_numeric_zone_labels_are_removed(self):
        self.assertEqual(TimeZoneRow.local_zone_text(("+11",), 11), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("GMT", "+00"), 0), "")
        self.assertEqual(TimeZoneRow.local_zone_text(("PKT", "+05"), 5), "PKT")
        self.assertEqual(TimeZoneRow.local_zone_text(("SST", "-11"), -11), "SST")

    def test_time_period_uses_local_hour_day_and_keeps_24_hour_time(self):
        row = TimeZoneRow(0)
        try:
            expectations = (
                (datetime(2026, 8, 2, 0, 6, 55, tzinfo=timezone.utc), "00:06:55", "Today · AM"),
                (datetime(2026, 8, 2, 11, 59, 59, tzinfo=timezone.utc), "11:59:59", "Today · AM"),
                (datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc), "12:00:00", "Today · PM"),
                (datetime(2026, 8, 2, 18, 6, 55, tzinfo=timezone.utc), "18:06:55", "Today · PM"),
            )
            for local_datetime, displayed_time, period in expectations:
                row.update_snapshot(
                    TimeZoneSnapshot(
                        offset=0,
                        local_datetime=local_datetime,
                        locations=(),
                        abbreviations=("GMT",),
                    )
                )
                self.assertIn(displayed_time, row.time_label.text())
                self.assertEqual(row.period_label.text(), period)
        finally:
            row.close()

    def test_time_period_labels_relative_day_from_reference_date(self):
        row = TimeZoneRow(0)
        reference_date = date(2026, 8, 2)
        expectations = (
            (datetime(2026, 8, 1, 23, 30, tzinfo=timezone.utc), "Yesterday · PM"),
            (datetime(2026, 8, 2, 0, 30, tzinfo=timezone.utc), "Today · AM"),
            (datetime(2026, 8, 3, 0, 30, tzinfo=timezone.utc), "Tomorrow · AM"),
        )
        try:
            for local_datetime, period in expectations:
                row.update_snapshot(
                    TimeZoneSnapshot(
                        offset=0,
                        local_datetime=local_datetime,
                        locations=(),
                        abbreviations=("GMT",),
                    ),
                    reference_date,
                )
                self.assertEqual(row.period_label.text(), period)
        finally:
            row.close()

    def test_day_period_labels_follow_selected_reference_row(self):
        window = TimeZoneWindow(enable_tray=False, config_path=self.config_path)
        at_utc = datetime(2026, 8, 2, 0, 30, tzinfo=timezone.utc)
        try:
            window.set_reference_offset(-1, at_utc=at_utc)
            window.refresh_times(at_utc)
            self.assertEqual(window._rows[-1].period_label.text(), "Today · PM")
            self.assertEqual(window._rows[0].period_label.text(), "Tomorrow · AM")
            self.assertEqual(window._rows[-2].period_label.text(), "Today · PM")
        finally:
            window._timer.stop()
            window.close()

    def test_unselected_row_keeps_snapshot_locations_hidden(self):
        row = TimeZoneRow(13.75)
        location = Location(
            "New Zealand (Chatham Islands)",
            "Waitangi",
            "Pacific/Chatham",
        )
        row.update_snapshot(
            TimeZoneSnapshot(
                offset=13.75,
                local_datetime=datetime(2026, 8, 3, tzinfo=timezone.utc),
                locations=(location,),
                abbreviations=("CHADT",),
            )
        )
        self.assertEqual(row.locations, (location,))
        self.assertTrue(all(cell.isHidden() for cell in row.location_cells))

    def test_row_renders_only_the_selected_location_across_middle_column(self):
        row = TimeZoneRow(0)
        try:
            row.resize(800, 90)
            row.show()
            self.app.processEvents()
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
            self.assertEqual(row.locations, locations)
            self.assertTrue(all(cell.isHidden() for cell in row.location_cells))

            selected = locations[0]
            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=locations,
                    abbreviations=("GMT",),
                ),
                selected_location=selected,
                transition_text="Moves to UTC+1 on 29 Mar",
                region_text="Europe",
            )
            self.app.processEvents()
            visible = [cell for cell in row.location_cells if not cell.isHidden()]
            self.assertEqual(len(visible), 1)
            cell = visible[0]
            self.assertEqual(cell.country_label.text(), "United Kingdom")
            self.assertEqual(cell.city_label.text(), "London")
            self.assertEqual(
                row.time_transition_label.text(), "Moves to UTC+1 on 29 Mar"
            )
            self.assertEqual(cell.transition_label.text(), "")
            self.assertEqual(cell.region_label.text(), "Europe")
            self.assertEqual(cell.toolTip(), "United Kingdom — London")
            self.assertAlmostEqual(
                cell.geometry().center().x(),
                row.locations_slot.rect().center().x(),
                delta=1,
            )
            self.assertGreaterEqual(cell.width(), row.locations_slot.width() - 1)

            row.update_snapshot(
                TimeZoneSnapshot(
                    offset=0,
                    local_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    locations=(),
                    abbreviations=("GMT",),
                )
            )
            self.app.processEvents()
            self.assertTrue(all(cell.isHidden() for cell in row.location_cells))
        finally:
            row.close()

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
