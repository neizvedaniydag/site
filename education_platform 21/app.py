from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy import or_

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

from datetime import datetime
from models import db, User, TestResult, PhysicalEducationResult, Schedule, Homework, LearningMaterial, TrainingProgram, NutritionDiary, Recipe, FitnessGame, Message
from config import Config
import json
import os


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
    
    # Проверка настроек GigaChat при запуске
    if GIGACHAT_AVAILABLE:
        creds = app.config.get('GIGACHAT_CREDENTIALS')
        if creds:
            print(f"[OK] GIGACHAT_CREDENTIALS настроены (длина: {len(creds)} символов)")
        else:
            print("[WARNING] GIGACHAT_CREDENTIALS не найдены в config.py!")
            print("Добавьте в config.py: GIGACHAT_CREDENTIALS = 'ваш_ключ'")


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
        
        # Получаем роль
        role = request.form.get('role', 'student')
        if role not in ['teacher', 'student']:
            role = 'student'
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, nickname=nickname, email=email, password=hashed_password, role=role)
        db.session.add(user)
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
    if current_user.is_teacher():
        return redirect(url_for('teacher_profile'))
    else:
        return redirect(url_for('student_profile'))


# ПРОФИЛЬ УЧЕНИКА
@app.route('/profile/student')
@login_required
def student_profile():
    if current_user.is_teacher():
        return redirect(url_for('teacher_profile'))
    
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
                prompt = f"""Ты - эксперт по созданию тестов. Создай тест из {num_questions} вопросов по тексту:

{custom_text}

ВАЖНО:
- correct - это ИНДЕКС от 0 до 3
- 0 = первый вариант, 1 = второй, 2 = третий, 3 = четвертый

ПРИМЕР ПРАВИЛЬНОГО JSON:
{{
  "questions": [
    {{
      "question": "Какая планета ближайшая к Солнцу?",
      "options": ["Меркурий", "Венера", "Земля", "Марс"],
      "correct": 0,
      "explanation": "Правильный ответ - Меркурий (первый вариант). Меркурий находится ближе всего к Солнцу."
    }}
  ]
}}

Верни ТОЛЬКО JSON без пояснений:"""
            else:
                prompt = f"""Создай тест: предмет "{subject}", тема "{topic}", {num_questions} вопросов.

СТРОГИЙ ФОРМАТ:
- correct = индекс 0-3 (0-первый, 1-второй, 2-третий, 3-четвертый)

ПРИМЕР:
{{
  "questions": [
    {{
      "question": "Сколько будет 2+2?",
      "options": ["3", "4", "5", "6"],
      "correct": 1,
      "explanation": "Правильный ответ - 4 (второй вариант). Это базовая операция сложения: 2+2=4."
    }}
  ]
}}

Верни ТОЛЬКО JSON:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()
            
            print("=" * 80)
            print("GIGACHAT ОТВЕТ:")
            print(content[:800])
            print("=" * 80)
            
            content = content.replace('``````', '').strip()
            
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end <= json_start:
                return jsonify({'success': False, 'error': 'Нет JSON в ответе'}), 500
            
            json_str = content[json_start:json_end]
            
            try:
                test_data = json.loads(json_str)
            except json.JSONDecodeError as je:
                print(f"[ERROR] JSON error: {je}")
                return jsonify({'success': False, 'error': 'Невалидный JSON'}), 500
            
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
            prompt = f"""Ты — тренер. Сгенерируй тренировочную программу с заголовком, длительностью и расписанием на дни недели. Цель: {goal}. Уровень: {level}. Длительность: {duration}. Верни только JSON в формате:\n{{"title": "...", "duration": "...", "schedule": {{"Понедельник": ["упр - 3×10"], ...}}}}"""
            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()
            content = content.replace('``````', '').strip()
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start == -1 or json_end <= json_start:
                return jsonify({'success': False, 'error': 'Нет JSON в ответе GigaChat'}), 500
            json_str = content[json_start:json_end]
            program_data = json.loads(json_str)
            # Нормализуем
            program_data['schedule'] = program_data.get('schedule') or {}
            program_data['title'] = program_data.get('title') or f'{goal} — программа'
            program_data['duration'] = program_data.get('duration') or duration
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

            prompt = f"""Ты - помощник-диетолог. Составь план питания на один день в формате строго JSON.

