"""
Общие утилиты для compare_csv_sql.
Вынесены из main.py, chunked_comparator.py и data_frame_comparator.py
для устранения дублирования кода.
"""

from typing import Dict, List


def sort_columns_with_suffixes(df, key_columns: List[str], schema: Dict[str, str] = None):
    """
    Сортирует столбцы DataFrame: ключевые первыми, остальные попарно (_df1, _df2).
    
    Порядок non-key столбцов определяется схемой (schema), если она передана.
    Иначе используется порядок из DataFrame.
    
    Args:
        df: DataFrame для сортировки
        key_columns: Список ключевых столбцов
        schema: Словарь схемы {column_name: column_type} (опционально)
    
    Returns:
        DataFrame с отсортированными столбцами
    """
    key_cols = [col for col in key_columns if col in df.columns]
    other_cols = [col for col in df.columns if col not in key_cols]
    
    # Определяем порядок non-key столбцов
    if schema:
        # # Порядок из схемы (сохраняет пользовательский порядок)
        # schema_cols = [col for col in schema.keys() if col not in key_cols]
        # # Сохраняем только те, что есть в other_cols (на случай расхождений)
        # schema_order = [col for col in schema_cols if col in other_cols]
        # # Добавляем остальные, которых нет в схеме (на всякий случай)
        # remaining = [col for col in other_cols if col not in schema_order]
        # ordered_bases = schema_order + remaining
    # Идём по схеме и для каждого базового имени берём существующие суффиксы
        ordered_bases = []
        for base in schema.keys():
            if base in key_cols:
                continue
            for suffixed in (f"{base}_df1", f"{base}_df2", base):
                if suffixed in other_cols:
                    ordered_bases.append(suffixed)
        # добавляем всё, что не покрыто схемой
        for col in other_cols:
            if col not in ordered_bases:
                ordered_bases.append(col)        
    else:
        # Fallback: порядок из DataFrame
        ordered_bases = other_cols
    
    # Группируем base_name -> (_df1, _df2)
    base_to_suffixes = {}
    for col in ordered_bases:
        if col.endswith("_df1"):
            base = col[:-4]
            base_to_suffixes.setdefault(base, []).append("_df1")
        elif col.endswith("_df2"):
            base = col[:-4]
            base_to_suffixes.setdefault(base, []).append("_df2")
        else:
            # Столбец без суффикса — добавляем как есть
            base_to_suffixes.setdefault(col, []).append(None)
    
    # Собираем итоговый список столбцов
    sorted_other_cols = []
    for base in base_to_suffixes:
        suffixes = base_to_suffixes[base]
        if None in suffixes:
            # Столбец без суффикса
            sorted_other_cols.append(base)
        else:
            # Парные столбцы _df1, _df2
            if "_df1" in suffixes:
                sorted_other_cols.append(f"{base}_df1")
            if "_df2" in suffixes:
                sorted_other_cols.append(f"{base}_df2")
    
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

