import os
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QDialog, QLabel, QLineEdit, QPushButton,\
            QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QRadioButton, QButtonGroup, QFormLayout, \
            QDialogButtonBox
from PyQt5.QtCore import Qt  # Для флагов, если нужно

# Глобальная проверка и инициализация QApplication
def ensure_qapp():
    if QApplication.instance() is None:
        app = QApplication(sys.argv)
        return app
    return QApplication.instance()

'''
Модуль UI с функциями, переписанными на PyQt5:
input_ui:                   Отображает интерфейс для ввода названия.
select_folder:              Открывает диалог для выбора директории.
select_file:                Открывает диалог для выбора файла.
path_out_ui:                Отображает интерфейс для выбора названия файла и папки сохранения.
message_ui:                 Отображает сообщение пользователю в зависимости от типа.
login_ui:                   Отображает интерфейс для ввода логина и пароля.
select_save_file            Открывает диалог для выбора файла. Эта версия использует диалог сохранения
show_yes_no_dialog          Создает диалоговое окно с кнопками 'Да' и 'Нет'
show_radio_button_dialog    Создает диалоговое окно с радиокнопками на основе списка элементов
'''

def input_ui(title: str = "Укажите название", ext: str = ""):
    """
    Отображает интерфейс для ввода названия.
    Возвращает введённое название с расширением или None, если отмена.

    Параметры:
    title (str): Текст для метки.
    ext (str): Расширение для добавления к названию.
    """
    app = ensure_qapp()  # Убедимся, что QApplication запущен
    
    dialog = QDialog()
    dialog.setWindowTitle("Выбор названия")
    
    layout = QVBoxLayout()
    
    label = QLabel(f"{title}:")
    layout.addWidget(label)
    
    line_edit = QLineEdit()
    layout.addWidget(line_edit)
    
    if ext:
        ext_label = QLabel(f"({ext})")
        layout.addWidget(ext_label)
    
    result = None  # Переменная для результата
    
    def on_ok():
        nonlocal result
        str_name = line_edit.text().strip()
        if not str_name:
            QMessageBox.critical(dialog, "Ошибка", "Поле не может быть пустым.")
            return
        result = f"{str_name}{ext}"
        dialog.accept()  # Закрываем диалог с подтверждением
    
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(on_ok)
    layout.addWidget(ok_button)
    
    dialog.setLayout(layout)
    
    if dialog.exec_() == QDialog.Accepted:  # Ждём результата
        return result
    return None

def select_folder(title: str = "Выберите папку с исходными данными", initial_dir: str = ""):
    """
    Открывает диалог для выбора директории.

    Параметры:
    title (str): Заголовок диалога.
    initial_dir (str): Начальная директория (опционально).

    Возвращает:
    str: Путь к выбранной директории или None, если отмена.
    """
    app = ensure_qapp()
    try:
        folder = QFileDialog.getExistingDirectory(None, title, initial_dir)
        return folder if folder else None
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        return None

def select_file(title: str = "Выберите файл с исходными данными", ext: str = "All Files (*);;Excel Files (*.xls *.xlsx)"):
    """
    Открывает диалог для выбора файла.

    Параметры:
    title (str): Заголовок диалога.
    ext (str): Фильтр для расширений файлов (например, "All Files (*);;Excel Files (*.xls *.xlsx)").

    Возвращает:
    str: Путь к выбранному файлу или None, если отмена.
    """
    app = ensure_qapp()
    try:
        file_path, _ = QFileDialog.getOpenFileName(None, title, "", ext)
        return file_path if file_path else None
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        return None
    
