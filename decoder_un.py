import re
import pandas as pd

CONFINES = 0.7  # Порог для распознавания русского текста
EN_LETTER = re.compile(r'[a-z/<>\n\t]', flags=re.IGNORECASE)  # английские буквы
RUS_DIGITS = re.compile(r'[а-яё0-9/., -]', flags=re.IGNORECASE)  # русские буквы и цифры
NOT_PATTERN = re.compile(r'[^а-яё]', flags=re.IGNORECASE)  # кроме русских букв
BYTE_PATTERN = re.compile(r'[a-wyzG-Z .,/<>-]')  # английские буквы, которых нет в байт-строке


def decode_unknown(text):
    """
    Функция перекодировки из кразозябр в читаемый русский текст
    :param text: текст
    :return: перекодированный текст
    """
    # Если в строке более порога русских букв и цифр - то текст уже годный к использованию
    if len(RUS_DIGITS.findall(text)) > len(text) * CONFINES:
        return text

    # Список кодировок для перебора
    encodings = ['UTF-8', 'KOI8-R', 'CP866', 'WINDOWS-1251', 'WINDOWS-1252', ]
    for encoding in encodings:
        try:
            if any(0 <= ord(c) < 255 for c in BYTE_PATTERN.sub('', text)):
                # Если есть хоть один символ от байт-кодов -->
                # Восстанавливаем байт-строку двойной перекодировкой
                text_ = text.encode('latin1').decode('unicode_escape')
                decoded = text_.encode('latin1').decode(encoding)
            else:
                # Обычную строку с кракозабрами пытаемся закодировать и раскодировать в UTF-8
                decoded = text.encode(encoding, errors='ignore').decode('UTF-8')

            # В некоторых кодировках преобладают буквы п, я - уберем их
            temp = EN_LETTER.sub('', decoded).replace('п', '').replace('я', '')
            #  Если в строке русских букв и цифр больше порога - текст годный к использованию
            if len(RUS_DIGITS.findall(temp)) > len(temp) * CONFINES:
                return decoded
        except:
            pass
    # Не смогли распознать кракозябры --> возвращаем как есть и удалим их потом
    return text

def read_file(path, mode:str = 'r', encoding:str = 'utf-8'):
    try:
        with open(file=path, mode=mode, encoding=encoding) as file:
            # Читаем весь файл за раз
            content = file.read()
            return content
    except Exception as e:
        raise e
if __name__ == '__main__':
    path_file = '/home/PR.RT.RU/v.karitsky/work_tmp/tmp/ferst_10.csv'
    try:
        # Открываем файл в режиме чтения с указанием кодировки (чтобы избежать проблем с символами)
        content = read_file(path_file, 'r', 'cp1251')
        # content = read_file(path_file, 'r')
        print("Содержимое файла:")
        print(content)
        # Для демонстрации: Подсчитываем строки
        lines = content.splitlines()  # Разделяем на строки
        print(f"Всего строк: {len(lines)}")

    except FileNotFoundError:
        print(f"Ошибка: Файл '{path_file}' не найден. Проверьте путь.")
    except UnicodeDecodeError:
        print(f"Ошибка: Не удалось прочитать файл из-за кодировки. Попробуйте encoding='cp1251'.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    # df = pd.read_csv(path_file)
    # print(df)

