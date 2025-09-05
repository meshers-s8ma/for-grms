
# app/services/part_service.py

import os
import csv
import io
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from PIL import Image

from app import db, socketio
from app.models.models import (Part, AuditLog, RouteTemplate, ResponsibleHistory,
                               User, StatusHistory, Stage, RouteStage)
from app.utils import generate_qr_code_as_base64


def _send_websocket_notification(event_type: str, message: str, part_id: str = None):
    """Централизованная функция для отправки WebSocket-уведомлений."""
    data = {'event': event_type, 'message': message}
    if part_id:
        data['part_id'] = part_id
    socketio.emit('notification', data)


def save_part_drawing(file_storage, config):
    """
    Безопасно сохраняет файл чертежа, сжимая его, и возвращает уникальное имя.
    """
    filename = secure_filename(file_storage.filename)
    unique_filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{filename}"
    file_path = os.path.join(config['DRAWING_UPLOAD_FOLDER'], unique_filename)

    try:
        img = Image.open(file_storage)
        img.save(file_path, optimize=True, quality=85)
        return unique_filename
    except Exception:
        file_storage.seek(0)
        file_storage.save(file_path)
        return unique_filename


def create_single_part(form, user, config):
    """
    Создает одну деталь на основе данных из формы, включая новые поля.
    """
    drawing_filename = None
    if form.drawing.data:
        drawing_filename = save_part_drawing(form.drawing.data, config)
    
    # ПРИМЕЧАНИЕ: В форме PartForm должны быть поля name и material.
    new_part = Part(
        part_id=form.part_id.data,
        product_designation=form.product.data,
        name=form.name.data, # Новое поле
        material=form.material.data, # Новое поле
        route_template_id=form.route_template.data,
        drawing_filename=drawing_filename,
        quantity_total=form.quantity_total.data
    )
    db.session.add(new_part)
    
    log_entry = AuditLog(part_id=new_part.part_id, user_id=user.id, action="Создание", details="Деталь создана вручную.", category='part')
    db.session.add(log_entry)
    db.session.commit()
    
    _send_websocket_notification(
        'part_created',
        f"Пользователь {user.username} создал деталь: {new_part.part_id}",
        new_part.part_id
    )


def import_parts_from_excel(file_storage, user, config):
    """
    Обрабатывает загруженный Excel/CSV файл с иерархической структурой
    для массового импорта изделий и их составных частей.
    """
    added_count = 0
    skipped_count = 0
    current_product_designation = "Без названия"
    
    # Читаем файл как текст и декодируем
    content = file_storage.read().decode('utf-8')
    reader = csv.reader(io.StringIO(content))
    
    # Пропускаем первые 2 строки заголовка файла
    next(reader, None)
    product_header_row = next(reader, None)
    if product_header_row and len(product_header_row) > 1 and product_header_row[1]:
        current_product_designation = product_header_row[1]

    headers_row = next(reader, None)
    if not headers_row or "Обозначение" not in headers_row:
        raise ValueError("Не найдены заголовки. Ожидается строка с 'Обозначение', 'Наименование' и т.д.")
        
    header_map = {header: i for i, header in enumerate(headers_row)}

    for row in reader:
        if not any(row): continue # Пропускаем полностью пустые строки

        part_id = row[header_map.get("Обозначение")].strip()
        name = row[header_map.get("Наименование")].strip()

        if not part_id or not name:
            skipped_count += 1
            continue

        if db.session.get(Part, part_id):
            skipped_count += 1
            continue
            
        material = row[header_map.get("Прим", "")].strip()
        if not material:
            material = "Не указан" # Заглушка, т.к. поле обязательное

        operations_str = row[header_map.get("Операции", "")].strip()
        route_template_id = _get_or_create_route_from_operations(operations_str).id

        new_part = Part(
            part_id=part_id,
            product_designation=current_product_designation,
            name=name,
            quantity_total=int(row[header_map.get("Кол-во")] or 1),
            size=row[header_map.get("Размер", "")].strip(),
            material=material,
            route_template_id=route_template_id
        )
        db.session.add(new_part)
        
        log_entry = AuditLog(
            part_id=part_id, user_id=user.id, action="Создание",
            details=f"Деталь импортирована из файла {file_storage.filename}.",
            category='part'
        )
        db.session.add(log_entry)
        added_count += 1

    db.session.commit()
    
    _send_websocket_notification(
        'import_finished',
        f"Пользователь {user.username} импортировал {added_count} новых деталей."
    )
    
    return added_count, skipped_count


