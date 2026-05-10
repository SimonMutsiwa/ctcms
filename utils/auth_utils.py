"""
Authentication and authorization utilities
"""

from flask_jwt_extended import get_jwt_identity, get_jwt
from functools import wraps
from flask import jsonify
import logging

logger = logging.getLogger(__name__)

class AuthUtils:
    """Authentication helper utilities"""
    
    ROLES = {
        'admin': ['view_all', 'edit_all', 'delete_all', 'train_models'],
        'auditor': ['view_cases', 'edit_cases', 'view_reports'],
        'compliance_officer': ['view_scores', 'view_alerts', 'generate_reports'],
        'taxpayer': ['view_own_profile', 'view_own_scores'],
        'viewer': ['view_reports']
    }
    
    @staticmethod
    def get_current_user():
        """Get current authenticated user"""
        try:
            return get_jwt_identity()
        except Exception:
            return None
    
    @staticmethod
    def get_current_user_roles():
        """Get roles of current user"""
        try:
            claims = get_jwt()
            return claims.get('roles', [])
        except Exception:
            return []
    
    @staticmethod
    def has_permission(permission):
        """Check if current user has specific permission"""
        user_roles = AuthUtils.get_current_user_roles()
        for role in user_roles:
            if role in AuthUtils.ROLES and permission in AuthUtils.ROLES[role]:
                return True
        return False
    
    @staticmethod
    def require_permission(permission):
        """Decorator to require permission for route"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not AuthUtils.has_permission(permission):
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'required': permission
                    }), 403
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    @staticmethod
    def require_role(role):
        """Decorator to require specific role"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                user_roles = AuthUtils.get_current_user_roles()
                if role not in user_roles:
                    return jsonify({
                        'error': f'Role {role} required'
                    }), 403
                return f(*args, **kwargs)
            return decorated_function
        return decorator