import socket
import os
import subprocess
import threading
import sys
import select
import msvcrt
from get_ip import get_local_ip

# Задаём секретный код доступа
ACCESS_CODE = os.getenv('TELNET_ACCESS', '').strip()

# Константы Telnet
IAC  = b'\xff'
WILL = b'\xfb'
WONT = b'\xfc'
DO   = b'\xfd'
DONT = b'\xfe'
ECHO = b'\x01'

def handle_telnet_negotiation(conn, data):
    """Обрабатывает Telnet-команды от клиента"""
    i = 0
    while i < len(data):
        if data[i:i+1] == IAC:
            if i + 2 < len(data):
                cmd = data[i+1:i+2]
                opt = data[i+2:i+3]
                print(f"[Telnet] Получено: {cmd} {opt}")
                
                # Отвечаем на запросы клиента
                if cmd == DO and opt == ECHO:
                    # Клиент согласен, что мы будем отправлять эхо
                    pass
                elif cmd == DONT and opt == ECHO:
                    # Клиент отказывается
                    pass
                    
                i += 3
                continue
        i += 1
    
    # Возвращаем только "чистые" данные (без Telnet-команд)
    clean = bytearray()
    i = 0
    while i < len(data):
        if data[i:i+1] == IAC and i + 2 < len(data):
            i += 3
        else:
            clean.append(data[i])
            i += 1
    
    return bytes(clean)

def authenticate(conn):
    """Аутентификация клиента"""
    # Говорим клиенту: "Я буду отправлять эхо"
    conn.send(IAC + WILL + ECHO)
    
    # Даём время клиенту ответить
    conn.settimeout(0.5)
    try:
        resp = conn.recv(1024)
        if resp:
            handle_telnet_negotiation(conn, resp)
    except socket.timeout:
        pass
    conn.settimeout(None)
    
    # Отправляем приглашение
    conn.send(b"Access code: ")
    
    # Читаем пароль
    data = conn.recv(1024)
    if not data:
        return False
    
    # Очищаем от Telnet-команд
    clean_data = handle_telnet_negotiation(conn, data)
    
    # Декодируем данные с лучшей обработкой ошибок
    try:
        received = clean_data.decode('utf-8').rstrip('\r\n').strip()
    except UnicodeDecodeError as e:
        print(f"Ошибка декодирования: {e}")
        received = ""
    
    # Говорим клиенту: "Я больше не буду отправлять эхо"
    conn.send(IAC + WONT + ECHO)
    
    # Переводим строку
    conn.send(b"\r\n")

    # Сравнение паролей
    if received.lower() == ACCESS_CODE.strip().lower():
        conn.send(b"Access granted. Starting shell...\r\n\n")
        return True
    else:
        conn.send(b"Access denied.\r\n")
        return False

