from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy import or_
from datetime import datetime
from models import db, User, TestResult, PhysicalEducationResult, Schedule, Homework, LearningMaterial, TrainingProgram, NutritionDiary, Recipe, FitnessGame, Message, GameSession, GameCard, GameParticipant, GameAnswer, MessageReaction, AdminNotification, ActivityLog
from config import Config
import json
import os
import re

# GigaChat - улучшенная проверка импорта
GIGACHAT_AVAILABLE = False
try:
    from gigachat import GigaChat
    GIGACHAT_AVAILABLE = True
    print("[OK] GigaChat успешно импортирован")
except ImportError as e:
    print(f"[WARNING] GigaChat не установлен: {e}")
    print("Установите: pip install gigachat")
    GigaChat = None
except Exception as e:
    print(f"[WARNING] Ошибка импорта GigaChat: {e}")
    GigaChat = None




# Загрузка тем из JSON
def load_subjects_topics():
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'subjects_topics.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARNING] Файл {json_path} не найден. Используется пустой набор тем.")
        return {}
    except json.JSONDecodeError:
        print(f"[WARNING] Ошибка парсинга JSON в {json_path}")
        return {}


# Вспомогательная функция для надежного парсинга JSON из ответа нейросети
def parse_json_safely(content, location_name=""):
    """
    Извлекает и парсит JSON из текста, обрезая лишние данные.
    
    Args:
        content: текст, из которого нужно извлечь JSON
        location_name: название места (для логирования)
    
    Returns:
        parsed_json: распарсенный JSON объект
        
    Raises:
        json.JSONDecodeError: если JSON не валиден
    """
    original_content = content
    
    # 1. Очистка от markdown
    content = content.replace('```json', '').replace('```', '').replace('````', '').strip()
    
    # 2. Найти первую открывающую скобку
    json_start = content.find('{')
    if json_start == -1:
        raise json.JSONDecodeError("JSON не найден (нет '{' в ответе)", content, 0)
    
    # 3. Найти последнюю закрывающую скобку
    json_end = content.rfind('}') + 1
    if json_end <= json_start:
        raise json.JSONDecodeError("JSON не закрыт (нет '}')", content, len(content))
    
    # 4. Извлечь потенциальный JSON
    potential_json = content[json_start:json_end]
    
    # 5. Пытаемся разные стратегии парсинга
    
    # Стратегия A: Прямой парсинг
    try:
        result = json.loads(potential_json)
        return result
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Прямой парсинг не прошел: {str(e)[:80]}")
    
    # Стратегия B: Обрезать конец (лишние символы после })
    for i in range(len(potential_json) - 1, -1, -1):
        if potential_json[i] == '}':
            candidate = potential_json[:i+1]
            try:
                result = json.loads(candidate)
                print(f"[INFO] JSON очищен от лишних {len(potential_json) - (i+1)} символов в конце")
                return result
            except json.JSONDecodeError:
                continue
    
    # Стратегия C: Убрать управляющие символы и попробовать снова
    cleaned = potential_json.replace('\x00', '').replace('\r', '').replace('\n', ' ')
    try:
        result = json.loads(cleaned)
        print(f"[INFO] JSON успешно спарсен после очистки управляющих символов")
        return result
    except json.JSONDecodeError as e:
        print(f"[DEBUG] После очистки управляющих: {str(e)[:80]}")
    
    # Стратегия D: Попытка найти правильные границы JSON
    # Этот подход подсчитывает открывающие и закрывающие скобки
    brace_count = 0
    for i in range(json_start, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                candidate = content[json_start:i+1]
                try:
                    result = json.loads(candidate)
                    print(f"[INFO] JSON найден по подсчету скобок")
                    return result
                except json.JSONDecodeError:
                    pass
                break
    
    # 6. Если ничего не помогло, выдать информативную ошибку
    print(f"[ERROR] Не удалось парсить JSON{' (' + location_name + ')' if location_name else ''}")
    print(f"[DEBUG] Исходный ответ (первые 300 символов): {original_content[:300]}")
    print(f"[DEBUG] Потенциальный JSON (первые 300 символов): {potential_json[:300]}")
    print(f"[DEBUG] Потенциальный JSON (последние 300 символов): {potential_json[-300:]}")
    print(f"[DEBUG] Длина потенциального JSON: {len(potential_json)}")
    
    raise json.JSONDecodeError(
        f"JSON невозможно парсить ({location_name}). Попробовали 4 стратегии парсинга.",
        potential_json[:100],
        0
    )


SUBJECTS_TOPICS = load_subjects_topics()
app = Flask(__name__)
app.config.from_object(Config)


# Инициализация
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Создание БД
with app.app_context():
    # Проверяем, существует ли колонка nickname
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    
    try:
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        # Проверяем и добавляем колонку nickname
        if 'nickname' not in columns:
            # Добавляем колонку nickname через ALTER TABLE
            print("[INFO] Добавление колонки nickname в таблицу user...")
            with db.engine.connect() as conn:
                # SQLite не поддерживает ALTER TABLE ADD COLUMN с UNIQUE напрямую
                # Сначала добавляем колонку без UNIQUE
                conn.execute(text("ALTER TABLE user ADD COLUMN nickname VARCHAR(80)"))
                conn.commit()
        
        # Проверяем и добавляем колонку role
        if 'role' not in columns:
            print("[INFO] Добавление колонки role в таблицу user...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'student'"))
                conn.commit()
            
            # Обновляем существующих пользователей (по умолчанию student)
            try:
                db.session.execute(text("UPDATE user SET role = 'student' WHERE role IS NULL"))
                db.session.commit()
                print("[OK] Обновлены роли существующих пользователей")
            except Exception as e:
                print(f"[WARNING] Ошибка при обновлении ролей: {e}")
                db.session.rollback()
        
        # Проверяем и добавляем колонку mentor_id
        if 'mentor_id' not in columns:
            print("[INFO] Добавление колонки mentor_id в таблицу user...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN mentor_id INTEGER"))
                conn.commit()
            
            # Обновляем существующих пользователей
            try:
                users = User.query.all()
                for user in users:
                    if not hasattr(user, 'nickname') or not user.nickname:
                        # Используем username как nickname по умолчанию
                        db.session.execute(
                            text("UPDATE user SET nickname = :username WHERE id = :user_id"),
                            {"username": user.username, "user_id": user.id}
                        )
                db.session.commit()
                print(f"[OK] Миграция завершена. Обновлено {len(users)} пользователей.")
            except Exception as e:
                print(f"[WARNING] Ошибка при обновлении пользователей: {e}")
                db.session.rollback()
        else:
            # Колонка уже существует, просто обновляем пустые значения
            users_without_nickname = db.session.execute(
                text("SELECT id, username FROM user WHERE nickname IS NULL OR nickname = ''")
            ).fetchall()
            
            for user_id, username in users_without_nickname:
                db.session.execute(
                    text("UPDATE user SET nickname = :username WHERE id = :user_id"),
                    {"username": username, "user_id": user_id}
                )
            
            if users_without_nickname:
                db.session.commit()
                print(f"[INFO] Обновлено {len(users_without_nickname)} пользователей: добавлен nickname")
    except Exception as e:
        print(f"[WARNING] Ошибка при проверке миграции: {e}")
        # Если таблица еще не создана, создаем её
        try:
            db.create_all()
            print("[OK] База данных создана")
        except Exception as create_error:
            print(f"[ERROR] Ошибка создания БД: {create_error}")
    
    # Создаем все таблицы (если их еще нет)
    db.create_all()
    
    # Миграция для таблицы message - добавляем колонки message_type и file_path
    try:
        inspector = inspect(db.engine)
        message_columns = [col['name'] for col in inspector.get_columns('message')]
        
        # Добавляем колонку message_type если её нет
        if 'message_type' not in message_columns:
            print("[INFO] Добавление колонки message_type в таблицу message...")
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE message ADD COLUMN message_type VARCHAR(20) DEFAULT 'text'"))
                    conn.commit()
                print("[OK] Колонка message_type добавлена")
            except Exception as e:
                print(f"[WARNING] Ошибка при добавлении message_type: {e}")
                db.session.rollback()
        
        # Добавляем колонку file_path если её нет
        if 'file_path' not in message_columns:
            print("[INFO] Добавление колонки file_path в таблицу message...")
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE message ADD COLUMN file_path VARCHAR(500)"))
                    conn.commit()
                print("[OK] Колонка file_path добавлена")
            except Exception as e:
                print(f"[WARNING] Ошибка при добавлении file_path: {e}")
                db.session.rollback()
        
        # Обновляем существующие сообщения (устанавливаем message_type = 'text' если null)
        try:
            db.session.execute(text("UPDATE message SET message_type = 'text' WHERE message_type IS NULL"))
            db.session.commit()
            print("[OK] Миграция message завершена")
        except Exception as e:
            print(f"[WARNING] Ошибка при обновлении message_type: {e}")
            db.session.rollback()
    except Exception as e:
        print(f"[WARNING] Таблица message еще не существует - будет создана при инициализации: {e}")
    
    # Проверка настроек GigaChat при запуске
    if GIGACHAT_AVAILABLE:
        creds = app.config.get('GIGACHAT_CREDENTIALS')
        if creds:
            print(f"[OK] GIGACHAT_CREDENTIALS настроены (длина: {len(creds)} символов)")
        else:
            print("[WARNING] GIGACHAT_CREDENTIALS не найдены в config.py!")
            print("Добавьте в config.py: GIGACHAT_CREDENTIALS = 'ваш_ключ'")

    # Миграция: новые колонки для User (is_approved, is_banned)
    try:
        inspector = inspect(db.engine)
        user_columns = [col['name'] for col in inspector.get_columns('user')]

        if 'is_approved' not in user_columns:
            print("[INFO] Добавление колонки is_approved в таблицу user...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN is_approved BOOLEAN DEFAULT 1"))
                conn.commit()

        if 'is_banned' not in user_columns:
            print("[INFO] Добавление колонки is_banned в таблицу user...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN is_banned BOOLEAN DEFAULT 0"))
                conn.commit()
    except Exception as e:
        print(f"[WARNING] Миграция user (is_approved/is_banned): {e}")

    # Миграция: новые колонки для Recipe (user_id, status)
    try:
        inspector = inspect(db.engine)
        recipe_columns = [col['name'] for col in inspector.get_columns('recipe')]

        if 'user_id' not in recipe_columns:
            print("[INFO] Добавление колонки user_id в таблицу recipe...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE recipe ADD COLUMN user_id INTEGER"))
                conn.commit()

        if 'status' not in recipe_columns:
            print("[INFO] Добавление колонки status в таблицу recipe...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE recipe ADD COLUMN status VARCHAR(20) DEFAULT 'approved'"))
                conn.commit()
    except Exception as e:
        print(f"[WARNING] Миграция recipe (user_id/status): {e}")

    # Создаём таблицы AdminNotification и ActivityLog
    db.create_all()

    # Создание аккаунта администратора
    admin_email = 'mur4ika1@gmail.com'
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        print("[INFO] Создание аккаунта администратора...")
        admin_password = bcrypt.generate_password_hash('59655965').decode('utf-8')
        admin = User(
            username='Admin',
            nickname='admin',
            email=admin_email,
            password=admin_password,
            role='admin',
            is_approved=True,
            is_banned=False
        )
        db.session.add(admin)
        db.session.commit()
        print("[OK] Аккаунт администратора создан")
    elif admin.role != 'admin':
        admin.role = 'admin'
        admin.is_approved = True
        db.session.commit()
        print("[OK] Существующий пользователь обновлён до администратора")


