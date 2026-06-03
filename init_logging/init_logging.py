import logging

def init_logging(level: int = logging.INFO, log_file:str = ''):
    '''
    Инициализирует логирование
    '''
    # DEWEC = DEBUG < INFO < WARNING < ERROR < CRITICAL
    if log_file:
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
                ]
    else:
        handlers=[
            logging.StreamHandler()
                ]
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

#   Функция Инициализирует логирование
def set_logging(level: int = logging.INFO, log_file: str = '', file_mode: str = 'a'):
    '''
    Инициализирует логирование.
    
    :param level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    :param log_file: Путь к файлу лога. Если указан, логи будут записываться в файл и консоль.
    :param file_mode: Режим открытия файла лога ('a' для дозаписи или 'w' для перезаписи). По умолчанию 'a'.
    '''
    # DEWEC = DEBUG < INFO < WARNING < ERROR < CRITICAL
    # Валидация file_mode для предотвращения ошибок
    if file_mode not in ['a', 'w']:
        raise ValueError("file_mode должен быть 'a' (дозапись) или 'w' (перезапись)")
    
    if log_file:
        handlers = [
            logging.FileHandler(log_file, mode=file_mode),  # Используем file_mode для режима открытия
            logging.StreamHandler()
        ]
    else:
        handlers = [
            logging.StreamHandler()
        ]
    # 
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
