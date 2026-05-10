"""
Configuration settings for CTCMS
Updated for Render deployment with PostgreSQL
"""

import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        # Render provides 'postgres://', SQLAlchemy needs 'postgresql://'
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Fallback to SQLite for local development
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
        if not os.path.exists(INSTANCE_DIR):
            os.makedirs(INSTANCE_DIR)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(INSTANCE_DIR, 'forensic.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # JWT (optional, kept for compatibility)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    # Risk scoring thresholds
    RISK_THRESHOLD_HIGH = int(os.environ.get('RISK_THRESHOLD_HIGH', 70))
    RISK_THRESHOLD_MEDIUM = int(os.environ.get('RISK_THRESHOLD_MEDIUM', 40))
    AUDIT_CASE_THRESHOLD = int(os.environ.get('AUDIT_CASE_THRESHOLD', 70))
    STATUTORY_TAX_RATE = float(os.environ.get('STATUTORY_TAX_RATE', 25.0))
    
    # ML Model settings
    MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'behavioral_model.pkl'))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    LOG_LEVEL = 'WARNING'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Return the appropriate configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, DevelopmentConfig)