def handle_client_windows(conn):
    """Обработка клиента для Windows с использованием cmd.exe"""
    if not authenticate(conn):
        conn.close()
        return
    
    # Запускаем cmd.exe как подпроцесс
    try:
        # Используем cmd.exe вместо shell
        process = subprocess.Popen(
            ['cmd.exe'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=False,  # Работаем с байтами
            bufsize=0,   # Небуферизованный режим
            creationflags=subprocess.CREATE_NO_WINDOW  # Без окна консоли
        )
        
        def read_from_process():
            """Чтение вывода из процесса и отправка клиенту"""
            try:
                while True:
                    # Читаем из stdout
                    if process.stdout and not process.stdout.closed:
                        data = process.stdout.read(1)
                        if data:
                            conn.send(data)
                        else:
                            break
            except Exception as e:
                print(f"Ошибка чтения из процесса: {e}")
        
        def read_from_stderr():
            """Чтение ошибок из процесса и отправка клиенту"""
            try:
                while True:
                    if process.stderr and not process.stderr.closed:
                        data = process.stderr.read(1)
                        if data:
                            conn.send(data)
                        else:
                            break
            except Exception as e:
                print(f"Ошибка чтения stderr: {e}")
        
        def write_to_process():
            """Чтение данных от клиента и отправка в процесс"""
            try:
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # Очищаем от Telnet-команд
                    clean_data = handle_telnet_negotiation(conn, data)
                    
                    if clean_data and process.stdin and not process.stdin.closed:
                        try:
                            process.stdin.write(clean_data)
                            process.stdin.flush()
                        except:
                            break
            except Exception as e:
                print(f"Ошибка записи в процесс: {e}")
        
        # Запускаем потоки для асинхронной работы
        stdout_thread = threading.Thread(target=read_from_process, daemon=True)
        stderr_thread = threading.Thread(target=read_from_stderr, daemon=True)
        stdin_thread = threading.Thread(target=write_to_process, daemon=True)
        
        stdout_thread.start()
        stderr_thread.start()
        stdin_thread.start()
        
        # Ждем завершения процесса или отключения клиента
        while process.poll() is None and stdin_thread.is_alive():
            stdin_thread.join(0.1)
        
        # Завершаем процесс если он еще работает
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        
    except Exception as e:
        print(f"Ошибка при работе с клиентом: {e}")
        try:
            conn.send(f"\r\nОшибка сервера: {e}\r\n".encode('utf-8'))
        except:
            pass
    finally:
        conn.close()

def handle_client_powershell(conn):
    """Обработка клиента с использованием PowerShell (альтернативный вариант)"""
    if not authenticate(conn):
        conn.close()
        return
    
    try:
        # Запускаем PowerShell
        process = subprocess.Popen(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-Command', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            text=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        def forward_data():
            """Пересылка данных между клиентом и процессом"""
            try:
                while True:
                    # Используем select для неблокирующего чтения
                    readable, _, _ = select.select([conn, process.stdout], [], [], 0.1)
                    
                    # Данные от клиента
                    if conn in readable:
                        data = conn.recv(1024)
                        if not data:
                            break
                        
                        clean_data = handle_telnet_negotiation(conn, data)
                        if clean_data:
                            process.stdin.write(clean_data)
                            process.stdin.flush()
                    
                    # Данные от процесса
                    if process.stdout in readable:
                        data = process.stdout.read(1024)
                        if data:
                            conn.send(data)
                        else:
                            break
                    
                    # Проверяем завершение процесса
                    if process.poll() is not None:
                        break
                        
            except Exception as e:
                print(f"Ошибка пересылки данных: {e}")
        
        forward_data()
        
    except Exception as e:
        print(f"Ошибка при работе с клиентом: {e}")
    finally:
        # Завершаем процесс если он еще работает
        if process.poll() is None:
            process.terminate()
        conn.close()

def start_server(host='0.0.0.0', port=4022, shell_type='cmd'):
    """Запуск Telnet сервера"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Сервер запущен на {host}:{port}")
    print(f"Тип оболочки: {shell_type}")
    
    # Выбираем обработчик в зависимости от типа оболочки
    handler = handle_client_windows if shell_type == 'cmd' else handle_client_powershell
    
    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"Подключение от {addr}")
            
            # Обрабатываем каждого клиента в отдельном потоке
            client_thread = threading.Thread(
                target=handler,
                args=(conn,),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server_socket.close()

# def test_connection():
#     """Функция для тестирования сервера"""
#     import telnetlib
    
#     try:
#         tn = telnetlib.Telnet('localhost', 4022)
#         print("Тестовое подключение успешно")
#         tn.close()
#         return True
#     except Exception as e:
#         print(f"Ошибка тестового подключения: {e}")
#         return False

if __name__ == "__main__":
    telnet_port = 4022
    
    # Получаем IP адрес
    try:
        ip_adress = get_local_ip()
    except:
        ip_adress = '127.0.0.1'
    
    # Запрашиваем тип оболочки
    shell_type = input("Выберите тип оболочки (cmd/powershell) [по умолчанию cmd]: ").strip().lower()
    if shell_type not in ['cmd', 'powershell']:
        shell_type = 'cmd'
    
    print(f"Запуск сервера на {ip_adress}:{telnet_port}")
    start_server(host=ip_adress, port=telnet_port, shell_type=shell_type)