import socket
import os
import subprocess
import threading
import sys
import select
import time
import signal
from get_ip import get_local_ip

# Задаём секретный код доступа
ACCESS_CODE = os.getenv('TELNET_ACCESS', '').strip()

# Глобальные переменные для управления сервером
server_running = True
active_connections = []
connections_lock = threading.Lock()

# Константы Telnet
IAC  = b'\xff'
WILL = b'\xfb'
WONT = b'\xfc'
DO   = b'\xfd'
DONT = b'\xfe'
SB   = b'\xfa'
SE   = b'\xf0'

# Опции Telnet
ECHO = b'\x01'
SUPPRESS_GO_AHEAD = b'\x03'
TERMINAL_TYPE = b'\x18'
WINDOW_SIZE = b'\x1f'
LINEMODE = b'\x22'  # Режим построчного ввода
BINARY = b'\x00'    # Бинарный режим

def handle_telnet_negotiation(conn, data):
    """Обрабатывает Telnet-команды от клиента"""
    i = 0
    response = b""
    
    while i < len(data):
        if data[i:i+1] == IAC:
            if i + 2 < len(data):
                cmd = data[i+1:i+2]
                opt = data[i+2:i+3]
                
                print(f"[Telnet Debug] Получена команда: IAC {cmd.hex() if cmd else '??'} {opt.hex() if opt else '??'}")
                
                # Обработка команд
                if cmd == DO:
                    # Клиент просит нас выполнять опцию
                    if opt == SUPPRESS_GO_AHEAD:
                        # Соглашаемся подавлять Go Ahead
                        response += IAC + WILL + SUPPRESS_GO_AHEAD
                        print("[Telnet] Включаем Suppress Go Ahead")
                    elif opt == ECHO:
                        # Соглашаемся на эхо (мы будем отправлять эхо)
                        response += IAC + WILL + ECHO
                        print("[Telnet] Включаем Echo")
                    elif opt == BINARY:
                        # Соглашаемся на бинарный режим
                        response += IAC + WILL + BINARY
                        print("[Telnet] Включаем Binary mode")
                    else:
                        # Отказываемся от других опций
                        response += IAC + WONT + opt
                        
                elif cmd == WILL:
                    # Клиент хочет выполнять опцию
                    if opt == TERMINAL_TYPE:
                        # Запрашиваем тип терминала
                        response += IAC + SB + TERMINAL_TYPE + b'\x01' + IAC + SE
                        print("[Telnet] Запрашиваем тип терминала")
                    elif opt == WINDOW_SIZE:
                        # Соглашаемся на информацию о размере окна
                        response += IAC + DO + WINDOW_SIZE
                        print("[Telnet] Принимаем информацию о размере окна")
                    elif opt == BINARY:
                        # Соглашаемся на бинарный режим
                        response += IAC + DO + BINARY
                        print("[Telnet] Принимаем Binary mode")
                    else:
                        # Отказываемся от других опций
                        response += IAC + DONT + opt
                
                elif cmd == SB:
                    # Подкоманда - ищем SE (конец подкоманды)
                    sub_end = data.find(IAC + SE, i + 3)
                    if sub_end != -1:
                        sub_data = data[i+3:sub_end]
                        print(f"[Telnet] Подкоманда: {opt.hex()} данные: {sub_data.hex() if sub_data else 'пусто'}")
                        i = sub_end + 2
                        continue
                
                i += 3
                continue
        i += 1
    
    # Отправляем ответы на Telnet-команды
    if response:
        conn.send(response)
    
    # Возвращаем только "чистые" данные (без Telnet-команд)
    clean = bytearray()
    i = 0
    while i < len(data):
        if data[i:i+1] == IAC:
            if i + 1 < len(data) and data[i+1:i+2] == SB:
                # Пропускаем всю подкоманду до SE
                sub_end = data.find(IAC + SE, i + 2)
                if sub_end != -1:
                    i = sub_end + 2
                else:
                    i += 1
            elif i + 2 < len(data):
                i += 3
            else:
                i += 1
        else:
            clean.append(data[i])
            i += 1
    
    return bytes(clean)

