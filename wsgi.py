# wsgi.py

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

from app import create_app
from config import config_by_name

load_dotenv()

config_name = os.environ.get('FLASK_ENV', 'development')
try:
    config_class = config_by_name[config_name]
except KeyError:
    sys.exit(f"Ошибка: Неверное имя конфигурации '{config_name}'.")

app, socketio = create_app(config_class)

# --- Настройка логирования ---
if not app.debug:
    log_dir = os.path.join(app.instance_path, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file_path = os.path.join(log_dir, 'app.log')
    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=10485760, backupCount=5, encoding='utf-8'
    )
    log_format = '%(asctime)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
    file_handler.setFormatter(logging.Formatter(log_format))
    app.logger.addHandler(file_handler)
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    app.logger.setLevel(log_level)
    app.logger.info('Product Tracker application startup')