@app.route('/api/subjects-topics')
def get_subjects_topics():
    return jsonify(SUBJECTS_TOPICS)


# РЕГИСТРАЦИЯ
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')

        # Проверяем username на уникальность
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже используется', 'error')
            return redirect(url_for('register'))

        # Если никнейм не указан, используем username
        if not nickname or nickname.strip() == '':
            nickname = username

        # Проверяем уникальность никнейма
        existing_user = User.query.filter_by(nickname=nickname).first()
        if existing_user:
            flash('Никнейм уже занят. Выберите другой.', 'error')
            return redirect(url_for('register'))

        # Валидируем роль
        if role not in ['teacher', 'student', 'cook']:
            role = 'student'

        # Учителя и повара требуют одобрения админа
        needs_approval = role in ['teacher', 'cook']

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            nickname=nickname,
            email=email,
            password=hashed_password,
            role=role,
            is_approved=not needs_approval
        )
        db.session.add(user)
        db.session.commit()

        # Создаём уведомление для админа если нужно одобрение
        if needs_approval:
            role_name = 'Учитель' if role == 'teacher' else 'Повар'
            notification = AdminNotification(
                type='registration',
                message=f'Новая заявка на регистрацию: {username} ({role_name})',
                related_user_id=user.id
            )
            db.session.add(notification)

            # Лог активности
            log = ActivityLog(
                user_id=user.id,
                action='registration_pending',
                details=f'Пользователь {username} зарегистрировался как {role_name} и ожидает одобрения'
            )
            db.session.add(log)
            db.session.commit()

            flash(f'Регистрация отправлена на одобрение администратору. Вы сможете войти после подтверждения.', 'info')
        else:
            log = ActivityLog(
                user_id=user.id,
                action='registration',
                details=f'Пользователь {username} зарегистрировался как ученик'
            )
            db.session.add(log)
            db.session.commit()
            flash('Регистрация успешна', 'success')

        return redirect(url_for('login'))

    return render_template('register.html')


# ВХОД
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            if user.is_banned:
                flash('Ваш аккаунт заблокирован. Обратитесь к администратору.', 'error')
                return redirect(url_for('login'))
            if not user.is_approved:
                flash('Ваш аккаунт ещё не одобрен администратором. Пожалуйста, подождите.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль', 'error')

    return render_template('login.html')


# ВЫХОД
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ГЛАВНАЯ
@app.route('/')
@login_required
def dashboard():
    tests = TestResult.query.filter_by(user_id=current_user.id).order_by(TestResult.created_at.desc()).limit(10).all()
    pe_results = PhysicalEducationResult.query.filter_by(user_id=current_user.id).order_by(PhysicalEducationResult.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', tests=tests, pe_results=pe_results)


# ЛИЧНЫЙ КАБИНЕТ
@app.route('/profile')
@login_required
def profile():
    if current_user.is_admin():
        return redirect(url_for('admin_panel'))
    elif current_user.is_cook():
        return redirect(url_for('cook_profile'))
    elif current_user.is_teacher():
        return redirect(url_for('teacher_profile'))
    else:
        return redirect(url_for('student_profile'))


# ПРОФИЛЬ УЧЕНИКА
@app.route('/profile/student')
@login_required
def student_profile():
    if current_user.is_teacher():
        return redirect(url_for('teacher_profile'))
    if current_user.is_cook():
        return redirect(url_for('cook_profile'))
    if current_user.is_admin():
        return redirect(url_for('admin_panel'))
    
    # Статистика тестов
    tests = TestResult.query.filter_by(user_id=current_user.id).all()
    tests_count = len(tests)
    recent_tests = TestResult.query.filter_by(user_id=current_user.id).order_by(TestResult.created_at.desc()).limit(5).all()
    
    # Средняя оценка
    scores = [t.score for t in tests if t.score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    
    # Статистика тренировок
    pe_count = PhysicalEducationResult.query.filter_by(user_id=current_user.id).count()
    
    # Статистика сообщений
    messages_sent = Message.query.filter_by(sender_id=current_user.id).count()
    messages_received = Message.query.filter_by(receiver_id=current_user.id).count()
    
    # Программы тренировок
    training_programs_count = TrainingProgram.query.filter_by(user_id=current_user.id).count()
    
    return render_template('student_profile.html',
                         tests_count=tests_count,
                         pe_count=pe_count,
                         avg_score=avg_score,
                         messages_sent=messages_sent,
                         messages_received=messages_received,
                         training_programs_count=training_programs_count,
                         recent_tests=recent_tests,
                         mentor=current_user.mentor)


# ПРОФИЛЬ УЧИТЕЛЯ
@app.route('/profile/teacher')
@login_required
def teacher_profile():
    if not current_user.is_teacher():
        return redirect(url_for('student_profile'))
    
    students_query = current_user.assigned_students.order_by(User.created_at.desc())
    students = students_query.all()
    students_count = len(students)
    student_ids = [s.id for s in students]
    
    if student_ids:
        all_tests = TestResult.query.filter(TestResult.user_id.in_(student_ids)).all()
        all_tests_count = len(all_tests)
        all_scores = [t.score for t in all_tests if t.score is not None]
        avg_score_all = round(sum(all_scores) / len(all_scores)) if all_scores else 0
        all_pe_count = PhysicalEducationResult.query.filter(PhysicalEducationResult.user_id.in_(student_ids)).count()
        recent_student_tests = TestResult.query.filter(TestResult.user_id.in_(student_ids)).order_by(TestResult.created_at.desc()).limit(10).all()
    else:
        all_tests_count = 0
        avg_score_all = 0
        all_pe_count = 0
        recent_student_tests = []
    
    return render_template('teacher_profile.html',
                         students_count=students_count,
                         all_tests_count=all_tests_count,
                         avg_score_all=avg_score_all,
                         all_pe_count=all_pe_count,
                         recent_student_tests=recent_student_tests,
                         students=students)


# УПРАВЛЕНИЕ УЧЕНИКАМИ (для учителя)
@app.route('/teacher/students')
@login_required
def teacher_students():
    if not current_user.is_teacher():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))
    
    students = current_user.assigned_students.order_by(User.created_at.desc()).all()
    
    # Статистика для каждого ученика
    students_data = []
    for student in students:
        tests = TestResult.query.filter_by(user_id=student.id).all()
        scores = [t.score for t in tests if t.score is not None]
        avg_score = round(sum(scores) / len(scores)) if scores else 0
        
        students_data.append({
            'student': student,
            'tests_count': len(tests),
            'avg_score': avg_score,
            'pe_count': PhysicalEducationResult.query.filter_by(user_id=student.id).count(),
            'last_activity': student.created_at
        })
    
    return render_template('teacher_students.html', students_data=students_data)


# ПРОСМОТР РЕЗУЛЬТАТОВ УЧЕНИКА (для учителя)
@app.route('/teacher/student/<int:student_id>')
@login_required
def teacher_view_student(student_id):
    if not current_user.is_teacher():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))
    
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Этот пользователь не является учеником', 'error')
        return redirect(url_for('teacher_students'))
    
    if student.mentor_id != current_user.id:
        flash('Этот ученик не прикреплен к вам', 'error')
        return redirect(url_for('teacher_students'))
    
    # Все тесты ученика
    tests = TestResult.query.filter_by(user_id=student.id).order_by(TestResult.created_at.desc()).all()
    
    # Статистика
    scores = [t.score for t in tests if t.score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    
    # Тренировки
    pe_results = PhysicalEducationResult.query.filter_by(user_id=student.id).order_by(PhysicalEducationResult.created_at.desc()).all()
    
    # Программы тренировок
    training_programs = TrainingProgram.query.filter_by(user_id=student.id).all()
    
    return render_template('teacher_view_student.html',
                         student=student,
                         tests=tests,
                         avg_score=avg_score,
                         pe_results=pe_results,
                         training_programs=training_programs)


# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
@app.route('/users')
@login_required
def users_list():
    query = (request.args.get('q') or '').strip()
    users_query = User.query.filter(User.id != current_user.id)
    
    if query:
        like_pattern = f"%{query}%"
        users_query = users_query.filter(
            or_(
                User.username.ilike(like_pattern),
                User.nickname.ilike(like_pattern),
                User.email.ilike(like_pattern)
            )
        )
    
    users = users_query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=users, query=query)


# ПУБЛИЧНЫЙ ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
@app.route('/users/<int:user_id>')
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return redirect(url_for('profile'))
    
    is_teacher = user.is_teacher()
    is_student = user.is_student()
    teacher_students = user.assigned_students.order_by(User.created_at.desc()).all() if is_teacher else []
    students_count = len(teacher_students) if is_teacher else 0
    
    tests = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.created_at.desc()).limit(5).all()
    pe_count = PhysicalEducationResult.query.filter_by(user_id=user.id).count()
    
    can_join_teacher = current_user.is_student() and is_teacher
    already_joined = current_user.mentor_id == user.id if can_join_teacher else False
    mentor = user.mentor if is_student else None
    
    return render_template('user_profile.html',
                         profile_user=user,
                         is_teacher=is_teacher,
                         is_student=is_student,
                         tests=tests,
                         pe_count=pe_count,
                         students_count=students_count,
                         teacher_students=teacher_students,
                         can_join_teacher=can_join_teacher,
                         already_joined=already_joined,
                         mentor=mentor)


# ПРИСОЕДИНИТЬСЯ К УЧИТЕЛЮ
@app.route('/users/<int:user_id>/assign', methods=['POST'])
@login_required
def assign_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    
    if not teacher.is_teacher():
        flash('Этот пользователь не является учителем', 'error')
        return redirect(url_for('view_user', user_id=user_id))
    
    if not current_user.is_student():
        flash('Только ученик может присоединиться к учителю', 'error')
        return redirect(url_for('view_user', user_id=user_id))
    
    current_user.mentor_id = teacher.id
    db.session.commit()
    flash(f'Вы успешно присоединились к учителю {teacher.nickname or teacher.username}', 'success')
    return redirect(url_for('view_user', user_id=user_id))


# ОТКРЕПИТЬСЯ ОТ УЧИТЕЛЯ
@app.route('/users/<int:user_id>/unassign', methods=['POST'])
@login_required
def unassign_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    
    if not teacher.is_teacher():
        flash('Этот пользователь не является учителем', 'error')
        return redirect(url_for('view_user', user_id=user_id))
    
    if not current_user.is_student() or current_user.mentor_id != teacher.id:
        flash('Вы не прикреплены к этому учителю', 'error')
        return redirect(url_for('view_user', user_id=user_id))
    
    current_user.mentor_id = None
    db.session.commit()
    flash('Вы успешно открепились от учителя', 'success')
    return redirect(url_for('view_user', user_id=user_id))


# ГЕНЕРАТОР ТЕСТОВ - СТРАНИЦА
@app.route('/tests')
@login_required
def tests():
    user_tests = TestResult.query.filter_by(user_id=current_user.id).order_by(TestResult.created_at.desc()).all()
    return render_template('tests.html', tests=user_tests)


