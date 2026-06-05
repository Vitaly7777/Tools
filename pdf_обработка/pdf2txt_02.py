import sys
import os
import argparse

def pdf_to_txt(pdf_path, txt_path=None, method='auto'):
    """
    Универсальная функция преобразования PDF в TXT
    
    Parameters:
    pdf_path (str): путь к PDF файлу
    txt_path (str): путь для сохранения TXT файла (опционально)
    method (str): метод извлечения ('pypdf2', 'pdfplumber', 'auto')
    """
    
    # Определяем путь для выходного файла
    if txt_path is None:
        base_name = os.path.splitext(pdf_path)[0]
        txt_path = f"{base_name}.txt"
    
    # Проверяем существование файла
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Файл {pdf_path} не найден")
    
    # Проверяем допустимость метода
    valid_methods = ['pypdf2', 'pdfplumber', 'auto']
    if method not in valid_methods:
        raise ValueError(f"Неверный метод. Доступные методы: {', '.join(valid_methods)}")
    
    # Автоматический выбор метода
    if method == 'auto':
        try:
            import pdfplumber
            method = 'pdfplumber'
            print("Автоматически выбран метод: pdfplumber")
        except ImportError:
            try:
                import PyPDF2
                method = 'pypdf2'
                print("Автоматически выбран метод: PyPDF2")
            except ImportError:
                raise ImportError("Установите PyPDF2 или pdfplumber: pip install PyPDF2 pdfplumber")
    
    # Выполняем преобразование
    print(f"Начинаю преобразование с методом: {method}")
    print(f"Входной файл: {pdf_path}")
    print(f"Выходной файл: {txt_path}")
    
    if method == 'pypdf2':
        import PyPDF2
        pdf_to_txt_pypdf2(pdf_path, txt_path)
    elif method == 'pdfplumber':
        import pdfplumber
        pdf_to_txt_pdfplumber(pdf_path, txt_path)
    
    return txt_path

def pdf_to_txt_pypdf2(pdf_path, txt_path):
    """Внутренняя функция для PyPDF2"""
    import PyPDF2
    
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Всего страниц: {total_pages}")
        
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                if text:
                    txt_file.write(f"[Страница {page_num + 1}]\n{text}\n\n")
                
                # Прогресс-бар
                progress = (page_num + 1) / total_pages * 100
                print(f"PyPDF2: обработка страницы {page_num + 1}/{total_pages} [{progress:.1f}%]")
    
    print(f"✅ Преобразование завершено! Результат сохранен в: {txt_path}")

def pdf_to_txt_pdfplumber(pdf_path, txt_path):
    """Внутренняя функция для pdfplumber"""
    import pdfplumber
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        print(f"Всего страниц: {total_pages}")
        
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                
                if text:
                    txt_file.write(f"[Страница {page_num}]\n{text}\n\n")
                
                # Прогресс-бар
                progress = page_num / total_pages * 100
                print(f"pdfplumber: обработка страницы {page_num}/{total_pages} [{progress:.1f}%]")
    
    print(f"✅ Преобразование завершено! Результат сохранен в: {txt_path}")

def interactive_mode():
    """Интерактивный режим ввода параметров"""
    print("=" * 50)
    print("PDF в TXT конвертер")
    print("=" * 50)
    
    # Ввод пути к PDF файлу
    while True:
        pdf_path = input("Введите путь к PDF файлу: ").strip()
        print(pdf_path)
        if os.path.exists(pdf_path):
            break
        print(f"❌ Файл '{pdf_path}' не найден. Попробуйте снова.")
    
    # Ввод пути для сохранения TXT файла
    default_txt = os.path.splitext(pdf_path)[0] + ".txt"
    txt_path = input(f"Введите путь для сохранения TXT файла (Enter для '{default_txt}'): ").strip()
    if not txt_path:
        txt_path = default_txt
    
    # Выбор метода
    print("\nДоступные методы:")
    print("1. auto (автоматический выбор)")
    print("2. pypdf2 (простой, для текстовых PDF)")
    print("3. pdfplumber (лучше для таблиц и сложной структуры)")
    
    while True:
        method_choice = input("Выберите метод (1-3) или введите название метода: ").strip().lower()
        
        if method_choice in ['1', 'auto']:
            method = 'auto'
            break
        elif method_choice in ['2', 'pypdf2']:
            method = 'pypdf2'
            break
        elif method_choice in ['3', 'pdfplumber']:
            method = 'pdfplumber'
            break
        else:
            print("❌ Неверный выбор. Введите 1, 2, 3 или название метода.")
    
    # Запуск преобразования
    print("\n" + "=" * 50)
    try:
        pdf_to_txt(pdf_path, txt_path, method)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def main():
    """Главная функция с парсингом аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Преобразование PDF файла в текстовый TXT файл',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s input.pdf
  %(prog)s input.pdf -o output.txt
  %(prog)s input.pdf -m pdfplumber
  %(prog)s input.pdf -o result.txt -m pypdf2
  %(prog)s -i  (интерактивный режим)
        """
    )
    
    parser.add_argument(
        'pdf_file', 
        nargs='?', 
        help='Путь к PDF файлу'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='txt_file',
        help='Путь для сохранения TXT файла'
    )
    
    parser.add_argument(
        '-m', '--method',
        choices=['pypdf2', 'pdfplumber', 'auto'],
        default='auto',
        help='Метод извлечения текста (по умолчанию: auto)'
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Запустить в интерактивном режиме'
    )
    
    # Парсим аргументы
    args = parser.parse_args()
    
    # Интерактивный режим
    if args.interactive or not args.pdf_file:
        if not args.pdf_file and not args.interactive:
            print("Запуск в интерактивном режиме...")
        interactive_mode()
        return
    
    # Запуск с аргументами командной строки
    try:
        pdf_to_txt(args.pdf_file, args.txt_file, args.method)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()