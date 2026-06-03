from __future__ import annotations

import sys
import subprocess
import os
from dataclasses import dataclass, field
from pathlib import Path

from excel_core import DEFAULT_PREVIEW_PAGE_SIZE, load_preview_page, load_total_rows
from excel_wizard import open_excel_wizard
from PySide6 import QtWidgets, QtCore
import pandas as pd
import numpy as np


@dataclass
class PreviewState:
    """Состояние preview для одного Excel-файла"""
    file_path: str = ""
    sheet_name: str = ""
    header_row: int = 0
    offset: int = 0
    total_rows: int = 0
    page_size: int = DEFAULT_PREVIEW_PAGE_SIZE
    selected_columns: list[str] = field(default_factory=list)
    column_types: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.selected_columns is None:
            self.selected_columns = []
        if self.column_types is None:
            self.column_types = {}


class PreviewTab(QtWidgets.QWidget):
    """Вкладка для одного Excel-файла с preview таблицей"""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.preview_state = PreviewState(file_path=file_path)
        self._is_loading = False
        self._full_dataframe: pd.DataFrame | None = None
        
        self._build_ui()
        self._connect_signals()
        
        self.file_label.setText(f"Файл: {Path(file_path).name}")
        self.status_label.setText("Нажмите «Настроить книгу»")
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        info_layout = QtWidgets.QHBoxLayout()
        self.file_label = QtWidgets.QLabel("Файл: -")
        self.sheet_label = QtWidgets.QLabel("Лист: -")
        self.header_label = QtWidgets.QLabel("Шапка: -")
        info_layout.addWidget(self.file_label)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.sheet_label)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.header_label)
        info_layout.addStretch(1)
        layout.addLayout(info_layout)
        
        actions_layout = QtWidgets.QHBoxLayout()
        self.configure_button = QtWidgets.QPushButton("Настроить книгу")
        self.refresh_button = QtWidgets.QPushButton("Обновить")
        self.configure_button.setEnabled(True)
        self.refresh_button.setEnabled(False)
        actions_layout.addWidget(self.configure_button)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addStretch(1)
        layout.addLayout(actions_layout)
        
        self.status_label = QtWidgets.QLabel("Готов")
        layout.addWidget(self.status_label)
        
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)
    
    def _connect_signals(self):
        self.configure_button.clicked.connect(self._configure_workbook)
        self.refresh_button.clicked.connect(self._reload_preview_from_start)
        self.table.verticalScrollBar().valueChanged.connect(self._on_table_scroll)
    
    def _configure_workbook(self):
        result = open_excel_wizard(self, self.file_path)
        if not result:
            return
        
        self.preview_state.sheet_name = str(result.get("sheet_name", "") or "")
        self.preview_state.header_row = int(result.get("header", 0) or 0)
        self.preview_state.selected_columns = list(result.get("selected_columns", []) or [])
        self.preview_state.column_types = dict(result.get("column_types", {}) or {})
        self.preview_state.offset = 0
        
        self.preview_state.total_rows = load_total_rows(
            self.preview_state.file_path,
            self.preview_state.sheet_name,
            self.preview_state.header_row,
        )
        
        self.sheet_label.setText(f"Лист: {self.preview_state.sheet_name or '-'}")
        self.header_label.setText(f"Шапка: строка {self.preview_state.header_row + 1}")
        self.refresh_button.setEnabled(True)
        
        self._full_dataframe = None
        self._load_next_page(clear_table=True)
    
    def _reload_preview_from_start(self):
        if not self.preview_state.sheet_name:
            return
        self.preview_state.offset = 0
        self._full_dataframe = None
        self._load_next_page(clear_table=True)
    
    def _load_next_page(self, *, clear_table: bool):
        if self._is_loading:
            return
        if not self.preview_state.sheet_name:
            return
        if not clear_table and self.preview_state.offset >= self.preview_state.total_rows:
            return
        
        self._is_loading = True
        try:
            page = load_preview_page(
                self.preview_state.file_path,
                self.preview_state.sheet_name,
                self.preview_state.header_row,
                offset=self.preview_state.offset,
                limit=self.preview_state.page_size,
            )
            
            if self.preview_state.selected_columns:
                col_indices = [i for i, col in enumerate(page.columns) if col in self.preview_state.selected_columns]
                filtered_columns = [page.columns[i] for i in col_indices]
                filtered_rows = [[row[i] for i in col_indices] for row in page.rows]
                page.columns = filtered_columns
                page.rows = filtered_rows
            
            if clear_table:
                self.table.clear()
                self.table.setColumnCount(len(page.columns))
                self.table.setHorizontalHeaderLabels(page.columns)
                self.table.setRowCount(0)
            
            start_row = self.table.rowCount()
            self.table.setRowCount(start_row + len(page.rows))
            for row_index, row_values in enumerate(page.rows):
                for col_index, value in enumerate(row_values):
                    self.table.setItem(
                        start_row + row_index,
                        col_index,
                        QtWidgets.QTableWidgetItem(value),
                    )
            
            self.preview_state.offset += len(page.rows)
            shown_rows = self.table.rowCount()
            if shown_rows == 0:
                self.status_label.setText("Таблица пуста")
            else:
                self.status_label.setText(
                    f"Показаны строки: 1-{shown_rows} из {page.total_rows}"
                )
        finally:
            self._is_loading = False
    
    def _on_table_scroll(self, value: int):
        scrollbar = self.table.verticalScrollBar()
        if value < scrollbar.maximum():
            return
        self._load_next_page(clear_table=False)
    
    def _apply_column_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Применить сохраненные типы данных к DataFrame"""
        if not self.preview_state.column_types:
            return df
        
        df_result = df.copy()
        for col, col_type in self.preview_state.column_types.items():
            if col not in df_result.columns:
                continue
            
            try:
                if col_type == "Int64":
                    df_result[col] = pd.to_numeric(df_result[col], errors='coerce')
                elif col_type == "float64":
                    df_result[col] = pd.to_numeric(df_result[col], errors='coerce')
                elif col_type == "boolean":
                    true_vals = ['true', 'yes', '1', 'да', 'истина']
                    false_vals = ['false', 'no', '0', 'нет', 'ложь']
                    df_result[col] = df_result[col].astype(str).str.lower()
                    df_result[col] = df_result[col].apply(
                        lambda x: True if x in true_vals else (False if x in false_vals else pd.NA)
                    )
                elif col_type == "string":
                    df_result[col] = df_result[col].astype(str)
            except Exception as e:
                print(f"Ошибка преобразования колонки {col} в тип {col_type}: {e}")
        
        return df_result
    
    def get_full_dataframe(self) -> pd.DataFrame | None:
        """Получить ВСЕ данные таблицы с примененными типами"""
        if self._full_dataframe is not None:
            return self._full_dataframe
        
        if not self.preview_state.sheet_name:
            return None
        
        try:
            all_data = load_preview_page(
                self.preview_state.file_path,
                self.preview_state.sheet_name,
                self.preview_state.header_row,
                offset=0,
                limit=self.preview_state.total_rows,
            )
            
            if self.preview_state.selected_columns:
                col_indices = [i for i, col in enumerate(all_data.columns) if col in self.preview_state.selected_columns]
                filtered_columns = [all_data.columns[i] for i in col_indices]
                filtered_rows = [[row[i] for i in col_indices] for row in all_data.rows]
                all_data.columns = filtered_columns
                all_data.rows = filtered_rows
            
            df = pd.DataFrame(all_data.rows, columns=all_data.columns)
            df = self._apply_column_types(df)
            
            self._full_dataframe = df
            self.status_label.setText(f"Загружено всего строк: {len(df)}")
            return df
        except Exception as e:
            self.status_label.setText(f"Ошибка загрузки данных: {str(e)}")
            return None
    
    def get_preview_dataframe(self) -> pd.DataFrame | None:
        """Получить только загруженные preview данные"""
        if self.table.rowCount() == 0 or self.table.columnCount() == 0:
            return None
        
        columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        
        return pd.DataFrame(data, columns=columns)


class CompositeKeySelector(QtWidgets.QDialog):
    """Диалог выбора составного ключа из нескольких столбцов"""
    
    def __init__(self, columns: list[str], parent=None):
        super().__init__(parent)
        self.columns = columns
        self.selected_columns: list[str] = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("Выбор составного ключа")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        info_label = QtWidgets.QLabel(
            "Выберите один или несколько столбцов для составного ключа.\n"
            "Порядок столбцов важен: ключ будет формироваться как 'значение1|значение2|...'"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.column_list = QtWidgets.QListWidget()
        self.column_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        for col in self.columns:
            self.column_list.addItem(col)
        layout.addWidget(self.column_list)
        
        btn_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Выбрать все")
        clear_all_btn = QtWidgets.QPushButton("Снять все")
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(clear_all_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)
        
        order_label = QtWidgets.QLabel("Порядок столбцов в ключе (перетаскивайте для изменения):")
        layout.addWidget(order_label)
        
        self.order_list = QtWidgets.QListWidget()
        self.order_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.order_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self.order_list)
        
        order_btn_layout = QtWidgets.QHBoxLayout()
        move_up_btn = QtWidgets.QPushButton("↑ Вверх")
        move_down_btn = QtWidgets.QPushButton("↓ Вниз")
        order_btn_layout.addWidget(move_up_btn)
        order_btn_layout.addWidget(move_down_btn)
        order_btn_layout.addStretch(1)
        layout.addLayout(order_btn_layout)
        
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)
        
        select_all_btn.clicked.connect(self._select_all)
        clear_all_btn.clicked.connect(self._clear_all)
        move_up_btn.clicked.connect(self._move_up)
        move_down_btn.clicked.connect(self._move_down)
        self.column_list.itemSelectionChanged.connect(self._on_selection_changed)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        self._update_order_list()
    
    def _select_all(self):
        self.column_list.selectAll()
    
    def _clear_all(self):
        self.column_list.clearSelection()
    
    def _on_selection_changed(self):
        selected = [item.text() for item in self.column_list.selectedItems()]
        current_order = [self.order_list.item(i).text() for i in range(self.order_list.count())]
        
        new_order = [col for col in current_order if col in selected]
        for col in selected:
            if col not in new_order:
                new_order.append(col)
        
        self.order_list.clear()
        for col in new_order:
            self.order_list.addItem(col)
    
    def _update_order_list(self):
        selected = [item.text() for item in self.column_list.selectedItems()]
        self.order_list.clear()
        for col in selected:
            self.order_list.addItem(col)
    
    def _move_up(self):
        current_row = self.order_list.currentRow()
        if current_row > 0:
            item = self.order_list.takeItem(current_row)
            self.order_list.insertItem(current_row - 1, item)
            self.order_list.setCurrentRow(current_row - 1)
    
    def _move_down(self):
        current_row = self.order_list.currentRow()
        if current_row < self.order_list.count() - 1:
            item = self.order_list.takeItem(current_row)
            self.order_list.insertItem(current_row + 1, item)
            self.order_list.setCurrentRow(current_row + 1)
    
    def get_selected_columns(self) -> list[str]:
        return [self.order_list.item(i).text() for i in range(self.order_list.count())]


class ComparisonResultWidget(QtWidgets.QWidget):
    """Виджет для отображения результата сравнения двух таблиц"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        self.title_label = QtWidgets.QLabel("Результат сравнения")
        self.title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        self.stats_label = QtWidgets.QLabel("")
        layout.addWidget(self.stats_label)
        
        self.result_table = QtWidgets.QTableWidget()
        self.result_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        layout.addWidget(self.result_table, 1)
    
    def set_comparison_result(self, result_df: pd.DataFrame, left_name: str, right_name: str, key_columns: list[str]):
        key_str = " + ".join(key_columns)
        self.title_label.setText(f"Результат сравнения: {left_name} vs {right_name} (по ключу '{key_str}')")
        
        total_rows = len(result_df)
        only_left = sum(result_df["_comparison_status"] == "только в левой")
        only_right = sum(result_df["_comparison_status"] == "только в правой")
        different = sum(result_df["_comparison_status"] == "различаются")
        
        self.stats_label.setText(
            f"Всего записей с различиями: {total_rows} | "
            f"⚠️ Различаются значения: {different} | "
            f"📌 Только в '{left_name}': {only_left} | "
            f"📌 Только в '{right_name}': {only_right}"
        )
        
        display_df = result_df.drop(columns=["_comparison_status"])
        self.result_table.clear()
        self.result_table.setColumnCount(len(display_df.columns))
        self.result_table.setHorizontalHeaderLabels(display_df.columns)
        self.result_table.setRowCount(len(display_df))
        
        for row_idx, row in display_df.iterrows():
            for col_idx, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(value))
                status = result_df.iloc[row_idx]["_comparison_status"]
                if status == "только в левой":
                    item.setBackground(QtCore.Qt.GlobalColor.cyan)
                elif status == "только в правой":
                    item.setBackground(QtCore.Qt.GlobalColor.lightGray)
                elif status == "различаются":
                    item.setBackground(QtCore.Qt.GlobalColor.yellow)
                self.result_table.setItem(row_idx, col_idx, item)
        
        self.result_table.resizeColumnsToContents()
    
    def get_result_dataframe(self) -> pd.DataFrame | None:
        if self.result_table.rowCount() == 0:
            return None
        
        columns = [self.result_table.horizontalHeaderItem(i).text() for i in range(self.result_table.columnCount())]
        data = []
        for row in range(self.result_table.rowCount()):
            row_data = []
            for col in range(self.result_table.columnCount()):
                item = self.result_table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        
        return pd.DataFrame(data, columns=columns)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Excel Preview — сравнение таблиц (только различия)")
        self.resize(1300, 800)
        self._last_comparison_result: pd.DataFrame | None = None
        self._last_key_columns: list[str] = []
        self._last_comparison_info = None
        
        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self):
        """Построение интерфейса главного окна"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Верхняя панель с кнопками
        toolbar = QtWidgets.QHBoxLayout()
        self.add_file_button = QtWidgets.QPushButton("➕ Добавить файл")
        self.compare_button = QtWidgets.QPushButton("🔍 Сравнить таблицы")
        self.save_all_button = QtWidgets.QPushButton("💾 Сохранить preview.xlsx")
        
        toolbar.addWidget(self.add_file_button)
        toolbar.addWidget(self.compare_button)
        toolbar.addWidget(self.save_all_button)
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)
        
        # Вкладки с файлами
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(True)
        main_layout.addWidget(self.tab_widget, 1)
        
        # Виджет результата сравнения
        self.comparison_widget = ComparisonResultWidget()
        self.comparison_widget.setVisible(False)
        main_layout.addWidget(self.comparison_widget)
        
        # Строка состояния
        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Готов")
    
    def _connect_signals(self):
        """Подключение сигналов"""
        self.add_file_button.clicked.connect(self._add_file)
        self.compare_button.clicked.connect(self._show_comparison_dialog)
        self.save_all_button.clicked.connect(self._save_all_previews)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
    
    def _add_file(self):
        """Добавление нового Excel файла"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Выберите Excel файл",
            "",
            "Excel files (*.xlsx *.xls);;CSV files (*.csv);;All files (*.*)"
        )
        
        if not file_path:
            return
        
        # Проверяем, не открыт ли уже этот файл
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, PreviewTab) and tab.file_path == file_path:
                self.tab_widget.setCurrentIndex(i)
                self.statusbar.showMessage(f"Файл уже открыт: {Path(file_path).name}")
                return
        
        tab = PreviewTab(file_path)
        tab_name = Path(file_path).name
        self.tab_widget.addTab(tab, tab_name)
        self.tab_widget.setCurrentWidget(tab)
        self.statusbar.showMessage(f"Добавлен файл: {tab_name}")
    
    def _close_tab(self, index: int):
        """Закрытие вкладки"""
        tab = self.tab_widget.widget(index)
        if tab:
            self.tab_widget.removeTab(index)
            tab.deleteLater()
            self.statusbar.showMessage("Вкладка закрыта")
    
    def _normalize_value(self, value: any, col_type: str = "auto") -> any:
        """Нормализовать значение с учетом типа данных"""
        if pd.isna(value) or value == "":
            return None
        
        if col_type in ("Int64", "float64"):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif col_type == "boolean":
            str_val = str(value).lower()
            if str_val in ("true", "yes", "1", "да", "истина"):
                return True
            elif str_val in ("false", "no", "0", "нет", "ложь"):
                return False
            return None
        else:
            return str(value).strip()
    
    def _compare_values(self, val_left: any, val_right: any, col_type: str) -> tuple[bool, str | None]:
        """Сравнить два значения с учетом типа данных"""
        norm_left = self._normalize_value(val_left, col_type)
        norm_right = self._normalize_value(val_right, col_type)
        
        if norm_left is None and norm_right is None:
            return True, None
        if norm_left is None or norm_right is None:
            str_left = str(val_left) if not pd.isna(val_left) else "(пусто)"
            str_right = str(val_right) if not pd.isna(val_right) else "(пусто)"
            return False, f"{str_left} ≠ {str_right}"
        
        if col_type in ("Int64", "float64"):
            try:
                diff = float(norm_left) - float(norm_right)
                if abs(diff) < 1e-9:
                    return True, None
                else:
                    return False, f"{norm_left} ≠ {norm_right}"
            except (ValueError, TypeError):
                return False, f"{norm_left} ≠ {norm_right}"
        
        if norm_left == norm_right:
            return True, None
        else:
            return False, f"{norm_left} ≠ {norm_right}"
    
    def _compare_tables(self, left_tab: PreviewTab, right_tab: PreviewTab, left_name: str, right_name: str, key_columns: list[str]):
        """Сравнить две таблицы, выводим только строки с различиями"""
        df_left = left_tab.get_full_dataframe()
        df_right = right_tab.get_full_dataframe()
        
        if df_left is None or df_right is None:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Не удалось загрузить данные для сравнения.")
            return
        
        missing_in_left = [col for col in key_columns if col not in df_left.columns]
        missing_in_right = [col for col in key_columns if col not in df_right.columns]
        
        if missing_in_left:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Столбцы {missing_in_left} не найдены в таблице '{left_name}'.")
            return
        if missing_in_right:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Столбцы {missing_in_right} не найдены в таблице '{right_name}'.")
            return
        
        left_types = left_tab.preview_state.column_types
        right_types = right_tab.preview_state.column_types
        
        df_left_copy = df_left.copy()
        df_right_copy = df_right.copy()
        
        def make_composite_key(row, cols):
            parts = []
            for col in cols:
                val = row.get(col, "")
                if pd.isna(val):
                    val = ""
                parts.append(str(val).strip())
            return "|".join(parts)
        
        df_left_copy["_composite_key"] = df_left_copy.apply(lambda row: make_composite_key(row, key_columns), axis=1)
        df_right_copy["_composite_key"] = df_right_copy.apply(lambda row: make_composite_key(row, key_columns), axis=1)
        
        all_keys = set(df_left_copy["_composite_key"]) | set(df_right_copy["_composite_key"])
        all_columns = set(df_left.columns) | set(df_right.columns)
        compare_columns = [col for col in all_columns if col not in key_columns]
        
        result_rows = []
        
        for key in all_keys:
            row_left = df_left_copy[df_left_copy["_composite_key"] == key]
            row_right = df_right_copy[df_right_copy["_composite_key"] == key]
            
            key_parts = key.split("|")
            row_data = {}
            for i, col in enumerate(key_columns):
                row_data[col] = key_parts[i] if i < len(key_parts) else ""
            
            if row_left.empty and not row_right.empty:
                status = "только в правой"
                for col in compare_columns:
                    if col in df_right.columns:
                        row_data[col] = row_right.iloc[0][col]
                    else:
                        row_data[col] = ""
                result_rows.append({**row_data, "_comparison_status": status})
            
            elif not row_left.empty and row_right.empty:
                status = "только в левой"
                for col in compare_columns:
                    if col in df_left.columns:
                        row_data[col] = row_left.iloc[0][col]
                    else:
                        row_data[col] = ""
                result_rows.append({**row_data, "_comparison_status": status})
            
            else:
                diff_found = False
                row_diff_data = row_data.copy()
                
                for col in compare_columns:
                    val_left = row_left.iloc[0][col] if col in df_left.columns else None
                    val_right = row_right.iloc[0][col] if col in df_right.columns else None
                    col_type = left_types.get(col, right_types.get(col, "auto"))
                    
                    are_equal, diff_str = self._compare_values(val_left, val_right, col_type)
                    
                    if not are_equal:
                        diff_found = True
                        row_diff_data[col] = diff_str
                    else:
                        val = val_left if not pd.isna(val_left) else val_right
                        row_diff_data[col] = val if not pd.isna(val) else ""
                
                if diff_found:
                    row_diff_data["_comparison_status"] = "различаются"
                    result_rows.append(row_diff_data)
        
        if not result_rows:
            QtWidgets.QMessageBox.information(self, "Результат", "Различий не найдено. Таблицы полностью совпадают.")
            self.comparison_widget.setVisible(False)
            self._last_comparison_result = None
            self._last_comparison_info = None
            return
        
        result_df = pd.DataFrame(result_rows)
        
        status_order = {"различаются": 0, "только в левой": 1, "только в правой": 2}
        result_df["_order"] = result_df["_comparison_status"].map(status_order)
        result_df = result_df.sort_values("_order").drop(columns=["_order"])
        
        self.comparison_widget.set_comparison_result(result_df, left_name, right_name, key_columns)
        self.comparison_widget.setVisible(True)
        
        self._last_comparison_result = result_df
        self._last_key_columns = key_columns
        self.statusbar.showMessage(f"Найдено различий: {len(result_df)} записей")
    
    def _show_comparison_dialog(self):
        """Показать диалог выбора таблиц и составного ключа"""
        if self.tab_widget.count() < 2:
            QtWidgets.QMessageBox.warning(self, "Недостаточно таблиц", "Для сравнения нужно минимум 2 таблицы.")
            return
        
        tabs = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, PreviewTab) and tab.get_full_dataframe() is not None:
                tabs.append((i, tab, self.tab_widget.tabText(i)))
        
        if len(tabs) < 2:
            QtWidgets.QMessageBox.warning(self, "Нет данных", "Убедитесь, что таблицы настроены (нажата кнопка 'Настроить книгу').")
            return
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Сравнение таблиц")
        dialog.setMinimumWidth(450)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        left_layout = QtWidgets.QHBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("Левая таблица:"))
        left_combo = QtWidgets.QComboBox()
        for idx, _, name in tabs:
            left_combo.addItem(name, idx)
        left_layout.addWidget(left_combo)
        layout.addLayout(left_layout)
        
        right_layout = QtWidgets.QHBoxLayout()
        right_layout.addWidget(QtWidgets.QLabel("Правая таблица:"))
        right_combo = QtWidgets.QComboBox()
        for idx, _, name in tabs:
            right_combo.addItem(name, idx)
        right_combo.setCurrentIndex(min(1, len(tabs) - 1))
        right_layout.addWidget(right_combo)
        layout.addLayout(right_layout)
        
        key_button_layout = QtWidgets.QHBoxLayout()
        self.key_label = QtWidgets.QLabel("Ключевые столбцы: не выбраны")
        self.key_label.setWordWrap(True)
        select_key_btn = QtWidgets.QPushButton("Выбрать ключевые столбцы...")
        select_key_btn.setEnabled(False)
        key_button_layout.addWidget(self.key_label, 1)
        key_button_layout.addWidget(select_key_btn)
        layout.addLayout(key_button_layout)
        
        selected_key_columns: list[str] = []
        
        def on_left_table_changed():
            left_idx = left_combo.currentData()
            left_tab = tabs[left_idx][1] if 0 <= left_idx < len(tabs) else None
            if left_tab:
                df = left_tab.get_full_dataframe()
                select_key_btn.setEnabled(df is not None and not df.empty)
            else:
                select_key_btn.setEnabled(False)
        
        def on_select_key():
            nonlocal selected_key_columns
            left_idx = left_combo.currentData()
            left_tab = tabs[left_idx][1] if 0 <= left_idx < len(tabs) else None
            if left_tab:
                df = left_tab.get_full_dataframe()
                if df is not None and not df.empty:
                    selector = CompositeKeySelector(df.columns.tolist(), dialog)
                    if selector.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_key_columns = selector.get_selected_columns()
                        if selected_key_columns:
                            self.key_label.setText(f"Ключевые столбцы: {' + '.join(selected_key_columns)}")
                        else:
                            self.key_label.setText("Ключевые столбцы: не выбраны")
        
        left_combo.currentIndexChanged.connect(on_left_table_changed)
        select_key_btn.clicked.connect(on_select_key)
        on_left_table_changed()
        
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        
        if not selected_key_columns:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один ключевой столбец.")
            return
        
        left_idx = left_combo.currentData()
        right_idx = right_combo.currentData()
        
        left_tab = tabs[left_idx][1]
        right_tab = tabs[right_idx][1]
        left_name = tabs[left_idx][2]
        right_name = tabs[right_idx][2]
        
        self._last_comparison_info = (left_idx, right_idx, tabs, left_name, right_name)
        
        self._compare_tables(left_tab, right_tab, left_name, right_name, selected_key_columns)
    
    def _open_file_with_default_app(self, file_path: Path):
        """Открыть файл в Linux: сначала пробуем LibreOffice, затем xdg-open"""
        if not file_path.exists():
            return False
        
        commands = [
            ["libreoffice", "--calc", str(file_path)],
            ["libreoffice", str(file_path)],
            ["soffice", "--calc", str(file_path)],
            ["soffice", str(file_path)],
            ["xdg-open", str(file_path)],
        ]
        
        for cmd in commands:
            try:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return True
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
        
        return False
    
    def _save_all_previews(self):
        """Сохранить ВСЕ строки каждого файла и ТОЛЬКО РАЗЛИЧИЯ на лист result"""
        if self.tab_widget.count() == 0:
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Сохранение preview",
            f"Сохранить ВСЕ строки ({self.tab_widget.count()} таблиц) и РАЗЛИЧИЯ в файл 'preview.xlsx'?\n\n"
            "Каждая таблица будет на отдельном листе.\n"
            "На лист 'result' будут выведены ТОЛЬКО строки с различиями.\n"
            "Для всех столбцов показывается формат 'значение1 ≠ значение2'.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        output_path = Path.cwd() / "preview.xlsx"
        
        try:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                saved_count = 0
                
                for i in range(self.tab_widget.count()):
                    tab = self.tab_widget.widget(i)
                    if not isinstance(tab, PreviewTab):
                        continue
                    
                    df = tab.get_full_dataframe()
                    if df is None or df.empty:
                        self.statusbar.showMessage(f"Нет данных для {Path(tab.file_path).name}")
                        continue
                    
                    sheet_name = Path(tab.file_path).stem[:31]
                    original_name = sheet_name
                    counter = 1
                    while sheet_name in writer.book.sheetnames:
                        sheet_name = f"{original_name[:27]}_{counter}"
                        counter += 1
                    
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    saved_count += 1
                    self.statusbar.showMessage(f"Сохранено: {sheet_name} ({len(df)} строк)")
                
                if self._last_comparison_result is not None and not self._last_comparison_result.empty:
                    save_df = self._last_comparison_result.drop(columns=["_comparison_status"], errors='ignore')
                    save_df.to_excel(writer, sheet_name="result", index=False)
                    saved_count += 1
                    self.statusbar.showMessage(f"Сохранены различия: {len(save_df)} строк на листе 'result'")
                else:
                    empty_df = pd.DataFrame({"Сообщение": ["Различий не найдено. Таблицы полностью совпадают."]})
                    empty_df.to_excel(writer, sheet_name="result", index=False)
                    self.statusbar.showMessage("Различий не найдено, создан лист 'result' с пояснением")
            
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setWindowTitle("Сохранение завершено")
            msg_box.setText(f"Файл сохранен:\n{output_path}\n\nСохранено {saved_count} листов.")
            msg_box.setInformativeText("Открыть файл?")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
            
            if msg_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
                if self._open_file_with_default_app(output_path):
                    self.statusbar.showMessage(f"Файл открыт: {output_path}")
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Ошибка",
                        "Не удалось открыть файл.\n\n"
                        "Убедитесь, что установлен LibreOffice или другой редактор Excel.\n"
                        "Файл сохранен по пути:\n" + str(output_path)
                    )
            
            self.statusbar.showMessage(f"Сохранено {saved_count} листов в {output_path}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить файл:\n{str(e)}"
            )
            self.statusbar.showMessage(f"Ошибка: {str(e)}")


def main() -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
