import random

class RossignolCipher:
    def __init__(self):
        # Словарь: слово/слог -> код (число)
        self.word_to_code = {}
        # Обратный словарь: код -> слово/слог
        self.code_to_word = {}
        # Пустышки (обманные числа, не имеющие смысла)
        self.dummy_codes = set()

    def build_dictionary(self, word_list, dummy_count=20):
        """
        word_list: список слов/слогов для кодирования (например, ['король', 'армия', 'немедленно'])
        dummy_count: сколько добавить пустышек
        """
        # Генерируем уникальные коды для слов
        used_codes = set()
        for word in word_list:
            while True:
                code = random.randint(1000, 9999)  # 4-значные коды
                if code not in used_codes:
                    used_codes.add(code)
                    break
            self.word_to_code[word] = code
            self.code_to_word[code] = word

        # Добавляем пустышки
        while len(self.dummy_codes) < dummy_count:
            code = random.randint(1000, 9999)
            if code not in self.code_to_word and code not in self.dummy_codes:
                self.dummy_codes.add(code)

    def encrypt(self, text):
        """
        text: строка для шифрования
        Возвращает список кодов (чисел)
        """
        # Токенизация: разбиваем на слова по пробелам и базовым знакам препинания
        import re
        tokens = re.findall(r"[А-Яа-яЁё]+|[^\w\s]", text, flags=re.UNICODE)

        encrypted = []
        for token in tokens:
            token_lower = token.lower()
            if token_lower in self.word_to_code:
                # Кодируем известное слово
                encrypted.append(self.word_to_code[token_lower])
            elif token in {'.', ',', '!', '?', ';', ':', '-'}:
                # Знаки препинания можно оставить как есть или закодировать отдельно
                # Здесь просто добавляем их «как есть» в виде строки
                encrypted.append(token)
            else:
                # Если слово не в словаре — можно либо пропустить, либо выдать ошибку
                # Для демонстрации заменим на случайную пустышку
                dummy = random.choice(list(self.dummy_codes))
                encrypted.append(dummy)
        return encrypted

    def decrypt(self, codes):
        """
        codes: список кодов (чисел) и знаков препинания
        Возвращает расшифрованный текст
        """
        decrypted_tokens = []
        for item in codes:
            if isinstance(item, int):
                if item in self.code_to_word:
                    decrypted_tokens.append(self.code_to_word[item])
                elif item in self.dummy_codes:
                    # Пустышка: ничего не добавляем или ставим [?]
                    decrypted_tokens.append("[?]")
                else:
                    # Неизвестный код: помечаем
                    decrypted_tokens.append(f"[{item}]")
            else:
                # Знаки препинания
                decrypted_tokens.append(item)

        # Простая сборка: между словами пробел, но аккуратно с пунктуацией
        result = ""
        for i, tok in enumerate(decrypted_tokens):
            if tok in {'.', ',', '!', '?', ';', ':'}:
                result += tok
            else:
                if result and not result.endswith(" "):
                    result += " "
                result += tok
        return result.strip()


# Пример использования
if __name__ == "__main__":
    cipher = RossignolCipher()

    # Словарь типичных «смысловых блоков» (слоги/слова/понятия)
    dictionary_words = [
        "король", "армия", "немедленно", "секретно", "враг",
        "план", "город", "мост", "переправа", "атака", "приказал", "и", "начать", "атака", "у" , "на"
    ]

    cipher.build_dictionary(dictionary_words, dummy_count=20)

    message = "Король немедленно приказал армия и начать атака у на город."
    encrypted = cipher.encrypt(message)
    print("Зашифровано:", encrypted)

    decrypted = cipher.decrypt(encrypted)
    print("Расшифровано:", decrypted)