Требования:
- Верни только JSON с ключом "meals" — массив из {meals_count} приёмов пищи
- Каждый приём пищи — объект с полями: meal_type, food_items (массив строк), calories, proteins, fats, carbs
- Целевое количество калорий: {calories or '2000'}
- Предпочтения: {preferences or 'нет'}
- Ограничения/аллергии: {restrictions or 'нет'}

Пример:
{{
  "meals": [
    {{
      "meal_type": "Завтрак",
      "food_items": ["Овсянка с ягодами 200г", "Яйцо всмятку", "Зелёный чай"],
      "calories": 450,
      "proteins": 20,
      "fats": 15,
      "carbs": 60
    }}
  ]
}}

Верни ТОЛЬКО JSON:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()

            print(f"[INFO] GigaChat ответ (план питания): {content[:300]}...")

            content = content.replace('``````', '').strip()
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end <= json_start:
                return jsonify({'success': False, 'error': 'Нет JSON в ответе'}), 500

            json_str = content[json_start:json_end]
            
            try:
                plan = json.loads(json_str)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Невалидный JSON от GigaChat'}), 500

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
        
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            scope="GIGACHAT_API_PERS",
            temperature=0.7  # Повышаем для более креативных рецептов
        ) as giga:

            prompt = f"""Ты - профессиональный шеф-повар. Создай детальный кулинарный рецепт в формате JSON.

Параметры:
- Тип блюда: {dish_type or 'основное блюдо'}
- Кухня: {cuisine or 'европейская'}
- Диета: {dietary or 'обычная'}
- Максимум калорий: {max_calories or '500'} ккал

СТРОГИЙ ФОРМАТ JSON:
{{
  "title": "Название блюда",
  "ingredients": [
    "200г куриной грудки",
    "100г риса басмати",
    "1 средняя морковь",
    "2 ст.л. оливкового масла",
    "Соль, перец по вкусу"
  ],
  "instructions": "1. Промойте рис и отварите в подсоленной воде 15 минут до готовности. 2. Куриную грудку нарежьте кубиками 2x2 см. 3. Разогрейте сковороду с оливковым маслом на среднем огне. 4. Обжарьте курицу 7-8 минут до золотистой корочки. 5. Морковь натрите на крупной тёрке и добавьте к курице. 6. Тушите 5 минут. 7. Смешайте с рисом, посолите и поперчите.",
  "calories": 420,
  "proteins": 38,
  "fats": 12,
  "carbs": 45
}}

ВАЖНО:
- ingredients - массив строк с точными количествами
- instructions - подробная пошаговая инструкция одной строкой
- calories, proteins, fats, carbs - только числа
- Рецепт должен быть реалистичным и вкусным

Верни ТОЛЬКО JSON без дополнительного текста:"""

            response = giga.chat(prompt)
            content = response.choices[0].message.content.strip()

            print("=" * 80)
            print("GIGACHAT ОТВЕТ (РЕЦЕПТ):")
            print(content[:600])
            print("=" * 80)

            # Очистка markdown
            content = content.replace('``````', '').strip()
            
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start == -1 or json_end <= json_start:
                print("[ERROR] JSON не найден в ответе GigaChat")
                return jsonify({'success': False, 'error': 'Нет JSON в ответе GigaChat'}), 500

            json_str = content[json_start:json_end]

            try:
                recipe_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Ошибка парсинга JSON: {e}")
                print(f"Проблемный JSON: {json_str[:300]}")
                return jsonify({'success': False, 'error': f'Невалидный JSON от GigaChat: {str(e)}'}), 500

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
    all_recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
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
        title=data['title'],
        ingredients=json.dumps(data['ingredients'], ensure_ascii=False),
        instructions=data['instructions'],
        calories=data['calories'],
        proteins=data['proteins'],
        fats=data['fats'],
        carbs=data['carbs'],
        image_url=data.get('image_url'),
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
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
