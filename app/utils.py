import os
import re
import qrcode
from io import BytesIO
import base64

def create_safe_file_name(name):
    """
    Создает безопасное имя файла, заменяя недопустимые для Windows/Linux символы.
    """
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def generate_qr_code(part_id):
    """
    Генерирует QR-код и возвращает его как объект BytesIO в оперативной памяти.
    Это позволяет отдавать файл напрямую пользователю без сохранения на диске.
    Возвращает объект BytesIO в случае успеха или None в случае ошибки.
    """
    # --- НАЧАЛО ИЗМЕНЕНИЯ 2.3.2 ---
    
    # IP-адрес берется из переменной окружения. Если ее нет, используется '127.0.0.1'.
    SERVER_PUBLIC_IP = os.environ.get("SERVER_PUBLIC_IP", "127.0.0.1")
    # Порт теперь тоже берется из переменной окружения. По умолчанию '5000'.
    SERVER_PORT = os.environ.get("SERVER_PORT", "5000")

    url = f"http://{SERVER_PUBLIC_IP}:{SERVER_PORT}/scan/{part_id}"
    
    # --- КОНЕЦ ИЗМЕНЕНИЯ 2.3.2 ---
    
    try:
        qr_img = qrcode.make(url)
        
        img_buffer = BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        print(f"  -> QR-код для детали {part_id} сгенерирован в памяти.")
        return img_buffer
    except Exception as e:
        print(f"  -> ОШИБКА создания QR-кода для {part_id}: {e}")
        return None

def generate_qr_code_as_base64(part_id):
    """
    Генерирует QR-код и возвращает его как строку Base64 Data URI,
    готовую для вставки в HTML-тег <img src="...">.
    """
    img_buffer = generate_qr_code(part_id)
    
    if img_buffer:
        encoded_string = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"
        
    return None

def to_safe_key(text):
    """
    Преобразует текст (например, название изделия) в безопасный для использования
    в URL и как HTML id/class. Транслитерирует кириллицу и заменяет
    недопустимые символы на подчеркивание.
    """
    text = text.lower()
    translit = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
        'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
        'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c',
        'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    }
    for char, repl in translit.items():
        text = text.replace(char, repl)
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')