import socket
import os
import subprocess
import threading
import sys
import select
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
                if cmd == DO:
                    # Клиент хочет, чтобы мы что-то делали - отказываем
                    conn.send(IAC + WONT + opt)
                elif cmd == WILL:
                    # Клиент хочет что-то делать - отказываем
                    conn.send(IAC + DONT + opt)
                    
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
    """Аутентификация клиента для Windows Telnet"""
    
    # Отправляем начальные настройки Telnet
    # Говорим, что будем эхоировать
    conn.send(IAC + WILL + ECHO)
    # Говорим, что не будем использовать go-ahead
    conn.send(IAC + WILL + SUPPRESS_GO_AHEAD)
    
    # Даём время клиенту ответить и обрабатываем его команды
    conn.settimeout(1.0)
    try:
        while True:
            try:
                resp = conn.recv(1024)
                if resp:
                    # Проверяем, есть ли в ответе Telnet-команды
                    if IAC in resp:
                        handle_telnet_negotiation(conn, resp)
                    else:
                        # Если нет Telnet-команд, выходим из цикла
                        break
                else:
                    break
            except socket.timeout:
                break
    except Exception as e:
        print(f"Ошибка при начальной настройке: {e}")
    conn.settimeout(None)
    
    # Отправляем приглашение для ввода пароля
    conn.send(b"\r\nAccess code: ")
    
    # Получаем пароль посимвольно
    password = ""
    conn.settimeout(30)  # Таймаут 30 секунд на ввод пароля
    
    try:
        while True:
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
            
            # Проверяем на Enter (Windows Telnet отправляет \r\n или \r\0)
            if decoded_char in ['\r', '\n']:
                conn.send(b"\r\n")
                break
            
            # Проверяем на Backspace
            if decoded_char in ['\b', '\x7f']:
                if password:
                    password = password[:-1]
                    # Отправляем backspace для стирания символа в клиенте
                    conn.send(b'\b \b')
                continue
            
            # Добавляем символ к паролю и отправляем эхо (*)
            if decoded_char.isprintable():
                password += decoded_char
                # Отправляем эхо (звездочку)
                conn.send(b'*')
            
    except socket.timeout:
        print("Таймаут при вводе пароля")
        return False
    finally:
        conn.settimeout(None)
    
    print(f"Получен пароль: {password}")
    print(f"Ожидаемый пароль: {ACCESS_CODE}")
    
    # Сравниваем пароли
    if password.strip().lower() == ACCESS_CODE.strip().lower():
        conn.send(b"\r\nAccess granted. Starting shell...\r\n\r\n")
        return True
    else:
        conn.send(b"\r\nAccess denied.\r\n")
        return False

def handle_client_windows(conn):
    """Обработка клиента для Windows с использованием cmd.exe"""
    if not authenticate(conn):
        conn.close()
        return
    
    # Запускаем cmd.exe как подпроцесс
    try:
        process = subprocess.Popen(
            'cmd.exe',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=False,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        def read_from_process():
            """Чтение вывода из процесса и отправка клиенту"""
            try:
                while True:
                    # Читаем из stdout
                    char = process.stdout.read(1)
                    if char:
                        conn.send(char)
                    else:
                        break
            except Exception as e:
                if "Broken pipe" not in str(e):
                    print(f"Ошибка чтения из процесса: {e}")
        
        def write_to_process():
            """Чтение данных от клиента и отправка в процесс"""
            try:
                while True:
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
                if "Broken pipe" not in str(e):
                    print(f"Ошибка записи в процесс: {e}")
        
        # Запускаем потоки для асинхронной работы
        stdout_thread = threading.Thread(target=read_from_process, daemon=True)
        stdin_thread = threading.Thread(target=write_to_process, daemon=True)
        
        stdout_thread.start()
        stdin_thread.start()
        
        # Ждем завершения потоков
        stdin_thread.join()
        
        # Завершаем процесс
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except:
                process.kill()
        
    except Exception as e:
        print(f"Ошибка при работе с клиентом: {e}")
    finally:
        try:
            conn.close()
        except:
            pass

def start_server(host='0.0.0.0', port=4022):
    """Запуск Telnet сервера"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Устанавливаем опцию для немедленной отправки данных
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Сервер запущен на {host}:{port}")
    print(f"Код доступа: {ACCESS_CODE}")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"\nПодключение от {addr}")
            
            # Устанавливаем TCP_NODELAY для клиентского соединения
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Обрабатываем каждого клиента в отдельном потоке
            client_thread = threading.Thread(
                target=handle_client_windows,
                args=(conn,),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    # Устанавливаем код доступа, если не задан
    if not ACCESS_CODE:
        ACCESS_CODE = "1234"  # Пароль по умолчанию
        print(f"Внимание: Используется пароль по умолчанию: {ACCESS_CODE}")
        print("Задайте переменную окружения TELNET_ACCESS для изменения пароля")
    
    telnet_port = 4022
    
    # Получаем IP адрес
    try:
        ip_adress = get_local_ip()
    except:
        ip_adress = '127.0.0.1'
    
    print(f"Запуск сервера на {ip_adress}:{telnet_port}")
    start_server(host=ip_adress, port=telnet_port)