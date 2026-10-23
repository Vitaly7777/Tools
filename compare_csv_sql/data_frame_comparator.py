import pandas as pd
from typing import Dict, List, Tuple, Optional

# Импортируем чанковый компаратор (если модуль доступен)
try:
    from chunked_comparator import ChunkedComparator
except ImportError:
    ChunkedComparator = None

# Импортируем общие утилиты
try:
    from utils import sort_columns_with_suffixes
except ImportError:
    sort_columns_with_suffixes = None


class InMemoryComparator:
    """
    Оригинальный класс для сравнения DataFrame в оперативной памяти.
    (Переименован из DataFrameComparator для ясности.)
    """
    def __init__(self, df1: pd.DataFrame, df2: pd.DataFrame, float_tolerance: float = 0.0,
                 schema_default=None,
                 compare_columns: List[str] = None):
        """
        Инициализация компаратора датафреймов
        """
        self.df1 = df1.copy()
        self.df2 = df2.copy()
        self.float_tolerance = float_tolerance

        if schema_default is None:
            schema_default = {
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
            }
        self.schema = schema_default

        if compare_columns is None:
            compare_columns = ["Код ЦФО", "Статья Hyperion Forecast", "Источник аллокации",
                               "Сегмент для отчета", "Квартал", "ДЗО"]
        self.key_columns = compare_columns

        self.df1_only = None
        self.df2_only = None
        self.df1_df2_value = None

    def validate_schema(self) -> bool:
        """Проверка соответствия схемы данных для обоих датафреймов"""
        for df_name, df in [("df1", self.df1), ("df2", self.df2)]:
            missing_columns = set(self.schema.keys()) - set(df.columns)
            if missing_columns:
                raise ValueError(
                    f"В датафрейме {df_name} отсутствуют столбцы: {', '.join(missing_columns)}"
                )
            for column, expected_type in self.schema.items():
                actual_type = df[column].dtype
                if expected_type == "string":
                    if not pd.api.types.is_string_dtype(actual_type):
                        raise ValueError(
                            f"В датафрейме {df_name} столбец '{column}' имеет тип {actual_type}, "
                            f"ожидается string"
                        )
                elif expected_type == "float":
                    if not pd.api.types.is_numeric_dtype(actual_type):
                        raise ValueError(
                            f"В датафрейме {df_name} столбец '{column}' имеет тип {actual_type}, "
                            f"ожидается float"
                        )
        return True

    def sort_dataframes(self) -> None:
        """Сортировка датафреймов по ключевым столбцам"""
        self.df1 = self.df1.sort_values(by=self.key_columns, ignore_index=True)
        self.df2 = self.df2.sort_values(by=self.key_columns, ignore_index=True)

    def _create_key(self, row: pd.Series) -> Tuple:
        return tuple(row[col] for col in self.key_columns)

    def _get_non_key_columns(self) -> List[str]:
        return [col for col in self.schema.keys() if col not in self.key_columns]

    def _values_equal(self, val1, val2) -> bool:
        if pd.isna(val1) and pd.isna(val2):
            return True
        if pd.isna(val1) or pd.isna(val2):
            return False
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) <= self.float_tolerance
        return val1 == val2

    def compare(self) -> None:
        """Выполнение сравнения датафреймов"""
        self.validate_schema()
        self.sort_dataframes()

        # Оптимизация: apply(tuple) вместо iterrows() — в 2-3x быстрее
        df1_dict = dict(
            zip(
                self.df1[self.key_columns].apply(tuple, axis=1),
                self.df1.index
            )
        )
        df2_dict = dict(
            zip(
                self.df2[self.key_columns].apply(tuple, axis=1),
                self.df2.index
            )
        )

        df1_only_indices = []
        df2_only_indices = []
        df1_df2_value_data = []
        non_key_columns = self._get_non_key_columns()

        for key, idx1 in df1_dict.items():
            if key not in df2_dict:
                df1_only_indices.append(idx1)
            else:
                idx2 = df2_dict[key]
                row1 = self.df1.iloc[idx1]
                row2 = self.df2.iloc[idx2]
                has_diff = False
                diff_data = {col: row1[col] for col in self.key_columns}
                for col in non_key_columns:
                    if not self._values_equal(row1[col], row2[col]):
                        has_diff = True
                        diff_data[f"{col}_df1"] = row1[col]
                        diff_data[f"{col}_df2"] = row2[col]
                    else:
                        diff_data[f"{col}_df1"] = row1[col]
                        diff_data[f"{col}_df2"] = row2[col]
                if has_diff:
                    df1_df2_value_data.append(diff_data)

        for key, idx2 in df2_dict.items():
            if key not in df1_dict:
                df2_only_indices.append(idx2)

        self.df1_only = self.df1.iloc[df1_only_indices].reset_index(drop=True) \
            if df1_only_indices else pd.DataFrame(columns=self.df1.columns)
        self.df2_only = self.df2.iloc[df2_only_indices].reset_index(drop=True) \
            if df2_only_indices else pd.DataFrame(columns=self.df2.columns)

        if df1_df2_value_data:
            self.df1_df2_value = pd.DataFrame(df1_df2_value_data)
            self.df1_df2_value = self._sort_columns_with_suffixes(self.df1_df2_value)
        else:
            self.df1_df2_value = None

    def _sort_columns_with_suffixes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Передаёт работу общей утилите из utils.py"""
        if sort_columns_with_suffixes:
            return sort_columns_with_suffixes(df, self.key_columns)
        # Fallback: оригинальная реализация
        key_cols = [col for col in self.key_columns if col in df.columns]
        other_cols = [col for col in df.columns if col not in key_cols]
        base_names = set()
        for col in other_cols:
            if col.endswith("_df1"):
                base_names.add(col[:-4])
            elif col.endswith("_df2"):
                base_names.add(col[:-4])
            else:
                base_names.add(col)
        sorted_other_cols = []
        for base_name in sorted(base_names):
            df1_col = f"{base_name}_df1"
            df2_col = f"{base_name}_df2"
            if df1_col in other_cols:
                sorted_other_cols.append(df1_col)
            if df2_col in other_cols:
                sorted_other_cols.append(df2_col)
        return df[key_cols + sorted_other_cols]

    def print_results(self) -> None:
        if (self.df1_only.empty and self.df2_only.empty and self.df1_df2_value is None):
            print("Нет отличий")
        else:
            if not self.df1_only.empty:
                print("\n=== Строки только в df1 (df1_only) ===")
                print(self.df1_only)
            if not self.df2_only.empty:
                print("\n=== Строки только в df2 (df2_only) ===")
                print(self.df2_only)
            if self.df1_df2_value is not None and not self.df1_df2_value.empty:
                print("\n=== Различия в значениях (df1_df2_value) ===")
                print(self.df1_df2_value)


# -------------------------------------------
# ФАБРИКА КОМПАРАТОРОВ
# -------------------------------------------

def create_comparator(df1, df2, key_columns, schema, tolerance=0.0,
                      use_chunked=False, df1_path=None, df2_path=None,
                      chunksize=50000, db_path=None, encoding='utf-8', separator=','):
    """
    Возвращает подходящий компаратор в зависимости от режима.

    Параметры:
        df1, df2: DataFrame (для in-memory режима) или None (для чанкового)
        key_columns: список ключевых столбцов
        schema: словарь типов
        tolerance: допуск для float
        use_chunked: если True, используется чанковый режим
        df1_path, df2_path: пути к CSV (обязательны при use_chunked=True)
        chunksize: размер чанка
        db_path: путь к SQLite (по умолчанию :memory:)

    Возвращает:
        Объект с методами compare() и атрибутами df1_only, df2_only, df1_df2_value.
    """
    if use_chunked and df1_path and df2_path and ChunkedComparator is not None:
        return ChunkedComparator(
            df1_path, df2_path,
            key_columns, schema, tolerance,
            chunksize=chunksize,
            db_path=db_path,
            encoding=encoding,
            sep=separator
        )
    else:
        return InMemoryComparator(df1, df2, tolerance, schema, key_columns)