# API ГЕНЕРАЦИИ ТЕСТА
@app.route('/api/generate-test', methods=['POST'])
@login_required
def api_generate_test():
    data = request.json
    subject = data.get('subject')
    topic = data.get('topic')
    custom_text = data.get('custom_text', '')
    num_questions = int(data.get('num_questions', 10))
    
    # Проверка доступности GigaChat
    if not GIGACHAT_AVAILABLE or GigaChat is None:
        print("[WARNING] GigaChat недоступен, используется fallback")
        questions = []
        for i in range(1, num_questions + 1):
            q_text = f"Вопрос {i} по теме: {topic or 'общие знания'}"
            options = [f"Вариант {c}" for c in ['A', 'B', 'C', 'D']]
            questions.append({
                'question': q_text,
                'options': options,
                'correct': 1,
                'explanation': f"Правильный ответ - {options[1]} (второй вариант)."
            })

        test_data = {'questions': questions}
        
        new_test = TestResult(
            user_id=current_user.id,
            subject=subject if not custom_text else "Пользовательский материал",
            topic=topic if not custom_text else "Тест из загруженного текста",
            test_content=json.dumps(test_data, ensure_ascii=False)
        )
        db.session.add(new_test)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'test_id': new_test.id,
            'questions_count': len(test_data['questions']),
            'warning': 'GigaChat недоступен. Используются тестовые данные.'
        })
    
    # Проверка credentials
    credentials = app.config.get('GIGACHAT_CREDENTIALS')
    if not credentials:
        return jsonify({
            'success': False, 
            'error': 'GIGACHAT_CREDENTIALS не настроены в config.py'
        }), 500
    
    # Используем GigaChat для генерации
    try:
        print(f"[INFO] Запуск GigaChat для генерации теста...")
        
        with GigaChat(
            credentials=credentials, 
            verify_ssl_certs=False,
            scope="GIGACHAT_API_PERS",
            temperature=0.3
        ) as giga:
            
            if custom_text:
                prompt = f"""Создай JSON тест с {num_questions} вопросами по тексту.

⚠️ АБСОЛЮТНО СТРОГИЕ ТРЕБОВАНИЯ:
✓ ТОЛЬКО ВАЛИДНЫЙ JSON - начни с {{ и закончи с }}
✓ Без markdown, без кода, без объяснений ДО И ПОСЛЕ JSON
✓ "correct" - число: 0, 1, 2 или 3 ТОЛЬКО
✓ "options" - массив РОВНО 4 строк
✓ Поля: "question", "options", "correct", "explanation"

📋 ФОРМАТ (КОПИРУЙ ТОЧНО, ДАЖЕ ПРОБЕЛЫ):
{{"questions":[{{"question":"Q1","options":["A","B","C","D"],"correct":0,"explanation":"E1"}},{{"question":"Q2","options":["A","B","C","D"],"correct":1,"explanation":"E2"}}]}}

ТЕКСТ ДЛЯ ТЕСТА:
{custom_text}

ВЫПОЛНИ:
1. Прочитай текст выше
2. Создай {num_questions} вопросов к нему
3. Каждый вопрос в JSON формате
4. Верни ТОЛЬКО JSON без пробелов в начале и конце
5. НИКАКИХ объяснений, комментариев, кода

ГОТОВ? НАЧНИ С {{ :"""
            else:
                prompt = f"""Создай ТОЛЬКО JSON тест ({num_questions} вопросов).

ПРЕДМЕТ: {subject}
ТЕМА: {topic}

⚠️ КРИТИЧЕСКИЕ ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON - ничего больше, никаких слов
2. "correct" значение: только 0, 1, 2 или 3
3. "options" содержит ровно 4 элемента
4. Каждая question, каждый option, каждое explanation - строка

JSON ШАБЛОН (ИСПОЛЬЗУЙ):
{{"questions":[{{"question":"Вопрос 1?","options":["Опция1","Опция2","Опция3","Опция4"],"correct":0,"explanation":"Объяснение"}}]}}

ГЕНЕРИРУЙ {num_questions} ТАКИХ ВОПРОСОВ.
НАЧНИ СРАЗУ С {{, БЕЗ СЛОВ:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()
            
            print("=" * 80)
            print("GIGACHAT ОТВЕТ (первые 500 символов):")
            print(content[:500])
            print("=" * 80)
            
            try:
                test_data = parse_json_safely(content, "generate-test")
            except json.JSONDecodeError as je:
                print(f"[ERROR] JSON парсинг ошибка (тесты): {je}")
                print(f"[ERROR] Ответ от GigaChat: {content[:1000]}")
                # Пытаемся создать fallback тест
                try:
                    # Извлекаем вопросы, если это возможно
                    # Пытаемся найти JSON части вручную
                    if '"questions"' in content or '\"questions\"' in content:
                        # Есть структура, попробуем спасти вопросы
                        questions = []
                        # Ищем pattern "question": "...", "options": ...
                        pattern = r'"question"\s*:\s*"([^"]*)".*?"options"\s*:\s*\[(.*?)\].*?"correct"\s*:\s*(\d+).*?"explanation"\s*:\s*"([^"]*)"'
                        matches = re.finditer(pattern, content, re.DOTALL)
                        for match in matches:
                            try:
                                q_text = match.group(1)
                                options_str = match.group(2)
                                correct = int(match.group(3))
                                explanation = match.group(4)
                                # Извлекаем опции
                                options = re.findall(r'"([^"]*)"', options_str)[:4]
                                if len(options) == 4 and 0 <= correct <= 3:
                                    questions.append({
                                        'question': q_text,
                                        'options': options,
                                        'correct': correct,
                                        'explanation': explanation
                                    })
                            except:
                                pass
                        
                        if len(questions) >= 3:
                            test_data = {'questions': questions[:num_questions]}
                            print(f"[OK] Спасли {len(questions)} вопросов из ответа GigaChat")
                        else:
                            return jsonify({'success': False, 'error': 'Невозможно спасти данные из ответа GigaChat'}), 500
                    else:
                        return jsonify({'success': False, 'error': 'GigaChat вернул невалидный JSON'}), 500
                except Exception as e:
                    print(f"[ERROR] Ошибка при спасении данных: {e}")
                    return jsonify({'success': False, 'error': 'Невалидный JSON от GigaChat'}), 500
            
            if 'questions' not in test_data or not test_data['questions']:
                return jsonify({'success': False, 'error': 'Нет вопросов'}), 500
            
            valid_questions = []
            for i, q in enumerate(test_data['questions'], 1):
                if not all(k in q for k in ['question', 'options', 'correct', 'explanation']):
                    continue
                
                if len(q['options']) != 4:
                    continue
                
                correct_idx = q['correct']
                
                if not isinstance(correct_idx, int) or not (0 <= correct_idx <= 3):
                    q['correct'] = 0
                
                if len(q['explanation']) < 30:
                    q['explanation'] = f"Правильный ответ: {q['options'][q['correct']]}."
                
                valid_questions.append(q)
            
            if len(valid_questions) < 3:
                return jsonify({'success': False, 'error': f'Мало вопросов: {len(valid_questions)}'}), 500
            
            test_data['questions'] = valid_questions[:num_questions]
            
            new_test = TestResult(
                user_id=current_user.id,
                subject=subject if not custom_text else "Пользовательский материал",
                topic=topic if not custom_text else "Тест из загруженного текста",
                test_content=json.dumps(test_data, ensure_ascii=False)
            )
            db.session.add(new_test)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'test_id': new_test.id,
                'questions_count': len(test_data['questions'])
            })
        
    except Exception as e:
        print(f"[ERROR] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ПРОХОЖДЕНИЕ ТЕСТА
@app.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    test = TestResult.query.get_or_404(test_id)
    if test.user_id != current_user.id:
        return redirect(url_for('dashboard'))
    
    test_data = json.loads(test.test_content)
    return render_template('take_test.html', test=test, test_data=test_data)


# ПРОВЕРКА ТЕСТА
@app.route('/test/<int:test_id>/check', methods=['POST'])
@login_required
def check_test(test_id):
    test = TestResult.query.get_or_404(test_id)
    if test.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    test_data = json.loads(test.test_content)
    user_answers = request.json.get('answers', {})
    
    correct_count = 0
    total = len(test_data['questions'])
    
    for i, question in enumerate(test_data['questions']):
        user_answer = user_answers.get(str(i))
        if user_answer is not None and int(user_answer) == question['correct']:
            correct_count += 1
    
    score = round((correct_count / total) * 100) if total > 0 else 0
    
    test.score = score
    db.session.commit()
    
    return jsonify({
        'score': score,
        'correct': correct_count,
        'total': total
    })


# УДАЛЕНИЕ ТЕСТА
@app.route('/api/test/<int:test_id>', methods=['DELETE'])
@login_required
def delete_test(test_id):
    test = TestResult.query.filter_by(id=test_id, user_id=current_user.id).first()
    if not test:
        return jsonify({'success': False, 'error': 'Test not found'}), 404
    
    db.session.delete(test)
    db.session.commit()
    
    return jsonify({'success': True})


# ФИЗКУЛЬТУРА
@app.route('/physical-education')
@login_required
def physical_education():
    return render_template('physical_education.html')


# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ФИЗКУЛЬТУРЫ
@app.route('/api/save-pe-result', methods=['POST'])
@login_required
def save_pe_result():
    data = request.get_json()
    
    pe_result = PhysicalEducationResult(
        user_id=current_user.id,
        exercise_type=data.get('exercise_type'),
        repetitions=data.get('repetitions', 0),
        correct_count=data.get('correct_count', 0),
        incorrect_count=data.get('incorrect_count', 0),
        errors=json.dumps(data.get('errors', []), ensure_ascii=False),
        score=data.get('score', 0)
    )
    db.session.add(pe_result)
    db.session.commit()
    
    return jsonify({'status': 'success', 'id': pe_result.id})


# API для получения тем
@app.route('/api/topics/<subject>')
def get_topics(subject):
    topics = SUBJECTS_TOPICS.get(subject, [])
    return jsonify({'topics': topics})


# ОБУЧЕНИЕ/ТЕОРИЯ
@app.route('/learning')
@login_required
def learning():
    materials = LearningMaterial.query.order_by(LearningMaterial.created_at.desc()).all()
    return render_template('learning.html', materials=materials)


@app.route('/learning/<int:material_id>')
@login_required
def view_material(material_id):
    material = LearningMaterial.query.get_or_404(material_id)
    return render_template('view_material.html', material=material)


# ПРОГРАММЫ ТРЕНИРОВОК
@app.route('/training-programs')
@login_required
def training_programs():
    # Убедимся, что у пользователя есть набор из 10 готовых программ
    def ensure_default_programs(user):
        existing = TrainingProgram.query.filter_by(user_id=user.id).count()
        if existing >= 10:
            return

        default_templates = [
            {
                'title': 'Базовая сила (4 недели)',
                'duration': '1 месяц',
                'schedule': {
                    'Понедельник': ['Приседания - 3×8', 'Жим лёжа - 3×8', 'Планка - 3×60с'],
                    'Среда': ['Тяга в наклоне - 3×8', 'Выпады - 3×10', 'Скручивания - 3×20'],
                    'Пятница': ['Румынская тяга - 3×8', 'Жим над головой - 3×8', 'Подтягивания - 3×6']
                }
            },
            {
                'title': 'Кардио и выносливость (2 недели)',
                'duration': '2 недели',
                'schedule': {
                    'Понедельник': ['Бег 30 мин', 'Скакалка 10 мин'],
                    'Среда': ['Интервальный бег 20 мин', 'Берпи 3×15'],
                    'Суббота': ['Велотренажёр 40 мин']
                }
            },
            {
                'title': 'Функциональная тренировка (3 недели)',
                'duration': '3 недели',
                'schedule': {
                    'Вторник': ['Мёртвая тяга с гантелями - 3×10', 'Русские скручивания - 3×20'],
                    'Четверг': ['Бёрпи - 4×12', 'Отжимания - 4×15']
                }
            },
            {
                'title': 'Похудение (6 недель)',
                'duration': '1 месяц',
                'schedule': {
                    'Понедельник': ['Интервальное кардио 30 мин', 'Приседания с собственным весом - 3×15'],
                    'Среда': ['HIIT 20 мин', 'Планка - 3×60с'],
                    'Пятница': ['Бег 40 мин']
                }
            },
            {
                'title': 'Гибкость и мобильность (2 недели)',
                'duration': '2 недели',
                'schedule': {
                    'Ежедневно': ['Растяжка 20 мин', 'Динамическая разминка 10 мин']
                }
            },
            {
                'title': 'Тренировка корпуса (4 недели)',
                'duration': '1 месяц',
                'schedule': {
                    'Вторник': ['Скручивания - 4×20', 'Боковая планка - 3×45с'],
                    'Четверг': ['Подъёмы ног - 4×15', 'Русские скручивания - 4×20']
                }
            },
            {
                'title': 'Домашняя программа без инвентаря (3 недели)',
                'duration': '3 недели',
                'schedule': {
                    'Понедельник': ['Приседания 4×20', 'Отжимания 4×15', 'Планка 3×60с'],
                    'Среда': ['Выпады 4×15', 'Бёрпи 4×12'],
                    'Пятница': ['Скручивания 4×25', 'Мост 4×12']
                }
            },
            {
                'title': 'Сила на рельсе (4 недели)',
                'duration': '1 месяц',
                'schedule': {
                    'Понедельник': ['Приседания 5×5', 'Тяга 5×5'],
                    'Среда': ['Жим 5×5', 'Подтягивания 4×6'],
                    'Пятница': ['Становая тяга 3×5']
                }
            },
            {
                'title': 'Сплит верх/низ (4 недели)',
                'duration': '1 месяц',
                'schedule': {
                    'Понедельник': ['Ноги: Присед 4×8, Выпады 3×12'],
                    'Вторник': ['Верх: Жим 4×8, Тяга 4×8'],
                    'Четверг': ['Ноги: Румынская тяга 4×8, Икры 3×15'],
                    'Пятница': ['Верх: Подтягивания 4×8, Отжимания 4×15']
                }
            },
            {
                'title': 'Комплексная подготовка (8 недель)',
                'duration': '2 месяца',
                'schedule': {
                    'Понедельник': ['Силовая тренировка 60 мин'],
                    'Среда': ['Кардио 45 мин'],
                    'Пятница': ['Смешанная тренировка 50 мин']
                }
            }
        ]

        for tpl in default_templates:
            program = TrainingProgram(
                user_id=user.id,
                title=tpl['title'],
                duration=tpl['duration'],
                schedule=json.dumps(tpl['schedule'], ensure_ascii=False)
            )
            db.session.add(program)
        db.session.commit()

    ensure_default_programs(current_user)
    programs = TrainingProgram.query.filter_by(user_id=current_user.id).order_by(TrainingProgram.created_at.desc()).all()
    return render_template('training_programs.html', programs=programs)


@app.route('/training-programs/<int:program_id>/edit', methods=['POST'])
@login_required
def edit_program(program_id):
    program = TrainingProgram.query.filter_by(id=program_id, user_id=current_user.id).first_or_404()
    data = request.get_json() or {}
    title = data.get('title')
    duration = data.get('duration')
    schedule = data.get('schedule')
    if title:
        program.title = title
    if duration:
        program.duration = duration
    if schedule is not None:
        program.schedule = json.dumps(schedule, ensure_ascii=False)
    db.session.commit()
    return jsonify({'success': True, 'id': program.id})


@app.route('/api/generate-training-program', methods=['POST'])
@login_required
def api_generate_training_program():
    data = request.get_json() or {}
    goal = data.get('goal', '')
    duration = data.get('duration', '1 месяц')
    level = data.get('level', 'начальный')
    preferences = data.get('preferences', '')  # Дополнительные пожелания

    # Fallback если GigaChat недоступен
    if not GIGACHAT_AVAILABLE or GigaChat is None:
        # Простая генерация шаблона
        schedule = {
            'Понедельник': [f'{goal} — лёгкая сессия 30 мин'],
            'Среда': [f'{goal} — средняя сессия 30-45 мин'],
            'Пятница': [f'{goal} — интенсивная сессия 30-45 мин']
        }
        return jsonify({'success': True, 'program': {'title': f'{goal} — программа ({level})', 'duration': duration, 'schedule': schedule}, 'warning': 'GigaChat недоступен'})

    credentials = app.config.get('GIGACHAT_CREDENTIALS')
    if not credentials:
        return jsonify({'success': False, 'error': 'GIGACHAT_CREDENTIALS не настроены'}), 500

    try:
        with GigaChat(credentials=credentials, verify_ssl_certs=False, scope='GIGACHAT_API_PERS', temperature=0.4) as giga:
            # Строим промт с учетом пожеланий
            preferences_text = ""
            if preferences:
                preferences_text = f"""
