# app/admin/forms.py

from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField, SubmitField,
                     SelectMultipleField, SelectField, IntegerField, TextAreaField)
from wtforms.validators import DataRequired, Optional, Length, ValidationError, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired
from app.models.models import RouteTemplate, Stage, Role, Permission, User
from wtforms_sqlalchemy.fields import QuerySelectField

# --- Фабрики для полей QuerySelectField ---

def get_route_templates():
    """Возвращает все шаблоны маршрутов для выпадающего списка."""
    return RouteTemplate.query.order_by(RouteTemplate.name).all()

def get_stages():
    """Возвращает все этапы из справочника для выпадающего списка."""
    return Stage.query.order_by(Stage.name).all()

def get_roles():
    """Возвращает все роли для выпадающего списка."""
    return Role.query.order_by(Role.name).all()

def get_all_users():
    """Возвращает всех пользователей для выпадающего списка."""
    return User.query.order_by(User.username).all()

# --- Формы для деталей (Parts) ---

class PartForm(FlaskForm):
    """Форма для добавления одной детали вручную. ОБНОВЛЕНА."""
    product = StringField('Изделие (напр. "Наборка №3")', validators=[DataRequired(), Length(max=100)])
    part_id = StringField('Обозначение (Артикул)', validators=[DataRequired(), Length(max=100)])
    name = StringField('Наименование', validators=[DataRequired(), Length(max=150)])
    material = StringField('Материал (из колонки "Прим.")', validators=[DataRequired(), Length(max=150)])
    size = StringField('Размер (необязательно)', validators=[Optional(), Length(max=100)])
    
    quantity_total = IntegerField(
        'Общее количество в партии',
        default=1,
        validators=[
            DataRequired(),
            NumberRange(min=1, message='Количество должно быть не меньше 1')
        ]
    )

    route_template = SelectField('Технологический маршрут', coerce=int, validators=[DataRequired()])
    drawing = FileField('Чертеж (изображение, необязательно)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения (jpg, png, gif)!')
    ])
    submit = SubmitField('Добавить деталь')


class EditPartForm(FlaskForm):
    """Форма для редактирования данных детали. ОБНОВЛЕНА."""
    product_designation = StringField('Изделие', validators=[DataRequired(), Length(max=100)])
    name = StringField('Наименование', validators=[DataRequired(), Length(max=150)])
    material = StringField('Материал', validators=[DataRequired(), Length(max=150)])
    size = StringField('Размер', validators=[Optional(), Length(max=100)])
    
    drawing = FileField('Заменить чертеж (необязательно)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения (jpg, png, gif)!')
    ])
    submit = SubmitField('Сохранить изменения')


class AddChildPartForm(FlaskForm):
    """Форма для добавления дочернего узла к детали. ОБНОВЛЕНА."""
    # --- НАЧАЛО ИЗМЕНЕНИЯ: Приводим валидаторы в соответствие с PartForm ---
    part_id = StringField('Обозначение узла/компонента', validators=[DataRequired(), Length(max=100)])
    name = StringField('Наименование узла/компонента', validators=[DataRequired(), Length(max=150)])
    material = StringField('Материал', validators=[DataRequired(), Length(max=150)])
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    
    quantity_total = IntegerField(
        'Количество в составе родителя',
        default=1,
        validators=[
            DataRequired(),
            NumberRange(min=1, message='Количество должно быть не меньше 1')
        ]
    )
    submit = SubmitField('Добавить узел')


# --- Формы для управления и импорта ---

class FileUploadForm(FlaskForm):
    """Форма для загрузки файла Excel."""
    file = FileField('Excel/CSV-файл', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Только файлы Excel (.xlsx, .xls) или CSV (.csv)!')
    ])
    submit = SubmitField('Загрузить и импортировать')


class GenerateFromCloudForm(FlaskForm):
    """НОВАЯ форма для генерации отчета из облачного файла."""
    excel_path = StringField('Путь к Excel-файлу в OneDrive', validators=[DataRequired()])
    row_number = IntegerField('Номер строки для обработки', validators=[
        DataRequired(),
        NumberRange(min=2, message="Номер строки должен быть больше 1.")
    ])
    word_template = FileField('Файл шаблона Word (.docx)', validators=[
        FileRequired(),
        FileAllowed(['docx'], 'Только файлы Word (.docx)!')
    ])
    submit = SubmitField('Сгенерировать документ')


