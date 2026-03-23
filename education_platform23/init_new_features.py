"""
Скрипт для инициализации новых функций:
- Стрики (система заходов дней подряд)
- Достижения
"""

from app import app, db
from models import UserStreak, Achievement, UserAchievement

with app.app_context():
    print("[INFO] Создание новых таблиц...")
    db.create_all()
    print("[OK] Таблицы созданы")

    print("[INFO] Инициализация достижений...")
    achievements_data = [
        {'code': 'first_test', 'title': '🎯 Первый тест', 'description': 'Пройдите первый тест', 'icon': '🎯', 'category': 'tests', 'requirement_value': 1},
        {'code': 'tests_10', 'title': '📚 Знаток', 'description': 'Пройдите 10 тестов', 'icon': '📚', 'category': 'tests', 'requirement_value': 10},
        {'code': 'tests_50', 'title': '🏆 Эксперт', 'description': 'Пройдите 50 тестов', 'icon': '🏆', 'category': 'tests', 'requirement_value': 50},
        {'code': 'first_workout', 'title': '💪 Первая тренировка', 'description': 'Завершите первую тренировку', 'icon': '💪', 'category': 'training', 'requirement_value': 1},
        {'code': 'workouts_10', 'title': '🔥 Спортсмен', 'description': 'Завершите 10 тренировок', 'icon': '🔥', 'category': 'training', 'requirement_value': 10},
        {'code': 'workouts_50', 'title': '⚡ Атлет', 'description': 'Завершите 50 тренировок', 'icon': '⚡', 'category': 'training', 'requirement_value': 50},
        {'code': 'streak_7', 'title': '📅 Неделя подряд', 'description': 'Заходите 7 дней подряд', 'icon': '📅', 'category': 'streak', 'requirement_value': 7},
        {'code': 'streak_30', 'title': '🌟 Месяц подряд', 'description': 'Заходите 30 дней подряд', 'icon': '🌟', 'category': 'streak', 'requirement_value': 30},
        {'code': 'streak_100', 'title': '👑 Легенда', 'description': 'Заходите 100 дней подряд', 'icon': '👑', 'category': 'streak', 'requirement_value': 100},
        {'code': 'perfect_score', 'title': '💯 Отличник', 'description': 'Получите 100% на тесте', 'icon': '💯', 'category': 'tests', 'requirement_value': 1},
    ]

    for ach_data in achievements_data:
        existing = Achievement.query.filter_by(code=ach_data['code']).first()
        if not existing:
            achievement = Achievement(**ach_data)
            db.session.add(achievement)
            print(f"  + Добавлено достижение: {ach_data['code']}")
        else:
            print(f"  - Достижение уже существует: {ach_data['code']}")

    db.session.commit()
    print("[OK] Достижения инициализированы")
    print("\n[SUCCESS] Все новые функции успешно инициализированы!")
    print("\nНовые функции:")
    print("  1. Система стриков - отслеживание заходов дней подряд")
    print("  2. Система достижений - 10 различных достижений")
    print("  3. Темная тема - переключатель в навигации")
    print("  4. Мобильная адаптация мессенджера")
    print("  5. Обновленные иконки предметов")
