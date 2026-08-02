"""Application stylesheet."""

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
QLabel#countrySearchLabel {
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
    min-width: 34px;
    max-width: 34px;
    min-height: 30px;
    max-height: 30px;
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
QWidget#timezoneRow[searchHighlight="true"] {
    border: 2px solid #ffffff;
    border-radius: 6px;
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
QLabel#timePeriodLabel {
    background: transparent;
    color: #66768a;
    font-size: 8pt;
    font-weight: 600;
}
QWidget#offsetSlot {
    background: #11151c;
}
QLabel#futureOffsetLabel, QLabel#referenceOffsetLabel, QLabel#pastOffsetLabel,
QLabel#localZoneLabel, QLabel#hemisphereLabel {
    background: transparent;
}
QLabel#localZoneLabel {
    color: #8f9daf;
    font-size: 9pt;
}
QLabel#hemisphereLabel {
    color: #66768a;
    font-size: 8pt;
    font-weight: 600;
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
QLabel#locationTransitionLabel {
    background: transparent;
    color: #7f91a6;
    font-size: 8pt;
}
QLabel#locationRegionLabel {
    background: transparent;
    color: #66768a;
    font-size: 8pt;
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
