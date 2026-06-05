#### Программа преобразования PDF(с текстовым слоем) в TXT
### Способы использования программы:
1. Интерактивный режим (с вопросами)
bash
python pdf_to_txt.py -i
# или просто
python pdf_to_txt.py
2. Командная строка с параметрами
Простое преобразование (автоматический метод):

bash
python pdf_to_txt.py document.pdf
С указанием выходного файла:

bash
python pdf_to_txt.py document.pdf -o result.txt
С выбором конкретного метода:

bash
# Использовать PyPDF2
python pdf_to_txt.py document.pdf -m pypdf2

# Использовать pdfplumber
python pdf_to_txt.py document.pdf -m pdfplumber

# Автоматический выбор
python pdf_to_txt.py document.pdf -m auto
Все параметры вместе:

bash
python pdf_to_txt.py document.pdf -o output.txt -m pdfplumber
3. Просмотр справки
bash
python pdf_to_txt.py -h