ДОПОЛНИТЕЛЬНЫЕ ПОЖЕЛАНИЯ ПОЛЬЗОВАТЕЛЯ:
{preferences}

Обязательно учитай эти пожелания при создании программы!"""

            prompt = f"""Создай СТРОГО JSON тренировочную программу.

ПАРАМЕТРЫ:
- Цель: {goal}
- Уровень подготовки: {level}
- Длительность: {duration}{preferences_text}

⚠️ КРИТИЧЕСКИЕ ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON, БЕЗ текста до/после
2. schedule содержит ВСЕ 7 дней недели (Понедельник-Воскресенье)
3. Каждый день (value) - массив упражнений: ["упр - 3×10", "упр2 - 2×12"]
4. title - информативное название программы
5. Программа соответствует УРОВНЮ и ЦЕЛИ

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ JSON:
{{"title":"Название программы","duration":"{duration}","schedule":{{"Понедельник":["упр1 - 3×10"],"Вторник":["упр2 - 2×12"],"Среда":["упр1 - 3×12"],"Четверг":["упр3 - 3×10"],"Пятница":["упр2 - 3×10"],"Суббота":["упр4 - 2×15"],"Воскресенье":["отдых или растяжка"]}}}}

НАЧНИ С {{ БЕЗ ОБЪЯСНЕНИЙ:"""
            
            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()
            
            try:
                program_data = parse_json_safely(content, "generate-training-program")
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON ошибка (программа): {e}")
                # Fallback на шаблон
                return jsonify({'success': True, 'program': {
                    'title': f'{goal} — программа ({level})',
                    'duration': duration,
                    'schedule': {
                        'Понедельник': [f'{goal} - базовые упражнения 30 мин'],
                        'Среда': [f'{goal} - промежуточные упражнения 40 мин'],
                        'Пятница': [f'{goal} - интенсивные упражнения 45 мин']
                    }
                }, 'warning': 'GigaChat вернул невалидный JSON, использован шаблон'}), 200
            
            # Валидация и нормализация
            program_data['schedule'] = program_data.get('schedule') or {}
            program_data['title'] = program_data.get('title') or f'{goal} — программа'
            program_data['duration'] = program_data.get('duration') or duration
            
            # Убедимся что schedule - объект и содержит необходимые дни
            if not isinstance(program_data['schedule'], dict):
                program_data['schedule'] = {}
            
            # Добавляем недостающие дни если нужно
            days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            for day in days:
                if day not in program_data['schedule']:
                    program_data['schedule'][day] = ['отдых'] if day == 'Воскресенье' else []
            
            return jsonify({'success': True, 'program': program_data})

    except Exception as e:
        print(f"[ERROR] ERROR generate-training-program: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/training-programs/create', methods=['GET', 'POST'])
@login_required
def create_program():
    if request.method == 'POST':
        data = request.get_json()
        program = TrainingProgram(
            user_id=current_user.id,
            title=data['title'],
            duration=data['duration'],
            schedule=json.dumps(data['schedule'], ensure_ascii=False)
        )
        db.session.add(program)
        db.session.commit()
        return jsonify({'status': 'success', 'id': program.id})
    
    return redirect(url_for('training_programs'))


@app.route('/training-programs/<int:program_id>/schedule')
@login_required
def get_program_schedule(program_id):
    program = TrainingProgram.query.filter_by(id=program_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'title': program.title,
        'schedule': json.loads(program.schedule)
    })


@app.route('/training-programs/<int:program_id>/start')
@login_required
def start_training(program_id):
    program = TrainingProgram.query.filter_by(id=program_id, user_id=current_user.id).first_or_404()
    schedule = json.loads(program.schedule)
    today = datetime.now().strftime('%A')
    return render_template('start_training.html', program=program, schedule=schedule, today=today)


# ПИТАНИЕ/ЗДОРОВЬЕ
@app.route('/nutrition')
@login_required
def nutrition():
    today = datetime.utcnow().date()
    diary = NutritionDiary.query.filter_by(
        user_id=current_user.id,
        date=today
    ).order_by(NutritionDiary.meal_type).all()
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).limit(10).all()
    return render_template('nutrition.html', diary=diary, recipes=recipes)


@app.route('/nutrition/diary/add', methods=['POST'])
@login_required
def add_diary_entry():
    data = request.get_json()
    entry = NutritionDiary(
        user_id=current_user.id,
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        meal_type=data['meal_type'],
        food_items=json.dumps(data['food_items'], ensure_ascii=False),
        calories=data['calories'],
        proteins=data['proteins'],
        fats=data['fats'],
        carbs=data['carbs']
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'status': 'success', 'id': entry.id})


# API: сгенерировать план питания на день через GigaChat
@app.route('/api/generate-mealplan', methods=['POST'])
@login_required
def api_generate_mealplan():
    data = request.get_json()
    calories = data.get('calories_target') or ''
    meals_count = int(data.get('meals_count') or 3)
    preferences = data.get('preferences', '')
    restrictions = data.get('restrictions', '')

    # Проверка доступности GigaChat
    if not GIGACHAT_AVAILABLE or GigaChat is None:
        print("[WARNING] GigaChat недоступен для генерации плана питания")
        meals = []
        default_meals = ['Завтрак', 'Обед', 'Ужин', 'Перекус']
        for i in range(meals_count):
            meal_type = default_meals[i] if i < len(default_meals) else f'Приём {i+1}'
            items = [f'Блюдо {i+1}A', f'Блюдо {i+1}B']
            meal = {
                'meal_type': meal_type,
                'food_items': items,
                'calories': round((int(calories) if str(calories).isdigit() else 2000) / meals_count),
                'proteins': 15,
                'fats': 10,
                'carbs': 30
            }
            meals.append(meal)

        return jsonify({'success': True, 'meals': meals, 'warning': 'GigaChat недоступен'})

    credentials = app.config.get('GIGACHAT_CREDENTIALS')
    if not credentials:
        return jsonify({'success': False, 'error': 'GIGACHAT_CREDENTIALS не настроены'}), 500

    try:
        print("[INFO] Генерация плана питания через GigaChat...")
        
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            scope="GIGACHAT_API_PERS",
            temperature=0.3
        ) as giga:

            prompt = f"""Создай план дневного питания. ВОЗВРАТИ ТОЛЬКО JSON.

ПАРАМЕТРЫ:
- Количество приемов: {meals_count}
- Целевые калории: {calories or '2000'}
- Предпочтения: {preferences or 'нет'}
- Ограничения: {restrictions or 'нет'}

ВАЖНО: ОБЯЗАТЕЛЬНО УЧИТАЙ ПОЖЕЛАНИЯ И ОГРАНИЧЕНИЯ В КАЖДОМ ПРИЕМЕ!

ТОЧНЫЙ ФОРМАТ:
{{
  "meals": [
    {{
      "meal_type": "Завтрак",
      "food_items": ["Омлет из 2 яиц с овощами 150g", "Хлеб цельнозерновой 30g", "Масло сливочное 10g"],
      "calories": 350,
      "proteins": 20,
      "fats": 15,
      "carbs": 30
    }},
    {{
      "meal_type": "Полдник",
      "food_items": ["Банан средний 100g"],
      "calories": 90,
      "proteins": 1,
      "fats": 0,
      "carbs": 23
    }}
  ]
}}

ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON, БЕЗ текста, комментариев, markdown кодов
2. "meals" - массив ровно {meals_count} приемов
3. У каждого приема: meal_type, food_items (массив с величинами), calories, proteins, fats, carbs
4. Числовые значения вместо строк
5. food_items - конкретные продукты с граммами/мл
6. Сумма калорий близко к {calories or '2000'}
7. ВСЕ БЛЮДА должны соответствовать предпочтениям: {preferences or 'нет'}
8. ВСЕ БЛЮДА должны избегать: {restrictions or 'нет'}

БЕЗ ПОЯСНЕНИЙ, НАЧНИ С {{:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()

            try:
                plan = parse_json_safely(content, "generate-mealplan")
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON ошибка (питание): {e}")
                return jsonify({'success': False, 'error': f'Невалидный JSON: {str(e)[:50]}'}), 500

            meals = plan.get('meals') or []
            cleaned = []
            for m in meals[:meals_count]:
                if not all(k in m for k in ('meal_type', 'food_items')):
                    continue
                try:
                    m['calories'] = int(m.get('calories') or 0)
                    m['proteins'] = int(m.get('proteins') or 0)
                    m['fats'] = int(m.get('fats') or 0)
                    m['carbs'] = int(m.get('carbs') or 0)
                except Exception:
                    m['calories'] = 0
                    m['proteins'] = 0
                    m['fats'] = 0
                    m['carbs'] = 0

                cleaned.append(m)

            print(f"[OK] План питания сгенерирован: {len(cleaned)} приёмов пищи")
            return jsonify({'success': True, 'meals': cleaned})

    except Exception as e:
        print(f"[ERROR] ERROR в generate-mealplan: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ГЕНЕРАЦИЯ РЕЦЕПТА ЧЕРЕЗ GIGACHAT - ИСПРАВЛЕННАЯ ВЕРСИЯ
@app.route('/api/generate-recipe', methods=['POST'])
@login_required
def api_generate_recipe():
    data = request.get_json()
    dish_type = data.get('dish_type', '')
    cuisine = data.get('cuisine', '')
    dietary = data.get('dietary', '')
    max_calories = data.get('max_calories', '')
    preferences = data.get('notes', '')  # Дополнительные пожелания от пользователя

    # Проверка доступности GigaChat
    if not GIGACHAT_AVAILABLE or GigaChat is None:
        print("[WARNING] GigaChat недоступен для генерации рецепта, используется fallback")
        return jsonify({
            'success': False,
            'error': 'GigaChat недоступен. Установите библиотеку: pip install gigachat'
        }), 503

    credentials = app.config.get('GIGACHAT_CREDENTIALS')
    if not credentials:
        print("[ERROR] GIGACHAT_CREDENTIALS не настроены!")
        return jsonify({
            'success': False,
            'error': 'GIGACHAT_CREDENTIALS не настроены в config.py'
        }), 500

    try:
        print(f"[INFO] Генерация рецепта через GigaChat: {dish_type or 'любое'}, {cuisine or 'любая кухня'}...")
        if preferences:
            print(f"[INFO] Пожелания пользователя: {preferences}")
        
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            scope="GIGACHAT_API_PERS",
            temperature=0.7  # Повышаем для более креативных рецептов
        ) as giga:

            # Строим промт с учетом пожеланий
            preferences_text = ""
            if preferences:
                preferences_text = f"""
ДОПОЛНИТЕЛЬНЫЕ ПОЖЕЛАНИЯ ПОЛЬЗОВАТЕЛЯ:
{preferences}

Обязательно учитай эти пожелания при создании рецепта!"""

            prompt = f"""Создай кулинарный рецепт в JSON. ВОЗВРАТИ ТОЛЬКО JSON.

ПАРАМЕТРЫ:
- Блюдо: {dish_type or 'основное блюдо'}
- Кухня: {cuisine or 'европейская'}
- Диета: {dietary or 'обычная'}
- Макс. калории: {max_calories or '500'} ккал{preferences_text}

ОБЯЗАТЕЛЬНЫЙ JSON:
{{
  "title": "Название блюда",
  "ingredients": [
    "200г куриного филе",
    "150g рис басмати",
    "1 морковь средняя",
    "2 ст.л. оливкового масла",
    "Соль, перец по вкусу"
  ],
  "instructions": "1. Промойте рис в холодной воде. 2. Варите рис 12-15 минут. 3. Филе нарежьте на кусочки. 4. На сковороде с маслом обжарьте мясо 6 минут. 5. Натрите морковь и добавьте к мясу. 6. Тушите 5 минут. 7. Смешайте с рисом, посолите.",
  "calories": 450,
  "proteins": 38,
  "fats": 12,
  "carbs": 45
}}

ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON, БЕЗ текста и markdown
2. ingredients - массив строк с точными граммами (200g, не "200 граммов")
3. instructions - один текст с пронумерованными шагами (1. 2. 3. и т.д.)
4. calories, proteins, fats, carbs - только числа, без кавычек
5. Итоговые калории близко к {max_calories or '500'}
6. Рецепт должен соответствовать ДИЕТЕ и другим параметрам{' - учитай пожелания!' if preferences else ''}

НАЧНИ С {{, БЕЗ ОБЪЯСНЕНИЙ:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()

            try:
                recipe_data = parse_json_safely(content, "generate-recipe")
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON ошибка (рецепт): {e}")
                return jsonify({'success': False, 'error': f'Невалидный JSON: {str(e)[:50]}'}), 500

            # Валидация обязательных полей
            required = ['title', 'ingredients', 'instructions', 'calories', 'proteins', 'fats', 'carbs']
            missing = [field for field in required if field not in recipe_data]
            
            if missing:
                print(f"[WARNING] Пропущены поля: {missing}")
                return jsonify({'success': False, 'error': f'Пропущены поля: {", ".join(missing)}'}), 500

            # Приведение типов к числам
            try:
                recipe_data['calories'] = int(recipe_data.get('calories') or 0)
                recipe_data['proteins'] = int(recipe_data.get('proteins') or 0)
                recipe_data['fats'] = int(recipe_data.get('fats') or 0)
                recipe_data['carbs'] = int(recipe_data.get('carbs') or 0)
            except (ValueError, TypeError) as e:
                print(f"[WARNING] Ошибка конвертации чисел: {e}")

            # Проверка что ingredients - массив
            if not isinstance(recipe_data.get('ingredients'), list):
                print("[WARNING] ingredients не является массивом")
                recipe_data['ingredients'] = []

            # Проверка минимальной длины instructions
            if len(str(recipe_data.get('instructions', ''))) < 50:
                print("[WARNING] instructions слишком короткий")
                recipe_data['instructions'] = 'Приготовьте по рецепту.'

            print(f"[OK] Рецепт успешно сгенерирован: {recipe_data['title']}")
            print(f"   Ингредиентов: {len(recipe_data['ingredients'])}, Калорий: {recipe_data['calories']}")

            return jsonify({'success': True, 'recipe': recipe_data})

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] КРИТИЧЕСКАЯ ОШИБКА в generate-recipe: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Более информативное сообщение об ошибке
        if 'credentials' in error_msg.lower() or 'auth' in error_msg.lower():
            return jsonify({
                'success': False, 
                'error': 'Ошибка авторизации GigaChat. Проверьте GIGACHAT_CREDENTIALS в config.py'
            }), 401
        else:
            return jsonify({'success': False, 'error': f'Ошибка GigaChat: {error_msg}'}), 500


# ФИТНЕС ИГРЫ
@app.route('/fitness-games')
@login_required
def fitness_games():
    games_list = [
        {
            'id': 'dance',
            'title': 'Танцевальная игра',
            'description': 'Повторяйте движения за виртуальным тренером',
            'game_type': 'cardio',
            'difficulty_level': 'medium'
        },
        {
            'id': 'boxing',
            'title': 'Виртуальный бокс',
            'description': 'Тренируйте реакцию и координацию',
            'game_type': 'intense',
            'difficulty_level': 'hard'
        },
        {
            'id': 'ninja',
            'title': 'Ниндзя-рефлексы',
            'description': 'Уклоняйтесь от виртуальных препятствий',
            'game_type': 'agility',
            'difficulty_level': 'easy'
        }
    ]

    stats = {
        'total_games': 0,
        'total_score': 0,
        'avg_accuracy': 0
    }
    try:
        results = FitnessGame.query.filter_by(user_id=current_user.id).all()
        if results:
            stats['total_games'] = len(results)
            stats['total_score'] = sum(getattr(r, 'score', 0) or 0 for r in results)
            stats['avg_accuracy'] = round((sum(getattr(r, 'accuracy', 0) or 0 for r in results) / len(results)), 1)
    except Exception:
        pass

    return render_template('fitness_games.html', games=games_list, stats=stats)


@app.route('/fitness-games/save-result', methods=['POST'])
@login_required
def save_game_result():
    data = request.get_json()
    game_result = FitnessGame(
        user_id=current_user.id,
        game_type=data['game_type'],
        score=data['score'],
        accuracy=data['accuracy'],
        created_at=datetime.utcnow()
    )
    db.session.add(game_result)
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/fitness-games/stats')
@login_required
def get_game_stats():
    games = FitnessGame.query.filter_by(user_id=current_user.id).all()
    total_games = len(games)
    total_score = sum(game.score for game in games) if games else 0
    avg_accuracy = sum(game.accuracy for game in games) / total_games if games else 0
    
    return jsonify({
        'total_games': total_games,
        'total_score': total_score,
        'avg_accuracy': round(avg_accuracy, 1)
    })


# РЕЦЕПТЫ
@app.route('/nutrition/recipes')
@login_required
def recipes():
    if current_user.is_cook() or current_user.is_admin():
        all_recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    else:
        all_recipes = Recipe.query.filter_by(status='approved').order_by(Recipe.created_at.desc()).all()
    return render_template('recipes.html', recipes=all_recipes)


@app.route('/nutrition/recipes/<int:recipe_id>')
@login_required
def get_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    try:
        ingredients = json.loads(recipe.ingredients)
        if not isinstance(ingredients, list):
            ingredients = [str(ingredients)]
    except Exception:
        if recipe.ingredients:
            ingredients = [i for i in str(recipe.ingredients).split('\n') if i.strip()]
        else:
            ingredients = []

    return jsonify({
        'id': recipe.id,
        'title': recipe.title,
        'ingredients': ingredients,
        'instructions': recipe.instructions,
        'calories': recipe.calories,
        'proteins': recipe.proteins,
        'fats': recipe.fats,
        'carbs': recipe.carbs,
        'image_url': recipe.image_url
    })


@app.route('/nutrition/recipes/add', methods=['POST'])
@login_required
def add_recipe():
    data = request.get_json()
    recipe = Recipe(
        user_id=current_user.id,
        title=data['title'],
        ingredients=json.dumps(data['ingredients'], ensure_ascii=False),
        instructions=data['instructions'],
        calories=data['calories'],
        proteins=data['proteins'],
        fats=data['fats'],
        carbs=data['carbs'],
        image_url=data.get('image_url'),
        status='pending',
        created_at=datetime.utcnow()
    )
    db.session.add(recipe)
    db.session.commit()
    return jsonify({'status': 'success', 'id': recipe.id})


# МЕССЕНДЖЕР
@app.route('/messenger')
@login_required
def messenger():
    user_messages = Message.query.filter(
        or_(
            Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id
        )
    ).order_by(Message.created_at.desc()).all()
    
    conversations = []
    seen_users = set()
    
    for message in user_messages:
        other_user_id = message.receiver_id if message.sender_id == current_user.id else message.sender_id
        if other_user_id in seen_users:
            continue
        
        other_user = User.query.get(other_user_id)
        if not other_user:
            continue
        
        unread_count = Message.query.filter_by(
            sender_id=other_user_id,
            receiver_id=current_user.id,
            is_read=False
        ).count()
        
        conversations.append({
            'user': other_user,
            'last_message': message,
            'unread_count': unread_count
        })
        seen_users.add(other_user_id)
    
    return render_template('messenger.html', conversations=conversations)


# API: Получить сообщения с конкретным пользователем
@app.route('/api/messenger/conversation/<int:user_id>', methods=['GET'])
@login_required
def get_conversation(user_id):
    other_user = User.query.get_or_404(user_id)
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    # Помечаем сообщения как прочитанные
    Message.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    messages_data = [{
        'id': msg.id,
        'sender_id': msg.sender_id,
        'receiver_id': msg.receiver_id,
        'content': msg.content,
        'message_type': msg.message_type,
        'file_path': msg.file_path,
        'is_read': msg.is_read,
        'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'sender_username': msg.sender.username
    } for msg in messages]
    
    return jsonify({
        'success': True,
        'messages': messages_data,
        'other_user': {
            'id': other_user.id,
            'username': other_user.username,
            'email': other_user.email
        }
    })


# API: Отправить сообщение
@app.route('/api/messenger/send', methods=['POST'])
@login_required
def send_message():
    # Поддержка текстовых сообщений
    if request.is_json:
        data = request.get_json()
        receiver_id = data.get('receiver_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        
        if not receiver_id or not content:
            return jsonify({'success': False, 'error': 'Не указан получатель или текст сообщения'}), 400
        
        receiver = User.query.get(receiver_id)
        if not receiver:
            return jsonify({'success': False, 'error': 'Получатель не найден'}), 404
        
        if receiver_id == current_user.id:
            return jsonify({'success': False, 'error': 'Нельзя отправить сообщение самому себе'}), 400
        
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            is_read=False
        )
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'sender_id': message.sender_id,
                'receiver_id': message.receiver_id,
                'content': message.content,
                'message_type': message.message_type,
                'file_path': message.file_path,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'sender_username': current_user.username
            }
        })
    
    # Поддержка загрузки файлов и фото
    elif request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        receiver_id = request.form.get('receiver_id')
        message_type = request.form.get('message_type', 'file')  # photo или file
        
        if not receiver_id or not file:
            return jsonify({'success': False, 'error': 'Не указан файл или получатель'}), 400
        
        receiver = User.query.get(receiver_id)
        if not receiver:
            return jsonify({'success': False, 'error': 'Получатель не найден'}), 404
        
        if int(receiver_id) == current_user.id:
            return jsonify({'success': False, 'error': 'Нельзя отправить сообщение самому себе'}), 400
        
        # Валидация имени файла
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Файл не выбран'}), 400
        
        # Создаем папку uploads если её нет
        upload_folder = os.path.join('static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Генерируем уникальное имя файла
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Сохраняем URL для доступа в браузере
        file_url = f'/static/uploads/{filename}'
        
        message = Message(
            sender_id=current_user.id,
            receiver_id=int(receiver_id),
            content=f'Отправил(а) {message_type}',
            message_type=message_type,
            file_path=file_url,
            is_read=False
        )
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'sender_id': message.sender_id,
                'receiver_id': message.receiver_id,
                'content': message.content,
                'message_type': message.message_type,
                'file_path': message.file_path,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'sender_username': current_user.username
            }
        })


# API: Получить количество непрочитанных сообщений
@app.route('/api/messenger/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    count = Message.query.filter_by(
        receiver_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'success': True, 'count': count})


# API: Инициировать звонок
@app.route('/api/messenger/call', methods=['POST'])
@login_required
def initiate_call():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    call_type = data.get('call_type', 'audio')  # audio или video
    
    if not receiver_id:
        return jsonify({'success': False, 'error': 'Не указан получатель'}), 400
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'error': 'Получатель не найден'}), 404
    
    if receiver_id == current_user.id:
        return jsonify({'success': False, 'error': 'Нельзя позвонить самому себе'}), 400
    
    # Сохраняем информацию о звонке как сообщение
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=f'Входящий {call_type} звонок от {current_user.username}',
        message_type='call',
        file_path=call_type,  # Сохраняем тип звонка
        is_read=False
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'call_id': message.id,
        'caller': {
            'id': current_user.id,
            'username': current_user.username
        },
        'call_type': call_type
    })


# API: Поиск пользователей по никнейму
@app.route('/api/messenger/search-users', methods=['GET'])
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'success': True, 'users': []})
    
    # Ищем пользователей по никнейму или username
    users = User.query.filter(
        User.id != current_user.id,
        (User.nickname.ilike(f'%{query}%')) | (User.username.ilike(f'%{query}%'))
    ).limit(10).all()
    
    users_data = [{
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname or user.username,
        'email': user.email
    } for user in users]
    
    return jsonify({'success': True, 'users': users_data})



@app.route('/card-game')
@login_required
def card_game():
    # Мои созданные сессии
    my_sessions = GameSession.query.filter_by(creator_id=current_user.id).order_by(GameSession.created_at.desc()).all()
    
    # Сессии, в которых я участвую
    my_participations = GameParticipant.query.filter_by(user_id=current_user.id).all()
    participated_session_ids = [p.session_id for p in my_participations]
    participant_sessions = GameSession.query.filter(GameSession.id.in_(participated_session_ids)).order_by(GameSession.created_at.desc()).all() if participated_session_ids else []
    
    return render_template('card_game.html', 
                         my_sessions=my_sessions, 
                         participant_sessions=participant_sessions)

@app.route('/card-game/create', methods=['GET', 'POST'])
@login_required
def create_card_game():
    """Создание новой игровой сессии"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        title = data.get('title', '').strip()
        subject = data.get('subject', '').strip()
        topic = data.get('topic', '').strip()
        num_cards = int(data.get('num_cards', 10))
        material_text = data.get('material_text', '').strip()
        
        if not title or not subject or not topic:
            return jsonify({'success': False, 'error': 'Заполните все обязательные поля'}), 400
        
        session = GameSession(
            creator_id=current_user.id,
            title=title,
            subject=subject,
            topic=topic,
            material_text=material_text,
            num_cards=num_cards,
            status='waiting'
        )
        
        db.session.add(session)
        db.session.commit()
        
        # Добавить создателя как участника
        participant = GameParticipant(
            session_id=session.id,
            user_id=current_user.id,
            status='ready'
        )
        db.session.add(participant)
        db.session.commit()
        
        return jsonify({'success': True, 'session_id': session.id})
    
    return render_template('card_game_create.html', subjects_topics=SUBJECTS_TOPICS)


# Просмотр игровой сессии
@app.route('/card-game/session/<int:session_id>')
@login_required
def view_card_game_session(session_id):
    """Просмотр информации об игровой сессии"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что пользователь может просматривать эту сессию
    is_creator = session.creator_id == current_user.id
    is_participant = GameParticipant.query.filter_by(
        session_id=session_id, user_id=current_user.id
    ).first() is not None
    
    if not is_creator and not is_participant:
        flash('У вас нет доступа к этой сессии', 'danger')
        return redirect(url_for('card_game'))
    
    cards = GameCard.query.filter_by(session_id=session_id).order_by(GameCard.order_index).all()
    participants = GameParticipant.query.filter_by(session_id=session_id).all()
    
    return render_template('card_game_session.html', 
                          session=session, 
                          cards=cards, 
                          participants=participants,
                          is_creator=is_creator)


# API: Пригласить друга в игру
@app.route('/api/card-game/session/<int:session_id>/invite', methods=['POST'])
@login_required
def invite_to_card_game(session_id):
    """Пригласить пользователя в игровую сессию"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что запрашивающий - создатель
    if session.creator_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только создатель может приглашать'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    user = User.query.get_or_404(user_id)
    
    # Проверить, что уже не участник
    existing = GameParticipant.query.filter_by(
        session_id=session_id, user_id=user_id
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Пользователь уже приглашен'}), 400
    
    participant = GameParticipant(
        session_id=session_id,
        user_id=user_id,
        status='invited'
    )
    db.session.add(participant)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Приглашение отправлено {user.username}'})


# API: Присоединиться к игре
@app.route('/api/card-game/session/<int:session_id>/join', methods=['POST'])
@login_required
def join_card_game(session_id):
    """Присоединиться к игровой сессии"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что не уже участник
    existing = GameParticipant.query.filter_by(
        session_id=session_id, user_id=current_user.id
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Вы уже в этой игре'}), 400
    
    participant = GameParticipant(
        session_id=session_id,
        user_id=current_user.id,
        status='joined'
    )
    db.session.add(participant)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Вы присоединились к игре'})


# API: Генерация карточек через GigaChat
@app.route('/api/card-game/session/<int:session_id>/generate-cards', methods=['POST'])
@login_required
def generate_cards(session_id):
    """Генерация карточек через ИИ"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что запрашивающий - создатель
    if session.creator_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только создатель может генерировать карточки'}), 403
    
    # Проверка доступности GigaChat
    if not GIGACHAT_AVAILABLE or GigaChat is None:
        print("[WARNING] GigaChat недоступен для генерации карточек")
        # Fallback - создаем простые карточки
        cards_data = []
        for i in range(1, session.num_cards + 1):
            cards_data.append({
                'question': f'Вопрос {i} по теме: {session.topic}',
                'answer': f'Ответ на вопрос {i}',
                'explanation': f'Объяснение для вопроса {i}'
            })
        
        # Сохраняем карточки
        for idx, card_data in enumerate(cards_data):
            card = GameCard(
                session_id=session.id,
                question=card_data['question'],
                answer=card_data['answer'],
                explanation=card_data['explanation'],
                order_index=idx
            )
            db.session.add(card)
        
        db.session.commit()
        return jsonify({'success': True, 'cards_count': len(cards_data), 'warning': 'GigaChat недоступен, использованы тестовые карточки'})
    
    credentials = app.config.get('GIGACHAT_CREDENTIALS')
    if not credentials:
        return jsonify({'success': False, 'error': 'GIGACHAT_CREDENTIALS не настроены'}), 500
    
    try:
        print(f"[INFO] Генерация {session.num_cards} карточек через GigaChat...")
        
        # ИСПРАВЛЕНО: отключение проверки SSL и увеличение таймаута
        import ssl
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,  # Отключить проверку SSL
            scope="GIGACHAT_API_PERS",
            temperature=0.7,
            timeout=120,  # Увеличен таймаут до 2 минут
            model="GigaChat"
        ) as giga:
            
            if session.material_text:
                prompt = f"""Создай {session.num_cards} учебных карточек JSON.

ТЕКСТ:
{session.material_text[:2000]}

ТОЧНЫЙ ФОРМАТ:
{{
  "cards": [
    {{
      "question": "Что такое фотосинтез?",
      "answer": "Процесс преобразования света в энергию растениями.",
      "explanation": "Фотосинтез происходит в листьях растений. Хлорофилл поглощает свет, преобразуя воду и углекислый газ в глюкозу и кислород. Это основной источник кислорода на Земле."
    }}
  ]
}}

ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON, БЕЗ текста/markdown
2. "cards" - массив ровно {session.num_cards} карточек
3. question - вопрос по материалу (10-50 символов)
4. answer - конкретный краткий ответ (1-2 предложения)
5. explanation - подробное обоснование (3-5 предложений)
6. Вопросы от простых к сложным

НАЧНИ С {{, БЕЗ ПОЯСНЕНИЙ:"""
            else:
                prompt = f"""Создай {session.num_cards} карточек изучения JSON.

ПАРАМЕТРЫ:
- Предмет: {session.subject}
- Тема: {session.topic}

ОБЯЗАТЕЛЬНЫЙ JSON:
{{
  "cards": [
    {{
      "question": "Вопрос 1?",
      "answer": "Четкий ответ.",
      "explanation": "Расширенное объяснение с деталями и контекстом."
    }},
    {{
      "question": "Вопрос 2?",
      "answer": "Ответ два.",
      "explanation": "Объяснение второго ответа с примерами."
    }}
  ]
}}

ТРЕБОВАНИЯ:
1. ТОЛЬКО JSON, БЕЗ текста до/после и markdown кодов
2. "cards" - массив из {session.num_cards} объектов
3. question - один вопрос (10-50 символов), заканчивается на ?
4. answer - прямой ответ (20-100 символов)
5. explanation - подробное объяснение (80-200 символов)
6. Вопросы логично прогрессируют от базовых к сложным

НАЧНИ СРАЗУ С {{:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()
            
            try:
                data = parse_json_safely(content, "generate-cards")
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON ошибка (карточки): {e}")
                return jsonify({'success': False, 'error': f'Невалидный JSON: {str(e)[:50]}'}), 500
            
            cards_data = data.get('cards', [])
            
            if not cards_data:
                print("[ERROR] Нет карточек в ответе")
                return jsonify({'success': False, 'error': 'GigaChat не создал карточки'}), 500
            
            # Валидация и сохранение карточек
            valid_cards = []
            for idx, card_data in enumerate(cards_data[:session.num_cards]):
                if not all(k in card_data for k in ['question', 'answer', 'explanation']):
                    print(f"[WARNING] Пропущена карточка {idx}: неполные данные")
                    continue
                
                card = GameCard(
                    session_id=session.id,
                    question=card_data['question'],
                    answer=card_data['answer'],
                    explanation=card_data['explanation'],
                    order_index=idx
                )
                db.session.add(card)
                valid_cards.append(card)
            
            if not valid_cards:
                return jsonify({'success': False, 'error': 'Не удалось создать валидные карточки'}), 500
            
            db.session.commit()
            
            print(f"[OK] Создано {len(valid_cards)} карточек")
            return jsonify({'success': True, 'cards_count': len(valid_cards)})
        
    except ssl.SSLError as e:
        print(f"[ERROR] SSL Error: {str(e)}")
        return jsonify({'success': False, 'error': f'Ошибка SSL подключения к GigaChat: {str(e)}'}), 500
    except Exception as e:
        print(f"[ERROR] Общая ошибка в generate_cards: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Ошибка генерации: {str(e)}'}), 500


# API: Начать игру (распределить карточки)
@app.route('/api/card-game/session/<int:session_id>/start', methods=['POST'])
@login_required
def start_card_game(session_id):
    """Начать игру - распределить карточки между участниками"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что запрашивающий - создатель
    if session.creator_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только создатель может начать игру'}), 403
    
    cards = GameCard.query.filter_by(session_id=session_id).all()
    participants = GameParticipant.query.filter_by(session_id=session_id).all()
    
    if not cards:
        return jsonify({'success': False, 'error': 'Нет карточек для игры. Сгенерируйте карточки.'}), 400
    
    if len(participants) < 2:
        return jsonify({'success': False, 'error': 'Нужно минимум 2 участника'}), 400
    
    # Распределить карточки между участниками
    for i, card in enumerate(cards):
        participant = participants[i % len(participants)]
        card.assigned_to_user_id = participant.user_id
    
    session.status = 'in_progress'
    session.started_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Игра началась!'})


# Страница игры (отвечаем на вопросы)
@app.route('/card-game/session/<int:session_id>/play')
@login_required
def play_card_game(session_id):
    """Страница игры - ответ на карточки"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что пользователь - участник
    participant = GameParticipant.query.filter_by(
        session_id=session_id, user_id=current_user.id
    ).first()
    
    if not participant:
        flash('Вы не участник этой игры', 'danger')
        return redirect(url_for('card_game'))
    
    # Получить карточки, назначенные текущему пользователю
    my_cards = GameCard.query.filter_by(
        session_id=session_id, 
        assigned_to_user_id=current_user.id
    ).order_by(GameCard.order_index).all()
    
    # Получить карточки других участников для проверки
    cards_to_check = GameCard.query.filter_by(session_id=session_id).filter(
        GameCard.assigned_to_user_id != current_user.id
    ).all()
    
    return render_template('card_game_play.html', 
                          session=session, 
                          my_cards=my_cards,
                          cards_to_check=cards_to_check)


# API: Отправить ответ на карточку
@app.route('/api/card-game/card/<int:card_id>/answer', methods=['POST'])
@login_required
def submit_card_answer(card_id):
    """Отправить ответ на карточку"""
    card = GameCard.query.get_or_404(card_id)
    data = request.get_json()
    
    answer_text = data.get('answer_text', '').strip()
    if not answer_text:
        return jsonify({'success': False, 'error': 'Ответ не может быть пустым'}), 400
    
    # Проверить, что карточка назначена текущему пользователю
    if card.assigned_to_user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Эта карточка вам не назначена'}), 403
    
    answer = GameAnswer(
        card_id=card_id,
        user_id=current_user.id,
        answer_text=answer_text
    )
    
    db.session.add(answer)
    db.session.commit()
    
    return jsonify({'success': True, 'answer_id': answer.id})


# API: Оценить ответ товарища
@app.route('/api/card-game/answer/<int:answer_id>/rate', methods=['POST'])
@login_required
def rate_card_answer(answer_id):
    """Оценить ответ другого участника"""
    answer = GameAnswer.query.get_or_404(answer_id)
    card = GameCard.query.get(answer.card_id)
    
    # Проверить, что карточка назначена текущему пользователю (он проверяет)
    if card.assigned_to_user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Вы не можете проверять эту карточку'}), 403
    
    data = request.get_json()
    
    answer.rating = int(data.get('rating', 0))
    answer.is_correct = data.get('is_correct', False)
    answer.feedback = data.get('feedback', '').strip()
    answer.checked_by_user_id = current_user.id
    answer.checked_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Оценка сохранена'})


# API: Завершить игру
@app.route('/api/card-game/session/<int:session_id>/complete', methods=['POST'])
@login_required
def complete_card_game(session_id):
    """Завершить игру и подвести итоги"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что запрашивающий - создатель
    if session.creator_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только создатель может завершить игру'}), 403
    
    # Рассчитать баллы для каждого участника
    participants = GameParticipant.query.filter_by(session_id=session_id).all()
    
    for participant in participants:
        # Подсчитать правильные ответы этого участника
        correct_answers = GameAnswer.query.join(GameCard).filter(
            GameCard.session_id == session_id,
            GameAnswer.user_id == participant.user_id,
            GameAnswer.is_correct == True
        ).count()
        
        participant.score = correct_answers
    
    session.status = 'completed'
    session.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Игра завершена'})


# API: Удалить игровую сессию
@app.route('/api/card-game/session/<int:session_id>', methods=['DELETE'])
@login_required
def delete_card_game_session(session_id):
    """Удалить игровую сессию"""
    session = GameSession.query.get_or_404(session_id)
    
    # Проверить, что запрашивающий - создатель
    if session.creator_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только создатель может удалить игру'}), 403
    
    # Удалить все связанные данные
    GameAnswer.query.join(GameCard).filter(GameCard.session_id == session_id).delete()
    GameCard.query.filter_by(session_id=session_id).delete()
    GameParticipant.query.filter_by(session_id=session_id).delete()
    GameSession.query.filter_by(id=session_id).delete()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Игра удалена'})


# API: Добавить реакцию на сообщение
@app.route('/api/messenger/reaction/add', methods=['POST'])
@login_required
def add_reaction():
    data = request.get_json()
    message_id = data.get('message_id')
    emoji = data.get('emoji')
    
    if not message_id or not emoji:
        return jsonify({'success': False, 'error': 'Не указано сообщение или эмодзи'}), 400
    
    message = Message.query.get(message_id)
    if not message:
        return jsonify({'success': False, 'error': 'Сообщение не найдено'}), 404
    
    # Проверяем, что пользователь участник этого диалога
    if not ((message.sender_id == current_user.id or message.receiver_id == current_user.id) and
            (message.sender_id == current_user.id or message.receiver_id == current_user.id)):
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403
    
    # Проверяем, есть ли уже такая реакция
    existing = MessageReaction.query.filter_by(
        message_id=message_id,
        user_id=current_user.id,
        emoji=emoji
    ).first()
    
    if existing:
        # Если реакция уже есть, удаляем её (toggle)
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'action': 'removed'})
    else:
        # Добавляем новую реакцию
        reaction = MessageReaction(
            message_id=message_id,
            user_id=current_user.id,
            emoji=emoji
        )
        db.session.add(reaction)
        db.session.commit()
        return jsonify({'success': True, 'action': 'added'})


# API: Получить реакции на сообщение
@app.route('/api/messenger/message/<int:message_id>/reactions', methods=['GET'])
@login_required
def get_reactions(message_id):
    message = Message.query.get(message_id)
    if not message:
        return jsonify({'success': False, 'error': 'Сообщение не найдено'}), 404
    
    # Проверяем, что пользователь участник этого диалога
    if not ((message.sender_id == current_user.id) or (message.receiver_id == current_user.id)):
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403
    
    # Получаем все реакции и группируем по эмодзи
    reactions = MessageReaction.query.filter_by(message_id=message_id).all()
    
    reactions_dict = {}
    for reaction in reactions:
        emoji = reaction.emoji
        if emoji not in reactions_dict:
            reactions_dict[emoji] = {
                'emoji': emoji,
                'count': 0,
                'users': [],
                'current_user_reacted': False
            }
        reactions_dict[emoji]['count'] += 1
        reactions_dict[emoji]['users'].append({
            'id': reaction.user.id,
            'username': reaction.user.username,
            'nickname': reaction.user.nickname or reaction.user.username
        })
        if reaction.user_id == current_user.id:
            reactions_dict[emoji]['current_user_reacted'] = True
    
    return jsonify({
        'success': True,
        'reactions': list(reactions_dict.values())
    })


# ===== УПРАВЛЕНИЕ СТУДЕНТАМИ ДЛЯ УЧИТЕЛЕЙ =====

# API: Получить список свободных студентов для учителя
@app.route('/api/teacher/available-students', methods=['GET'])
@login_required
def get_available_students():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Только учителя могут добавлять студентов'}), 403
    
    # Получаем студентов без учителя
    students_without_teacher = User.query.filter(
        User.role == 'student',
        User.mentor_id.is_(None)
    ).all()
    
    students_data = [{
        'id': student.id,
        'username': student.username,
        'nickname': student.nickname or student.username,
        'email': student.email
    } for student in students_without_teacher]
    
    return jsonify({
        'success': True,
        'students': students_data,
        'count': len(students_data)
    })


# API: Получить список студентов учителя
@app.route('/api/teacher/my-students', methods=['GET'])
@login_required
def get_my_students():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Только учителя могут просматривать студентов'}), 403
    
    students = User.query.filter_by(mentor_id=current_user.id).all()
    
    students_data = [{
        'id': student.id,
        'username': student.username,
        'nickname': student.nickname or student.username,
        'email': student.email,
        'created_at': student.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for student in students]
    
    return jsonify({
        'success': True,
        'students': students_data,
        'count': len(students_data)
    })


# API: Добавить студента к учителю
@app.route('/api/teacher/add-student', methods=['POST'])
@login_required
def add_student():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Только учителя могут добавлять студентов'}), 403
    
    data = request.get_json()
    student_id = data.get('student_id')
    
    if not student_id:
        return jsonify({'success': False, 'error': 'Не указан ID студента'}), 400
    
    student = User.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'error': 'Студент не найден'}), 404
    
    if student.role != 'student':
        return jsonify({'success': False, 'error': 'Это не студент'}), 400
    
    if student.mentor_id is not None:
        return jsonify({'success': False, 'error': 'Этот студент уже привязан к другому учителю'}), 400
    
    # Привязываем студента к учителю
    student.mentor_id = current_user.id
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Студент {student.username} успешно добавлен',
        'student': {
            'id': student.id,
            'username': student.username,
            'nickname': student.nickname or student.username
        }
    })


