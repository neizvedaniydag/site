from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
# gigachat optional for diagnostics - guard import
try:
    from gigachat import GigaChat
except Exception:
    GigaChat = None
from models import db, User, TestResult, PhysicalEducationResult, Schedule, Homework
from config import Config
import json
import os

# ========== ДИАГНОСТИКА ==========
print("\n" + "="*70)
print("🔍 ДИАГНОСТИКА GIGACHAT CREDENTIALS")
print("="*70)

# Проверка 1: Текущая директория
print(f"📁 Текущая директория: {os.getcwd()}")

# Проверка 2: Наличие .env файла
env_path = os.path.join(os.getcwd(), '.env')
print(f"📄 .env файл существует: {os.path.exists(env_path)}")

# Проверка 3: Загрузка dotenv вручную
from dotenv import load_dotenv
load_dotenv_result = load_dotenv(verbose=True)
print(f"🔄 load_dotenv() результат: {load_dotenv_result}")

# Проверка 4: Прямое чтение .env
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        content = f.read()
        print(f"📝 Содержимое .env ({len(content)} символов):")
        # Показываем только первые символы ключа для безопасности
        for line in content.split('\n')[:5]:
            if 'GIGACHAT' in line:
                parts = line.split('=')
                if len(parts) == 2:
                    key = parts[0]
                    value = parts[1][:20] + "..." if len(parts[1]) > 20 else parts[1]
                    print(f"   {key} = {value}")
else:
    print("⚠️ ФАЙЛ .env НЕ НАЙДЕН!")

# Проверка 5: os.getenv
creds = os.getenv('GIGACHAT_CREDENTIALS')
print(f"\n🔑 os.getenv('GIGACHAT_CREDENTIALS'):")
if creds:
    print(f"   ✅ Загружен (длина: {len(creds)} символов)")
    print(f"   Начало: {creds[:30]}...")
else:
    print("   ❌ ВОЗВРАЩАЕТ None!")

# Проверка 6: Config класс
print(f"\n⚙️ Config.GIGACHAT_CREDENTIALS:")
if Config.GIGACHAT_CREDENTIALS:
    print(f"   ✅ Установлен (длина: {len(Config.GIGACHAT_CREDENTIALS)} символов)")
    print(f"   Начало: {Config.GIGACHAT_CREDENTIALS[:30]}...")
else:
    print("   ❌ ПУСТОЙ ИЛИ None!")

print("="*70 + "\n")
# ========== КОНЕЦ ДИАГНОСТИКИ ==========

# Загрузка тем из JSON
def load_subjects_topics():
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'subjects_topics.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

SUBJECTS_TOPICS = load_subjects_topics()
app = Flask(__name__)
app.config.from_object(Config)
