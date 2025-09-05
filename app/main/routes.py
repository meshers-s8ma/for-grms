# app/main/routes.py

from flask import (Blueprint, render_template, jsonify, request, redirect,
                   url_for, flash, current_app)
from sqlalchemy import func
from sqlalchemy.orm import joinedload 

from datetime import datetime, timezone
# --- НАЧАЛО ИЗМЕНЕНИЯ 1: Импортируем defaultdict ---
from collections import Counter, defaultdict
# --- КОНЕЦ ИЗМЕНЕНИЯ 1 ---

from app import db, socketio
from flask_login import current_user, login_required
from app.models.models import (Part, StatusHistory, AuditLog, RouteTemplate,
                               RouteStage, Stage, PartNote, Permission)
from app.admin.forms import ConfirmStageQuantityForm, AddNoteForm, AddChildPartForm
from app.services import query_service
from app.utils import to_safe_key

main = Blueprint('main', __name__)


def _send_websocket_notification(event_type: str, message: str, part_id: str = None):
    """Централизованная функция для отправки WebSocket-уведомлений."""
    data = {'event': event_type, 'message': message}
    if part_id:
        data['part_id'] = part_id
    socketio.emit('notification', data)


@main.route('/')
def dashboard():
    """
    Главная страница (панель мониторинга).
    Отображает сводную информацию по всем изделиям.
    """
    # Запрос выбирает только "корневые" детали (у которых нет родителя)
    product_progress_query = db.session.query(
        Part.product_designation,
        func.count(Part.part_id).label('total_parts'),
        func.sum(Part.quantity_total).label('total_quantity'),
        func.sum(Part.quantity_completed).label('completed_quantity')
    ).filter(Part.parent_id.is_(None)).group_by(Part.product_designation).all()

    products = [{
        'product_designation': row.product_designation,
        'total_parts': row.total_parts,
        'total_possible_stages': row.total_quantity or 0,
        'total_completed_stages': row.completed_quantity or 0
    } for row in product_progress_query]

    return render_template('dashboard.html', products=products)


@main.route('/api/parts/<path:product_designation>')
def api_parts_for_product(product_designation):
    """
    API-эндпоинт для динамической загрузки списка деталей для изделия.
    """
    parts_query = Part.query.options(
        joinedload(Part.route_template).joinedload(RouteTemplate.stages).joinedload(RouteStage.stage),
        joinedload(Part.responsible)
    ).filter(
        Part.product_designation == product_designation,
        Part.parent_id.is_(None)
    ).order_by(Part.part_id.asc())

    parts_list = []
    for part in parts_query:
        # --- НАЧАЛО ИЗМЕНЕНИЯ 2: Полностью переработана логика расчета статусов ---
        route_stages_data = []
        if part.route_template:
            # Суммируем фактическое количество выполненных изделий по каждому этапу
            completed_quantities = defaultdict(int)
            for h in part.history:
                completed_quantities[h.status] += h.quantity

            ordered_stages = sorted(part.route_template.stages, key=lambda s: s.order)
            
            for rs in ordered_stages:
                stage_name = rs.stage.name
                qty_done = completed_quantities.get(stage_name, 0)
                status = 'pending' # По умолчанию - не начат

                if qty_done >= part.quantity_total:
                    status = 'completed' # Выполнен, если сделано >= общего кол-ва
                elif qty_done > 0:
                    status = 'in_progress' # В процессе, если сделано > 0, но < общего

                route_stages_data.append({
                    'name': stage_name, 
                    'status': status,
                    'qty_done': qty_done
                })
        # --- КОНЕЦ ИЗМЕНЕНИЯ 2 ---
        
        parts_list.append({
            'part_id': part.part_id,
            'name': part.name,
            'material': part.material,
            'current_status': part.current_status,
            'creation_date': part.date_added.strftime('%Y-%m-%d'),
            'quantity_completed': part.quantity_completed,
            'quantity_total': part.quantity_total,
            'history_url': url_for('main.history', part_id=part.part_id),
            'route_stages': route_stages_data,
            'delete_url': url_for('admin.part.delete_part', part_id=part.part_id),
            'edit_url': url_for('admin.part.edit_part', part_id=part.part_id),
            'qr_url': url_for('admin.part.generate_single_qr', part_id=part.part_id),
            'responsible_user': part.responsible.username if part.responsible else 'Не назначен'
        })

    permissions = None
    if current_user.is_authenticated:
        permissions = {
            'can_delete': current_user.can(Permission.DELETE_PARTS),
            'can_edit': current_user.can(Permission.EDIT_PARTS),
            'can_generate_qr': current_user.can(Permission.GENERATE_QR)
        }

    return jsonify({'parts': parts_list, 'permissions': permissions})


