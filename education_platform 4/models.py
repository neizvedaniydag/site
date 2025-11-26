from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nickname = db.Column(db.String(80), unique=True, nullable=True)  # Уникальный никнейм для поиска
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'teacher' или 'student'
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Привязка ученика к учителю
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    mentor = db.relationship(
        'User',
        remote_side=[id],
        backref=db.backref('assigned_students', lazy='dynamic'),
        foreign_keys=[mentor_id],
        post_update=True
    )
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_student(self):
        return self.role == 'student'
    
    # Связи
    test_results = db.relationship('TestResult', backref='user', lazy=True)
    pe_results = db.relationship('PhysicalEducationResult', backref='user', lazy=True)
    homeworks = db.relationship('Homework', backref='user', lazy=True)
    training_programs = db.relationship('TrainingProgram', backref='user', lazy=True)
    nutrition_diaries = db.relationship('NutritionDiary', backref='user', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(200), nullable=False)
    test_content = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PhysicalEducationResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise_type = db.Column(db.String(100), nullable=False)
    repetitions = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    incorrect_count = db.Column(db.Integer, default=0)
    errors = db.Column(db.Text)  # JSON строка с ошибками
    score = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.String(20), nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher = db.Column(db.String(100))
    classroom = db.Column(db.String(50))

class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LearningMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(db.String(50), nullable=False)  # video, article, instruction
    category = db.Column(db.String(50), nullable=False)  # fitness, anatomy, nutrition
    content = db.Column(db.Text, nullable=False)
    video_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TrainingProgram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.String(50), nullable=False)  # week, month
    schedule = db.Column(db.Text, nullable=False)  # JSON с расписанием
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NutritionDiary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)  # breakfast, lunch, dinner, snack
    food_items = db.Column(db.Text, nullable=False)  # JSON с продуктами
    calories = db.Column(db.Float)
    proteins = db.Column(db.Float)
    fats = db.Column(db.Float)
    carbs = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)  # JSON со списком ингредиентов
    instructions = db.Column(db.Text, nullable=False)
    calories = db.Column(db.Float)
    proteins = db.Column(db.Float)
    fats = db.Column(db.Float)
    carbs = db.Column(db.Float)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FitnessGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_type = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
