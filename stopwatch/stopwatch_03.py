import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QListWidget
)
from PySide6.QtGui import QFont


class Stopwatch(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Секундомер")
        self.setFixedSize(300, 450)

        # Состояние
        self.elapsed_ms = 0
        self.running = False
        self.lap_count = 0

        # Таймер (интервал 100 мс = 0.1 с)
        self.timer_interval = 100
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)

        self.init_ui()

    def init_ui(self):
        # Центральный виджет (обязательно для QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # --- Метка времени ---
        self.time_label = QLabel("00:00:00.0")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setFont(QFont("Consolas", 30, QFont.Bold))
        main_layout.addWidget(self.time_label)

        # --- Кнопки управления ---
        btn_layout = QHBoxLayout()
        self.start_button = QPushButton("Старт")
        self.lap_button = QPushButton("Круг")
        self.reset_button = QPushButton("Сброс")

        btn_layout.addWidget(self.start_button)
        btn_layout.addWidget(self.lap_button)
        btn_layout.addWidget(self.reset_button)
        main_layout.addLayout(btn_layout)

        # --- Список кругов ---
        self.lap_list = QListWidget()
        main_layout.addWidget(self.lap_list)

        # --- Начальное состояние кнопок ---
        self.lap_button.setEnabled(False)   # пока таймер не запущен
        self.reset_button.setEnabled(True)  # всегда доступен

        # --- Подключение сигналов ---
        self.start_button.clicked.connect(self.start_stop)
        self.lap_button.clicked.connect(self.lap)
        self.reset_button.clicked.connect(self.reset)

        # Первоначальное отображение
        self.update_display()

    def start_stop(self):
        if self.running:
            # Остановка
            self.timer.stop()
            self.start_button.setText("Старт")
            self.lap_button.setEnabled(False)
        else:
            # Запуск
            self.timer.start(self.timer_interval)   # передаём интервал!
            self.start_button.setText("Стоп")
            self.lap_button.setEnabled(True)
        self.running = not self.running

    def reset(self):
        self.timer.stop()
        self.elapsed_ms = 0
        self.lap_count = 0
        self.running = False
        self.start_button.setText("Старт")
        self.lap_button.setEnabled(False)
        self.lap_list.clear()
        self.update_display()

    def lap(self):
        self.lap_count += 1
        lap_text = f"Круг {self.lap_count}: {self.format_time(self.elapsed_ms)}"
        self.lap_list.insertItem(0, lap_text)   # новые круги сверху

    def update_time(self):
        self.elapsed_ms += self.timer_interval
        self.update_display()

    def update_display(self):
        self.time_label.setText(self.format_time(self.elapsed_ms))

    def format_time(self, ms):
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        tenths = (ms // 100) % 10   # десятые доли секунды
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{tenths}"


def main():
    app = QApplication(sys.argv)
    window = Stopwatch()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()