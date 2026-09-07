import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit, QSpinBox,
    QGroupBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar, QLineEdit, QComboBox,
    QCheckBox, QScrollArea, QFormLayout, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QMenu, QMenuBar, QToolBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QIcon, QAction, QColor

from read_csv_with_schema import read_csv_with_schema_v1
# ИЗМЕНЕНО: используем фабрику вместо прямого импорта класса
from data_frame_comparator import create_comparator, InMemoryComparator


class SchemaManager:
    """Менеджер для работы со схемами данных"""
    
    def __init__(self):
        # Путь к файлу схем относительно main.py
        self.schema_file = self._get_schema_file_path()
        self.schemas = {}
        self._ensure_default_schemas()
        self.load_schemas()
    
    def _get_schema_file_path(self) -> str:
        """Получение пути к файлу схем относительно main.py"""
        # Получаем путь к каталогу main.py
        main_dir = Path(__file__).parent.resolve()
        return str(main_dir / "schemas.json")
    
    def _ensure_default_schemas(self):
        """Создание файла со схемами по умолчанию, если он не существует"""
        if not os.path.exists(self.schema_file):
            default_schemas = {
                "schemas": {
                    "Стандартная (12 полей)": {
                        'schema': {
                            "Код ЦФО": "string",
                            "Статья Hyperion Forecast": "string",
                            "Источник аллокации": "string",
                            "Сегмент для отчета": "string",
                            "Квартал": "string",
                            "Значение": "float",
                            "Пользовательская": "string",
                            "Версия": "string",
                            "План/Прогноз": "string",
                            "Группировка для анализа": "string",
                            "ДЗО": "string",
                            "БЕ": "string"
                        },
                        'key_columns': [
                            "Код ЦФО", "Статья Hyperion Forecast", 
                            "Источник аллокации", "Сегмент для отчета", 
                            "Квартал", "ДЗО"
                        ],
                        'tolerance': 0.0
                    },
                    "DZO Revenue Forecast 9+3": {
                        'schema': {
                            "Код ДЗО Forecast": "string",
                            "Код ЦФО": "string",
                            "Статья Hyperion Forecast": "string",
                            "Сегмент для отчета": "string",
                            "Источник аллокации": "string",
                            "Q3": "string",
                            "Q4": "float",
                            "Jul": "float",
                            "Aug": "float",
                            "Sep": "float",
                            "Oct": "float",
                            "Nov": "float",
                            "Dec": "float"
                        },
                        'key_columns': [
                            "Код ДЗО Forecast", "Код ЦФО",
                            "Статья Hyperion Forecast", "Сегмент для отчета",
                            "Источник аллокации"
                        ],
                        'tolerance': 0.0001
                    },
                    "DZO Revenue Forecast (Q)": {
                        'schema': {
                            "Код ДЗО Forecast": "string",
                            "Код ЦФО": "string",
                            "Статья Hyperion Forecast": "string",
                            "Сегмент для отчета": "string",
                            "Источник аллокации": "string",
                            "Квартал": "string",
                            "Значение": "float"
                        },
                        'key_columns': [
                            "Код ДЗО Forecast", "Код ЦФО",
                            "Статья Hyperion Forecast", "Сегмент для отчета",
                            "Источник аллокации", "Квартал"
                        ],
                        'tolerance': 0.0
                    },
                    "DZO Percent": {
                        'schema': {
                            "Код ДЗО Forecast": "string",
                            "Сегмент для отчета": "string",
                            "%": "float"
                        },
                        'key_columns': [
                            "Код ДЗО Forecast", "Сегмент для отчета"
                        ],
                        'tolerance': 0.0
                    }
                }
            }
            
            try:
                with open(self.schema_file, 'w', encoding='utf-8') as f:
                    json.dump(default_schemas, f, ensure_ascii=False, indent=2)
                print(f"Создан файл схем по умолчанию: {self.schema_file}")
            except Exception as e:
                print(f"Ошибка создания файла схем: {e}")
    
    def load_schemas(self):
        """Загрузка схем из JSON файла"""
        if os.path.exists(self.schema_file):
            try:
                with open(self.schema_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.schemas = data.get('schemas', {})
                    
                    # Проверяем, что каждая схема имеет поле tolerance
                    for name, schema_data in self.schemas.items():
                        if 'tolerance' not in schema_data:
                            schema_data['tolerance'] = 0.0
                    
                    print(f"Загружено {len(self.schemas)} схем из {self.schema_file}")
            except Exception as e:
                print(f"Ошибка загрузки схем: {e}")
                self.schemas = {}
        else:
            print(f"Файл схем не найден: {self.schema_file}")
            self.schemas = {}
    
    def save_schemas(self):
        """Сохранение схем в JSON файл"""
        try:
            with open(self.schema_file, 'w', encoding='utf-8') as f:
                json.dump({'schemas': self.schemas}, f, ensure_ascii=False, indent=2)
            print(f"Схемы сохранены в {self.schema_file}")
            return True
        except Exception as e:
            print(f"Ошибка сохранения схем: {e}")
            return False
    
    def get_schema(self, name: str) -> Dict:
        """Получение схемы по имени"""
        return self.schemas.get(name, {})
    
    def add_schema(self, name: str, schema: Dict, key_columns: List[str] = None, tolerance: float = 0.0):
        """Добавление или обновление схемы"""
        self.schemas[name] = {
            'schema': schema,
            'key_columns': key_columns or [],
            'tolerance': tolerance
        }
        return self.save_schemas()
    
    def update_schema(self, old_name: str, new_name: str, schema: Dict, key_columns: List[str] = None, tolerance: float = 0.0):
        """Обновление схемы с возможностью переименования"""
        # Если имя изменилось, удаляем старую схему
        if old_name != new_name and old_name in self.schemas:
            del self.schemas[old_name]
        
        self.schemas[new_name] = {
            'schema': schema,
            'key_columns': key_columns or [],
            'tolerance': tolerance
        }
        return self.save_schemas()
    
    def delete_schema(self, name: str) -> bool:
        """Удаление схемы"""
        if name in self.schemas:
            del self.schemas[name]
            return self.save_schemas()
        return False
    
    def get_schema_names(self) -> List[str]:
        """Получение списка имен схем"""
        return list(self.schemas.keys())
    
    def get_schema_file_path(self) -> str:
        """Получение пути к файлу схем"""
        return self.schema_file


def check_key_uniqueness(df: pd.DataFrame, key_columns: List[str], df_name: str = "") -> Tuple[bool, List[Tuple]]:
    """
    Проверка уникальности ключа в датафрейме
    
    Args:
        df: Датафрейм для проверки
        key_columns: Список ключевых столбцов
        df_name: Имя датафрейма для сообщения
    
    Returns:
        Tuple[bool, List[Tuple]]: (уникален ли ключ, список неуникальных ключей)
    """
    if not key_columns:
        return True, []
    
    # Проверяем, что все ключевые столбцы есть в датафрейме
    missing_columns = [col for col in key_columns if col not in df.columns]
    if missing_columns:
        return True, []  # Пропускаем проверку если нет столбцов
    
    # Создаем составной ключ
    df_temp = df.copy()
    df_temp['_composite_key'] = df_temp[key_columns].astype(str).agg('|'.join, axis=1)
    
    # Находим дубликаты
    duplicates = df_temp['_composite_key'].duplicated(keep=False)
    
    if duplicates.any():
        # Получаем неуникальные ключи
        duplicate_keys = df_temp[duplicates]['_composite_key'].unique().tolist()
        
        # Декодируем ключи обратно в кортежи
        decoded_keys = []
        for key in duplicate_keys:
            values = key.split('|')
            decoded_keys.append(tuple(values))
        
        return False, decoded_keys
    
    return True, []


def find_duplicate_rows(df: pd.DataFrame, key_columns: List[str]) -> pd.DataFrame:
    """
    Поиск дублирующихся строк по ключу
    
    Args:
        df: Датафрейм для проверки
        key_columns: Список ключевых столбцов
    
    Returns:
        pd.DataFrame: Датафрейм с дублирующимися строками
    """
    if not key_columns:
        return pd.DataFrame()
    
    # Проверяем, что все ключевые столбцы есть в датафрейме
    missing_columns = [col for col in key_columns if col not in df.columns]
    if missing_columns:
        return pd.DataFrame()
    
    # Находим дубликаты
    duplicates = df[df.duplicated(subset=key_columns, keep=False)]
    
    if not duplicates.empty:
        # Добавляем счетчик вхождений
        duplicates = duplicates.copy()
        duplicates['_count'] = duplicates.groupby(key_columns).cumcount() + 1
        duplicates['_total'] = duplicates.groupby(key_columns)['_count'].transform('max')
        
        # Сортируем для удобства просмотра
        duplicates = duplicates.sort_values(by=key_columns + ['_count'])
    
    return duplicates


class SchemaEditorDialog(QDialog):
    """Диалог для редактирования схемы"""
    
    def __init__(self, schema_manager: SchemaManager, schema_name: str = "", 
                 schema_data: Dict = None, parent=None):
        super().__init__(parent)
        self.schema_manager = schema_manager
        self.schema_name = schema_name
        self.schema_data = schema_data or {'schema': {}, 'key_columns': [], 'tolerance': 0.0}
        self.result = None
        
        self.setWindowTitle(f"Редактирование схемы: {schema_name}" if schema_name else "Новая схема")
        self.setMinimumSize(600, 550)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Имя схемы
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Имя схемы:"))
        self.name_edit = QLineEdit(self.schema_name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Редактор схемы
        layout.addWidget(QLabel("Столбцы (формат: имя:тип):"))
        self.schema_edit = QTextEdit()
        schema_text = "\n".join(
            [f"{col}:{dtype}" for col, dtype in self.schema_data['schema'].items()]
        )
        self.schema_edit.setText(schema_text)
        layout.addWidget(self.schema_edit)
        
        # Ключевые столбцы
        layout.addWidget(QLabel("Ключевые столбцы (через запятую):"))
        self.key_columns_edit = QLineEdit()
        if self.schema_data['key_columns']:
            self.key_columns_edit.setText(", ".join(self.schema_data['key_columns']))
        layout.addWidget(self.key_columns_edit)
        
        # Точность
        tolerance_layout = QHBoxLayout()
        tolerance_layout.addWidget(QLabel("Точность сравнения (0 - точное совпадение):"))
        self.tolerance_spin = QSpinBox()
        self.tolerance_spin.setRange(0, 1000000)
        tolerance_value = int(self.schema_data.get('tolerance', 0) * 1000000)
        self.tolerance_spin.setValue(tolerance_value)
        self.tolerance_spin.setSuffix(" (10⁻⁶)")
        tolerance_layout.addWidget(self.tolerance_spin)
        layout.addLayout(tolerance_layout)

        
        # Информация о файле
        info_label = QLabel(f"Схемы сохраняются в: {self.schema_manager.get_schema_file_path()}")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept_schema)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def accept_schema(self):
        """Обработка подтверждения"""
        try:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Предупреждение", "Введите имя схемы!")
                return
            
            # Парсим схему
            schema_text = self.schema_edit.toPlainText().strip()
            if not schema_text:
                QMessageBox.warning(self, "Предупреждение", "Схема пуста!")
                return
            
            schema = {}
            for line in schema_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Неверный формат строки: {line}")
                
                col_name = parts[0].strip()
                col_type = parts[1].strip().lower()
                
                if col_type not in ["string", "float", "int", "bool"]:
                    raise ValueError(f"Неподдерживаемый тип '{col_type}'")
                
                schema[col_name] = col_type
            
            # Парсим ключевые столбцы
            key_text = self.key_columns_edit.text().strip()
            key_columns = [col.strip() for col in key_text.split(",")] if key_text else []
            
            # Проверяем, что все ключевые столбцы есть в схеме
            for col in key_columns:
                if col not in schema:
                    QMessageBox.warning(
                        self, "Предупреждение",
                        f"Ключевой столбец '{col}' не найден в схеме!"
                    )
                    return
            
            # Получаем точность
            tolerance = self.tolerance_spin.value() / 1_000_000
            
            self.result = {
                'name': name,
                'schema': schema,
                'key_columns': key_columns,
                'tolerance': tolerance
            }
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))



