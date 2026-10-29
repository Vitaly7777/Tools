import sqlite3
import hashlib
import pandas as pd
import os
import tempfile
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Импортируем общие утилиты
try:
    from utils import sort_columns_with_suffixes, auto_detect_separator, classify_columns_by_schema
except ImportError:
    sort_columns_with_suffixes = None
    auto_detect_separator = None
    classify_columns_by_schema = None

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
                 log_callback=None,
                 progress_callback=None):
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
        self.progress_callback = progress_callback  # callback для прогресса загрузки (current_chunk, total_chunks)
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
        
        # Оптимизации для быстрой вставки миллионов строк
        self.conn.execute('PRAGMA synchronous=OFF')
        self.conn.execute('PRAGMA journal_mode=MEMORY')
        self.conn.execute('PRAGMA temp_store=MEMORY')
        
        # Без AUTOINCREMENT и индексов — вставка в 5-10x быстрее
        # key_hash используется для JOIN, индекс не нужен (JOIN по хешу быстрый)
        self.conn.execute('''
            CREATE TABLE df1 (
                key_hash TEXT,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE df2 (
                key_hash TEXT,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.commit()

    def _auto_detect_sep(self, file_path: str) -> str:
        """Автоопределение разделителя CSV файла"""
        if auto_detect_separator:
            return auto_detect_separator(file_path, self.encoding)
        # Fallback на случай если utils недоступен
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

    def _load_file(self, file_path: str, table_name: str, file_label: str = "",
                   file_total_chunks: int = 0, cumulative_offset: int = 0, cumulative_total: int = 0):
        """Загрузка CSV файла в SQLite с оптимизациями:
        1. Один astype(str) вместо трёх
        2. Векторизованное хеширование вместо apply(axis=1)
        3. Прогресс-бар через progress_callback
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
        batch_count = 0
        commits_per_batch = 100  # commit() раз на 100 батчей (~50 000 строк)
        current_chunk = 0
        total_chunks = 0
        
        # Реальное количество чанков — считаем через тот же pd.read_csv
        total_chunks = self._count_chunks(file_path, all_cols)
        
        try:
            for chunk in pd.read_csv(file_path,
                                      usecols=all_cols,
                                      dtype=self.schema,
                                      chunksize=self.chunksize,
                                      encoding=self.encoding,
                                      sep=self.sep,
                                      engine='python'):
                current_chunk += 1
                
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
                    batch_count += 1
                    # Commit раз на N батчей вместо каждого батча
                    if batch_count % commits_per_batch == 0:
                        self.conn.commit()
                
                # Эмитим прогресс после каждого чанка
                if self.progress_callback:
                    global_current = current_chunk + cumulative_offset if cumulative_offset else current_chunk
                    global_total = cumulative_total if cumulative_total else file_total_chunks
                    self.progress_callback(current_chunk, file_total_chunks,
                                          global_current, global_total, file_label)
        
        except ValueError as e:
            if "Usecols do not match columns" in str(e):
                # Показываем какие столбцы есть в файле
                try:
                    actual_cols = pd.read_csv(file_path, nrows=0, encoding=self.encoding, sep=self.sep).columns.tolist()
                except Exception:
                    actual_cols = ["не удалось прочитать"]
                raise ValueError(
                    f"Столбцы схемы не совпадают со столбцами файла {file_path}:\n"
                    f"  Ожидаются: {', '.join(all_cols)}\n"
                    f"  В файле:   {', '.join(actual_cols)}\n"
                    f"  Разделитель: '{self.sep}'\n\n"
                    f"Проверьте, что выбрана правильная схема для этого файла."
                ) from e
            raise
        
        # Финальный commit
        self.conn.commit()
        
        # Гарантируем прогресс для пустого файла (0 чанков)
        if self.progress_callback and file_total_chunks == 0:
            global_current = cumulative_offset if cumulative_offset else 0
            global_total = cumulative_total if cumulative_total else 1
            self.progress_callback(0, 1, global_current, global_total, file_label)

    def _count_chunks(self, file_path: str, all_cols: list) -> int:
        """Подсчёт реального количества чанков (итераций pd.read_csv)"""
        count = 0
        for _ in pd.read_csv(file_path,
                              usecols=all_cols,
                              chunksize=self.chunksize,
                            #   low_memory=False,
                              encoding=self.encoding,
                              sep=self.sep,
                              engine='python'):
            count += 1
        return max(1, count)

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
            
            # Получаем общее количество строк для логирования
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            total_rows = cursor.fetchone()[0]
            self._log(f"  Проверка уникальности в {table}: {total_rows} строк")
            
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
                self._log(f"  ✓ {table}: все {total_rows} ключей уникальны")
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
                self._log_error(f"  ⚠️ {table}: {dup_keys_count} неуникальных ключей ({dup_rows_count} строк из {total_rows})")
                
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
                    # Парсим key_json и row_json для показа всех столбцов
                    sample_dfs = []
                    all_cols = list(self.schema.keys())
                    for key_json_val, row_json_val in sample_data:
                        keys = key_json_val.split(SEP)
                        row_values = row_json_val.split(SEP)
                        key_dict = dict(zip(self.key_columns, keys))
                        # Дополняем row_values до нужного количества столбцов
                        while len(row_values) < len(all_cols):
                            row_values.append('')
                        row_dict = dict(zip(all_cols, row_values))
                        # Объединяем ключевые столбцы (из key_json) и все столбцы (из row_json)
                        row_dict.update(key_dict)
                        sample_dfs.append(row_dict)
                    sample_df = pd.DataFrame(sample_dfs)
                    dup_samples.append((table, sample_df))
        
        return results, dup_samples
    
    def load_data(self):
        # Считаем чанки для каждого файла заранее
        all_cols = list(self.schema.keys())
        df1_chunks = self._count_chunks(self.df1_path, all_cols)
        df2_chunks = self._count_chunks(self.df2_path, all_cols)
        total_all = df1_chunks + df2_chunks
        
        self._load_file(self.df1_path, 'df1', file_label='Файл 1',
                        file_total_chunks=df1_chunks,
                        cumulative_offset=0, cumulative_total=total_all)
        self._load_file(self.df2_path, 'df2', file_label='Файл 2',
                        file_total_chunks=df2_chunks,
                        cumulative_offset=df1_chunks, cumulative_total=total_all)
        
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

        def _fmt_number(value, col_type):
            """Возвращает строку в том же формате, что _load_file записал в row_json."""
            if pd.isna(value):
                return ''
            if col_type == 'int':
                return str(int(round(float(value))))
            # col_type == 'float'
            return str(float(value))

        
        for table in ['df1', 'df2']:
            # Получаем количество строк до агрегации
            cursor = self.conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            rows_before = cursor.fetchone()[0]
            self._log(f"\nОбработка {table}: {rows_before} строк до агрегации")
            
            # Читаем все данные из таблицы
            # cursor.execute(f'SELECT key_json, row_json FROM {table} ORDER BY row_id')
            cursor.execute(f'SELECT key_json, row_json FROM {table}')
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
            
            # Определяем числовые колонки ПО СХЕМЕ
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
            
            # Конвертируем числовые столбцы в float перед агрегацией
            # (данные хранятся как строки в SQLite, pandas не может агрегировать строки)
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            agg_dict = {col: agg_func for col in numeric_cols}
            for col in non_numeric_cols:
                agg_dict[col] = 'first'
            
            # Выполняем агрегацию
            if agg_dict:
                df_agg = df.groupby(self.key_columns, as_index=False).agg(agg_dict)
            else:
                df_agg = df.drop_duplicates(subset=self.key_columns, keep='first')
            
            # После groupby().agg() числовые столбцы стали float — конвертируем обратно в str
            # для совместимости с последующим форматированием и вставкой в SQLite
            for col in numeric_cols:
                if col in df_agg.columns:
                    df_agg[col] = df_agg[col].apply(lambda x: '' if pd.isna(x) else str(float(x)))
            
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
                
                row_values = [
                    _fmt_number(row[col], self.schema.get(col))
                    if col in numeric_cols else str(row[col])
                    for col in all_cols
                ]

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

    def _expand_csv_columns(self, filename: str, mode: str = 'only'):
        """Раскрывает key_json/row_json в отдельные столбцы схемы в сохранённом CSV.
        
        Args:
            filename: имя файла в self._temp_dir
            mode: 'only' — split row_json -> all_cols;
                  'diff' — split row1/row2 -> all_cols_df1/all_cols_df2
        """
        filepath = os.path.join(self._temp_dir, filename)
        if not os.path.exists(filepath):
            return
        
        all_cols = list(self.schema.keys())
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        def _split_and_align(series, expected_cols):
            """Раскрывает серию строк через SEP и выравнивает столбцы до expected_cols."""
            if series.empty:
                return pd.DataFrame(columns=expected_cols)
            
            # Раскрываем строки
            split_df = series.str.split(SEP, n=-1, expand=True)
            
            # Если split вернул 0 столбцов (все значения пустые)
            if split_df.shape[1] == 0:
                return pd.DataFrame(columns=expected_cols)
            
            # Обрезаем или дополняем до expected_cols
            n_cols = split_df.shape[1]
            if n_cols < len(expected_cols):
                # Дополняем пустыми столбцами
                for i in range(n_cols, len(expected_cols)):
                    split_df[i] = ''
            # Обрезаем лишние столбцы
            split_df = split_df.iloc[:, :len(expected_cols)]
            
            # Присваиваем правильные имена столбцов
            split_df.columns = expected_cols
            
            return split_df
        
        if mode == 'only':
            # row_json -> all_cols
            split_cols = _split_and_align(df['row_json'], all_cols)
            
            # key_json -> key_columns
            key_split = _split_and_align(df['key_json'], self.key_columns)
            
            expanded = pd.concat([key_split, split_cols], axis=1)
            expanded.to_csv(filepath, index=False, encoding='utf-8-sig')
            
        elif mode == 'diff':
            # key_json -> key_columns
            key_split = _split_and_align(df['key_json'], self.key_columns)
            
            # row1 -> all_cols_df1
            df1_cols = [f"{col}_df1" for col in all_cols]
            row1_split = _split_and_align(df['row1'], df1_cols)
            
            # row2 -> all_cols_df2
            df2_cols = [f"{col}_df2" for col in all_cols]
            row2_split = _split_and_align(df['row2'], df2_cols)
            
            # Собираем столбцы в правильном порядке: key + попарно col_df1, col_df2
            ordered_cols = list(key_split.columns)
            for col in all_cols:
                df1_col = f"{col}_df1"
                df2_col = f"{col}_df2"
                if df1_col in row1_split.columns:
                    ordered_cols.append(df1_col)
                if df2_col in row2_split.columns:
                    ordered_cols.append(df2_col)
            
            expanded = pd.concat([key_split, row1_split, row2_split], axis=1)[ordered_cols]
            expanded.to_csv(filepath, index=False, encoding='utf-8-sig')

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
        self._expand_csv_columns('df1_only.csv', mode='only')
        
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
        self._expand_csv_columns('df2_only.csv', mode='only')
        
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
        
        # Получаем все различия из SQL (по строковому сравнению)
        cursor = self.conn.cursor()
        cursor.execute(query_diff)
        diff_rows = cursor.fetchall()
        total_diff = len(diff_rows)
        
        # Применяем tolerance-фильтр к ПОЛНЫМ данным, а не только к отображаемым
        if diff_rows:
            # Парсим все различия
            all_row1 = [r[1] for r in diff_rows]
            all_row2 = [r[2] for r in diff_rows]
            
            diff_df = pd.DataFrame({'row1': all_row1, 'row2': all_row2})
            
            row1_split = diff_df['row1'].str.split(SEP, n=-1, expand=True)
            row2_split = diff_df['row2'].str.split(SEP, n=-1, expand=True)
            
            # Дополняем недостающие колонки
            if row1_split.shape[1] < len(all_cols):
                for i in range(row1_split.shape[1], len(all_cols)):
                    row1_split[i] = ''
            if row2_split.shape[1] < len(all_cols):
                for i in range(row2_split.shape[1], len(all_cols)):
                    row2_split[i] = ''
            row1_split = row1_split.iloc[:, :len(all_cols)]
            row2_split = row2_split.iloc[:, :len(all_cols)]
            row1_split.columns = all_cols
            row2_split.columns = all_cols
            
            # Фильтр по tolerance: строка остаётся в отчёте,
            # если ХОТЯ БЫ ОДИН неключевой столбец вне допуска.
            mask = pd.Series(False, index=row1_split.index)
            for col in non_key_cols:
                if self.schema.get(col) == 'float':
                    n1 = pd.to_numeric(row1_split[col], errors='coerce')
                    n2 = pd.to_numeric(row2_split[col], errors='coerce')
                    col_diff = ((n1 - n2).abs() > self.tolerance) | (n1.isna() ^ n2.isna())
                    mask |= col_diff
                elif self.schema.get(col) == 'string':
                    mask |= (row1_split[col] != row2_split[col])
            
            # Фильтруем ПОЛНЫЕ данные по tolerance
            row1_split_filtered = row1_split[mask]
            row2_split_filtered = row2_split[mask]
            
            # Обновляем total_diff с учётом tolerance
            total_diff = len(row1_split_filtered)
            
            # Сохраняем ФИЛЬТРОВАННЫЕ данные в CSV
            if not row1_split_filtered.empty:
                result_data = {}
                for col in self.key_columns:
                    # Получаем key_json для отфильтрованных строк
                    filtered_indices = row1_split_filtered.index.tolist()
                    result_data[col] = [diff_rows[i][0].split(SEP)[k] 
                                       for i in filtered_indices 
                                       for k, _ in enumerate(self.key_columns)]
                
                # Перестраиваем key_columns правильно
                filtered_keys = [diff_rows[i][0] for i in row1_split_filtered.index.tolist()]
                key_split_filtered = pd.DataFrame({'key_json': filtered_keys})
                key_split = key_split_filtered['key_json'].str.split(SEP, n=-1, expand=True)
                key_split.columns = self.key_columns
                
                result_data = {}
                for col in self.key_columns:
                    result_data[col] = key_split[col].values
                for col in non_key_cols:
                    result_data[f"{col}_df1"] = row1_split_filtered[col].values
                    result_data[f"{col}_df2"] = row2_split_filtered[col].values
                
                diff_filtered = pd.DataFrame(result_data)
                
                # Сохраняем отфильтрованные данные
                filepath = os.path.join(self._temp_dir, 'differences.csv') if self._temp_dir else None
                if filepath is None:
                    self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
                    filepath = os.path.join(self._temp_dir, 'differences.csv')
                diff_filtered.to_csv(filepath, index=False, encoding='utf-8-sig')
                self._saved_files.append(filepath)
                
                # Применяем _expand_csv_columns
                # Раскрываем столбцы (они уже раскрыты, просто обновляем файл)
                df_csv = pd.read_csv(filepath, encoding='utf-8-sig')
                # Столбцы уже в правильном формате (key + col_df1/col_df2)
            else:
                # Нет различий после фильтрации
                filepath = os.path.join(self._temp_dir, 'differences.csv') if self._temp_dir else None
                if filepath is None:
                    self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
                    filepath = os.path.join(self._temp_dir, 'differences.csv')
                cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + \
                       [f"{col}_df2" for col in non_key_cols]
                pd.DataFrame(columns=cols).to_csv(filepath, index=False, encoding='utf-8-sig')
                self._saved_files.append(filepath)
        else:
            total_diff = 0
            filepath = os.path.join(self._temp_dir, 'differences.csv') if self._temp_dir else None
            if filepath is None:
                self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
                filepath = os.path.join(self._temp_dir, 'differences.csv')
            cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + \
                   [f"{col}_df2" for col in non_key_cols]
            pd.DataFrame(columns=cols).to_csv(filepath, index=False, encoding='utf-8-sig')
            self._saved_files.append(filepath)
        
        self._total_diff = total_diff
        
        # Получаем отображаемые данные (лимитируем для UI)
        diff_full_path = os.path.join(self._temp_dir, 'differences.csv')
        if os.path.exists(diff_full_path):
            diff_full = pd.read_csv(diff_full_path, encoding='utf-8-sig')
            if len(diff_full) > self.max_display_rows:
                diff_raw = diff_full.head(self.max_display_rows)
                self._truncated_df1_df2_value = True
            else:
                diff_raw = diff_full
        else:
            diff_raw = pd.DataFrame()
        
        if not diff_raw.empty:
            row1_split = diff_raw[[c for c in diff_raw.columns if c.endswith("_df1")]].copy()
            row2_split = diff_raw[[c for c in diff_raw.columns if c.endswith("_df2")]].copy()
            
            # Восстанавливаем имена столбцов (без _df1/_df2)
            df1_cols = [c[:-4] for c in row1_split.columns]
            df2_cols = [c[:-4] for c in row2_split.columns]
            row1_split.columns = df1_cols
            row2_split.columns = df2_cols
            
            if not row1_split.empty:
                result_data = {}
                for col in self.key_columns:
                    result_data[col] = diff_raw[col].values
                for col in non_key_cols:
                    result_data[f"{col}_df1"] = row1_split[col].values
                    result_data[f"{col}_df2"] = row2_split[col].values
                self.df1_df2_value = self._sort_columns_with_suffixes(
                    pd.DataFrame(result_data), self.schema
                )
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

        self._total_only1 = total_only1
        self._total_only2 = total_only2
        self._total_diff = total_diff    

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

