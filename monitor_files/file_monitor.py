import os
import re
import json
import logging
from datetime import datetime
import fnmatch

# Определяем путь к файлу конфигурации относительно текущей директории скрипта
CONFIG_JSON = os.path.join(os.path.dirname(__file__), 'config.json')

# Функция загрузки конфигурации
def load_config(config_file=CONFIG_JSON):
    """
    Загружает конфигурацию из JSON-файла.

    :param config_file: Путь к файлу конфигурации (по умолчанию 'config.json' в той же директории, что и скрипт)
    :return: Словарь с конфигурацией
    """
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция сканирования каталога с игнорированием временных файлов
def scan_directory(logger, directory, ignore_dirs, ignore_patterns):
    state = []
    files_scanned = 0
    logger.info(f'Считывание текущего состояния каталога: {directory}')
    for root, dirs, files in os.walk(directory):
        skipped_dirs = []
        ignore_dirs_lower = [x.lower() for x in ignore_dirs]  # Подготавливаем список для быстрого сравнения

        filtered_dirs = []
        for d in dirs:
            if d.lower() in ignore_dirs_lower:
                skipped_dirs.append(d)  # Добавляем в список пропущенных
                full_path = os.path.join(root, d)  # Полный путь для логирования
                logger.debug(f"Пропущен каталог: {full_path} (причина: совпадает с {d} в ignore_dirs, регистронезависимо)")
            else:
                filtered_dirs.append(d)  # Добавляем в отфильтрованный список

        dirs[:] = filtered_dirs  # Применяем фильтр к dirs
        for file in files:
            full_path = os.path.join(root, file)
            # Игнорировать временные файлы
            if is_temp_file(file, ignore_patterns):
                logger.debug(f"Пропущен временный файл: {full_path}")
                continue
            try:
                modified_date = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')
                state.append({"path": full_path, "modified_date": modified_date})
                files_scanned += 1
                if files_scanned  % 10000 == 0:
                    logger.info(f'Считано {files_scanned} файлов.')
            except Exception as e:
                logger.error(f"Error scanning file {full_path}: {e}")
    logger.info(f'Всего считано {files_scanned} файлов в каталоге: {directory}.')
    return state

# функция для определения временных файлов
def is_temp_file(path, patterns):
    file_name = os.path.basename(path)  # Получаем базовое имя файла
    for pattern in patterns:
        if fnmatch.fnmatch(file_name, pattern):  # Проверяем соответствие шаблону
            return True
    return False  # Не совпало ни с одним шаблоном

# Функция сравнения состояний
def compare_states(logger, prev_state, current_state):
    # Преобразуем списки состояний в словари для быстрого доступа по пути файла
    # Ключ: путь файла, Значение: модифицированная_дата
    prev_state_map = {item['path']: item['modified_date'] for item in prev_state}
    current_state_map = {item['path']: item['modified_date'] for item in current_state}

    # Множества путей для эффективного определения добавленных и удаленных
    prev_paths_set = set(prev_state_map.keys())
    current_paths_set = set(current_state_map.keys())

    added = []
    removed = []
    changed = []

    logger.info("Проверка новых файлов:")
    new_paths = current_paths_set - prev_paths_set
    for path in new_paths:
        added.append({"path": path, "modified_date": current_state_map[path]})
    logger.info(f"Найдено {len(added)} новых файлов.")

    logger.info("Проверка удаленных файлов:")
    removed_paths = prev_paths_set - current_paths_set
    for path in removed_paths:
        removed.append(path) # Для удаленных файлов достаточно сохранить путь
    logger.info(f"Найдено {len(removed)} удаленных файлов.")

    logger.info("Проверка измененных файлов:")
    common_paths = prev_paths_set.intersection(current_paths_set)
    for indx, path in enumerate(common_paths, start=1):
        if prev_state_map[path] != current_state_map[path]:
            changed.append({"path": path, "old_modified_date": prev_state_map[path], "new_modified_date": current_state_map[path]})
        if indx % 10000 == 0:
            logger.info(f'Проверено на изменение {indx} файлов.')
    logger.info(f"Найдено {len(changed)} измененных файлов.")

    return added, removed, changed

# Функция сохранения состояния
def save_state(state, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False,  indent=4)

def add_suffix_to_filename_os(file_path, suffix):
    '''Функция добавляет суффикс к имени файла'''
    directory, file_name = os.path.split(file_path)
    name_without_ext, extension = os.path.splitext(file_name)
    new_file_name = f'{name_without_ext}_{suffix}{extension}'
    new_full_path = os.path.join(directory, new_file_name)
    return new_full_path

