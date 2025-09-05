# app/admin/utils.py

import functools
from flask import flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.models import Permission

def permission_required(permission):
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                flash('У вас нет прав для доступа к этой странице.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return permission_required(Permission.ADMIN)(f)