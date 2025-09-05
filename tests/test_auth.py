import pytest
from flask import url_for
from app.models.models import Permission
from app import db

class TestAccessAndAuth:
    """Группа тестов для проверки доступа и аутентификации."""

    def test_dashboard_access_for_guest(self, client, database):
        """Тест: Гость может получить доступ к главной панели."""
        response = client.get(url_for('main.dashboard'))
        assert response.status_code == 200
        assert 'Панель мониторинга' in response.data.decode('utf-8')

    def test_admin_pages_require_login(self, client, database):
        """Тест: Гость перенаправляется с защищенных админ-страниц на страницу входа."""
        admin_pages = [
            'admin.user.list_users',
            'admin.management.list_routes',
            'admin.management.list_stages'
        ]
        for page in admin_pages:
            response = client.get(url_for(page), follow_redirects=True)
            assert response.status_code == 200
            assert 'Вход в систему' in response.data.decode('utf-8')
            assert 'Пожалуйста, войдите в систему' in response.data.decode('utf-8')

    def test_login_and_logout(self, client, database):
        """Тест: Администратор может успешно войти и выйти из системы."""
        # Вход
        response_login = client.post(url_for('admin.user.login'), data={
            'username': 'admin',
            'password': 'password123',
            'csrf_token': 'fake-token'
        }, follow_redirects=True)
        assert response_login.status_code == 200
        assert 'Вы успешно вошли в систему!' in response_login.data.decode('utf-8')
        assert 'admin (Administrator)' in response_login.data.decode('utf-8')

        # Выход
        response_logout = client.get(url_for('admin.user.logout'), follow_redirects=True)
        assert response_logout.status_code == 200
        assert 'Вы вышли из системы.' in response_logout.data.decode('utf-8')
        assert 'Войти' in response_logout.data.decode('utf-8')

    def test_manager_cannot_access_user_management(self, auth_client, database):
        """Тест: Пользователь с ролью 'Manager' не может управлять пользователями."""
        client = auth_client(username='manager', password='password123')
        
        # Делаем запрос БЕЗ follow_redirects, чтобы проверить сам редирект
        response = client.get(url_for('admin.user.list_users'))
        
        # 1. Проверяем, что сервер вернул статус 302 (Found - это стандартный редирект)
        assert response.status_code == 302
        
        # 2. Проверяем, что он перенаправляет нас именно на дашборд
        # Генерируем относительный URL для сравнения
        expected_path = url_for('main.dashboard', _external=False)
        assert response.location.endswith(expected_path)