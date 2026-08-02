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
- Each occupied UTC row shows one hard-coded representative country, its
  capital or regional centre, its next clock change, and its region.
- Representatives move automatically between UTC rows when their IANA
  summer/winter rules change.

## Reference time zone

Choose a country or one of its regional time zones from **World countries
list** to set its live offset as the reference. Entries include the country,
capital or regional centre, and region, for example **France — Paris —
Europe**. Selecting an entry scrolls to and highlights its current UTC row but
does not alter the row's hard-coded representative. The selected country
controls the reference row: it is blue, earlier offsets are red, and later
offsets are green. The reference is stored for the current Windows user in
local app data as `timezone_config.json`. You can also right-click a visible UTC row and choose
**Set UTC±N as my reference**. A manual row selection chooses a representative
country so seasonal changes remain automatic. Use the reset icon beside the
UTC header icon to clear the selected reference country and return to fixed UTC.

## Tests

```powershell
python -m unittest discover -s tests -v
```
