# app/admin/routes/management_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.models import db, Part, AuditLog, RouteTemplate, RouteStage, Stage, Permission
from app.admin.forms import PartForm, FileUploadForm, StageDictionaryForm, RouteTemplateForm

management_bp = Blueprint('management', __name__)

@management_bp.route('/')
@login_required
def admin_page():
    if not any([current_user.can(p) for p in [Permission.ADMIN, Permission.VIEW_AUDIT_LOG, Permission.ADD_PARTS,
                                              Permission.MANAGE_STAGES, Permission.MANAGE_ROUTES, Permission.VIEW_REPORTS]]):
        flash('У вас нет прав для доступа к этому разделу.', 'error')
        return redirect(url_for('main.dashboard'))
    
    part_form = PartForm()
    part_form.route_template.choices = [
        (rt.id, rt.name) for rt in RouteTemplate.query.order_by(RouteTemplate.name).all()
    ]
    
    upload_form = FileUploadForm()
    return render_template('admin.html', part_form=part_form, upload_form=upload_form)

@management_bp.route('/stages')
@login_required
def list_stages():
    stages = Stage.query.order_by(Stage.name).all()
    form = StageDictionaryForm()
    return render_template('list_stages.html', stages=stages, form=form)

@management_bp.route('/stages/add', methods=['POST'])
@login_required
def add_stage():
    form = StageDictionaryForm()
    if form.validate_on_submit():
        stage_name = form.name.data.strip()
        if Stage.query.filter(Stage.name.ilike(stage_name)).first():
            flash('Этап с таким названием уже существует.', 'error')
        else:
            new_stage = Stage(name=stage_name)
            db.session.add(new_stage)
            db.session.commit()
            flash(f'Этап "{stage_name}" успешно добавлен в справочник.', 'success')
    return redirect(url_for('admin.management.list_stages'))

@management_bp.route('/stages/delete/<int:stage_id>', methods=['POST'])
@login_required
def delete_stage(stage_id):
    stage = db.get_or_404(Stage, stage_id)
    if RouteStage.query.filter_by(stage_id=stage_id).first():
        flash('Нельзя удалить этап, так как он используется в одном или нескольких маршрутах.', 'error')
    else:
        stage_name = stage.name
        db.session.delete(stage)
        db.session.commit()
        flash(f'Этап "{stage_name}" удален из справочника.', 'success')
    return redirect(url_for('admin.management.list_stages'))

@management_bp.route('/routes')
@login_required
def list_routes():
    routes = RouteTemplate.query.order_by(RouteTemplate.name).all()
    return render_template('list_routes.html', routes=routes)

@management_bp.route('/routes/add', methods=['GET', 'POST'])
@login_required
def add_route():
    form = RouteTemplateForm()
    if form.validate_on_submit():
        try:
            if form.is_default.data:
                current_default = RouteTemplate.query.filter_by(is_default=True).first()
                if current_default:
                    current_default.is_default = False
            
            new_template = RouteTemplate(name=form.name.data, is_default=form.is_default.data)
            db.session.add(new_template)
            for i, stage_id in enumerate(form.stages.data):
                route_stage = RouteStage(template=new_template, stage_id=stage_id, order=i)
                db.session.add(route_stage)

            log_entry = AuditLog(user_id=current_user.id, action="Управление маршрутами", details=f"Создан новый маршрут '{new_template.name}'.", category='management')
            db.session.add(log_entry)
            
            db.session.commit()
            
            flash('Новый технологический маршрут успешно создан.', 'success')
            return redirect(url_for('admin.management.list_routes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка при создании маршрута: {e}', 'error')
    return render_template('route_form.html', form=form, title='Создать новый маршрут')

@management_bp.route('/routes/edit/<int:route_id>', methods=['GET', 'POST'])
@login_required
def edit_route(route_id):
    template = db.get_or_404(RouteTemplate, route_id)
    form = RouteTemplateForm(obj=template)
    if form.validate_on_submit():
        try:
            if form.is_default.data:
                current_default = RouteTemplate.query.filter(
                    RouteTemplate.is_default==True, 
                    RouteTemplate.id != template.id
                ).first()
                if current_default:
                    current_default.is_default = False

            template.name = form.name.data
            template.is_default = form.is_default.data
            
            RouteStage.query.filter_by(template_id=template.id).delete()
            for i, stage_id in enumerate(form.stages.data):
                route_stage = RouteStage(template=template, stage_id=stage_id, order=i)
                db.session.add(route_stage)

            log_entry = AuditLog(user_id=current_user.id, action="Управление маршрутами", details=f"Изменен маршрут '{template.name}'.", category='management')
            db.session.add(log_entry)
            
            db.session.commit()
            
            flash('Маршрут успешно обновлен.', 'success')
            return redirect(url_for('admin.management.list_routes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка при обновлении маршрута: {e}', 'error')
    
    form.stages.data = [stage.stage_id for stage in sorted(template.stages, key=lambda s: s.order)]
    return render_template('route_form.html', form=form, title=f'Редактировать: {template.name}')

@management_bp.route('/routes/delete/<int:route_id>', methods=['POST'])
@login_required
def delete_route(route_id):
    template = db.get_or_404(RouteTemplate, route_id)
    if Part.query.filter_by(route_template_id=route_id).first():
        flash('Нельзя удалить маршрут, так как он присвоен одной или нескольким деталям.', 'error')
    else:
        template_name = template.name
        db.session.delete(template)
        log_entry = AuditLog(user_id=current_user.id, action="Управление маршрутами", details=f"Удален маршрут '{template_name}'.", category='management')
        db.session.add(log_entry)
        db.session.commit()
        flash(f'Маршрут "{template_name}" успешно удален.', 'success')
    return redirect(url_for('admin.management.list_routes'))