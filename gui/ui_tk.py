import tkinter as tk
from tkinter import filedialog, messagebox
'''
в модуль ui входят функции:
input_ui                    Отображает интерфейс для ввода названия
select_folder               Открывает диалог для выбора директории.
select_file                 Открывает диалог для выбора файла.
path_out_ui                 Отображает интерфейс для выбора названия файла и папки сохранения.
message_ui                  Отображает сообщение пользователю в зависимости от типа.
login_ui                    Отображает интерфейс для ввода логина и пароля
select_save_file            Открывает диалог для выбора файла.
show_yes_no_dialog          Создает диалоговое окно с кнопками 'Да' и 'Нет'.
show_radio_button_dialog    Создает диалоговое окно с радиокнопками на основе списка элементов.
'''
def input_ui(title:str = "Выбор названия", messange: str = "Укажите название", ext: str = ""):
    """
    Отображает интерфейс для ввода названия.
    Возвращает введённое название с расширением или None, если отмена.

    Параметры:
    messange (str): Текст для метки.
    ext (str): Расширение для добавления к названию.
    """
    def _finish():
        str_name = str_name_var.get()
        if not str_name:
            tk.messagebox.showerror("Ошибка", messange)
            return None  # Возвращаем None, если пусто
        return f"{str_name}{ext}"  # Возвращаем полный путь
    
    root = tk.Tk()
    root.title(title)
    root.lift()  # Поднимаем окно на передний план
    root.attributes('-topmost', 1)  # Делаем окно самым верхним
    root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
    root.update_idletasks()
    
    str_name_var = tk.StringVar()
    
    # Метки и поле ввода
    tk.Label(root, text=f"{messange}:").grid(row=0, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=str_name_var).grid(row=0, column=1, padx=10, pady=10)
    if ext:
        tk.Label(root, text=f"({ext})").grid(row=0, column=2, padx=10, pady=10)
    
    result = None  # Переменная для результата
    
    def _save():
        nonlocal result  # Используем nonlocal для изменения переменной
        result_var = _finish()
        if result_var is not None:
            result = result_var  # Устанавливаем результат
            root.quit()  # Завершаем
    
    tk.Button(root, text="ОК", command=_save).grid(row=1, column=1, padx=10, pady=20)
    
    # Обработка закрытия окна
    def on_closing():
        nonlocal result
        result = None  # Устанавливаем None, если окно закрыто
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)  # Вызывать on_closing при закрытии
    root.mainloop()
    
    return result  # Возвращаем результат после mainloop

def select_folder(title: str = "Выберите каталог", initial_dir: str = ""):
    """
    Открывает диалог для выбора директории.

    Параметры:
    title (str): Заголовок диалога.
    initial_dir (str): Начальная директория (опционально).

    Возвращает:
    str: Путь к выбранной директории или None, если отмена.
    """
    try:
        root = tk.Tk()
        root.withdraw()  # Скрываем окно
        # root.lift()  # Поднимаем окно на передний план
        # root.attributes('-topmost', 1)  # Делаем окно самым верхним
        # root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
        # root.update_idletasks()
        source_folder = tk.filedialog.askdirectory(
            title=title,
            initialdir=initial_dir  # Начальная директория, если указана
        )
        root.destroy()  # Чистим за собой
        return source_folder if source_folder else None  # Возвращаем None, если пусто
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        return None