def _get_or_create_route_from_operations(operations_str: str) -> RouteTemplate:
    """
    Находит существующий маршрут по строке операций или создает новый.
    Также создает недостающие этапы в справочнике.
    """
    if not operations_str:
        default_route = RouteTemplate.query.filter_by(is_default=True).first()
        if not default_route:
            raise ValueError("Не найден маршрут по умолчанию для деталей без указания операций.")
        return default_route

    # Создаем каноничное имя для маршрута
    operations = [op.strip() for op in operations_str.split(',')]
    route_name = " -> ".join(operations)
    
    route = RouteTemplate.query.filter_by(name=route_name).first()
    if route:
        return route

    # Создаем новый маршрут
    new_route = RouteTemplate(name=route_name, is_default=False)
    db.session.add(new_route)
    
    for i, op_name in enumerate(operations):
        stage = Stage.query.filter(Stage.name.ilike(op_name)).first()
        if not stage:
            stage = Stage(name=op_name)
            db.session.add(stage)
        
        # Предварительно коммитим, чтобы получить ID
        db.session.flush()

        route_stage = RouteStage(template_id=new_route.id, stage_id=stage.id, order=i)
        db.session.add(route_stage)

    return new_route

def update_part_from_form(part, form, user, config):
    """
    Обновляет данные детали на основе формы, обрабатывает чертеж и логирует.
    """
    changes = []
    if part.product_designation != form.product_designation.data:
        changes.append(f"Изделие: '{part.product_designation}' -> '{form.product_designation.data}'")
        part.product_designation = form.product_designation.data
    
    # Предполагается, что в EditPartForm добавлены поля name, material, size
    if hasattr(form, 'name') and part.name != form.name.data:
        changes.append(f"Наименование: '{part.name}' -> '{form.name.data}'")
        part.name = form.name.data

    if hasattr(form, 'material') and part.material != form.material.data:
        changes.append(f"Материал: '{part.material}' -> '{form.material.data}'")
        part.material = form.material.data

    if hasattr(form, 'size') and part.size != form.size.data:
        changes.append(f"Размер: '{part.size}' -> '{form.size.data}'")
        part.size = form.size.data

    if form.drawing.data:
        if part.drawing_filename:
            old_file_path = os.path.join(config['DRAWING_UPLOAD_FOLDER'], part.drawing_filename)
            if os.path.exists(old_file_path): os.remove(old_file_path)
        
        part.drawing_filename = save_part_drawing(form.drawing.data, config)
        changes.append("Обновлен чертеж.")

    if changes:
        log_details = "; ".join(changes)
        log_entry = AuditLog(part_id=part.part_id, user_id=user.id, action="Редактирование", details=log_details, category='part')
        db.session.add(log_entry)
        db.session.commit()
        _send_websocket_notification(
            'part_updated',
            f"Пользователь {user.username} обновил данные детали {part.part_id}",
            part.part_id
        )

def delete_single_part(part, user, config):
    """
    Удаляет одну деталь, связанный чертеж и создает запись в логе.
    """
    part_id = part.part_id
    if part.drawing_filename:
        file_path = os.path.join(config['DRAWING_UPLOAD_FOLDER'], part.drawing_filename)
        if os.path.exists(file_path): os.remove(file_path)
            
    log_entry = AuditLog(part_id=part_id, user_id=user.id, action="Удаление", details=f"Деталь '{part_id}' и вся ее история были удалены.", category='part')
    db.session.add(log_entry)
    db.session.delete(part)
    db.session.commit()
    
    _send_websocket_notification(
        'part_deleted',
        f"Пользователь {user.username} удалил деталь: {part_id}",
        part_id
    )

def change_part_route(part, new_route, user):
    """Меняет технологический маршрут для детали и логирует действие."""
    if part.route_template_id != new_route.id:
        old_route_name = part.route_template.name if part.route_template else "Не назначен"
        part.route_template_id = new_route.id
        
        log_details = f"Маршрут изменен с '{old_route_name}' на '{new_route.name}'."
        log_entry = AuditLog(part_id=part.part_id, user_id=user.id, action="Редактирование", details=log_details, category='part')
        db.session.add(log_entry)
        db.session.commit()
        
        _send_websocket_notification(
            'part_updated',
            f"Для детали {part.part_id} изменен маршрут.",
            part.part_id
        )
        return True
    return False

