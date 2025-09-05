# app/services/query_service.py (ФИНАЛЬНАЯ ПОЛНАЯ ВЕРСИЯ С ЯВНЫМИ ИМЕНАМИ КОЛОНОК)

from sqlalchemy import union_all, literal_column, cast, String
from app.models.models import db, Part, StatusHistory, AuditLog, PartNote, User, Stage, ResponsibleHistory

def get_combined_history(part):
    """
    Получает объединенную и отсортированную историю для одной детали
    единым эффективным запросом с использованием UNION ALL.
    """
    
    # Запрос 1: История статусов
    status_query = db.session.query(
        StatusHistory.id.label("id"),
        StatusHistory.timestamp.label("timestamp"),
        literal_column("'status'").label("type"),
        StatusHistory.status.label("col1"),
        StatusHistory.operator_name.label("col2"),
        cast(StatusHistory.quantity, String).label("col3"),
        literal_column("NULL", type_=db.Integer).label("user_id")
    ).filter(StatusHistory.part_id == part.part_id)

    # Запрос 2: Логи аудита
    audit_query = db.session.query(
        AuditLog.id.label("id"),
        AuditLog.timestamp.label("timestamp"),
        literal_column("'audit'").label("type"),
        AuditLog.action.label("col1"),
        AuditLog.details.label("col2"),
        literal_column("NULL").label("col3"),
        AuditLog.user_id
    ).filter(
        AuditLog.part_id == part.part_id,
        AuditLog.action.notin_(['Добавлено примечание', 'Изменено примечание', 'Удалено примечание'])
    )

    # Запрос 3: Примечания
    notes_query = db.session.query(
        PartNote.id.label("id"),
        PartNote.timestamp.label("timestamp"),
        literal_column("'note'").label("type"),
        PartNote.text.label("col1"),
        cast(PartNote.stage_id, String).label("col2"),
        literal_column("NULL").label("col3"),
        PartNote.user_id
    ).filter(PartNote.part_id == part.part_id)
    
    # Запрос 4: История смены ответственных
    resp_query = db.session.query(
        ResponsibleHistory.id.label("id"),
        ResponsibleHistory.timestamp.label("timestamp"),
        literal_column("'responsible'").label("type"),
        literal_column("NULL").label("col1"),
        literal_column("NULL").label("col2"),
        literal_column("NULL").label("col3"),
        ResponsibleHistory.user_id
    ).filter(ResponsibleHistory.part_id == part.part_id)
    
    # Объединяем все четыре запроса
    combined_query = union_all(status_query, audit_query, notes_query, resp_query).alias("combined_history")
    
    # Финальный запрос для сортировки
    final_query = db.session.query(combined_query).order_by(combined_query.c.timestamp.desc())

    results = final_query.all()
    user_ids = {row.user_id for row in results if row.user_id}
    stage_ids_from_notes = {int(row.col2) for row in results if row.type == 'note' and row.col2}

    users_map = {u.id: u for u in db.session.query(User).filter(User.id.in_(user_ids))}
    stages_map = {s.id: s for s in db.session.query(Stage).filter(Stage.id.in_(stage_ids_from_notes))}

    history_list = []
    for row in results:
        entry = {
            'id': row.id,
            'timestamp': row.timestamp,
            'type': row.type
        }
        if row.type == 'status':
            entry['status'] = row.col1
            entry['operator_name'] = row.col2
            entry['quantity'] = int(row.col3)
        elif row.type == 'audit':
            entry['action'] = row.col1
            entry['details'] = row.col2
            entry['user'] = users_map.get(row.user_id)
        elif row.type == 'note':
            entry['text'] = row.col1
            stage_id = int(row.col2) if row.col2 else None
            entry['stage'] = stages_map.get(stage_id)
            entry['author'] = users_map.get(row.user_id)
            entry['user_id'] = row.user_id
        elif row.type == 'responsible':
            entry['action'] = "Назначен ответственный"
            entry['user'] = users_map.get(row.user_id)
        
        history_list.append(entry)
        
    return history_list