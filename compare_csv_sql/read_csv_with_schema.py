import pandas as pd
from typing import Dict, Optional


def read_csv_with_schema_v1(
    file_path: str,
    type_mapping: Optional[Dict[str, str]] = None,
    default_type: str = "string",
    **kwargs
) -> pd.DataFrame:
    """
    Считывает CSV файл с указанной схемой типов данных.
    
    Использует pandas nullable-типы для NaN-устойчивости:
    - 'int' → 'Int64' (позволяет NaN)
    - 'bool' → 'boolean' (позволяет NaN)
    - 'float' → 'float64' (NaN уже поддерживается)
    - 'string' → 'string' (по умолчанию)
    
    Args:
        file_path: Путь к CSV файлу
        type_mapping: Словарь с маппингом названий столбцов на типы данных.
                      Пример: {"Столбец3": "float", "Столбец9": "int"}
        default_type: Тип данных по умолчанию для столбцов, не указанных в type_mapping
                      По умолчанию "string"
        **kwargs: Дополнительные параметры для pd.read_csv()
    
    Returns:
        pd.DataFrame: Датафрейм с правильно типизированными столбцами
    
    Raises:
        FileNotFoundError: Если файл не найден
        ValueError: Если тип данных неподдерживаемый
        pd.errors.ParserError: Если файл некорректный CSV
    
    Example:
        >>> type_mapping = {"Столбец3": "float", "Столбец9": "int"}
        >>> df = read_csv_with_schema("data.csv", type_mapping)
    """
    
    if type_mapping is None:
        type_mapping = {}
    
    # Маппинг логических типов на pandas nullable-типы
    # Int64 (заглавная I) и boolean — поддерживают NaN
    NAIVE_TYPE_MAP = {
        'int': 'Int64',
        'float': 'float64',
        'bool': 'boolean',
        'string': 'string',
    }
    
    def resolve_dtype(col_type: str) -> str:
        """Преобразует логический тип в безопасный pandas dtype."""
        resolved = NAIVE_TYPE_MAP.get(col_type)
        if resolved is None:
            raise ValueError(
                f"Неподдерживаемый тип '{col_type}'. "
                f"Поддерживаемые: {', '.join(NAIVE_TYPE_MAP.keys())}"
            )
        return resolved
    
    try:
        # Считываем заголовки — sep/encoding должны совпадать с финальным чтением
        header_kwargs = {
            k: v for k, v in kwargs.items()
            if k in ('sep', 'delimiter', 'encoding', 'sep_whitespace', 'quotechar')
        }
        df_temp = pd.read_csv(file_path, nrows=0, **header_kwargs)        
        columns = df_temp.columns.tolist()
        
        # Создаём словарь dtype с nullable-типами
        dtype_dict = {}
        for column in columns:
            raw_type = type_mapping.get(column, default_type)
            dtype_dict[column] = resolve_dtype(raw_type)
        
        # Читаем файл с указанной типизацией
        df = pd.read_csv(file_path, dtype=dtype_dict, **kwargs)
        
        return df
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(f"Ошибка при чтении CSV файла: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при обработке файла: {e}")
