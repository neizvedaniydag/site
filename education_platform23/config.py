import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///education_platform.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GIGACHAT_CREDENTIALS = os.getenv('GIGACHAT_CREDENTIALS')

    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600
    PERMANENT_SESSION_LIFETIME = 3600