def rotate_file(path:str, rotate_number:int =10, logger = None):
    # Проверяем, существует ли файл path
    if os.path.exists(path):
        try:
            # Выполняем ротацию: переименовываем файлы от _(N-1) до _N
            for i in range(rotate_number, 1, -1):  # От rotate_number до 2
                old_name = add_suffix_to_filename_os(path, f'{i-1:02d}')
                new_name = add_suffix_to_filename_os(path, f'{i:02d}')
                if os.path.exists(old_name):
                    if os.path.exists(new_name):
                        os.remove(new_name)
                    os.rename(old_name, new_name)
            
            # Теперь переименовываем текущий файл (без суффикса) в _01
            new_name_for_original = add_suffix_to_filename_os(path, '01') # Исправлено на '01'
            if os.path.exists(new_name_for_original):
                os.remove(new_name_for_original)
            
            # Чтобы не переименовывать "файл в сам себя", сначала копируем его в _01, а потом очищаем основной
            # Или, чтобы сохранить историю, просто переименовываем
            # Если rotate_number был 0, то этот блок не выполнится, т.к. range(0,1,-1) пуст.
            # Но если rotare_number > 0, то текущий файл должен стать "первой" ротацией (file_01.ext)
            
            # Переименовываем основной файл, чтобы он стал _01
            if os.path.exists(path): # Проверяем, что основной файл существует перед переименованием
                os.rename(path, new_name_for_original)
            
            if logger:
                logger.info(f'Проведена ротация файлов {path}.')
            return
        except Exception as e:
            if logger:
                logger.error(f'Ошибка ротации файлов {path}: {e}')
            else:
                print(f'Ошибка ротации файлов {path}: {e}')
            raise e
    else:
        if logger:
            logger.debug(f"Файл для ротации не существует: {path}") # Изменено на debug, т.к. это не ошибка

def ensure_directory_exist(directory, logger=None):
    """
    Создает каталоги, указанные в конфигурации, если они не существуют.
    
    :param directory: путь к каталогу
    :param logger: настроенный логгер (если нужен)
    """
    if directory:
        fullpath = os.path.abspath(directory)
        
        if not os.path.exists(fullpath):
            os.makedirs(fullpath)
            message = f"Создан каталог: {fullpath}"
            if logger:
                logger.info(message)
            else:
                print(message)

#   Функция Инициализирует логирование
def set_logging(log_file: str = '', stream_on: bool = True, level: int = logging.INFO, file_mode: str = 'a'):
    '''
    Инициализирует логирование.
    
    :param level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    :param log_file: Путь к файлу лога. Если указан, логи будут записываться в файл и консоль.
    :param file_mode: Режим открытия файла лога ('a' для дозаписи или 'w' для перезаписи). По умолчанию 'a'.
    '''
    if file_mode not in ['a', 'w']:
        raise ValueError("file_mode должен быть 'a' (дозапись) или 'w' (перезапись)")
    
    handlers_list = []
    if log_file:
        handlers_list.append(logging.FileHandler(log_file, mode=file_mode, encoding='utf-8'))
    if stream_on:
        handlers_list.append(logging.StreamHandler())
    
    # Если лог-файл не указан и stream_on=False, логирование может быть отключено.
    # Но обычно stream_on по умолчанию True или должен быть хотя бы один хендлер.
    if not handlers_list:
        handlers_list.append(logging.NullHandler()) # Чтобы избежать ошибки, если хендлер не определен

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers_list
    )

