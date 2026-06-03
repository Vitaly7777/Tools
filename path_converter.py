import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QRadioButton, QLineEdit,
    QPushButton, QLabel, QVBoxLayout, QWidget, 
    QMessageBox, QHBoxLayout, QButtonGroup
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Преобразователь путей Samba")
        self.setGeometry(100, 100, 800, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Радиокнопки
        self.radio_two_to_one = QRadioButton("Убрать двойные \\\\ (Из Python в UNC)")
        self.radio_one_to_two = QRadioButton("Добавить двойные \\\\ (Из UNC в Python)")
        self.radio_unc_to_smb = QRadioButton("UNC в SMB (Из Windows в smb:)")
        self.radio_smb_to_unc = QRadioButton("SMB в UNC (Из smb: в Windows)")


        # Группировка радиокнопок
        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.radio_two_to_one)
        self.radio_group.addButton(self.radio_one_to_two)
        self.radio_group.addButton(self.radio_unc_to_smb)
        self.radio_group.addButton(self.radio_smb_to_unc)
        
        # Выбор по умолчанию
        self.radio_two_to_one.setChecked(True)

        # Layout для радиокнопок
        radio1_layout = QHBoxLayout()
        radio2_layout = QHBoxLayout()
        
        radio1_layout.addWidget(self.radio_two_to_one)
        radio1_layout.addWidget(self.radio_one_to_two)
        radio2_layout.addWidget(self.radio_unc_to_smb)
        radio2_layout.addWidget(self.radio_smb_to_unc)
        
        layout.addLayout(radio1_layout)
        layout.addLayout(radio2_layout)

        # Поля ввода
        self.label_input = QLabel("Введите путь:")
        self.line_edit_input = QLineEdit()
        layout.addWidget(self.label_input)
        layout.addWidget(self.line_edit_input)

        # Поле вывода
        self.label_output = QLabel("Результат:")
        self.line_edit_output = QLineEdit()
        self.line_edit_output.setReadOnly(True)
        layout.addWidget(self.label_output)
        layout.addWidget(self.line_edit_output)

        # Кнопки
        button_layout = QHBoxLayout()
        
        self.button_clear = QPushButton("Очистить (Ctrl+D)")
        self.button_clear.clicked.connect(self.on_clear_clicked)
        self.button_clear.setShortcut("Ctrl+D")
        
        self.button_convert = QPushButton("Преобразовать (Enter)")
        self.button_convert.clicked.connect(self.on_convert_clicked)
        self.button_convert.setShortcut("Return")
        
        self.button_copy = QPushButton("Копировать результат (Ctrl+C)")
        self.button_copy.clicked.connect(self.on_copy_clicked)
        self.button_copy.setShortcut("Ctrl+C")
        
        button_layout.addWidget(self.button_clear)
        button_layout.addWidget(self.button_convert)
        button_layout.addWidget(self.button_copy)
        layout.addLayout(button_layout)
        # Подсказки
        self.radio_two_to_one.setToolTip("Преобразует пути вида \\\\\\\\server\\\\share в \\\\server\\share")
        self.radio_one_to_two.setToolTip("Преобразует пути вида \\\\server\\share в \\\\\\\\server\\\\share")
        self.radio_unc_to_smb.setToolTip("Преобразует пути вида \\\\server\\share в smb://server/share")
        self.radio_smb_to_unc.setToolTip("Преобразует пути вида smb://server/share в \\\\server\\share")
        self.line_edit_input.setToolTip("Введите путь для преобразования")
        self.line_edit_output.setToolTip("Поле результата:Доступно только для копирования (Ctrl+C)")

    def on_convert_clicked(self):
        input_path = self.line_edit_input.text().strip().replace('"', '').replace("'", "")
        
        if not input_path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для преобразования.")
            return
        
        if self.radio_two_to_one.isChecked():
            # Более безопасная замена
            result = input_path.replace(r'\\', '\\')
        elif self.radio_one_to_two.isChecked():
            result = input_path.replace('\\', r'\\')
        elif self.radio_smb_to_unc.isChecked():
            # Убираем "smb:" в любом регистре
            cleaned = input_path[4:] if input_path.lower().startswith("smb:") else input_path
            # Заменяем все слеши на обратные
            result = cleaned.replace("/", "\\")
        elif self.radio_unc_to_smb.isChecked():
            if self.validate_unc(input_path):
                QMessageBox.warning(self, "Ошибка", "Удалите двойные обратные слеши из поля ввода.")
                return            
            # Заменяем обратные слеши на прямые
            cleaned = input_path.replace("\\", "/")
            # Убираем возможные дубли "smb:"
            if cleaned.lower().startswith("smb:"):
                cleaned = cleaned[4:]
            result = f"smb:{cleaned}"
            if not self.validate_smb(result):
                 QMessageBox.warning(self, "Внимание", "Некорректный smb путь.")
        else:
            QMessageBox.warning(self, "Ошибка", "Выберите направление преобразования.")
            return
            
        self.line_edit_output.setText(result)
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

    def validate_unc(self, path):
        # Проверка наличия двойных обратных слешов в поле ввода
        return  r"\\\\" in path or r'\\' in path[4:]

    def validate_smb(self, path):
        return path.startswith("smb://")   


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