# ============================================================
# НОВЫЙ КЛАСС CompareWorker с поддержкой чанкового режима
# ============================================================
class CompareWorker(QThread):
    """Поток для выполнения сравнения без блокировки UI"""
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)
    key_uniqueness_warning = Signal(str, str)

    def __init__(self, df1, df2, schema, compare_columns, tolerance,
                 use_chunked=False, df1_path=None, df2_path=None,
                 chunksize=50000, encoding='utf-8', csv_separator=','):
        super().__init__()
        self.df1 = df1
        self.df2 = df2
        self.schema = schema
        self.compare_columns = compare_columns
        self.tolerance = tolerance
        self.use_chunked = use_chunked
        self.df1_path = df1_path
        self.df2_path = df2_path
        self.chunksize = chunksize
        self.encoding = encoding
        self.csv_separator = csv_separator
    
    def run(self):
        comparator = None 
        try:
            self.progress.emit("Создание компаратора...")
            # ИСПОЛЬЗУЕМ ФАБРИКУ
            comparator = create_comparator(
                self.df1, self.df2,
                self.compare_columns,
                self.schema,
                self.tolerance,
                use_chunked=self.use_chunked,
                df1_path=self.df1_path,
                df2_path=self.df2_path,
                chunksize=self.chunksize,
                encoding=self.encoding,
                separator=self.csv_separator
            )

            if self.use_chunked:
                self.progress.emit("Загрузка данных в БД (чанками)...")
                comparator.load_data()

            self.progress.emit("Выполнение сравнения...")
            if self.use_chunked:
                # Чанковый компаратор: compare() заполняет атрибуты
                comparator.compare()
                # Для единообразия сохраняем результаты в те же поля
                # (они уже есть)
            else:
                # In-memory компаратор
                comparator.compare()

            self.progress.emit("Сравнение завершено!")
            self.finished.emit(comparator)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Закрываем соединение с БД, если оно есть
            if hasattr(comparator, 'close'):
                comparator.close()


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.comparator = None
        self.df1 = None
        self.df2 = None
        self.current_schema = {}
        self.current_compare_columns = []
        self.current_tolerance = 0.0
        self.output_dir = Path("./tmp/Results/compare_csv")
        self.schema_manager = SchemaManager()
        self.key_uniqueness_warnings = []

        self.init_ui()
        self._load_schema_list()

        if self.schema_combo.count() > 0:
            self.apply_schema_template(self.schema_combo.currentText())

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Сравнение DataFrame")
        self.setMinimumSize(1400, 900)

        self._create_menu()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)

        file_panel = self._create_file_panel()
        top_layout.addWidget(file_panel)

        settings_panel = self._create_settings_panel()
        top_layout.addWidget(settings_panel)

        main_layout.addWidget(top_panel)

        splitter = QSplitter(Qt.Vertical)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumHeight(150)
        font = QFont("Courier New", 9)
        self.log_panel.setFont(font)
        splitter.addWidget(self.log_panel)

        self.results_tabs = QTabWidget()
        splitter.addWidget(self.results_tabs)

        main_layout.addWidget(splitter)

        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        self._update_button_states()

    def _create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        # Выбор каталога для результатов
        set_output_dir_action = QAction("Выбрать каталог для результатов...", self)
        set_output_dir_action.triggered.connect(self._select_output_dir)
        file_menu.addAction(set_output_dir_action)
        
        file_menu.addSeparator()
        
        # Открыть файл схем
        open_schemas_action = QAction("Открыть файл схем...", self)
        open_schemas_action.triggered.connect(self._open_schemas_file)
        file_menu.addAction(open_schemas_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Схемы
        schemas_menu = menubar.addMenu("Схемы")
        
        add_schema_action = QAction("Создать новую схему...", self)
        add_schema_action.triggered.connect(self._add_schema)
        schemas_menu.addAction(add_schema_action)
        
        edit_schema_action = QAction("Редактировать текущую схему...", self)
        edit_schema_action.triggered.connect(self._edit_current_schema)
        schemas_menu.addAction(edit_schema_action)
        
        delete_schema_action = QAction("Удалить текущую схему", self)
        delete_schema_action.triggered.connect(self._delete_current_schema)
        schemas_menu.addAction(delete_schema_action)
        
        schemas_menu.addSeparator()
        
        reload_schemas_action = QAction("Перезагрузить схемы из файла", self)
        reload_schemas_action.triggered.connect(self._reload_schemas)
        schemas_menu.addAction(reload_schemas_action)

    def _create_file_panel(self) -> QGroupBox:
        """Создание панели выбора файлов"""
        group = QGroupBox("Выбор файлов для сравнения")
        layout = QVBoxLayout(group)
        
        # Файл 1 (эталон)
        file1_layout = QHBoxLayout()
        file1_layout.addWidget(QLabel("Файл 1 (эталон):"))
        self.file1_path = QLineEdit()
        self.file1_path.setPlaceholderText("Выберите CSV файл...")
        file1_layout.addWidget(self.file1_path)
        btn_file1 = QPushButton("Обзор...")
        btn_file1.clicked.connect(lambda: self._select_file(1))
        file1_layout.addWidget(btn_file1)
        layout.addLayout(file1_layout)
        
        # Файл 2 (сравнение)
        file2_layout = QHBoxLayout()
        file2_layout.addWidget(QLabel("Файл 2 (сравнение):"))
        self.file2_path = QLineEdit()
        self.file2_path.setPlaceholderText("Выберите CSV файл...")
        file2_layout.addWidget(self.file2_path)
        btn_file2 = QPushButton("Обзор...")
        btn_file2.clicked.connect(lambda: self._select_file(2))
        file2_layout.addWidget(btn_file2)
        layout.addLayout(file2_layout)
        
        # Каталог для результатов
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Каталог результатов:"))
        self.output_path = QLineEdit(str(self.output_dir))
        output_layout.addWidget(self.output_path)
        btn_output = QPushButton("Обзор...")
        btn_output.clicked.connect(self._select_output_dir)
        output_layout.addWidget(btn_output)
        layout.addLayout(output_layout)

        # Разделитель CSV
        sep_layout = QHBoxLayout()
        sep_layout.addWidget(QLabel("Разделитель CSV:"))
        self.sep_combo = QComboBox()
        self.sep_combo.addItems([",", ";", "\t", "|"])
        self.sep_combo.setCurrentText(",")
        sep_layout.addWidget(self.sep_combo)
        sep_layout.addStretch()
        layout.addLayout(sep_layout)

        return group

    def _create_settings_panel(self) -> QGroupBox:
        """Создание панели настроек с добавлением чанкового режима"""
        group = QGroupBox("Настройки сравнения")
        layout = QHBoxLayout(group)

        # Левая колонка: схема
        schema_layout = QVBoxLayout()

        # Выбор шаблона схемы
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Шаблон схемы:"))
        self.schema_combo = QComboBox()
        self.schema_combo.currentTextChanged.connect(self.apply_schema_template)
        template_layout.addWidget(self.schema_combo)

        btn_add_schema = QPushButton("+")
        btn_add_schema.setMaximumWidth(30)
        btn_add_schema.clicked.connect(self._add_schema)
        template_layout.addWidget(btn_add_schema)

        btn_edit_schema = QPushButton("✏")
        btn_edit_schema.setMaximumWidth(30)
        btn_edit_schema.clicked.connect(self._edit_current_schema)
        template_layout.addWidget(btn_edit_schema)

        btn_delete_schema = QPushButton("✕")
        btn_delete_schema.setMaximumWidth(30)
        btn_delete_schema.clicked.connect(self._delete_current_schema)
        template_layout.addWidget(btn_delete_schema)

        schema_layout.addLayout(template_layout)

        # Редактор схемы
        schema_layout.addWidget(QLabel("Столбцы (имя:тип):"))
        self.schema_editor = QTextEdit()
        self.schema_editor.setMaximumHeight(100)
        self.schema_editor.setPlaceholderText(
            "Формат: столбец:тип\nНапример:\nКод ЦФО:string\nЗначение:float"
        )
        schema_layout.addWidget(self.schema_editor)

        # Ключевые столбцы
        schema_layout.addWidget(QLabel("Ключевые столбцы (через запятую):"))
        self.key_columns_edit = QLineEdit()
        self.key_columns_edit.setPlaceholderText(
            "Код ЦФО, Статья Hyperion Forecast, ..."
        )
        schema_layout.addWidget(self.key_columns_edit)

        # Кнопки для схемы
        schema_buttons = QHBoxLayout()
        btn_apply_schema = QPushButton("Применить схему")
        btn_apply_schema.clicked.connect(self._apply_custom_schema)
        schema_buttons.addWidget(btn_apply_schema)

        btn_save_schema = QPushButton("Сохранить схему")
        btn_save_schema.clicked.connect(self._save_current_schema)
        schema_buttons.addWidget(btn_save_schema)

        schema_layout.addLayout(schema_buttons)

        # Информация о файле схем
        schema_file_label = QLabel(f"Файл схем: {self.schema_manager.get_schema_file_path()}")
        schema_file_label.setStyleSheet("color: gray; font-size: 10px;")
        schema_layout.addWidget(schema_file_label)

        layout.addLayout(schema_layout)

        # Правая колонка: параметры сравнения
        params_layout = QVBoxLayout()

        # Точность (без изменений)
        tolerance_layout = QHBoxLayout()
        tolerance_layout.addWidget(QLabel("Точность float:"))
        self.tolerance_spin = QSpinBox()
        self.tolerance_spin.setRange(0, 1000000)
        self.tolerance_spin.setValue(0)
        self.tolerance_spin.setSuffix(" (10⁻⁶)")
        tolerance_layout.addWidget(self.tolerance_spin)
        btn_set_tolerance_1 = QPushButton("0")
        btn_set_tolerance_1.clicked.connect(lambda: self.tolerance_spin.setValue(0))
        tolerance_layout.addWidget(btn_set_tolerance_1)
        btn_set_tolerance_2 = QPushButton("0.0001")
        btn_set_tolerance_2.clicked.connect(lambda: self.tolerance_spin.setValue(100))
        tolerance_layout.addWidget(btn_set_tolerance_2)
        btn_set_tolerance_3 = QPushButton("0.001")
        btn_set_tolerance_3.clicked.connect(lambda: self.tolerance_spin.setValue(1000))
        tolerance_layout.addWidget(btn_set_tolerance_3)
        params_layout.addLayout(tolerance_layout)

        # ----- НОВЫЙ БЛОК: РЕЖИМ ЭКОНОМИИ ПАМЯТИ (ЧАНКОВЫЙ) -----
        memory_layout = QHBoxLayout()
        self.chunked_checkbox = QCheckBox("Экономия памяти (чанковый режим)")
        self.chunked_checkbox.setChecked(False)
        memory_layout.addWidget(self.chunked_checkbox)

        memory_layout.addWidget(QLabel("Размер чанка:"))
        self.chunksize_spin = QSpinBox()
        self.chunksize_spin.setRange(1000, 500000)
        self.chunksize_spin.setValue(50000)
        self.chunksize_spin.setSingleStep(10000)
        memory_layout.addWidget(self.chunksize_spin)

        params_layout.addLayout(memory_layout)
        # ----- КОНЕЦ НОВОГО БЛОКА -----

        # Агрегация дубликатов (без изменений)
        agg_layout = QHBoxLayout()
        self.agg_checkbox = QCheckBox("Агрегировать дубликаты по ключам")
        self.agg_checkbox.setChecked(False)
        agg_layout.addWidget(self.agg_checkbox)
        self.agg_func_combo = QComboBox()
        self.agg_func_combo.addItems(["sum", "mean", "min", "max"])
        self.agg_func_combo.setCurrentText("sum")
        agg_layout.addWidget(QLabel("Функция:"))
        agg_layout.addWidget(self.agg_func_combo)
        agg_layout.addStretch()
        params_layout.addLayout(agg_layout)

        # Кнопка проверки уникальности (без изменений)
        check_uniqueness_btn = QPushButton("Проверить уникальность ключей")
        check_uniqueness_btn.clicked.connect(self._check_key_uniqueness_manual)
        check_uniqueness_btn.setStyleSheet("background-color: #9C27B0; color: white;")
        params_layout.addWidget(check_uniqueness_btn)

        params_layout.addWidget(QLabel(""))

        # Кнопки управления (без изменений)
        control_buttons = QVBoxLayout()
        btn_load = QPushButton("1. Загрузить файлы")
        btn_load.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        btn_load.clicked.connect(self._load_files)
        control_buttons.addWidget(btn_load)

        self.btn_compare = QPushButton("2. Сравнить!")
        self.btn_compare.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        self.btn_compare.clicked.connect(self._start_comparison)
        control_buttons.addWidget(self.btn_compare)

        self.btn_save = QPushButton("3. Сохранить результаты")
        self.btn_save.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self._save_results)
        control_buttons.addWidget(self.btn_save)

        btn_clear = QPushButton("Очистить все")
        btn_clear.clicked.connect(self._clear_all)
        control_buttons.addWidget(btn_clear)

        params_layout.addLayout(control_buttons)

        layout.addLayout(schema_layout)
        layout.addLayout(params_layout)

        return group

    def _check_key_uniqueness_manual(self):
        """Ручная проверка уникальности ключей"""
        if self.df1 is None or self.df2 is None:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите файлы!")
            return
        
        key_text = self.key_columns_edit.text().strip()
        if not key_text:
            QMessageBox.warning(self, "Предупреждение", "Укажите ключевые столбцы!")
            return
        
        key_columns = [col.strip() for col in key_text.split(",")]
        
        # Проверяем df1
        is_unique_1, dup_keys_1 = check_key_uniqueness(self.df1, key_columns, "df1")
        if not is_unique_1:
            duplicates_df1 = find_duplicate_rows(self.df1, key_columns)
            self.log(f"⚠️ В df1 обнаружено {len(dup_keys_1)} неуникальных ключей")
            
            # Показываем таблицу с дубликатами
            if not duplicates_df1.empty:
                self._show_duplicates_table(duplicates_df1, "Дубликаты в df1")
        else:
            self.log("✓ Ключи в df1 уникальны")
        
        # Проверяем df2
        is_unique_2, dup_keys_2 = check_key_uniqueness(self.df2, key_columns, "df2")
        if not is_unique_2:
            duplicates_df2 = find_duplicate_rows(self.df2, key_columns)
            self.log(f"⚠️ В df2 обнаружено {len(dup_keys_2)} неуникальных ключей")
            
            # Показываем таблицу с дубликатами
            if not duplicates_df2.empty:
                self._show_duplicates_table(duplicates_df2, "Дубликаты в df2")
        else:
            self.log("✓ Ключи в df2 уникальны")
        
        if is_unique_1 and is_unique_2:
            QMessageBox.information(self, "Уникальность ключей", "Ключи уникальны в обоих датафреймах!")

    def _show_duplicates_table(self, duplicates_df: pd.DataFrame, title: str):
        """Отображение таблицы с дубликатами"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Информация
        info_label = QLabel(f"{title}: {len(duplicates_df)} строк с дубликатами")
        info_label.setStyleSheet("font-weight: bold; color: red; padding: 5px;")
        layout.addWidget(info_label)
        
        # Таблица
        table = QTableWidget()
        table.setColumnCount(len(duplicates_df.columns))
        table.setHorizontalHeaderLabels(duplicates_df.columns.tolist())
        table.setRowCount(len(duplicates_df))
        
        for row_idx, (_, row) in enumerate(duplicates_df.iterrows()):
            for col_idx, col_name in enumerate(duplicates_df.columns):
                value = str(row[col_name]) if pd.notna(row[col_name]) else ""
                item = QTableWidgetItem(value)
                
                # Подсвечиваем дублирующиеся строки
                if '_count' in col_name or '_total' in col_name:
                    item.setBackground(Qt.yellow)
                
                table.setItem(row_idx, col_idx, item)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
        layout.addWidget(table)
        
        # Добавляем вкладку с дубликатами
        self.results_tabs.addTab(widget, f"⚠ {title}")
        self.results_tabs.setCurrentWidget(widget)
        
    # ---- МЕТОДЫ ОБРАБОТКИ ДЕЙСТВИЙ ----

    def _load_schema_list(self):
        """Загрузка списка схем в комбобокс"""
        self.schema_combo.blockSignals(True)   # отключаем сигналы
        self.schema_combo.clear()
        schema_names = self.schema_manager.get_schema_names()
        self.schema_combo.addItems(schema_names)
        self.schema_combo.blockSignals(False)  # включаем обратно


    def _open_schemas_file(self):
        """Открытие файла схем в системном редакторе"""
        schema_file = self.schema_manager.get_schema_file_path()
        if os.path.exists(schema_file):
            try:
                if sys.platform == 'win32':
                    os.startfile(schema_file)
                elif sys.platform == 'darwin':
                    os.system(f'open "{schema_file}"')
                else:
                    os.system(f'xdg-open "{schema_file}"')
                self.log(f"Открыт файл схем: {schema_file}")
            except Exception as e:
                self.log(f"Ошибка открытия файла: {e}", is_error=True)
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл: {e}")
        else:
            QMessageBox.warning(self, "Предупреждение", f"Файл схем не найден: {schema_file}")
 

    def apply_schema_template(self, schema_name: str):
        """Применение шаблона схемы"""
        if not schema_name:
            return
            
        schema_data = self.schema_manager.get_schema(schema_name)
        if not schema_data:
            return
        
        self.current_schema = schema_data.get('schema', {}).copy()
        self.current_compare_columns = schema_data.get('key_columns', []).copy()
        self.current_tolerance = schema_data.get('tolerance', 0.0)
        
        # Отображаем схему в редакторе
        schema_text = "\n".join(
            [f"{col}:{dtype}" for col, dtype in self.current_schema.items()]
        )
        self.schema_editor.setText(schema_text)
        
        # Отображаем ключевые столбцы
        if self.current_compare_columns:
            self.key_columns_edit.setText(", ".join(self.current_compare_columns))
        
        # Устанавливаем точность
        tolerance_value = int(self.current_tolerance * 1000000)
        self.tolerance_spin.setValue(tolerance_value)
        
        self.log(f"Применена схема: {schema_name} (точность: {self.current_tolerance})")
    

    def _apply_custom_schema(self):
        """Применение пользовательской схемы из редактора"""
        try:
            schema_text = self.schema_editor.toPlainText().strip()
            if not schema_text:
                QMessageBox.warning(self, "Предупреждение", "Схема пуста!")
                return
            
            schema = {}
            for line in schema_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Неверный формат строки: {line}")
                
                col_name = parts[0].strip()
                col_type = parts[1].strip().lower()
                
                if col_type not in ["string", "float", "int", "bool"]:
                    raise ValueError(f"Неподдерживаемый тип '{col_type}'")
                
                schema[col_name] = col_type
            
            self.current_schema = schema
            
            # Обновляем ключевые столбцы
            key_text = self.key_columns_edit.text().strip()
            if key_text:
                self.current_compare_columns = [col.strip() for col in key_text.split(",")]
            else:
                self.current_compare_columns = list(schema.keys())
            
            # Обновляем точность из интерфейса
            self.current_tolerance = self.tolerance_spin.value() / 1_000_000
            
            self.log(f"Применена пользовательская схема ({len(schema)} столбцов, точность: {self.current_tolerance})")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка в схеме: {e}")
            self.log(f"Ошибка схемы: {e}", is_error=True)
   
    def _save_current_schema(self):
        """Сохранение текущей схемы в файл JSON"""
        try:
            # Получаем текущую схему из редактора
            schema_text = self.schema_editor.toPlainText().strip()
            if not schema_text:
                QMessageBox.warning(self, "Предупреждение", "Схема пуста!")
                return
            
            schema = {}
            for line in schema_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Неверный формат строки: {line}")
                
                col_name = parts[0].strip()
                col_type = parts[1].strip().lower()
                
                if col_type not in ["string", "float", "int", "bool"]:
                    raise ValueError(f"Неподдерживаемый тип '{col_type}'")
                
                schema[col_name] = col_type
            
            # Получаем ключевые столбцы
            key_text = self.key_columns_edit.text().strip()
            key_columns = [col.strip() for col in key_text.split(",")] if key_text else []
            
            # Получаем точность из интерфейса
            tolerance = self.tolerance_spin.value() / 1_000_000
            
            # Текущее имя схемы
            schema_name = self.schema_combo.currentText()
            
            if schema_name:
                # Обновляем существующую схему
                self.schema_manager.update_schema(
                    schema_name, schema_name, schema, key_columns, tolerance
                )
                self.log(f"Схема обновлена: {schema_name} (точность: {tolerance})")
            else:
                # Создаем новую схему
                reply = QMessageBox.question(
                    self, "Новая схема",
                    "Хотите создать новую схему?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self._add_schema()
            
            # Перезагружаем список схем
            self._load_schema_list()
            
            QMessageBox.information(
                self, "Успех",
                f"Схема сохранена в файл:\n{self.schema_manager.get_schema_file_path()}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    

    def _add_schema(self):
        """Добавление новой схемы"""
        # Загружаем текущую схему из редактора
        schema_text = self.schema_editor.toPlainText().strip()
        key_text = self.key_columns_edit.text().strip()
        tolerance = self.tolerance_spin.value() / 1_000_000
        
        schema = {}
        if schema_text:
            try:
                for line in schema_text.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    if len(parts) == 2:
                        schema[parts[0].strip()] = parts[1].strip().lower()
            except:
                schema = {}
        
        key_columns = [col.strip() for col in key_text.split(",")] if key_text else []
        
        schema_data = {
            'schema': schema,
            'key_columns': key_columns,
            'tolerance': tolerance
        }
        
        dialog = SchemaEditorDialog(
            self.schema_manager,
            schema_name="",
            schema_data=schema_data,
            parent=self
        )
        
        if dialog.exec() == QDialog.Accepted:
            result = dialog.result
            if result:
                self.schema_manager.add_schema(
                    result['name'],
                    result['schema'],
                    result['key_columns'],
                    result.get('tolerance', 0.0)
                )
                self._load_schema_list()
                self.schema_combo.setCurrentText(result['name'])
                self.apply_schema_template(result['name'])
                self.log(f"Создана новая схема: {result['name']}")
                QMessageBox.information(
                    self, "Успех",
                    f"Схема '{result['name']}' сохранена в файл:\n"
                    f"{self.schema_manager.get_schema_file_path()}"
                )
    

    def _edit_current_schema(self):
        """Редактирование текущей схемы"""
        schema_name = self.schema_combo.currentText()
        if not schema_name:
            QMessageBox.warning(self, "Предупреждение", "Выберите схему для редактирования!")
            return
        
        schema_data = self.schema_manager.get_schema(schema_name)
        if not schema_data:
            return
        
        dialog = SchemaEditorDialog(
            self.schema_manager,
            schema_name=schema_name,
            schema_data=schema_data,
            parent=self
        )
        
        if dialog.exec() == QDialog.Accepted:
            result = dialog.result
            if result:
                # Обновляем схему (с возможностью переименования)
                self.schema_manager.update_schema(
                    schema_name, 
                    result['name'],
                    result['schema'],
                    result['key_columns'],
                    result.get('tolerance', 0.0)
                )
                self._load_schema_list()
                self.schema_combo.setCurrentText(result['name'])
                self.apply_schema_template(result['name'])
                self.log(f"Схема обновлена: {result['name']}")
                QMessageBox.information(
                    self, "Успех",
                    f"Схема '{result['name']}' обновлена в файле:\n"
                    f"{self.schema_manager.get_schema_file_path()}"
                )
  

    def _delete_current_schema(self):
        """Удаление текущей схемы"""
        schema_name = self.schema_combo.currentText()
        if not schema_name:
            QMessageBox.warning(self, "Предупреждение", "Выберите схему для удаления!")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить схему '{schema_name}' из файла {self.schema_manager.get_schema_file_path()}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.schema_manager.delete_schema(schema_name):
                self._load_schema_list()
                self.log(f"Схема удалена: {schema_name}")
   

    def _reload_schemas(self):
        """Перезагрузка схем из файла"""
        self.schema_manager.load_schemas()
        self._load_schema_list()
        self.log("Схемы перезагружены из файла")
    
    def _select_file(self, file_num: int):
        """Выбор CSV файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Выберите файл {file_num}",
            "",
            "CSV файлы (*.csv);;Все файлы (*)"
        )
        
        if file_path:
            if file_num == 1:
                self.file1_path.setText(file_path)
            else:
                self.file2_path.setText(file_path)
            
            self.log(f"Выбран файл {file_num}: {file_path}")
            self._update_button_states()
    

    def _select_output_dir(self):
        """Выбор каталога для результатов"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Выберите каталог для результатов", str(self.output_dir)
        )
        
        if dir_path:
            self.output_dir = Path(dir_path)
            self.output_path.setText(str(self.output_dir))
            self.log(f"Каталог результатов: {self.output_dir}")
  
    # ИЗМЕНЕНО: загрузка файлов с учётом чанкового режима
    def _load_files(self):
        """Загрузка файлов (в память или только проверка путей)"""
        path1 = self.file1_path.text()
        path2 = self.file2_path.text()

        if not path1 or not path2:
            QMessageBox.warning(self, "Предупреждение", "Выберите оба файла!")
            return

        if not os.path.exists(path1):
            QMessageBox.critical(self, "Ошибка", f"Файл не найден: {path1}")
            return
        if not os.path.exists(path2):
            QMessageBox.critical(self, "Ошибка", f"Файл не найден: {path2}")
            return

        # Обновляем каталог результатов
        output_path = self.output_path.text().strip()
        if output_path:
            self.output_dir = Path(output_path)

        # Если включён чанковый режим – не загружаем данные в память
        if self.chunked_checkbox.isChecked():
            self.df1 = None
            self.df2 = None
            self.log("Чанковый режим: файлы не загружены в память, будут читаться по частям.")
            self._update_button_states()
            return

        sep = self.sep_combo.currentText()
        # Иначе загружаем как обычно
        try:
            self.log(f"Загрузка файла 1: {path1}")
            self.df1 = read_csv_with_schema_v1(path1, type_mapping=self.current_schema, sep=sep)
            self.log(f"  ✓ Загружено: {len(self.df1)} строк, {len(self.df1.columns)} столбцов")

            self.log(f"Загрузка файла 2: {path2}")
            self.df2 = read_csv_with_schema_v1(path2, type_mapping=self.current_schema, sep=sep)
            self.log(f"  ✓ Загружено: {len(self.df2)} строк, {len(self.df2.columns)} столбцов")

            self._update_button_states()
            self.log("Файлы успешно загружены!")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", str(e))
            self.log(f"Ошибка загрузки: {e}", is_error=True)

    def _aggregate_duplicates(self, df: pd.DataFrame, key_columns: List[str], agg_func: str):
        """
        Агрегирует дублирующиеся строки по ключевым столбцам, если все неключевые столбцы числовые.
        
        Returns:
            (df_agg, error_msg) — если агрегация выполнена, error_msg = None;
            если невозможна, возвращается (None, сообщение об ошибке).
        """
        if df is None or df.empty:
            return df, None

        # Проверяем наличие дубликатов по ключу
        if not df.duplicated(subset=key_columns, keep=False).any():
            return df, None  # дубликатов нет, возвращаем исходный df

        non_key_cols = [col for col in df.columns if col not in key_columns]
        if not non_key_cols:
            # Все столбцы ключевые — просто удаляем дубликаты, оставляя первую запись
            return df.drop_duplicates(subset=key_columns, keep='first'), None

        # Проверяем, все ли неключевые столбцы числовые
        non_numeric = [col for col in non_key_cols if not pd.api.types.is_numeric_dtype(df[col])]
        if non_numeric:
            msg = f"Невозможно агрегировать: нечисловые столбцы {non_numeric}"
            return None, msg

        # Выполняем агрегацию
        try:
            agg_dict = {col: agg_func for col in non_key_cols}
            df_agg = df.groupby(key_columns, as_index=False).agg(agg_dict)
            return df_agg, None
        except Exception as e:
            return None, f"Ошибка агрегации: {e}"

    # ИЗМЕНЕНО: запуск сравнения с передачей параметров чанкового режима
    def _start_comparison(self):
        """Запуск сравнения с возможной агрегацией дубликатов и чанковым режимом"""
        if not self.chunked_checkbox.isChecked() and (self.df1 is None or self.df2 is None):
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите файлы!")
            return

        # Парсим ключевые столбцы
        key_text = self.key_columns_edit.text().strip()
        if key_text:
            self.current_compare_columns = [col.strip() for col in key_text.split(",")]

        if not self.current_compare_columns:
            QMessageBox.warning(self, "Предупреждение", "Укажите ключевые столбцы!")
            return

        # Проверка наличия столбцов в схеме
        for col in self.current_compare_columns:
            if col not in self.current_schema:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Столбец '{col}' не найден в схеме!\n"
                    f"Доступные столбцы: {', '.join(self.current_schema.keys())}"
                )
                return

        tolerance = self.tolerance_spin.value() / 1_000_000

        # --- АГРЕГАЦИЯ (если включена) ---
        df1_to_compare = self.df1
        df2_to_compare = self.df2

        if self.agg_checkbox.isChecked() and not self.chunked_checkbox.isChecked():
            agg_func = self.agg_func_combo.currentText()
            self.log("Агрегация дубликатов включена (функция: {})".format(agg_func))

            agg_df1, err1 = self._aggregate_duplicates(self.df1, self.current_compare_columns, agg_func)
            if err1:
                self.log(f"⚠️ df1: {err1}. Агрегация пропущена.", is_error=False)
            else:
                df1_to_compare = agg_df1
                self.log(f"✓ df1 агрегирован: {len(self.df1)} → {len(df1_to_compare)} строк")

            agg_df2, err2 = self._aggregate_duplicates(self.df2, self.current_compare_columns, agg_func)
            if err2:
                self.log(f"⚠️ df2: {err2}. Агрегация пропущена.", is_error=False)
            else:
                df2_to_compare = agg_df2
                self.log(f"✓ df2 агрегирован: {len(self.df2)} → {len(df2_to_compare)} строк")
        # --- КОНЕЦ АГРЕГАЦИИ ---

        self.key_uniqueness_warnings = []

        # Настройка UI
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self.btn_compare.setEnabled(False)
        self.btn_save.setEnabled(False)

        self.log(f"\n{'='*60}")
        self.log(f"Запуск сравнения...")
        self.log(f"Схема: {self.schema_combo.currentText()}")
        self.log(f"Точность: {tolerance}")
        self.log(f"Ключевые столбцы: {', '.join(self.current_compare_columns)}")
        if self.chunked_checkbox.isChecked():
            self.log(f"Режим: чанковый (размер чанка: {self.chunksize_spin.value()})")
        else:
            self.log(f"Режим: in-memory")
        self.log(f"{'='*60}")

        # Определяем, что передавать в worker
        use_chunked = self.chunked_checkbox.isChecked()
        if use_chunked:
            # В чанковом режиме передаём пути к файлам, а не DataFrame
            df1_worker = None
            df2_worker = None
            df1_path = self.file1_path.text()
            df2_path = self.file2_path.text()
        else:
            df1_worker = df1_to_compare
            df2_worker = df2_to_compare
            df1_path = None
            df2_path = None
        sep = self.sep_combo.currentText()
        self.worker = CompareWorker(
            df1_worker, df2_worker,
            self.current_schema,
            self.current_compare_columns,
            tolerance,
            use_chunked=use_chunked,
            df1_path=df1_path,
            df2_path=df2_path,
            chunksize=self.chunksize_spin.value(),
            encoding='utf-8',
            csv_separator=sep 
        )
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self._on_comparison_finished)
        self.worker.error.connect(self._on_comparison_error)
        self.worker.key_uniqueness_warning.connect(self._on_key_uniqueness_warning)
        self.worker.start()

    def _on_key_uniqueness_warning(self, message: str, details: str):
        """Обработка предупреждения о неуникальных ключах"""
        self.key_uniqueness_warnings.append((message, details))
        self.log(f"⚠️ {message}", is_error=False)
        
        # Показываем диалог с предупреждением
        reply = QMessageBox.warning(
            self, "Предупреждение о неуникальных ключах",
            f"{message}\n\n"
            f"Сравнение будет продолжено, но результаты могут быть некорректными.\n\n"
            f"Хотите просмотреть детали?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Показываем детали в отдельном диалоге
            detail_dialog = QDialog(self)
            detail_dialog.setWindowTitle("Детали неуникальных ключей")
            detail_dialog.setMinimumSize(800, 600)
            
            layout = QVBoxLayout(detail_dialog)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setText(details)
            font = QFont("Courier New", 9)
            text_edit.setFont(font)
            layout.addWidget(text_edit)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(detail_dialog.close)
            layout.addWidget(buttons)
            
            detail_dialog.exec()
        elif reply == QMessageBox.Cancel:
            self.worker.terminate()
            return

    def _on_comparison_finished(self, comparator):
        """Обработка завершения сравнения (без изменений)"""
        self.comparator = comparator
        self.progress_bar.hide()
        self.btn_compare.setEnabled(True)
        self.btn_save.setEnabled(True)
        self._display_results()

        total_diffs = 0
        if not comparator.df1_only.empty:
            total_diffs += len(comparator.df1_only)
        if not comparator.df2_only.empty:
            total_diffs += len(comparator.df2_only)
        if comparator.df1_df2_value is not None:
            total_diffs += len(comparator.df1_df2_value)

        message_parts = []
        if self.key_uniqueness_warnings:
            message_parts.append("⚠️ ВНИМАНИЕ: Обнаружены неуникальные ключи!")
            message_parts.append(f"   Количество предупреждений: {len(self.key_uniqueness_warnings)}")
            message_parts.append("")

        if total_diffs == 0:
            message_parts.append("✓ Нет отличий! DataFrame идентичны.")
            self.log("\n✓ Нет отличий! DataFrame идентичны.")
            QMessageBox.information(self, "Результат", "\n".join(message_parts))
        else:
            message_parts.append(f"✓ Найдено отличий: {total_diffs}")
            self.log(f"\n✓ Найдено отличий: {total_diffs}")
            QMessageBox.information(
                self, "Результат",
                "\n".join(message_parts) +
                f"\n\nСравнение завершено!\n"
                f"Найдено отличий: {total_diffs}\n"
                f"  - Только в df1: {len(comparator.df1_only)}\n"
                f"  - Только в df2: {len(comparator.df2_only)}\n"
                f"  - Различия в значениях: {len(comparator.df1_df2_value) if comparator.df1_df2_value is not None else 0}"
            )

    def _on_comparison_error(self, error_msg):
        """Обработка ошибки сравнения"""
        self.progress_bar.hide()
        self.btn_compare.setEnabled(True)
        self.btn_save.setEnabled(False)
        
        self.log(f"\nОШИБКА: {error_msg}", is_error=True)
        QMessageBox.critical(self, "Ошибка сравнения", error_msg)
    
    def _display_results(self):
        """Отображение результатов в таблицах"""
        self.results_tabs.clear()
        
        if self.comparator is None:
            return
        
        # Таблица "Только в df1"
        if not self.comparator.df1_only.empty:
            tab1 = self._create_table_widget(self.comparator.df1_only)
            self.results_tabs.addTab(tab1, f"Только в df1 ({len(self.comparator.df1_only)})")
        else:
            tab1 = QWidget()
            tab1_layout = QVBoxLayout(tab1)
            tab1_layout.addWidget(QLabel("Нет строк, присутствующих только в df1"))
            self.results_tabs.addTab(tab1, "Только в df1 (0)")
        
        # Таблица "Только в df2"
        if not self.comparator.df2_only.empty:
            tab2 = self._create_table_widget(self.comparator.df2_only)
            self.results_tabs.addTab(tab2, f"Только в df2 ({len(self.comparator.df2_only)})")
        else:
            tab2 = QWidget()
            tab2_layout = QVBoxLayout(tab2)
            tab2_layout.addWidget(QLabel("Нет строк, присутствующих только в df2"))
            self.results_tabs.addTab(tab2, "Только в df2 (0)")
        
        # Таблица "Различия в значениях"
        if self.comparator.df1_df2_value is not None and not self.comparator.df1_df2_value.empty:
            tab3 = self._create_table_widget(self.comparator.df1_df2_value)
            self.results_tabs.addTab(tab3, f"Различия ({len(self.comparator.df1_df2_value)})")
        else:
            tab3 = QWidget()
            tab3_layout = QVBoxLayout(tab3)
            tab3_layout.addWidget(QLabel("Нет различий в значениях"))
            self.results_tabs.addTab(tab3, "Различия (0)")
        
        # Если были предупреждения о неуникальных ключах, добавляем вкладку
        if self.key_uniqueness_warnings:
            warning_widget = QWidget()
            warning_layout = QVBoxLayout(warning_widget)
            
            for msg, details in self.key_uniqueness_warnings:
                warning_label = QLabel(f"⚠ {msg}")
                warning_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
                warning_layout.addWidget(warning_label)
                
                details_edit = QTextEdit()
                details_edit.setReadOnly(True)
                details_edit.setText(details)
                details_edit.setMaximumHeight(150)
                font = QFont("Courier New", 9)
                details_edit.setFont(font)
                warning_layout.addWidget(details_edit)
            
            self.results_tabs.addTab(warning_widget, f"⚠ Предупреждения ({len(self.key_uniqueness_warnings)})")
    

    def _create_table_widget(self, df: pd.DataFrame) -> QWidget:
        """Создание виджета таблицы из DataFrame с подсветкой различий"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Информация о таблице
        info_label = QLabel(f"Строк: {len(df)}, Столбцов: {len(df.columns)}")
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(info_label)
        
        # Таблица
        table = QTableWidget()
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels(df.columns.tolist())
        table.setRowCount(len(df))
        
        # Определяем пары столбцов для сравнения (без суффиксов _df1 и _df2)
        column_pairs = []
        base_columns = set()
        
        for col in df.columns:
            if col.endswith("_df1"):
                base_name = col[:-4]
                base_columns.add(base_name)
            elif col.endswith("_df2"):
                base_name = col[:-4]
                base_columns.add(base_name)
        
        # Создаем словарь соответствия базовых имен столбцам
        col_mapping = {}
        for base_name in base_columns:
            df1_col = f"{base_name}_df1"
            df2_col = f"{base_name}_df2"
            if df1_col in df.columns and df2_col in df.columns:
                col_mapping[base_name] = (df1_col, df2_col)
        
        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, col_name in enumerate(df.columns):
                value = str(row[col_name]) if pd.notna(row[col_name]) else ""
                item = QTableWidgetItem(value)
                # Подсветка сравниваемых столбцов
                if "_df1" in col_name or "_df2" in col_name:
                    item.setBackground(Qt.yellow)
                # Проверяем, является ли столбец частью пары для сравнения
                is_diff_column = False
                for base_name, (df1_col, df2_col) in col_mapping.items():
                    if col_name == df1_col or col_name == df2_col:
                        is_diff_column = True
                        
                        # Получаем значения для сравнения
                        val1 = row[df1_col]
                        val2 = row[df2_col]
                        
                        # Сравниваем значения
                        if pd.isna(val1) and pd.isna(val2):
                            are_equal = True
                        elif pd.isna(val1) or pd.isna(val2):
                            are_equal = False
                        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            tolerance = self.tolerance_spin.value() / 1_000_000
                            are_equal = abs(float(val1) - float(val2)) <= tolerance
                        else:
                            are_equal = str(val1) == str(val2)
                        
                        # Если значения не совпадают, выделяем ячейку красным
                        if not are_equal:
                            item.setBackground(QColor(255, 200, 200))  # Светло-красный
                            item.setForeground(QColor(200, 0, 0))  # Красный текст
                        
                        break
                
                # Если это ключевой столбец, выделяем его светло-желтым
                if not is_diff_column and col_name in self.current_compare_columns:
                    if item.background() == QColor(255, 255, 255) or item.background() == Qt.white:
                        item.setBackground(QColor(255, 255, 200))  # Светло-желтый
                
                table.setItem(row_idx, col_idx, item)
        
        # Подсвечиваем заголовки столбцов с различиями
        header = table.horizontalHeader()
        for col_idx, col_name in enumerate(df.columns):
            for base_name, (df1_col, df2_col) in col_mapping.items():
                if col_name == df1_col or col_name == df2_col:
                    # Проверяем, есть ли в этом столбце различия
                    has_diff = False
                    for row_idx in range(len(df)):
                        val1 = df.iloc[row_idx][df1_col]
                        val2 = df.iloc[row_idx][df2_col]
                        
                        if pd.isna(val1) and pd.isna(val2):
                            continue
                        elif pd.isna(val1) or pd.isna(val2):
                            has_diff = True
                            break
                        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            tolerance = self.tolerance_spin.value() / 1_000_000
                            if abs(float(val1) - float(val2)) > tolerance:
                                has_diff = True
                                break
                        elif str(val1) != str(val2):
                            has_diff = True
                            break
                    
                    if has_diff:
                        # Создаем виджет для заголовка с подсветкой
                        header_widget = QWidget()
                        header_layout = QHBoxLayout(header_widget)
                        header_layout.setContentsMargins(5, 0, 5, 0)
                        
                        label = QLabel(col_name)
                        if col_name.endswith("_df1"):
                            label.setStyleSheet("background-color: #FFCCCC; font-weight: bold; padding: 2px;")
                        elif col_name.endswith("_df2"):
                            label.setStyleSheet("background-color: #CCFFCC; font-weight: bold; padding: 2px;")
                        
                        header_layout.addWidget(label)
                        table.setCellWidget(-1, col_idx, header_widget)
                    
                    break
        
        # Автоматическая ширина столбцов
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
        # Разрешаем сортировку
        table.setSortingEnabled(True)
        
        layout.addWidget(table)
        
        return widget

    def _save_results(self):
        """Сохранение результатов"""
        if self.comparator is None:
            QMessageBox.warning(self, "Предупреждение", "Нет результатов для сохранения!")
            return
        
        # Используем выбранный каталог
        output_dir = self.output_dir
        
        try:
            # Создаем подкаталог с меткой времени
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = output_dir / f"comparison_{timestamp}"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            saved_files = []
            
            if not self.comparator.df1_only.empty:
                path = str(save_dir / "df1_only.xlsx")
                self.comparator.df1_only.to_excel(path, index=False)
                saved_files.append(path)
                self.log(f"Сохранено: {path}")
            
            if not self.comparator.df2_only.empty:
                path = str(save_dir / "df2_only.xlsx")
                self.comparator.df2_only.to_excel(path, index=False)
                saved_files.append(path)
                self.log(f"Сохранено: {path}")
            
            if self.comparator.df1_df2_value is not None and not self.comparator.df1_df2_value.empty:
                path = str(save_dir / "differences.xlsx")
                self.comparator.df1_df2_value.to_excel(path, index=False)
                saved_files.append(path)
                self.log(f"Сохранено: {path}")
            
            # Сохраняем информацию о предупреждениях, если они были
            if self.key_uniqueness_warnings:
                warnings_path = str(save_dir / "key_uniqueness_warnings.txt")
                with open(warnings_path, 'w', encoding='utf-8') as f:
                    for msg, details in self.key_uniqueness_warnings:
                        f.write(f"{msg}\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"{details}\n")
                        f.write("\n" + "=" * 80 + "\n\n")
                saved_files.append(warnings_path)
                self.log(f"Сохранено: {warnings_path}")
            
            if saved_files:
                QMessageBox.information(
                    self, "Сохранение",
                    f"Результаты сохранены в:\n{save_dir}\n\n"
                    f"Сохранено файлов: {len(saved_files)}"
                )
            else:
                QMessageBox.information(
                    self, "Информация",
                    "Нет данных для сохранения"
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", str(e))
            self.log(f"Ошибка сохранения: {e}", is_error=True)
    

    def _clear_all(self):
        """Полная очистка"""
        self.comparator = None
        self.df1 = None
        self.df2 = None
        self.key_uniqueness_warnings = []
        self.results_tabs.clear()
        self.log_panel.clear()
        self.file1_path.clear()
        self.file2_path.clear()
        self.btn_save.setEnabled(False)
        self.btn_compare.setEnabled(False)
        self.log("Все данные очищены")

    def _update_button_states(self):
        """Обновление состояния кнопок"""
        has_files = bool(self.file1_path.text()) and bool(self.file2_path.text())
        self.btn_compare.setEnabled(has_files)

    def log(self, message: str, is_error: bool = False):
        """Добавление сообщения в лог"""
        cursor = self.log_panel.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if is_error:
            self.log_panel.setTextColor(Qt.red)
        else:
            self.log_panel.setTextColor(Qt.black)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"[{timestamp}] {message}\n")
        cursor.movePosition(QTextCursor.End)
        self.log_panel.setTextCursor(cursor)
        self.log_panel.ensureCursorVisible()



def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()