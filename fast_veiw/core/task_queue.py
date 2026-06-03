# core/task_queue.py

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List
from collections import deque


class TaskType(Enum):
    LOAD_PREVIEW = auto()
    LOAD_FULL = auto()
    LOAD_MORE = auto()


@dataclass
class Task:
    type: TaskType
    sheet_name: str
    priority: int
    start_row: int = 0
    count: int = 0

    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return (self.type == other.type and
                self.sheet_name == other.sheet_name and
                self.priority == other.priority)


class TaskQueue:
    def __init__(self):
        self._active_sheet: Optional[str] = None
        self._sheet_order: List[str] = []
        self._queue: deque[Task] = deque()
        self._preview_done: set[str] = set()
        self._full_done: set[str] = set()

    def set_active_sheet(self, sheet_name: str) -> None:
        self._active_sheet = sheet_name

    def set_sheet_order(self, sheet_names: List[str]) -> None:
        self._sheet_order = sheet_names[:]

    def add_task(self, task: Task) -> None:
        self._queue.append(task)

    def _add_preview_task(self, sheet_name: str) -> None:
        priority = 0 if sheet_name == self._active_sheet else 1
        self._queue.append(Task(TaskType.LOAD_PREVIEW, sheet_name, priority))

    def _get_full_priority(self, sheet_name: str) -> int:
        if sheet_name == self._active_sheet:
            return 0
        return 1 + self._sheet_order.index(sheet_name)

    def on_sheet_changed(self, new_active: str) -> Optional[Task]:
        if self._active_sheet == new_active:
            return None

        old_active = self._active_sheet
        self._active_sheet = new_active

        # Понижаем приоритет FULL задач для старого активного листа
        new_queue = deque()
        for task in self._queue:
            if task.sheet_name == old_active and task.type == TaskType.LOAD_FULL:
                new_task = Task(task.type, task.sheet_name, self._get_full_priority(old_active))
                new_queue.append(new_task)
            else:
                new_queue.append(task)
        self._queue = new_queue

        # Если превью нового активного ещё не загружено — создаём PREVIEW
        if new_active not in self._preview_done:
            new_task = Task(TaskType.LOAD_PREVIEW, new_active, priority=0)
            self._queue.appendleft(new_task)
            return new_task

        # Если превью загружено, но FULL нет — создаём FULL
        if new_active not in self._full_done:
            new_task = Task(TaskType.LOAD_FULL, new_active, priority=0)
            # Удаляем старые FULL для этого листа
            self._queue = deque(t for t in self._queue if not (t.sheet_name == new_active and t.type == TaskType.LOAD_FULL))
            self._queue.appendleft(new_task)
            return new_task

        return None

    def add_tasks_for_new_file(self, sheet_names: List[str], active_sheet: str) -> None:
        self._queue.clear()
        self._preview_done.clear()
        self._full_done.clear()
        self.set_sheet_order(sheet_names)
        self.set_active_sheet(active_sheet)
        for name in sheet_names:
            self._add_preview_task(name)

    def on_preview_loaded(self, sheet_name: str, load_limit: int) -> Optional[Task]:
        self._preview_done.add(sheet_name)
        if load_limit == -1:
            return None

        # FULL задачи создаются только когда ВСЕ превью загружены
        if len(self._preview_done) == len(self._sheet_order):
            for name in self._sheet_order:
                if name not in self._full_done:
                    task = Task(TaskType.LOAD_FULL, name, priority=self._get_full_priority(name))
                    self._queue.append(task)
            # Возвращаем задачу для активного листа, если она есть в очереди
            for task in self._queue:
                if task.type == TaskType.LOAD_FULL and task.sheet_name == self._active_sheet:
                    return task
        return None

    def on_full_loaded(self, sheet_name: str) -> Optional[Task]:
        self._full_done.add(sheet_name)

        # Удаляем все оставшиеся задачи LOAD_FULL для этого листа
        self._queue = deque(t for t in self._queue if not (t.sheet_name == sheet_name and t.type == TaskType.LOAD_FULL))

        if sheet_name == self._active_sheet:
            for name in self._sheet_order:
                if name not in self._full_done and name in self._preview_done:
                    task = Task(TaskType.LOAD_FULL, name, priority=self._get_full_priority(name))
                    self._queue.append(task)
                    return task
        return None

    def pop_next(self) -> Optional[Task]:
        if not self._queue:
            return None
        min_priority = min(task.priority for task in self._queue)
        candidates = [t for t in self._queue if t.priority == min_priority]
        if len(candidates) > 1:
            candidates.sort(key=lambda t: self._sheet_order.index(t.sheet_name))
        task = candidates[0]
        self._queue.remove(task)
        return task

    def return_task(self, task: Task) -> None:
        # Вставляем задачу обратно с сохранением приоритета
        self._queue.append(task)
        # Пересортировываем очередь по приоритетам
        self._queue = deque(sorted(self._queue, key=lambda t: t.priority))

    def clear(self) -> None:
        self._queue.clear()

    def is_empty(self) -> bool:
        return len(self._queue) == 0
