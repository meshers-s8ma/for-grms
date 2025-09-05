# app/admin/__init__.py (ФИНАЛЬНАЯ ПОЛНАЯ ВЕРСЯ С ПРЕФИКСАМИ)

from flask import Blueprint

# Создаем главный "сборный" блюпринт для всей админки
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Импортируем дочерние блюприенты
from .routes.management_routes import management_bp
from .routes.part_routes import part_bp
from .routes.report_routes import report_bp
from .routes.user_routes import user_bp

# Регистрируем каждый дочерний блюпринт внутри нашего главного,
# добавляя им свои собственные префиксы URL для лучшей организации.
admin_bp.register_blueprint(management_bp) # Этот останется доступен по /admin/
admin_bp.register_blueprint(part_bp, url_prefix='/part') # Будет доступен по /admin/part/
admin_bp.register_blueprint(report_bp, url_prefix='/report') # Будет доступен по /admin/report/
admin_bp.register_blueprint(user_bp, url_prefix='/user') # Будет доступен по /admin/user/```