# API: Удалить студента у учителя
@app.route('/api/teacher/remove-student/<int:student_id>', methods=['DELETE'])
@login_required
def remove_student(student_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Только учителя могут удалять студентов'}), 403
    
    student = User.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'error': 'Студент не найден'}), 404
    
    if student.mentor_id != current_user.id:
        return jsonify({'success': False, 'error': 'Этот студент не ваш'}), 403
    
    student.mentor_id = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Студент {student.username} удален'
    })


# API: Получить учителя студента
@app.route('/api/student/my-teacher', methods=['GET'])
@login_required
def get_my_teacher():
    if current_user.role != 'student':
        return jsonify({'success': False, 'error': 'Только студенты могут просматривать учителя'}), 403
    
    if not current_user.mentor:
        return jsonify({
            'success': True,
            'has_teacher': False,
            'message': 'У вас нет назначенного учителя'
        })
    
    teacher = current_user.mentor
    return jsonify({
        'success': True,
        'has_teacher': True,
        'teacher': {
            'id': teacher.id,
            'username': teacher.username,
            'nickname': teacher.nickname or teacher.username,
            'email': teacher.email
        }
    })



# ==================== КАБИНЕТ ПОВАРА ====================

@app.route('/profile/cook')
@login_required
def cook_profile():
    if not current_user.is_cook():
        return redirect(url_for('profile'))

    pending_recipes = Recipe.query.filter_by(status='pending').order_by(Recipe.created_at.desc()).all()
    approved_recipes = Recipe.query.filter_by(status='approved').order_by(Recipe.created_at.desc()).all()
    rejected_count = Recipe.query.filter_by(status='rejected').count()

    return render_template('cook_profile.html',
                         pending_recipes=pending_recipes,
                         approved_recipes=approved_recipes,
                         rejected_count=rejected_count)


