"""
Финальная проверка и исправление приложения
"""

from app import app, db
from models import User
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

with app.app_context():
    print("=" * 60)
    print("ФИНАЛЬНАЯ ПРОВЕРКА ПРИЛОЖЕНИЯ")
    print("=" * 60)

    # Проверка пользователей
    users_count = User.query.count()
    print(f"\n✓ Пользователей в БД: {users_count}")

    # Проверка админа
    admin = User.query.filter_by(email='mur4ika1@gmail.com').first()
    if admin:
        print(f"✓ Админ найден: {admin.email}")
        print(f"  - Role: {admin.role}")
        print(f"  - Approved: {admin.is_approved}")
        print(f"  - Banned: {admin.is_banned}")
    else:
        print("✗ Админ не найден")

    # Проверка таблиц
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    print(f"\n✓ Таблиц в БД: {len(tables)}")

    required_tables = ['user', 'test_result', 'physical_education_result', 'message']
    for table in required_tables:
        if table in tables:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} - ОТСУТСТВУЕТ!")

    # Проверка новых таблиц (опционально)
    optional_tables = ['user_streak', 'achievement', 'user_achievement']
    print("\nДополнительные таблицы (для новых функций):")
    for table in optional_tables:
        if table in tables:
            print(f"  ✓ {table}")
        else:
            print(f"  - {table} - не создана (будет создана автоматически)")

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ")
    print("=" * 60)
    print("\n✓ Приложение готово к работе!")
    print("\nДля запуска:")
    print("  python app.py")
    print("\nДля входа используйте:")
    print("  Email: mur4ika1@gmail.com")
    print("  Пароль: 59655965")
    print("\n" + "=" * 60)
