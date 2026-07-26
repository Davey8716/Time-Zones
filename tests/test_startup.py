import unittest
from unittest.mock import patch

from main import show_time_zone_database_error, time_zone_database_error_message


class StartupDiagnosticTests(unittest.TestCase):
    def test_message_uses_the_launch_interpreter(self):
        executable = r"C:\Python 314\python.exe"
        message = time_zone_database_error_message(executable)
        self.assertIn(
            r'"C:\Python 314\python.exe" -m pip install tzdata==2025.2',
            message,
        )
        self.assertIn("restart World Time Zones", message)

    def test_missing_database_displays_a_critical_dialog(self):
        with patch("main.QMessageBox.critical") as critical:
            show_time_zone_database_error(r"C:\Python314\python.exe")
        critical.assert_called_once()
        title, message = critical.call_args.args[1:]
        self.assertEqual(title, "Time-zone data required")
        self.assertIn(r"C:\Python314\python.exe", message)


if __name__ == "__main__":
    unittest.main()
