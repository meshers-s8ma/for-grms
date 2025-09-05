#!/bin/sh

# Устанавливаем строгий режим: скрипт завершится, если какая-либо команда вернет ошибку.
set -e

# Экспортируем пароль от БД в переменную PGPASSWORD.
# Утилита psql автоматически использует эту переменную для аутентификации.
export PGPASSWORD=$POSTGRES_PASSWORD

echo "Waiting for database server to start..."
# Запускаем цикл, который ждет, пока сервер PostgreSQL не станет доступен.
# Мы подключаемся к служебной базе 'postgres', которая существует всегда.
until psql -h db -U "$POSTGRES_USER" -d "postgres" -c '\q'; do
  >&2 echo "Postgres server is unavailable - sleeping"
  sleep 1
done
>&2 echo "Postgres server is up."

# Проверяем, существует ли наша база данных, и создаем ее, если нет.
# Это решает проблему "гонки состояний" при первом запуске.
DB_EXISTS=$(psql -h db -U "$POSTGRES_USER" -d "postgres" -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'")
if [ "$DB_EXISTS" = "1" ]; then
    echo "Database '$POSTGRES_DB' already exists."
else
    echo "Database '$POSTGRES_DB' not found. Creating it..."
    psql -h db -U "$POSTGRES_USER" -d "postgres" -c "CREATE DATABASE $POSTGRES_DB"
    echo "Database '$POSTGRES_DB' created."
fi

# Удаляем переменную с паролем из окружения для безопасности.
unset PGPASSWORD

# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
# Мы запускаем команды flask как отдельные процессы,
# чтобы гарантировать, что одна завершится перед началом следующей.

echo "==> Applying database migrations..."
# Сначала применяем миграции, чтобы создать все таблицы.
flask db upgrade

echo "==> Seeding initial admin user (if not exists)..."
# Только после того, как таблицы созданы, запускаем сидер для их заполнения.
flask seed
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

echo "==> Starting Gunicorn server..."
# Запускаем основной процесс - веб-сервер Gunicorn.
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:app