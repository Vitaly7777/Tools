import schedule
import time
import sys
import subprocess  # для запуска другого скрипта

def my_job():
    subprocess.run(['./.venv/bin/python', 'file_monitor.py'])

schedule.every().day.at("19:30").do(my_job)

try:
    while True:
        schedule.run_pending()
        time.sleep(60)  # проверка каждую минуту
except KeyboardInterrupt:
    print("\nОстановка по Ctrl+C")
    sys.exit(0)
