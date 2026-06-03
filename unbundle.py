#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для распаковки бандла проекта обратно в файлы.
Восстанавливает ЛЮБЫЕ файлы, которые были упакованы.
"""

import os
import re
import sys
from pathlib import Path
import argparse

# ===== КОНСТАНТЫ НАСТРОЕК =====
# Имя файла бандла по умолчанию
DEFAULT_BUNDLE_FILE = "project_bundle.txt"
# ===============================


def parse_bundle(bundle_file: str) -> list:
    """
    Парсит бандл и возвращает список кортежей (путь_к_файлу, содержимое).
    Игнорирует структуру проекта и статистику, находит только реальные файлы.
    """
    files = []
    current_file = None
    current_content = []
    in_file_section = False
    
    # Паттерны для поиска маркеров файлов
    file_start_pattern = re.compile(r'^={60,}\s*$')  # строка из 60+ "="
    # file_name_pattern = re.compile(r'^FILE:\s*(.+?)\s*$')
    file_name_pattern = re.compile(r'^(?:FILE|ФАЙЛ):\s*(.+?)\s*$')
    
    with open(bundle_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')
        
        # Ищем начало секции файла (строку из "=")
        if file_start_pattern.match(line) and i + 1 < len(lines):
            next_line = lines[i + 1].rstrip('\n')
            file_match = file_name_pattern.match(next_line)
            
            if file_match:
                # Сохраняем предыдущий файл, если был
                if current_file is not None and current_content:
                    files.append((current_file, '\n'.join(current_content)))
                
                # Начинаем новый файл
                current_file = file_match.group(1).strip()
                current_content = []
                in_file_section = True
                i += 2  # Пропускаем строку с "=" и строку с "FILE:"
                continue
        
        # Если мы внутри секции файла, собираем содержимое
        elif in_file_section:
            # Проверяем, не началась ли новая секция
            if file_start_pattern.match(line):
                # Это начало следующего файла - сохраняем текущий
                if current_file is not None and current_content:
                    files.append((current_file, '\n'.join(current_content)))
                
                # Проверяем, не является ли следующая строка именем файла
                if i + 1 < len(lines):
                    next_line = lines[i + 1].rstrip('\n')
                    file_match = file_name_pattern.match(next_line)
                    if file_match:
                        current_file = file_match.group(1).strip()
                        current_content = []
                        i += 2
                        continue
                    else:
                        in_file_section = False
                        current_file = None
                else:
                    in_file_section = False
                    current_file = None
            else:
                # Обычная строка содержимого
                current_content.append(line)
        
        i += 1
    
    # Добавляем последний файл
    if current_file is not None and current_content:
        files.append((current_file, '\n'.join(current_content)))
    
    return files


def ensure_directory(file_path: str):
    """Создаёт директорию для файла, если её нет"""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def get_file_emoji(file_path: str) -> str:
    """Возвращает эмодзи в зависимости от типа файла"""
    if file_path.endswith('.py'):
        return "🐍"
    elif file_path.endswith('.md'):
        return "📝"
    elif file_path.endswith('.txt'):
        return "📄"
    elif file_path.endswith('.json'):
        return "📊"
    elif file_path.endswith('.csv'):
        return "📈"
    elif file_path.endswith('.xlsx') or file_path.endswith('.xls'):
        return "📗"
    elif file_path == 'requirements.txt':
        return "📦"
    elif file_path.endswith('.gitignore'):
        return "🔒"
    elif file_path.endswith('.yml') or file_path.endswith('.yaml'):
        return "⚙️"
    elif file_path.endswith('.html'):
        return "🌐"
    elif file_path.endswith('.css'):
        return "🎨"
    elif file_path.endswith('.js'):
        return "🟨"
    else:
        return "📄"


def write_files(files: list, dry_run: bool = False, verbose: bool = False, overwrite: bool = False):
    """
    Записывает файлы на диск.
    
    Args:
        files: список (путь, содержимое)
        dry_run: если True, только показывает, что будет сделано
        verbose: подробный вывод
        overwrite: True - перезаписывать все существующие файлы без вопросов
                  False - спрашивать про каждый существующий файл
    """
    created = []
    skipped = []
    
    for file_path, content in files:
        file_path = file_path.replace('\\', '/')
        
        # Проверяем безопасность пути
        if '..' in file_path or file_path.startswith('/'):
            print(f"⚠️  Безопасность: пропущен потенциально опасный путь: {file_path}")
            skipped.append((file_path, "опасный путь"))
            continue
        
        # Проверяем, существует ли файл
        file_exists = os.path.exists(file_path)
        
        # Если файл существует и не включён режим overwrite
        if file_exists and not overwrite and not dry_run:
            emoji = get_file_emoji(file_path)
            response = input(f"\n{emoji} Файл уже существует: {file_path}\n   Перезаписать? (y/n/a): ").lower()
            
            if response == 'a':  # a = all (перезаписать все)
                overwrite = True
                # Продолжаем с перезаписью этого файла
            elif response == 'y':  # перезаписать этот
                pass  # продолжим выполнение
            else:  # любой другой ответ - пропустить
                print(f"   ⏭️  Пропущен: {file_path}")
                skipped.append((file_path, "пользователь пропустил"))
                continue
        
        # Если файл существует и режим overwrite выключен - пропускаем
        elif file_exists and not overwrite and not dry_run:
            if verbose:
                print(f"⏭️  Пропущен (уже существует): {file_path}")
            skipped.append((file_path, "уже существует"))
            continue
        
        if dry_run:
            emoji = get_file_emoji(file_path)
            action = "Будет перезаписан" if file_exists else "Будет создан"
            print(f"{emoji} {action}: {file_path} ({len(content)} символов)")
            created.append(file_path)
            continue
        
        try:
            # Создаём директорию
            ensure_directory(file_path)
            
            # Записываем файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if verbose:
                emoji = get_file_emoji(file_path)
                action = "Перезаписан" if file_exists else "Создан"
                print(f"{emoji} {action}: {file_path} ({len(content)} символов)")
            
            created.append(file_path)
            
        except Exception as e:
            print(f"❌ Ошибка при создании {file_path}: {e}")
            skipped.append((file_path, str(e)))
    
    return created, skipped


def main():
    parser = argparse.ArgumentParser(description='Распаковка бандла проекта обратно в файлы')
    parser.add_argument('bundle', nargs='?', default=DEFAULT_BUNDLE_FILE,
                       help=f'Путь к файлу бандла (по умолчанию: {DEFAULT_BUNDLE_FILE})')
    parser.add_argument('-o', '--output-dir', default='.', 
                       help='Директория для распаковки (по умолчанию текущая)')
    parser.add_argument('-d', '--dry-run', action='store_true',
                       help='Режим проверки (без записи файлов)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Подробный вывод')
    parser.add_argument('--overwrite', action='store_true',
                       help='Перезаписывать существующие файлы без подтверждения')
    parser.add_argument('--list-files', action='store_true',
                       help='Только показать список файлов в бандле')
    parser.add_argument('--no-skip', action='store_true',
                       help='Не пропускать никакие файлы (восстанавливать всё)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.bundle):
        print(f"❌ Файл не найден: {args.bundle}")
        print(f"   Искали файл: {os.path.abspath(args.bundle)}")
        print(f"\n💡 Подсказка: можно указать имя файла как аргумент")
        print(f"   Пример: python unbundle.py my_project.txt")
        print(f"   Или изменить константу DEFAULT_BUNDLE_FILE в начале скрипта")
        sys.exit(1)
    
    print(f"📖 Чтение бандла: {args.bundle}")
    files = parse_bundle(args.bundle)
    
    if not files:
        print("❌ Не найдено ни одного файла в бандле")
        sys.exit(1)
    
    # Если не указано --no-skip, фильтруем только служебные файлы
    if not args.no_skip:
        # Пропускаем только явно служебные секции
        valid_files = []
        skipped_sections = 0
        
        for file_path, content in files:
            # Проверяем, не является ли это служебной секцией
            if (file_path.startswith('СТРУКТУРА ПРОЕКТА') or
                file_path.startswith('СТАТИСТИКА') or
                file_path.startswith('КОНФИГУРАЦИЯ')):
                skipped_sections += 1
                continue
            
            valid_files.append((file_path, content))
        
        files = valid_files
        if skipped_sections > 0:
            print(f"📊 Пропущено служебных секций: {skipped_sections}")
    else:
        print(f"⚠️  Режим 'без пропуска' — восстанавливаются ВСЕ секции, включая служебные")
    
    print(f"📦 Найдено файлов для восстановления: {len(files)}")
    
    # Группируем по типам для статистики
    by_extension = {}
    for file_path, _ in files:
        ext = os.path.splitext(file_path)[1] or "(без расширения)"
        if ext not in by_extension:
            by_extension[ext] = 0
        by_extension[ext] += 1
    
    if by_extension and args.verbose:
        print("\n📊 Статистика по типам файлов:")
        for ext, count in sorted(by_extension.items()):
            if ext == '.py':
                emoji = "🐍"
            elif ext == '.md':
                emoji = "📝"
            elif ext == '.txt':
                emoji = "📄"
            elif ext == '.json':
                emoji = "📊"
            elif ext == '.csv':
                emoji = "📈"
            else:
                emoji = "📁"
            print(f"  {emoji} {ext or 'без расширения'}: {count}")
    
    # Если нужно только показать список
    if args.list_files:
        print("\n📋 Файлы в бандле:")
        # Группируем по папкам для удобства
        by_folder = {}
        for file_path, _ in files:
            folder = os.path.dirname(file_path) or "."
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(file_path)
        
        for folder, file_list in sorted(by_folder.items()):
            print(f"\n  📁 {folder}/")
            for file_path in sorted(file_list):
                emoji = get_file_emoji(file_path)
                print(f"    {emoji} {os.path.basename(file_path)}")
        return
    
    # Переходим в целевую директорию
    original_dir = os.getcwd()
    if args.output_dir != '.':
        os.makedirs(args.output_dir, exist_ok=True)
        os.chdir(args.output_dir)
        print(f"📂 Распаковка в: {os.path.abspath('.')}")
    
    try:
        # Записываем файлы
        created, skipped = write_files(
            files, 
            args.dry_run, 
            args.verbose,
            args.overwrite
        )
        
        # Итог
        print("\n" + "="*50)
        if args.dry_run:
            print(f"🔍 РЕЖИМ ПРОВЕРКИ: будет создано {len(created)} файлов")
        else:
            print(f"✅ РАСПАКОВКА ЗАВЕРШЕНА:")
            print(f"   Создано файлов: {len(created)}")
            if skipped:
                print(f"   Пропущено: {len(skipped)}")
        
        if skipped and args.verbose:
            print("\nПропущенные файлы:")
            for f, reason in skipped:
                emoji = get_file_emoji(f)
                print(f"  {emoji} {f}: {reason}")
                
    finally:
        # Возвращаемся в исходную директорию
        os.chdir(original_dir)


if __name__ == "__main__":
    main()