def select_save_file(title: str = "Выберите файл", ext: str = "All Files (*);;Excel Files (*.xls *.xlsx)"):
    """
    Открывает диалог для выбора файла. Эта версия использует диалог сохранения,
    чтобы не проверять существование файла напрямую. Пользователь может ввести
    или выбрать путь, даже если файл не существует.

    Параметры:
    title (str): Заголовок диалога.
    ext (str): Фильтр для расширений файлов (например, "All Files (*);;Excel Files (*.xls *.xlsx)").

    Возвращает:
    str: Путь к выбранному файлу или None, если отмена.
    """
    app = ensure_qapp()  # Убедимся, что QApplication запущен
    try:
        # Используем getSaveFileName() вместо getOpenFileName(), чтобы избежать проверки существования
        file_path, _ = QFileDialog.getSaveFileName(
            None,  # Родительское окно (None для модального диалога)
            title,  # Заголовок
            "",     # Начальный путь (пустой по умолчанию)
            ext     # Фильтр расширений
        )
        return file_path if file_path else None  # Возвращаем путь, если выбран, иначе None
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        return None

def path_out_ui(title: str = "Выберите папку для сохранения", ext: str = "xlsx"):
    """
    Отображает интерфейс для выбора названия файла и папки сохранения.
    Возвращает полный путь к файлу или None, если пользователь отменил операцию.

    Параметры:
    title (str): Заголовок для выбора папки.
    ext (str): Расширение файла (например, "xlsx").
    """
    app = ensure_qapp()
    
    dialog = QDialog()
    dialog.setWindowTitle("Выбор файла для сохранения")
    
    layout = QVBoxLayout()
    
    # Строка для папки
    folder_layout = QHBoxLayout()
    folder_label = QLabel("Папка для сохранения:")
    folder_line = QLineEdit()
    folder_line.setReadOnly(True)
    folder_button = QPushButton("Выбрать папку")
    
    def select_directory():
        folder = QFileDialog.getExistingDirectory(dialog, title)
        if folder:
            folder_line.setText(folder)
    
    folder_button.clicked.connect(select_directory)
    folder_layout.addWidget(folder_label)
    folder_layout.addWidget(folder_line)
    folder_layout.addWidget(folder_button)
    layout.addLayout(folder_layout)
    
    # Строка для имени файла
    file_layout = QHBoxLayout()
    file_label = QLabel("Название файла:")
    file_line = QLineEdit()
    ext_label = QLabel(f".{ext}")
    file_layout.addWidget(file_label)
    file_layout.addWidget(file_line)
    file_layout.addWidget(ext_label)
    layout.addLayout(file_layout)
    
    result = None
    
    def on_save():
        nonlocal result
        file_name = file_line.text().strip()
        directory = folder_line.text().strip()
        if not file_name or not directory:
            QMessageBox.critical(dialog, "Ошибка", "Укажите название файла и выберите папку.")
            return
        result = f"{directory}/{file_name}.{ext}"
        dialog.accept()
    
    save_button = QPushButton("Сохранить")
    save_button.clicked.connect(on_save)
    layout.addWidget(save_button)
    
    dialog.setLayout(layout)
    
    if dialog.exec_() == QDialog.Accepted:
        return result
    return None

def message_ui(message: str, mtype: str = "info"):
    """
    Отображает сообщение пользователю в зависимости от типа.

    Параметры:
    message (str): Текст сообщения.
    mtype (str): Тип сообщения. Допустимые значения: 'info', 'warning', 'error'. По умолчанию 'info'.
    """
    app = ensure_qapp()
    mtype = mtype.lower()
    
    if mtype == 'error':
        QMessageBox.critical(None, "Ошибка", message)
    elif mtype == 'warning':
        QMessageBox.warning(None, "Внимание", message)
    else:
        QMessageBox.information(None, "Информация", message)

