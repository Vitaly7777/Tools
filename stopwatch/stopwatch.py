import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QListWidget
)
from PySide6.QtGui import QFont

class Stopwatch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Секундомер")
        self.setFixedSize(350, 400)

        # Состояние: прошедшие миллисекунды
        self.elapsed_ms = 0

        self.running = False
        self.lap_count = 0

        # Интервал обновления (100 мс = 0.1 с)
        self.timer_interval = 100
        self.timer = QTimer()
        self.timer.setInterval(self.timer_interval)
        self.timer.timeout.connect(self.update_time)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()   

        # Элементы интерфейса
        self.time_label = QLabel("00:00:00.0")
        self.time_label.setAlignment(Qt.AlignCenter)
        # self.time_label.setStyleSheet("font-size: 30px; font-weight: bold;")
        self.time_label.setFont(QFont("Consolas", 30, QFont.Bold))
        layout.addWidget(self.time_label)

        # Кнопки управления
        btn_layout = QHBoxLayout()

        self.start_button = QPushButton("Старт")
        btn_layout.addWidget(self.start_button)
        # self.stop_button = QPushButton("Стоп")
        self.lap_button = QPushButton("Круг")
        btn_layout.addWidget(self.lap_button)
        self.reset_button = QPushButton("Сброс")
        btn_layout.addWidget(self.reset_button)
        self.copy_button = QPushButton("Копи.круги")   # новая кнопка
        self.copy_button.setEnabled(False)     # активна только когда есть круги
        btn_layout.addWidget(self.copy_button)               # добавляем в ряд

        # Подключение сигналов
        self.start_button.clicked.connect(self.start_stop)
        self.lap_button.clicked.connect(self.lap)
        self.reset_button.clicked.connect(self.reset)
        self.copy_button.clicked.connect(self.copy_laps)

        # # Расположение
        layout.addLayout(btn_layout)

        #  список кругов
        self.lap_list = QListWidget()
        layout.addWidget(self.lap_list)
        
        # Начальное отображение
        self.setLayout(layout)

    def start_stop(self):
        if self.running:
            #остановка
            self.timer.stop() 
            self.start_button.setText('Старт')  
            # self.lap_button.setEnabled(False) 
        else:
            # Запуск
            self.timer.start()
            self.start_button.setText('Стоп')  
            # self.lap_button.setEnabled(True)
        self.running = not self.running

    def reset(self):
        """Сбросить время и остановить таймер."""
        self.timer.stop()
        self.elapsed_ms = 0
        self.lap_count = 0
        self.running = False
        self.time_label.setText("00:00:00.0")
        self.start_button.setText('Старт')
        # self.start_button.setEnabled(True)
        # self.lap_list.setEnabled(False)
        self.copy_button.setEnabled(False) 
        self.lap_list.clear()

    def format_time(self, ms):
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        tenths = (ms // 100) % 10   # десятые доли секунды
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{tenths}'

    def update_time(self):
        """Обновить прошедшее время при срабатывании таймера."""
        self.elapsed_ms += self.timer_interval
        self.time_label.setText(self.format_time(self.elapsed_ms))


    def lap(self):
        self.lap_count += 1
        self.lap_text = f'Круг {self.lap_count}: {self.format_time(self.elapsed_ms)}'
        self.lap_list.insertItem(0, self.lap_text)      # новый круг сверху
        self.copy_button.setEnabled(True)       # после добавления круга кнопка становится доступной


    def copy_laps(self):
        """Копирует все записи из списка кругов в буфер обмена."""
        items = []
        for i in range(self.lap_list.count()):
            items.append(self.lap_list.item(i).text())
        text = "\n".join(items)
        clipboard = QApplication.clipboard()   # получаем доступ к буферу обмена
        clipboard.setText(text)

def main():
    app = QApplication(sys.argv)
    window = Stopwatch()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()