@app.route('/cook/recipe/<int:recipe_id>/approve', methods=['POST'])
@login_required
def cook_approve_recipe(recipe_id):
    if not current_user.is_cook() and not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.status = 'approved'
    log = ActivityLog(user_id=current_user.id, action='recipe_approved',
                      details=f'Рецепт "{recipe.title}" одобрен')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Рецепт одобрен'})


@app.route('/cook/recipe/<int:recipe_id>/reject', methods=['POST'])
@login_required
def cook_reject_recipe(recipe_id):
    if not current_user.is_cook() and not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.status = 'rejected'
    log = ActivityLog(user_id=current_user.id, action='recipe_rejected',
                      details=f'Рецепт "{recipe.title}" отклонён')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Рецепт отклонён'})


# ==================== АДМИН-ПАНЕЛЬ ====================

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin():
        flash('Доступ запрещён', 'error')
        return redirect(url_for('dashboard'))

    users = User.query.order_by(User.created_at.desc()).all()
    pending_users = User.query.filter_by(is_approved=False).all()
    notifications = AdminNotification.query.filter_by(is_read=False).order_by(AdminNotification.created_at.desc()).all()
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()

    total_users = User.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_teachers = User.query.filter_by(role='teacher', is_approved=True).count()
    total_cooks = User.query.filter_by(role='cook', is_approved=True).count()
    total_recipes = Recipe.query.count()
    pending_recipes = Recipe.query.filter_by(status='pending').count()
    total_tests = TestResult.query.count()

    return render_template('admin_panel.html',
                         users=users,
                         pending_users=pending_users,
                         notifications=notifications,
                         recent_logs=recent_logs,
                         total_users=total_users,
                         total_students=total_students,
                         total_teachers=total_teachers,
                         total_cooks=total_cooks,
                         total_recipes=total_recipes,
                         pending_recipes=pending_recipes,
                         total_tests=total_tests)