def select_file(title: str = "Выберите файл", ext: str = "*.xls*"):
    """
    Открывает диалог для выбора файла.

    Параметры:
    title (str): Заголовок диалога.
    ext (str): Фильтр для расширений файлов (например, "*.xlsx").

    Возвращает:
    str: Путь к выбранному файлу или None, если отмена.
    """
    try:
        root = tk.Tk()
        root.withdraw()  # Скрываем окно
        source_file = filedialog.askopenfilename(
            title=title,
            filetypes=[("Выбранные файлы", ext)]  # Более точный заголовок для фильтра
        )
        root.destroy()  # Чистим за собой
        return source_file if source_file else None  # Возвращаем None, если пусто
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
    
    def select_directory():
        directory = filedialog.askdirectory(title=title)
        if directory:
            directory_var.set(directory)
    
    def finish_and_save():
        file_name = file_name_var.get()
        directory = directory_var.get()
        
        if not file_name or not directory:
            messagebox.showerror("Ошибка", "Укажите название файла и выберите папку.")
            return None
        
        return f"{directory}/{file_name}.{ext}"
    
    root = tk.Tk()
    root.title(title)
    root.lift()  # Поднимаем окно на передний план
    root.attributes('-topmost', 1)  # Делаем окно самым верхним
    root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
    root.update_idletasks()
    
    file_name_var = tk.StringVar()
    directory_var = tk.StringVar()
    
    tk.Label(root, text="Название файла:").grid(row=1, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=file_name_var).grid(row=1, column=1, padx=10, pady=10)
    tk.Label(root, text=f".{ext}").grid(row=1, column=2, padx=10, pady=10)
    
    tk.Label(root, text="Каталог для сохранения:").grid(row=0, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=directory_var, state='readonly').grid(row=0, column=1, padx=10, pady=10)
    tk.Button(root, text="Выбрать папку", command=select_directory).grid(row=0, column=2, padx=10, pady=10)
    
    result = None  # Переменная для результата
    
    def on_save():
        nonlocal result
        result_value = finish_and_save()
        if result_value is not None:
            result = result_value
            root.quit()
    
    tk.Button(root, text="Сохранить", command=on_save).grid(row=2, column=1, padx=10, pady=20)
    
    def on_closing():
        nonlocal result
        result = None
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    
    return result

def message_ui(message: str, mtype: str = "info"):
    """
    Отображает сообщение пользователю в зависимости от типа.

    Параметры:
    message (str): Текст сообщения.
    mtype (str): Тип сообщения. Допустимые значения: 'info', 'warning', 'error'. По умолчанию 'info'.
    
    Возвращает:
    None, но отображает диалоговое окно.
    """
    mtype = mtype.lower()  # Приводим к нижнему регистру
    
    # Проверяем, что mtype допустим
    if mtype not in ['info', 'warning', 'error']:
        mtype = 'info'  # По умолчанию, если неверно
        print(f"Неверный тип сообщения '{mtype}'. Использую 'info'.")
    
    try:
        root = tk.Tk()  # Создаём временное корневое окно (если не существует)
        root.withdraw()  # Скрываем основное окно, чтобы оно не отображалось
        
        if mtype == 'error':
            messagebox.showerror("Ошибка", message)
        elif mtype == 'warning':
            messagebox.showwarning("Внимание", message)
        else:
            messagebox.showinfo("Информация", message)
        
        root.destroy()  # Закрываем корневое окно после показа сообщения
    except Exception as e:
        print(f"Ошибка Tkinter: {e}. Невозможно отобразить сообщение.")

