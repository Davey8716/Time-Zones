"""The frameless PySide6 application window."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import re

from PySide6.QtCore import QEvent, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QCloseEvent,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QComboBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from timezone_config import (
    LOCATION_ORDER_EASTERN,
    LOCATION_ORDER_WESTERN,
    TimeZoneConfig,
    is_valid_location_order,
    is_valid_reference_offset,
)
from timezone_data import (
    COUNTRIES,
    COUNTRY_TIME_ZONES,
    COUNTRY_ZONE_OPTIONS,
    OFFSET_ORDER,
    Location,
    Offset,
    TimeZoneSnapshot,
    format_gmt_offset,
    offset_for,
    snapshots,
    time_zone_for_country,
)

from app_style import APP_STYLE


EXE_BUILDER_TRAY_ICON_ENV_VAR = "EXE_BUILDER_TRAY_ICON_PATH"


def resolve_build_icon() -> QIcon:
    """Return EXE Builder's bundled icon or Qt's standard Windows fallback."""
    icon_path = os.environ.get(EXE_BUILDER_TRAY_ICON_ENV_VAR, "").strip()
    if icon_path:
        return QIcon(icon_path)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)


def create_column_icon(kind: str, size: int = 18) -> QPixmap:
    """Create compact header icons without relying on platform emoji fonts."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#758397"), 1.5))

    if kind == "timezone":
        centre = QPoint(size * 11 // 20, size * 9 // 20)
        painter.drawEllipse(size * 3 // 10, size // 10, size * 3 // 5, size * 3 // 5)
        painter.drawLine(centre, QPoint(centre.x(), size * 3 // 10))
        painter.drawLine(centre, QPoint(size * 3 // 4, centre.y()))
        painter.drawLine(1, size * 3 // 10, size // 4, size * 3 // 10)
        painter.drawLine(size // 8, size // 5, size // 8, size * 2 // 5)
        painter.drawLine(1, size * 4 // 5, size // 4, size * 4 // 5)
    elif kind == "globe":
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.drawEllipse(size // 3, 2, size // 3, size - 4)
        painter.drawLine(3, size // 2, size - 3, size // 2)
    elif kind == "clock":
        centre = QPoint(size // 2, size // 2)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.drawLine(centre, QPoint(size // 2, size // 4))
        painter.drawLine(centre, QPoint(size * 3 // 4 - 1, size // 2 + 1))
    else:
        raise ValueError(f"Unknown column icon: {kind}")

    painter.end()
    return pixmap


def create_reset_icon(size: int = 18) -> QIcon:
    """Create a globe-and-reset glyph for returning the reference to UTC."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#aeb9c7"), 1.35))

    # Globe: the meridian and latitude lines make the control's time-zone
    # context clear even at the compact title-bar size.
    globe_left = 2
    globe_top = 2
    globe_size = size - 4
    painter.drawEllipse(globe_left, globe_top, globe_size, globe_size)
    painter.drawEllipse(size // 2 - 3, globe_top, 6, globe_size)
    painter.drawEllipse(globe_left + 1, size // 2 - 3, globe_size - 2, 6)

    # Reset arrow: a heavier open arc and triangular head distinguish the
    # action from the globe's latitude/longitude lines.
    painter.setPen(QPen(QColor("#aeb9c7"), 1.8))
    painter.drawArc(1, 1, size - 2, size - 2, 55 * 16, 255 * 16)
    arrow_tip = QPoint(2, size // 2 - 1)
    painter.setBrush(QColor("#aeb9c7"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(
        QPolygon(
            [
                arrow_tip,
                QPoint(6, size // 2 - 4),
                QPoint(6, size // 2 + 2),
            ]
        )
    )
    painter.end()
    return QIcon(pixmap)


def create_titlebar_icon(kind: str, size: int = 18) -> QIcon:
    """Draw equally sized title-bar control glyphs on a shared canvas."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#aeb9c7"), 1.7))
    if kind == "minimize":
        painter.drawLine(4, size * 2 // 3, size - 4, size * 2 // 3)
    elif kind == "close":
        painter.drawLine(4, 4, size - 4, size - 4)
        painter.drawLine(size - 4, 4, 4, size - 4)
    else:
        raise ValueError(f"Unknown title-bar icon: {kind}")
    painter.end()
    return QIcon(pixmap)


class TitleBar(QFrame):
    def __init__(self, window: "TimeZoneWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(80)

        title = QLabel("WORLD TIME ZONES")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Live UTC offsets · daylight-saving aware")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 10, 0, 10)
        title_stack.setSpacing(1)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)

        minimize = QPushButton()
        minimize.setObjectName("windowButton")
        minimize.setIcon(create_titlebar_icon("minimize"))
        minimize.setIconSize(QSize(18, 18))
        minimize.setFixedSize(42, 34)
        minimize.setToolTip("Minimize")
        minimize.clicked.connect(window.showMinimized)

        close = QPushButton()
        close.setObjectName("closeButton")
        close.setIcon(create_titlebar_icon("close"))
        close.setIconSize(QSize(18, 18))
        close.setFixedSize(42, 34)
        close.setToolTip("Hide to tray")
        close.clicked.connect(window.close)

        country_search_label = QLabel("World countries list")
        country_search_label.setObjectName("countrySearchLabel")
        country_search_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        country_search_label.setFixedHeight(18)

        country_search = QComboBox()
        country_search.setObjectName("countrySearch")
        country_search.setEditable(True)
        country_search.addItems(COUNTRIES)
        country_search.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        country_search.setCurrentIndex(-1)
        country_search.lineEdit().clear()
        country_search.setPlaceholderText("Search country")
        longest_country = max(COUNTRIES, key=len)
        popup_width = country_search.fontMetrics().horizontalAdvance(longest_country) + 52
        country_search.setFixedWidth(260)
        country_search.view().setMinimumWidth(popup_width)
        country_search.setMaxVisibleItems(18)
        country_search.completer().setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        country_search.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        country_search.setFixedHeight(30)
        country_search.setToolTip("Search for a country")
        country_search.activated[int].connect(
            lambda index: window.search_country(country_search.itemText(index))
        )
        country_search.lineEdit().returnPressed.connect(
            lambda: window.search_country(country_search.currentText())
        )
        self.country_search = country_search

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 8, 12, 8)
        left_layout.setSpacing(2)
        left_layout.addWidget(country_search_label)
        left_layout.addWidget(country_search, 0, Qt.AlignmentFlag.AlignLeft)
        left_layout.addStretch()

        title_panel = QWidget()
        title_panel.setLayout(title_stack)

        right_panel = QWidget()
        right_layout = QHBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 12, 0)
        right_layout.setSpacing(0)
        right_layout.addStretch()
        right_layout.addWidget(minimize)
        right_layout.addWidget(close)

        side_width = country_search.width() + 24
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(0)
        layout.addWidget(left_panel, 0, 0)
        layout.addWidget(title_panel, 0, 1)
        layout.addWidget(right_panel, 0, 2)
        layout.setColumnMinimumWidth(0, side_width)
        layout.setColumnMinimumWidth(2, side_width)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class LocationPairCell(QWidget):
    """A compact, two-line location pair used within a time-zone row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("locationPairCell")

        self.country_label = QLabel()
        self.country_label.setObjectName("locationCountryLabel")
        self.country_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.country_label.setWordWrap(True)

        self.city_label = QLabel()
        self.city_label.setObjectName("locationCityLabel")
        self.city_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.city_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)
        layout.addWidget(self.country_label)
        layout.addWidget(self.city_label)
        self.set_location(None)

    def set_location(self, location: Location | None) -> None:
        if location is None:
            self.country_label.clear()
            self.city_label.clear()
            self.setToolTip("")
            self.hide()
            return

        self.country_label.setText(location.country)
        self.city_label.setText(location.city)
        self.setToolTip(location.display_name)
        self.show()

    def set_fallback(self, message: str) -> None:
        self.country_label.setText(message)
        self.city_label.clear()
        self.setToolTip("")
        self.show()


class TimeZoneRow(QWidget):
    def __init__(self, offset: Offset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.offset = offset
        self.locations: tuple[Location, ...] = ()
        self.setObjectName("timezoneRow")
        self.setProperty("searchHighlight", False)
        self._search_glow = QGraphicsDropShadowEffect(self)
        self._search_glow.setColor(QColor("#ffffff"))
        self._search_glow.setBlurRadius(16)
        self._search_glow.setOffset(0, 0)
        self._search_glow.setEnabled(False)
        self.setGraphicsEffect(self._search_glow)
        self._search_flash = QPropertyAnimation(
            self._search_glow, b"blurRadius", self
        )
        self._search_flash.setDuration(550)
        self._search_flash.setStartValue(8.0)
        self._search_flash.setKeyValueAt(0.45, 28.0)
        self._search_flash.setEndValue(16.0)

        self.offset_slot = QWidget(self)
        self.offset_slot.setObjectName("offsetSlot")
        self.offset_slot.setFixedWidth(155)

        self.offset_label = QLabel(format_gmt_offset(offset), self.offset_slot)
        self.offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.local_zone_label = QLabel(self.offset_slot)
        self.local_zone_label.setObjectName("localZoneLabel")
        self.local_zone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hemisphere_label = QLabel(
            self.hemisphere_text(offset), self.offset_slot
        )
        self.hemisphere_label.setObjectName("hemisphereLabel")
        self.hemisphere_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hemisphere_label.setVisible(bool(self.hemisphere_label.text()))

        offset_layout = QGridLayout(self.offset_slot)
        offset_layout.setContentsMargins(4, 6, 4, 6)
        offset_layout.setHorizontalSpacing(0)
        offset_layout.setVerticalSpacing(0)
        offset_layout.addWidget(self.offset_label, 0, 0)
        offset_layout.addWidget(self.local_zone_label, 1, 0)
        offset_layout.addWidget(self.hemisphere_label, 2, 0)
        for row, height in enumerate((22, 16, 16)):
            offset_layout.setRowMinimumHeight(row, height)

        self.locations_slot = QWidget(self)
        self.locations_slot.setObjectName("locationsSlot")
        self.locations_slot.setMinimumWidth(280)
        locations_layout = QGridLayout(self.locations_slot)
        locations_layout.setContentsMargins(0, 2, 0, 2)
        locations_layout.setHorizontalSpacing(0)
        locations_layout.setVerticalSpacing(0)
        for column in range(3):
            locations_layout.setColumnStretch(column, 1)
        self._locations_layout = locations_layout
        self.location_cells = [
            LocationPairCell(self.locations_slot) for _ in range(3)
        ]
        for column, cell in enumerate(self.location_cells):
            locations_layout.addWidget(cell, 0, column)

        self.time_slot = QWidget(self)
        self.time_slot.setObjectName("timeSlot")
        self.time_slot.setFixedWidth(215)

        self.time_label = QLabel(self.time_slot)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.period_label = QLabel(self.time_slot)
        self.period_label.setObjectName("timePeriodLabel")
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        time_layout = QGridLayout(self.time_slot)
        time_layout.setContentsMargins(4, 6, 4, 6)
        time_layout.setHorizontalSpacing(0)
        time_layout.setVerticalSpacing(0)
        time_layout.addWidget(self.time_label, 0, 0)
        time_layout.addWidget(self.period_label, 1, 0)
        for row, height in enumerate((22, 16, 16)):
            time_layout.setRowMinimumHeight(row, height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)
        layout.addWidget(self.offset_slot)
        layout.addWidget(self.locations_slot, 1)
        layout.addWidget(self.time_slot)
        self.set_reference_offset(0)

    @staticmethod
    def hemisphere_text(offset: Offset) -> str:
        return ""

    def set_reference_offset(self, reference_offset: Offset) -> None:
        if self.offset == reference_offset:
            offset_name = "referenceOffsetLabel"
            time_name = "referenceTimeLabel"
        elif self.offset < reference_offset:
            offset_name = "pastOffsetLabel"
            time_name = "pastTimeLabel"
        else:
            offset_name = "futureOffsetLabel"
            time_name = "futureTimeLabel"
        self._set_dynamic_style(self.offset_label, offset_name)
        self._set_dynamic_style(self.time_label, time_name)

    def set_search_highlight(self, highlighted: bool) -> None:
        self._search_flash.stop()
        self._search_glow.setBlurRadius(16)
        self.setProperty("searchHighlight", highlighted)
        self._search_glow.setEnabled(highlighted)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def flash_search_highlight(self) -> None:
        self.set_search_highlight(True)
        self._search_flash.start()

    @staticmethod
    def _set_dynamic_style(label: QLabel, object_name: str) -> None:
        label.setObjectName(object_name)
        style = label.style()
        style.unpolish(label)
        style.polish(label)
        label.update()

    def update_snapshot(
        self,
        snapshot: TimeZoneSnapshot,
        reference_date: date | None = None,
    ) -> None:
        self.locations = snapshot.locations
        if snapshot.locations:
            columns_by_count = {
                1: (0,),
                2: (0, 2),
                3: (0, 1, 2),
            }
            visible_locations = snapshot.locations[:3]
            for cell in self.location_cells:
                self._locations_layout.removeWidget(cell)
            for cell, location, column in zip(
                self.location_cells,
                visible_locations,
                columns_by_count[len(visible_locations)],
            ):
                self._locations_layout.addWidget(cell, 0, column)
                cell.set_location(location)
            for cell in self.location_cells[len(visible_locations) :]:
                cell.set_location(None)
        else:
            for cell in self.location_cells:
                self._locations_layout.removeWidget(cell)
            self._locations_layout.addWidget(self.location_cells[0], 0, 0, 1, 3)
            fallback_message = "No major country or capital represented"
            if snapshot.offset == 13.75:
                fallback_message += " (this will change during the DST switchover)"
            self.location_cells[0].set_fallback(fallback_message)
            for cell in self.location_cells[1:]:
                cell.set_location(None)

        self.time_label.setText(
            snapshot.local_datetime.strftime("%a, %d %b %Y  ·  %H:%M:%S")
        )
        local_date = snapshot.local_datetime.date()
        reference_date = reference_date or local_date
        self.period_label.setText(
            f"{self.relative_day_text(local_date, reference_date)} · "
            f"{'AM' if snapshot.local_datetime.hour < 12 else 'PM'}"
        )
        local_zones = self.local_zone_text(snapshot.abbreviations, snapshot.offset)
        self.local_zone_label.setText(local_zones)
        self.local_zone_label.setVisible(bool(local_zones))

    @staticmethod
    def relative_day_text(local_date: date, reference_date: date) -> str:
        delta_days = (local_date - reference_date).days
        if delta_days == -1:
            return "Yesterday"
        if delta_days == 1:
            return "Tomorrow"
        return "Today"

    @staticmethod
    def local_zone_text(abbreviations: tuple[str, ...], offset: Offset) -> str:
        """Keep named local zones, omitting labels that only repeat the UTC offset."""
        numeric_offset = re.compile(r"(?:GMT|UTC)?[+-]\d{1,2}(?::?\d{2})?$")
        meaningful = [
            abbreviation
            for abbreviation in abbreviations
            if abbreviation.upper() not in {"GMT", "UTC"}
            and not numeric_offset.fullmatch(abbreviation.upper())
        ]
        return " / ".join(meaningful)


class TimeZoneWindow(QMainWindow):
    RESIZE_MARGIN = 7

    def __init__(
        self,
        enable_tray: bool = True,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._allow_close = False
        self._tray: QSystemTrayIcon | None = None
        self._rows: dict[Offset, TimeZoneRow] = {}
        self._items: dict[Offset, QListWidgetItem] = {}
        self._highlighted_row: TimeZoneRow | None = None
        self._config = TimeZoneConfig(config_path)
        self.reference_offset = self._config.load_reference_offset()
        self.reference_country = self._config.load_reference_country()
        self.location_order = self._config.load_location_order()

        self.setWindowTitle("World Time Zones")
        self.setWindowIcon(resolve_build_icon())
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(790, 500)
        self.resize(1000, 800)

        surface = QWidget()
        surface.setObjectName("windowSurface")
        self.setCentralWidget(surface)
        root = QVBoxLayout(surface)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)
        root.addWidget(self._create_column_header())

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_reference_menu)
        root.addWidget(self.list_widget, 1)
        self._create_rows()

        self.setStyleSheet(APP_STYLE)
        self._centre_on_screen()

        if enable_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray()
            QApplication.instance().setQuitOnLastWindowClosed(False)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.refresh_times)
        self._timer.start(1000)
        current = datetime.now(timezone.utc)
        self.refresh_times(current)
        self._restore_reference(current)

    def _create_column_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(34)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 2, 32, 2)
        layout.setSpacing(14)

        offset_header = QWidget()
        offset_header.setFixedWidth(155)
        offset_layout = QHBoxLayout(offset_header)
        offset_layout.setContentsMargins(0, 0, 0, 0)
        offset_layout.setSpacing(0)

        reset = QPushButton()
        reset.setObjectName("resetButton")
        reset.setIcon(create_reset_icon())
        reset.setIconSize(QSize(18, 18))
        reset.setToolTip("Reset reference to UTC")
        reset.clicked.connect(self.reset_reference)

        offset_icon = QLabel()
        offset_icon.setObjectName("columnHeader")
        offset_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        offset_icon.setToolTip("Offset and local zone")
        offset_icon.setPixmap(create_column_icon("timezone"))

        right_balance = QWidget()
        right_balance.setFixedWidth(34)
        offset_layout.addWidget(reset)
        offset_layout.addWidget(offset_icon, 1)
        offset_layout.addWidget(right_balance)
        layout.addWidget(offset_header)

        country_header = QWidget()
        country_layout = QHBoxLayout(country_header)
        country_layout.setContentsMargins(0, 0, 0, 0)
        country_layout.setSpacing(3)

        globe_icon = QLabel()
        globe_icon.setObjectName("columnHeader")
        globe_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        globe_icon.setToolTip("Country / capital or centre")
        globe_icon.setPixmap(create_column_icon("globe"))

        western_order = QPushButton("<")
        western_order.setObjectName("westernOrderButton")
        western_order.setFixedSize(26, 26)
        western_order.setCheckable(True)
        western_order.setToolTip("Show Western locations first")
        western_order.clicked.connect(
            lambda _checked=False: self.set_location_order(LOCATION_ORDER_WESTERN)
        )

        eastern_order = QPushButton(">")
        eastern_order.setObjectName("easternOrderButton")
        eastern_order.setFixedSize(26, 26)
        eastern_order.setCheckable(True)
        eastern_order.setToolTip("Show Eastern locations first")
        eastern_order.clicked.connect(
            lambda _checked=False: self.set_location_order(LOCATION_ORDER_EASTERN)
        )

        location_order_group = QButtonGroup(self)
        location_order_group.setExclusive(True)
        location_order_group.addButton(western_order)
        location_order_group.addButton(eastern_order)
        western_order.setChecked(self.location_order == LOCATION_ORDER_WESTERN)
        eastern_order.setChecked(self.location_order == LOCATION_ORDER_EASTERN)
        self._location_order_group = location_order_group
        self._western_order_button = western_order
        self._eastern_order_button = eastern_order

        country_layout.addStretch()
        country_layout.addWidget(western_order, 0, Qt.AlignmentFlag.AlignVCenter)
        country_layout.addWidget(globe_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        country_layout.addWidget(eastern_order, 0, Qt.AlignmentFlag.AlignVCenter)
        country_layout.addStretch()
        layout.addWidget(country_header, 1)

        clock_icon = QLabel()
        clock_icon.setObjectName("columnHeader")
        clock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock_icon.setToolTip("Local date and time")
        clock_icon.setPixmap(create_column_icon("clock"))
        clock_icon.setFixedWidth(215)
        layout.addWidget(clock_icon)
        return header

    def _create_rows(self) -> None:
        for offset in OFFSET_ORDER:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 90))
            row = TimeZoneRow(offset)
            row.set_reference_offset(self.reference_offset)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
            self._rows[offset] = row
            self._items[offset] = item

    @staticmethod
    def reference_action_text(offset: Offset) -> str:
        return f"Set {format_gmt_offset(offset)} as my reference"

    def _row_at(self, position: QPoint) -> TimeZoneRow | None:
        item = self.list_widget.itemAt(position)
        if item is None:
            return None
        row = self.list_widget.itemWidget(item)
        return row if isinstance(row, TimeZoneRow) else None

    def _show_reference_menu(self, position: QPoint) -> None:
        row = self._row_at(position)
        if row is None:
            return
        menu = self._build_reference_menu(row)
        menu.exec(self.list_widget.viewport().mapToGlobal(position))

    def _build_reference_menu(self, row: TimeZoneRow) -> QMenu:
        menu = QMenu(self)
        action = menu.addAction(self.reference_action_text(row.offset))
        action.triggered.connect(
            lambda _checked=False, offset=row.offset: self.set_reference_offset(offset)
        )
        return menu

    def set_reference_offset(
        self,
        offset: Offset,
        country: str | None = None,
        at_utc: datetime | None = None,
    ) -> None:
        if not is_valid_reference_offset(offset):
            raise ValueError(f"Invalid reference offset: {offset}")
        self.reference_offset = offset
        for row in self._rows.values():
            row.set_reference_offset(offset)
        selected_country = country or self._country_for_offset(
            offset, at_utc or datetime.now(timezone.utc)
        )
        country_index = self.title_bar.country_search.findText(
            selected_country, Qt.MatchFlag.MatchFixedString
        )
        if country_index >= 0:
            self.title_bar.country_search.setCurrentIndex(country_index)
            self.reference_country = selected_country
            self._config.save_reference(offset, selected_country)
        self._highlight_offset(offset)

    def _restore_reference(self, at_utc: datetime) -> None:
        """Restore a saved country/offset pair after live rows are populated."""
        offset = self.reference_offset
        country = self.reference_country
        country_index = self.title_bar.country_search.findText(
            country or "", Qt.MatchFlag.MatchFixedString
        )
        if country_index >= 0:
            if not (country == self._gmt_country(at_utc) and offset == 0):
                zone_id = time_zone_for_country(country or "")
                if zone_id is not None:
                    result = offset_for(Location(country or "", "", zone_id), at_utc)
                    if result is not None:
                        offset = result[0]
        else:
            country = (
                self._gmt_country(at_utc)
                if offset == 0
                else self._country_for_offset(offset, at_utc)
            )
        self.set_reference_offset(offset, country=country, at_utc=at_utc)

    def _country_for_offset(self, offset: Offset, at_utc: datetime) -> str:
        """Prefer a displayed country, then any alphabetical country-zone match."""
        row = self._rows[offset]
        dropdown_country_by_zone = {
            zone_id: country for country, zone_id in COUNTRY_TIME_ZONES
        }
        canonical_country_by_zone = {
            zone_id: country for country, zone_id in COUNTRY_ZONE_OPTIONS
        }
        canonical_names = {country.casefold(): country for country in COUNTRIES}
        for location in row.locations:
            country = canonical_names.get(location.country.casefold())
            if country is None:
                country = dropdown_country_by_zone.get(location.zone_id)
            if country is None:
                canonical_country = canonical_country_by_zone.get(location.zone_id)
                country = canonical_names.get((canonical_country or "").casefold())
            if country is None:
                base_name = re.sub(r"\s*\([^)]*\)\s*$", "", location.country)
                country = canonical_names.get(base_name.casefold())
            if country is not None:
                return country
        for country, zone_id in COUNTRY_TIME_ZONES:
            result = offset_for(Location(country, "", zone_id), at_utc)
            if result is not None and result[0] == offset:
                return country
        for seasonal_date in (
            at_utc - timedelta(days=182),
            at_utc + timedelta(days=182),
        ):
            for country, zone_id in COUNTRY_TIME_ZONES:
                result = offset_for(Location(country, "", zone_id), seasonal_date)
                if result is not None and result[0] == offset:
                    return country
        return self.title_bar.country_search.currentText()

    def set_location_order(self, location_order: str) -> None:
        if not is_valid_location_order(location_order):
            raise ValueError(f"Invalid location order: {location_order}")
        self.location_order = location_order
        self._western_order_button.setChecked(
            location_order == LOCATION_ORDER_WESTERN
        )
        self._eastern_order_button.setChecked(
            location_order == LOCATION_ORDER_EASTERN
        )
        self._config.save_location_order(location_order)
        self.refresh_times()

    def reset_reference(self) -> None:
        current = datetime.now(timezone.utc)
        country = self._gmt_country(current)
        self.set_reference_offset(0, country=country, at_utc=current)
        self._highlight_offset(0, flash=True)

    @staticmethod
    def _gmt_country(_at_utc: datetime) -> str:
        """Return the country displayed when resetting the reference to GMT."""
        return "Portugal (Mainland)"

    def search_country(self, country: str) -> None:
        """Centre and highlight the current offset row for a selected country."""
        country_name = country.strip()
        if not country_name:
            return
        zone_id = time_zone_for_country(country_name)
        if zone_id is None:
            return
        current = datetime.now(timezone.utc)
        result = offset_for(Location(country_name, "", zone_id), current)
        if result is None:
            return
        offset, _abbreviation = result
        self.set_reference_offset(offset, country=country_name, at_utc=current)

    def _highlight_offset(self, offset: Offset, flash: bool = False) -> None:
        row = self._rows[offset]
        if self._highlighted_row is not None and self._highlighted_row is not row:
            self._highlighted_row.set_search_highlight(False)
        if flash:
            row.flash_search_highlight()
        else:
            row.set_search_highlight(True)
        self._highlighted_row = row
        self._center_on_reference()
        QTimer.singleShot(0, self._center_on_reference)

    def _center_on_reference(self) -> None:
        self.list_widget.scrollToItem(
            self._items[self.reference_offset],
            QListWidget.ScrollHint.PositionAtCenter,
        )

    def _create_tray(self) -> None:
        self._tray = QSystemTrayIcon(self.windowIcon(), self)
        self._tray.setToolTip("World Time Zones")
        menu = QMenu(self)
        menu.setStyleSheet(APP_STYLE)
        self._show_action = QAction("Hide", self)
        self._show_action.triggered.connect(self.toggle_visibility)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_application)
        menu.addAction(self._show_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def refresh_times(self, at_utc: datetime | None = None) -> None:
        current = at_utc or datetime.now(timezone.utc)
        current_snapshots = snapshots(current, location_order=self.location_order)
        reference_snapshot = next(
            snapshot
            for snapshot in current_snapshots
            if snapshot.offset == self.reference_offset
        )
        reference_date = reference_snapshot.local_datetime.date()
        for snapshot in current_snapshots:
            self._rows[snapshot.offset].update_snapshot(snapshot, reference_date)

    def _centre_on_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def show_and_activate(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if self._tray is not None:
            self._show_action.setText("Hide")

    def show_after_first_layout(self) -> None:
        """Prime layout and painting without creating a visible native window."""
        self.ensurePolished()
        surface = self.centralWidget()
        if surface is not None:
            surface.ensurePolished()
            if surface.layout() is not None:
                surface.layout().activate()
        self.list_widget.doItemsLayout()
        self._center_on_reference()

        first_frame = QPixmap(self.size())
        first_frame.fill(Qt.GlobalColor.transparent)
        self.render(first_frame)

        self._centre_on_screen()
        self.show()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            if self._tray is not None:
                self._show_action.setText("Show")
        else:
            self.show_and_activate()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_and_activate()

    def quit_application(self) -> None:
        self._allow_close = True
        if self._tray is not None:
            self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close and self._tray is not None:
            event.ignore()
            self.hide()
            self._show_action.setText("Show")
            return
        event.accept()

    def _resize_edges(self, global_position: QPoint):
        if self.isMaximized() or self.isFullScreen():
            return Qt.Edge(0)
        local = self.mapFromGlobal(global_position)
        edges = Qt.Edge(0)
        if local.x() <= self.RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif local.x() >= self.width() - self.RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if local.y() <= self.RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        elif local.y() >= self.height() - self.RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges) -> Qt.CursorShape:
        horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        if horizontal and vertical:
            if bool(edges & Qt.Edge.LeftEdge) == bool(edges & Qt.Edge.TopEdge):
                return Qt.CursorShape.SizeFDiagCursor
            return Qt.CursorShape.SizeBDiagCursor
        if horizontal:
            return Qt.CursorShape.SizeHorCursor
        if vertical:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def eventFilter(self, watched, event: QEvent) -> bool:
        if isinstance(watched, QWidget) and (
            watched is self or self.isAncestorOf(watched)
        ):
            if event.type() == QEvent.Type.MouseMove:
                edges = self._resize_edges(event.globalPosition().toPoint())
                self.setCursor(self._cursor_for_edges(edges))
            elif (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                edges = self._resize_edges(event.globalPosition().toPoint())
                if edges:
                    handle = self.windowHandle()
                    if handle is not None and handle.startSystemResize(edges):
                        return True
        return super().eventFilter(watched, event)
