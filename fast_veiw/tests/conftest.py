import os
import signal
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import openpyxl
from pathlib import Path

@pytest.fixture(autouse=True)
def kill_on_timeout():
    def handler(signum, frame):
        os._exit(1)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(5)  # 5 секунд на тест
    yield
    signal.alarm(0)

@pytest.fixture(autouse=True)
def close_windows(qapp):
    yield
    for widget in qapp.topLevelWidgets():
        widget.close()
    qapp.processEvents()

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Не вызываем app.exec(), чтобы не блокировать тесты

@pytest.fixture
def qtbot(qapp, request):
    from pytestqt.qtbot import QtBot
    bot = QtBot(request)
    yield bot
    # Принудительно закрываем все виджеты после теста
    for widget in qapp.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    qapp.processEvents()
