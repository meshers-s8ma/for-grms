
# tests/test_admin_routes.py

import pytest
from flask import url_for
from io import BytesIO

from app import db
from app.models.models import Part, User, Stage, RouteTemplate, Role, Permission


class TestAdminCRUD:
    """Группа тестов для всех CRUD-операций в админ-панели."""

    def test_create_and_delete_stage(self, client, auth_client, database):
        """Тест: Администратор может создать и удалить этап."""
        auth_client('admin')  # Выполняем вход

        # Создание
        response_add = client.post(
            url_for('admin.management.add_stage'),
            data={'name': 'New Stage From Test', 'csrf_token': 'fake-token'},
            follow_redirects=True
        )
        assert response_add.status_code == 200
        assert 'New Stage From Test' in response_add.data.decode('utf-8')

        new_stage = Stage.query.filter_by(name='New Stage From Test').first()
        assert new_stage is not None

        # Удаление
        client.post(
            url_for('admin.management.delete_stage', stage_id=new_stage.id),
            data={'csrf_token': 'fake-token'},
            follow_redirects=True
        )

        deleted_stage = Stage.query.filter_by(name='New Stage From Test').first()
        assert deleted_stage is None

    def test_create_route_successfully(self, auth_client, database):
        """Тест: Администратор может успешно создать маршрут."""
        client = auth_client('admin')
        stage1 = Stage.query.filter_by(name='Test Stage 1').first()
        stage2 = Stage.query.filter_by(name='Test Stage 2').first()

        form_data = {
            'name': 'My New Test Route',
            'is_default': 'y',
            'stages': [stage1.id, stage2.id],
            'csrf_token': 'fake-token'
        }
        response = client.post(
            url_for('admin.management.add_route'),
            data=form_data,
            follow_redirects=True
        )
        assert response.status_code == 200
        assert 'Новый технологический маршрут успешно создан.' in response.data.decode('utf-8')

        new_route = RouteTemplate.query.filter_by(name='My New Test Route').first()
        assert new_route is not None
        assert new_route.is_default is True

        route_stages = sorted(new_route.stages, key=lambda s: s.order)
        assert len(route_stages) == 2
        assert route_stages[0].stage_id == stage1.id
        assert route_stages[1].stage_id == stage2.id

    def test_create_part_with_quantity_and_drawing(self, auth_client, app, database):
        """Тест: Администратор может создать деталь с количеством и чертежом."""
        client = auth_client('admin')
        drawing_file = (BytesIO(b"this is a fake image"), 'test_drawing.jpg')
        route = RouteTemplate.query.filter_by(name='Стандартный маршрут').first()

        data = {
            'product': 'Изделие с чертежом',
            'part_id': 'DRAW-001',
            'name': 'Кронштейн тестовый',
            'material': 'Сталь 45',
            'quantity_total': 50,
            'route_template': route.id,
            'drawing': drawing_file,
            'csrf_token': 'fake-token'
        }

        response = client.post(
            url_for('admin.part.add_single_part'),
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert "Успешно добавлена деталь: DRAW-001" in response.data.decode('utf-8')

        new_part = db.session.get(Part, 'DRAW-001')
        assert new_part is not None
        assert new_part.quantity_total == 50
        assert 'test_drawing.jpg' in new_part.drawing_filename
        assert new_part.name == 'Кронштейн тестовый'
        assert new_part.material == 'Сталь 45'

    def test_create_and_delete_user(self, auth_client, database):
        """Тест: Администратор может создать и удалить пользователя."""
        client = auth_client('admin')
        operator_role_id = Role.query.filter_by(name='Operator').first().id
        user_data = {
            'username': 'new_worker',
            'password': 'new_password123',
            'role': operator_role_id,
            'csrf_token': 'fake-token'
        }
        response_add = client.post(
            url_for('admin.user.add_user'),
            data=user_data,
            follow_redirects=True
        )
        assert 'Пользователь new_worker успешно создан' in response_add.data.decode('utf-8')

        new_user = User.query.filter_by(username='new_worker').first()
        assert new_user is not None

        response_delete = client.post(
            url_for('admin.user.delete_user', user_id=new_user.id),
            data={'csrf_token': 'fake-token'},
            follow_redirects=True
        )
        assert 'Пользователь new_worker удален' in response_delete.data.decode('utf-8')

        assert User.query.filter_by(username='new_worker').first() is None

    def test_create_user_with_duplicate_username_fails(self, auth_client, database):
        """
        Тест "несчастливого пути": Проверяет, что система не позволяет создать
        пользователя с именем, которое уже существует.
        """
        # Arrange (Подготовка)
        client = auth_client('admin')
        operator_role_id = Role.query.filter_by(name='Operator').first().id
        initial_user_count = User.query.count()
        
        # Данные нового пользователя с уже существующим именем 'admin'
        duplicate_user_data = {
            'username': 'admin', # Имя, которое уже занято
            'password': 'some_password',
            'role': operator_role_id,
            'csrf_token': 'fake-token'
        }

        # Act (Действие)
        response = client.post(
            url_for('admin.user.add_user'),
            data=duplicate_user_data,
            follow_redirects=True
        )

        # Assert (Проверка)
        assert response.status_code == 200 # Страница должна просто перезагрузиться
        # Проверяем наличие flash-сообщения об ошибке
        assert 'Пользователь с таким именем уже существует.' in response.data.decode('utf-8')
        # Проверяем, что количество пользователей в базе данных не изменилось
        assert User.query.count() == initial_user_count


class TestAdvancedFeatures:
    """Группа тестов для API, массовых действий и т.д."""

    def test_api_reports_return_json(self, auth_client, database):
        """Тест: API для отчетов возвращают корректный JSON."""
        client = auth_client('admin')
        response_op = client.get(url_for('admin.report.api_report_operator_performance'))
        assert response_op.status_code == 200
        assert response_op.is_json

        response_dur = client.get(url_for('admin.report.api_report_stage_duration'))
        assert response_dur.status_code == 200
        assert response_dur.is_json

    def test_bulk_delete_action(self, auth_client, database):
        """Тест: Массовое удаление деталей работает корректно."""
        client = auth_client('admin')
        route = RouteTemplate.query.filter_by(name='Стандартный маршрут').first()

        p1 = Part(part_id='BULK-001', product_designation='Bulk Test',
                  name='Bulk Part 1', material='Ст3', route_template_id=route.id)
        p2 = Part(part_id='BULK-002', product_designation='Bulk Test',
                  name='Bulk Part 2', material='Ст3', route_template_id=route.id)

        db.session.add_all([p1, p2])
        db.session.commit()

        delete_data = {
            'action': 'delete',
            'part_ids': ['BULK-001', 'BULK-002'],
            'csrf_token': 'fake-token'
        }
        response = client.post(
            url_for('admin.part.bulk_action'),
            data=delete_data,
            follow_redirects=True
        )
        assert response.status_code == 200
        assert 'Успешно удалено 2 деталей.' in response.data.decode('utf-8')

        assert db.session.get(Part, 'BULK-001') is None
        assert db.session.get(Part, 'BULK-002') is None


class TestHierarchyFeatures:
    """Группа тестов для проверки функционала иерархии деталей."""

    def test_add_child_part_successfully(self, auth_client, database):
        """Тест: Администратор может успешно добавить дочерний узел к существующей детали."""
        client = auth_client('admin')

        form_data = {
            'part_id': 'CHILD-001',
            'name': 'Дочерний узел',
            'material': 'Алюминий',
            'quantity_total': 2,
            'csrf_token': 'fake-token'
        }

        response = client.post(
            url_for('admin.part.add_child_part', parent_part_id='TEST-001'),
            data=form_data,
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Новый узел успешно добавлен' in response.data.decode('utf-8')

        child_part = db.session.get(Part, 'CHILD-001')
        assert child_part is not None
        assert child_part.name == 'Дочерний узел'
        assert child_part.material == 'Алюминий'
        assert child_part.quantity_total == 2
        assert child_part.parent_id == 'TEST-001'

    def test_delete_parent_part_cascades_to_children(self, auth_client, database):
        """Тест: Удаление родительской детали должно автоматически удалять все дочерние."""
        client = auth_client('admin')

        parent = Part(part_id='PARENT-CASCADE', product_designation='Родитель для удаления',
                      name='Родитель', material='Чугун')
        child = Part(part_id='CHILD-CASCADE', product_designation='Родитель для удаления',
                     name='Дочерний', material='Чугун', parent_id='PARENT-CASCADE')

        db.session.add_all([parent, child])
        db.session.commit()

        assert db.session.get(Part, 'PARENT-CASCADE') is not None
        assert db.session.get(Part, 'CHILD-CASCADE') is not None

        response = client.post(
            url_for('admin.part.delete_part', part_id='PARENT-CASCADE'),
            data={'csrf_token': 'fake-token'},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert 'Деталь PARENT-CASCADE и вся ее история удалены' in response.data.decode('utf-8')

        assert db.session.get(Part, 'PARENT-CASCADE') is None
        assert db.session.get(Part, 'CHILD-CASCADE') is None