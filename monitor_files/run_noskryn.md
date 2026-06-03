# Запуск  — для работы в фоне: 
nohup python3 script.py > log.txt 2>&1 &
nohup /usr/bin/python3 /home/PR.RT.RU/v.karitsky/work/file_monitor/shedule.py > /home/PR.RT.RU/v.karitsky/work/file_monitor/log.txt 2>&1 
 - Если используете виртуальное окружение: source /путь/к/venv/bin/activate && python скрипт.py
nohup /home/PR.RT.RU/v.karitsky/work/file_monitor/.venv/bin/python /home/PR.RT.RU/v.karitsky/work/file_monitor/shedule.py > /home/PR.RT.RU/v.karitsky/work/file_monitor/log.txt 2>&1 
which python3 

/home/PR.RT.RU/v.karitsky/work/file_monitor/.venv/bin/python /home/PR.RT.RU/v.karitsky/work/file_monitor/shedule.py


 Или screen -S myscript → запустить → Ctrl+A, D (отсоединиться)
