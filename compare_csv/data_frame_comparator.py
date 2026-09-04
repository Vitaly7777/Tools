import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class DataFrameComparator:
    def __init__(self, df1: pd.DataFrame, df2: pd.DataFrame, float_tolerance: float = 0.0, 
                 schema_default  = {
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
        },
        compare_columns: List[str] = ["Код ЦФО", "Статья Hyperion Forecast", "Источник аллокации", 
                                     "Сегмент для отчета", "Квартал", 
                                     "ДЗО"]
        ):
        """
        Инициализация компаратора датафреймов
        
        Args:
            df1: Первый датафрейм
            df2: Второй датафрейм
            float_tolerance: Допуск для сравнения float значений
        """
        self.df1 = df1.copy()
        self.df2 = df2.copy()
        self.float_tolerance = float_tolerance
        
        # Определение схемы данных
        self.schema = schema_default

        # Ключевые столбцы для сравнения
        self.key_columns = compare_columns
        # Результирующие датафреймы
        self.df1_only = None
        self.df2_only = None
        self.df1_df2_value = None
        
    def validate_schema(self) -> bool:
        """
        Проверка соответствия схемы данных для обоих датафреймов
        
        Returns:
            True если валидация успешна
            
        Raises:
            ValueError если есть несоответствие
        """
        for df_name, df in [("df1", self.df1), ("df2", self.df2)]:
            # Проверка наличия всех столбцов
            missing_columns = set(self.schema.keys()) - set(df.columns)
            if missing_columns:
                raise ValueError(
                    f"В датафрейме {df_name} отсутствуют столбцы: {', '.join(missing_columns)}"
                )
            
            # Проверка типов данных
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
        """
        Создание ключа из значений ключевых столбцов
        
        Args:
            row: Строка датафрейма
            
        Returns:
            Кортеж ключевых значений
        """
        return tuple(row[col] for col in self.key_columns)
    
    def _get_non_key_columns(self) -> List[str]:
        """Получение списка неключевых столбцов"""
        return [col for col in self.schema.keys() if col not in self.key_columns]
    
    def _values_equal(self, val1, val2) -> bool:
        """
        Сравнение значений с учетом типа и допуска
        
        Args:
            val1: Первое значение
            val2: Второе значение
            
        Returns:
            True если значения равны
        """
        # Обработка NaN значений
        if pd.isna(val1) and pd.isna(val2):
            return True
        if pd.isna(val1) or pd.isna(val2):
            return False
        
        # Для float значений применять допуск
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) <= self.float_tolerance
        
        # Для остальных типов - прямое сравнение
        return val1 == val2
    
    def compare(self) -> None:
        """Выполнение сравнения датафреймов"""
        # Валидация схемы
        self.validate_schema()
        
        # Сортировка
        self.sort_dataframes()
        
        # Создание словарей для быстрого поиска
        df1_dict = {self._create_key(row): idx for idx, row in self.df1.iterrows()}
        df2_dict = {self._create_key(row): idx for idx, row in self.df2.iterrows()}
        
        df1_only_indices = []
        df2_only_indices = []
        df1_df2_value_data = []
        
        non_key_columns = self._get_non_key_columns()
        
        # Поиск строк только в df1 и различий
        for key, idx1 in df1_dict.items():
            if key not in df2_dict:
                # Ключ только в df1
                df1_only_indices.append(idx1)
            else:
                # Ключ есть в обоих, проверяем значения
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
                        # Значения одинаковые, добавляем с суффиксом для консистентности
                        diff_data[f"{col}_df1"] = row1[col]
                        diff_data[f"{col}_df2"] = row2[col]
                
                if has_diff:
                    df1_df2_value_data.append(diff_data)
        
        # Поиск строк только в df2
        for key, idx2 in df2_dict.items():
            if key not in df1_dict:
                df2_only_indices.append(idx2)
        
        # Создание результирующих датафреймов
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
        """
        Сортировка столбцов так чтобы _df1 шли перед _df2
        
        Args:
            df: Датафрейм для сортировки
            
        Returns:
            Датафрейм с отсортированными столбцами
        """
        # Сначала ключевые столбцы
        key_cols = [col for col in self.key_columns if col in df.columns]
        
        # Затем остальные столбцы, сгруппированные по базовому имени
        other_cols = [col for col in df.columns if col not in key_cols]
        
        # Получить базовые имена (без суффиксов)
        base_names = set()
        for col in other_cols:
            if col.endswith("_df1"):
                base_names.add(col[:-4])
            elif col.endswith("_df2"):
                base_names.add(col[:-4])
            else:
                base_names.add(col)
        
        # Сортировка: для каждого базового имени сначала _df1, потом _df2
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
        """Вывод результатов сравнения"""
        if (self.df1_only.empty and 
            self.df2_only.empty and 
            self.df1_df2_value is None):
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