class ConfirmForm(FlaskForm):
    """Пустая форма для генерации CSRF-токена в простых POST-запросах."""
    pass


# --- Формы для справочников (Этапы, Маршруты) ---

class StageDictionaryForm(FlaskForm):
    """Форма для добавления этапа в справочник."""
    name = StringField('Название этапа', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class RouteTemplateForm(FlaskForm):
    """Форма для создания и редактирования шаблона маршрута."""
    name = StringField('Название шаблона маршрута', validators=[DataRequired()])
    is_default = BooleanField('Использовать по умолчанию для новых деталей (при импорте)')
    stages = SelectMultipleField(
        'Этапы',
        coerce=int,
        validators=[DataRequired(message="В маршруте должен быть как минимум один этап.")]
    )
    submit = SubmitField('Сохранить маршрут')

    def __init__(self, *args, **kwargs):
        self.obj = kwargs.get('obj')
        super(RouteTemplateForm, self).__init__(*args, **kwargs)
        self.stages.choices = [(s.id, s.name) for s in Stage.query.order_by('name').all()]

    def validate_name(self, name):
        query = RouteTemplate.query.filter(RouteTemplate.name == name.data)
        if self.obj:
            query = query.filter(RouteTemplate.id != self.obj.id)
        if query.first():
            raise ValidationError('Шаблон с таким названием уже существует.')


# --- Формы для пользователей и ролей ---

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class UserBaseForm(FlaskForm):
    username = StringField('Имя пользователя (логин)', validators=[DataRequired(), Length(min=3, max=64)])
    role = QuerySelectField('Роль', query_factory=get_roles, get_label='name', allow_blank=False)


class AddUserForm(UserBaseForm):
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Создать пользователя')


class EditUserForm(UserBaseForm):
    password = PasswordField('Новый пароль (оставьте пустым, чтобы не менять)', validators=[Optional(), Length(min=6)])
    submit = SubmitField('Сохранить изменения')


class RoleForm(FlaskForm):
    name = StringField('Название роли', validators=[DataRequired()])
    permissions = SelectMultipleField('Права доступа', coerce=int)
    submit = SubmitField('Сохранить роль')

    def __init__(self, *args, **kwargs):
        super(RoleForm, self).__init__(*args, **kwargs)
        self.permissions.choices = [
            (Permission.ADD_PARTS, 'Добавление изделий/деталей'),
            (Permission.EDIT_PARTS, 'Корректировка изделий/деталей'),
            (Permission.DELETE_PARTS, 'Удаление изделий/деталей'),
            (Permission.GENERATE_QR, 'Генерация QR-кодов'),
            (Permission.VIEW_AUDIT_LOG, 'Просмотр журнала аудита'),
            (Permission.MANAGE_STAGES, 'Управление справочником этапов'),
            (Permission.MANAGE_ROUTES, 'Управление маршрутами'),
            (Permission.VIEW_REPORTS, 'Просмотр отчетов'),
            (Permission.MANAGE_USERS, 'Управление пользователями'),
            (Permission.ADMIN, 'Полный администратор')
        ]

# --- Прочие формы ---

class ConfirmStageQuantityForm(FlaskForm):
    quantity = IntegerField(
        'Количество выполненных изделий',
        validators=[
            DataRequired(),
            NumberRange(min=1, message='Количество должно быть не меньше 1')
        ]
    )
    operator_name = StringField('Ваше ФИО', validators=[DataRequired()])
    submit = SubmitField('Подтвердить выполнение')


class AddNoteForm(FlaskForm):
    stage = QuerySelectField(
        'Привязать к этапу (необязательно)',
        query_factory=get_stages,
        get_label='name',
        allow_blank=True,
        blank_text='-- Общее примечание --'
    )
    text = TextAreaField('Текст примечания', validators=[DataRequired()])
    submit = SubmitField('Добавить примечание')


class ChangeRouteForm(FlaskForm):
    new_route = QuerySelectField(
        'Новый технологический маршрут',
        query_factory=get_route_templates,
        get_label='name',
        allow_blank=False
    )
    submit = SubmitField('Сохранить новый маршрут')


class ChangeResponsibleForm(FlaskForm):
    responsible = QuerySelectField(
        'Назначить ответственного',
        query_factory=get_all_users,
        get_label='username',
        allow_blank=True,
        blank_text='-- Не назначен --'
    )
    submit = SubmitField('Сохранить')