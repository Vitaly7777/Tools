# tests/test_task_queue.py

from core.task_queue import TaskQueue, Task, TaskType


def test_add_tasks_for_new_file():
    q = TaskQueue()
    q.add_tasks_for_new_file(["Sheet1", "Sheet2", "Sheet3"], "Sheet2")

    t1 = q.pop_next()
    assert t1.type == TaskType.LOAD_PREVIEW
    assert t1.sheet_name == "Sheet2"
    assert t1.priority == 0

    t2 = q.pop_next()
    assert t2.type == TaskType.LOAD_PREVIEW
    assert t2.sheet_name in ("Sheet1", "Sheet3")
    assert t2.priority == 1


def test_on_sheet_changed_returns_new_task_when_not_in_queue():
    q = TaskQueue()
    q.set_sheet_order(["A", "B"])
    q.set_active_sheet("A")
    task = q.on_sheet_changed("B")
    assert task is not None
    assert task.type == TaskType.LOAD_PREVIEW
    assert task.sheet_name == "B"
    assert task.priority == 0


def test_return_task():
    q = TaskQueue()
    q.set_sheet_order(["Sheet1"])
    task = Task(TaskType.LOAD_FULL, "Sheet1", 0)
    q.add_task(task)
    q.return_task(task)
    assert q.pop_next() == task