@app.route('/admin/approve-user/<int:user_id>', methods=['POST'])
@login_required
def admin_approve_user(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)
    user.is_approved = True

    # Помечаем уведомление как прочитанное
    notif = AdminNotification.query.filter_by(related_user_id=user.id, type='registration', is_read=False).first()
    if notif:
        notif.is_read = True

    log = ActivityLog(user_id=current_user.id, action='user_approved',
                      details=f'Админ одобрил пользователя {user.username} ({user.role})')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Пользователь {user.username} одобрен'})


@app.route('/admin/reject-user/<int:user_id>', methods=['POST'])
@login_required
def admin_reject_user(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)

    notif = AdminNotification.query.filter_by(related_user_id=user.id, type='registration', is_read=False).first()
    if notif:
        notif.is_read = True

    log = ActivityLog(user_id=current_user.id, action='user_rejected',
                      details=f'Админ отклонил регистрацию {user.username} ({user.role})')
    db.session.add(log)

    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Заявка пользователя отклонена'})


@app.route('/admin/ban-user/<int:user_id>', methods=['POST'])
@login_required
def admin_ban_user(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)
    if user.is_admin():
        return jsonify({'success': False, 'error': 'Нельзя заблокировать админа'}), 403

    user.is_banned = not user.is_banned
    status = 'заблокирован' if user.is_banned else 'разблокирован'
    log = ActivityLog(user_id=current_user.id, action='user_ban_toggle',
                      details=f'Пользователь {user.username} {status}')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Пользователь {user.username} {status}', 'is_banned': user.is_banned})