def authenticate(conn):
    """Аутентификация клиента с правильной настройкой Telnet"""
    
    # Отправляем начальные настройки для посимвольного режима
    # Включаем эхо
    conn.send(IAC + WILL + ECHO)
    # Включаем Suppress Go Ahead (важно для посимвольного режима)
    conn.send(IAC + WILL + SUPPRESS_GO_AHEAD)
    
    # Даём время клиенту ответить
    time.sleep(0.5)
    
    # Обрабатываем начальные переговоры
    conn.setblocking(False)
    try:
        for _ in range(10):
            ready = select.select([conn], [], [], 0.2)
            if ready[0]:
                data = conn.recv(4096)
                if data:
                    if IAC in data:
                        handle_telnet_negotiation(conn, data)
                    else:
                        break
                else:
                    break
            else:
                break
    except:
        pass
    conn.setblocking(True)
    
    # Отправляем приглашение для ввода пароля
    conn.send(b"\r\nAccess code: ")
    
    # Получаем пароль
    password = ""
    
    while True:
        try:
            char = conn.recv(1)
            if not char:
                return False
            
            # Проверяем на Telnet-команды
            if char == IAC:
                # Читаем следующие байты команды
                cmd = conn.recv(1)
                if cmd == SB:
                    # Подкоманда - читаем до SE
                    buffer = bytearray()
                    while True:
                        b = conn.recv(1)
                        if b == IAC:
                            next_b = conn.recv(1)
                            if next_b == SE:
                                break
                            buffer.extend(b + next_b)
                        else:
                            buffer.append(b[0])
                    handle_telnet_negotiation(conn, IAC + cmd + buffer + IAC + SE)
                elif cmd:
                    opt = conn.recv(1)
                    if cmd and opt:
                        handle_telnet_negotiation(conn, IAC + cmd + opt)
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

def handle_client_windows(conn, addr):
    """Обработка клиента для Windows с посимвольным вводом"""
    
    with connections_lock:
        active_connections.append(conn)
    
    try:
        if not authenticate(conn):
            return
        
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
        
        running = True
        
        def read_from_process():
            """Чтение вывода процесса и отправка клиенту"""
            nonlocal running
            try:
                while running and server_running:
                    char = process.stdout.read(1)
                    if not char:
                        break
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
                while running and server_running:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # Очищаем от Telnet-команд
                    clean_data = handle_telnet_negotiation(conn, data)
                    
                    if clean_data:
                        # Отправляем эхо обратно клиенту (чтобы видеть что печатаешь)
                        conn.send(clean_data)
                        
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
        print(f"Ошибка при работе с клиентом {addr}: {e}")
    finally:
        try:
            if 'process' in locals():
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)
        except:
            pass
        
        try:
            conn.close()
        except:
            pass
        
        with connections_lock:
            if conn in active_connections:
                active_connections.remove(conn)
        
        print(f"Клиент {addr} отключен")

def shutdown_server():
    """Корректное завершение сервера"""
    global server_running
    print("\nЗавершение работы сервера...")
    server_running = False
    
    with connections_lock:
        for conn in active_connections:
            try:
                conn.send(b"\r\nServer is shutting down...\r\n")
                conn.close()
            except:
                pass
        active_connections.clear()

def admin_console():
    """Административная консоль для управления сервером"""
    global server_running
    
    while server_running:
        try:
            command = input().strip().lower()
            
            if command in ['stop', 'quit', 'exit']:
                shutdown_server()
                break
            elif command == 'status':
                with connections_lock:
                    print(f"Активных подключений: {len(active_connections)}")
            elif command == 'help':
                print("\nДоступные команды:")
                print("  stop/quit/exit - остановить сервер")
                print("  status - показать статус сервера")
                print("  help - показать эту справку")
                print("  Ctrl+C - быстрое завершение\n")
            elif command:
                print(f"Неизвестная команда: {command}")
                
        except EOFError:
            break
        except KeyboardInterrupt:
            shutdown_server()
            break

def signal_handler(signum, frame):
    """Обработчик сигналов"""
    print(f"\nПолучен сигнал {signum}")
    shutdown_server()

def start_server(host='0.0.0.0', port=4022):
    """Запуск Telnet сервера"""
    global server_running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    server_socket.settimeout(1.0)
    
    print(f"Telnet сервер запущен на {host}:{port}")
    print(f"Код доступа: {ACCESS_CODE}")
    print("Для подключения используйте: telnet {} {}".format(host, port))
    print("\nКоманды управления сервером:")
    print("  stop/quit/exit - остановить сервер")
    print("  status - показать статус")
    print("  help - показать справку")
    print("  Ctrl+C - быстрое завершение\n")
    
    admin_thread = threading.Thread(target=admin_console, daemon=True)
    admin_thread.start()
    
    try:
        while server_running:
            try:
                conn, addr = server_socket.accept()
                print(f"\nНовое подключение от {addr}")
                
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                client_thread = threading.Thread(
                    target=handle_client_windows,
                    args=(conn, addr),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if server_running:
                    print(f"Ошибка при принятии подключения: {e}")
                    
    except KeyboardInterrupt:
        print("\nПолучен сигнал прерывания")
    finally:
        shutdown_server()
        server_socket.close()
        print("Сервер остановлен")

if __name__ == "__main__":
    if not ACCESS_CODE:
        ACCESS_CODE = "1234"
        print(f"Используется пароль по умолчанию: {ACCESS_CODE}")
    
    telnet_port = 4022
    
    try:
        ip_address = get_local_ip()
    except:
        ip_address = '127.0.0.1'
    
    start_server(host=ip_address, port=telnet_port)