# World Time Zones

A compact, dark PySide6 desktop clock showing live whole-hour offsets from
GMT−12 through GMT+12. Curated countries and capitals automatically move to
their current offset when daylight-saving rules change.

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
the tray menu's **Exit** action to quit completely.

## Display rules

- Rows are ordered GMT−12 … GMT−1, GMT, then GMT+1 … GMT+12. The
  initial view is centred on GMT.
- Times use a 24-hour clock and include the local date and seconds.
- Locations are regrouped using current IANA daylight-saving rules.
- Half-hour, quarter-hour, GMT+13, and GMT+14 locations are intentionally
  outside this app's requested scope.

## Reference time zone

Right-click any row and choose **Set GMT±N as my reference**. The reference
row is blue, earlier offsets are red, and later offsets are green. The choice
is saved for the current Windows user in local app data as `timezone_config.json`.
Use the reset icon at the top-left of the title bar to return to GMT.

The same right-click menu can switch between **Show Western locations first**
and **Show Eastern locations first**. This ordering preference is also saved
per user.

## Tests

```powershell
python -m unittest discover -s tests -v
```
