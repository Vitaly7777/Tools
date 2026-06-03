# Найти PID
ps aux | grep python

# Graceful kill
kill -SIGINT <PID>  # Ctrl+C эквивалент

# Принудительно
kill -9 <PID>

# Просмотр лога
cat output.log
 # Найти процесс             
ps aux | grep main.py 
# Следить за логом в реальном времени     
tail -f output.log        


USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user     12345  0.1  0.5  10240  2048 pts/0    S    14:22   0:01 python3 schedule.py
user     12347  0.0  0.0   5120   256 ?        S    14:22   0:00 grep --color=auto schedule.py
