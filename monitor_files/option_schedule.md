# Основные опции schedule
Интервал	    Синтаксис	        Пример
Каждые N секунд	every(N).seconds	schedule.every(30).seconds.do(job)
Каждые N минут	every(N).minutes	schedule.every(5).minutes.do(job)
Каждые N часов	every(N).hours	    schedule.every(10).hours.do(job)
Каждые N дней	every(N).days	    schedule.every(2).days.do(job)
Каждые N недель	every(N).weeks	    schedule.every().week.do(job)



# Точное время в день/час/минуту
Задача	            Синтаксис
Ежедневно в 08:00	schedule.every().day.at("08:00").do(job)
Каждый час в :42	schedule.every().hour.at(":42").do(job)
Каждую минуту в :17	schedule.every().minute.at(":17").do(job)
С часовым поясом	schedule.every().day.at("08:00", "Europe/Moscow").do(job)

# Случайный интервал 5-10 минут
schedule.every(5).to(10).minutes.do(job)

# До определенного времени (до 18:30)
schedule.every(1).hours.until("18:30").do(job)

# Выполнить все задачи сразу
schedule.run_all(delay_seconds=10)  # с задержкой 10 сек между задачами
