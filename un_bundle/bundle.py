#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для упаковки проекта в один файл (бандл) с генерацией структуры.
Поддерживает конфигурационный файл .bundle.config.json и аргументы командной строки.
"""

import os
import sys
import json
import argparse
import fnmatch
from datetime import datetime
from typing import List, Dict, Any, Optional


# ===== КОНСТАНТЫ ПО УМОЛЧАНИЮ =====
DEFAULT_INCLUDE_MD = False
DEFAULT_INCLUDE_PATTERNS = []  # пустой список = всё
DEFAULT_EXCLUDE_PATTERNS = [
    'bundle.py', 'unbundle.py', 
    'venv', 'env', '.venv', '__pycache__', '*.pyc',
    '.git', '.idea', '.vscode', 'build', 'dist',
    '*.egg-info', 'project_bundle.txt', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', '.bundle.config.json',
    '.DS_Store', 'Thumbs.db', '*.log', '*.tmp'
]
DEFAULT_OUTPUT_FILE = 'project_bundle.txt'
DEFAULT_INCLUDE_REQUIREMENTS = False
DEFAULT_MAX_FILE_SIZE_MB = 10
# ===================================


class Config:
    """Класс для управления конфигурацией с поатрибутным приоритетом"""
    
    def __init__(self):
        self.args = self._parse_args()
        self.config_data = self._load_config_file()
        
        # Финальные настройки
        self.include_md = self._get_param(
            'include_md', 
            cli_flag='include_md',
            default=DEFAULT_INCLUDE_MD
        )
        
        self.include_patterns = self._get_list_param(
            'include_patterns',
            cli_flag='include',
            default=DEFAULT_INCLUDE_PATTERNS
        )
        
        self.exclude_patterns = self._get_list_param(
            'exclude_patterns',
            cli_flag='exclude',
            default=DEFAULT_EXCLUDE_PATTERNS
        )
        
        self.output_file = self._get_param(
            'output_file',
            cli_flag='output',
            default=DEFAULT_OUTPUT_FILE
        )
        
        self.include_requirements = self._get_param(
            'include_requirements',
            cli_flag='include_requirements',
            default=DEFAULT_INCLUDE_REQUIREMENTS
        )
        
        self.max_file_size_mb = self._get_param(
            'max_file_size_mb',
            cli_flag='max_size',
            default=DEFAULT_MAX_FILE_SIZE_MB
        )
        
        self.verbose = self.args.verbose if hasattr(self.args, 'verbose') else False
    
    def _parse_args(self) -> argparse.Namespace:
        """Парсит аргументы командной строки"""
        parser = argparse.ArgumentParser(
            description='Упаковка проекта в один файл',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # Флаги для include_md - взаимоисключающая группа с ОДНИМ dest
        md_group = parser.add_mutually_exclusive_group()
        md_group.add_argument(
            '--include-md', 
            action='store_true', 
            dest='include_md',
            help='Включить .md файлы в бандл',
            default=DEFAULT_INCLUDE_MD
        )
        md_group.add_argument(
            '--no-md', 
            action='store_false', 
            dest='include_md',
            help='Исключить .md файлы из бандла',
            default=DEFAULT_INCLUDE_MD
        )
        
        # Паттерны включения/исключения
        parser.add_argument(
            '--include', '-i',
            action='append',
            default=[],
            help='Паттерн включения (можно использовать несколько раз)'
        )
        parser.add_argument(
            '--exclude', '-e',
            action='append',
            default=[],
            help='Паттерн исключения (можно использовать несколько раз)'
        )
        
        # Флаги для requirements - взаимоисключающая группа с ОДНИМ dest
        req_group = parser.add_mutually_exclusive_group()
        req_group.add_argument(
            '--with-requirements',
            action='store_true', 
            dest='include_requirements',
            help='Включить requirements.txt в бандл',
            default=DEFAULT_INCLUDE_REQUIREMENTS
        )
        req_group.add_argument(
            '--no-requirements',
            action='store_false', 
            dest='include_requirements',
            help='Исключить requirements.txt из бандла',
            default=DEFAULT_INCLUDE_REQUIREMENTS
        )
        
        # Остальные параметры
        parser.add_argument(
            '-o', '--output',
            help='Имя выходного файла (по умолчанию: project_bundle.txt)'
        )
        parser.add_argument(
            '--max-size',
            type=float,
            help=f'Максимальный размер файла в МБ (по умолчанию: {DEFAULT_MAX_FILE_SIZE_MB})'
        )
        parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='Подробный вывод в консоль'
        )
        
        return parser.parse_args()
    
    def _load_config_file(self) -> Dict[str, Any]:
        """Загружает конфигурационный файл, если он существует"""
        config_paths = [
            os.path.join(os.getcwd(), '.bundle.config.json'),
            os.path.join(os.getcwd(), 'bundle.config.json')
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"⚠️  Ошибка загрузки конфига {path}: {e}")
                    return {}
        
        return {}
    
    def _get_param(self, name: str, cli_flag: str = None, default=None):
        """
        Получает параметр с учётом приоритета:
        1. Командная строка (если указана)
        2. Конфиг
        3. Значение по умолчанию
        """
        # Проверяем командную строку
        if cli_flag:
            cli_value = getattr(self.args, cli_flag, None)
        else:
            cli_value = getattr(self.args, name, None)
        
        # Для булевых значений проверяем, был ли флаг указан
        if cli_flag in ['include_md', 'include_requirements']:
            if hasattr(self.args, cli_flag):
                return cli_value
        
        # Для не-булевых проверяем не-None
        if cli_value is not None:
            return cli_value
        
        # Проверяем конфиг
        if name in self.config_data:
            return self.config_data[name]
        
        # Возвращаем значение по умолчанию
        return default
    
    def _get_list_param(self, name: str, cli_flag: str, default: List[str]) -> List[str]:
        """
        Получает список с учётом приоритета.
        Особенность: если в CLI список не пуст, значит флаг был указан.
        """
        # Проверяем командную строку
        cli_value = getattr(self.args, cli_flag, [])
        if cli_value:  # не пустой список = флаг был указан
            return cli_value
        
        # Проверяем конфиг
        if name in self.config_data:
            config_value = self.config_data[name]
            if isinstance(config_value, list):
                return config_value
            elif isinstance(config_value, str):
                return [config_value]
        
        # Возвращаем значение по умолчанию
        return default
    
    def __str__(self) -> str:
        """Строковое представление конфигурации"""
        lines = ["Текущая конфигурация:"]
        lines.append(f"  📝 Включение .md файлов: {self.include_md}")
        lines.append(f"  🔍 Паттерны включения: {self.include_patterns if self.include_patterns else '[всё]'}")
        lines.append(f"  🚫 Паттерны исключения: {self.exclude_patterns if self.exclude_patterns else '[нет]'}")
        lines.append(f"  📦 Выходной файл: {self.output_file}")
        lines.append(f"  📋 Включение requirements.txt: {self.include_requirements}")
        lines.append(f"  📏 Макс. размер файла: {self.max_file_size_mb} МБ")
        return "\n".join(lines)


def should_ignore(file_path: str, exclude_patterns: List[str]) -> bool:
    """Проверяет, нужно ли игнорировать файл/папку"""
    if not exclude_patterns:
        return False
    
    name = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, start=os.getcwd())
    
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def should_include(file_path: str, include_patterns: List[str]) -> bool:
    """
    Проверяет, нужно ли включать файл.
    Если include_patterns пуст - включаем всё.
    """
    if not include_patterns:
        return True
    
    rel_path = os.path.relpath(file_path, start=os.getcwd())
    name = os.path.basename(file_path)
    
    for pattern in include_patterns:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    
    return False


def should_include_by_size(file_path: str, max_size_mb: float) -> bool:
    """Проверяет размер файла"""
    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        return size_mb <= max_size_mb
    except OSError:
        return False


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} ТБ"


def get_file_summary(file_path: str) -> Dict[str, Any]:
    """Возвращает информацию о файле"""
    try:
        stat = os.stat(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        return {
            'size': stat.st_size,
            'size_str': format_file_size(stat.st_size),
            'lines': len(lines),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        }
    except Exception:
        return {
            'size': 0,
            'size_str': '0 Б',
            'lines': 0,
            'modified': 'неизвестно'
        }


def read_file_safe(file_path: str) -> Optional[str]:
    """Безопасное чтение файла"""
    encodings = ['utf-8', 'cp1251', 'latin-1', 'koi8-r']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception:
            return None
    
    # Если ничего не подошло
    try:
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')
    except Exception:
        return None


def collect_files(config: Config) -> List[str]:
    """Собирает файлы согласно конфигурации"""
    files = []
    project_root = os.getcwd()
    
    print(f"\n🔍 Поиск файлов (include_md = {config.include_md}):")
    
    for root, dirs, filenames in os.walk(project_root):
        # Фильтруем директории по exclude_patterns
        original_dirs = dirs.copy()
        dirs[:] = [d for d in dirs if not should_ignore(
            os.path.join(root, d), config.exclude_patterns
        )]
        
        # Для отладки показываем, какие директории исключены
        if config.verbose and len(original_dirs) != len(dirs):
            excluded = set(original_dirs) - set(dirs)
            for d in excluded:
                print(f"  🚫 Исключена директория: {os.path.join(root, d)}")
        
        for filename in filenames:
            file_path = os.path.join(root, filename)
            
            # Проверяем расширения (базовая фильтрация)
            is_py = filename.endswith('.py')
            is_md = filename.lower().endswith('.md')  # Добавил .lower() для надёжности
            
            if config.verbose and (is_py or is_md):
                print(f"  🔍 Найден: {filename} (py={is_py}, md={is_md})")
            
            # Для отладки показываем все .md файлы, даже если они не будут включены
            if is_md and config.verbose:
                print(f"  📝 Найден .md файл: {filename}, include_md={config.include_md}")
            
            if not (is_py or (config.include_md and is_md)):
                continue
            
            # Проверяем паттерны исключения
            if should_ignore(file_path, config.exclude_patterns):
                if config.verbose:
                    print(f"  🚫 Исключён по паттерну: {filename}")
                continue
            
            # Проверяем паттерны включения
            if not should_include(file_path, config.include_patterns):
                if config.verbose:
                    print(f"  ⚠️ Не соответствует паттернам включения: {filename}")
                continue
            
            # Проверяем размер
            if not should_include_by_size(file_path, config.max_file_size_mb):
                if config.verbose:
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    rel_path = os.path.relpath(file_path, project_root)
                    print(f"  📏 Пропущен большой файл: {rel_path} ({size:.1f} МБ)")
                continue
            
            files.append(file_path)
            if config.verbose:
                print(f"  ✅ Добавлен: {filename}")
    
    return sorted(files)


def print_tree(start_dir: str, config: Config, prefix: str = "", is_last: bool = True) -> None:
    """Выводит дерево структуры проекта"""
    dir_name = os.path.basename(start_dir)
    
    if prefix == "":
        print(f"📁 {dir_name}/")
    else:
        branch = "└── " if is_last else "├── "
        print(f"{prefix}{branch}📁 {dir_name}/")
    
    # Обновляем префикс
    if prefix == "":
        new_prefix = "    "
    else:
        new_prefix = prefix + ("    " if is_last else "│   ")
    
    try:
        items = sorted(os.listdir(start_dir))
    except PermissionError:
        print(f"{new_prefix}└── ⚠️ Нет доступа")
        return
    
    # Фильтруем по exclude_patterns
    items = [item for item in items if not should_ignore(
        os.path.join(start_dir, item), config.exclude_patterns
    )]
    
    # Разделяем на папки и файлы
    dirs = []
    py_files = []
    md_files = []
    other_files = []
    
    for item in items:
        full_path = os.path.join(start_dir, item)
        if os.path.isdir(full_path):
            dirs.append(item)
        else:
            if item.endswith('.py'):
                py_files.append(item)
            elif item.lower().endswith('.md'):  # Используем .lower() для надёжности
                if config.include_md:
                    md_files.append(item)
                else:
                    other_files.append(f"{item} (md отключены)")
            else:
                other_files.append(item)
    
    dirs.sort()
    py_files.sort()
    md_files.sort()
    other_files.sort()
    
    # Выводим папки
    for i, item in enumerate(dirs):
        item_path = os.path.join(start_dir, item)
        is_last_item = (i == len(dirs) - 1 and not py_files 
                        and not md_files and not other_files)
        print_tree(item_path, config, new_prefix, is_last_item)
    
    # Выводим Python файлы
    for i, item in enumerate(py_files):
        branch = "└── " if (i == len(py_files) - 1 and not md_files 
                            and not other_files) else "├── "
        print(f"{new_prefix}{branch}🐍 {item}")
    
    # Выводим Markdown файлы
    for i, item in enumerate(md_files):
        branch = "└── " if (i == len(md_files) - 1 and not other_files) else "├── "
        print(f"{new_prefix}{branch}📝 {item}")
    
    # Выводим остальные файлы
    for i, item in enumerate(other_files):
        branch = "└── " if i == len(other_files) - 1 else "├── "
        # Для файлов .md, которые не включены, добавляем пояснение
        if "md отключены" in item:
            print(f"{new_prefix}{branch}⬜ {item}")
        else:
            print(f"{new_prefix}{branch}⬜ {item} (не будет упакован)")


def bundle_project(files: List[str], config: Config) -> None:
    """Создаёт бандл из списка файлов"""
    project_root = os.getcwd()
    project_name = os.path.basename(project_root)
    
    py_files = [f for f in files if f.endswith('.py')]
    md_files = [f for f in files if f.lower().endswith('.md')] if config.include_md else []
    
    with open(config.output_file, 'w', encoding='utf-8') as out:
        # Заголовок
        out.write("#" + "="*78 + "\n")
        out.write(f"# BUNDLE: Проект {project_name}\n")
        out.write(f"# Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"# Python файлов: {len(py_files)}\n")
        if config.include_md:
            out.write(f"# Markdown файлов: {len(md_files)}\n")
        out.write(f"# Всего файлов: {len(files)}\n")
        out.write("#" + "="*78 + "\n\n")
        
        # Конфигурация бандла
        out.write(f"\n{'='*60}\n")
        out.write("КОНФИГУРАЦИЯ БАНДЛА\n")
        out.write(f"{'='*60}\n\n")
        out.write(f"INCLUDE_MD: {config.include_md}\n")
        out.write(f"INCLUDE_PATTERNS: {config.include_patterns if config.include_patterns else '[всё]'}\n")
        out.write(f"EXCLUDE_PATTERNS: {config.exclude_patterns if config.exclude_patterns else '[нет]'}\n")
        out.write(f"MAX_FILE_SIZE_MB: {config.max_file_size_mb}\n\n")
        
        # Статистика
        out.write(f"\n{'='*60}\n")
        out.write("СТАТИСТИКА ПО ФАЙЛАМ\n")
        out.write(f"{'='*60}\n\n")
        
        total_lines = 0
        total_size = 0
        
        for file_path in files:
            rel_path = os.path.relpath(file_path, project_root)
            summary = get_file_summary(file_path)
            total_lines += summary['lines']
            total_size += summary['size']
            
            emoji = "🐍" if file_path.endswith('.py') else "📝"
            out.write(f"{emoji} {rel_path:<50} {summary['lines']:4} строк, {summary['size_str']}\n")
        
        out.write(f"\n{'─'*60}\n")
        out.write(f"📊 ИТОГО: {len(files)} файлов, {total_lines} строк, {format_file_size(total_size)}\n\n")
        
        # Содержимое файлов
        out.write(f"\n{'='*60}\n")
        out.write("СОДЕРЖИМОЕ ФАЙЛОВ\n")
        out.write(f"{'='*60}\n")
        
        for file_path in files:
            rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
            
            out.write(f"\n{'='*60}\n")
            out.write(f"ФАЙЛ: {rel_path}\n")
            out.write(f"{'='*60}\n")
            
            content = read_file_safe(file_path)
            if content is not None:
                out.write(content)
                if not content.endswith('\n'):
                    out.write('\n')
        
        # requirements.txt
        if config.include_requirements and os.path.exists('requirements.txt'):
            out.write(f"\n{'='*60}\n")
            out.write("ФАЙЛ: requirements.txt\n")
            out.write(f"{'='*60}\n")
            
            content = read_file_safe('requirements.txt')
            if content:
                out.write(content)
                out.write("\n")


def main():
    # Загружаем конфигурацию
    config = Config()
    
    # Выводим информацию
    print("\n" + "="*60)
    print(f"📦 УПАКОВКА ПРОЕКТА: {os.path.basename(os.getcwd())}")
    print("="*60)
    
    print(config)
    
    # Выводим структуру
    print(f"\n📁 СТРУКТУРА ПРОЕКТА:")
    print("-"*40)
    print_tree(os.getcwd(), config)
    print("-"*40)
    
    # Собираем файлы
    files = collect_files(config)
    
    if not files:
        print("❌ Не найдено файлов для упаковки")
        sys.exit(1)
    
    # Статистика
    py_count = len([f for f in files if f.endswith('.py')])
    md_count = len([f for f in files if f.lower().endswith('.md')]) if config.include_md else 0
    
    print(f"\n📊 Найдено файлов для упаковки:")
    print(f"   🐍 Python: {py_count}")
    if config.include_md:
        print(f"   📝 Markdown: {md_count}")
    print(f"   📄 Всего: {len(files)}")
    
    # Создаём бандл
    bundle_project(files, config)
    
    # Итог
    bundle_size = os.path.getsize(config.output_file)
    print(f"\n✅ Бандл создан: {config.output_file}")
    print(f"   📊 Размер: {format_file_size(bundle_size)}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()