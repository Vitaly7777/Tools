import sqlite3
import hashlib
import pandas as pd
import os
import tempfile
import os
import tempfile
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from pathlib import Path

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
                 max_display_rows: int = 10000):  # <-- сколько строк загружать для отображения
                 insert_batch_size: int = 500,
                 sep: str = ',',
                 max_display_rows: int = 10000):  # <-- сколько строк загружать для отображения
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
        self.sep = sep
        self.max_display_rows = max_display_rows
        self.conn = None
        self.df1_only = pd.DataFrame()      # будет содержать только первые max_display_rows
        self.df1_only = pd.DataFrame()      # будет содержать только первые max_display_rows
        self.df2_only = pd.DataFrame()
        self.df1_df2_value = None
        self._temp_dir = None
        self._saved_files = []  # для хранения путей к сохранённым файлам
        self._temp_dir = None
        self._saved_files = []  # для хранения путей к сохранённым файлам
        self.max_display_rows = max_display_rows
        self._init_db()
        # print(f'DEBUG: self.tolerance = {self.tolerance}')

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
            CREATE TABLE df1 (
                key_hash TEXT PRIMARY KEY,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE df2 (
                key_hash TEXT PRIMARY KEY,
                key_json TEXT,
                row_json TEXT
            )
        ''')
        self.conn.commit()

    def _compute_key_hash(self, row: pd.Series) -> str:
        key_str = SEP.join(str(row[col]) if pd.notna(row[col]) else '' for col in self.key_columns)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def _load_file(self, file_path: str, table_name: str):
        all_cols = list(self.schema.keys())
        cursor = self.conn.cursor()
        for chunk in pd.read_csv(file_path,
                                 usecols=all_cols,
                                 dtype=self.schema,
                                 chunksize=self.chunksize,
                                 low_memory=False,
                                 encoding=self.encoding,
                                 sep=self.sep):
                                 sep=self.sep):
            chunk['key_hash'] = chunk.apply(self._compute_key_hash, axis=1)
            chunk['key_json'] = chunk[self.key_columns].astype(str).agg(SEP.join, axis=1)
            chunk['row_json'] = chunk[all_cols].astype(str).agg(SEP.join, axis=1)
            data = chunk[['key_hash', 'key_json', 'row_json']].values.tolist()
            for i in range(0, len(data), self.insert_batch_size):
                batch = data[i:i+self.insert_batch_size]
                cursor.executemany(
                    f"INSERT OR REPLACE INTO {table_name} (key_hash, key_json, row_json) VALUES (?, ?, ?)",
                    batch
                )
            self.conn.commit()
        self.conn.commit()

    def load_data(self):
        self._load_file(self.df1_path, 'df1')
        self._load_file(self.df2_path, 'df2')

    def _save_full_result_to_csv(self, query: str, columns: List[str], filename: str) -> str:
        """Сохраняет результат запроса в CSV-файл и возвращает путь."""
        # Используем временную директорию или каталог результатов
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
        filepath = os.path.join(self._temp_dir, filename)
        # Пишем в CSV с заголовками, используя итеративный подход
        # Используем pd.read_sql с chunksize для экономии памяти
        first_chunk = True
        for chunk in pd.read_sql(query, self.conn, chunksize=self.chunksize):
            # Если столбцы не заданы, используем из chunk
            if first_chunk:
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='w')
                first_chunk = False
    def _save_full_result_to_csv(self, query: str, columns: List[str], filename: str) -> str:
        """Сохраняет результат запроса в CSV-файл и возвращает путь."""
        # Используем временную директорию или каталог результатов
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="comp_results_")
        filepath = os.path.join(self._temp_dir, filename)
        # Пишем в CSV с заголовками, используя итеративный подход
        # Используем pd.read_sql с chunksize для экономии памяти
        first_chunk = True
        for chunk in pd.read_sql(query, self.conn, chunksize=self.chunksize):
            # Если столбцы не заданы, используем из chunk
            if first_chunk:
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='w')
                first_chunk = False
            else:
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='a', header=False)
        self._saved_files.append(filepath)
        return filepath

    def _get_display_df(self, query: str, columns: List[str], limit: int) -> pd.DataFrame:
        """Загружает только первые limit строк из запроса."""
        # Добавляем LIMIT к запросу (поддерживается SQLite)
        limited_query = f"{query} LIMIT {limit}"
        return pd.read_sql(limited_query, self.conn)
                chunk.to_csv(filepath, index=False, encoding='utf-8-sig', mode='a', header=False)
        self._saved_files.append(filepath)
        return filepath

    def _get_display_df(self, query: str, columns: List[str], limit: int) -> pd.DataFrame:
        """Загружает только первые limit строк из запроса."""
        # Добавляем LIMIT к запросу (поддерживается SQLite)
        limited_query = f"{query} LIMIT {limit}"
        return pd.read_sql(limited_query, self.conn)

    def compare(self):
        all_cols = list(self.schema.keys())
        non_key_cols = [col for col in all_cols if col not in self.key_columns]

        # ---- 1. Только в df1 ----
        query_only1 = '''
            SELECT key_json, row_json FROM df1
            WHERE key_hash NOT IN (SELECT key_hash FROM df2)
        '''
        # Сохраняем полный результат в CSV
        self._save_full_result_to_csv(query_only1, ['key_json', 'row_json'], 'df1_only.csv')
        # Для отображения загружаем только первые строки
        df1_only_raw = self._get_display_df(query_only1, ['key_json', 'row_json'], self.max_display_rows)
        # Сохраняем полный результат в CSV
        self._save_full_result_to_csv(query_only1, ['key_json', 'row_json'], 'df1_only.csv')
        # Для отображения загружаем только первые строки
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

        # ---- 2. Только в df2 ----
        query_only2 = '''
            SELECT key_json, row_json FROM df2
            WHERE key_hash NOT IN (SELECT key_hash FROM df1)
        '''
        self._save_full_result_to_csv(query_only2, ['key_json', 'row_json'], 'df2_only.csv')
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

        # ---- 3. Различия в значениях ----
        query_diff = '''
            SELECT a.key_json, a.row_json AS row1, b.row_json AS row2
            FROM df1 a JOIN df2 b ON a.key_hash = b.key_hash
            WHERE a.row_json != b.row_json
        '''
        self._save_full_result_to_csv(query_diff, ['key_json', 'row1', 'row2'], 'differences.csv')
        diff_raw = self._get_display_df(query_diff, ['key_json', 'row1', 'row2'], self.max_display_rows)
        if not diff_raw.empty:
            # print(f"DEBUG: first row1: {repr(diff_raw['row1'].iloc[0])}")
            # print(f"DEBUG: first row2: {repr(diff_raw['row2'].iloc[0])}")

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
            # print(f'DEBUG: row1_split before rows = {len(row1_split)}')
            # Фильтр по tolerance
            if self.tolerance == 0:
                mask = pd.Series([True] * len(row1_split))
                # print(f'DEBUG: self.tolerance == 0')
            else:
                mask = pd.Series([True] * len(row1_split))
                for col in non_key_cols:
                    if self.schema.get(col) == 'float':
                        diff_abs = (pd.to_numeric(row1_split[col], errors='coerce') -
                                    pd.to_numeric(row2_split[col], errors='coerce')).abs()
                        mask &= (diff_abs > self.tolerance)
                        # print('=====')
                        # print(diff_abs)
                        # print(f'self.tolerance {self.tolerance}')
                    elif self.schema.get(col) == 'string':
                        mask &= (row1_split[col] != row2_split[col])

            row1_split = row1_split[mask]
            row2_split = row2_split[mask]
            # row1_split = row1_split[mask].reset_index(drop=True)
            # row2_split = row2_split[mask].reset_index(drop=True)
            # print(f'DEBUG: row1_split after rows = {len(row1_split)}')
            if not row1_split.empty:
                result_data = {}
                for col in self.key_columns:
                    result_data[col] = row1_split[col].values
                for col in non_key_cols:
                    result_data[f"{col}_df1"] = row1_split[col].values
                    result_data[f"{col}_df2"] = row2_split[col].values
                self.df1_df2_value = self._sort_columns_with_suffixes(pd.DataFrame(result_data))
                # print(f'DEBUG: rdf1_df2_value 1')
                # print(self.df1_df2_value.head())
            else:
                cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + [f"{col}_df2" for col in non_key_cols]
                self.df1_df2_value = pd.DataFrame(columns=cols)
                # print(f'DEBUG: rdf1_df2_value 2')
                # print(self.df1_df2_value.head())
        else:
            cols = self.key_columns + [f"{col}_df1" for col in non_key_cols] + [f"{col}_df2" for col in non_key_cols]
            self.df1_df2_value = pd.DataFrame(columns=cols)
            # print(f'DEBUG: rdf1_df2_value 3')
            # print(self.df1_df2_value.head())

    def _sort_columns_with_suffixes(self, df: pd.DataFrame) -> pd.DataFrame:
        # ... (как в предыдущих версиях)
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

    def _sort_columns_with_suffixes(self, df: pd.DataFrame) -> pd.DataFrame:
        # ... (как в предыдущих версиях)
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

    def _sort_columns_with_suffixes(self, df: pd.DataFrame) -> pd.DataFrame:
        # ... (как в предыдущих версиях)
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
        if self.conn:
            self.conn.close()
        # Можно удалить временные файлы, но пока оставим для доступа

    def get_saved_files(self) -> List[str]:
        """Возвращает пути к сохранённым полным результатам."""
        return self._saved_files
        # Можно удалить временные файлы, но пока оставим для доступа

    def get_saved_files(self) -> List[str]:
        """Возвращает пути к сохранённым полным результатам."""
        return self._saved_files