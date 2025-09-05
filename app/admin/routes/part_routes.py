# app/admin/routes/part_routes.py

from flask import (Blueprint, render_template, request, flash, redirect, url_for,
                   current_app, send_file, send_from_directory)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.models import Part, RouteTemplate, Permission
from app.utils import generate_qr_code, create_safe_file_name
from app.admin.forms import (PartForm, EditPartForm, FileUploadForm, ChangeRouteForm,
                             ConfirmForm, ChangeResponsibleForm, AddChildPartForm)
from app.services import part_service
from app.admin.utils import permission_required

part_bp = Blueprint('part', __name__)


@part_bp.route('/drawings/<path:filename>')
@login_required
def serve_drawing(filename):
    """Отдает файл чертежа из защищенной папки."""
    return send_from_directory(
        current_app.config['DRAWING_UPLOAD_FOLDER'], filename
    )


@part_bp.route('/add_single_part', methods=['POST'])
@permission_required(Permission.ADD_PARTS)
def add_single_part():
    """Обрабатывает добавление одной детали через форму."""
    form = PartForm()
    form.route_template.choices = [
        (rt.id, rt.name) for rt in RouteTemplate.query.order_by(RouteTemplate.name).all()
    ]

    if form.validate_on_submit():
        try:
            part_service.create_single_part(form, current_user, current_app.config)
            flash(f"Успешно добавлена деталь: {form.part_id.data}", 'success')
        except IntegrityError:
            db.session.rollback()
            flash(f"Ошибка: Деталь {form.part_id.data} уже существует!", 'error')
        except Exception as e:
            db.session.rollback()
            flash(f"Произошла непредвиденная ошибка: {e}", 'error')
            current_app.logger.error(f"Error creating single part: {e}", exc_info=True)
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", 'error')

    return redirect(url_for('admin.management.admin_page'))


@part_bp.route('/upload_excel', methods=['POST'])
@permission_required(Permission.ADD_PARTS)
def upload_excel():
    """Обрабатывает загрузку и импорт деталей из Excel-файла."""
    form = FileUploadForm()
    if form.validate_on_submit():
        try:
            added, skipped = part_service.import_parts_from_excel(
                form.file.data, current_user, current_app.config
            )
            flash(f"Импорт завершен. Добавлено: {added}, пропущено дубликатов: {skipped}.", 'success')
        except ValueError as e:
            flash(f"Ошибка валидации: {e}", 'error')
        except Exception as e:
            flash(f"Произошла ошибка при обработке файла: {e}", 'error')
            current_app.logger.error(f"Excel import error: {e}", exc_info=True)
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')

    return redirect(url_for('admin.management.admin_page'))


@part_bp.route('/edit/<path:part_id>', methods=['GET', 'POST'])
@permission_required(Permission.EDIT_PARTS)
def edit_part(part_id):
    """Отображает и обрабатывает форму редактирования детали."""
    part_to_edit = db.get_or_404(Part, part_id)
    form = EditPartForm(obj=part_to_edit)

    if form.validate_on_submit():
        try:
            part_service.update_part_from_form(
                part=part_to_edit,
                form=form,
                user=current_user,
                config=current_app.config
            )
            flash(f"Данные для детали {part_id} успешно обновлены.", 'success')
            return redirect(url_for('main.history', part_id=part_id))
        except Exception as e:
            flash(f"Произошла ошибка при обновлении: {e}", "error")
            current_app.logger.error(f"Error updating part {part_id}: {e}", exc_info=True)

    # Предзаполняем форму текущими данными объекта при GET-запросе
    form.process(obj=part_to_edit)
    return render_template('edit_part.html', part=part_to_edit, form=form)


@part_bp.route('/delete/<path:part_id>', methods=['POST'])
@permission_required(Permission.DELETE_PARTS)
def delete_part(part_id):
    """Обрабатывает удаление одной детали."""
    part_to_delete = db.get_or_404(Part, part_id)
    try:
        part_service.delete_single_part(part_to_delete, current_user, current_app.config)
        flash(f"Деталь {part_id} и вся ее история удалены.", 'success')
    except Exception as e:
        flash(f"Ошибка при удалении: {e}", 'error')
        current_app.logger.error(f"Error deleting part {part_id}: {e}", exc_info=True)

    return redirect(url_for('main.dashboard'))


@part_bp.route('/generate_qr/<path:part_id>', methods=['POST'])
@permission_required(Permission.GENERATE_QR)
def generate_single_qr(part_id):
    """Генерирует и отдает для скачивания QR-код для одной детали."""
    form = ConfirmForm()
    if form.validate_on_submit():
        qr_img_bytes = generate_qr_code(part_id)
        if qr_img_bytes:
            part_service.log_qr_generation(part_id, current_user)
            safe_filename = create_safe_file_name(f"part_{part_id}_qr.png")
            return send_file(qr_img_bytes, mimetype='image/png', as_attachment=True, download_name=safe_filename)
        else:
            flash(f'Не удалось создать QR-код для детали {part_id}.', 'error')
    else:
        flash('Ошибка безопасности. Попробуйте еще раз.', 'error')

    return redirect(url_for('main.dashboard'))