@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)
    if user.is_admin():
        return jsonify({'success': False, 'error': 'Нельзя удалить админа'}), 403

    username = user.username
    log = ActivityLog(user_id=current_user.id, action='user_deleted',
                      details=f'Админ удалил пользователя {username} ({user.role})')
    db.session.add(log)

    # Удаляем связанные данные
    TestResult.query.filter_by(user_id=user.id).delete()
    PhysicalEducationResult.query.filter_by(user_id=user.id).delete()
    TrainingProgram.query.filter_by(user_id=user.id).delete()
    NutritionDiary.query.filter_by(user_id=user.id).delete()
    Recipe.query.filter_by(user_id=user.id).delete()
    FitnessGame.query.filter_by(user_id=user.id).delete()
    Message.query.filter(or_(Message.sender_id == user.id, Message.receiver_id == user.id)).delete()
    Homework.query.filter_by(user_id=user.id).delete()
    AdminNotification.query.filter_by(related_user_id=user.id).delete()

    # Открепляем учеников
    User.query.filter_by(mentor_id=user.id).update({'mentor_id': None})

    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Пользователь {username} удалён'})


@app.route('/admin/change-nickname/<int:user_id>', methods=['POST'])
@login_required
def admin_change_nickname(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_nickname = data.get('nickname', '').strip()

    if not new_nickname:
        return jsonify({'success': False, 'error': 'Никнейм не может быть пустым'}), 400

    existing = User.query.filter_by(nickname=new_nickname).first()
    if existing and existing.id != user.id:
        return jsonify({'success': False, 'error': 'Этот никнейм уже занят'}), 400

    old_nickname = user.nickname
    user.nickname = new_nickname
    log = ActivityLog(user_id=current_user.id, action='nickname_changed',
                      details=f'Никнейм пользователя {user.username} изменён: {old_nickname} → {new_nickname}')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Никнейм изменён на {new_nickname}'})


@app.route('/admin/change-role/<int:user_id>', methods=['POST'])
@login_required
def admin_change_role(user_id):
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    user = User.query.get_or_404(user_id)
    if user.is_admin():
        return jsonify({'success': False, 'error': 'Нельзя менять роль админа'}), 403

    data = request.get_json()
    new_role = data.get('role', '')
    if new_role not in ['student', 'teacher', 'cook']:
        return jsonify({'success': False, 'error': 'Недопустимая роль'}), 400

    old_role = user.role
    user.role = new_role
    user.is_approved = True
    log = ActivityLog(user_id=current_user.id, action='role_changed',
                      details=f'Роль пользователя {user.username} изменена: {old_role} → {new_role}')
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Роль изменена на {new_role}'})


@app.route('/admin/notifications/read-all', methods=['POST'])
@login_required
def admin_read_all_notifications():
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403

    AdminNotification.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