def login_ui(title: str = "Вход в систему"):
    """
    Отображает интерфейс для ввода логина и пароля.
    Возвращает кортеж (логин, пароль) или None, если операция отменена.

    Параметры:
    title (str): Заголовок окна.
    """
    
    def on_login():
        username = username_var.get()
        password = password_var.get()
        
        if not username or not password:
            messagebox.showerror("Ошибка", "Введите логин и пароль.")
            return None  # Не закрываем, если ошибка
        
        root.quit()  # Завершаем
        return username, password  # Возвращаем значения
    
    root = tk.Tk()
    root.title(title)
    root.lift()  # Поднимаем окно на передний план
    root.attributes('-topmost', 1)  # Делаем окно самым верхним
    root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
    root.update_idletasks()
    
    username_var = tk.StringVar()
    password_var = tk.StringVar()
    
    tk.Label(root, text="Логин:").grid(row=0, column=0, padx=20, pady=10)
    tk.Entry(root, textvariable=username_var).grid(row=0, column=1, padx=20, pady=10)
    
    tk.Label(root, text="Пароль:").grid(row=1, column=0, padx=20, pady=10)
    tk.Entry(root, textvariable=password_var, show="*").grid(row=1, column=1, padx=20, pady=10)
    
    result = None  # Переменная для результата
    
    def on_save():
        nonlocal result
        result_value = on_login()
        if result_value is not None:
            result = result_value
            root.destroy()
    
    tk.Button(root, text="OK", command=on_save).grid(row=2, column=1, padx=10, pady=20)
    
    def on_closing():
        nonlocal result
        result = None
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    
    return result       

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
    try:
        root = tk.Tk()
        root.withdraw()  # Скрываем основное окно Tkinter, чтобы оно не отображалось
        root.update()    # Обновляем, чтобы избежать проблем с фокусом
        
        # Разбираем ext и преобразуем в формат, подходящий для filedialog
        # ext ожидается в формате "Описание1 (шаблон1);;Описание2 (шаблон2)"
        if ext:
            filetypes = []
            for part in ext.split(";;"):
                if part.strip():
                    description, patterns = part.split("(", 1)  # Разделяем описание и шаблоны
                    description = description.strip().strip('"')  # Убираем лишние символы
                    patterns = patterns.strip(")").strip()  # Убираем скобки
                    filetypes.append((description, patterns))  # Добавляем как кортеж
        else:
            filetypes = []  # Пустой список, если ext не указан
        
        # Вызываем диалог asksaveasfilename
        file_path = filedialog.asksaveasfilename(
            title=title,
            filetypes=filetypes,  # Передаём отформатированный список
            defaultextension=""   # Не добавляем расширение автоматически
        )
        
        root.destroy()  # Закрываем корневое окно
        return file_path if file_path else None  # Возвращаем путь, если выбран, иначе None
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        return None
    
def show_yes_no_dialog(title="Подтверждение", message="Выберите действие:"):
    """
    Создает диалоговое окно с кнопками 'Да' и 'Нет'.
    
    Параметры:
    title (str): Заголовок окна.
    message (str): Текст сообщения в окне.
    
    Возвращает:
    bool: True, если выбрана кнопка 'Да'; False, если выбрана 'Нет'.
    """
    root = tk.Tk()
    root.title(title)
    root.withdraw()  # Скрываем окно изначально
    root.lift()  # Поднимаем окно на передний план
    root.attributes('-topmost', 1)  # Делаем окно самым верхним
    root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
    root.update_idletasks()  # Обновляем задачи
    
    result = False  # Инициализируем результат
    
    def on_yes():
        nonlocal result
        result = True  # Устанавливаем True для 'Да'
        root.destroy()  # Закрываем окно
    
    def on_no():
        nonlocal result
        result = False  # Устанавливаем False для 'Нет'
        root.destroy()  # Закрываем окно
    
    # Добавляем элементы в окно
    label = tk.Label(root, text=message, padx=20, pady=10)
    label.pack()
    
    yes_button = tk.Button(root, text="Да", command=on_yes, width=10)
    yes_button.pack(side=tk.LEFT, padx=20, pady=10)
    
    no_button = tk.Button(root, text="Нет", command=on_no, width=10)
    no_button.pack(side=tk.RIGHT, padx=20, pady=10)
    
    root.deiconify()  # Показываем окно
    root.mainloop()  # Запускаем цикл событий
    return result  # Возвращаем результат после закрытия