@part_bp.route('/qr_print_preview', methods=['POST'])
@permission_required(Permission.GENERATE_QR)
def qr_print_preview():
    """Формирует страницу для массовой печати QR-кодов."""
    part_ids = request.form.getlist('part_ids')
    if not part_ids:
        flash('Вы не выбрали ни одной детали для печати.', 'error')
        return redirect(url_for('main.dashboard'))

    parts_for_print = part_service.get_parts_for_printing(part_ids)
    return render_template('qr_print_preview.html', parts_for_print=parts_for_print)


@part_bp.route('/change_route/<path:part_id>', methods=['GET', 'POST'])
@permission_required(Permission.EDIT_PARTS)
def change_part_route(part_id):
    """Отображает и обрабатывает форму смены технологического маршрута."""
    part = db.get_or_404(Part, part_id)
    form = ChangeRouteForm(obj=part)

    if form.validate_on_submit():
        was_changed = part_service.change_part_route(part, form.new_route.data, current_user)
        if was_changed:
            flash(f"Маршрут для детали {part.part_id} успешно изменен.", 'success')
        else:
            flash("Изменений не было.", "info")
        return redirect(url_for('main.history', part_id=part.part_id))

    return render_template('change_route.html', form=form, part=part)


@part_bp.route('/cancel_stage/<int:history_id>', methods=['POST'])
@permission_required(Permission.EDIT_PARTS)
def cancel_stage(history_id):
    """Обрабатывает отмену производственного этапа."""
    try:
        part, stage_name = part_service.cancel_stage_by_history_id(history_id, current_user)
        flash(f"Этап '{stage_name}' для детали {part.part_id} был успешно отменен.", 'success')
        return redirect(url_for('main.history', part_id=part.part_id))
    except Exception as e:
        flash(f"Ошибка при отмене этапа: {e}", "error")
        current_app.logger.error(f"Error cancelling stage history {history_id}: {e}", exc_info=True)
        return redirect(request.referrer or url_for('main.dashboard'))


@part_bp.route('/bulk_action', methods=['POST'])
@login_required  # Проверка прав (удаление/печать) внутри сервиса или JS
def bulk_action():
    """Обрабатывает массовые действия с деталями (например, удаление)."""
    part_ids = request.form.getlist('part_ids')
    action = request.form.get('action')

    if not part_ids:
        flash('Вы не выбрали ни одной детали.', 'error')
        return redirect(url_for('main.dashboard'))

    if action == 'delete' and current_user.can(Permission.DELETE_PARTS):
        try:
            deleted_count = part_service.delete_multiple_parts(part_ids, current_user, current_app.config)
            flash(f'Успешно удалено {deleted_count} деталей.', 'success')
        except Exception as e:
            flash(f'Произошла ошибка при массовом удалении: {e}', 'error')
            current_app.logger.error(f"Bulk delete error: {e}", exc_info=True)
    else:
        flash('Неизвестное действие или недостаточно прав.', 'error')

    return redirect(url_for('main.dashboard'))


@part_bp.route('/change_responsible/<path:part_id>', methods=['GET', 'POST'])
@permission_required(Permission.EDIT_PARTS)
def change_responsible(part_id):
    """Отображает и обрабатывает форму смены ответственного."""
    part = db.get_or_404(Part, part_id)
    form = ChangeResponsibleForm()

    if request.method == 'GET':
        form.responsible.data = part.responsible

    if form.validate_on_submit():
        was_changed = part_service.change_responsible_user(part, form.responsible.data, current_user)
        if was_changed:
            flash('Ответственный за деталь успешно изменен.', 'success')
        else:
            flash('Изменений не было.', 'info')
        return redirect(url_for('main.history', part_id=part.part_id))

    return render_template('change_responsible.html', form=form, part=part)


@part_bp.route('/change_responsible_form/<path:part_id>')
@permission_required(Permission.EDIT_PARTS)
def change_responsible_form(part_id):
    """Возвращает HTML-код формы для смены ответственного (для модального окна)."""
    part = db.get_or_404(Part, part_id)
    form = ChangeResponsibleForm()
    form.responsible.data = part.responsible
    
    return render_template('_change_responsible_form.html', form=form, part=part)


@part_bp.route('/add_child/<path:parent_part_id>', methods=['POST'])
@permission_required(Permission.ADD_PARTS)
def add_child_part(parent_part_id):
    """Обрабатывает добавление дочернего узла к детали."""
    form = AddChildPartForm()
    
    if form.validate_on_submit():
        try:
            part_service.create_child_part(form, parent_part_id, current_user)
            flash('Новый узел успешно добавлен в состав изделия.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash(f"Ошибка: Деталь с артикулом '{form.part_id.data}' уже существует!", 'error')
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка: {e}', 'error')
            current_app.logger.error(f"Error adding child part: {e}", exc_info=True)
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", 'error')

    return redirect(url_for('main.history', part_id=parent_part_id))