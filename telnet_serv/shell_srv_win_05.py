import socket
import os
import subprocess
import threading
import sys
import select
import time
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
SUPPRESS_GO_AHEAD = b'\x03'
TERMINAL_TYPE = b'\x18'
WINDOW_SIZE = b'\x1f'

def handle_telnet_negotiation(conn, data):
    """Обрабатывает Telnet-команды от клиента"""
    i = 0
    while i < len(data):
        if data[i:i+1] == IAC:
            if i + 2 < len(data):
                cmd = data[i+1:i+2]
                opt = data[i+2:i+3]
                
                # Отвечаем на запросы клиента
                if cmd == DO:
                    # Клиент хочет, чтобы мы что-то делали
                    if opt in [ECHO, SUPPRESS_GO_AHEAD]:
                        conn.send(IAC + WILL + opt)  # Соглашаемся
                    else:
                        conn.send(IAC + WONT + opt)  # Отказываемся
                elif cmd == WILL:
                    # Клиент хочет что-то делать
                    if opt in [TERMINAL_TYPE, WINDOW_SIZE]:
                        conn.send(IAC + DO + opt)  # Соглашаемся
                    else:
                        conn.send(IAC + DONT + opt)  # Отказываемся
                    
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
    
    # Отправляем начальные настройки Telnet
    conn.send(IAC + WILL + ECHO)
    conn.send(IAC + WILL + SUPPRESS_GO_AHEAD)
    
    # Даём время клиенту ответить
    time.sleep(0.3)
    
    # Читаем и обрабатываем ответы клиента
    conn.setblocking(False)
    try:
        for _ in range(5):
            ready = select.select([conn], [], [], 0.2)
            if ready[0]:
                data = conn.recv(4096)
                if data and IAC in data:
                    handle_telnet_negotiation(conn, data)
                else:
                    break
            else:
                break
    except:
        pass
    conn.setblocking(True)
    
    # Отправляем приглашение для ввода пароля
    conn.send(b"\r\nAccess code: ")
    
    # Получаем пароль посимвольно
    password = ""
    
    while True:
        try:
            char = conn.recv(1)
            if not char:
                return False
            
            # Проверяем на Telnet-команды
            if char == IAC:
                # Читаем следующие 2 байта команды
                cmd = conn.recv(2)
                if len(cmd) == 2:
                    handle_telnet_negotiation(conn, char + cmd)
                continue
            
            # Если получили символ
            try:
                decoded_char = char.decode('utf-8', errors='ignore')
            except:
                continue
            
            # Проверяем на Enter
            if decoded_char in ['\r', '\n']:
                conn.send(b"\r\n")
                break
            
            # Проверяем на Backspace
            if decoded_char in ['\b', '\x7f']:
                if password:
                    password = password[:-1]
                    conn.send(b'\b \b')
                continue
            
            # Добавляем символ к паролю
            if decoded_char.isprintable():
                password += decoded_char
                conn.send(b'*')
            
        except Exception as e:
            print(f"Ошибка при чтении пароля: {e}")
            return False
    
    # Проверяем пароль
    if password.strip().lower() == ACCESS_CODE.strip().lower():
        conn.send(b"\r\nAccess granted. Starting shell...\r\n\r\n")
        return True
    else:
        conn.send(b"\r\nAccess denied.\r\n")
        return False

def handle_client_windows(conn):
    """Исправленная обработка клиента для Windows"""
    
    if not authenticate(conn):
        conn.close()
        return
    
    try:
        # Запускаем cmd.exe
        process = subprocess.Popen(
            'cmd.exe',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Флаг для остановки потоков
        running = True
        
        def read_from_process():
            """Чтение вывода процесса и отправка клиенту"""
            nonlocal running
            try:
                while running:
                    # Читаем один байт за раз для немедленного отображения
                    char = process.stdout.read(1)
                    if not char:
                        break
                    
                    # Отправляем байт клиенту
                    try:
                        conn.send(char)
                    except:
                        break
                        
            except Exception as e:
                if running:
                    print(f"Ошибка чтения из процесса: {e}")
        
        def write_to_process():
            """Чтение ввода клиента и отправка процессу"""
            nonlocal running
            try:
                while running:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # Очищаем от Telnet-команд
                    clean_data = handle_telnet_negotiation(conn, data)
                    
                    if clean_data:
                        try:
                            process.stdin.write(clean_data)
                            process.stdin.flush()
                        except:
                            break
                            
            except Exception as e:
                if running:
                    print(f"Ошибка записи в процесс: {e}")
        
        # Запускаем потоки
        read_thread = threading.Thread(target=read_from_process, daemon=True)
        write_thread = threading.Thread(target=write_to_process, daemon=True)
        
        read_thread.start()
        write_thread.start()
        
        # Ждем завершения потоков
        read_thread.join()
        write_thread.join()
        
        running = False
        
    except Exception as e:
        print(f"Ошибка при работе с клиентом: {e}")
    finally:
        # Останавливаем процесс
        try:
            if 'process' in locals():
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)
        except:
            pass
        
        # Закрываем соединение
        try:
            conn.close()
        except:
            pass

def start_server(host='0.0.0.0', port=4022):
    """Запуск Telnet сервера"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    
    print(f"Telnet сервер запущен на {host}:{port}")
    print(f"Код доступа: {ACCESS_CODE}")
    print("Для подключения используйте: telnet {} {}".format(host, port))

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"\nНовое подключение от {addr}")
            
            # Настройка клиентского соединения
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Запускаем обработку клиента в отдельном потоке
            client_thread = threading.Thread(
                target=handle_client_windows,
                args=(conn,),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nСервер остановлен пользователем")
    except Exception as e:
        print(f"Ошибка сервера: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    # Устанавливаем код доступа
    if not ACCESS_CODE:
        ACCESS_CODE = "1234"
        print(f"Используется пароль по умолчанию: {ACCESS_CODE}")
    
    telnet_port = 4022
    
    # Получаем IP адрес
    try:
        ip_address = get_local_ip()
    except:
        ip_address = '127.0.0.1'
    
    start_server(host=ip_address, port=telnet_port)