def login_ui(title: str = "Вход в систему"):
    """
    Отображает интерфейс для ввода логина и пароля.
    Возвращает кортеж (логин, пароль) или None, если операция отменена.
    """
    app = ensure_qapp()
    width = 330
    height = 100
    dialog = QDialog()
    dialog.setWindowTitle(title)
    dialog.resize(width, height) 
    layout = QVBoxLayout()
    username_label = QLabel("Логин:")
    username_line = QLineEdit()
    layout.addWidget(username_label)
    layout.addWidget(username_line)
    # Проверка переменной окружения 'DOMAIN_USERNAME'
    domain_username = os.getenv('DOMAIN_USERNAME', '').strip()
    if domain_username:
        username_line.setText(domain_username)
    password_label = QLabel("Пароль:")
    password_line = QLineEdit()
    password_line.setEchoMode(QLineEdit.Password)  # Скрывает пароль
    # Проверка переменной окружения 'DOMAIN_PASSWORD'
    domain_pass = os.getenv('DOMAIN_PASSWORD', '').strip()
    if domain_pass:
        password_line.setText(domain_pass)  
    layout.addWidget(password_label)
    layout.addWidget(password_line)  
    result = None
    
    def on_login():
        nonlocal result
        username = username_line.text().strip()
        password = password_line.text().strip()
        if not username or not password:
            QMessageBox.critical(dialog, "Ошибка", "Введите логин и пароль.")
            return
        result = (username, password)
        dialog.accept()
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(on_login)
    layout.addWidget(ok_button)
    dialog.setLayout(layout) 
    if dialog.exec_() == QDialog.Accepted:
        return result
    return None

def show_yes_no_dialog(title="Подтверждение", message="Выберите действие:"):
    """
    Создает диалоговое окно с кнопками 'Да' и 'Нет' используя PyQt5.
    
    Параметры:
    title (str): Заголовок окна.
    message (str): Текст сообщения в окне.
    
    Возвращает:
    bool: True, если выбрана кнопка 'Да'; False, если выбрана 'Нет'.
    """
    # app = QApplication.instance()
    
    # if app is None:
    #     app = QApplication(sys.argv)  # Инициализируем QApplication, если не существует
    app = ensure_qapp()
    dialog = QDialog()
    dialog.setWindowTitle(title)
    
    layout = QVBoxLayout()  # Основной вертикальный layout
    
    message_label = QLabel(message)  # Метка для сообщения
    layout.addWidget(message_label)
    
    button_layout = QHBoxLayout()  # Горизонтальный layout для кнопок
    
    yes_button = QPushButton("Да")
    no_button = QPushButton("Нет")
    
    def on_yes():
        dialog.done(1)  # Устанавливаем результат как 1 для 'Да'
    
    def on_no():
        dialog.done(0)  # Устанавливаем результат как 0 для 'Нет'
    
    yes_button.clicked.connect(on_yes)  # Подключаем слот
    no_button.clicked.connect(on_no)    # Подключаем слот
    
    button_layout.addWidget(yes_button)
    button_layout.addWidget(no_button)
    
    layout.addLayout(button_layout)  # Добавляем layout кнопок в основной layout
    dialog.setLayout(layout)
    
    result = dialog.exec_()  # Показываем диалог и ждём результата
    return result == 1  # Возвращаем True, если результат 1 (Да), иначе False

