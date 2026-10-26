import sqlite3
import hashlib
import pandas as pd
import os
import tempfile
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Импортируем общую утилиту
try:
    from utils import sort_columns_with_suffixes
except ImportError:
    sort_columns_with_suffixes = None

SEP = '\x01'


class ChunkedComparator:
    def __init__(self, df1_path: str, df2_path: str,
                 key_columns: List[str],
                 schema: Dict[str, str],
                 tolerance: float = 0.0,
                 chunksize: int = 50000,
                 db_path: Optional[str] = None,
                 encoding: str = 'utf-8',
                 insert_batch_size: int = 500,
                 sep: str = ',',
                 max_display_rows: int = 10000,
                 agg_func: str = None,
                 log_callback=None):
        self.df1_path = df1_path
        self.df2_path = df2_path
        self.key_columns = key_columns
        self.schema = schema
        self.tolerance = tolerance
        self.chunksize = chunksize
        self.db_path = db_path or ":memory:"
        self.encoding = encoding
        self.insert_batch_size = insert_batch_size
        self.sep = sep
        self.max_display_rows = max_display_rows
        self.agg_func = agg_func  # функция агрегации ('sum', 'mean', 'min', 'max') или None
        self.log_callback = log_callback  # callback для логирования
        self.conn = None
        self.df1_only = pd.DataFrame()
        self.df2_only = pd.DataFrame()
        self.df1_df2_value = None
        # Флаги усечения (показаны ли не все строки)
        self._truncated_df1_only = False
        self._truncated_df2_only = False
        self._truncated_df1_df2_value = False
        self._temp_dir = None
        self._saved_files = []
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
            CREATE TABLE df1 (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.execute('''
            CREATE INDEX idx_df1_key_hash ON df1(key_hash)
        ''')
        self.conn.execute('''
            CREATE TABLE df2 (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.execute('''
            CREATE INDEX idx_df2_key_hash ON df2(key_hash)
        ''')
        self.conn.commit()

    def _auto_detect_sep(self, file_path: str) -> str:
        """Автоопределение разделителя CSV файла"""
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                sample = f.read(8192)
            candidates = {
                ',': sample.count(','),
                ';': sample.count(';'),
                '\t': sample.count('\t'),
                '|': sample.count('|')
            }
            best_sep = max(candidates, key=candidates.get)
            if candidates[best_sep] >= 3:
                return best_sep
        except Exception:
            pass
        return ','

    def _validate_columns(self, file_path: str, table_name: str):
        """Проверка что все столбцы из схемы есть в CSV-файле"""
        all_cols = list(self.schema.keys())
        
        # Автоопределение разделителя перед чтением заголовков
        detected_sep = self._auto_detect_sep(file_path)
        
        # Читаем только заголовки с определённым разделителем
        try:
            df_temp = pd.read_csv(file_path, nrows=0, encoding=self.encoding, sep=detected_sep)
            file_columns = set(df_temp.columns)
        except Exception as e:
            raise FileNotFoundError(f"Не удалось прочитать заголовки {file_path}: {e}")
        
        missing_cols = [col for col in all_cols if col not in file_columns]
        if missing_cols:
            available = ', '.join(list(file_columns)[:10])
            if len(file_columns) > 10:
                available += '...'
            raise ValueError(
                f"В файле {table_name} ({file_path}) не найдены столбцы схемы:\n"
                f"  Отсутствуют: {', '.join(missing_cols)}\n"
                f"  Доступные: {available}\n"
                f"  Разделитель определён: '{detected_sep}'"
            )
        
        # Если разделитель не совпадает с указанным — обновляем
        if detected_sep != self.sep:
            self.sep = detected_sep
        
        return True

    def _load_file(self, file_path: str, table_name: str):
        """Загрузка CSV файла в SQLite с оптимизациями:
        1. Один astype(str) вместо трёх
        2. Векторизованное хеширование вместо apply(axis=1)
        """
        all_cols = list(self.schema.keys())
        
        # Валидация столбцов перед загрузкой
        try:
            self._validate_columns(file_path, table_name)
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Ошибка валидации {table_name}: {e}")
        
        cursor = self.conn.cursor()
        for chunk in pd.read_csv(file_path,
                                 usecols=all_cols,
                                 dtype=self.schema,
                                 chunksize=self.chunksize,
                                 low_memory=False,
                                 encoding=self.encoding,
                                 sep=self.sep):
            # Оптимизация: один astype(str) вместо трёх
            # chunk_str = chunk.astype(str).fillna('')
            # ВАЖНО: fillna ДО astype — иначе NaN превращается в строку 'nan'
            # и fillna('') уже ничего не делает.
            chunk_str = chunk.fillna('').astype(str)            

            # Оптимизация: векторизованное хеширование
            # key_strs = chunk_str[self.key_columns].copy()
            # # Заменяем SEP внутри значений, чтобы не ломать парсинг
            # key_strs = key_strs.replace(SEP, ' ', regex=True)
            # key_hash_input = key_strs.agg(SEP.join, axis=1)
            # Экранируем SEP во ВСЕХ строках один раз, а не только в ключах:
            # иначе row_json/key_json содержат "сырой" \x01 и обратный
            # split(SEP) в compare() даст некорректные столбцы.
            chunk_str = chunk_str.replace(SEP, ' ', regex=True)

            key_strs = chunk_str[self.key_columns]
            key_hash_input = key_strs.agg(SEP.join, axis=1)

            chunk['key_hash'] = key_hash_input.apply(
                lambda s: hashlib.md5(s.encode('utf-8')).hexdigest()
            )

            chunk['key_json'] = chunk_str[self.key_columns].agg(SEP.join, axis=1)
            chunk['row_json'] = chunk_str[all_cols].agg(SEP.join, axis=1)
            data = chunk[['key_hash', 'key_json', 'row_json']].values.tolist()
            for i in range(0, len(data), self.insert_batch_size):
                batch = data[i:i + self.insert_batch_size]
                cursor.executemany(
                    f"INSERT INTO {table_name} (key_hash, key_json, row_json) VALUES (?, ?, ?)",
                    batch
                )
            self.conn.commit()
        self.conn.commit()

    def _log(self, message: str):
        """Отправка сообщения в лог"""
        if self.log_callback:
            self.log_callback(message)
    
    def _log_error(self, message: str):
        """Отправка сообщения об ошибке в лог"""
        if self.log_callback:
            self.log_callback(message, is_error=True)
    
    def check_uniqueness(self) -> Tuple[Dict[str, Dict], List[Tuple]]:
        """
        Проверка уникальности ключей через SQL GROUP BY HAVING.
        Использует key_json — сериализованные ключи, как в compare().
        
        Returns:
            (results, dup_samples) — results: {table: {unique: bool, dup_keys: int, dup_rows: int}}
            dup_samples: список кортежей (table_name, sample_df) для показа в UI
        """
        results = {}
        dup_samples = []
        
        for table in ['df1', 'df2']:
            cursor = self.conn.cursor()
            
            # Группируем по key_json — тому же полю, что используется в compare()
            query = f'''
                SELECT key_json, COUNT(*) as cnt
                FROM {table}
                GROUP BY key_json
                HAVING cnt > 1
            '''
            
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
            except Exception as e:
                self._log(f"  ⚠️ Ошибка проверки уникальности в {table}: {e}")
                results[table] = {'unique': True, 'dup_keys': 0, 'dup_rows': 0}
                continue
            
            dup_keys_count = len(rows)
            
            if dup_keys_count == 0:
                results[table] = {'unique': True, 'dup_keys': 0, 'dup_rows': 0}
                self._log(f"  ✓ {table}: ключи уникальны")
            else:
                # Подсчитываем общее количество строк с дубликатами
                count_query = f'''
                    SELECT COUNT(*) FROM {table}
                    WHERE key_json IN (
                        SELECT key_json FROM {table}
                        GROUP BY key_json
                        HAVING COUNT(*) > 1
                    )
                '''
                cursor.execute(count_query)
                dup_rows_count = cursor.fetchone()[0]
                
                results[table] = {'unique': False, 'dup_keys': dup_keys_count, 'dup_rows': dup_rows_count}
                self._log_error(f"  ⚠️ {table}: обнаружено {dup_keys_count} неуникальных ключей ({dup_rows_count} строк)")
                
                # Получаем примеры дублирующихся строк (до 20)
                sample_query = f'''
                    SELECT key_json, row_json FROM {table}
                    WHERE key_json IN (
                        SELECT key_json FROM {table}
                        GROUP BY key_json
                        HAVING COUNT(*) > 1
                    )
                    LIMIT 20
                '''
                cursor.execute(sample_query)
                sample_data = cursor.fetchall()
                
                if sample_data:
                    # Парсим key_json для показа
                    sample_dfs = []
                    for key_json_val, row_json_val in sample_data:
                        keys = key_json_val.split(SEP)
                        row_dict = dict(zip(self.key_columns, keys))
                        sample_dfs.append(row_dict)
                    sample_df = pd.DataFrame(sample_dfs)
                    dup_samples.append((table, sample_df))
        
        return results, dup_samples
    
    def load_data(self):
        self._load_file(self.df1_path, 'df1')
        self._load_file(self.df2_path, 'df2')
        
        # Агрегация если включена
        if self.agg_func:
            self.aggregate(self.agg_func)

    def aggregate(self, agg_func: str = 'sum'):
        """
        Агрегация дублирующихся строк по ключевым столбцам.
        
        Для каждого уникального ключа агрегирует неключевые столбцы:
        - float: sum, mean, min, max
        - string: первое значение (first)
        
        Args:
            agg_func: функция агрегации ('sum', 'mean', 'min', 'max')
        """
        import io
        import csv
        
        all_cols = list(self.schema.keys())
        non_key_cols = [col for col in all_cols if col not in self.key_columns]
        
        self._log(f"\n{'='*60}")
        self._log(f"НАЧАЛО АГРЕГАЦИИ ДУБЛИКАТОВ")
        self._log(f"Функция агрегации: {agg_func}")
        self._log(f"Ключевые столбцы: {', '.join(self.key_columns)}")
        self._log(f"{'='*60}")
        
        for table in ['df1', 'df2']:
            # Получаем количество строк до агрегации
            cursor = self.conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            rows_before = cursor.fetchone()[0]
            self._log(f"\nОбработка {table}: {rows_before} строк до агрегации")
            
            # Читаем все данные из таблицы
            cursor.execute(f'SELECT key_json, row_json FROM {table} ORDER BY row_id')
            rows = cursor.fetchall()
            
            if not rows:
                self._log(f"  {table}: таблица пуста, пропуск")
                continue
            
            # Парсим key_json и row_json
            parsed_data = []
            for key_json, row_json in rows:
                keys = key_json.split(SEP)
                values = row_json.split(SEP)
                row_dict = dict(zip(all_cols, values))
                key_dict = dict(zip(self.key_columns, keys))
                parsed_data.append({**key_dict, **row_dict})
            
            # Создаём DataFrame
            df = pd.DataFrame(parsed_data)
            
            # Проверяем, какие неключевые столбцы числовые
            numeric_cols = []
            non_numeric_cols = []
            
            for col in non_key_cols:
                try:
                    pd.to_numeric(df[col], errors='coerce')
                    # Проверяем, что хотя бы 50% значений числовые
                    numeric_count = df[col].apply(lambda x: pd.to_numeric(x, errors='ignore') if isinstance(x, str) else x).apply(
                        lambda x: isinstance(x, (int, float))
                    ).sum()
                    if numeric_count > len(df) * 0.5:
                        numeric_cols.append(col)
                    else:
                        non_numeric_cols.append(col)
                except (ValueError, TypeError):
                    non_numeric_cols.append(col)
            
            if numeric_cols:
                self._log(f"  Числовые столбцы (агрегируются): {', '.join(numeric_cols)}")
            if non_numeric_cols:
                self._log(f"  Строковые столбцы (первое значение): {', '.join(non_numeric_cols)}")
            
            # Строим словарь агрегации
            agg_dict = {}
            for col in numeric_cols:
                if agg_func == 'first':
                    agg_dict[col] = 'first'
                else:
                    agg_dict[col] = agg_func
            
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
                self._log(f"  ✓ {table} агрегирован: {rows_before} → {rows_after} строк")
            else:
                self._log(f"  ℹ {table} дубликатов не найдено")
            
            # Очищаем таблицу
            self.conn.execute(f'DELETE FROM {table}')
            
            # Подготавливаем данные для вставки
            data_to_insert = []
            for _, row in df_agg.iterrows():
                key_values = [str(row[col]) for col in self.key_columns]
                row_values = [str(row[col]) for col in all_cols]
                
                key_hash_input = SEP.join(key_values)
                key_hash = hashlib.md5(key_hash_input.encode('utf-8')).hexdigest()
                key_json = SEP.join(key_values)
                row_json = SEP.join(row_values)
                
                data_to_insert.append((key_hash, key_json, row_json))
            
            # Вставляем агрегированные данные
            cursor = self.conn.cursor()
            for i in range(0, len(data_to_insert), self.insert_batch_size):
                batch = data_to_insert[i:i + self.insert_batch_size]
                cursor.executemany(
                    f"INSERT INTO {table} (key_hash, key_json, row_json) VALUES (?, ?, ?)",
                    batch
                )
            self.conn.commit()
        
        self._log(f"\nАГРЕГАЦИЯ ЗАВЕРШЕНА")
        self._log(f"{'='*60}\n")

    def _save_full_result_to_csv(self, query: str, columns: List[str], filename: str) -> str:
        """Сохраняет результат запроса в CSV-файл и возвращает путь."""
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
        filepath = os.path.join(self._temp_dir, filename)
        first_chunk = True
        for chunk in pd.read_sql(query, self.conn, chunksize=self.chunksize):
            if first_chunk:
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='w')
                first_chunk = False
            else:
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='a', header=False)
        self._saved_files.append(filepath)
        return filepath

    def _get_display_df(self, query: str, columns: List[str], limit: int) -> pd.DataFrame:
        """Загружает только первые limit строк из запроса."""
        limited_query = f"{query} LIMIT {limit}"
        return pd.read_sql(limited_query, self.conn)

    def compare(self):
        all_cols = list(self.schema.keys())
        non_key_cols = [col for col in all_cols if col not in self.key_columns]

        # ---- 1. Только в df1 ----
        # Оптимизация: LEFT JOIN вместо NOT IN
        query_only1 = '''
            SELECT a.key_json, a.row_json FROM df1 a
            LEFT JOIN df2 b ON a.key_hash = b.key_hash
            WHERE b.key_hash IS NULL
        '''
        self._save_full_result_to_csv(query_only1, ['key_json', 'row_json'], 'df1_only.csv')
        
        # Получаем реальное количество строк для определения усечения
        cursor = self.conn.cursor()
        cursor.execute(query_only1.replace('SELECT a.key_json, a.row_json', 'SELECT COUNT(*)'))
        total_only1 = cursor.fetchone()[0]
        
        df1_only_raw = self._get_display_df(query_only1, ['key_json', 'row_json'], self.max_display_rows)
        if not df1_only_raw.empty:
            split_rows = df1_only_raw['row_json'].str.split(SEP, expand=True)
            if split_rows.shape[1] == len(all_cols):
                split_rows.columns = all_cols
                self.df1_only = split_rows
            else:
                self.df1_only = pd.DataFrame(columns=all_cols)
        else:
            self.df1_only = pd.DataFrame(columns=all_cols)
        
        self._truncated_df1_only = total_only1 > self.max_display_rows

        # ---- 2. Только в df2 ----
        # Оптимизация: LEFT JOIN вместо NOT IN
        query_only2 = '''
            SELECT a.key_json, a.row_json FROM df2 a
            LEFT JOIN df1 b ON a.key_hash = b.key_hash
            WHERE b.key_hash IS NULL
        '''
        self._save_full_result_to_csv(query_only2, ['key_json', 'row_json'], 'df2_only.csv')
        
        cursor = self.conn.cursor()
        cursor.execute(query_only2.replace('SELECT a.key_json, a.row_json', 'SELECT COUNT(*)'))
        total_only2 = cursor.fetchone()[0]
        
        df2_only_raw = self._get_display_df(query_only2, ['key_json', 'row_json'], self.max_display_rows)
        if not df2_only_raw.empty:
            split_rows = df2_only_raw['row_json'].str.split(SEP, expand=True)
            if split_rows.shape[1] == len(all_cols):
                split_rows.columns = all_cols
                self.df2_only = split_rows
            else:
                self.df2_only = pd.DataFrame(columns=all_cols)
        else:
            self.df2_only = pd.DataFrame(columns=all_cols)
        
        self._truncated_df2_only = total_only2 > self.max_display_rows

        # ---- 3. Различия в значениях ----
        query_diff = '''
            SELECT a.key_json, a.row_json AS row1, b.row_json AS row2
            FROM df1 a JOIN df2 b ON a.key_hash = b.key_hash
            WHERE a.row_json != b.row_json
        '''
        self._save_full_result_to_csv(query_diff, ['key_json', 'row1', 'row2'], 'differences.csv')
        
        cursor = self.conn.cursor()
        cursor.execute(query_diff.replace('SELECT a.key_json, a.row_json AS row1, b.row_json AS row2', 'SELECT COUNT(*)'))
        total_diff = cursor.fetchone()[0]
        
        diff_raw = self._get_display_df(query_diff, ['key_json', 'row1', 'row2'], self.max_display_rows)
        if not diff_raw.empty:
            row1_split = diff_raw['row1'].str.split(SEP, expand=True)
            row2_split = diff_raw['row2'].str.split(SEP, expand=True)

            # Дополняем недостающие колонки
            if row1_split.shape[1] != len(all_cols):
                for i in range(len(all_cols) - row1_split.shape[1]):
                    row1_split[i + row1_split.shape[1]] = ''
            if row2_split.shape[1] != len(all_cols):
                for i in range(len(all_cols) - row2_split.shape[1]):
                    row2_split[i + row2_split.shape[1]] = ''
            row1_split = row1_split.iloc[:, :len(all_cols)]
            row2_split = row2_split.iloc[:, :len(all_cols)]
            row1_split.columns = all_cols
            row2_split.columns = all_cols

            # # Фильтр по tolerance
            # if self.tolerance == 0:
            #     mask = pd.Series([True] * len(row1_split))
            # else:
            #     mask = pd.Series([True] * len(row1_split))
            #     for col in non_key_cols:
            #         if self.schema.get(col) == 'float':
            #             diff_abs = (pd.to_numeric(row1_split[col], errors='coerce') -
            #                         pd.to_numeric(row2_split[col], errors='coerce')).abs()
            #             mask &= (diff_abs > self.tolerance)
            #         elif self.schema.get(col) == 'string':
            #             mask &= (row1_split[col] != row2_split[col])

            # Фильтр по tolerance: строка остаётся в отчёте,
            # если ХОТЯ БЫ ОДИН неключевой столбец вне допуска.
            # Ранее использовался AND — ошибочно оставляло только строки,
            # где ВСЕ столбцы различаются одновременно.
            mask = pd.Series(False, index=row1_split.index)
            for col in non_key_cols:
                if self.schema.get(col) == 'float':
                    n1 = pd.to_numeric(row1_split[col], errors='coerce')
                    n2 = pd.to_numeric(row2_split[col], errors='coerce')
                    # Различие вне допуска ИЛИ ровно один NaN
                    col_diff = ((n1 - n2).abs() > self.tolerance) | (n1.isna() ^ n2.isna())
                    mask |= col_diff
                elif self.schema.get(col) == 'string':
                    mask |= (row1_split[col] != row2_split[col])            

            row1_split = row1_split[mask]
            row2_split = row2_split[mask]

            if not row1_split.empty:
                result_data = {}
                for col in self.key_columns:
                    result_data[col] = row1_split[col].values
                for col in non_key_cols:
                    result_data[f"{col}_df1"] = row1_split[col].values
                    result_data[f"{col}_df2"] = row2_split[col].values
                self.df1_df2_value = self._sort_columns_with_suffixes(pd.DataFrame(result_data))
            else:
                cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + \
                       [f"{col}_df2" for col in non_key_cols]
                self.df1_df2_value = pd.DataFrame(columns=cols)
        else:
            cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + \
                   [f"{col}_df2" for col in non_key_cols]
            self.df1_df2_value = pd.DataFrame(columns=cols)
        
        # diff_raw уже усечён на уровне SQL LIMIT, но mask может уменьшить количество строк.
        # Реальное количество строк до маски = len(diff_raw), после = len(self.df1_df2_value).
        # Показываем info про усечение по LIMIT.
        if self.df1_df2_value is not None and not self.df1_df2_value.empty:
            self._truncated_df1_df2_value = total_diff > self.max_display_rows

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

    def close(self):
        # if self.conn:
        #     self.conn.close()
        # if self._temp_dir and os.path.exists(self._temp_dir):
        #     import shutil
        #     shutil.rmtree(self._temp_dir)
        #     self._temp_dir = None

        """Закрывает соединение с БД. Временные файлы НЕ удаляются —
        для их удаления вызовите cleanup()."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def cleanup(self):
        """Удаляет временные файлы с полными результатами."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None
        self._saved_files = []

    def get_saved_files(self) -> List[str]:
        """Возвращает пути к сохранённым полным результатам."""
        return self._saved_files
