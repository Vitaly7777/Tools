"""
Графический интерфейс для скрипта обрезки Excel/ODS файлов.
Требуется PySide6: pip install PySide6
"""

import sys

from PySide6.QtWidgets import (
    QApplication
)

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
