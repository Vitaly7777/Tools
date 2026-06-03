import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QRadioButton, QLineEdit, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Преобразователь путей Samba")
        self.setGeometry(100, 100, 400, 300)  # Размер окна
        
        # Основной layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Радиокнопки
        self.radio_smb_to_unc = QRadioButton("SMB в UNC (нормализовать путь)")
        self.radio_unc_to_smb = QRadioButton("UNC в SMB (извлечь относительный путь)")
        layout.addWidget(self.radio_smb_to_unc)
        layout.addWidget(self.radio_unc_to_smb)
        
        # Поля ввода
        self.label_input = QLabel("Введите путь:")
        self.line_edit_input = QLineEdit()
        layout.addWidget(self.label_input)
        layout.addWidget(self.line_edit_input)
        
        self.label_extra1 = QLabel("SMB Share (например, \\\\server\\\\share):")
        self.line_edit_extra1 = QLineEdit()  # Для SMB Share
        layout.addWidget(self.label_extra1)
        layout.addWidget(self.line_edit_extra1)
        
        self.label_extra2 = QLabel("Дополнительный путь (если нужно):")
        self.line_edit_extra2 = QLineEdit()  # Для относительного пути или другого параметра
        layout.addWidget(self.label_extra2)
        layout.addWidget(self.line_edit_extra2)
        
        # Кнопка преобразования
        self.button_convert = QPushButton("Преобразовать")
        self.button_convert.clicked.connect(self.on_convert_clicked)
        layout.addWidget(self.button_convert)
        
        # Поле вывода
        self.label_output = QLabel("Результат:")
        self.line_edit_output = QLineEdit()
        self.line_edit_output.setReadOnly(True)  # Только для чтения
        layout.addWidget(self.label_output)
        layout.addWidget(self.line_edit_output)
        
        # Кнопка копирования
        self.button_copy = QPushButton("Копировать результат")
        self.button_copy.clicked.connect(self.on_copy_clicked)
        layout.addWidget(self.button_copy)
        
        # Новая кнопка очистки
        self.button_clear = QPushButton("Очистить")
        self.button_clear.clicked.connect(self.on_clear_clicked)
        layout.addWidget(self.button_clear)
        
        # Подключение радиокнопок
        self.radio_smb_to_unc.toggled.connect(self.on_radio_toggled)
        self.radio_unc_to_smb.toggled.connect(self.on_radio_toggled)
    
    def on_radio_toggled(self, checked):
        if self.radio_smb_to_unc.isChecked():
            self.label_extra1.setText("SMB Share (например, \\\\server\\\\share):")
            self.label_extra2.setText("Относительный путь (например, folder/file.txt):")
        elif self.radio_unc_to_smb.isChecked():
            self.label_extra1.setText("UNC Путь (например, \\\\server\\\\share\\\\folder/file.txt):")
            self.label_extra2.setText("SMB Share (например, \\\\server\\\\share):")
    
    def on_convert_clicked(self):
        input_path = self.line_edit_input.text().strip()  # Основной ввод
        extra1 = self.line_edit_extra1.text().strip()  # Дополнительное поле 1
        extra2 = self.line_edit_extra2.text().strip()  # Дополнительное поле 2
        
        if self.radio_smb_to_unc.isChecked():
            # Логика: SMB в UNC - Нормализуем путь, добавляя SMB Share к относительному пути
            if not extra1.startswith("\\\\"):  # Проверяем, что SMB Share валиден
                QMessageBox.warning(self, "Ошибка", "SMB Share должен начинаться с \\\\.")
                return
            relative_path = input_path  # Или extra2, в зависимости от использования
            if not relative_path:  # Если не указан, используем extra2
                relative_path = extra2
            
            # Собрать полный UNC-путь
            full_unc_path = extra1 + "\\" + relative_path.replace("/", "\\")  # Заменяем / на \
            self.line_edit_output.setText(full_unc_path)
        
        elif self.radio_unc_to_smb.isChecked():
            # Логика: UNC в SMB - Извлечь относительный путь из UNC
            unc_path = extra1  # Полный UNC-путь
            smb_share = extra2  # Ожидаемый SMB Share
            
            if not unc_path.startswith("\\\\") or not smb_share.startswith("\\\\"):
                QMessageBox.warning(self, "Ошибка", "UNC-путь и SMB Share должны начинаться с \\\\.")
                return
            
            if unc_path.startswith(smb_share):
                relative_path = unc_path[len(smb_share):].lstrip("\\")  # Извлекаем относительный путь
                relative_path = relative_path.replace("\\", "/")  # Нормализуем, заменяя \ на /
                self.line_edit_output.setText(relative_path)
            else:
                QMessageBox.warning(self, "Ошибка", "UNC-путь не начинается с указанного SMB Share.")
                self.line_edit_output.setText("Ошибка")
        
        else:
            QMessageBox.warning(self, "Ошибка", "Выберите направление преобразования.")
            self.line_edit_output.setText("Ошибка")
    
    def on_copy_clicked(self):
        text_to_copy = self.line_edit_output.text()  # Получаем текст из поля вывода
        if text_to_copy:  # Проверяем, есть ли текст
            QApplication.clipboard().setText(text_to_copy)  # Копируем в буфер обмена
            QMessageBox.information(self, "Копирование", "Результат скопирован в буфер обмена!")  # Сообщение подтверждения
        else:
            QMessageBox.warning(self, "Ошибка", "Нет результата для копирования.")
    
    def on_clear_clicked(self):
        # Очищаем все поля
        self.line_edit_input.setText('')  # Очищаем основное поле ввода
        self.line_edit_extra1.setText('')  # Очищаем первое дополнительное поле
        self.line_edit_extra2.setText('')  # Очищаем второе дополнительное поле
        self.line_edit_output.setText('')  # Очищаем поле вывода

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
