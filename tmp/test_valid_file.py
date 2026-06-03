from pathlib import Path

filename= '/mnt/dfs/РУЗ/РУЗ_2/РУЗ_2_ЦК/Проверка ПУ_РУЗ2/ТЗ_Проверка ПУ_САП/Затраты/.~lock.Выгрузка по затратам 11_2.xlsb#'
# filename= 'agsfdhfd.ret'
script_path =Path(filename)
print(script_path.name)
# print(type(script_path.name))

def is_valid_file(filename: str) -> bool:
    """
    Проверяет, является ли файл валидным (не начинается с '.' или '~').
    
    Args:
        filename (str): Имя файла.
    
    Returns:
        bool: True, если файл валидный.
    """
    script_path =Path(filename)
    return not script_path.name.startswith(('.', '~'))

print(is_valid_file(filename))
