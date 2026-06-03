from typing import Optional, List, Tuple, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QHeaderView, QProgressBar, QApplication
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QTimer
from PySide6.QtGui import QColor, QKeySequence, QAction, QClipboard, QIcon, QPainter, QPixmap


# gui/sheet_tab.py

class SpinnerIcon:
    """Генератор анимированной иконки-спиннера."""
    _cache: dict[tuple, QIcon] = {}

    @classmethod
    def get(cls, size: int = 16, angle: int = 0) -> QIcon:
        key = (size, angle)
        if key not in cls._cache:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.translate(size / 2, size / 2)
            painter.rotate(angle)
            for i in range(12):
                alpha = 255 - i * 20
                painter.setBrush(QColor(70, 130, 200, alpha))
                painter.drawRoundedRect(-1, -size/2 + 3, 2, 5, 1, 1)
                painter.rotate(30)
            painter.end()
            cls._cache[key] = QIcon(pixmap)
        return cls._cache[key]


class SheetDataModel(QAbstractTableModel):
    needMoreRows = Signal(str, int, int)

    def __init__(self, sheet_name: str, max_columns: int):
        super().__init__()
        self.sheet_name = sheet_name
        self._data: List[Tuple[Any, ...]] = []
        self._max_columns = max_columns
        self._total_rows = 0

    def set_total_rows(self, total: int) -> None:
        self._total_rows = total

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return self._max_columns

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row = self._data[index.row()]
            if index.column() < len(row):
                val = row[index.column()]
                return str(val) if val is not None else ""
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._column_letter(section)
            else:
                return str(section + 1)
        return None

    def _column_letter(self, index: int) -> str:
        result = ""
        n = index
        while n >= 0:
            result = chr(65 + (n % 26)) + result
            n = n // 26 - 1
        return result

    def set_data(self, rows: list, start_index: int = -1) -> None:
        if not rows:
            return
        if start_index == -1:
            start_index = len(self._data)
        needed_len = start_index + len(rows)
        if len(self._data) < needed_len:
            self.beginInsertRows(QModelIndex(), len(self._data), needed_len - 1)
            self._data.extend([()] * (needed_len - len(self._data)))
            self.endInsertRows()
        for i, row in enumerate(rows):
            idx = start_index + i
            if idx < len(self._data):
                self._data[idx] = row
                self.dataChanged.emit(
                    self.index(idx, 0),
                    self.index(idx, self._max_columns - 1)
                )

    def canFetchMore(self, parent=QModelIndex()) -> bool:
        return len(self._data) < self._total_rows

    def fetchMore(self, parent=QModelIndex()) -> None:
        if not self.canFetchMore():
            return
        start_row = len(self._data)
        count = 100
        self.needMoreRows.emit(self.sheet_name, start_row, count)


class SheetTab(QWidget):
    def __init__(self, name: str, max_row: int, max_col: int):
        super().__init__()
        self.name = name
        self.max_row = max_row
        self.max_col = max_col
        self._spinner_angle = 0
        self._loading = False
        self._setup_ui()
        self._setup_sparsity_indicator()
        self._setup_copy_action()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        metrics_panel = QHBoxLayout()
        self._total_rows_label = QLabel(f"Всего строк (max_row): {self.max_row}")
        metrics_panel.addWidget(self._total_rows_label)
        metrics_panel.addWidget(QLabel(f"Столбцов: {self.max_col}"))

        self._effective_label = QLabel("Эффективных строк: 0")
        self._filled_label = QLabel("Заполненных строк: 0")
        metrics_panel.addWidget(self._effective_label)
        metrics_panel.addWidget(self._filled_label)

        self._progress_label = QLabel("Прогресс загрузки: 0 из 0 (0%)")
        metrics_panel.addWidget(self._progress_label)
        metrics_panel.addStretch()

        layout.addLayout(metrics_panel)

        self.model = SheetDataModel(self.name, self.max_col)
        self.model.set_total_rows(self.max_row)

        self._table = QTableView()
        self._table.setModel(self.model)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        layout.addWidget(self._table)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

    def _setup_copy_action(self) -> None:
        copy_action = QAction("Копировать", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selected)
        self.addAction(copy_action)
        self._table.addAction(copy_action)

    def _copy_selected(self) -> None:
        indexes = self._table.selectedIndexes()
        if not indexes:
            return

        rows: dict[int, dict[int, str]] = {}
        for idx in indexes:
            row = idx.row()
            col = idx.column()
            val = self.model.data(idx, Qt.DisplayRole)
            rows.setdefault(row, {})[col] = val if val is not None else ""

        lines = []
        for row_idx in sorted(rows.keys()):
            row_data = rows[row_idx]
            max_col = max(row_data.keys())
            line_cells = [row_data.get(c, "") for c in range(max_col + 1)]
            lines.append("\t".join(line_cells))

        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

    def _setup_sparsity_indicator(self) -> None:
        self._total_rows_label.setAutoFillBackground(True)

    def update_spinner_angle(self) -> None:
        """Вызывается из MainWindow по таймеру."""
        if self._loading:
            self._spinner_angle = (self._spinner_angle + 45) % 360

    def set_loading(self, loading: bool) -> None:
        self._loading = loading

    def get_spinner_icon(self) -> QIcon:
        return SpinnerIcon.get(16, self._spinner_angle)

    def set_data(self, rows: list, start_index: int = -1) -> None:
        self.model.set_data(rows, start_index)
        self._update_progress()

    def update_sparsity(self, filled: int, max_row: int) -> None:
        if max_row == 0:
            return
        ratio = filled / max_row
        if ratio >= 0.9:
            color = QColor(144, 238, 144)
        elif ratio >= 0.5:
            color = QColor(255, 255, 0)
        elif ratio >= 0.2:
            color = QColor(255, 165, 0)
        else:
            color = QColor(255, 99, 71)
        pal = self._total_rows_label.palette()
        pal.setColor(self._total_rows_label.backgroundRole(), color)
        self._total_rows_label.setPalette(pal)

    def update_metrics(self, effective: int, filled: int, is_final: bool) -> None:
        color = "green" if is_final else "goldenrod"
        self._effective_label.setText(f"Эффективных строк: {effective}")
        self._effective_label.setStyleSheet(f"color: {color};")
        self._filled_label.setText(f"Заполненных строк: {filled}")
        self._filled_label.setStyleSheet(f"color: {color};")
        
        if is_final and filled > 0:
            self.model.set_total_rows(filled)
        
        self._update_progress()
        self.update_sparsity(filled, self.max_row)

    def _update_progress(self) -> None:
        loaded = self.model.rowCount()
        percent = (loaded / self.max_row * 100) if self.max_row else 0
        self._progress_label.setText(f"Прогресс загрузки: {loaded} из {self.max_row} ({percent:.1f}%)")

    def show_error(self, error: str) -> None:
        self._error_label.setText(f"Ошибка: {error}")
        self._error_label.show()
        self._table.hide()

    def set_progress_bar(self, progress: QProgressBar) -> None:
        self.progress_bar = progress
        self.layout().addWidget(progress)
