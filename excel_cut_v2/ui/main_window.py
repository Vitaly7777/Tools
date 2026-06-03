from core.worker import CutFilesWorker
from ui.windgets import LogWidget


from PySide6.QtCore import QThread
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget

from ui.windgets import ConfigWidget, ProgressWidget


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Обрезка Excel/ODS файлов")
        self.resize(900, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.config_widget = ConfigWidget()
        self.progress_widget = ProgressWidget()
        self.log_widget = LogWidget()

        self.tabs.addTab(self.config_widget, "Конфигурация")
        self.tabs.addTab(self.progress_widget, "Прогресс")
        self.tabs.addTab(self.log_widget, "Логи")

        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("Запустить")
        self.start_btn.clicked.connect(self.start_processing)
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)

        control_layout.addStretch()
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)

        layout.addLayout(control_layout)

    def start_processing(self):
        config = self.config_widget.get_config()
        self.progress_widget.reset()
        self.log_widget.text_edit.clear()

        self.worker_thread = QThread()
        self.worker = CutFilesWorker(config)
        self.worker.moveToThread(self.worker_thread)

        self.worker.progress.connect(self.progress_widget.set_progress)
        self.worker.file_done.connect(self.progress_widget.add_result)
        self.worker.log.connect(self.log_widget.append_log)
        self.worker.finished.connect(self.on_finished)

        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def stop_processing(self):
        if self.worker:
            self.worker.stop()
        self.log_widget.append_log("Остановка обработки...", "WARNING")

    def on_finished(self, _config):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker = None
        self.worker_thread = None

        self.progress_widget.status_label.setText("Обработка завершена")
