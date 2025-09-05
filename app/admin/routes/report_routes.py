# app/admin/routes/report_routes.py

from flask import (Blueprint, render_template, request, jsonify, flash,
                   redirect, url_for, send_file, current_app)
from flask_login import login_required
from datetime import datetime
from sqlalchemy import func
import io

from app.models.models import db, StatusHistory, Part, Permission
from app.admin.utils import permission_required
from app.admin.forms import GenerateFromCloudForm
from app.services import graph_service, document_service

report_bp = Blueprint('report', __name__)


@report_bp.route('/')
@permission_required(Permission.VIEW_REPORTS)
def reports_index():
    """Отображает главную страницу раздела отчетов."""
    return render_template('reports/index.html')


@report_bp.route('/operator_performance')
@permission_required(Permission.VIEW_REPORTS)
def report_operator_performance():
    """Отображает страницу отчета по производительности операторов."""
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    return render_template(
        'reports/operator_performance.html',
        date_from=date_from_str,
        date_to=date_to_str
    )


@report_bp.route('/stage_duration')
@permission_required(Permission.VIEW_REPORTS)
def report_stage_duration():
    """Отображает страницу отчета по средней длительности этапов."""
    return render_template('reports/stage_duration.html')


@report_bp.route('/generate_from_cloud', methods=['GET', 'POST'])
@permission_required(Permission.VIEW_REPORTS)
def generate_from_cloud():
    """
    Отображает и обрабатывает форму для генерации Word-отчета
    из данных Excel-файла в OneDrive.
    """
    form = GenerateFromCloudForm()
    if form.validate_on_submit():
        excel_path = form.excel_path.data
        row_number = form.row_number.data
        word_template_file = form.word_template.data

        try:
            # Шаг 1: Скачиваем Excel-файл из OneDrive
            current_app.logger.info(f"Attempting to download Excel file from OneDrive: {excel_path}")
            excel_bytes = graph_service.download_file_from_onedrive(excel_path)
            current_app.logger.info("Excel file downloaded successfully.")

            # Шаг 2: Читаем данные из указанной строки
            current_app.logger.info(f"Reading row {row_number} from Excel file.")
            placeholders = graph_service.read_row_from_excel_bytes(excel_bytes, row_number)
            current_app.logger.info(f"Data parsed successfully: {placeholders}")

            # Шаг 3: Генерируем Word-документ
            current_app.logger.info("Generating Word document from template.")
            document_stream = document_service.generate_word_from_data(
                word_template_file.stream, placeholders
            )
            current_app.logger.info("Word document generated successfully.")

            # Шаг 4: Отправляем сгенерированный файл пользователю
            # Пытаемся извлечь имя для файла из данных
            birka_name = placeholders.get('{{№ бирки}}', f'report_{row_number}')
            safe_filename = "".join(c for c in str(birka_name) if c.isalnum() or c in "._- ").strip()
            final_filename = f"{safe_filename}.docx"
            
            return send_file(
                document_stream,
                as_attachment=True,
                download_name=final_filename,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )

        # Обработка специфичных ошибок для понятного вывода пользователю
        except FileNotFoundError as e:
            flash(f"Ошибка: Файл не найден в OneDrive. {e}", "error")
        except (ValueError, IndexError) as e:
            flash(f"Ошибка чтения данных из Excel: {e}", "error")
        except graph_service.GraphAPIError as e:
            flash(f"Ошибка подключения к Microsoft Cloud: {e}", "error")
            current_app.logger.error(f"Graph API Error: {e}", exc_info=True)
        except Exception as e:
            flash(f"Произошла непредвиденная ошибка: {e}", "error")
            current_app.logger.error(f"Unhandled error in generate_from_cloud: {e}", exc_info=True)

    return render_template('reports/generate_from_cloud.html', form=form)


# --- API Эндпоинты для графиков (без изменений) ---

@report_bp.route('/api/reports/operator_performance')
@login_required
def api_report_operator_performance():
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    query = db.session.query(
        StatusHistory.operator_name,
        func.count(StatusHistory.id).label('stages_completed')
    ).group_by(StatusHistory.operator_name).order_by(func.count(StatusHistory.id).desc())
    if date_from_str:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        query = query.filter(StatusHistory.timestamp >= date_from)
    if date_to_str:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        query = query.filter(StatusHistory.timestamp <= date_to)
    
    data = query.all()
    
    chart_data = {
        'labels': [row.operator_name for row in data],
        'datasets': [{
            'label': 'Выполнено этапов',
            'data': [row.stages_completed for row in data],
            'backgroundColor': 'rgba(40, 167, 69, 0.7)',
            'borderColor': 'rgba(40, 167, 69, 1)',
            'borderWidth': 1
        }]
    }
    return jsonify(chart_data)


@report_bp.route('/api/reports/stage_duration')
@login_required
def api_report_stage_duration():
    previous_event_time = func.lag(StatusHistory.timestamp).over(
        partition_by=StatusHistory.part_id, 
        order_by=StatusHistory.timestamp
    )
    cte = db.session.query(
        StatusHistory.status.label('stage_name'),
        (StatusHistory.timestamp - func.coalesce(previous_event_time, Part.date_added)).label('duration')
    ).join(Part, Part.part_id == StatusHistory.part_id).subquery()
    
    report_data = db.session.query(
        cte.c.stage_name,
        func.extract('epoch', func.avg(cte.c.duration)).label('avg_duration_seconds'),
    ).group_by(cte.c.stage_name).order_by(func.extract('epoch', func.avg(cte.c.duration)).desc()).all()

    chart_data = {
        'labels': [row.stage_name for row in report_data],
        'datasets': [{
            'label': 'Среднее время (в часах)',
            'data': [(row.avg_duration_seconds / 3600) if row.avg_duration_seconds else 0 for row in report_data],
            'backgroundColor': 'rgba(0, 123, 255, 0.7)',
            'borderColor': 'rgba(0, 123, 255, 1)',
            'borderWidth': 1
        }]
    }
    return jsonify(chart_data)