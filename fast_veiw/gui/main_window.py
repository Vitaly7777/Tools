import json
import logging
from pathlib import Path
from typing import Optional, Dict
from venv import logger

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QStatusBar,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QByteArray, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon

from core.config import AppConfig
from core.models import SheetInfo, SheetState
from core.loader_worker import LoaderWorker
from core.excel_reader import ExcelReader
from gui.sheet_tab import SheetTab

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._file_path: Optional[Path] = None
        self._sheets: Dict[str, SheetInfo] = {}
        self._worker: Optional[LoaderWorker] = None
        self._tabs: Dict[str, SheetTab] = {}
        self._recent_files: list[str] = []
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinners)
        self._spinner_timer.start(100)
        self._setup_ui()
        self._setup_menu()
        self._load_settings()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Fast Excel Viewer")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._tab_widget = QTabWidget()
        self._tab_widget.setTabPosition(QTabWidget.South)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tab_widget)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_status_bar()

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        open_action = QAction("Открыть...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        reload_action = QAction("Перечитать", self)
        reload_action.setShortcut(QKeySequence("Ctrl+R"))
        reload_action.triggered.connect(self._reload_file)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu("Вид")
        reset_geom_action = QAction("Сбросить геометрию окна", self)
        reset_geom_action.triggered.connect(self._reset_geometry)
        view_menu.addAction(reset_geom_action)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть Excel файл", "",
            "Excel файлы (*.xlsx *.xlsm *.xltx *.xltm);;Все файлы (*.*)"
        )
        if path:
            self._load_file(Path(path))

    def _load_file(self, path: Path, active_sheet: Optional[str] = None) -> None:
        try:
            with ExcelReader(path) as reader:
                self._file_path = path
                self._add_to_recent(str(path))
                self._sheets.clear()
                self._tabs.clear()
                self._tab_widget.clear()

                excel_active = reader.get_active_sheet_name()

                for name in reader.sheet_names:
                    max_row, max_col = reader.get_sheet_metadata(name)
                    is_active = (name == active_sheet) if active_sheet else (name == excel_active)
                    self._sheets[name] = SheetInfo(
                        name=name, max_row=max_row, max_col=max_col,
                        is_active=is_active, state=SheetState.META_LOADED
                    )
                    tab = SheetTab(name, max_row, max_col)
                    tab.model.needMoreRows.connect(self._on_need_more_rows)
                    self._tabs[name] = tab
                    index = self._tab_widget.addTab(tab, name)
                    if is_active:
                        self._tab_widget.setCurrentIndex(index)

            self._start_worker()
            self._update_status_bar()
            self.setWindowTitle(f"Fast Excel Viewer - {path.name}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{str(e)}")

    def _start_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop_loading()
            self._worker.quit()
            self._worker.wait()

        self._worker = LoaderWorker(self.config)
        self._worker.set_file(self._file_path, self._sheets)
        self._worker.rows_loaded.connect(self._on_rows_loaded)
        self._worker.metrics_updated.connect(self._on_metrics_updated)
        self._worker.preview_done.connect(self._on_preview_done)
        self._worker.full_done.connect(self._on_full_done)
        self._worker.error_occurred.connect(self._on_sheet_error)
        self._worker.memory_limit_exceeded.connect(self._on_memory_limit_exceeded)
        self._worker.loading_started.connect(self._on_loading_started)
        self._worker.start()

    def _on_loading_started(self, sheet_name: str) -> None:
        if sheet_name in self._tabs:
            index = self._tab_widget.indexOf(self._tabs[sheet_name])
            self._tab_widget.setTabIcon(index, self._tabs[sheet_name].get_spinner_icon())

    def _update_spinners(self) -> None:
        for name, tab in self._tabs.items():
            info = self._sheets.get(name)
            if info and info.state in (SheetState.PREVIEW_LOADING, SheetState.FULL_LOADING):
                tab.set_loading(True)
                tab.update_spinner_angle()
                index = self._tab_widget.indexOf(tab)
                self._tab_widget.setTabIcon(index, tab.get_spinner_icon())
            else:
                tab.set_loading(False)

    def _on_tab_changed(self, index: int) -> None:
        if index >= 0 and self._worker:
            sheet_name = self._tab_widget.tabText(index)
            self._worker.set_active_sheet(sheet_name)
            self._update_status_bar()

    def _on_rows_loaded(self, sheet_name: str, rows: list, start_index: int) -> None:
        if sheet_name in self._tabs:
            self._tabs[sheet_name].set_data(rows, start_index)

    def _on_metrics_updated(self, sheet_name: str, effective: int, filled: int, is_final: bool) -> None:
        if sheet_name in self._tabs:
            self._tabs[sheet_name].update_metrics(effective, filled, is_final)
            self._sheets[sheet_name].effective_rows = effective
            self._sheets[sheet_name].filled_rows = filled
            if is_final:
                self._sheets[sheet_name].state = SheetState.FULL_LOADED

    def _on_preview_done(self, sheet_name: str) -> None:
        if sheet_name in self._tabs:
            index = self._tab_widget.indexOf(self._tabs[sheet_name])
            self._tab_widget.setTabIcon(index, QIcon())

    def _on_full_done(self, sheet_name: str) -> None:
        if sheet_name in self._tabs:
            index = self._tab_widget.indexOf(self._tabs[sheet_name])
            self._tab_widget.setTabIcon(index, QIcon())

    def _on_sheet_error(self, sheet_name: str, error: str) -> None:
        if sheet_name in self._tabs:
            self._tabs[sheet_name].show_error(error)
            index = self._tab_widget.indexOf(self._tabs[sheet_name])
            self._tab_widget.setTabIcon(index, QIcon.fromTheme("dialog-error"))

    def _on_memory_limit_exceeded(self) -> None:
        self._status_bar.showMessage("⚠ Превышен лимит кэша. Невидимые данные сброшены.", 5000)

    def _on_need_more_rows(self, sheet_name: str, start_row: int, count: int) -> None:
        if self._worker:
            self._worker.request_more_rows(sheet_name, start_row, count)

    def _reload_file(self) -> None:
        if self._file_path:
            active_sheet = self._tab_widget.tabText(self._tab_widget.currentIndex())
            self._load_file(self._file_path, active_sheet)

    def _update_status_bar(self) -> None:
        if not self._file_path:
            self._status_bar.showMessage("Файл не открыт")
            return

        stat = self._file_path.stat()
        size_mb = stat.st_size / (1024 * 1024)
        from datetime import datetime
        dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

        total_rows = sum(s.max_row for s in self._sheets.values())
        active_sheet = self._tab_widget.tabText(self._tab_widget.currentIndex())

        msg = f"{self._file_path.name} | {size_mb:.1f} МБ | {dt} | Листов: {len(self._sheets)} | Всего строк: {total_rows} | Активный: {active_sheet}"
        self._status_bar.showMessage(msg)

    def _load_settings(self) -> None:
        settings_path = Path("settings.json")
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "window_geometry" in data:
                self.restoreGeometry(QByteArray.fromBase64(data["window_geometry"].encode()))
            if "window_state" in data:
                self.restoreState(QByteArray.fromBase64(data["window_state"].encode()))
            if "recent_files" in data:
                self._recent_files = data["recent_files"]

    def _save_settings(self) -> None:
        data = {
            "window_geometry": self.saveGeometry().toBase64().data().decode(),
            "window_state": self.saveState().toBase64().data().decode(),
            "last_opened_file": str(self._file_path) if self._file_path else "",
            "recent_files": self._recent_files[-5:]
        }
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _add_to_recent(self, path: str) -> None:
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:5]

    def _reset_geometry(self) -> None:
        self.resize(800, 600)
        self.move(100, 100)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Tab and event.modifiers() == Qt.ControlModifier:
            idx = self._tab_widget.currentIndex()
            self._tab_widget.setCurrentIndex((idx + 1) % self._tab_widget.count())
        elif event.key() == Qt.Key_Backtab and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            idx = self._tab_widget.currentIndex()
            self._tab_widget.setCurrentIndex((idx - 1) % self._tab_widget.count())
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            logger.info("Закрытие окна, остановка воркера")
            self._worker.stop_loading()
            self._worker.quit()
            if not self._worker.wait(5000):  # увеличить до 5 секунд
                logger.warning("Воркер не завершился, принудительная остановка")
                self._worker.terminate()
                self._worker.wait()
        self._save_settings()
        event.accept()
