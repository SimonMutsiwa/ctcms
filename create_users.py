#!/usr/bin/env python
"""
Create default users for the system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from __init__ import create_app, db
from blueprints.governance.models import User

def create_default_users():
    app = create_app()
    with app.app_context():
        users = [
            {
                'username': 'admin',
                'email': 'admin@zimra.gov.zw',
                'password': 'admin123',
                'role': 'admin',
                'full_name': 'System Administrator'
            },
            {
                'username': 'auditor',
                'email': 'auditor@zimra.gov.zw',
                'password': 'auditor123',
                'role': 'auditor',
                'full_name': 'Senior Auditor'
            },
            {
                'username': 'compliance',
                'email': 'compliance@zimra.gov.zw',
                'password': 'compliance123',
                'role': 'compliance',
                'full_name': 'Compliance Officer'
            },
            {
                'username': 'viewer',
                'email': 'viewer@zimra.gov.zw',
                'password': 'viewer123',
                'role': 'viewer',
                'full_name': 'Tax Analyst'
            }
        ]
        
        for user_data in users:
            existing = User.query.filter_by(username=user_data['username']).first()
            if not existing:
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    role=user_data['role'],
                    full_name=user_data['full_name']
                )
                user.set_password(user_data['password'])
                db.session.add(user)
                print(f"Created user: {user_data['username']} ({user_data['role']})")
            else:
                print(f"User already exists: {user_data['username']}")
        
        db.session.commit()
        print("\n✅ Default users created successfully!")

if __name__ == "__main__":
    create_default_users()