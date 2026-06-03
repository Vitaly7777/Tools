from __future__ import annotations

import json
from typing import Any

from excel_core import (
    DEFAULT_HEADER_SCAN_ROWS,
    build_source_schema_preview,
    read_sheet_names,
)
from PySide6 import QtCore, QtWidgets


class _ColumnsStepWidget(QtWidgets.QWidget):
    stateChanged = QtCore.Signal()

    TYPE_OPTIONS = [
        ("auto", "auto"),
        ("string", "string"),
        ("Int64", "Int64"),
        ("float64", "float64"),
        ("boolean", "boolean"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.section_title_label = QtWidgets.QLabel("Колонки")
        self.section_title_label.setObjectName("columns_step_title_label")
        layout.addWidget(self.section_title_label)

        actions = QtWidgets.QHBoxLayout()
        self.read_all_button = QtWidgets.QPushButton("Читать все")
        self.read_none_button = QtWidgets.QPushButton("Не читать все")
        self.invert_button = QtWidgets.QPushButton("Инвертировать")
        self.bulk_type_combo = QtWidgets.QComboBox()
        for value, label in self.TYPE_OPTIONS:
            self.bulk_type_combo.addItem(label, value)
        self.apply_type_button = QtWidgets.QPushButton("Применить тип к выбранным")
        actions.addWidget(self.read_all_button)
        actions.addWidget(self.read_none_button)
        actions.addWidget(self.invert_button)
        actions.addStretch(1)
        actions.addWidget(self.bulk_type_combo)
        actions.addWidget(self.apply_type_button)
        layout.addLayout(actions)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Колонка", "Определено", "Читать", "Тип"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table)

        self.raw_options_label = QtWidgets.QLabel("Дополнительные options (JSON)")
        self.raw_options_label.setObjectName("columns_step_raw_title_label")
        layout.addWidget(self.raw_options_label)
        self.advanced_edit = QtWidgets.QPlainTextEdit()
        self.advanced_edit.setMaximumHeight(120)
        self.advanced_edit.setPlaceholderText('{"dtype": {"Код БП": "string"}}')
        layout.addWidget(self.advanced_edit)

        self.validation_label = QtWidgets.QLabel("")
        layout.addWidget(self.validation_label)

        self.read_all_button.clicked.connect(lambda: self._set_all_enabled(True))
        self.read_none_button.clicked.connect(lambda: self._set_all_enabled(False))
        self.invert_button.clicked.connect(self._invert)
        self.apply_type_button.clicked.connect(self._apply_type_to_selected)
        self.advanced_edit.textChanged.connect(self.stateChanged.emit)

    def load_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        selected_columns: list[str],
        column_types: dict[str, str],
        raw_read_config: dict[str, Any],
        columns_configured: bool = False,
    ) -> None:
        self.table.setRowCount(0)
        selected = set(selected_columns or [])
        for row_index, row in enumerate(rows):
            self.table.insertRow(row_index)
            column_name = str(row["name"])
            detected_type = str(row["detected_type"])
            enabled = (
                column_name in selected
                if columns_configured
                else (True if not selected else column_name in selected)
            )
            read_as = column_types.get(column_name, "auto")

            self.table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(column_name))
            self.table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(detected_type))

            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(enabled)
            checkbox.stateChanged.connect(lambda _state: self.stateChanged.emit())
            wrapper = QtWidgets.QWidget()
            wrapper_layout = QtWidgets.QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            wrapper_layout.addWidget(checkbox)
            self.table.setCellWidget(row_index, 2, wrapper)

            combo = QtWidgets.QComboBox()
            for value, label in self.TYPE_OPTIONS:
                combo.addItem(label, value)
            combo_index = combo.findData(read_as)
            combo.setCurrentIndex(combo_index if combo_index >= 0 else 0)
            combo.currentIndexChanged.connect(lambda _index: self.stateChanged.emit())
            self.table.setCellWidget(row_index, 3, combo)

        if raw_read_config:
            self.advanced_edit.setPlainText(
                json.dumps(raw_read_config, ensure_ascii=False, indent=2)
            )
        else:
            self.advanced_edit.clear()

    def export_state(self) -> dict[str, Any]:
        selected_columns: list[str] = []
        column_types: dict[str, str] = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            wrapper = self.table.cellWidget(row, 2)
            checkbox = (
                wrapper.findChild(QtWidgets.QCheckBox) if wrapper is not None else None
            )
            combo = self.table.cellWidget(row, 3)
            if name_item is None or checkbox is None:
                continue
            if checkbox.isChecked():
                column_name = name_item.text().strip()
                selected_columns.append(column_name)
                if isinstance(combo, QtWidgets.QComboBox):
                    read_as = str(combo.currentData() or "auto")
                    if read_as != "auto":
                        column_types[column_name] = read_as

        raw_read_config = self._parse_advanced_options()
        return {
            "selected_columns": selected_columns,
            "column_types": column_types,
            "raw_read_config": raw_read_config,
            "advanced_read_options": raw_read_config,
            "columns_configured": True,
        }

    def has_selected_columns(self) -> bool:
        return bool(self.export_state()["selected_columns"])

    def _iter_checkboxes(self):
        for row in range(self.table.rowCount()):
            wrapper = self.table.cellWidget(row, 2)
            checkbox = (
                wrapper.findChild(QtWidgets.QCheckBox) if wrapper is not None else None
            )
            if checkbox is not None:
                yield checkbox

    def _set_all_enabled(self, enabled: bool) -> None:
        for checkbox in self._iter_checkboxes():
            checkbox.setChecked(enabled)
        self.stateChanged.emit()

    def _invert(self) -> None:
        for checkbox in self._iter_checkboxes():
            checkbox.setChecked(not checkbox.isChecked())
        self.stateChanged.emit()

    def _apply_type_to_selected(self) -> None:
        target_type = self.bulk_type_combo.currentData()
        selected_rows = {
            index.row() for index in self.table.selectionModel().selectedRows()
        }
        if not selected_rows:
            selected_rows = set(range(self.table.rowCount()))
        for row in selected_rows:
            combo = self.table.cellWidget(row, 3)
            if isinstance(combo, QtWidgets.QComboBox):
                index = combo.findData(target_type)
                if index >= 0:
                    combo.setCurrentIndex(index)
        self.stateChanged.emit()

    def _parse_advanced_options(self) -> dict[str, Any]:
        text = self.advanced_edit.toPlainText().strip()
        if not text:
            self.validation_label.setText("")
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            self.validation_label.setText("JSON options содержат ошибку.")
            return {}
        if not isinstance(parsed, dict):
            self.validation_label.setText("JSON options должны быть объектом.")
            return {}
        self.validation_label.setText("")
        return parsed

    def set_sheet_context(self, *, sheet_name: str, is_multi: bool) -> None:
        normalized_sheet = str(sheet_name or "").strip()
        if is_multi and normalized_sheet:
            self.section_title_label.setText(f"Колонки листа {normalized_sheet}")
            self.raw_options_label.setText(f"Raw options для листа {normalized_sheet}")
            return
        self.section_title_label.setText("Колонки")
        self.raw_options_label.setText("Дополнительные options (JSON)")


