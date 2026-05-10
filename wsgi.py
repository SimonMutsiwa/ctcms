"""
WSGI entry point for Render deployment
"""
import os
import sys

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the create_app function
from __init__ import create_app
from config import config

# Get environment
env = os.environ.get('FLASK_ENV', 'production')

# Create the Flask application instance
app = create_app(config[env])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))