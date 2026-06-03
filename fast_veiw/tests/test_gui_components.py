import sys
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QItemSelectionModel

from gui.sheet_tab import SheetTab, SheetDataModel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_sheet_tab_creation(qapp, qtbot):
    tab = SheetTab("Test", 100, 10)
    qtbot.addWidget(tab)

    assert tab.name == "Test"
    assert tab.model.rowCount() == 0
    assert tab.model.columnCount() == 10


def test_sheet_tab_update_metrics(qapp, qtbot):
    tab = SheetTab("Test", 100, 10)
    qtbot.addWidget(tab)

    tab.update_metrics(50, 30, False)
    assert "50" in tab._effective_label.text()
    assert "goldenrod" in tab._effective_label.styleSheet()

    tab.update_metrics(50, 30, True)
    assert "green" in tab._effective_label.styleSheet()


def test_sheet_data_model(qapp):
    model = SheetDataModel("test", 5)
    model.set_total_rows(100)

    rows = [("A", "B"), ("C", "D")]
    model.set_data(rows)

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0)) == "A"
    assert model.canFetchMore() is True


def test_sheet_data_model_set_data_with_index(qapp):
    model = SheetDataModel("test", 5)
    model.set_total_rows(100)

    rows1 = [("A", "B"), ("C", "D")]
    model.set_data(rows1, 0)
    assert model.rowCount() == 2

    rows2 = [("E", "F")]
    model.set_data(rows2, 2)
    assert model.rowCount() == 3
    assert model.data(model.index(2, 0)) == "E"

    rows3 = [("G", "H")]
    model.set_data(rows3, 1)
    assert model.rowCount() == 3
    assert model.data(model.index(1, 0)) == "G"


def test_copy_selected(qapp, qtbot):
    tab = SheetTab("Test", 10, 3)
    qtbot.addWidget(tab)
    tab.model.set_data([("X", "Y"), ("Z", "W")])

    tab._table.selectAll()
    tab._copy_selected()

    clipboard = QApplication.clipboard()
    assert "X\tY" in clipboard.text()
    assert "Z\tW" in clipboard.text()
