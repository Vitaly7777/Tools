import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from core.config import AppConfig
from core.logger import setup_logging
from gui.main_window import MainWindow


def main():
    config_path = Path(__file__).parent / "config.json"
    config = AppConfig.from_file(config_path)
    setup_logging(config)

    app = QApplication(sys.argv)
    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))    
    window = MainWindow(config)
    window.show()

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if file_path.exists():
            window._load_file(file_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