# Пример использования
if __name__ == "__main__":
    # Создание примеров датафреймов
    data1 = {
        "Код ЦФО": ["ЦФО1", "ЦФО2", "ЦФО3"],
        "Статья Hyperion Forecast": ["Статья1", "Статья2", "Статья1"],
        "Источник аллокации": ["Источник1", "Источник1", "Источник2"],
        "Сегмент для отчета": ["Сегмент1", "Сегмент2", "Сегмент1"],
        "Квартал": ["Q1", "Q1", "Q2"],
        "Значение": [100.0, 200.0, 150.0],
        "Пользовательская": ["Пользователь1", "Пользователь2", "Пользователь1"],
        "Версия": ["V1", "V1", "V1"],
        "План/Прогноз": ["План", "Прогноз", "План"],
        "Группировка для анализа": ["Группа1", "Группа2", "Группа1"],
        "ДЗО": ["ДЗО1", "ДЗО2", "ДЗО1"],
        "БЕ": ["БЕ1", "БЕ2", "БЕ1"]
    }
    
    data2 = {
        "Код ЦФО": ["ЦФО1", "ЦФО2", "ЦФО4"],
        "Статья Hyperion Forecast": ["Статья1", "Статья2", "Статья3"],
        "Источник аллокации": ["Источник1", "Источник1", "Источник2"],
        "Сегмент для отчета": ["Сегмент1", "Сегмент2", "Сегмент2"],
        "Квартал": ["Q1", "Q1", "Q2"],
        "Значение": [100.5, 250.0, 300.0],  # Первое значение отличается в пределах допуска
        "Пользовательская": ["Пользователь1", "Пользователь3", "Пользователь2"],
        "Версия": ["V1", "V2", "V1"],
        "План/Прогноз": ["План", "Прогноз", "План"],
        "Группировка для анализа": ["Группа1", "Группа2", "Группа2"],
        "ДЗО": ["ДЗО1", "ДЗО3", "ДЗО2"],
        "БЕ": ["БЕ1", "БЕ2", "БЕ2"]
    }
    
    df1 = pd.DataFrame(data1)
    df2 = pd.DataFrame(data2)
    
    try:
        # Создание компаратора с допуском 1.0 для float значений
        comparator = DataFrameComparator(df1, df2, float_tolerance=1.0)
        
        # Выполнение сравнения
        comparator.compare()
        
        # Вывод результатов
        comparator.print_results()
        path_to_result = "./tmp/Results"
        comparator.save_results(path_to_result)
        print(f"Результаты сохранены в файл: {path_to_result}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        # Доступ к результирующим датафреймам
        print("\n=== Доступ к результирующим датафреймам ===")
        print(f"df1_only shape: {comparator.df1_only.shape}")
        comparator.df1_only.to_excel(f"{path_to_result}/df1_only.xlsx", index=False )
        print(f"df2_only shape: {comparator.df2_only.shape}")
        comparator.df2_only.to_excel(f"{path_to_result}/df2_only.xlsx", index=False )
        if comparator.df1_df2_value is not None:
            print(f"df1_df2_value shape: {comparator.df1_df2_value.shape}")
            comparator.df1_df2_value.to_excel(f"{path_to_result}/comparator.df1_df2_value.xlsx", index=False )
    except ValueError as e:
        print(f"Ошибка: {e}")