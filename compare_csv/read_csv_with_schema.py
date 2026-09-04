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
    
    Args:
        file_path: Путь к CSV файлу
        type_mapping: Словарь с маппингом названий столбцов на типы данных.
                     Если None, используется значение по умолчанию.
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
    
    try:
        # Сначала читаем файл без типизации для получения названий столбцов
        df_temp = pd.read_csv(file_path, nrows=0)
        columns = df_temp.columns.tolist()
        
        # Создаем словарь dtype для всех столбцов
        dtype_dict = {}
        
        for column in columns:
            if column in type_mapping:
                dtype_dict[column] = type_mapping[column]
            else:
                dtype_dict[column] = default_type
        
        # Читаем файл с указанной типизацией
        df = pd.read_csv(file_path, dtype=dtype_dict, **kwargs)
        
        print(f"Файл успешно загружен: {file_path}")
        print(f"Количество строк: {len(df)}")
        print(f"Количество столбцов: {len(df.columns)}")
        print("\nТипы данных:")
        print(df.dtypes)
        
        return df
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(f"Ошибка при чтении CSV файла: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при обработке файла: {e}")


def read_csv_with_schema_v2(
    file_path: str,
    type_mapping: Optional[Dict[str, str]] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Альтернативная версия с более подробной обработкой типов.
    
    Args:
        file_path: Путь к CSV файлу
        type_mapping: Словарь маппинга типов.
                     Пример: {"Столбец3": "float", "Столбец9": "int"}
        **kwargs: Дополнительные параметры для pd.read_csv()
    
    Returns:
        pd.DataFrame: Датафрейм с правильно типизированными столбцами
    """
    
    if type_mapping is None:
        type_mapping = {}
    
    # Поддерживаемые типы данных
    supported_types = {
        "string": str,
        "int": int,
        "float": float,
        "bool": bool,
        "datetime": "datetime64[ns]"
    }
    
    # Валидация типов в type_mapping
    for column, dtype in type_mapping.items():
        if dtype not in supported_types:
            raise ValueError(
                f"Неподдерживаемый тип '{dtype}' для столбца '{column}'. "
                f"Поддерживаемые типы: {list(supported_types.keys())}"
            )
    
    try:
        # Читаем первую строку для получения названий столбцов
        df_temp = pd.read_csv(file_path, nrows=0)
        columns = df_temp.columns.tolist()
        
        # Создаем словарь dtype
        dtype_dict = {}
        
        for column in columns:
            if column in type_mapping:
                mapped_type = type_mapping[column]
                dtype_dict[column] = supported_types[mapped_type]
            else:
                dtype_dict[column] = str  # По умолчанию string
        
        # Читаем файл
        df = pd.read_csv(file_path, dtype=dtype_dict, **kwargs)
        
        # Информация о загрузке
        print("=" * 60)
        print(f"✓ Файл успешно загружен: {file_path}")
        print(f"✓ Размер датафрейма: {len(df)} строк × {len(df.columns)} столбцов")
        print("=" * 60)
        print("\nТипы данных столбцов:")
        print("-" * 60)
        
        for column, dtype in df.dtypes.items():
            print(f"  {column:<30} : {dtype}")
        
        print("-" * 60)
        
        return df
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(f"Ошибка при чтении CSV файла: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при обработке файла: {e}")


def read_csv_with_schema_v3(
    file_path: str,
    type_mapping: Optional[Dict[str, type]] = None,
    default_type: type = str,
    encoding: str = "utf-8",
    sep: str = ",",
    **kwargs
) -> pd.DataFrame:
    """
    Версия с использованием типов Python напрямую.
    
    Args:
        file_path: Путь к CSV файлу
        type_mapping: Словарь маппинга типов Python.
                     Пример: {"Столбец3": float, "Столбец9": int}
        default_type: Тип данных по умолчанию (используется type Python)
        encoding: Кодировка файла (по умолчанию utf-8)
        sep: Разделитель CSV (по умолчанию запятая)
        **kwargs: Дополнительные параметры для pd.read_csv()
    
    Returns:
        pd.DataFrame: Датафрейм с правильно типизированными столбцами
    """
    
    if type_mapping is None:
        type_mapping = {}
    
    try:
        # Читаем первую строку для получения названий столбцов
        df_temp = pd.read_csv(
            file_path,
            nrows=0,
            encoding=encoding,
            sep=sep
        )
        columns = df_temp.columns.tolist()
        
        # Создаем словарь dtype
        dtype_dict = {}
        
        for column in columns:
            if column in type_mapping:
                dtype_dict[column] = type_mapping[column]
            else:
                dtype_dict[column] = default_type
        
        # Читаем файл с полной типизацией
        df = pd.read_csv(
            file_path,
            dtype=dtype_dict,
            encoding=encoding,
            sep=sep,
            **kwargs
        )
        
        # Вывод информации
        print(f"\n{'Информация о загруженном файле':^60}")
        print("=" * 60)
        print(f"Файл: {file_path}")
        print(f"Размер: {len(df)} строк × {len(df.columns)} столбцов")
        print("=" * 60)
        print(f"\n{'Типы данных':^60}")
        print("-" * 60)
        
        for column in df.columns:
            original_type = type_mapping.get(column, default_type).__name__
            actual_type = str(df[column].dtype)
            status = "✓" if str(original_type).lower() in actual_type.lower() or \
                           (original_type == "str" and actual_type == "object") else "⚠"
            print(f"{status} {column:<30} : {actual_type}")
        
        print("-" * 60)
        
        return df
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    except pd.errors.ParserError as e:
        raise pd.errors.ParserError(f"Ошибка при чтении CSV файла: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при обработке файла: {e}")


# ============================================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ============================================================================

if __name__ == "__main__":
    
    # Создание примера CSV файла для тестирования
    import os
    
    # Создаем пример CSV файла
    sample_csv = "sample_data.csv"
    
    sample_data = """Столбец1,Столбец2,Столбец3,Столбец4,Столбец5,Столбец9
Текст1,Текст2,10.5,Текст4,Текст5,1
Текст6,Текст7,20.3,Текст8,Текст9,2
Текст10,Текст11,15.7,Текст12,Текст13,3
Текст14,Текст15,25.2,Текст16,Текст17,4"""
    
    with open(sample_csv, "w", encoding="utf-8") as f:
        f.write(sample_data)
    
    print("ПРИМЕР 1: Базовое использование v1")
    print("=" * 60)
    try:
        type_mapping = {"Столбец3": "float", "Столбец9": "int"}
        df1 = read_csv_with_schema_v1(sample_csv, type_mapping)
        print("\nПервые строки датафрейма:")
        print(df1.head())
    except Exception as e:
        print(f"Ошибка: {e}")
    
    print("\n\nПРИМЕР 2: Использование v2 (с подробной информацией)")
    print("=" * 60)
    try:
        type_mapping = {"Столбец3": "float", "Столбец9": "int"}
        df2 = read_csv_with_schema_v2(sample_csv, type_mapping)
        print("\nПервые строки датафрейма:")
        print(df2.head())
    except Exception as e:
        print(f"Ошибка: {e}")
    
    print("\n\nПРИМЕР 3: Использование v3 (с типами Python)")
    print("=" * 60)
    try:
        type_mapping = {"Столбец3": float, "Столбец9": int}
        df3 = read_csv_with_schema_v3(sample_csv, type_mapping)
        print("\nПервые строки датафрейма:")
        print(df3.head())
        print("\nПроверка типов:")
        print(df3.dtypes)
    except Exception as e:
        print(f"Ошибка: {e}")
    
    # Очистка
    if os.path.exists(sample_csv):
        os.remove(sample_csv)
