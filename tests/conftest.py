# tests/conftest.py

import pytest
import sys
import os
from flask import url_for

# Добавляем корневую папку проекта в путь Python, чтобы импорты работали
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from config import TestingConfig
from app.models.models import User, Stage, RouteTemplate, RouteStage, Part, Role


@pytest.fixture(scope='module')
def app():
    """
    Создает и настраивает новый экземпляр приложения для каждого тестового модуля.
    """
    # create_app теперь возвращает кортеж (app, socketio).
    # Для тестов нам нужен только первый элемент - само Flask-приложение.
    flask_app, _ = create_app(TestingConfig)
    return flask_app


@pytest.fixture(scope='module')
def client(app):
    """Предоставляет тестовый клиент для Flask-приложения."""
    return app.test_client()


@pytest.fixture(scope='function')
def database(app):
    """
    Создает чистую базу данных для каждого теста и наполняет ее
    минимально необходимыми данными.
    """
    with app.app_context():
        db.create_all()

        Role.insert_roles()

        admin_role = Role.query.filter_by(name='Administrator').first()
        manager_role = Role.query.filter_by(name='Manager').first()
        operator_role = Role.query.filter_by(name='Operator').first()

        admin = User(username='admin', role=admin_role)
        admin.set_password('password123')
        
        manager = User(username='manager', role=manager_role)
        manager.set_password('password123')
        
        operator = User(username='operator', role=operator_role)
        operator.set_password('password123')

        stage1 = Stage(name='Резка')
        stage2 = Stage(name='Сверловка')
        stage3 = Stage(name='Контроль ОТК')
        test_stage1 = Stage(name='Test Stage 1')
        test_stage2 = Stage(name='Test Stage 2')
        route1 = RouteTemplate(name='Стандартный маршрут', is_default=True)
        
        db.session.add_all([admin, manager, operator, stage1, stage2, stage3,
                            test_stage1, test_stage2, route1])
        db.session.commit()

        rs1 = RouteStage(template_id=route1.id, stage_id=stage1.id, order=0)
        rs2 = RouteStage(template_id=route1.id, stage_id=stage2.id, order=1)
        rs3 = RouteStage(template_id=route1.id, stage_id=stage3.id, order=2)
        
        # --- ИЗМЕНЕНИЕ: Добавлены обязательные поля name и material ---
        part1 = Part(
            part_id='TEST-001',
            product_designation='Тестовое изделие',
            name='Крышка тестовая',
            material='Ст3',
            route_template_id=route1.id
        )
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        db.session.add_all([rs1, rs2, rs3, part1])
        db.session.commit()
        
        yield db
        
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def auth_client(client, app, database):
    """
    Фикстура для создания аутентифицированного клиента.
    """
    def login(username='admin', password='password123'):
        with app.app_context():
            # Используем поддельный CSRF-токен, т.к. CSRF-защита в тестах отключена
            client.post(
                url_for('admin.user.login'),
                data={'username': username, 'password': password, 'csrf_token': 'fake-token'},
                follow_redirects=True
            )
        return client
    
    yield login
    
    # После выполнения теста выходим из системы, чтобы очистить сессию
    with app.app_context():
        client.get(url_for('admin.user.logout'))