def main():
    level_log = logging.DEBUG
    config = load_config()

    rotare_state_files = config.get('rotare_state_files', 0)
    rotare_remove_files = config.get('rotare_remove_files', 0)
    rotare_log_files = config.get('rotare_log_files', 0)
    
    # Новые параметры
    changed_files_file_base = config.get('changed_files_file', '')
    rotare_change_files = config.get('rotare_change_files', 0) # По умолчанию 0, если не указано

    stream_on = bool(config.get('stream_on', True)) # Конвертируем в булево значение

    if not stream_on:
        print('Выполняется сканирование.')
    
    str_ignore_dirs = config.get('ignore_dirs', "''")
    ignore_dirs = re.findall(r"'([^']*)'", str_ignore_dirs)
    str_ignore_patterns = config.get('ignore_patterns', "''")
    ignore_patterns = re.findall(r"'([^']*)'", str_ignore_patterns)
    str_monitor_directory = config.get('monitor_directory', "''")
    list_monitor_directory = re.findall(r"'([^']*)'", str_monitor_directory)

    # Проверка и создание каталога логов
    log_file_path_base = config.get('log_file', '')
    if log_file_path_base:
        directory = os.path.dirname(log_file_path_base)
        ensure_directory_exist(directory)

    # Ротация и настройка основного лога
    if rotare_log_files > 0 and log_file_path_base:
        rotate_file(log_file_path_base, rotare_log_files)
    set_logging(log_file_path_base, stream_on, level_log)
    logger = logging.getLogger(__name__)

    # Проверка и создание каталога состояний
    state_file_path_base = config.get('state_file', '')
    if state_file_path_base:
        directory = os.path.dirname(state_file_path_base)
        ensure_directory_exist(directory, logger)
    else:
        logger.warning("Параметр 'state_file' не указан в конфигурации. Состояния файлов не будут сохраняться.")

    # Проверка и создание каталога удаленных файлов
    removed_files_file_path_base = config.get('removed_files_file', '')
    if removed_files_file_path_base:
        directory = os.path.dirname(removed_files_file_path_base)
        ensure_directory_exist(directory, logger)
    else:
        logger.warning("Параметр 'removed_files_file' не указан в конфигурации. Список удаленных файлов не будет сохраняться.")

    # Проверка и создание каталога измененных файлов
    if changed_files_file_base and changed_files_file_base != '':
        directory = os.path.dirname(changed_files_file_base)
        ensure_directory_exist(directory, logger)
    elif changed_files_file_base == '':
        logger.info("Параметр 'changed_files_file' не указан или пуст. Список измененных файлов не будет сохраняться.")

    # Перебор каталогов сканирования
    for monitor_directory in list_monitor_directory:
        # Нормализуем путь и извлекаем суффикс для специфичных файлов
        normalized_dir = os.path.normpath(monitor_directory)
        suffix = os.path.basename(normalized_dir)
        if not suffix: # Если корень диска или что-то подобное, где basename пуст
            suffix = 'root'
        suffix = re.sub(r'[\W_]', '_', suffix) # Очищаем суффикс от недопустимых символов

        current_state_file = add_suffix_to_filename_os(state_file_path_base, suffix) if state_file_path_base else ""
        current_removed_files_file = add_suffix_to_filename_os(removed_files_file_path_base, suffix) if removed_files_file_path_base else ""
        
        # Для changed_files_file
        current_changed_files_file = ""
        if changed_files_file_base and changed_files_file_base != '':
            current_changed_files_file = add_suffix_to_filename_os(changed_files_file_base, suffix)


        logger.info(f"Старт проверки каталога {monitor_directory}")

        try:
            current_state_data = scan_directory(logger, monitor_directory, ignore_dirs, ignore_patterns)
            
            if os.path.exists(current_state_file):
                with open(current_state_file, 'r', encoding='utf-8') as f:
                    prev_state_data = json.load(f)
                added, removed, changed = compare_states(logger, prev_state_data, current_state_data)
                
                logger.info(f"Новых файлов: {len(added)}")
                logger.info(f"Удаленных файлов: {len(removed)}")
                logger.info(f"Измененных файлов: {len(changed)}")

                # Сохранение удаленных файлов
                if current_removed_files_file and removed:
                    if rotare_remove_files > 0:
                        rotate_file(current_removed_files_file, rotare_remove_files, logger=logger)
                    with open(current_removed_files_file, 'w', encoding='utf-8') as f:
                        for file_path in removed:
                            f.write(file_path + '\n')
                    logger.info(f"Список удаленных файлов сохранен в файл {current_removed_files_file}.")
                elif current_removed_files_file:
                    logger.info("Удаленных файлов не обнаружено.")

                # Сохранение измененных файлов
                if current_changed_files_file and changed:
                    if rotare_change_files > 0:
                        rotate_file(current_changed_files_file, rotare_change_files, logger=logger)
                    with open(current_changed_files_file, 'w', encoding='utf-8') as f:
                        for item in changed:
                            f.write(f"{item['path']} (Старая дата: {item['old_modified_date']}, Новая дата: {item['new_modified_date']})\n")
                    logger.info(f"Список измененных файлов сохранен в файл {current_changed_files_file}.")
                elif current_changed_files_file:
                    logger.info("Измененных файлов не обнаружено.")

            else:
                logger.info(f"Файл предыдущего состояния не найден для {monitor_directory}. Текущее состояние будет сохранено как первое.")
            
            # Сохранение текущего состояния
            if current_state_file:
                if rotare_state_files > 0:
                    rotate_file(current_state_file, rotare_state_files, logger=logger)
                save_state(current_state_data, current_state_file)
                logger.info(f"Текущее состояние сохранено в файл {current_state_file}.")

        except Exception as e:
            logger.error(f"Program error during monitoring {monitor_directory}: {e}", exc_info=True)
        
        logger.info(f"Окончание выполнения проверки каталога {monitor_directory}")
        
    if not stream_on:
        print('Cканирование выполнено (см. логи).')

if __name__ == "__main__":
    main()
