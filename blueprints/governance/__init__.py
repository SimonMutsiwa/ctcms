from flask import Blueprint
from flask_sqlalchemy import SQLAlchemy

# Create a db instance specific to this blueprint if needed
# But better to import from main app
import sys
import os

# Add parent directory to path to import from blueprints
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import db from the main module
try:
    from __init__ import db
except ImportError:
    # Fallback: create a new db instance (not ideal)
    db = SQLAlchemy()

# Create the blueprint
bp = Blueprint('governance', __name__, url_prefix='/api/v1/governance')

# Import routes at the bottom to avoid circular imports
from . import routes