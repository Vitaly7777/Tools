import socket

def get_local_ip():
    try:
        # Создаём сокет и подключаемся к случайному внешнему адресу
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('portal.rt.ru', 443))  # Используем портал как тестовый адрес
        local_ip = s.getsockname()[0]  # Получаем локальный IP
    except socket.error:
        local_ip = '127.0.0.1'  # Если ошибка, возвращаем localhost
    finally:
        s.close()
    return local_ip

# Вызов функции
if __name__ == "__main__":
    print("Ваш локальный IP-адрес:", get_local_ip())
