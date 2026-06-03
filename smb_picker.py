import smbclient
from typing import List, Optional
# from PyQt5 import QtWidgets
from PyQt5.QtWidgets import ( QDialog, QVBoxLayout, 
                             QHBoxLayout, QTreeView, QPushButton, QLabel,
                             QLineEdit, QMessageBox, QAbstractItemView)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt
from smb_utils import load_smb_credentials
from gui.ui_qt5 import ensure_qapp

class NetworkFileDialog(QDialog):
    def __init__(
            self,
            server: str,
            current_path: str,
            username: str,
            password: str,
    ):
        super().__init__()
        self.username = username
        self.password = password
        self.current_path = current_path
        self.server = server
        self.selected_file = None
        self.init_ui()
        self.connect_to_share()

    def init_ui(self):
        self.setWindowTitle('Выбор файла на сетевой шаре')
        self.setGeometry(100, 100, 800, 600)

        # Основной макет
        layout = QVBoxLayout(self)  # Используем self для установки макета в диалог

        # Поле текущего пути
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel('Текущий путь:'))
        self.path_edit = QLineEdit()
        self.path_edit.textChanged.connect(self.path_changed)  # Подключаем сигнал
        path_layout.addWidget(self.path_edit)

        self.up_btn = QPushButton('Вверх')
        self.up_btn.clicked.connect(self.go_up)
        path_layout.addWidget(self.up_btn)

        layout.addLayout(path_layout)

        # Дерево файлов
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Имя', 'Размер', 'Тип'])
        self.tree_view.setModel(self.model)
        self.tree_view.doubleClicked.connect(self.item_double_clicked)
        self.tree_view.clicked.connect(self.item_clicked)

         # Устанавливаем ширину столбцов
        self.tree_view.setColumnWidth(0, self.width() - 300)  # Ширина столбца "Имя"
        self.tree_view.setColumnWidth(1, 150)  # Ширина столбца "Размер" (1,5 см)
        self.tree_view.setColumnWidth(2, 150)  # Ширина столбца "Тип" (1,5 см)
        self.tree_view.header().setStretchLastSection(True)  # Растягиваем последний столбец
        # Подключаем сигнал раскрытия папки
        self.tree_view.expanded.connect(self.on_item_expanded)

        self.tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        layout.addWidget(self.tree_view)

        # Кнопки выбора
        button_layout = QHBoxLayout()
        self.select_btn = QPushButton('Выбрать файл')
        self.select_btn.clicked.connect(self.select_file)
        self.select_btn.setEnabled(False)
        button_layout.addWidget(self.select_btn)

        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # Статус бар (используем QLabel вместо QStatusBar)
        self.status_label = QLabel('Введите учетные данные и подключитесь к шаре')
        layout.addWidget(self.status_label)

    def connect_to_share(self):
        username = self.username
        password = self.password
        try:
            # Регистрируем сессию
            smbclient.register_session(self.server, username=username, password=password)
            # Устанавливаем начальный путь
            self.path_edit.setText(self.current_path)
            self.load_directory_contents(self.current_path)
            self.status_label.setText('Успешно подключено к сетевой шаре')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка подключения', f'Не удалось подключиться: {str(e)}')

    def path_changed(self, text):
        """
        Обработчик изменения текста в поле текущего пути.
        Обновляет текущий путь и загружает содержимое новой директории.
        """
        self.current_path = text

    def go_up(self):
        """
        Переход на уровень выше в дереве директорий.
        """
        if self.current_path.count('\\') > 2:
            parts = self.current_path.split('\\')
            new_path = '\\'.join(parts[:-1])
            self.current_path = new_path
            self.path_edit.setText(new_path)
            self.load_directory_contents(new_path)

    def load_directory_contents(self, path, parent_item=None):
        try:
            if parent_item is None:
                # Загрузка корневого уровня
                self.model.removeRows(0, self.model.rowCount())

            entries = smbclient.listdir(path)

            for entry in entries:
                full_path = f"{path}\\{entry}"
                try:
                    stat = smbclient.stat(full_path)

                    item_name = QStandardItem(entry)

                    if stat.st_mode & 0o40000:  # Это папка
                        item_size = QStandardItem('')
                        item_type = QStandardItem('Папка')

                        # Добавляем фиктивный дочерний элемент, чтобы показать стрелку раскрытия
                        dummy_child = QStandardItem('Загрузка...')
                        item_name.appendRow([dummy_child, QStandardItem(''), QStandardItem('')])

                        # Сохраняем полный путь в данных элемента
                        item_name.setData(full_path, Qt.UserRole)

                    else:  # Это файл
                        size_str = self.format_size(stat.st_size)
                        item_size = QStandardItem(size_str)
                        item_type = QStandardItem('Файл')
                        item_name.setData(full_path, Qt.UserRole)

                    if parent_item is None:
                        self.model.appendRow([item_name, item_size, item_type])
                    else:
                        parent_item.appendRow([item_name, item_size, item_type])

                except Exception as e:
                    print(f"Ошибка получения информации о {entry}: {e}")

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить содержимое: {str(e)}')

    def on_item_expanded(self, index):
        """Обработчик раскрытия папки"""
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        if item is None:
            return

        # Получаем путь к папке
        folder_path = item.data(Qt.UserRole)
        if not folder_path:
            return

        # Проверяем, не загружено ли уже содержимое
        if item.rowCount() == 1:
            child = item.child(0, 0)
            if child and child.text() == 'Загрузка...':
                # Удаляем фиктивный элемент и загружаем реальное содержимое
                item.removeRow(0)
                self.load_directory_contents(folder_path, item)

    def item_double_clicked(self, index):
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        if item is None:
            return

        item_name = item.text()
        full_path = item.data(Qt.UserRole)

        if not full_path:
            return

        try:
            stat = smbclient.stat(full_path)
            if stat.st_mode & 0o40000:  # Это папка - переходим в нее
                self.current_path = full_path
                self.path_edit.setText(full_path)
                self.load_directory_contents(full_path)
            else:  # Это файл - выбираем его
                self.selected_file = full_path
                self.accept_selection()

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось получить информацию: {str(e)}')

    def item_clicked(self, index):
        """Обработчик клика по элементу - активирует кнопку выбора для файлов"""
        if not index.isValid():
            self.select_btn.setEnabled(False)
            return

        item = self.model.itemFromIndex(index)
        if item is None:
            self.select_btn.setEnabled(False)
            return

        full_path = item.data(Qt.UserRole)
        if not full_path:
            self.select_btn.setEnabled(False)
            return

        try:
            stat = smbclient.stat(full_path)
            # Активируем кнопку только для файлов, не для папок
            self.select_btn.setEnabled(not (stat.st_mode & 0o40000))
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
            self.select_btn.setEnabled(False)

    def select_file(self):
        selection_model = self.tree_view.selectionModel()
        if selection_model.hasSelection():
            index = selection_model.currentIndex()
            item = self.model.itemFromIndex(index)
            if item:
                full_path = item.data(Qt.UserRole)
                if full_path:
                    try:
                        stat = smbclient.stat(full_path)
                        if not (stat.st_mode & 0o40000):  # Если это файл, а не папка
                            self.selected_file = full_path
                            self.accept_selection()
                        else:
                            QMessageBox.information(self, 'Информация', 'Пожалуйста, выберите файл, а не папку')
                    except Exception as e:
                        QMessageBox.critical(self, 'Ошибка', f'Не удалось получить информацию о файле: {str(e)}')

    def accept_selection(self):
        if self.selected_file:
            self.accept()
            # QMessageBox.information(self, 'Файл выбран', f'Выбран файл: {self.selected_file}')
            # # Здесь можно добавить логику для работы с выбранным файлом
            # print(f"Выбран файл: {self.selected_file}")

    def format_size(self, size_bytes):
        """Форматирование размера файла в читаемый вид"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.2f} {size_names[i]}"

def normalize_path(path: str) -> str:
    if not path or path == ".":
        return ""
    if not path.startswith("\\"):
        path = f"{path}"
    return path.replace("/", "\\")

def parse_smb_path(smb_path: str) -> tuple[str, str, str]:
    """Split UNC-like path (\\server\share\folder) into server/share/start_path."""
    if not smb_path:
        raise ValueError("SMB path must not be empty.")
    cleaned = smb_path.strip()
    cleaned = cleaned.replace("smb://", "", 1) if cleaned.lower().startswith("smb://") else cleaned
    cleaned = cleaned.replace("/", "\\")
    while cleaned.startswith("\\"):
        cleaned = cleaned[1:]
    parts = [part for part in cleaned.split("\\") if part]
    if len(parts) < 2:
        raise ValueError(f"Invalid SMB path '{smb_path}'. Expected format \\\\server\\share\\path.")
    server, share, *rest = parts
    start_path = "" + "\\".join(rest) if rest else ""
    return server, share, normalize_path(start_path)


def select_smb_file(
    smb_path: str,
    username: str,
    password: str,
    close_app: bool = True,
) -> Optional[str]:
    """
    Launch a modal dialog that lets the user pick a file on an SMB share.

    Args:
        smb_path: UNC-style path (e.g. \\\\server\\share\\folder) that sets initial location.
        username: SMB username.
        password: SMB password.

    Returns:
        The absolute path inside the share (e.g. /reports/2024.xlsx) or None if
        the dialog was cancelled.
    """

    server, share, start_path = parse_smb_path(smb_path)
    if start_path:
        current_path = f'\\\\{server}\\{share}\\{start_path}'
    else:
        current_path = f'\\\\{server}\\{share}' 

    # app = QApplication.instance()
    # created_app = False
    # if app is None:
    #     app = QApplication([])
    #     created_app = True
    app = ensure_qapp()

    dialog = NetworkFileDialog(server=server, current_path=current_path, username=username, password=password)

    try:
        result = dialog.selected_file if dialog.exec_() == QDialog.Accepted else None
    finally:
        if close_app:
            app.quit()
    return result


def main():
    # Инициализация логирования (заглушка)
    def init_logging(level):
        pass
    init_logging(level=None)
    secret = load_smb_credentials()
    path = "\\\\pr.rt.ru\\FSPR\\РУЗ\\"
    if secret:
        username, password = secret 
        try:
            selection = select_smb_file(path, username, password)
            print(f"Selected file: {selection}")
        except Exception as exc:
            print(f'Ошибка!\n{exc}')
    else:
        print(f'Необходимо ввести пароль!')    


if __name__ == '__main__':
    main()
