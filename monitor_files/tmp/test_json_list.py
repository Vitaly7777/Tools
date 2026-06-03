import os
import json
# Определяем путь к файлу конфигурации относительно текущей директории скрипта
CONFIG_JSON = os.path.join(os.path.dirname(__file__), 'config (копия).json')

# Функция загрузки конфигурации
def load_config(config_file=CONFIG_JSON):
    """
    Загружает конфигурацию из JSON-файла.

    :param config_file: Путь к файлу конфигурации (по умолчанию 'config.json' в той же директории, что и скрипт)
    :return: Словарь с конфигурацией
    """
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)
    

def main():
    config = load_config()
    print(config["source_file_paths"])

if __name__ == "__main__":
    main()
       
