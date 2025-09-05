
# app/__init__.py

import os
import re
import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import DevelopmentConfig
from flask_wtf.csrf import CSRFProtect
from jinja2 import pass_eval_context
from markupsafe import Markup, escape
from flask_socketio import SocketIO
from whitenoise import WhiteNoise

# Глобально создаем экземпляры, но не настраиваем их
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate(render_as_batch=True)
csrf = CSRFProtect()
socketio = SocketIO()

def create_app(config_class=DevelopmentConfig):
    
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class())

    # --- ИЗМЕНЕНИЕ: Указываем правильный, КОРОТКИЙ путь к папке static ---
    # Структура: /app (WORKDIR) -> /app/static (цель)
    app.wsgi_app = WhiteNoise(app.wsgi_app, root='app/static/')
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # Инициализируем расширения с нашим приложением
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    socketio.init_app(app)

    # Настраиваем login manager
    login_manager.login_view = 'admin.user.login'
    login_manager.login_message = "Пожалуйста, войдите в систему для доступа к этой странице."
    login_manager.login_message_category = "error"
    from .models.models import AnonymousUser
    login_manager.anonymous_user = AnonymousUser

    with app.app_context():
        
        # --- Создание папок ---
        try:
            os.makedirs(app.instance_path)
        except OSError:
            pass
        app.config.update(
            UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads'),
            DRAWING_UPLOAD_FOLDER = os.path.join(app.instance_path, 'drawings')
        )
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        if not os.path.exists(app.config['DRAWING_UPLOAD_FOLDER']):
            os.makedirs(app.config['DRAWING_UPLOAD_FOLDER'])

        # --- РЕГИСТРАЦИЯ БЛЮПРИНТОВ ---
        from .main.routes import main as main_blueprint
        app.register_blueprint(main_blueprint)

        from .admin import admin_bp as admin_blueprint
        app.register_blueprint(admin_blueprint)

        # --- Контекстные процессоры и фильтры ---
        from .utils import to_safe_key
        from .admin.forms import get_stages as get_stages_query
        from .models.models import Permission
        @app.context_processor
        def utility_processor():
            def get_stages_for_template():
                stages_objects = get_stages_query()
                return [{'id': stage.id, 'name': stage.name} for stage in stages_objects]
            
            # Добавляем в контекст функцию, возвращающую текущее время в UTC
            return dict(
                to_safe_key=to_safe_key,
                get_stages=get_stages_for_template,
                Permission=Permission,
                now=datetime.datetime.utcnow  # Делаем datetime доступным в шаблонах
            )

        _paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')
        @app.template_filter()
        @pass_eval_context
        def nl2br(eval_ctx, value):
            result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br>\n') \
                for p in _paragraph_re.split(escape(value)))
            if eval_ctx.autoescape:
                result = Markup(result)
            return result

        # --- Загрузчик пользователя ---
        from .models.models import User
        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        # --- Регистрация CLI команд ---
        from . import commands
        app.cli.add_command(commands.seed_command)

    # Возвращаем оба объекта для использования в run.py
    return app, socketio