# World Time Zones

A compact, dark PySide6 desktop clock showing live global offsets from UTC−12
through UTC+14. Countries automatically resolve to their current offset when
daylight-saving rules change.

## Requirements

- Python 3.10 or newer
- Windows 10/11 recommended (the clock and interface are otherwise portable)

## Install and run

```powershell
python -m pip install -r requirements.txt
python main.py
```

Use the same Python executable for both commands. This matters particularly on
Windows systems with multiple Python installations. For example:

```powershell
C:\Path\To\Python\python.exe -m pip install -r requirements.txt
C:\Path\To\Python\python.exe main.py
```

If the required IANA database is unavailable, the app stops at startup and
shows the exact installation command for the interpreter that launched it.

Only one copy runs at a time. Starting the program again restores the existing
window. The custom **×** button hides the window to the notification area; use
one left-click on the tray icon to restore and focus it. Use the tray menu's
**Exit** action to quit completely.

## Display rules

- Rows are ordered UTC−12 through UTC+14, including supported half-hour and
  quarter-hour offsets. The initial view is centred on UTC.
- Times use a 24-hour clock and include the local date and seconds.
- Locations are regrouped using current IANA daylight-saving rules.
- Fractional rows include real capitals such as Kathmandu and New Delhi. For
  multi-zone territories, the app uses an appropriate regional centre such as
  Taiohae, Eucla, Waitangi, or Kiritimati.

## Reference time zone

Choose a country or one of its regional time zones, such as
**United States (Mountain)**, from **World countries list** to set its live
offset as the reference. Regional names in the dropdown match the names shown
in the time-zone rows where available. Dropdown-only regions, including
Russia's 11 time zones, navigate to their existing UTC rows without adding new
location cards. Multi-zone countries also separate regions that share an
offset during part of the year but follow different daylight-saving rules.
The reference row is blue, earlier offsets are red, and
later offsets are green. The choice is saved for the current Windows user in
local app data as `timezone_config.json`, including both the exact dropdown
location and its reference offset. You can also right-click a visible UTC row and choose
**Set UTC±N as my reference**. Use the reset icon beside the UTC
header icon to return to UTC.

Use the **<** and **>** buttons beside the globe header icon to show Western or
Eastern locations first. This ordering preference is also saved per user.

## Tests

```powershell
python -m unittest discover -s tests -v
```