@main.route('/history/<path:part_id>')
def history(part_id):
    """Страница с полной историей одной детали."""
    part = db.get_or_404(Part, part_id)
    combined_history = query_service.get_combined_history(part)
    note_form = AddNoteForm()
    child_form = AddChildPartForm()

    if part.route_template:
        note_form.stage.query = db.session.query(Stage).join(RouteStage).filter(
            RouteStage.template_id == part.route_template_id
        ).order_by(Stage.name)
    else:
        note_form.stage.query = db.session.query(Stage).filter_by(id=-1)

    return render_template(
        'history.html', part=part, combined_history=combined_history,
        note_form=note_form, child_form=child_form
    )


@main.route('/scan/<path:part_id>')
def select_stage(part_id):
    """Страница, открывающаяся после сканирования QR-кода."""
    part = db.get_or_404(Part, part_id)
    if not part.route_template:
        flash('Ошибка: Этой детали не присвоен технологический маршрут.', 'error')
        return redirect(url_for('main.dashboard'))

    # --- НАЧАЛО ИЗМЕНЕНИЯ 3: Исправлена логика определения следующего этапа ---
    completed_quantities = defaultdict(int)
    for h in part.history:
        completed_quantities[h.status] += h.quantity
        
    ordered_stages = sorted(part.route_template.stages, key=lambda s: s.order)
    next_stage_obj = None
    for rs in ordered_stages:
        # Ищем первый этап, на котором выполнено меньше, чем общее количество
        if completed_quantities.get(rs.stage.name, 0) < part.quantity_total:
            next_stage_obj = rs.stage
            break
    # --- КОНЕЦ ИЗМЕНЕНИЯ 3 ---

    form = ConfirmStageQuantityForm()
    if next_stage_obj and form.quantity.data is None:
        remaining = part.quantity_total - part.quantity_completed
        form.quantity.data = remaining if remaining > 0 else 1

    return render_template(
        'select_stage.html', part=part, next_stage=next_stage_obj, form=form
    )


@main.route('/confirm_stage/<path:part_id>/<int:stage_id>', methods=['POST'])
def confirm_stage(part_id, stage_id):
    """Обрабатывает подтверждение завершения этапа."""
    part = db.get_or_404(Part, part_id)
    stage = db.get_or_404(Stage, stage_id)
    form = ConfirmStageQuantityForm()

    if form.validate_on_submit():
        quantity_done = form.quantity.data
        
        # --- НАЧАЛО ИЗМЕНЕНИЯ 4: Более точная проверка остатка ---
        completed_on_this_stage = db.session.query(func.sum(StatusHistory.quantity)).filter_by(part_id=part.part_id, status=stage.name).scalar() or 0
        remaining_on_stage = part.quantity_total - completed_on_this_stage
        
        if quantity_done > remaining_on_stage:
            flash(f'Ошибка: Нельзя выполнить {quantity_done} шт. '
                  f'На этом этапе осталось {remaining_on_stage} шт.', 'error')
            return redirect(url_for('main.select_stage', part_id=part.part_id))
        # --- КОНЕЦ ИЗМЕНЕНИЯ 4 ---

        part.quantity_completed += quantity_done
        part.current_status = stage.name
        part.last_update = datetime.now(timezone.utc)

        new_history = StatusHistory(
            part_id=part_id,
            status=stage.name,
            operator_name=form.operator_name.data,
            quantity=quantity_done
        )
        db.session.add(new_history)
        db.session.commit()

        # Отправляем событие на обновление дашборда
        socketio.emit('update_dashboard', {
            'part_id': part.part_id,
            'new_status': part.current_status,
            'quantity_completed': part.quantity_completed,
            'quantity_total': part.quantity_total,
            'product_designation': part.product_designation,
            'safe_key': to_safe_key(part.product_designation)
        })

        # Отправляем "тост"-уведомление всем пользователям
        _send_websocket_notification(
            'stage_completed',
            f"Деталь {part_id} перешла на этап '{stage.name}'.",
            part.part_id
        )

        flash(f"Статус для детали {part_id} обновлен на '{stage.name}'! "
              f"Готово: {quantity_done} шт.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template(
        'select_stage.html', part=part, next_stage=stage, form=form
    )


