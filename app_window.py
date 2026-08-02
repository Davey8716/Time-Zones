"""The frameless PySide6 application window."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer
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
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
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
    OFFSET_ORDER,
    Location,
    TimeZoneSnapshot,
    format_gmt_offset,
    snapshots,
)


APP_STYLE = """
QWidget {
    background: #11151c;
    color: #dce5ef;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QWidget#windowSurface {
    border: 1px solid #2a3340;
    border-radius: 8px;
}
QFrame#titleBar {
    background: #171c25;
    border: none;
    border-bottom: 1px solid #29313d;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QLabel#appTitle {
    background: transparent;
    color: #f4f7fb;
    font-size: 11pt;
    font-weight: 700;
}
QLabel#appSubtitle {
    background: transparent;
    color: #758397;
    font-size: 8.5pt;
}
QLabel#columnHeader {
    background: transparent;
    color: #758397;
    font-size: 8.5pt;
}
QPushButton#windowButton {
    border: none;
    background: transparent;
    color: #aeb9c7;
    font-size: 12pt;
    min-width: 42px;
    max-width: 42px;
    min-height: 34px;
    max-height: 34px;
}
QPushButton#windowButton:hover {
    background: #29313d;
    color: white;
}
QPushButton#resetButton {
    border: none;
    background: transparent;
    min-width: 42px;
    max-width: 42px;
    min-height: 34px;
    max-height: 34px;
}
QPushButton#resetButton:hover {
    background: #29313d;
}
QPushButton#closeButton {
    border: none;
    background: transparent;
    color: #aeb9c7;
    font-size: 12pt;
    min-width: 42px;
    max-width: 42px;
    min-height: 34px;
    max-height: 34px;
}
QPushButton#closeButton:hover {
    background: #d94b5d;
    color: white;
}
QListWidget {
    background: #11151c;
    border: none;
    outline: none;
    padding: 0 6px 6px 6px;
}
QListWidget::item {
    background: #171c25;
    border: 1px solid #232b37;
    border-radius: 6px;
    margin: 3px 2px;
}
QListWidget::item:hover {
    background: #1b222d;
    border-color: #344052;
}
QScrollBar:vertical {
    background: #11151c;
    width: 10px;
    margin: 3px 0;
}
QScrollBar::handle:vertical {
    background: #3a4656;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #4b5a6d;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#futureOffsetLabel {
    color: #62d5c4;
    font-size: 12pt;
    font-weight: 700;
}
QLabel#referenceOffsetLabel {
    color: #5caeff;
    font-size: 12pt;
    font-weight: 700;
}
QLabel#pastOffsetLabel {
    color: #ff6677;
    font-size: 12pt;
    font-weight: 700;
}
QLabel#futureTimeLabel {
    color: #62d5c4;
    font-size: 11pt;
    font-weight: 600;
}
QLabel#referenceTimeLabel {
    color: #5caeff;
    font-size: 11pt;
    font-weight: 600;
}
QLabel#pastTimeLabel {
    color: #ff6677;
    font-size: 11pt;
    font-weight: 600;
}
QWidget#offsetSlot {
    background: #11151c;
}
QLabel#futureOffsetLabel, QLabel#referenceOffsetLabel, QLabel#pastOffsetLabel,
QLabel#localZoneLabel {
    background: transparent;
}
QLabel#localZoneLabel {
    color: #8f9daf;
    font-size: 9pt;
}
QWidget#locationsSlot, QWidget#locationPairCell {
    background: transparent;
}
QLabel#locationCountryLabel {
    background: transparent;
    color: #ecf1f7;
    font-weight: 650;
    font-size: 9pt;
}
QLabel#locationCityLabel {
    background: transparent;
    color: #aeb9c7;
    font-size: 9pt;
}
QToolTip {
    color: #dce5ef;
    background-color: #1a202a;
    border: 1px solid #354052;
    border-radius: 4px;
    padding: 5px 7px;
}
QMenu {
    background: #1a202a;
    border: 1px solid #354052;
    padding: 5px;
}
QMenu::item {
    padding: 7px 28px 7px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #2d786f;
}
QMenu::separator {
    height: 1px;
    background: #354052;
    margin: 5px 8px;
}
"""


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
    """Create a globe-and-reset glyph for returning the reference to GMT."""
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
        self.setFixedHeight(58)

        title = QLabel("WORLD TIME ZONES")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Live GMT offsets · daylight-saving aware")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 8, 0, 7)
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

        reset = QPushButton()
        reset.setObjectName("resetButton")
        reset.setIcon(create_reset_icon())
        reset.setIconSize(QSize(18, 18))
        reset.setToolTip("Reset reference to GMT")
        reset.clicked.connect(window.reset_reference)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)
        layout.addWidget(reset)
        layout.addSpacing(42)
        layout.addStretch()
        layout.addLayout(title_stack)
        layout.addStretch()
        layout.addWidget(minimize)
        layout.addWidget(close)

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
    def __init__(self, offset: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.offset = offset

        self.offset_label = QLabel(format_gmt_offset(offset))
        self.offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.local_zone_label = QLabel()
        self.local_zone_label.setObjectName("localZoneLabel")
        self.local_zone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.offset_slot = QWidget()
        self.offset_slot.setObjectName("offsetSlot")
        self.offset_slot.setFixedWidth(155)
        offset_layout = QVBoxLayout(self.offset_slot)
        offset_layout.setContentsMargins(4, 6, 4, 6)
        offset_layout.setSpacing(0)
        offset_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        offset_layout.addWidget(self.offset_label)
        offset_layout.addWidget(self.local_zone_label)

        self.locations_slot = QWidget()
        self.locations_slot.setObjectName("locationsSlot")
        self.locations_slot.setMinimumWidth(280)
        locations_layout = QHBoxLayout(self.locations_slot)
        locations_layout.setContentsMargins(0, 2, 0, 2)
        locations_layout.setSpacing(4)
        self.location_cells = [LocationPairCell() for _ in range(3)]
        for cell in self.location_cells:
            locations_layout.addWidget(cell, 1)

        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFixedWidth(215)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)
        layout.addWidget(self.offset_slot)
        layout.addWidget(self.locations_slot, 1)
        layout.addWidget(self.time_label)
        self.set_reference_offset(0)

    def set_reference_offset(self, reference_offset: int) -> None:
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

    @staticmethod
    def _set_dynamic_style(label: QLabel, object_name: str) -> None:
        label.setObjectName(object_name)
        style = label.style()
        style.unpolish(label)
        style.polish(label)
        label.update()

    def update_snapshot(self, snapshot: TimeZoneSnapshot) -> None:
        if snapshot.locations:
            for cell, location in zip(self.location_cells, snapshot.locations):
                cell.set_location(location)
            for cell in self.location_cells[len(snapshot.locations) :]:
                cell.set_location(None)
        else:
            self.location_cells[0].set_fallback(
                "No major country or capital represented"
            )
            for cell in self.location_cells[1:]:
                cell.set_location(None)

        self.time_label.setText(
            snapshot.local_datetime.strftime("%a, %d %b %Y  ·  %H:%M:%S")
        )
        local_zones = self.local_zone_text(snapshot.abbreviations, snapshot.offset)
        self.local_zone_label.setText(local_zones)
        self.local_zone_label.setVisible(bool(local_zones))

    @staticmethod
    def local_zone_text(abbreviations: tuple[str, ...], offset: int) -> str:
        """Keep named local zones, omitting labels that only repeat the GMT offset."""
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
        self._rows: dict[int, TimeZoneRow] = {}
        self._items: dict[int, QListWidgetItem] = {}
        self._config = TimeZoneConfig(config_path)
        self.reference_offset = self._config.load_reference_offset()
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
        self.resize(1000, 720)

        surface = QWidget()
        surface.setObjectName("windowSurface")
        self.setCentralWidget(surface)
        root = QVBoxLayout(surface)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(TitleBar(self))
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
        QTimer.singleShot(0, self._center_on_gmt)

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
        self.refresh_times()

    def _create_column_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(32)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 6, 32, 4)
        layout.setSpacing(14)
        for text, width, icon, tooltip in (
            ("", 155, "timezone", "Offset and local zone"),
            ("", None, "globe", "Country / capital or centre"),
            ("", 215, "clock", "Local date and time"),
        ):
            label = QLabel(text)
            label.setObjectName("columnHeader")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip(tooltip)
            if icon is not None:
                label.setPixmap(create_column_icon(icon))
            if width is not None:
                label.setFixedWidth(width)
            layout.addWidget(label, 1 if width is None else 0)
        return header

    def _create_rows(self) -> None:
        for offset in OFFSET_ORDER:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 78))
            row = TimeZoneRow(offset)
            row.set_reference_offset(self.reference_offset)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
            self._rows[offset] = row
            self._items[offset] = item

    @staticmethod
    def reference_action_text(offset: int) -> str:
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
        menu = self._build_row_context_menu(row)
        menu.exec(self.list_widget.viewport().mapToGlobal(position))

    def _build_row_context_menu(self, row: TimeZoneRow) -> QMenu:
        menu = QMenu(self)
        action = menu.addAction(self.reference_action_text(row.offset))
        action.triggered.connect(
            lambda _checked=False, offset=row.offset: self.set_reference_offset(offset)
        )
        menu.addSeparator()
        eastern_action = menu.addAction("Show Eastern locations first")
        eastern_action.setCheckable(True)
        eastern_action.setChecked(self.location_order == LOCATION_ORDER_EASTERN)
        eastern_action.triggered.connect(
            lambda _checked=False: self.set_location_order(LOCATION_ORDER_EASTERN)
        )
        western_action = menu.addAction("Show Western locations first")
        western_action.setCheckable(True)
        western_action.setChecked(self.location_order == LOCATION_ORDER_WESTERN)
        western_action.triggered.connect(
            lambda _checked=False: self.set_location_order(LOCATION_ORDER_WESTERN)
        )
        return menu

    def set_reference_offset(self, offset: int) -> None:
        if not is_valid_reference_offset(offset):
            raise ValueError(f"Invalid reference offset: {offset}")
        self.reference_offset = offset
        for row in self._rows.values():
            row.set_reference_offset(offset)
        self._config.save_reference_offset(offset)

    def set_location_order(self, location_order: str) -> None:
        if not is_valid_location_order(location_order):
            raise ValueError(f"Invalid location order: {location_order}")
        self.location_order = location_order
        self._config.save_location_order(location_order)
        self.refresh_times()

    def reset_reference(self) -> None:
        self.set_reference_offset(0)
        self._center_on_gmt()

    def _center_on_gmt(self) -> None:
        gmt_index = OFFSET_ORDER.index(0)
        gmt_item = self.list_widget.item(gmt_index)
        if gmt_item is not None:
            self.list_widget.scrollToItem(
                gmt_item,
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
        for snapshot in snapshots(current, location_order=self.location_order):
            self._rows[snapshot.offset].update_snapshot(snapshot)

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

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            if self._tray is not None:
                self._show_action.setText("Show")
        else:
            self.show_and_activate()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()

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
