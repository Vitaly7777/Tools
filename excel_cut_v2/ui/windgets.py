import json
import logging

from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from pathlib import Path
import sys


class LogHandler(logging.Handler):
    """Обработчик логов для перенаправления в GUI."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg, record.levelname)


class ConfigWidget(QWidget):
    """Виджет конфигурации."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Параметры обработки")
        form = QFormLayout(group)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("data")
        browse_source = QPushButton("Обзор")
        browse_source.clicked.connect(self.browse_source)

        source_layout = QHBoxLayout()
        source_layout.addWidget(self.source_edit)
        source_layout.addWidget(browse_source)
        form.addRow("Исходная папка:", source_layout)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("оставить пустым для data_cut")
        browse_output = QPushButton("Обзор")
        browse_output.clicked.connect(self.browse_output)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(browse_output)
        form.addRow("Выходная папка:", output_layout)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(0, 1000000)
        self.rows_spin.setValue(50)
        self.rows_spin.setSpecialValueText("Без обрезки")
        form.addRow("Строк для сохранения:", self.rows_spin)

        self.preserve_check = QCheckBox()
        form.addRow("Сохранять форматирование:", self.preserve_check)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(1)
        form.addRow("Количество потоков:", self.workers_spin)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        form.addRow("Уровень логирования:", self.log_level_combo)

        self.log_file_edit = QLineEdit()
        self.log_file_edit.setPlaceholderText("logs/cut_files.log")
        form.addRow("Файл лога:", self.log_file_edit)

        self.stats_file_edit = QLineEdit()
        self.stats_file_edit.setPlaceholderText("reports/processing_stats.xlsx")
        form.addRow("Файл статистики:", self.stats_file_edit)

        layout.addWidget(group)

        buttons_layout = QHBoxLayout()
        self.save_config_btn = QPushButton("Сохранить конфиг")
        self.save_config_btn.clicked.connect(self.save_config)
        self.load_config_btn = QPushButton("Загрузить конфиг")
        self.load_config_btn.clicked.connect(self.load_config_dialog)

        buttons_layout.addWidget(self.save_config_btn)
        buttons_layout.addWidget(self.load_config_btn)
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

    def browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите исходную папку")
        if folder:
            self.source_edit.setText(folder)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите выходную папку")
        if folder:
            self.output_edit.setText(folder)

    def save_config(self):
        config = self.get_config()
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить конфиг", "config.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Успех", f"Конфиг сохранён в {file_path}")

    def load_config_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Загрузить конфиг", "", "JSON (*.json)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.set_config(config)

    def get_config(self):
        return {
            "source_folder": self.source_edit.text() or "data",
            "output_folder": self.output_edit.text() or "",
            "rows_to_keep": self.rows_spin.value(),
            "preserve_formatting": self.preserve_check.isChecked(),
            "max_workers": self.workers_spin.value(),
            "log_level": self.log_level_combo.currentText(),
            "log_file": self.log_file_edit.text() or "cut_files.log",
            "stats_file": self.stats_file_edit.text() or "processing_stats.xlsx"
        }

    def set_config(self, config):
        self.source_edit.setText(config.get("source_folder", "data"))
        self.output_edit.setText(config.get("output_folder", ""))
        self.rows_spin.setValue(config.get("rows_to_keep", 50))
        self.preserve_check.setChecked(config.get("preserve_formatting", False))
        self.workers_spin.setValue(config.get("max_workers", 1))
        self.log_level_combo.setCurrentText(config.get("log_level", "INFO"))
        self.log_file_edit.setText(config.get("log_file", "cut_files.log"))
        self.stats_file_edit.setText(config.get("stats_file", "processing_stats.xlsx"))

    def load_config(self):

        # base_dir = Path(__file__).resolve().parent
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir= Path(__file__).resolve().parent.parent   
        
        default_path = base_dir / "config.json"
        if default_path.exists():
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.set_config(config)
            except Exception:
                pass


class ProgressWidget(QWidget):
    """Виджет прогресса обработки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Готов к запуску")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Файл", "Статус", "Строк до", "Строк после", "Время (сек)"])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def set_progress(self, current, total, filename):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Обработка: {filename} [{current}/{total}]")

    def add_result(self, stats):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(stats.get("file_name", "")))
        self.table.setItem(row, 1, QTableWidgetItem(stats.get("status", "")))

        if stats.get("status") == "error":
            self.table.item(row, 1).setForeground(QColor("red"))

        self.table.setItem(row, 2, QTableWidgetItem(str(stats.get("original_rows", ""))))
        self.table.setItem(row, 3, QTableWidgetItem(str(stats.get("rows_saved", ""))))
        self.table.setItem(row, 4, QTableWidgetItem(f"{stats.get('processing_time_sec', 0):.3f}"))

    def reset(self):
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Готов к запуску")
        self.table.setRowCount(0)


class LogWidget(QWidget):
    """Виджет логов."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 9))

        layout.addWidget(self.text_edit)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(lambda: self.text_edit.clear())
        layout.addWidget(clear_btn)

    def append_log(self, message, level):
        color = "black"
        if level == "ERROR":
            color = "red"
        elif level == "WARNING":
            color = "orange"
        elif level == "DEBUG":
            color = "gray"

        self.text_edit.append(f'<span style="color:{color}">{message}</span>')
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)
