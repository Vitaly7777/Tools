import pandas as pd
from typing import Dict, List, Tuple, Optional

# Импортируем чанковый компаратор (если модуль доступен)
try:
    from chunked_comparator import ChunkedComparator
except ImportError:
    ChunkedComparator = None

# Импортируем общие утилиты
try:
    from utils import sort_columns_with_suffixes, classify_columns_by_schema
except ImportError:
    sort_columns_with_suffixes = None
    classify_columns_by_schema = None


class InMemoryComparator:
    """
    Оригинальный класс для сравнения DataFrame в оперативной памяти.
    (Переименован из DataFrameComparator для ясности.)
    """
    def __init__(self, df1: pd.DataFrame, df2: pd.DataFrame, float_tolerance: float = 0.0,
                 schema_default=None,
                 compare_columns: List[str] = None,
                 agg_func: str = None,
                 log_callback=None):
        """
        Инициализация компаратора датафреймов
        """
        self.df1 = df1.copy()
        self.df2 = df2.copy()
        self.float_tolerance = float_tolerance
        self.agg_func = agg_func
        self.log_callback = log_callback

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

    def _log(self, message: str):
        """Отправка сообщения в лог"""
        if self.log_callback:
            self.log_callback(message)

    def _log_error(self, message: str):
        """Отправка сообщения об ошибке в лог"""
        if self.log_callback:
            self.log_callback(message, is_error=True)

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
                elif expected_type == "int":
                    if not pd.api.types.is_integer_dtype(actual_type):
                        raise ValueError(
                            f"В датафрейме {df_name} столбец '{column}' имеет тип {actual_type}, "
                            f"ожидается int"
                        )
                elif expected_type == "bool":
                    if not pd.api.types.is_bool_dtype(actual_type):
                        raise ValueError(
                            f"В датафрейме {df_name} столбец '{column}' имеет тип {actual_type}, "
                            f"ожидается bool"
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

    def aggregate(self, agg_func: str = 'sum'):
        """
        Агрегация дублирующихся строк по ключевым столбцам.
        
        Для каждого уникального ключа агрегирует неключевые столбцы:
        - float: sum, mean, min, max
        - string: первое значение (first)
        
        Args:
            agg_func: функция агрегации ('sum', 'mean', 'min', 'max')
        """
        all_cols = list(self.schema.keys())
        non_key_cols = [col for col in all_cols if col not in self.key_columns]
        
        self._log(f"\n{'='*60}")
        self._log(f"НАЧАЛО АГРЕГАЦИИ ДУБЛИКАТОВ")
        self._log(f"Функция агрегации: {agg_func}")
        self._log(f"Ключевые столбцы: {', '.join(self.key_columns)}")
        self._log(f"{'='*60}")
        
        for df_name, df in [('df1', self.df1), ('df2', self.df2)]:
            # Получаем количество строк до агрегации
            rows_before = len(df)
            self._log(f"\nОбработка {df_name}: {rows_before} строк до агрегации")
            
            if df.empty:
                self._log(f"  {df_name}: таблица пуста, пропуск")
                continue
            
            # Определяем числовые колонки ПО СХЕМЕ, а не по значениям.
            # Причины: (1) детерминизм, (2) согласованность с chunked режимом,
            # (3) одинаковое поведение для df1 и df2.
            if classify_columns_by_schema:
                numeric_cols, non_numeric_cols = classify_columns_by_schema(
                    non_key_cols, self.schema, agg_func
                )
            else:
                # Fallback: если utils недоступен
                numeric_cols = []
                non_numeric_cols = []
                for col in non_key_cols:
                    if agg_func == 'first':
                        non_numeric_cols.append(col)
                        continue
                    col_type = self.schema.get(col)
                    if col_type in ('float', 'int'):
                        numeric_cols.append(col)
                    else:
                        non_numeric_cols.append(col)
            
            if numeric_cols:
                self._log(f"  Числовые столбцы (агрегируются): {', '.join(numeric_cols)}")
            if non_numeric_cols:
                self._log(f"  Строковые столбцы (первое значение): {', '.join(non_numeric_cols)}")
            
            # Строим словарь агрегации: числовые — по agg_func, остальные — 'first'
            agg_dict = {col: agg_func for col in numeric_cols}
            for col in non_numeric_cols:
                agg_dict[col] = 'first'
            
            # Выполняем агрегацию
            if agg_dict:
                df_agg = df.groupby(self.key_columns, as_index=False).agg(agg_dict)
            else:
                df_agg = df.drop_duplicates(subset=self.key_columns, keep='first')
            
            rows_after = len(df_agg)
            duplicates_removed = rows_before - rows_after
            
            self._log(f"  После агрегации: {rows_after} строк")
            self._log(f"  Удалено дубликатов: {duplicates_removed}")
            
            if duplicates_removed > 0:
                self._log(f"  ✓ {df_name} агрегирован: {rows_before} → {rows_after} строк")
            else:
                self._log(f"  ℹ {df_name} дубликатов не найдено")
            
            # Обновляем DataFrame
            if df_name == 'df1':
                self.df1 = df_agg
            else:
                self.df2 = df_agg
        
        self._log(f"\nАГРЕГАЦИЯ ЗАВЕРШЕНА")
        self._log(f"{'='*60}\n")

    def compare(self) -> None:
        """Выполнение сравнения датафреймов"""
        # Агрегация если включена
        if self.agg_func:
            self.aggregate(self.agg_func)
        
        self.validate_schema()
        self.sort_dataframes()

        non_key_columns = self._get_non_key_columns()

        # Обработка дубликатов: если агрегация не включена — оставляем первую строку
        # и предупреждаем пользователя.
        # check_uniqueness() уже вызван заранее в main.py.
        for df_name, df in [('df1', self.df1), ('df2', self.df2)]:
            dup_mask = df.duplicated(subset=self.key_columns, keep='first')
            if dup_mask.any():
                dup_count = int(dup_mask.sum())
                self._log(
                    f"  ⚠️ {df_name}: {dup_count} строк с дублирующимися ключами "
                    f"(оставлена первая строка из каждой группы)"
                )
                if df_name == 'df1':
                    self.df1 = df[~dup_mask].reset_index(drop=True)
                else:
                    self.df2 = df[~dup_mask].reset_index(drop=True)

        merged = self.df1.merge(
            self.df2,
            on=self.key_columns,
            how='outer',
            suffixes=('_df1', '_df2'),
            indicator=True,
            sort=False,
        )

        df1_cols = list(self.key_columns) + [f"{c}_df1" for c in non_key_columns]
        df2_cols = list(self.key_columns) + [f"{c}_df2" for c in non_key_columns]
        flat_cols = list(self.key_columns) + list(non_key_columns)

        only1 = merged.loc[merged['_merge'] == 'left_only', df1_cols].reset_index(drop=True)
        only1.columns = flat_cols
        only2 = merged.loc[merged['_merge'] == 'right_only', df2_cols].reset_index(drop=True)
        only2.columns = flat_cols

        self.df1_only = only1 if not only1.empty else pd.DataFrame(columns=self.df1.columns)
        self.df2_only = only2 if not only2.empty else pd.DataFrame(columns=self.df2.columns)

        both = merged.loc[merged['_merge'] == 'both'].reset_index(drop=True)
        if both.empty:
            self.df1_df2_value = None
            return

        # Векторизованная маска: строка различий, если ХОТЯ БЫ ОДИН
        # неключевой столбец не совпал (учитываем tolerance и NaN)
        diff_mask = pd.Series(False, index=both.index)
        for col in non_key_columns:
            s1 = both[f"{col}_df1"]
            s2 = both[f"{col}_df2"]
            both_na = s1.isna() & s2.isna()
            if pd.api.types.is_numeric_dtype(s1) and pd.api.types.is_numeric_dtype(s2):
                diff = (s1.astype(float) - s2.astype(float)).abs()
                equal = (diff <= self.float_tolerance) | both_na
            else:
                equal = (s1 == s2) | both_na
            diff_mask |= ~equal

        diff_df = both.loc[diff_mask]
        if diff_df.empty:
            self.df1_df2_value = None
            return

        result_data = {}
        for col in self.key_columns:
            result_data[col] = diff_df[col].values
        for col in non_key_columns:
            result_data[f"{col}_df1"] = diff_df[f"{col}_df1"].values
            result_data[f"{col}_df2"] = diff_df[f"{col}_df2"].values
        self.df1_df2_value = self._sort_columns_with_suffixes(
            pd.DataFrame(result_data), self.schema
        )

    def _sort_columns_with_suffixes(self, df: pd.DataFrame, schema: List[str] = None) -> pd.DataFrame:
        """Передаёт работу общей утилите из utils.py"""
        if sort_columns_with_suffixes:
            return sort_columns_with_suffixes(df, self.key_columns, schema or self.schema)
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

    def check_uniqueness(self) -> Tuple[Dict[str, Dict], List[Tuple]]:
        """
        Проверка уникальности ключей.
        
        Returns:
            (results, dup_samples) — results: {table: {unique: bool, dup_keys: int, dup_rows: int}}
            dup_samples: список кортежей (table_name, sample_df) для показа в UI
        """
        SEP = '\x01'
        results = {}
        dup_samples = []
        
        for df_name, df in [('df1', self.df1), ('df2', self.df2)]:
            if not self.key_columns or df.empty:
                results[df_name] = {'unique': True, 'dup_keys': 0, 'dup_rows': 0}
                continue
            
            # Создаём составной ключ (аналог key_json в ChunkedComparator)
            df_temp = df.copy()
            df_temp['_composite_key'] = df_temp[self.key_columns].astype(str).agg(SEP.join, axis=1)
            
            # Находим дублирующиеся ключи
            key_counts = df_temp['_composite_key'].value_counts()
            dup_keys = key_counts[key_counts > 1]
            
            if len(dup_keys) == 0:
                results[df_name] = {'unique': True, 'dup_keys': 0, 'dup_rows': 0}
                self._log(f"  ✓ {df_name}: ключи уникальны")
            else:
                dup_keys_count = len(dup_keys)
                dup_rows_count = int(dup_keys.sum())
                
                results[df_name] = {'unique': False, 'dup_keys': dup_keys_count, 'dup_rows': dup_rows_count}
                self._log_error(f"  ⚠️ {df_name}: обнаружено {dup_keys_count} неуникальных ключей ({dup_rows_count} строк)")
                
                # Получаем примеры дублирующихся строк (до 20)
                dup_mask = df_temp['_composite_key'].isin(dup_keys.index)
                sample_data = df_temp[dup_mask].head(20)
                
                if not sample_data.empty:
                    all_cols = list(self.schema.keys())
                    sample_dfs = []
                    for _, row in sample_data.iterrows():
                        row_dict = {col: row[col] for col in all_cols}
                        sample_dfs.append(row_dict)
                    sample_df = pd.DataFrame(sample_dfs)
                    dup_samples.append((df_name, sample_df))
        
        return results, dup_samples


# -------------------------------------------
# ФАБРИКА КОМПАРАТОРОВ
# -------------------------------------------

def create_comparator(df1, df2, key_columns, schema, tolerance=0.0,
                      use_chunked=False, df1_path=None, df2_path=None,
                      chunksize=50000, db_path=None, encoding='utf-8', separator=',',
                      agg_func=None, log_callback=None, progress_callback=None):
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
    if use_chunked:
        if ChunkedComparator is None:
            raise RuntimeError(
                "Чанковый режим недоступен: модуль chunked_comparator "
                "не импортирован (проверьте установку зависимостей)."
            )
        if not df1_path or not df2_path:
            raise ValueError(
                "Для чанкового режима обязательны df1_path и df2_path."
            )
        return ChunkedComparator(
            df1_path, df2_path,
            key_columns, schema, tolerance,
            chunksize=chunksize,
            db_path=db_path,
            encoding=encoding,
            sep=separator,
            agg_func=agg_func,
            log_callback=log_callback,
            progress_callback=progress_callback
        )
    if df1 is None or df2 is None:
        raise ValueError(
            "Для in-memory режима обязательны df1 и df2 (DataFrame)."
        )
    return InMemoryComparator(df1, df2, tolerance, schema, key_columns,
                              agg_func=agg_func, log_callback=log_callback)   