def change_responsible_user(part, new_user, current_user):
    """Меняет ответственного пользователя для детали и логирует действие."""
    old_responsible_id = part.responsible_id
    new_responsible_id = new_user.id if new_user else None

    if old_responsible_id != new_responsible_id:
        old_user_name = part.responsible.username if part.responsible else "Не назначен"
        new_user_name = new_user.username if new_user else "Не назначен"
        part.responsible_id = new_responsible_id
        
        db.session.add(ResponsibleHistory(part_id=part.part_id, user_id=new_responsible_id))
        
        log_details = f"Ответственный изменен с '{old_user_name}' на '{new_user_name}'."
        log_entry = AuditLog(part_id=part.part_id, user_id=current_user.id, action="Смена ответственного", details=log_details, category='management')
        db.session.add(log_entry)
        db.session.commit()
        
        _send_websocket_notification(
            'part_updated',
            f"Для детали {part.part_id} сменен ответственный.",
            part.part_id
        )
        return True
    return False

# --- Функции без изменений, но с добавлением WebSocket ---

def create_child_part(form, parent_part_id, user):
    """Создает новую дочернюю деталь и привязывает ее к родителю."""
    parent_part = db.session.get(Part, parent_part_id)
    if not parent_part:
        raise ValueError(f"Родительская деталь с ID {parent_part_id} не найдена.")

    # --- НАЧАЛО ИЗМЕНЕНИЯ: Используем правильное поле `name` из формы ---
    new_part = Part(
        part_id=form.part_id.data,
        product_designation=parent_part.product_designation, # Наследует изделие родителя
        name=form.name.data, 
        material=form.material.data,
        quantity_total=form.quantity_total.data,
        parent_id=parent_part_id,
        route_template_id=parent_part.route_template_id # Наследует маршрут родителя
    )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    db.session.add(new_part)
    
    log_details = f"В состав '{parent_part.name}' добавлен узел '{new_part.name}'."
    log_entry = AuditLog(part_id=parent_part_id, user_id=user.id, action="Обновление состава", details=log_details, category='part')
    db.session.add(log_entry)
    
    db.session.commit()
    
    _send_websocket_notification(
        'part_updated',
        f"В состав изделия {parent_part.part_id} добавлен новый узел.",
        parent_part.part_id
    )

def log_qr_generation(part_id, user):
    """Логирует факт генерации или перегенерации QR-кода."""
    log_entry = AuditLog(part_id=part_id, user_id=user.id, action="Генерация QR", details=f"Создан QR-код для детали '{part_id}'.", category='part')
    db.session.add(log_entry)
    db.session.commit()

def get_parts_for_printing(part_ids):
    """Получает данные деталей и их QR-коды для страницы печати."""
    parts = Part.query.filter(Part.part_id.in_(part_ids)).all()
    return [{'part': part, 'qr_image': generate_qr_code_as_base64(part.part_id)} for part in parts]

def cancel_stage_by_history_id(history_id, user):
    """Отменяет этап производства по ID записи в истории."""
    history_entry = db.get_or_404(StatusHistory, history_id)
    part = history_entry.part
    
    part.quantity_completed -= history_entry.quantity
    if part.quantity_completed < 0: part.quantity_completed = 0
    
    log_details = f"Отменен этап: '{history_entry.status}' ({history_entry.quantity} шт.)."
    db.session.add(AuditLog(part_id=part.part_id, user_id=user.id, action="Отмена этапа", details=log_details, category='part'))
    
    stage_name = history_entry.status
    db.session.delete(history_entry)

    new_last_history = StatusHistory.query.filter_by(part_id=part.part_id).order_by(StatusHistory.timestamp.desc()).first()
    part.current_status = new_last_history.status if new_last_history else 'На складе'
    
    db.session.commit()
    
    _send_websocket_notification(
        'part_updated',
        f"Для детали {part.part_id} отменен этап '{stage_name}'.",
        part.part_id
    )
    return part, stage_name

def delete_multiple_parts(part_ids, user, config):
    """Массово удаляет детали из списка их ID."""
    parts_to_delete = Part.query.filter(Part.part_id.in_(part_ids)).all()
    deleted_count = 0
    for part in parts_to_delete:
        if part.drawing_filename:
            file_path = os.path.join(config['DRAWING_UPLOAD_FOLDER'], part.drawing_filename)
            if os.path.exists(file_path): os.remove(file_path)
        
        db.session.add(AuditLog(part_id=part.part_id, user_id=user.id, action="Массовое удаление", details=f"Деталь '{part.part_id}' удалена.", category='part'))
        db.session.delete(part)
        deleted_count += 1
        
    db.session.commit()
    
    if deleted_count > 0:
        _send_websocket_notification(
            'bulk_delete',
            f"Пользователь {user.username} удалил {deleted_count} деталей."
        )
    return deleted_count