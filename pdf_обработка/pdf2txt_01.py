import sys
import os

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
    
    # Автоматический выбор метода
    if method == 'auto':
        try:
            import pdfplumber
            method = 'pdfplumber'
            print("Используется метод: pdfplumber")
        except ImportError:
            try:
                import PyPDF2
                method = 'pypdf2'
                print("Используется метод: PyPDF2")
            except ImportError:
                raise ImportError("Установите PyPDF2 или pdfplumber: pip install PyPDF2 pdfplumber")
    
    # Выполняем преобразование
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
        
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                if text:
                    txt_file.write(f"[Страница {page_num + 1}]\n{text}\n\n")
                
                print(f"PyPDF2: обработка страницы {page_num + 1}/{total_pages}")

def pdf_to_txt_pdfplumber(pdf_path, txt_path):
    """Внутренняя функция для pdfplumber"""
    import pdfplumber
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                
                if text:
                    txt_file.write(f"[Страница {page_num}]\n{text}\n\n")
                
                print(f"pdfplumber: обработка страницы {page_num}/{total_pages}")

# Использование
if __name__ == "__main__":
    # Обработка из командной строки
    if len(sys.argv) >= 2:
        input_pdf = sys.argv[1]
        output_txt = sys.argv[2] if len(sys.argv) >= 3 else None
        pdf_to_txt(input_pdf, output_txt)
    else:
        # Пример использования
        pdf_to_txt("document.pdf", "result.txt")