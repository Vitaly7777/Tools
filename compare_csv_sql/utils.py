"""
Общие утилиты для compare_csv_sql.
Вынесены из main.py, chunked_comparator.py и data_frame_comparator.py
для устранения дублирования кода.
"""

from typing import Dict, List


def sort_columns_with_suffixes(df, key_columns: List[str]):
    """
    Сортирует столбцы DataFrame: ключевые первыми, остальные попарно (_df1, _df2).
    
    Args:
        df: DataFrame для сортировки
        key_columns: Список ключевых столбцов
    
    Returns:
        DataFrame с отсортированными столбцами
    """
    key_cols = [col for col in key_columns if col in df.columns]
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


def parse_schema_text(text: str) -> Dict[str, str]:
    """
    Парсит текстовое представление схемы в словарь {column: type}.
    
    Формат: каждая строка - "имя_столбца:тип"
    Поддерживаемые типы: string, float, int, bool
    Строки, начинающиеся с '#', игнорируются.
    
    Args:
        text: Текстовое представление схемы
    
    Returns:
        Словарь {column_name: column_type}
    
    Raises:
        ValueError: Если строка имеет неверный формат или неподдерживаемый тип
    """
    schema = {}
    for line in text.strip().split("\n"):
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
    
    return schema


def parse_key_columns(text: str) -> List[str]:
    """
    Парсит текст ключевых столбцов (через запятую) в список.
    
    Args:
        text: Текст "col1, col2, col3"
    
    Returns:
        Список ["col1", "col2", "col3"]
    """
    if not text or not text.strip():
        return []
    return [col.strip() for col in text.split(",")]
