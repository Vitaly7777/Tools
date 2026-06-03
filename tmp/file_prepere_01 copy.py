import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QRadioButton, QLineEdit, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Преобразователь путей Samba")
        self.setGeometry(100, 100, 800, 300)  # Размер окна
        
        # Основной layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Радиокнопки
        self.radio_two_to_one = QRadioButton("Убрать двойные \\\\")
        self.radio_smb_to_unc = QRadioButton("SMB в UNC (нормализовать путь)")
        self.radio_unc_to_smb = QRadioButton("UNC в SMB (извлечь относительный путь)")

        layout.addWidget(self.radio_two_to_one)
        layout.addWidget(self.radio_smb_to_unc)
        layout.addWidget(self.radio_unc_to_smb)
        # кнопка очиски
        self.button_clear = QPushButton("Очистить")
        self.button_clear.clicked.connect(self.on_clear_clicked)
        layout.addWidget(self.button_clear)
        
        # Поля ввода
        self.label_input = QLabel("Введите путь:")
        self.line_edit_input = QLineEdit()
        layout.addWidget(self.label_input)
        layout.addWidget(self.line_edit_input)
        
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

        # Новая кнопка копирования
        self.button_copy = QPushButton("Копировать результат")
        self.button_copy.clicked.connect(self.on_copy_clicked)
        layout.addWidget(self.button_copy)
        
        # Подключение радиокнопок
        # self.radio_smb_to_unc.toggled.connect(self.on_radio_toggled)
        # self.radio_smb_to_unc.toggled.connect(self.on_radio_toggled)
        # self.radio_unc_to_smb.toggled.connect(self.on_radio_toggled)
    
    # def on_radio_toggled(self, checked):
    #     if self.radio_smb_to_unc.isChecked():
    #         self.label_extra1.setText("SMB Share (например, \\\\server\\\\share):")
    #         # self.label_extra2.setText("Относительный путь (например, folder/file.txt):")
    #     elif self.radio_unc_to_smb.isChecked():
    #         self.label_extra1.setText("UNC Путь (например, \\\\server\\\\share\\\\folder/file.txt):")
    #         self.label_extra2.setText("SMB Share (например, \\\\server\\\\share):")
    
    def on_convert_clicked(self):
        input_path = self.line_edit_input.text().strip()  # Основной ввод

        if self.radio_two_to_one.isChecked():
            self.line_edit_output.setText(input_path.replace("\\\\","\\"))
        elif self.radio_smb_to_unc.isChecked():
            if input_path.lower().startswith("smb:"):
                input_path = input_path[4:]
            self.line_edit_output.setText(input_path.replace("/","\\"))    
        elif self.radio_unc_to_smb.isChecked():
            input_path = input_path.replace("\\","/")
            path_smb = f'smb:{input_path}'
            self.line_edit_output.setText(path_smb ) 
        else:
            QMessageBox.warning(self, "Ошибка", "Выберите направление преобразования.")
            self.line_edit_output.setText("Ошибка")

    def on_copy_clicked(self):
        text_to_copy = self.line_edit_output.text()  # Получаем текст из поля вывода
        if text_to_copy:  # Проверяем, есть ли текст
            QApplication.clipboard().setText(text_to_copy)  # Копируем в буфер обмена
            # QMessageBox.information(self, "Копирование", "Результат скопирован в буфер обмена!")  # Сообщение подтверждения
        else:
            QMessageBox.warning(self, "Ошибка", "Нет результата для копирования.")

    def on_clear_clicked(self):
        self.line_edit_input.setText('')
        self.line_edit_output.setText('')  

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
