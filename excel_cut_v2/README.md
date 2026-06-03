```markdown
# Обрезка Excel/ODS файлов — Быстрый старт и инструкция

## 🚀 Быстрый старт

### Установка
```bash
# Клонировать или скачать проект
cd excel_cut

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Установить зависимости
pip install pandas openpyxl odfpy calamine ezodf
# Для GUI дополнительно:
pip install PySide6
```

### Первый запуск
```bash
# Консольная версия
python cut_files.py

# Графический интерфейс
python main.py
```

**По умолчанию**:
- Ищет файлы в папке `./data`.
- Сохраняет результат в `./data_cut`.
- Обрезает до 50 строк на лист.
- Конвертирует всё в `.xlsx`.

---

## 📋 Подробная инструкция

### Структура проекта
```
excel_cut/
├── core/
│   ├── __init__.py
│   ├── processor.py   # CutFilesProcessor
│   └── worker.py      # CutFilesWorker
├── ui/
│   ├── __init__.py
│   ├── main_window.py # MainWindow
│   └── widgets.py     # ConfigWidget, ProgressWidget, LogWidget
├── cut_files.py       # точка входа для консоли
└── main.py            # точка входа для GUI
```

---

### Способы запуска

#### 1. Консольный режим (`cut_files.py`)

| Команда | Описание |
|---------|----------|
| `python cut_files.py` | Запуск с параметрами по умолчанию |
| `python cut_files.py --source my_data` | Указать исходную папку |
| `python cut_files.py --rows 100` | Обрезать до 100 строк |
| `python cut_files.py --output /path/to/output` | Указать выходную папку |
| `python cut_files.py --workers 4` | 4 потока |
| `python cut_files.py --preserve-formatting` | Сохранить форматирование |
| `python cut_files.py --config my_config.json` | Загрузить конфиг из JSON |

**Приоритет параметров**: CLI > JSON > значения по умолчанию.

#### 2. Графический режим (`main.py`)

```bash
python main.py
```

**Вкладки интерфейса**:

| Вкладка | Назначение |
|---------|------------|
| Конфигурация | Настройка всех параметров, загрузка/сохранение JSON |
| Прогресс | Таблица обработанных файлов, прогресс-бар |
| Логи | Вывод сообщений в реальном времени |

---

### Конфигурация (config.json)

```json
{
    "source_folder": "data",
    "output_folder": "",
    "rows_to_keep": 50,
    "preserve_formatting": false,
    "max_workers": 1,
    "log_level": "INFO",
    "log_file": "logs/cut_files.log",
    "stats_file": "reports/processing_stats.xlsx"
}
```

| Параметр | Тип | Описание |
|----------|-----|----------|
| `source_folder` | строка | Путь к исходной папке (относительный или абсолютный) |
| `output_folder` | строка | Путь к выходной папке. Если пусто — `source_folder + "_cut"` |
| `rows_to_keep` | число | Количество сохраняемых строк. `0` — без обрезки |
| `preserve_formatting` | bool | Сохранять форматирование (только `.xlsx`/`.xlsm`) |
| `max_workers` | число | Количество потоков. `1` — последовательно |
| `log_level` | строка | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `log_file` | строка | Путь к файлу лога |
| `stats_file` | строка | Путь к файлу отчёта Excel |

---

### Поддерживаемые форматы

| Расширение | Чтение | Сохранение форматирования | Примечание |
|------------|--------|---------------------------|------------|
| `.xlsx` | ✅ | ✅ | |
| `.xlsm` | ✅ | ✅ | макросы не сохраняются |
| `.xlsb` | ✅ | ❌ | конвертируется в `.xlsx` |
| `.ods` | ✅ | ❌ | конвертируется в `.xlsx` |

---

### Отчёт статистики

После обработки создаётся Excel-файл с временной меткой.

**Колонки отчёта**:
| Колонка | Описание |
|---------|----------|
| `file_name` | Имя файла |
| `source_path` | Полный исходный путь |
| `status` | `success` или `error` |
| `error_message` | Текст ошибки (если есть) |
| `original_rows` | Строк до обрезки |
| `sheets_count` | Количество листов |
| `output_path` | Полный выходной путь |
| `rows_saved` | Строк после обрезки |
| `processing_time_sec` | Время обработки в секундах |

**Итоговая строка** содержит суммы по всем файлам.

---

### Особенности

#### Сохранение форматирования
- Работает только для `.xlsx` и `.xlsm`.
- Реализовано через удаление строк ниже лимита в оригинальном файле.
- При ошибке — fallback на сохранение без форматирования.

#### Многопоточность
- `max_workers > 1` включает параллельную обработку.
- Эффективно для большого количества файлов.
- Потокобезопасность обеспечена через отдельные чтения/записи.

#### Логирование
- Одновременно в консоль и файл.
- Папка для логов создаётся автоматически.
- Уровень настраивается в конфиге.

---

### Примеры использования

#### Обрезать все файлы до 100 строк
```bash
python cut_files.py --source ./my_excel_files --rows 100
```

#### Только конвертировать `.ods` в `.xlsx` без обрезки
```bash
python cut_files.py --source ./ods_files --rows 0
```

#### Обработка с сохранением форматирования в 4 потока
```bash
python cut_files.py --source ./data --preserve-formatting --workers 4
```

#### GUI с автоматической загрузкой конфига
```bash
python main.py --config production.json
```

---

### Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError: No module named 'pandas'` | `pip install pandas openpyxl odfpy calamine` |
| `Cannot save file into a non-existent directory` | Проверить права на запись в выходную папку |
| `Ошибка чтения ODS` | Установить `odfpy`: `pip install odfpy` |
| Форматирование не сохраняется | Убедиться, что файл `.xlsx` или `.xlsm` |
| GUI не запускается | `pip install PySide6` |

---

### Зависимости

```
pandas>=1.5.0
openpyxl>=3.0.0
odfpy>=1.4.0
calamine>=0.1.0
ezodf>=0.3.0
PySide6>=6.5.0  # только для GUI
pytest>=7.0.0   # только для тестов
pytest-qt>=4.2.0  # только для тестов GUI
```
```
