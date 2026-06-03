
"""
Скрипт для обрезки xlsb, xlsx, xlsm и ods файлов до указанного(ROWS_TO_KEEP = 50) количества строк на каждом листе.
Если rows_to_keep = 0 (или не является целым), то файлы не обрезаются и 
сохраняются значения без формул и форматирования в формате *.xlsx
Использование:
1. Скопировать папку с данными(таблицами) в рабочую директорию forwork_dir (./data)
2. Запустить: python cut_files.py
3. Скрипт создаст папку forwork_dir с суффиксом _cut с обрезанными файлами
4. Все файлы сохраняются как *.xlsx, даже если исходный формат был *.xlsb, или *.xlsm, или *.ods
"""

import sys
from pathlib import Path
import pandas as pd
import ezodf
import time

# Конфигурация
WORK_DIR = Path(__file__).resolve().parent
ROWS_TO_KEEP = 50
# Сканируем только папку data
forwork_dir = WORK_DIR / 'data'


def print_progress(current, total, message):
    """Вывод прогресса в формате: [номер/всего] сообщение"""
    print(f'[{current}/{total}] {message}')

def process_files(forwork_dir:str = forwork_dir, rows_to_keep = ROWS_TO_KEEP):
    """Основная функция обработки файлов"""
    print('=' * 60)
    print('Скрипт обрезки xlsb/xlsx/xlsm файлов до 50 строк (все листы)')
    print('=' * 60)
    print(f'Рабочая директория: {WORK_DIR}')
    print(f'Количество строк для сохранения: {rows_to_keep}')
    print()

    if not forwork_dir.is_dir():
        print(f'Папка {forwork_dir} не найдена')
        return

    print(f'Папка для обработки: {forwork_dir}')
    print()

    # Создать папку _cut в родительской директории
    output_folder = forwork_dir.parent / (forwork_dir.name + '_cut')
    output_folder.mkdir(exist_ok=True)
    print(f'  Создана папка: {output_folder.name}')

    # Собрать xlsb, xlsx и xlsm файлы из каталога forwork_dir и его подпапок
    all_files = []
    # Счётчики
    xlsb_count = 0
    xlsx_count = 0
    xlsm_count = 0
    ods_count = 0

    for ext, count_var in [('*.xlsb', 'xlsb'), ('*.xlsx', 'xlsx'), ('*.xlsm', 'xlsm'), ('*.ods', 'ods')]:
        for file in forwork_dir.rglob(ext):
            if not file.name.startswith('.'):
                all_files.append(file)
                if count_var == 'xlsb':
                    xlsb_count += 1
                elif count_var == 'xlsx':
                    xlsx_count += 1
                elif count_var == 'xlsm':
                    xlsm_count += 1
                else:
                    ods_count += 1

    if not all_files:
        print(f'  Нет xlsb/xlsx/xlsm файлов в папке')
        print()
        return

    print(f'  Найдено файлов: {len(all_files)} (xlsb: {xlsb_count}, xlsx: {xlsx_count}, xlsm: {xlsm_count})')
    print()

    total_files_count = len(all_files)

    # Обработать каждый файл
    for idx, filepath in enumerate(all_files, start=1):
        # total_files += 1
        print_progress(idx, total_files_count, f'{filepath.name} (чтение всех листов)')
        try:
            # Выбираем engine в зависимости от расширения
            if filepath.suffix == '.ods':
                sheets = read_all_ods_sheets(filepath)
            else:
                if filepath.suffix == '.xlsb':
                    engine = 'calamine'
                else:  # .xlsx или .xlsm
                    engine = 'openpyxl'
                # Читаем все листы файла (как словарь {имя_листа: DataFrame})
                sheets = pd.read_excel(filepath, sheet_name=None, engine=engine, header=None, dtype=object)

            # Обрезаем каждый лист до rows_to_keep строк если rows_to_keep целое число больше 0 иначе оставляем как есть
            if isinstance(rows_to_keep, int):
                if rows_to_keep:
                    cut_sheets = {}
                    for sheet_name, df in sheets.items():
                        cut_sheets[sheet_name] = df.iloc[:rows_to_keep].copy()
                else:
                    cut_sheets = sheets
            else:
                cut_sheets = sheets

            # Рассчитываем относительный путь и создаем структуру папок
            relative_path = filepath.relative_to(forwork_dir)  # Получаем относительный путь, напр. 'АБС/ВАС/file.xlsb'
            new_relative_path = relative_path.with_suffix('.xlsx')  # Изменяем расширение на .xlsx, сохраняя подпапки

            output_path = output_folder / new_relative_path  # Полный путь, напр. output_folder/АБС/ВАС/file.xlsx
            
            # Создаем необходимые папки, если они не существуют
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Сохраняем как xlsx (все листы в один файл)
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for sheet_name, df_cut in cut_sheets.items():
                    # Если имя листа слишком длинное, openpyxl может ругаться, обрежем до 31 символа
                    safe_sheet_name = sheet_name[:31] if len(sheet_name) > 31 else sheet_name
                    df_cut.to_excel(writer, sheet_name=safe_sheet_name, header=False, index=False)

            print(f'      → Сохранено {len(cut_sheets)} листов в {output_path.name}')

        except Exception as e:
            print(f'      ОШИБКА: {e}')
            continue

    print('=' * 60)
    print(f'Готово!')
    print(f'Обработано файлов: {idx}')
    print('=' * 60)

def read_all_ods_sheets(filepath):
    """
    Читает все листы из файла .ods и возвращает словарь DataFrames.

    Args:
        filepath (str): Путь к файлу .ods.

    Returns:
        dict: Словарь, где ключи — имена листов, а значения —
              соответствующие pandas DataFrames.
    """
    all_sheets = {}
    # 1. Используем ezodf для открытия документа и получения имен листов
    try:
        doc = ezodf.opendoc(filepath)
        sheet_names = [sheet.name for sheet in doc.sheets if len(sheet.name)<32]


    except Exception as e:
        print(f"Ошибка при открытии файла {filepath} для получения списка листов: {e}")
        return {}
    finally:

        pass

    # 2. Загружаем каждый лист в отдельный DataFrame с помощью pandas_ods_reader
    
    for sheet_name in sheet_names:
        try:
            df = pd.read_excel(filepath, sheet_name=sheet_name, engine='calamine', header=None, dtype=object)
            all_sheets[sheet_name] = df
            # print(f"Лист '{sheet_name}' успешно загружен. Размер: {df.shape}")
        except Exception as e:
            print(f"Ошибка при загрузке листа '{sheet_name}': {e}")
            # Продолжаем загрузку остальных листов
            continue

    return all_sheets

if __name__ == '__main__':
    try:
        start_time = time.perf_counter()
        process_files(forwork_dir = forwork_dir, rows_to_keep = ROWS_TO_KEEP)
        elapsed_time = time.perf_counter() - start_time 
        print((f"Вычисление заняло {elapsed_time:0.5f} секунд"))
    except KeyboardInterrupt:
        print()
        print('Прервано пользователем')
        sys.exit(1)
    except Exception as e:
        print()
        print(f'Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
