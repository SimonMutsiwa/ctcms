"""
Configuration settings for CTCMS
Updated for Render deployment with PostgreSQL (Neon.tech)
"""

import os
from datetime import timedelta
import sys

# Simple configuration - supports both SQLite (local) and PostgreSQL (Render)
class Config:
    """Base configuration - dynamically selects database"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Get the directory where this file is located
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    
    # Create instance directory if it doesn't exist
    if not os.path.exists(INSTANCE_DIR):
        os.makedirs(INSTANCE_DIR)
    
    # ============================================
    # DATABASE CONFIGURATION
    # ============================================
    
    # Check for Render PostgreSQL URL (priority)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        # Render provides 'postgres://', SQLAlchemy needs 'postgresql://'
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        
        # Use PostgreSQL from environment (Render + Neon.tech)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        print(f"✅ Using PostgreSQL database: {DATABASE_URL[:50]}...")  # Partial for security
    else:
        # Fallback to SQLite for local development
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(INSTANCE_DIR, 'forensic.db')}"
        print("✅ Using SQLite database (local development)")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # ============================================
    # SESSION & SECURITY
    # ============================================
    
    # Session settings (using Flask-Login, not JWT for this prototype)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # JWT (kept for potential future use)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # ============================================
    # CORS SETTINGS
    # ============================================
    
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # ============================================
    # LOGGING
    # ============================================
    
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'ctcms.log')
    
    # Create logs directory if needed
    if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
        os.makedirs(os.path.join(BASE_DIR, 'logs'))
    
    # ============================================
    # FILE UPLOADS
    # ============================================
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # ============================================
    # RISK SCORING THRESHOLDS
    # ============================================
    
    RISK_THRESHOLD_HIGH = int(os.environ.get('RISK_THRESHOLD_HIGH', 70))
    RISK_THRESHOLD_MEDIUM = int(os.environ.get('RISK_THRESHOLD_MEDIUM', 40))
    AUDIT_CASE_THRESHOLD = int(os.environ.get('AUDIT_CASE_THRESHOLD', 70))
    STATUTORY_TAX_RATE = float(os.environ.get('STATUTORY_TAX_RATE', 25.0))
    
    # ============================================
    # ML MODEL SETTINGS
    # ============================================
    
    MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(BASE_DIR, 'models', 'behavioral_model.pkl'))


class DevelopmentConfig(Config):
    """Development configuration - uses SQLite"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration - uses in-memory SQLite"""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration - for Render deployment"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    LOG_LEVEL = 'WARNING'
    
    # Production security: require DATABASE_URL to be set
    if not os.environ.get('DATABASE_URL'):
        print("⚠️ WARNING: DATABASE_URL not set in production!")
        print("Using SQLite will cause data loss on Render restarts.")
        print("Please set DATABASE_URL environment variable.")


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