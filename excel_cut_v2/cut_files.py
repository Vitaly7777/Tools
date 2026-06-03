"""
Скрипт для обрезки xlsb, xlsx, xlsm и ods файлов до указанного количества строк на каждом листе.
Поддерживает конфигурацию из JSON и аргументы командной строки.
"""

import sys
import argparse
from pathlib import Path


from core.processor import CutFilesProcessor


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help="Путь к JSON-конфигу")
    args, _ = parser.parse_known_args()

    config_path = Path(args.config) if args.config else None
    processor = CutFilesProcessor(config_path)
    processor._setup_logging()

    try:
        processor.process_files()
    except KeyboardInterrupt:
        processor.logger.info("Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        processor.logger.exception(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
