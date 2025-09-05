import click
import secrets
import string
import sys
from flask.cli import with_appcontext
from .models.models import db, User, Role

# Используем click для создания команды
@click.command('seed')
@with_appcontext
def seed_command():
    """
    Заполняет базу данных начальными данными:
    создает роли и первого администратора.
    """
    if Role.query.count() == 0:
        click.echo("Создание ролей пользователей...")
        Role.insert_roles()
        click.secho("Роли успешно созданы.", fg="green")

    if User.query.count() == 0:
        click.echo("Создание первого администратора ('суперпользователя')...")
        
        alphabet = string.ascii_letters + string.digits
        admin_password = ''.join(secrets.choice(alphabet) for i in range(12))
        
        admin_user = User(
            username='admin', 
            role=Role.query.filter_by(name='Administrator').first()
        )
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        db.session.commit()
        
        click.secho("\n✅ Администратор успешно создан.", fg="green")
        click.echo("\n--- Учетные данные администратора ---")
        click.echo(f"   Логин: admin")
        click.echo(f"   Пароль: {admin_password}")
        click.secho("\nВАЖНО: Этот пароль отображается только один раз. Сохраните его в надежном месте.", fg="yellow")
        click.echo("------------------------------------")
    else:
        click.echo("Пользователи уже существуют. Пропуск создания администратора.")