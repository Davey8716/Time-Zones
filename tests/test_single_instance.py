import os
import sys
import unittest
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QProcess, QTimer
from PySide6.QtWidgets import QApplication

from single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_second_owner_is_rejected(self):
        name = f"TimeZones.Test.{uuid4().hex}"
        first = SingleInstance(name)
        try:
            self.assertTrue(first.is_primary)
            self.assertTrue(first.listen())
            activated = []
            first.activation_requested.connect(lambda: activated.append(True))
            loop = QEventLoop()
            process = QProcess()
            process.finished.connect(loop.quit)
            child_code = (
                "from PySide6.QtCore import QCoreApplication; "
                "from single_instance import SingleInstance; "
                "app=QCoreApplication([]); "
                f"instance=SingleInstance({name!r}); "
                "ok=(not instance.is_primary and instance.notify_existing()); "
                "instance.close(); "
                "raise SystemExit(0 if ok else 1)"
            )
            process.start(sys.executable, ["-c", child_code])
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
            self.assertEqual(process.state(), QProcess.ProcessState.NotRunning)
            self.assertEqual(process.exitCode(), 0)
            self.assertEqual(activated, [True])
        finally:
            first.close()


if __name__ == "__main__":
    unittest.main()