def show_radio_button_dialog(items: list, title="Выберите вариант", return_index=False):
    """
    Создает диалоговое окно с радиокнопками на основе списка элементов используя PyQt5.
    
    Параметры:
    items (list): Список элементов для отображения как радиокнопки.
    title (str): Заголовок окна.
    return_index (bool): Если True, возвращает индекс выбранного элемента; иначе, возвращает сам элемент.
    
    Возвращает:
    str или int или None: Выбранный элемент, его индекс или None, если не выбрано.
    """
    if not items:  # Проверяем, что список не пуст
        print("Список элементов пуст.")
        return None
    
    # app = QApplication.instance()
    # if app is None:
    #     app = QApplication(sys.argv)  # Инициализируем QApplication, если не существует
    app = ensure_qapp()
    dialog = QDialog()
    dialog.setWindowTitle(title)
    
    layout = QVBoxLayout()  # Основной вертикальный layout
    
    message_label = QLabel("Выберите один вариант:")  # Метка для сообщения
    layout.addWidget(message_label)
    
    button_group = QButtonGroup()  # Группа для радиокнопок
    
    for index, item in enumerate(items):
        radio = QRadioButton(item)
        button_group.addButton(radio, index)  # Добавляем кнопку в группу с ID = index
        layout.addWidget(radio)  # Добавляем в layout
    
    result = None  # Инициализируем результат
    
    def on_ok():
        nonlocal result
        selected_id = button_group.checkedId()  # Получаем ID выбранной кнопки
        if selected_id != -1:  # Если что-то выбрано
            if return_index:
                result = selected_id  # Возвращаем индекс
            else:
                result = items[selected_id]  # Возвращаем элемент
        dialog.accept()  # Закрываем диалог
    
    ok_button = QPushButton("OK")
    ok_button.clicked.connect(on_ok)  # Подключаем слот
    layout.addWidget(ok_button)  # Добавляем кнопку OK
    
    dialog.setLayout(layout)
    
    if dialog.exec_() == QDialog.Accepted and result is not None:
        return result  # Возвращаем результат, если диалог принят
    return None  # Если не выбрано или диалог отменён

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Авторизация")
        self.setModal(True)

        layout = QFormLayout()
        self.login_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addRow("Логин:", self.login_input)
        layout.addRow("Пароль:", self.password_input)
        # Проверка переменной окружения 'DOMAIN_USERNAME'
        domain_username = os.getenv('DOMAIN_USERNAME', '').strip()
        if domain_username:
            self.login_input.setText(domain_username)
        # Проверка переменной окружения 'DOMAIN_USERNAME'
        domain_pass = os.getenv('DOMAIN_PASSWORD', '').strip()
        if domain_pass:
            self.password_input.setText(domain_pass)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_credentials(self):
        return self.login_input.text(), self.password_input.text()


# Пример использования (аналогично оригиналу)
if __name__ == "__main__":
    import pandas as pd
    from pathlib import Path
    # # Пример датафрейма
    # df = pd.DataFrame({
    #     'Name': ['Alice', 'Bob', 'Charlie'],
    #     'Age': [25, 30, 35]
    # })
    
    # app = ensure_qapp()  # Инициализируем QApplication
    # save_path = select_save_file(ext="*.xls*")
    
    # if save_path:
    #     df.to_excel(save_path, index=False)
    #     message_ui(f"Файл сохранен: {save_path}")
    # else:
    #     print("Операция сохранения отменена.")
    
    input_str = '//pr.rt.ru/FSPR/РУЗ/Общие_вопросы_ЦК/Обучение/Python_проекты/автоматизация_дзо/Test/Модель КПЭ.xlsx'
    input_str = '/mnt/dfs/РУЗ/Общие_вопросы_ЦК/Обучение/Python_проекты/автоматизация_дзо/Test/Модель КПЭ.xlsx'
    input_str = select_file()
    if input_str:
        folder_path = Path(input_str).parent
        # print(folder_path)
        test_df = pd.read_excel(input_str, sheet_name='Медицина КПЭ GM2', header=2)
        print(test_df)
        OUT_FILE =  folder_path / 'test.xlsx'
        test_df.to_excel(OUT_FILE, index=False)
    # sys.exit(app.exec_())  # Запускаем основной цикл, если нужно

    # response = show_yes_no_dialog(title="Вопрос", message="Согласны ли вы с действием?")
    # print(f"Выбранный ответ: {'Да' if response else 'Нет'}")
    # print(login_ui())

    # item_list = ["Опция 1", "Опция 2", "Опция 3"]
    # selected = show_radio_button_dialog(items=item_list, title="Выбор опции", return_index=True)
    # if selected is not None:
    #     print(f"Выбранный индекс: {selected}")
    # else:
    #     print("Ничего не выбрано.")

    pass
