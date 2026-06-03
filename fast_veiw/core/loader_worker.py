# core/loader_worker.py

import sys
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtCore import QThread, Signal

from core.models import SheetInfo, SheetState
from core.task_queue import TaskQueue, Task, TaskType
from core.excel_reader import ExcelReader
from core.config import AppConfig


logger = logging.getLogger(__name__)


def get_deep_size(obj: Any, seen: Optional[set] = None) -> int:
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(get_deep_size(k, seen) + get_deep_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(get_deep_size(i, seen) for i in obj)
    return size


class LoaderWorker(QThread):
    rows_loaded = Signal(str, list, int)
    metrics_updated = Signal(str, int, int, bool)
    preview_done = Signal(str)
    full_done = Signal(str)
    error_occurred = Signal(str, str)
    memory_limit_exceeded = Signal()
    loading_started = Signal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._queue = TaskQueue()
        self._stop_event = threading.Event()
        self._file_path: Optional[Path] = None
        self._sheets: Dict[str, SheetInfo] = {}
        self._current_task: Optional[Task] = None
        self._active_sheet: Optional[str] = None
        self._paused_task: Optional[Task] = None
        self._paused_progress: Dict[str, Tuple[int, int, int]] = {}

    def set_file(self, file_path: Path, sheets: Dict[str, SheetInfo]) -> None:
        self._file_path = file_path
        self._sheets = sheets
        self._queue.add_tasks_for_new_file(
            list(sheets.keys()),
            next(name for name, info in sheets.items() if info.is_active)
        )
        logger.info(f"Файл открыт: {file_path}, листов: {len(sheets)}")

    def set_active_sheet(self, sheet_name: str) -> None:
        if self._active_sheet == sheet_name:
            return

        logger.debug(f"Смена активного листа: {self._active_sheet} -> {sheet_name}")

        if self._current_task and self.isRunning():
            self._stop_event.set()
            info = self._sheets[self._current_task.sheet_name]
            self._paused_progress[info.name] = (
                info.loaded_rows, info.effective_rows, info.filled_rows
            )
            if self._current_task.type == TaskType.LOAD_FULL:
                self._paused_task = self._current_task
            info.state = SheetState.PAUSED
            logger.debug(f"Лист {info.name} поставлен на паузу, прогресс: {info.loaded_rows} строк")
            self._current_task = None

        self._active_sheet = sheet_name

        if sheet_name in self._paused_progress:
            loaded, eff, filled = self._paused_progress[sheet_name]
            info = self._sheets[sheet_name]
            info.loaded_rows = loaded
            info.effective_rows = eff
            info.filled_rows = filled
            logger.debug(f"Восстановлен прогресс листа {sheet_name}: {loaded} строк")

        task = self._queue.on_sheet_changed(sheet_name)
        if task:
            self._queue.add_task(task)
            logger.debug(f"Добавлена задача для листа {sheet_name}: {task.type}")

    def request_more_rows(self, sheet_name: str, start_row: int, count: int) -> None:
        info = self._sheets.get(sheet_name)
        if not info:
            return
        if info.state in (SheetState.PREVIEW_LOADED, SheetState.FULL_LOADING, SheetState.PAUSED):
            task = Task(TaskType.LOAD_MORE, sheet_name, priority=0, start_row=start_row, count=count)
            self._queue.add_task(task)
            logger.debug(f"Запрос дозагрузки: {sheet_name}, строки {start_row}+{count}")

    def stop_loading(self) -> None:
        logger.debug("Остановка загрузки")
        self._stop_event.set()
        self._queue.clear()

    def _load_more(self, reader: ExcelReader, info: SheetInfo, start_row: int, count: int) -> None:
        if self._stop_event.is_set():
            return

        excel_start_row = start_row + 1

        rows, eff, filled = self._read_with_interrupt_check(reader, info, excel_start_row, count)

        if not rows:
            return

        needed_len = start_row + len(rows)
        if len(info.data_cache) < needed_len:
            info.data_cache.extend([()] * (needed_len - len(info.data_cache)))
        for i, row in enumerate(rows):
            idx = start_row + i
            if idx < len(info.data_cache):
                info.data_cache[idx] = row

        info.effective_rows += eff
        if filled > info.filled_rows:
            info.filled_rows = filled
        info.loaded_rows = max(info.loaded_rows, start_row + len(rows))

        self.rows_loaded.emit(info.name, rows, start_row)
        self.metrics_updated.emit(info.name, info.effective_rows, info.filled_rows, False)

    def _all_sheets_done(self) -> bool:
        return all(
            info.state in (SheetState.FULL_LOADED, SheetState.ERROR)
            for info in self._sheets.values()
        )

    def _check_memory_limit(self) -> bool:
        total = 0
        for info in self._sheets.values():
            total += get_deep_size(info.data_cache)
        limit_bytes = self.config.CACHE_MEMORY_LIMIT_MB * 1024 * 1024
        if total > limit_bytes:
            logger.warning(f"Превышен лимит памяти кэша: {total / (1024*1024):.1f} МБ > {self.config.CACHE_MEMORY_LIMIT_MB} МБ")
            self.memory_limit_exceeded.emit()
            self._clear_inactive_caches()
            return True
        return False

    def run(self) -> None:
        logger.info("Запуск воркера загрузки")
        self._stop_event.clear()
        with ExcelReader(self._file_path) as reader:
            while not self._stop_event.is_set():
                task = self._queue.pop_next()
                if task is None:
                    self.msleep(50)
                    if self._queue.is_empty() and self._all_sheets_done():
                        logger.info("Все листы загружены, воркер завершается")
                        break
                    continue

                self._stop_event.clear()
                self._current_task = task
                sheet_info = self._sheets[task.sheet_name]

                logger.debug(f"Выполнение задачи: {task.type} для листа {task.sheet_name}")

                try:
                    if task.type == TaskType.LOAD_PREVIEW:
                        self._load_preview(reader, sheet_info)
                    elif task.type == TaskType.LOAD_FULL:
                        self._load_full(reader, sheet_info)
                    elif task.type == TaskType.LOAD_MORE:
                        self._load_more(reader, sheet_info, task.start_row, task.count)
                except Exception as e:
                    logger.error(f"Ошибка загрузки листа {task.sheet_name}: {e}", exc_info=True)
                    sheet_info.state = SheetState.ERROR
                    self.error_occurred.emit(task.sheet_name, str(e))
                finally:
                    self._current_task = None

                # Сбрасываем флаг, если он был установлен во время задачи
                if self._stop_event.is_set():
                    self._stop_event.clear()

                if self._check_memory_limit():
                    continue

        self._current_task = None
        logger.info("Воркер остановлен")

    def _load_preview(self, reader: ExcelReader, info: SheetInfo) -> None:
        logger.debug(f"Загрузка превью листа {info.name}, строк: {self.config.PREVIEW_ROWS}")
        self.loading_started.emit(info.name)
        info.state = SheetState.PREVIEW_LOADING

        rows, eff, filled = self._read_with_interrupt_check(reader, info, 1, self.config.PREVIEW_ROWS)

        info.data_cache = rows
        info.effective_rows = eff
        info.filled_rows = filled
        info.loaded_rows = len(rows)
        info.state = SheetState.PREVIEW_LOADED

        self.rows_loaded.emit(info.name, rows, 0)
        self.metrics_updated.emit(info.name, eff, filled, False)
        self.preview_done.emit(info.name)

        logger.info(f"Превью листа {info.name} загружено: {len(rows)} строк, эффективных: {eff}, заполненных: {filled}")

        full_task = self._queue.on_preview_loaded(info.name, self.config.LOAD_LIMIT)
        if full_task:
            self._queue.add_task(full_task)

    def _load_full(self, reader: ExcelReader, info: SheetInfo) -> None:
        if self.config.LOAD_LIMIT == -1:
            logger.debug(f"Полная загрузка листа {info.name} отключена (LOAD_LIMIT=-1)")
            info.state = SheetState.PREVIEW_LOADED
            self.metrics_updated.emit(info.name, info.effective_rows, info.filled_rows, True)
            self.full_done.emit(info.name)
            return

        self.loading_started.emit(info.name)
        logger.debug(f"Полная загрузка листа {info.name}, уже загружено: {info.loaded_rows} строк")
        info.state = SheetState.FULL_LOADING

        start_row = info.loaded_rows + 1
        limit = None if self.config.LOAD_LIMIT == 0 else self.config.LOAD_LIMIT - info.loaded_rows

        if limit is not None and limit <= 0:
            info.state = SheetState.FULL_LOADED
            self.metrics_updated.emit(info.name, info.effective_rows, info.filled_rows, True)
            self.full_done.emit(info.name)
            return

        rows, eff, filled = self._read_with_interrupt_check(reader, info, start_row, limit)

        if self._stop_event.is_set():
            # Сохраняем прочитанные строки перед возвратом задачи в очередь
            info.data_cache.extend(rows)
            info.effective_rows += eff
            if filled > info.filled_rows:
                info.filled_rows = filled
            info.loaded_rows += len(rows)
            self._queue.return_task(Task(TaskType.LOAD_FULL, info.name, priority=0))
            logger.debug(f"Полная загрузка листа {info.name} прервана, задача возвращена в очередь, сохранено строк: {len(rows)}")
            return

        # Отправляем данные чанками по 5000 строк
        chunk_size = 10000
        for i in range(0, len(rows), chunk_size):
            if self._stop_event.is_set():
                # Сохраняем оставшиеся строки
                remaining = rows[i:]
                info.data_cache.extend(remaining)
                #info.effective_rows += eff
                if filled > info.filled_rows:
                    info.filled_rows = filled
                info.loaded_rows += len(rows)
                self._queue.return_task(Task(TaskType.LOAD_FULL, info.name, priority=0))
                logger.debug(f"Отправка чанков листа {info.name} прервана, сохранено строк: {len(remaining)}")
                return
            chunk = rows[i:i+chunk_size]
            info.data_cache.extend(chunk)
            self.metrics_updated.emit(info.name, info.effective_rows + eff, max(info.filled_rows, filled), False)

        info.effective_rows += eff
        if filled > info.filled_rows:
            info.filled_rows = filled
        info.loaded_rows += len(rows)

        if not self._stop_event.is_set():
            visible_rows = rows[:filled - start_row + 1] if filled >= start_row else []
            if visible_rows:
                self.rows_loaded.emit(info.name, visible_rows, start_row - 1)
            info.state = SheetState.FULL_LOADED
            self.metrics_updated.emit(info.name, info.effective_rows, info.filled_rows, True)
            self.full_done.emit(info.name)
            logger.info(f"Полная загрузка листа {info.name} завершена: {info.loaded_rows} строк, эффективных: {info.effective_rows}, заполненных: {info.filled_rows}")

            next_task = self._queue.on_full_loaded(info.name)
            if next_task:
                self._queue.add_task(next_task)

    def _read_with_interrupt_check(self, reader: ExcelReader, info: SheetInfo, start_row: int, max_rows: Optional[int]) -> Tuple[List[Tuple], int, int]:
        rows_data: List[Tuple] = []
        effective = 0
        filled = 0

        max_row = None if max_rows is None else start_row + max_rows - 1
        iterator = reader.iter_sheet_rows(info.name, min_row=start_row, max_row=max_row)

        check_interval = 100  # уменьшить с 500 для быстрой реакции
        stop_check = self._stop_event.is_set

        for idx, row in enumerate(iterator, start=start_row):
            if idx % check_interval == 0 and stop_check():
                logger.debug(f"Чтение листа {info.name} прервано на строке {idx}")
                break

            row_tuple = tuple(row)
            rows_data.append(row_tuple)

            if any(cell not in (None, "") for cell in row_tuple):
                effective += 1
                filled = idx

        return rows_data, effective, filled

    def _clear_inactive_caches(self) -> None:
        for name, info in self._sheets.items():
            if name != self._active_sheet:
                if info.data_cache:
                    logger.debug(f"Сброс кэша неактивного листа: {name}, было строк: {len(info.data_cache)}")
                info.data_cache.clear()
                if info.state == SheetState.FULL_LOADING:
                    info.state = SheetState.PREVIEW_LOADED
            else:
                # Для активного листа оставляем только последние PREVIEW_ROWS * 2 строк
                if len(info.data_cache) > self.config.PREVIEW_ROWS * 2:
                    keep_rows = self.config.PREVIEW_ROWS * 2
                    info.data_cache = info.data_cache[-keep_rows:]
                    logger.debug(f"Обрезан кэш активного листа {name} до {keep_rows} строк")

    def iter_sheet_rows(self, sheet_name: str, min_row: int = 1, max_row: Optional[int] = None):
        """
        Возвращает итератор по строкам листа.
        
        Args:
            sheet_name: имя листа
            min_row: начальная строка (с 1)
            max_row: конечная строка (включительно) или None для чтения до конца
            
        Returns:
            итератор кортежей значений ячеек
        """
        sheet = self._workbook[sheet_name]
        return sheet.iter_rows(min_row=min_row, max_row=max_row, values_only=True)                    
