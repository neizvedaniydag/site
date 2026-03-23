"""
Скрипт для проверки базы данных и пользователей
"""

from app import app, db, bcrypt
from models import User

with app.app_context():
    print("=" * 50)
    print("ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("=" * 50)

    # Проверка всех пользователей
    users = User.query.all()
    print(f"\nВсего пользователей в БД: {len(users)}")

    if not users:
        print("\n[WARNING] В базе данных нет пользователей!")
        print("Создайте нового пользователя через регистрацию.")
    else:
        print("\nСписок пользователей:")
        print("-" * 50)
        for user in users:
            print(f"\nID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Nickname: {user.nickname}")
            print(f"Email: {user.email}")
            print(f"Role: {user.role}")
            print(f"Is Approved: {user.is_approved}")
            print(f"Is Banned: {user.is_banned}")
            print(f"Is Active (computed): {user.is_active}")
            print(f"Created: {user.created_at}")
            print("-" * 50)

    # Проверка админа
    admin = User.query.filter_by(email='mur4ika1@gmail.com').first()
    if admin:
        print(f"\n[OK] Админ найден: {admin.email}")
        print(f"    Role: {admin.role}")
        print(f"    Is Active: {admin.is_active}")

        # Проверка пароля админа
        test_password = '59655965'
        if bcrypt.check_password_hash(admin.password, test_password):
            print(f"[OK] Пароль админа корректный")
        else:
            print(f"[ERROR] Пароль админа НЕ совпадает!")
    else:
        print("\n[WARNING] Админ не найден в БД")

    print("\n" + "=" * 50)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 50)
