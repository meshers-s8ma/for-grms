
# app/admin/routes/user_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from app.models.models import db, User, AuditLog, Role, Permission
from app.admin.forms import LoginForm, AddUserForm, EditUserForm, RoleForm
from app.admin.utils import admin_required, permission_required

user_bp = Blueprint('user', __name__)

@user_bp.route('/audit_log')
@permission_required(Permission.VIEW_AUDIT_LOG)
def audit_log():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.options(joinedload(AuditLog.user)).filter_by(category='part').order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=25)
    return render_template('audit_log.html', logs=logs)

@user_bp.route('/user_log')
@permission_required(Permission.VIEW_AUDIT_LOG)
def user_log():
    page = request.args.get('page', 1, type=int)
    user_logs = AuditLog.query.options(joinedload(AuditLog.user)).filter(
        AuditLog.category.in_(['auth', 'management'])
    ).order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=25)
    return render_template('user_log.html', logs=user_logs)

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            log_entry = AuditLog(user_id=user.id, action="Вход в систему", details=f"Пользователь '{user.username}' вошел в систему.", category='auth')
            db.session.add(log_entry)
            db.session.commit()
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Неверный логин или пароль.', 'error')
    return render_template('login.html', form=form)

@user_bp.route('/logout')
@login_required
def logout():
    log_entry = AuditLog(user_id=current_user.id, action="Выход из системы", details=f"Пользователь '{current_user.username}' вышел из системы.", category='auth')
    db.session.add(log_entry)
    db.session.commit()
    logout_user()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('admin.user.login'))

@user_bp.route('/roles')
@admin_required
def list_roles():
    roles = Role.query.order_by(Role.id).all()
    return render_template('list_roles.html', roles=roles)

@user_bp.route('/roles/add', methods=['GET', 'POST'])
@admin_required
def add_role():
    form = RoleForm()
    if form.validate_on_submit():
        permissions_sum = sum(form.permissions.data)
        new_role = Role(name=form.name.data, permissions=permissions_sum)
        db.session.add(new_role)
        log_entry = AuditLog(user_id=current_user.id, action="Управление ролями", details=f"Создана новая роль '{new_role.name}'.", category='management')
        db.session.add(log_entry)
        db.session.commit()
        flash(f'Роль "{new_role.name}" успешно создана.', 'success')
        return redirect(url_for('admin.user.list_roles'))
    
    form.permissions.data = []
    return render_template('role_form.html', form=form, title="Создать новую роль")

@user_bp.route('/roles/edit/<int:role_id>', methods=['GET', 'POST'])
@admin_required
def edit_role(role_id):
    role = db.get_or_404(Role, role_id)
    form = RoleForm(obj=role)
    if form.validate_on_submit():
        role.name = form.name.data
        role.permissions = sum(form.permissions.data)
        log_entry = AuditLog(user_id=current_user.id, action="Управление ролями", details=f"Изменена роль '{role.name}'.", category='management')
        db.session.add(log_entry)
        db.session.commit()
        flash(f'Роль "{role.name}" успешно обновлена.', 'success')
        return redirect(url_for('admin.user.list_roles'))
    
    form.permissions.data = [p for p in Permission.__dict__.values() if isinstance(p, int) and role.has_permission(p)]
    return render_template('role_form.html', form=form, title=f'Редактировать роль: {role.name}')

@user_bp.route('/roles/delete/<int:role_id>', methods=['POST'])
@admin_required
def delete_role(role_id):
    role = db.get_or_404(Role, role_id)
    if role.users.count() > 0:
        flash('Нельзя удалить роль, которая присвоена пользователям.', 'error')
    elif role.default:
        flash('Нельзя удалить роль по умолчанию.', 'error')
    else:
        role_name = role.name
        db.session.delete(role)
        log_entry = AuditLog(user_id=current_user.id, action="Управление ролями", details=f"Удалена роль '{role_name}'.", category='management')
        db.session.add(log_entry)
        db.session.commit()
        flash(f'Роль "{role_name}" успешно удалена.', 'success')
    return redirect(url_for('admin.user.list_roles'))

@user_bp.route('/users')
@permission_required(Permission.MANAGE_USERS)
def list_users():
    users = User.query.options(joinedload(User.role)).order_by(User.id).all()
    return render_template('users.html', users=users)

@user_bp.route('/add_user', methods=['GET', 'POST'])
@permission_required(Permission.MANAGE_USERS)
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Пользователь с таким именем уже существует.', 'error')
        else:
            new_user = User(
                username=form.username.data,
                role=form.role.data
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            log_entry = AuditLog(user_id=current_user.id, action="Управление пользователями", details=f"Создан новый пользователь '{new_user.username}'.", category='management')
            db.session.add(log_entry)
            db.session.commit()
            flash(f'Пользователь {new_user.username} успешно создан.', 'success')
            return redirect(url_for('admin.user.list_users'))
    return render_template('add_user.html', form=form)

@user_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@permission_required(Permission.MANAGE_USERS)
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        existing_user = User.query.filter(User.username == form.username.data, User.id != user_id).first()
        if existing_user:
            flash('Пользователь с таким именем уже существует.', 'error')
        else:
            user.username = form.username.data
            user.role = form.role.data
            if form.password.data:
                user.set_password(form.password.data)
            log_entry = AuditLog(user_id=current_user.id, action="Управление пользователями", details=f"Изменены данные пользователя '{user.username}'.", category='management')
            db.session.add(log_entry)
            db.session.commit()
            flash(f'Данные пользователя {user.username} обновлены.', 'success')
            return redirect(url_for('admin.user.list_users'))
    
    form.role.data = user.role
    return render_template('edit_user.html', user=user, form=form)

@user_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@permission_required(Permission.MANAGE_USERS)
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Вы не можете удалить свою собственную учетную запись.', 'error')
        return redirect(url_for('admin.user.list_users'))
    
    user_to_delete = db.get_or_404(User, user_id)
    username_deleted = user_to_delete.username
    
    # --- НАЧАЛО ФИНАЛЬНОГО ИСПРАВЛЕНИЯ ---
    # Проверяем, является ли удаляемый пользователь администратором
    if user_to_delete.can(Permission.ADMIN):
        # Если да, то считаем, сколько всего пользователей с правами администратора в системе.
        # Используем метод .op('&') для побитовой операции в SQLAlchemy.
        # Это надежно работает со всеми версиями.
        admin_count = User.query.join(Role).filter(
            Role.permissions.op('&')(Permission.ADMIN) == Permission.ADMIN
        ).count()
        
        if admin_count <= 1:
            flash('Нельзя удалить последнего администратора в системе.', 'error')
            return redirect(url_for('admin.user.list_users'))
    # --- КОНЕЦ ФИНАЛЬНОГО ИСПРАВЛЕНИЯ ---

    log_entry = AuditLog(user_id=current_user.id, action="Управление пользователями", details=f"Удален пользователь '{username_deleted}'.", category='management')
    db.session.add(log_entry)
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Пользователь {username_deleted} удален.', 'success')
    return redirect(url_for('admin.user.list_users'))