def show_radio_button_dialog(items: list, title="Выберите вариант", return_index=False):
    """
    Создает диалоговое окно с радиокнопками на основе списка элементов.
    
    Параметры:
    items (list): Список элементов для отображения как радиокнопки.
    title (str): Заголовок окна.
    return_index (bool): Если True, возвращает индекс выбранного элемента; иначе, возвращает сам элемент.
    
    Возвращает:
    str или int или None: Выбранный элемент, его индекс или None, если не выбрано.
    """
    if not items:  # Проверяем, что список не пуст
        messagebox.showerror("Ошибка", "Список элементов пуст.")
        return None
    
    root = tk.Tk()
    root.title(title)
    root.lift()  # Поднимаем окно на передний план
    root.attributes('-topmost', 1)  # Делаем окно самым верхним
    root.after_idle(root.attributes, '-topmost', 0)  # Снимаем флаг после
    root.update_idletasks()
    
    selected_var = tk.IntVar(value=0)  # Переменная для хранения индекса выбранного элемента
    
    label = tk.Label(root, text="Выберите один вариант:", padx=10, pady=10)
    label.pack()
    
    for index, item in enumerate(items):
        radio = tk.Radiobutton(root, text=item, variable=selected_var, value=index)
        radio.pack(anchor=tk.W, padx=20, pady=5)  # Располагаем радиокнопки
    
    result = None  # Инициализируем результат
    
    def on_ok():
        nonlocal result
        selected_index = selected_var.get()  # Получаем выбранный индекс
        if return_index:
            result = selected_index  # Возвращаем индекс
        else:
            result = items[selected_index]  # Возвращаем элемент
        root.destroy()  # Закрываем окно
    
    ok_button = tk.Button(root, text="OK", command=on_ok)
    ok_button.pack(pady=20)
    
    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())  # Обработка закрытия окна
    root.mainloop()  # Запускаем цикл событий
    return result  # Возвращаем результат после закрытия


# Примеры использования `162`
if __name__ == "__main__":
    # # input_ui
    # print(input_ui(messange='Введите что-нибудь',title='Заголовок'))
    # # select_folder
    # print(select_folder('Выберите папку с исходными данными'))
    # # select_file
    print(select_file('Выберите файл с исходными данными'))
    # # path_out_ui - устарело лучше испльзовать select_save_file
    # print(path_out_ui('Файл результата'))
    # # message_ui
    # message_ui('Простое сообщение')
    # message_ui('ПРЕДУПРЕЖДЕНИЕ!', 'Warning')
    # message_ui(mtype='error', message='Сообщение об ошибке')
    # # login_ui
    # secret = login_ui('Укажите номер карты и пин код')
    # if secret:
    #     login, password = secret
    #     print(f'login = {login}, password = {password}')
    #     secret, login, password = None, None, None
    # else:
    #     print('Пользователь не ввел логин/пароль')
    # select_save_file
    save_path = select_save_file(ext='Excel Files (*.xls *.xlsx *.xlsm *.xlsb)')
    # save_path = select_save_file(ext='Excel Files (*.xlsx)')
    # save_path = select_save_file(ext='Excel Files (*.xlsx *.xlsm *.xlsb)')
    print(save_path)
    # #  show_yes_no_dialog
    # print(show_yes_no_dialog(title="Проверка", message="Нажмите любую кнопку!"))
    # # def show_radio_button_dialog
    # item_list = ["Опция 1", "Опция 2", "Опция 3", "Опция 4", "Опция 5", "Опция 6"]
    # selected = show_radio_button_dialog(items=item_list, title="Выбор опции", return_index=True)
    # if selected is not None:
    #     print(f"Выбранный индекс: {selected}")
    # else:
    #     print("Ничего не выбрано.")   

    # import pandas as pd
    # # Пример датафрейма
    # df = pd.DataFrame({
    #     'Name': ['Alice', 'Bob', 'Charlie'],
    #     'Age': [25, 30, 35]
    # })
    
    # Вызов функции
    # save_path = path_out_ui()
    # save_path = select_save_file(ext='*.xlx*')
    # save_path = select_save_file(ext='Excel Files (*.xls *.xlsx *.xlsm *.xlsb)')
    # if save_path:
    #     # print(f"Путь к файлу сохранения: {save_path}")
    #     # Сохранение датафрейма
    #     df.to_excel(save_path, index=False)
    #     message_ui(f"Файл сохранен: {save_path}")
    # else:
    #     print("Операция сохранения отменена.")
    pass