@main.route('/add_note/<path:part_id>', methods=['POST'])
@login_required
def add_note(part_id):
    """Обрабатывает добавление примечания к детали."""
    part = db.get_or_404(Part, part_id)
    form = AddNoteForm()
    # Динамически заполняем поле выбора этапов
    if part.route_template:
        form.stage.query = db.session.query(Stage).join(RouteStage).filter(
            RouteStage.template_id == part.route_template_id
        ).order_by(Stage.name)
    else:
        form.stage.query = db.session.query(Stage).filter_by(id=-1)

    if form.validate_on_submit():
        stage_obj = form.stage.data
        new_note = PartNote(
            part_id=part.part_id,
            user_id=current_user.id,
            text=form.text.data,
            stage_id=stage_obj.id if stage_obj else None
        )
        db.session.add(new_note)

        log_details = f"К детали '{part.part_id}' добавлено примечание."
        log_entry = AuditLog(
            user_id=current_user.id, action="Добавлено примечание",
            details=log_details, category='part', part_id=part.part_id
        )
        db.session.add(log_entry)
        db.session.commit()
        flash('Примечание успешно добавлено.', 'success')
    else:
        error_messages = [e for field, errors in form.errors.items() for e in errors]
        flash('Ошибка: ' + ' '.join(error_messages), 'error')

    return redirect(url_for('main.history', part_id=part.part_id))


@main.route('/edit_note/<int:note_id>', methods=['POST'])
@login_required
def edit_note(note_id):
    """Обрабатывает редактирование существующего примечания."""
    note = db.get_or_404(PartNote, note_id)
    if note.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'status': 'error', 'message': 'Нет прав'}), 403

    new_text = request.form.get('text')
    if new_text and new_text.strip():
        note.text = new_text
        log_details = f"В детали '{note.part_id}' изменено примечание (ID: {note.id})."
        log_entry = AuditLog(
            user_id=current_user.id, action="Изменено примечание",
            details=log_details, category='management', part_id=note.part_id
        )
        db.session.add(log_entry)
        db.session.commit()
        # --- НАЧАЛО ИЗМЕНЕНИЯ 5: Возвращаем JSON вместо редиректа ---
        return jsonify({'status': 'success', 'message': 'Примечание обновлено.', 'new_text': new_text})
        # --- КОНЕЦ ИЗМЕНЕНИЯ 5 ---
    else:
        # --- НАЧАЛО ИЗМЕНЕНИЯ 6: Возвращаем JSON об ошибке ---
        return jsonify({'status': 'error', 'message': 'Текст не может быть пустым.'}), 400
        # --- КОНЕЦ ИЗМЕНЕНИЯ 6 ---


@main.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    """Обрабатывает удаление примечания."""
    note = db.get_or_404(PartNote, note_id)
    if note.user_id != current_user.id and not current_user.is_admin():
        flash('У вас нет прав для удаления этого примечания.', 'error')
        return redirect(url_for('main.history', part_id=note.part_id))

    part_id = note.part_id
    log_details = f"В детали '{part_id}' удалено примечание (ID: {note.id})."
    log_entry = AuditLog(
        user_id=current_user.id, action="Удалено примечание",
        details=log_details, category='management', part_id=part_id
    )
    db.session.add(log_entry)

    db.session.delete(note)
    db.session.commit()
    flash('Примечание удалено.', 'success')
    return redirect(url_for('main.history', part_id=part_id))