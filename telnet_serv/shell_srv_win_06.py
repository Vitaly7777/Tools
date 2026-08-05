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
                
                if cmd == DO:
                    if opt in [ECHO, SUPPRESS_GO_AHEAD]:
                        conn.send(IAC + WILL + opt)
                    else:
                        conn.send(IAC + WONT + opt)
                elif cmd == WILL:
                    if opt in [TERMINAL_TYPE, WINDOW_SIZE]:
                        conn.send(IAC + DO + opt)
                    else:
                        conn.send(IAC + DONT + opt)
                    
                i += 3
                continue
        i += 1
    
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
    
    conn.send(IAC + WILL + ECHO)
    conn.send(IAC + WILL + SUPPRESS_GO_AHEAD)
    
    time.sleep(0.3)
    
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
    
    conn.send(b"\r\nAccess code: ")
    
    password = ""
    
    while True:
        try:
            char = conn.recv(1)
            if not char:
                return False
            
            if char == IAC:
                cmd = conn.recv(2)
                if len(cmd) == 2:
                    handle_telnet_negotiation(conn, char + cmd)
                continue
            
            try:
                decoded_char = char.decode('utf-8', errors='ignore')
            except:
                continue
            
            if decoded_char in ['\r', '\n']:
                conn.send(b"\r\n")
                break
            
            if decoded_char in ['\b', '\x7f']:
                if password:
                    password = password[:-1]
                    conn.send(b'\b \b')
                continue
            
            if decoded_char.isprintable():
                password += decoded_char
                conn.send(b'*')
            
        except Exception as e:
            print(f"Ошибка при чтении пароля: {e}")
            return False
    
    if password.strip().lower() == ACCESS_CODE.strip().lower():
        conn.send(b"\r\nAccess granted. Starting shell...\r\n\r\n")
        return True
    else:
        conn.send(b"\r\nAccess denied.\r\n")
        return False

def handle_client_windows(conn, addr):
    """Обработка клиента для Windows"""
    
    # Добавляем соединение в список активных
    with connections_lock:
        active_connections.append(conn)
    
    try:
        if not authenticate(conn):
            return
        
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
            except:
                pass
        
        def write_to_process():
            nonlocal running
            try:
                while running and server_running:
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    clean_data = handle_telnet_negotiation(conn, data)
                    
                    if clean_data:
                        # Проверяем на команду выхода
                        if clean_data.strip() == b'exit':
                            break
                        try:
                            process.stdin.write(clean_data)
                            process.stdin.flush()
                        except:
                            break
            except:
                pass
        
        read_thread = threading.Thread(target=read_from_process, daemon=True)
        write_thread = threading.Thread(target=write_to_process, daemon=True)
        
        read_thread.start()
        write_thread.start()
        
        read_thread.join()
        write_thread.join()
        
        running = False
        
    except Exception as e:
        print(f"Ошибка при работе с клиентом {addr}: {e}")
    finally:
        # Останавливаем процесс
        try:
            if 'process' in locals():
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)
        except:
            pass
        
        # Закрываем соединение и удаляем из списка
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
    
    # Закрываем все активные соединения
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
            
            if command == 'stop' or command == 'quit' or command == 'exit':
                shutdown_server()
                break
            elif command == 'status':
                with connections_lock:
                    print(f"Активных подключений: {len(active_connections)}")
            elif command == 'help':
                print("Доступные команды:")
                print("  stop/quit/exit - остановить сервер")
                print("  status - показать статус сервера")
                print("  help - показать эту справку")
            else:
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
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    server_socket.settimeout(1.0)  # Таймаут для возможности проверки server_running
    
    print(f"Telnet сервер запущен на {host}:{port}")
    print(f"Код доступа: {ACCESS_CODE}")
    print("Для подключения используйте: telnet {} {}".format(host, port))
    print("\nКоманды управления сервером:")
    print("  stop/quit/exit - остановить сервер")
    print("  status - показать статус")
    print("  help - показать справку")
    print("  Ctrl+C - быстрое завершение\n")
    
    # Запускаем административную консоль в отдельном потоке
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