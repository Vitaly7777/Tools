from core.processor import CutFilesProcessor
from ui.windgets import LogHandler


from PySide6.QtCore import QObject, Signal


import logging
from datetime import datetime
from pathlib import Path
import sys


class CutFilesWorker(QObject):
    """Фоновый поток для обработки файлов."""

    progress = Signal(int, int, str)
    file_done = Signal(dict)
    finished = Signal(dict)
    log = Signal(str, str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.processor = None
        self._is_running = False

    

    def run(self):
        """Запуск обработки."""
        self._is_running = True
        self.processor = CutFilesProcessor()
        self.processor.config = self.config
  
        # self.processor.work_dir = Path(__file__).resolve().parent
        if getattr(sys, 'frozen', False):
            self.processor.work_dir = Path(sys.executable).parent
        else:
            self.processor.work_dir = Path(__file__).resolve().parent.parent    
        
        
        self.processor.stats = []
        self.processor._setup_logging()

        logger = logging.getLogger()
        gui_handler = LogHandler(self.log)
        logger.addHandler(gui_handler)

        old_level = logger.level
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))
        try:
            self.processor.logger = logger
            self._run_with_callbacks()

        except Exception as e:
            self.log.emit(f"Критическая ошибка: {e}", "ERROR")
        finally:
            logger.removeHandler(gui_handler)
            logger.setLevel(old_level)
            self._is_running = False
            self.finished.emit(self.config)



    def _run_with_callbacks(self):
        """Выполнение process_files с обратными вызовами."""
        processor = self.processor
        config = self.config

        processor.logger.info("=" * 60)
        processor.logger.info("Запуск скрипта обрезки Excel/ODS файлов")
        processor.logger.info(f"Конфигурация: {config}")
        processor.logger.info("=" * 60)

        # source_dir_str = config["source_folder"]
        # source_dir = Path(source_dir_str)
        source_dir = processor._resolve_path(config["source_folder"], processor.work_dir)


        if not source_dir.is_dir():
            processor.logger.error(f"Папка {source_dir} не найдена")
            return

        processor.source_dir = source_dir

        output_folder = processor._resolve_path(config["output_folder"], processor.work_dir) if config.get("output_folder") else source_dir.parent / (source_dir.name + "_cut")
        output_folder.mkdir(parents=True, exist_ok=True)
        processor.logger.info(f"Выходная папка: {output_folder}")

        extensions = ["*.xlsb", "*.xlsx", "*.xlsm", "*.ods"]
        all_files = []
        for ext in extensions:
            all_files.extend(f for f in source_dir.rglob(ext) if not f.name.startswith("~"))

        if not all_files:
            processor.logger.warning("Файлы для обработки не найдены")
            return

        total_start = datetime.now()
        total = len(all_files)

        for idx, filepath in enumerate(all_files, 1):
            if not self._is_running:
                break

            self.progress.emit(idx, total, filepath.name)
            processor.logger.info(f"[{idx}/{total}] Обработка {filepath.name}")

            result = processor.process_single_file(filepath, output_folder)
            if result:
                processor.stats.append(result)
                self.file_done.emit(result)

        total_time = (datetime.now() - total_start).total_seconds()
        success = sum(1 for s in processor.stats if s.get("status") == "success")
        error = len(processor.stats) - success
        original = sum(s.get("original_rows", 0) for s in processor.stats)
        saved = sum(s.get("rows_saved", 0) for s in processor.stats)

        processor.logger.info("=" * 60)
        processor.logger.info(f"Готово! Успешно: {success}, ошибок: {error}")
        processor.logger.info(f"Строк: {original} -> {saved}, время: {total_time:.2f} сек")
        processor.logger.info("=" * 60)

        if config.get("stats_file"):
            processor.save_stats_to_excel()

    def stop(self):
        """Остановка обработки."""
        self._is_running = False
