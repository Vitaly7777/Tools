import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from core.config import AppConfig
from core.models import SheetInfo, SheetState
from core.loader_worker import LoaderWorker, get_deep_size
from core.task_queue import Task, TaskType
from core.excel_reader import ExcelReader


def test_get_deep_size():
    data = [("a", "b"), ("c", "d")]
    size = get_deep_size(data)
    assert size > 0

    nested = {"key": [1, 2, 3]}
    assert get_deep_size(nested) > sys.getsizeof(nested)


def test_check_memory_limit(qtbot):
    config = AppConfig()
    config.CACHE_MEMORY_LIMIT_MB = 0
    worker = LoaderWorker(config)

    info = SheetInfo("test", 1000, 10, True)
    info.data_cache = [tuple(range(10))] * 100
    worker._sheets = {"test": info}
    worker._active_sheet = "test"

    with patch.object(worker, 'memory_limit_exceeded') as mock_signal:
        result = worker._check_memory_limit()
        assert result is True
        mock_signal.emit.assert_called_once()


def test_clear_inactive_caches():
    config = AppConfig()
    worker = LoaderWorker(config)

    active = SheetInfo("active", 100, 10, True)
    active.state = SheetState.FULL_LOADING
    active.data_cache = [("data",)]

    inactive = SheetInfo("inactive", 100, 10, False)
    inactive.state = SheetState.FULL_LOADING
    inactive.data_cache = [("data",)]

    worker._sheets = {"active": active, "inactive": inactive}
    worker._active_sheet = "active"
    worker._clear_inactive_caches()

    assert len(active.data_cache) == 1
    assert len(inactive.data_cache) == 0
    assert inactive.state == SheetState.PREVIEW_LOADED


def test_load_preview(qtbot):
    config = AppConfig()
    worker = LoaderWorker(config)
    worker._queue.set_sheet_order(["test"])

    info = SheetInfo("test", 100, 5, True)
    worker._sheets = {"test": info}
    worker._file_path = Path("fake.xlsx")

    mock_reader = MagicMock(spec=ExcelReader)
    mock_reader._workbook = {"test": MagicMock()}

    def fake_read(reader, info, start_row, max_rows):
        return [("a",)], 1, 1

    with patch.object(worker, '_read_with_interrupt_check', side_effect=fake_read):
        worker._load_preview(mock_reader, info)

    assert info.state == SheetState.PREVIEW_LOADED
    assert info.loaded_rows == 1


def test_request_more_rows_adds_task():
    config = AppConfig()
    worker = LoaderWorker(config)
    worker._queue.set_sheet_order(["test"])
    info = SheetInfo("test", 100, 5, True)
    info.state = SheetState.PREVIEW_LOADED
    worker._sheets = {"test": info}

    worker.request_more_rows("test", 10, 50)

    task = worker._queue.pop_next()
    assert task is not None
    assert task.type == TaskType.LOAD_MORE
    assert task.sheet_name == "test"
    assert task.start_row == 10
    assert task.count == 50


def test_request_more_rows_ignores_wrong_state():
    config = AppConfig()
    worker = LoaderWorker(config)
    worker._queue.set_sheet_order(["test"])
    info = SheetInfo("test", 100, 5, True)
    info.state = SheetState.NOT_STARTED
    worker._sheets = {"test": info}

    worker.request_more_rows("test", 10, 50)

    assert worker._queue.is_empty()


def test_set_active_sheet_does_not_clear_cache():
    config = AppConfig()
    worker = LoaderWorker(config)

    active = SheetInfo("active", 100, 10, True)
    active.state = SheetState.PREVIEW_LOADED
    active.data_cache = [("data",)]

    inactive = SheetInfo("inactive", 100, 10, False)
    inactive.state = SheetState.PREVIEW_LOADED
    inactive.data_cache = [("data",)]

    worker._sheets = {"active": active, "inactive": inactive}
    worker._active_sheet = "active"

    worker.set_active_sheet("inactive")

    assert len(active.data_cache) == 1
    assert len(inactive.data_cache) == 1
