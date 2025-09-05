import os
from typing import Type

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Базовый класс конфигурации.
    Содержит общие настройки и константы для переменных окружения.
    """
    # --- Техническое улучшение: Централизация имен переменных ---
    # Теперь, если нужно будет переименовать переменную в .env,
    # достаточно изменить ее в одном месте здесь.
    ENV_FLASK_SECRET_KEY = 'FLASK_SECRET_KEY'
    ENV_DATABASE_URI = 'SQLALCHEMY_DATABASE_URI'

    # --- Чтение переменных окружения ---
    SECRET_KEY = os.environ.get(ENV_FLASK_SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = os.environ.get(ENV_DATABASE_URI)

    # --- Статические настройки приложения ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """
    Конфигурация для локальной разработки.
    Включает режим отладки для подробных сообщений об ошибках.
    """
    DEBUG = True
    # Улучшение для верификации производительности:
    # Позволяет видеть все SQL-запросы в консоли.
    # В обычном режиме можно закомментировать.
    SQLALCHEMY_ECHO = True 


class TestingConfig(Config):
    """
    Конфигурация для запуска автоматических тестов.
    Использует базу данных в памяти для изоляции и скорости.
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # БД в памяти
    SERVER_NAME = 'localhost.localdomain' # Для корректной генерации URL в тестах
    WTF_CSRF_ENABLED = False # Отключаем CSRF-защиту для упрощения тестов
    SECRET_KEY = 'a-secret-key-for-testing-purposes' # Используем постоянный ключ


class ProductionConfig(Config):
    """
    Конфигурация для "боевого" (production) сервера.
    """
    # --- Техническое улучшение: Более строгие настройки ---
    # Явно указываем, что отладка и тестирование должны быть выключены.
    DEBUG = False
    TESTING = False
    
    def __init__(self):
        """
        Конструктор проверяет наличие критически важных переменных окружения.
        """
        super().__init__()
        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError(f"Переменная {self.ENV_DATABASE_URI} не установлена для production-окружения!")
        if not self.SECRET_KEY:
            raise ValueError(f"Переменная {self.ENV_FLASK_SECRET_KEY} не установлена для production-окружения!")

# --- Техническое улучшение: Типизация ---
# Словарь для удобного выбора класса конфигурации по имени
config_by_name: dict[str, Type[Config]] = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}