class ExcelSourceWizardDialog(QtWidgets.QDialog):
    def __init__(
        self,
        file_path: str,
        parent=None,
        initial_state: dict[str, Any] | None = None,
    ):
        super().__init__(parent)
        self._file_path = str(file_path or "")
        self._temp_state = self._build_temp_state(initial_state=initial_state)
        self._active_sheet_name = str(
            self._temp_state.get("sheet_name")
            or next(iter(self._temp_state.get("sheet_names", []) or []), "")
        ).strip()
        self._current_preview_rows: list[dict[str, Any]] = []
        self._current_raw_rows: list[list[str]] = []
        self._loading_sheet_ui = False
        self._setup_ui()
        self._load_sheets()
        self._sync_step_state()

    @staticmethod
    def _build_temp_state(
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema = dict(initial_state or {})
        top_level_sheet_name = str(schema.get("sheet_name") or "").strip()
        sheet_mode = str(schema.get("sheet_mode", "single") or "single").strip().lower()
        sheet_names = [
            str(name).strip()
            for name in (schema.get("sheet_names", []) or [])
            if str(name).strip()
        ]
        if (
            sheet_mode != "multiple"
            and top_level_sheet_name
            and top_level_sheet_name not in sheet_names
        ):
            sheet_names.insert(0, top_level_sheet_name)
        if not sheet_names and top_level_sheet_name:
            sheet_names = [top_level_sheet_name]

        top_level_raw = dict(
            schema.get("raw_read_config", schema.get("advanced_read_options", {})) or {}
        )
        top_level_raw.pop("sheet_name", None)
        shared_multi_defaults = {
            "header_mode": str(schema.get("header_mode", "auto") or "auto"),
            "header_strategy": str(
                schema.get("header_strategy", "densest_unique_row")
                or "densest_unique_row"
            ),
            "header_scan_rows": int(
                schema.get("header_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            ),
            "header_detected_row": schema.get(
                "header_detected_row", schema.get("header")
            ),
            "header_confirmed": bool(schema.get("header_confirmed", False)),
            "marker_enabled": bool(schema.get("marker_enabled", True)),
            "header_markers": list(schema.get("header_markers", []) or []),
            "marker_match_mode": str(schema.get("marker_match_mode", "any") or "any"),
            "marker_scan_rows": int(
                schema.get("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            ),
            "marker_detected_row_on_sample": schema.get(
                "marker_detected_row_on_sample",
                schema.get("header"),
            ),
            "header": None,
            "skiprows": 0,
            "selected_columns": [],
            "columns_configured": False,
            "column_types": {},
            "raw_read_config": {},
            "advanced_read_options": {},
        }
        top_level_sheet_config = {
            "sheet_name": top_level_sheet_name,
            **dict(shared_multi_defaults),
            "header": schema.get("header"),
            "skiprows": top_level_raw.get("skiprows", 0),
            "selected_columns": list(schema.get("selected_columns", []) or []),
            "columns_configured": bool(
                schema.get(
                    "columns_configured",
                    bool(schema.get("selected_columns", []) or []),
                )
            ),
            "column_types": dict(schema.get("column_types", {}) or {}),
            "raw_read_config": top_level_raw,
            "advanced_read_options": dict(top_level_raw),
        }

        raw_sheet_configs = schema.get("sheet_read_configs", {}) or {}
        normalized_sheet_configs: dict[str, dict[str, Any]] = {}
        if isinstance(raw_sheet_configs, dict):
            for raw_sheet_name, raw_config in raw_sheet_configs.items():
                sheet_name = str(raw_sheet_name or "").strip()
                if not sheet_name:
                    continue
                if sheet_mode == "multiple":
                    payload = {
                        **dict(shared_multi_defaults),
                        "sheet_name": sheet_name,
                    }
                else:
                    payload = dict(top_level_sheet_config)
                payload.update(dict(raw_config or {}))
                raw_read_config = dict(
                    payload.get(
                        "raw_read_config",
                        payload.get("advanced_read_options", {}),
                    )
                    or {}
                )
                raw_read_config["sheet_name"] = sheet_name
                payload["sheet_name"] = sheet_name
                payload["raw_read_config"] = raw_read_config
                payload["advanced_read_options"] = dict(raw_read_config)
                normalized_sheet_configs[sheet_name] = payload

        for sheet_name in list(sheet_names):
            normalized_sheet_configs.setdefault(
                sheet_name,
                {
                    **(
                        dict(shared_multi_defaults)
                        if sheet_mode == "multiple" and normalized_sheet_configs
                        else dict(top_level_sheet_config)
                    ),
                    "sheet_name": sheet_name,
                    "raw_read_config": {
                        **dict(
                            (
                                shared_multi_defaults
                                if sheet_mode == "multiple" and normalized_sheet_configs
                                else top_level_sheet_config
                            ).get("raw_read_config", {})
                            or {}
                        ),
                        "sheet_name": sheet_name,
                    },
                    "advanced_read_options": {
                        **dict(
                            (
                                shared_multi_defaults
                                if sheet_mode == "multiple" and normalized_sheet_configs
                                else top_level_sheet_config
                            ).get("raw_read_config", {})
                            or {}
                        ),
                        "sheet_name": sheet_name,
                    },
                },
            )

        schema["sheet_mode"] = "multiple" if sheet_mode == "multiple" else "single"
        if schema["sheet_mode"] == "multiple":
            schema["sheet_name"] = top_level_sheet_name or (
                sheet_names[0] if sheet_names else ""
            )
        else:
            schema["sheet_name"] = top_level_sheet_name
        schema["sheet_names"] = list(sheet_names)
        schema["sheet_read_configs"] = normalized_sheet_configs
        schema.setdefault("marker_enabled", True)
        schema.setdefault("header_markers", [])
        schema.setdefault("marker_match_mode", "any")
        schema.setdefault("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
        schema.setdefault("marker_detected_row_on_sample", schema.get("header"))
        return schema

    def get_result_state(self) -> dict[str, Any]:
        self._sync_active_sheet_config_from_ui()
        result = dict(self._temp_state)
        selected_sheet_names = self._selected_sheet_names_from_ui()
        result["sheet_mode"] = str(self.sheet_mode_combo.currentData() or "single")
        result["sheet_names"] = list(selected_sheet_names)
        result["sheet_name"] = selected_sheet_names[0] if selected_sheet_names else ""

        sheet_configs: dict[str, dict[str, Any]] = {}
        for sheet_name in selected_sheet_names:
            sheet_configs[sheet_name] = self._finalize_sheet_config(
                dict(self._ensure_sheet_config(sheet_name)),
                sheet_name=sheet_name,
            )
        result["sheet_read_configs"] = sheet_configs

        primary_config = (
            dict(sheet_configs.get(result["sheet_name"], {}))
            if result["sheet_name"]
            else {}
        )
        raw_read_config = dict(primary_config.get("raw_read_config", {}) or {})
        result["header_mode"] = primary_config.get("header_mode", "auto")
        result["header_strategy"] = primary_config.get(
            "header_strategy", "densest_unique_row"
        )
        result["header_scan_rows"] = primary_config.get(
            "header_scan_rows", DEFAULT_HEADER_SCAN_ROWS
        )
        result["header_detected_row"] = primary_config.get(
            "header_detected_row", primary_config.get("header")
        )
        result["header_confirmed"] = bool(primary_config.get("header_confirmed", False))
        result["marker_enabled"] = bool(primary_config.get("marker_enabled", True))
        result["header_markers"] = list(primary_config.get("header_markers", []) or [])
        result["marker_match_mode"] = str(
            primary_config.get("marker_match_mode", "any") or "any"
        )
        result["marker_scan_rows"] = int(
            primary_config.get("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
            or DEFAULT_HEADER_SCAN_ROWS
        )
        result["marker_detected_row_on_sample"] = primary_config.get(
            "marker_detected_row_on_sample",
            primary_config.get("header"),
        )
        result["header"] = primary_config.get("header")
        result["selected_columns"] = list(
            primary_config.get("selected_columns", []) or []
        )
        result["columns_configured"] = bool(
            primary_config.get("columns_configured", False)
        )
        result["column_types"] = dict(primary_config.get("column_types", {}) or {})
        result["raw_read_config"] = raw_read_config
        result["advanced_read_options"] = dict(raw_read_config)
        return result

    def _setup_ui(self) -> None:
        self.setWindowTitle("Настройка Excel-источника")
        self.resize(980, 720)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(8)

        self.steps_label = QtWidgets.QLabel("")
        layout.addWidget(self.steps_label)

        self.active_sheet_bar = QtWidgets.QFrame()
        self.active_sheet_bar.setObjectName("header_status_card")
        self.active_sheet_bar.setProperty("statusState", "blocked")
        self.active_sheet_bar.setStyleSheet(
            "#header_status_card {"
            "border: 1px solid #F6C453;"
            "border-radius: 6px;"
            "background-color: #FFFBEB;"
            "}"
            "#header_status_card[statusState='ready'] {"
            "border: 1px solid #86EFAC;"
            "background-color: #F0FDF4;"
            "}"
        )
        active_sheet_layout = QtWidgets.QVBoxLayout(self.active_sheet_bar)
        active_sheet_layout.setContentsMargins(10, 10, 10, 10)
        active_sheet_layout.setSpacing(6)
        active_sheet_row = QtWidgets.QHBoxLayout()
        active_sheet_row.setContentsMargins(0, 0, 0, 0)
        active_sheet_row.setSpacing(8)
        self.active_sheet_label = QtWidgets.QLabel("Сейчас настраиваете:")
        self.active_sheet_label.setObjectName("active_sheet_title")
        self.active_sheet_combo = QtWidgets.QComboBox()
        self.active_sheet_combo.setObjectName("active_sheet_combo")
        active_sheet_combo_size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.active_sheet_combo.setSizePolicy(active_sheet_combo_size_policy)
        active_sheet_row.addWidget(self.active_sheet_label)
        active_sheet_row.addWidget(self.active_sheet_combo, 1)
        self.header_status_message_label = QtWidgets.QLabel("")
        self.header_status_message_label.setObjectName("header_status_message")
        self.header_status_message_label.setWordWrap(True)
        active_sheet_layout.addLayout(active_sheet_row)
        active_sheet_layout.addWidget(self.header_status_message_label)
        self.active_sheet_bar.setVisible(False)
        layout.addWidget(self.active_sheet_bar)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.sheet_page = self._build_sheet_page()
        self.header_page = self._build_header_page()
        self.columns_page = self._build_columns_page()
        self.review_page = self._build_review_page()

        self.stack.addWidget(self.sheet_page)
        self.stack.addWidget(self.header_page)
        self.stack.addWidget(self.columns_page)
        self.stack.addWidget(self.review_page)

        buttons = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("Назад")
        self.next_button = QtWidgets.QPushButton("Далее")
        self.save_button = QtWidgets.QPushButton("Сохранить")
        self.cancel_button = QtWidgets.QPushButton("Отмена")
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.stack.currentChanged.connect(self._sync_step_state)
        self.sheet_mode_combo.currentIndexChanged.connect(self._on_sheet_mode_changed)
        self.sheet_list.itemSelectionChanged.connect(self._on_sheet_selection_changed)
        self.sheet_list.currentRowChanged.connect(self._on_sheet_changed)
        self.select_all_sheets_button.clicked.connect(self._select_all_sheets)
        self.clear_sheet_selection_button.clicked.connect(self._clear_sheet_selection)
        self.active_sheet_combo.currentIndexChanged.connect(
            self._on_active_sheet_combo_changed
        )
        self.header_mode_combo.currentIndexChanged.connect(self._on_header_mode_changed)
        self.scan_rows_spin.valueChanged.connect(self._sync_step_state)
        self.header_row_spin.valueChanged.connect(self._on_manual_header_changed)
        self.find_header_button.clicked.connect(self._find_header)
        self.marker_enabled_checkbox.toggled.connect(self._on_marker_enabled_toggled)
        self.fill_markers_button.clicked.connect(self._fill_markers_from_current_header)
        self.clear_markers_button.clicked.connect(self._clear_markers)
        self.marker_list_edit.textChanged.connect(self._sync_step_state)
        self.marker_match_mode_combo.currentIndexChanged.connect(self._sync_step_state)
        self.marker_scan_rows_spin.valueChanged.connect(self._sync_step_state)
        self.columns_step.stateChanged.connect(self._sync_step_state)
        self.back_button.clicked.connect(self._go_back)
        self.next_button.clicked.connect(self._go_next)
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.marker_enabled_checkbox.setChecked(
            bool(self._temp_state.get("marker_enabled", False))
        )
        self.marker_list_edit.setPlainText(
            "\n".join(self._temp_state.get("header_markers", []) or [])
        )
        marker_mode_index = self.marker_match_mode_combo.findData(
            str(self._temp_state.get("marker_match_mode", "any") or "any")
        )
        self.marker_match_mode_combo.setCurrentIndex(
            marker_mode_index if marker_mode_index >= 0 else 0
        )
        self.marker_scan_rows_spin.setValue(
            int(
                self._temp_state.get("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            )
        )
        self._update_marker_controls()

    @staticmethod
    def _style_neutral_card(frame: QtWidgets.QFrame) -> None:
        frame.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        frame.setStyleSheet(
            f"#{frame.objectName()} {{"
            "border: 1px solid #E5E7EB;"
            "border-radius: 6px;"
            "background-color: #F8FAFC;"
            "}"
        )

    def _build_sheet_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        controls = QtWidgets.QHBoxLayout()
        self.sheet_mode_combo = QtWidgets.QComboBox()
        self.sheet_mode_combo.addItem("Один лист", "single")
        self.sheet_mode_combo.addItem("Несколько листов", "multiple")
        self.select_all_sheets_button = QtWidgets.QPushButton("Добавить все")
        self.clear_sheet_selection_button = QtWidgets.QPushButton("Очистить")
        controls.addWidget(QtWidgets.QLabel("Режим листов"))
        controls.addWidget(self.sheet_mode_combo)
        controls.addStretch(1)
        controls.addWidget(self.select_all_sheets_button)
        controls.addWidget(self.clear_sheet_selection_button)
        layout.addLayout(controls)

        body = QtWidgets.QHBoxLayout()

        self.sheet_list = QtWidgets.QListWidget()
        body.addWidget(self.sheet_list, 1)

        self.sheet_preview = QtWidgets.QTableWidget()
        self.sheet_preview.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        body.addWidget(self.sheet_preview, 3)
        layout.addLayout(body, 1)
        return page

    def _build_header_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.header_controls_card = QtWidgets.QFrame()
        self.header_controls_card.setObjectName("header_controls_card")
        self._style_neutral_card(self.header_controls_card)
        controls_card_layout = QtWidgets.QVBoxLayout(self.header_controls_card)
        controls_card_layout.setContentsMargins(10, 10, 10, 10)
        controls_card_layout.setSpacing(6)

        controls = QtWidgets.QHBoxLayout()
        self.header_mode_combo = QtWidgets.QComboBox()
        self.header_mode_combo.addItem("Авто", "auto")
        self.header_mode_combo.addItem("Вручную", "manual")
        self.scan_rows_spin = QtWidgets.QSpinBox()
        self.scan_rows_spin.setRange(1, 500)
        self.scan_rows_spin.setValue(
            int(
                self._temp_state.get("header_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            )
        )
        self.scan_rows_spin.setSuffix(" строк")
        self.header_row_spin = QtWidgets.QSpinBox()
        self.header_row_spin.setRange(1, 100000)
        self.find_header_button = QtWidgets.QPushButton("Найти шапку")
        controls.addWidget(QtWidgets.QLabel("Режим"))
        controls.addWidget(self.header_mode_combo)
        controls.addWidget(QtWidgets.QLabel("Сканировать"))
        controls.addWidget(self.scan_rows_spin)
        controls.addWidget(self.header_row_spin)
        controls.addWidget(self.find_header_button)
        controls.addStretch(1)
        controls_card_layout.addLayout(controls)

        self.header_hint_label = QtWidgets.QLabel("")
        self.header_hint_label.setWordWrap(True)
        controls_card_layout.addWidget(self.header_hint_label)
        layout.addWidget(self.header_controls_card)

        self.preview_card = QtWidgets.QFrame()
        self.preview_card.setObjectName("header_preview_card")
        self._style_neutral_card(self.preview_card)
        preview_layout = QtWidgets.QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(6)
        preview_title = QtWidgets.QLabel("Preview")
        preview_title.setObjectName("header_preview_title")
        preview_layout.addWidget(preview_title)
        self.header_preview = QtWidgets.QTableWidget()
        self.header_preview.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        preview_layout.addWidget(self.header_preview, 1)
        layout.addWidget(self.preview_card, 1)

        self.marker_card = QtWidgets.QFrame()
        self.marker_card.setObjectName("marker_card")
        self._style_neutral_card(self.marker_card)
        marker_card_layout = QtWidgets.QVBoxLayout(self.marker_card)
        marker_card_layout.setContentsMargins(10, 10, 10, 10)
        marker_card_layout.setSpacing(6)
        self.marker_enabled_checkbox = QtWidgets.QCheckBox(
            "Использовать маркеры для поиска шапки при запуске"
        )
        marker_card_layout.addWidget(self.marker_enabled_checkbox)

        self.marker_settings_widget = QtWidgets.QWidget()
        marker_layout = QtWidgets.QVBoxLayout(self.marker_settings_widget)
        marker_layout.setContentsMargins(16, 0, 0, 0)
        marker_layout.setSpacing(6)

        marker_buttons = QtWidgets.QHBoxLayout()
        self.fill_markers_button = QtWidgets.QPushButton("Заполнить из текущей шапки")
        self.clear_markers_button = QtWidgets.QPushButton("Очистить")
        marker_buttons.addWidget(self.fill_markers_button)
        marker_buttons.addWidget(self.clear_markers_button)
        marker_buttons.addStretch(1)
        marker_layout.addLayout(marker_buttons)

        marker_layout.addWidget(QtWidgets.QLabel("Маркеры шапки"))
        self.marker_list_edit = QtWidgets.QPlainTextEdit()
        self.marker_list_edit.setMaximumHeight(90)
        self.marker_list_edit.setPlaceholderText("код\nфио\nиндекс")
        marker_layout.addWidget(self.marker_list_edit)

        marker_options = QtWidgets.QHBoxLayout()
        self.marker_match_mode_combo = QtWidgets.QComboBox()
        self.marker_match_mode_combo.addItem("Любой маркер", "any")
        self.marker_match_mode_combo.addItem("Все маркеры", "all")
        self.marker_scan_rows_spin = QtWidgets.QSpinBox()
        self.marker_scan_rows_spin.setRange(1, 500)
        self.marker_scan_rows_spin.setSuffix(" строк")
        marker_options.addWidget(QtWidgets.QLabel("Совпадение"))
        marker_options.addWidget(self.marker_match_mode_combo)
        marker_options.addWidget(QtWidgets.QLabel("Искать вверху"))
        marker_options.addWidget(self.marker_scan_rows_spin)
        marker_options.addStretch(1)
        marker_layout.addLayout(marker_options)

        self.marker_help_label = QtWidgets.QLabel(
            "При запуске runtime заново ищет шапку по этим маркерам в пользовательском файле."
        )
        self.marker_help_label.setWordWrap(True)
        marker_layout.addWidget(self.marker_help_label)
        marker_card_layout.addWidget(self.marker_settings_widget)
        layout.addWidget(self.marker_card)
        return page

    def _build_columns_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.columns_step = _ColumnsStepWidget()
        layout.addWidget(self.columns_step)
        return page

    def _build_review_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.review_general_card, general_layout = self._create_review_card(
            "Общая конфигурация", "review_general_card"
        )
        self.review_file_label = self._create_review_value_label("review_file_label")
        self.review_mode_label = self._create_review_value_label("review_mode_label")
        self.review_sheet_label = self._create_review_value_label("review_sheet_label")
        self.review_header_label = self._create_review_value_label(
            "review_header_label"
        )
        general_layout.addWidget(self.review_file_label)
        general_layout.addWidget(self.review_mode_label)
        general_layout.addWidget(self.review_sheet_label)
        general_layout.addWidget(self.review_header_label)
        layout.addWidget(self.review_general_card)

        self.review_columns_card, columns_layout = self._create_review_card(
            "Колонки", "review_columns_card"
        )
        self.review_columns_count_label = self._create_review_value_label(
            "review_columns_count_label"
        )
        self.review_column_types_label = self._create_review_value_label(
            "review_column_types_label"
        )
        columns_layout.addWidget(self.review_columns_count_label)
        columns_layout.addWidget(self.review_column_types_label)
        layout.addWidget(self.review_columns_card)

        self.review_markers_card, markers_layout = self._create_review_card(
            "Маркеры", "review_markers_card"
        )
        self.review_markers_state_label = self._create_review_value_label(
            "review_markers_state_label"
        )
        markers_layout.addWidget(self.review_markers_state_label)
        layout.addWidget(self.review_markers_card)

        self.review_sheets_card, sheets_layout = self._create_review_card(
            "Листы", "review_sheets_card"
        )
        self.review_sheets_container = QtWidgets.QVBoxLayout()
        self.review_sheets_container.setContentsMargins(0, 0, 0, 0)
        self.review_sheets_container.setSpacing(8)
        sheets_layout.addLayout(self.review_sheets_container)
        layout.addWidget(self.review_sheets_card)

        self.review_runtime_card, runtime_layout = self._create_review_card(
            "Что получит script.py", "review_runtime_card"
        )
        self.review_runtime_contract_label = self._create_review_value_label(
            "review_runtime_contract_label"
        )
        runtime_layout.addWidget(self.review_runtime_contract_label)
        layout.addWidget(self.review_runtime_card)

        layout.addStretch(1)
        return page

    def _create_review_card(
        self, title: str, object_name: str
    ) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
        frame = QtWidgets.QFrame()
        frame.setObjectName(object_name)
        self._style_neutral_card(frame)
        card_layout = QtWidgets.QVBoxLayout(frame)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName(f"{object_name}_title")
        card_layout.addWidget(title_label)
        body_layout = QtWidgets.QVBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)
        card_layout.addLayout(body_layout)
        return frame, body_layout

    @staticmethod
    def _create_review_value_label(object_name: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel("")
        label.setObjectName(object_name)
        label.setWordWrap(True)
        return label

    def _clear_layout(self, layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _build_sheet_review_block(
        self, sheet_name: str, config: dict[str, Any]
    ) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("review_sheet_summary_block")
        frame.setStyleSheet(
            "#review_sheet_summary_block {"
            "border: 1px solid #E5E7EB;"
            "border-radius: 6px;"
            "background-color: #FFFFFF;"
            "}"
        )
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        title_label = QtWidgets.QLabel(str(sheet_name))
        title_label.setObjectName("review_sheet_summary_title")
        layout.addWidget(title_label)

        header_value = int(config.get("header", 0) or 0) + 1
        selected_columns = list(config.get("selected_columns", []) or [])
        if not config.get("marker_enabled"):
            markers_text = "Маркеры: выключены"
        else:
            markers_text = "Маркеры: " + (
                ", ".join(config.get("header_markers", []) or []) or "не заданы"
            )

        for text in (
            f"Шапка: строка {header_value}",
            f"Колонок: {len(selected_columns)}",
            markers_text,
        ):
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)

        return frame

    def _load_sheets(self) -> None:
        self.sheet_list.clear()
        for sheet_name in read_sheet_names(self._file_path):
            self.sheet_list.addItem(sheet_name)
        if self.sheet_list.count() == 0:
            return
        mode_index = self.sheet_mode_combo.findData(
            str(self._temp_state.get("sheet_mode", "single") or "single")
        )
        self.sheet_mode_combo.blockSignals(True)
        self.sheet_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.sheet_mode_combo.blockSignals(False)
        self._update_sheet_mode_ui()
        self._apply_sheet_selection_from_state()
        self._refresh_active_sheet_choices()
        if self._active_sheet_name:
            self._load_active_sheet_into_ui()

    def _apply_sheet_selection_from_state(self) -> None:
        selected_names = set(self._temp_state.get("sheet_names", []) or [])
        target_sheet = str(self._temp_state.get("sheet_name", "") or "").strip()
        first_index = 0
        self.sheet_list.blockSignals(True)
        try:
            for index in range(self.sheet_list.count()):
                if self.sheet_list.item(index).text() == target_sheet:
                    first_index = index
            if str(self.sheet_mode_combo.currentData() or "single") == "multiple":
                self.sheet_list.setCurrentRow(
                    first_index,
                    QtCore.QItemSelectionModel.SelectionFlag.NoUpdate,
                )
            else:
                self.sheet_list.setCurrentRow(first_index)
            self.sheet_list.clearSelection()
            for index in range(self.sheet_list.count()):
                item = self.sheet_list.item(index)
                if item.text() not in selected_names:
                    continue
                model_index = self.sheet_list.model().index(index, 0)
                self.sheet_list.selectionModel().select(
                    model_index,
                    QtCore.QItemSelectionModel.SelectionFlag.Select,
                )
            if not selected_names and self.sheet_list.count() > 0:
                self.sheet_list.item(first_index).setSelected(True)
        finally:
            self.sheet_list.blockSignals(False)
        self._on_sheet_selection_changed()

    def _selected_sheet_names_from_ui(self) -> list[str]:
        if str(self.sheet_mode_combo.currentData() or "single") == "multiple":
            selected_names = {
                item.text()
                for item in self.sheet_list.selectedItems()
                if item is not None
            }
            return [
                self.sheet_list.item(index).text()
                for index in range(self.sheet_list.count())
                if self.sheet_list.item(index).text() in selected_names
            ]
        current_item = self.sheet_list.currentItem()
        return [current_item.text()] if current_item is not None else []

    def _update_sheet_mode_ui(self) -> None:
        is_multi = str(self.sheet_mode_combo.currentData() or "single") == "multiple"
        self.sheet_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.MultiSelection
            if is_multi
            else QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.select_all_sheets_button.setVisible(is_multi)
        self.clear_sheet_selection_button.setVisible(is_multi)

    def _on_sheet_mode_changed(self) -> None:
        self._sync_active_sheet_config_from_ui()
        self._update_sheet_mode_ui()
        if str(self.sheet_mode_combo.currentData() or "single") == "single":
            current_item = self.sheet_list.currentItem() or (
                self.sheet_list.item(0) if self.sheet_list.count() else None
            )
            self.sheet_list.clearSelection()
            if current_item is not None:
                current_item.setSelected(True)
        elif not self.sheet_list.selectedItems() and self.sheet_list.count():
            self.sheet_list.item(0).setSelected(True)
        self._on_sheet_selection_changed()

    def _select_all_sheets(self) -> None:
        for index in range(self.sheet_list.count()):
            self.sheet_list.item(index).setSelected(True)
        self._on_sheet_selection_changed()

    def _clear_sheet_selection(self) -> None:
        self.sheet_list.clearSelection()
        self._on_sheet_selection_changed()

    def _refresh_active_sheet_choices(self) -> None:
        selected_sheet_names = self._selected_sheet_names_from_ui()
        current_step = self.stack.currentIndex()
        self.active_sheet_bar.setVisible(
            str(self.sheet_mode_combo.currentData() or "single") == "multiple"
            and current_step in {1, 2}
            and bool(selected_sheet_names)
        )
        self.active_sheet_combo.blockSignals(True)
        self.active_sheet_combo.clear()
        for sheet_name in selected_sheet_names:
            self.active_sheet_combo.addItem(sheet_name, sheet_name)
        target_sheet = self._active_sheet_name or (
            selected_sheet_names[0] if selected_sheet_names else ""
        )
        combo_index = self.active_sheet_combo.findData(target_sheet)
        self.active_sheet_combo.setCurrentIndex(combo_index if combo_index >= 0 else 0)
        self.active_sheet_combo.blockSignals(False)
        if selected_sheet_names:
            self._active_sheet_name = str(
                self.active_sheet_combo.currentData() or selected_sheet_names[0]
            )
        else:
            self._active_sheet_name = ""
        self._update_columns_step_context()
        self._update_header_status_card()

    def _on_sheet_selection_changed(self) -> None:
        selected_sheet_names = self._selected_sheet_names_from_ui()
        self._temp_state["sheet_mode"] = str(
            self.sheet_mode_combo.currentData() or "single"
        )
        self._temp_state["sheet_names"] = list(selected_sheet_names)
        self._temp_state["sheet_name"] = (
            selected_sheet_names[0] if selected_sheet_names else ""
        )
        for sheet_name in selected_sheet_names:
            self._ensure_sheet_config(sheet_name)
        if self._active_sheet_name not in selected_sheet_names:
            self._active_sheet_name = (
                selected_sheet_names[0] if selected_sheet_names else ""
            )
        self._refresh_active_sheet_choices()
        self._sync_step_state()

    def _on_sheet_changed(self, row: int) -> None:
        if row < 0:
            self._sync_step_state()
            return
        sheet_name = self.sheet_list.item(row).text()
        if str(self.sheet_mode_combo.currentData() or "single") == "single":
            self._temp_state["sheet_name"] = sheet_name
            self._temp_state["sheet_names"] = [sheet_name]
            self._active_sheet_name = sheet_name
        self._refresh_sheet_preview()
        if self.stack.currentIndex() > 0 and self._active_sheet_name:
            self._load_active_sheet_into_ui()
        self._sync_step_state()

    def _on_active_sheet_combo_changed(self) -> None:
        if self._loading_sheet_ui:
            return
        self._sync_active_sheet_config_from_ui()
        self._active_sheet_name = str(
            self.active_sheet_combo.currentData() or ""
        ).strip()
        if self._active_sheet_name:
            self._load_active_sheet_into_ui()
        self._sync_step_state()

    def _refresh_sheet_preview(self) -> None:
        preview_sheet_name = ""
        current_item = self.sheet_list.currentItem()
        if current_item is not None:
            preview_sheet_name = current_item.text()
        elif self._active_sheet_name:
            preview_sheet_name = self._active_sheet_name
        try:
            preview = build_source_schema_preview(
                self._file_path,
                scan_rows=5,
                header_row=0,
                sheet_name=preview_sheet_name,
            )
        except Exception as exc:
            self.sheet_preview.setRowCount(0)
            self.sheet_preview.setColumnCount(0)
            self.sheet_preview.setToolTip(str(exc))
            return
        self._fill_sheet_preview_table(preview.get("raw_rows", []))

    def _build_default_sheet_config(self, sheet_name: str) -> dict[str, Any]:
        raw_read_config = dict(
            self._temp_state.get(
                "raw_read_config",
                self._temp_state.get("advanced_read_options", {}),
            )
            or {}
        )
        raw_read_config.pop("sheet_name", None)
        raw_read_config["sheet_name"] = sheet_name
        return {
            "sheet_name": sheet_name,
            "header_mode": str(self._temp_state.get("header_mode", "auto") or "auto"),
            "header_strategy": str(
                self._temp_state.get("header_strategy", "densest_unique_row")
                or "densest_unique_row"
            ),
            "header_scan_rows": int(
                self._temp_state.get("header_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            ),
            "header_detected_row": self._temp_state.get(
                "header_detected_row", self._temp_state.get("header")
            ),
            "header_confirmed": bool(self._temp_state.get("header_confirmed", False)),
            "marker_enabled": bool(self._temp_state.get("marker_enabled", True)),
            "header_markers": list(self._temp_state.get("header_markers", []) or []),
            "marker_match_mode": str(
                self._temp_state.get("marker_match_mode", "any") or "any"
            ),
            "marker_scan_rows": int(
                self._temp_state.get("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                or DEFAULT_HEADER_SCAN_ROWS
            ),
            "marker_detected_row_on_sample": self._temp_state.get(
                "marker_detected_row_on_sample", self._temp_state.get("header")
            ),
            "header": self._temp_state.get("header"),
            "skiprows": int(raw_read_config.get("skiprows", 0) or 0),
            "selected_columns": list(
                self._temp_state.get("selected_columns", []) or []
            ),
            "columns_configured": bool(
                self._temp_state.get("columns_configured", False)
            ),
            "column_types": dict(self._temp_state.get("column_types", {}) or {}),
            "raw_read_config": raw_read_config,
            "advanced_read_options": dict(raw_read_config),
        }

    def _ensure_sheet_config(self, sheet_name: str) -> dict[str, Any]:
        configs = self._temp_state.setdefault("sheet_read_configs", {})
        if sheet_name not in configs:
            configs[sheet_name] = self._build_default_sheet_config(sheet_name)
        config = dict(self._build_default_sheet_config(sheet_name))
        config.update(dict(configs.get(sheet_name, {}) or {}))
        config["sheet_name"] = sheet_name
        raw_read_config = dict(
            config.get("raw_read_config", config.get("advanced_read_options", {})) or {}
        )
        raw_read_config["sheet_name"] = sheet_name
        config["raw_read_config"] = raw_read_config
        config["advanced_read_options"] = dict(raw_read_config)
        configs[sheet_name] = config
        return config

    def _finalize_sheet_config(
        self, config: dict[str, Any], *, sheet_name: str
    ) -> dict[str, Any]:
        config["sheet_name"] = sheet_name
        raw_read_config = dict(
            config.get("raw_read_config", config.get("advanced_read_options", {})) or {}
        )
        raw_read_config["sheet_name"] = sheet_name
        if "header" in config:
            raw_read_config["header"] = config.get("header")
        selected_columns = list(config.get("selected_columns", []) or [])
        config["columns_configured"] = bool(config.get("columns_configured", False))
        if selected_columns:
            raw_read_config["usecols"] = list(selected_columns)
        else:
            raw_read_config.pop("usecols", None)
        column_types = dict(config.get("column_types", {}) or {})
        if column_types:
            raw_read_config["dtype"] = dict(column_types)
        else:
            raw_read_config.pop("dtype", None)
        config["raw_read_config"] = raw_read_config
        config["advanced_read_options"] = dict(raw_read_config)
        return config

    def _sync_active_sheet_config_from_ui(self) -> None:
        if self._loading_sheet_ui or not self._active_sheet_name:
            return
        config = dict(self._ensure_sheet_config(self._active_sheet_name))
        config["header_mode"] = str(self.header_mode_combo.currentData() or "auto")
        config["header_scan_rows"] = int(self.scan_rows_spin.value())
        config["marker_enabled"] = self.marker_enabled_checkbox.isChecked()
        config["header_markers"] = self._parse_marker_lines()
        config["marker_match_mode"] = str(
            self.marker_match_mode_combo.currentData() or "any"
        )
        config["marker_scan_rows"] = int(self.marker_scan_rows_spin.value())
        if config["header_mode"] == "manual":
            config["header"] = max(0, self.header_row_spin.value() - 1)
            config["header_detected_row"] = config["header"]
            config["header_confirmed"] = True
        if self.columns_step.table.rowCount() > 0:
            exported_columns = self.columns_step.export_state()
            config.update(exported_columns)
            config["columns_configured"] = bool(
                exported_columns.get("columns_configured", False)
            )
        config["marker_detected_row_on_sample"] = (
            config.get("header") if config.get("marker_enabled") else None
        )
        self._temp_state.setdefault("sheet_read_configs", {})[
            self._active_sheet_name
        ] = self._finalize_sheet_config(config, sheet_name=self._active_sheet_name)

    def _load_active_sheet_into_ui(self) -> None:
        if not self._active_sheet_name:
            return
        config = dict(self._ensure_sheet_config(self._active_sheet_name))
        self._loading_sheet_ui = True
        try:
            header_mode_index = self.header_mode_combo.findData(
                str(config.get("header_mode", "auto") or "auto")
            )
            self.header_mode_combo.setCurrentIndex(
                header_mode_index if header_mode_index >= 0 else 0
            )
            self.scan_rows_spin.setValue(
                int(
                    config.get("header_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                    or DEFAULT_HEADER_SCAN_ROWS
                )
            )
            header_value = config.get("header")
            self.header_row_spin.setValue(int(header_value or 0) + 1)
            self.marker_enabled_checkbox.setChecked(
                bool(config.get("marker_enabled", True))
            )
            self.marker_list_edit.setPlainText(
                "\n".join(config.get("header_markers", []) or [])
            )
            marker_mode_index = self.marker_match_mode_combo.findData(
                str(config.get("marker_match_mode", "any") or "any")
            )
            self.marker_match_mode_combo.setCurrentIndex(
                marker_mode_index if marker_mode_index >= 0 else 0
            )
            self.marker_scan_rows_spin.setValue(
                int(
                    config.get("marker_scan_rows", DEFAULT_HEADER_SCAN_ROWS)
                    or DEFAULT_HEADER_SCAN_ROWS
                )
            )
        finally:
            self._loading_sheet_ui = False
        self._update_marker_controls()
        self._update_columns_step_context()
        self._refresh_header_preview(
            reset_header=not bool(config.get("header_confirmed"))
        )

    def _update_columns_step_context(self) -> None:
        is_multi = str(self.sheet_mode_combo.currentData() or "single") == "multiple"
        current_sheet = ""
        if is_multi:
            current_sheet = self._active_sheet_name
        else:
            selected_sheet_names = self._selected_sheet_names_from_ui()
            current_sheet = selected_sheet_names[0] if selected_sheet_names else ""
        self.columns_step.set_sheet_context(sheet_name=current_sheet, is_multi=is_multi)

    def _refresh_header_preview(self, *, reset_header: bool) -> None:
        if not self._active_sheet_name:
            return
        config = dict(self._ensure_sheet_config(self._active_sheet_name))
        previous_markers = self._parse_marker_lines()
        previous_auto_markers = self._suggest_markers_from_current_header()
        try:
            preview = build_source_schema_preview(
                self._file_path,
                scan_rows=int(self.scan_rows_spin.value()),
                header_row=None if reset_header else config.get("header"),
                sheet_name=self._active_sheet_name,
                selected_columns=list(config.get("selected_columns", []) or []),
                column_types=dict(config.get("column_types", {}) or {}),
            )
        except Exception as exc:
            self.header_hint_label.setText(str(exc))
            self.header_preview.setRowCount(0)
            self.header_preview.setColumnCount(0)
            return

        self._current_preview_rows = preview["rows"]
        self._current_raw_rows = preview.get("raw_rows", [])
        header_row = int(preview["header_row"])
        config["header"] = header_row
        config["header_detected_row"] = header_row
        config["header_confirmed"] = bool(preview.get("header_confirmed", True))
        self.header_row_spin.setValue(header_row + 1)
        confidence = float(preview.get("header_confidence", 0.0) or 0.0)
        explanation = str(preview.get("header_explanation", "") or "").strip()
        if config["header_confirmed"]:
            self.header_hint_label.setText(
                f"Выбран лист: {self._active_sheet_name}. "
                f"Шапка: строка {header_row + 1}. "
                f"Уверенность: {confidence:.2f}. {explanation}"
            )
        else:
            self.header_hint_label.setText(
                f"Автоопределение не уверено ({confidence:.2f}). "
                f"Кандидат: строка {header_row + 1}. Выберите шапку вручную."
            )
        if self.marker_enabled_checkbox.isChecked() and (
            not previous_markers or previous_markers == previous_auto_markers
        ):
            self._fill_markers_from_current_header()
        self._fill_raw_header_table(header_row)
        self.columns_step.load_rows(
            preview["rows"],
            selected_columns=list(config.get("selected_columns", []) or []),
            column_types=dict(config.get("column_types", {}) or {}),
            raw_read_config=dict(
                config.get("raw_read_config", config.get("advanced_read_options", {}))
                or {}
            ),
            columns_configured=bool(config.get("columns_configured", False)),
        )
        self._temp_state.setdefault("sheet_read_configs", {})[
            self._active_sheet_name
        ] = self._finalize_sheet_config(config, sheet_name=self._active_sheet_name)

    def _find_header(self) -> None:
        self._refresh_header_preview(reset_header=True)
        self._sync_step_state()

    def _on_manual_header_changed(self) -> None:
        if self._loading_sheet_ui or not self._active_sheet_name:
            self._sync_step_state()
            return
        if self.header_mode_combo.currentData() != "manual":
            self._sync_step_state()
            return
        config = dict(self._ensure_sheet_config(self._active_sheet_name))
        previous_markers = self._parse_marker_lines()
        previous_auto_markers = self._suggest_markers_from_current_header()
        header_row = max(0, self.header_row_spin.value() - 1)
        try:
            preview = build_source_schema_preview(
                self._file_path,
                scan_rows=int(self.scan_rows_spin.value()),
                header_row=header_row,
                sheet_name=self._active_sheet_name,
                selected_columns=list(config.get("selected_columns", []) or []),
                column_types=dict(config.get("column_types", {}) or {}),
            )
        except Exception as exc:
            self.header_hint_label.setText(str(exc))
            return
        self._current_preview_rows = preview["rows"]
        self._current_raw_rows = preview.get("raw_rows", [])
        config["header"] = header_row
        config["header_detected_row"] = header_row
        config["header_confirmed"] = True
        self.header_hint_label.setText(
            f"Шапка выбрана вручную: строка {header_row + 1}."
        )
        if self.marker_enabled_checkbox.isChecked() and (
            not previous_markers or previous_markers == previous_auto_markers
        ):
            self._fill_markers_from_current_header()
        self._fill_raw_header_table(header_row)
        self.columns_step.load_rows(
            preview["rows"],
            selected_columns=list(config.get("selected_columns", []) or []),
            column_types=dict(config.get("column_types", {}) or {}),
            raw_read_config=dict(
                config.get("raw_read_config", config.get("advanced_read_options", {}))
                or {}
            ),
            columns_configured=bool(config.get("columns_configured", False)),
        )
        self._temp_state.setdefault("sheet_read_configs", {})[
            self._active_sheet_name
        ] = self._finalize_sheet_config(config, sheet_name=self._active_sheet_name)
        self._sync_step_state()

    def _on_header_mode_changed(self) -> None:
        if (
            self.header_mode_combo.currentData() == "manual"
            and not self._temp_state.get("header_confirmed")
        ):
            self._on_manual_header_changed()
            return
        self._sync_step_state()

    def _parse_marker_lines(self) -> list[str]:
        text = self.marker_list_edit.toPlainText().strip()
        if not text:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _suggest_markers_from_current_header(self) -> list[str]:
        markers: list[str] = []
        seen: set[str] = set()
        for row in self._current_preview_rows:
            name = str(row.get("name", "") or "").strip().casefold()
            if not name or name in seen:
                continue
            markers.append(name)
            seen.add(name)
        return markers

    def _fill_markers_from_current_header(self) -> None:
        self.marker_list_edit.setPlainText(
            "\n".join(self._suggest_markers_from_current_header())
        )
        self._sync_step_state()

    def _clear_markers(self) -> None:
        self.marker_list_edit.clear()
        self._sync_step_state()

    def _update_marker_controls(self) -> None:
        self.marker_settings_widget.setVisible(self.marker_enabled_checkbox.isChecked())

    def _on_marker_enabled_toggled(self, checked: bool) -> None:
        self._update_marker_controls()
        if checked and not self._parse_marker_lines():
            self._fill_markers_from_current_header()
        self._sync_step_state()

    def _fill_sheet_preview_table(self, raw_rows: list[list[str]]) -> None:
        table = self.sheet_preview
        if not raw_rows:
            table.setRowCount(0)
            table.setColumnCount(0)
            return
        column_count = max(len(row) for row in raw_rows)
        table.setRowCount(len(raw_rows))
        table.setColumnCount(column_count)
        table.setHorizontalHeaderLabels(
            [chr(65 + index) for index in range(column_count)]
        )
        for row_index, row in enumerate(raw_rows):
            for column_index in range(column_count):
                value = row[column_index] if column_index < len(row) else ""
                table.setItem(
                    row_index, column_index, QtWidgets.QTableWidgetItem(value)
                )

    def _fill_preview_table(
        self, table: QtWidgets.QTableWidget, rows, *, include_header: bool
    ) -> None:
        if not rows:
            table.setRowCount(0)
            table.setColumnCount(0)
            return
        table.setRowCount(len(rows))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Колонка", "Определено"])
        for row_index, row in enumerate(rows):
            table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(str(row["name"])))
            table.setItem(
                row_index, 1, QtWidgets.QTableWidgetItem(str(row["detected_type"]))
            )

    def _fill_raw_header_table(self, header_row: int) -> None:
        rows = self._current_raw_rows
        if not rows:
            self.header_preview.setRowCount(0)
            self.header_preview.setColumnCount(0)
            return
        column_count = max(len(row) for row in rows)
        self.header_preview.setRowCount(len(rows))
        self.header_preview.setColumnCount(column_count)
        self.header_preview.setVerticalHeaderLabels(
            [str(index + 1) for index in range(len(rows))]
        )
        self.header_preview.setHorizontalHeaderLabels(
            [chr(65 + index) for index in range(column_count)]
        )
        for row_index, row in enumerate(rows):
            for column_index in range(column_count):
                value = row[column_index] if column_index < len(row) else ""
                item = QtWidgets.QTableWidgetItem(value)
                if row_index == header_row:
                    item.setBackground(QtCore.Qt.GlobalColor.yellow)
                self.header_preview.setItem(row_index, column_index, item)

    def _go_back(self) -> None:
        self._sync_active_sheet_config_from_ui()
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync_step_state()

    def _go_next(self) -> None:
        self._sync_active_sheet_config_from_ui()
        if self.stack.currentIndex() == 2:
            self._refresh_review()
        next_index = min(self.stack.count() - 1, self.stack.currentIndex() + 1)
        self.stack.setCurrentIndex(next_index)
        if next_index in {1, 2} and self._active_sheet_name:
            self._load_active_sheet_into_ui()
        if next_index == 3:
            self._refresh_review()
        self._sync_step_state()

    def _format_sheet_names_for_status(self, sheet_names: list[str]) -> str:
        normalized = [
            str(sheet_name).strip()
            for sheet_name in sheet_names
            if str(sheet_name).strip()
        ]
        if len(normalized) <= 3:
            return ", ".join(normalized)
        return ", ".join(normalized[:3]) + f" и еще {len(normalized) - 3}"

    def _update_header_status_card(self) -> None:
        is_multi = str(self.sheet_mode_combo.currentData() or "single") == "multiple"
        current_step = self.stack.currentIndex()
        if not is_multi or current_step not in {1, 2}:
            self.active_sheet_bar.setVisible(False)
            return

        selected_sheet_names = self._selected_sheet_names_from_ui()
        if not selected_sheet_names:
            self.active_sheet_bar.setVisible(False)
            return

        sheet_configs = self._temp_state.get("sheet_read_configs", {}) or {}
        if current_step == 1:
            pending = [
                sheet_name
                for sheet_name in selected_sheet_names
                if not bool(
                    dict(sheet_configs.get(sheet_name, {})).get("header_confirmed")
                )
            ]
            blocked_text = "Чтобы продолжить, подтвердите шапку для листов: "
        else:
            pending = [
                sheet_name
                for sheet_name in selected_sheet_names
                if not bool(
                    dict(sheet_configs.get(sheet_name, {})).get("selected_columns", [])
                )
            ]
            blocked_text = "Чтобы продолжить, выберите колонки для листов: "
        if pending:
            self.active_sheet_bar.setProperty("statusState", "blocked")
            self.header_status_message_label.setText(
                blocked_text + self._format_sheet_names_for_status(pending)
            )
        else:
            self.active_sheet_bar.setProperty("statusState", "ready")
            self.header_status_message_label.setText(
                "Все выбранные листы настроены. Можно переходить дальше."
            )

        self.active_sheet_bar.style().unpolish(self.active_sheet_bar)
        self.active_sheet_bar.style().polish(self.active_sheet_bar)
        self.active_sheet_bar.update()
        self.active_sheet_bar.setVisible(True)

    def _refresh_review(self) -> None:
        state = self.get_result_state()
        sheet_mode = str(state.get("sheet_mode", "single") or "single")
        self.review_file_label.setText(f"Файл: {self._file_path}")
        self.review_mode_label.clear()
        self.review_sheet_label.clear()
        self.review_header_label.clear()
        self.review_columns_count_label.clear()
        self.review_column_types_label.clear()
        self.review_markers_state_label.clear()
        self.review_runtime_contract_label.clear()
        self._clear_layout(self.review_sheets_container)

        if sheet_mode == "multiple":
            sheet_names = list(state.get("sheet_names", []) or [])
            self.review_general_card.setVisible(True)
            self.review_columns_card.setVisible(False)
            self.review_markers_card.setVisible(False)
            self.review_sheets_card.setVisible(True)
            self.review_runtime_card.setVisible(True)
            self.review_mode_label.setText("Режим: Несколько листов")
            self.review_sheet_label.setText(f"Листов выбрано: {len(sheet_names)}")
            self.review_header_label.clear()
            for sheet_name in state.get("sheet_names", []) or []:
                config = dict(
                    (state.get("sheet_read_configs", {}) or {}).get(sheet_name, {})
                )
                self.review_sheets_container.addWidget(
                    self._build_sheet_review_block(sheet_name, config)
                )
            self.review_runtime_contract_label.setText(
                "script.py получит:\ninput.workbook\ninput.df_list"
            )
        else:
            selected_columns = state.get("selected_columns", []) or []
            column_types = state.get("column_types", {}) or {}
            self.review_general_card.setVisible(True)
            self.review_columns_card.setVisible(True)
            self.review_markers_card.setVisible(True)
            self.review_sheets_card.setVisible(False)
            self.review_runtime_card.setVisible(False)
            self.review_mode_label.setText("Режим: Один лист")
            self.review_sheet_label.setText(f"Лист: {state.get('sheet_name', '')}")
            self.review_header_label.setText(
                f"Шапка: строка {int(state.get('header', 0) or 0) + 1}"
            )
            self.review_columns_count_label.setText(
                f"Выбрано колонок: {len(selected_columns)}"
            )
            if column_types:
                preview_items = [
                    f"{column_name} -> {column_types.get(column_name, 'auto')}"
                    for column_name in list(column_types.keys())[:3]
                ]
                suffix = (
                    f" и еще {len(column_types) - 3}" if len(column_types) > 3 else ""
                )
                self.review_column_types_label.setText(
                    "Типы: " + ", ".join(preview_items) + suffix
                )
            else:
                self.review_column_types_label.setText("Типы: не заданы")

            if not state.get("marker_enabled"):
                self.review_markers_state_label.setText("Маркеры: выключены")
            else:
                self.review_markers_state_label.setText(
                    "Маркеры: "
                    + (", ".join(state.get("header_markers", []) or []) or "не заданы")
                )

    def _sync_step_state(self) -> None:
        index = self.stack.currentIndex()
        if index in {1, 2}:
            self._sync_active_sheet_config_from_ui()
        self.steps_label.setText(
            f"Шаг {index + 1} из 4: " + ["Лист", "Шапка", "Колонки", "Итог"][index]
        )
        selected_sheet_names = self._selected_sheet_names_from_ui()
        sheet_configs = self._temp_state.get("sheet_read_configs", {}) or {}
        has_sheet = bool(selected_sheet_names)
        has_header = bool(selected_sheet_names) and all(
            bool(dict(sheet_configs.get(sheet_name, {})).get("header_confirmed"))
            for sheet_name in selected_sheet_names
        )
        has_columns = bool(selected_sheet_names) and all(
            bool(dict(sheet_configs.get(sheet_name, {})).get("selected_columns", []))
            for sheet_name in selected_sheet_names
        )

        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < self.stack.count() - 1)
        self.save_button.setVisible(index == self.stack.count() - 1)
        self._refresh_active_sheet_choices()

        if index == 0:
            self.next_button.setEnabled(has_sheet)
        elif index == 1:
            self.next_button.setEnabled(has_header)
        elif index == 2:
            self.next_button.setEnabled(has_columns)


def create_wizard_dialog(
    file_path: str,
    *,
    parent=None,
    initial_state: dict[str, Any] | None = None,
) -> ExcelSourceWizardDialog:
    return ExcelSourceWizardDialog(
        file_path=str(file_path or ""),
        parent=parent,
        initial_state=dict(initial_state or {}),
    )


def open_excel_wizard(
    parent,
    file_path: str,
    *,
    initial_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    dialog = create_wizard_dialog(
        file_path,
        parent=parent,
        initial_state=initial_state,
    )
    result = dialog.exec()
    if result != dialog.DialogCode.Accepted:
        return None
    state = dialog.get_result_state()
    state["file_path"] = str(file_path or "")
    return state
