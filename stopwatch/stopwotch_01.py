import sys
from PySide6.QtCore import QTimer, QTime, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout

class Stopwatch(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Секундомер")
        self.setFixedSize(300, 150)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Время в миллисекундах
        self.elapsed_ms = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer_interval = 100  # мс

        # Виджеты
        self.time_label = QLabel("00:00:00.0")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 30px; font-weight: bold;")

        self.start_button = QPushButton("Старт")
        self.stop_button = QPushButton("Стоп")
        self.reset_button = QPushButton("Сброс")

        # Подключение сигналов
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.reset_button.clicked.connect(self.reset)

        # Layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.reset_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.time_label)
        main_layout.addLayout(button_layout)

        central_widget.setLayout(main_layout)

        self.update_display()

    def start(self):
        if not self.timer.isActive():
            self.timer.start(self.timer_interval)
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

    def stop(self):
        if self.timer.isActive():
            self.timer.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def reset(self):
        self.timer.stop()
        self.elapsed_ms = 0
        self.update_display()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_time(self):
        self.elapsed_ms += self.timer_interval
        self.update_display()

    def update_display(self):
        # Преобразуем миллисекунды в QTime
        seconds = self.elapsed_ms // 1000
        minutes = seconds // 60
        hours = minutes // 60
        seconds %= 60
        minutes %= 60
        # Десятые доли секунды
        tenths = (self.elapsed_ms // 100) % 10
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{tenths}"
        self.time_label.setText(time_str)

def main():
    app = QApplication(sys.argv)
    window = Stopwatch()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()