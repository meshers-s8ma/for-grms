import pytest
from flask import url_for
from app.models.models import Part, User, Stage, RouteTemplate, StatusHistory, AuditLog, Role, Permission
from app import db

class TestCoreWorkflow:
    """Группа тестов для проверки основного рабочего процесса."""

    def test_scan_and_confirm_stage_workflow(self, client, database):
        """Тест: Проверяет подтверждение этапа для детали."""
        part = db.session.get(Part, 'TEST-001')
        assert part.current_status == 'На складе'
        assert part.quantity_completed == 0

        first_stage = Stage.query.filter_by(name='Резка').first()
        assert first_stage is not None

        # Эмулируем POST-запрос с формы
        response = client.post(
            url_for('main.confirm_stage', part_id='TEST-001', stage_id=first_stage.id),
            data={
                'operator_name': 'Тестовый Оператор', 
                'quantity': 1,
                'csrf_token': 'fake-token' # Добавляем фейковый токен, чтобы пройти валидацию
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        # ИСПРАВЛЕНО: Проверяем наличие flash-сообщения в новой верстке
        assert 'Статус для детали TEST-001 обновлен' in response.data.decode('utf-8')

        # Проверяем изменения в базе данных
        part_after_stage1 = db.session.get(Part, 'TEST-001')
        assert part_after_stage1.current_status == 'Резка'
        # В нашей новой логике количество должно прибавляться, а не перезаписываться
        assert part_after_stage1.quantity_completed == 1
        
        history_entry = StatusHistory.query.filter_by(part_id='TEST-001').first()
        assert history_entry is not None
        assert history_entry.status == 'Резка'
        assert history_entry.operator_name == 'Тестовый Оператор'
        assert history_entry.quantity == 1

    def test_select_stage_page_shows_correct_form(self, client, database):
        """Тест: Страница /scan/<part_id> корректно отображает форму подтверждения."""
        response = client.get(url_for('main.select_stage', part_id='TEST-001'))
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        assert 'Следующий этап для выполнения:' in response_text
        assert 'Резка' in response_text # Проверяем, что предложен правильный следующий этап
        assert 'name="quantity"' in response_text
        assert 'name="operator_name"' in response_text
        assert 'Все этапы завершены' not in response_text