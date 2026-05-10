"""
Governance module routes with all required endpoints
"""

from decimal import Decimal
import os

from flask import request, jsonify, make_response, send_file
import joblib
import pandas as pd
from . import bp
from .services import GovernanceService
from .models import (
    AuditLog, DetectedBehavior, Taxpayer, TaxReturn, Payment, AuditOutcome, User, UserSession,
    ValidationIssue, BehavioralAlert, ETRAlert, ComplianceReport,
    GovernanceRiskScores, GovernanceIndicators, GovernanceRaw
)

from __init__ import db
from datetime import datetime
import json
import secrets
from functools import wraps
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash


# ==================== HELPER FUNCTIONS ====================

def role_required(role):
    """Decorator to require a specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            if not current_user.has_role(role):
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """Decorator to require a specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            if not current_user.has_permission(permission):
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_audit(action, resource, resource_id=None, details=None):
    """Log user action to audit trail"""
    try:
        audit = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
    except:
        db.session.rollback()


# ==================== AUTHENTICATION ENDPOINTS ====================

@bp.route('/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 401
        
        session_token = secrets.token_urlsafe(32)
        user.last_login = datetime.utcnow()
        
        session_record = UserSession(
            user_id=user.id,
            session_token=session_token,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(session_record)
        db.session.commit()
        
        log_audit('LOGIN', 'auth', str(user.id), f'User {user.username} logged in')
        
        response = jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'session_token': session_token,
            'role': user.role,
            'permissions': {
                'admin': user.has_permission('admin'),
                'auditor': user.has_permission('auditor'),
                'compliance': user.has_permission('compliance'),
                'viewer': user.has_permission('viewer')
            }
        })
        
        response.set_cookie('session_token', session_token, httponly=False, max_age=28800)
        return response, 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """User logout"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session_record = UserSession.query.filter_by(session_token=session_token, user_id=current_user.id).first()
        if session_record:
            session_record.is_active = False
            db.session.commit()
        
        log_audit('LOGOUT', 'auth', str(current_user.id), f'User {current_user.username} logged out')
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/register', methods=['POST'])
@role_required('admin')
def register():
    """Register a new user (admin only)"""
    try:
        data = request.get_json()
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            email=data['email'],
            role=data.get('role', 'viewer'),
            full_name=data.get('full_name')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        log_audit('CREATE_USER', 'users', str(user.id), f'Created user {user.username} with role {user.role}')
        return jsonify({'message': 'User created successfully', 'user': user.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/users', methods=['GET'])
@role_required('admin')
def get_users():
    """Get all users (admin only)"""
    try:
        users = User.query.all()
        return jsonify([u.to_dict() for u in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/users/<int:user_id>', methods=['PUT'])
@role_required('admin')
def update_user(user_id):
    """Update user (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        if 'role' in data:
            user.role = data['role']
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        db.session.commit()
        log_audit('UPDATE_USER', 'users', str(user.id), f'Updated user {user.username}')
        return jsonify({'message': 'User updated', 'user': user.to_dict()}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/users/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        db.session.delete(user)
        db.session.commit()
        log_audit('DELETE_USER', 'users', str(user.id), f'Deleted user {user.username}')
        return jsonify({'message': 'User deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user info"""
    return jsonify({
        'user': current_user.to_dict(),
        'role': current_user.role,
        'permissions': {
            'can_view_all': current_user.has_permission('view_all'),
            'can_edit': current_user.has_permission('edit_all'),
            'can_delete': current_user.has_permission('delete_all'),
            'can_manage_users': current_user.has_permission('manage_users'),
            'can_train_models': current_user.has_permission('train_models'),
            'can_export': current_user.has_permission('export_data')
        }
    }), 200


@bp.route('/auth/audit-logs', methods=['GET'])
@role_required('admin')
def get_audit_logs():
    """Get audit logs (admin only)"""
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return jsonify([l.to_dict() for l in logs]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== DASHBOARD ENDPOINTS ====================

@bp.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get all dashboard statistics"""
    try:
        taxpayers = Taxpayer.query.count()
        scores = GovernanceRiskScores.query.filter_by(fiscal_year=2024).all()
        high_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) >= 70)
        medium_risk = sum(1 for s in scores if s.governance_risk_score and 40 <= float(s.governance_risk_score) < 70)
        low_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) < 40)
        pending_validations = ValidationIssue.query.filter_by(status='Open').count()
        behavioral_alerts = BehavioralAlert.query.filter_by(status='New').count()
        audit_cases = AuditOutcome.query.filter(AuditOutcome.outcome != 'Compliant').count()
        compliance_rate = round((low_risk / taxpayers * 100) if taxpayers > 0 else 0, 1)
        
        try:
            etr_alerts = ETRAlert.query.filter_by(status='New').count()
        except:
            etr_alerts = 0
        
        return jsonify({
            'total_taxpayers': taxpayers,
            'high_risk': high_risk,
            'medium_risk': medium_risk,
            'low_risk': low_risk,
            'pending_validations': pending_validations,
            'etr_alerts': etr_alerts,
            'behavioral_alerts': behavioral_alerts,
            'audit_cases': audit_cases,
            'compliance_rate': compliance_rate
        }), 200
    except Exception as e:
        print(f"Error in dashboard stats: {e}")
        return jsonify({
            'total_taxpayers': Taxpayer.query.count() or 0,
            'high_risk': 0, 'medium_risk': 0, 'low_risk': 0,
            'pending_validations': 0, 'etr_alerts': 0,
            'behavioral_alerts': 0, 'audit_cases': 0,
            'compliance_rate': 0
        }), 200


@bp.route('/dashboard/recent-activity', methods=['GET'])
def get_recent_activity():
    """Get recent activity across all modules"""
    try:
        activities = []
        
        recent_validations = ValidationIssue.query.order_by(ValidationIssue.created_at.desc()).limit(5).all()
        for v in recent_validations:
            taxpayer = Taxpayer.query.get(v.taxpayer_id)
            activities.append({
                'type': 'validation',
                'title': f'Validation Issue: {v.issue_type}',
                'description': v.description[:100] if v.description else 'No description',
                'taxpayer_id': v.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'severity': v.severity,
                'date': v.created_at.isoformat() if v.created_at else None,
                'icon': 'fa-check-double',
                'level': v.severity.lower() if v.severity else 'info'
            })
        
        recent_alerts = BehavioralAlert.query.order_by(BehavioralAlert.created_at.desc()).limit(5).all()
        for a in recent_alerts:
            taxpayer = Taxpayer.query.get(a.taxpayer_id)
            activities.append({
                'type': 'behavioral',
                'title': f'Behavioral Alert: {a.alert_type}',
                'description': a.description[:100] if a.description else 'No description',
                'taxpayer_id': a.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'severity': a.severity,
                'confidence': float(a.confidence_score) if a.confidence_score else 0,
                'date': a.created_at.isoformat() if a.created_at else None,
                'icon': 'fa-brain',
                'level': a.severity.lower() if a.severity else 'info'
            })
        
        recent_audits = AuditOutcome.query.order_by(AuditOutcome.audit_date.desc()).limit(5).all()
        for a in recent_audits:
            taxpayer = Taxpayer.query.get(a.taxpayer_id)
            activities.append({
                'type': 'audit',
                'title': f'Audit Case: {a.outcome}',
                'description': a.findings[:100] if a.findings else 'No findings recorded',
                'taxpayer_id': a.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'outcome': a.outcome,
                'assessment': float(a.additional_assessment) if a.additional_assessment else 0,
                'date': a.audit_date.isoformat() if a.audit_date else None,
                'icon': 'fa-gavel',
                'level': 'info'
            })
        
        activities.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        return jsonify(activities[:10]), 200
        
    except Exception as e:
        print(f"Error in recent activity: {e}")
        return jsonify([]), 200


@bp.route('/tax-returns/<int:taxpayer_id>', methods=['GET'])
def get_tax_returns(taxpayer_id):
    """Get tax returns for a taxpayer"""
    try:
        returns = TaxReturn.query.filter_by(taxpayer_id=taxpayer_id).order_by(TaxReturn.fiscal_year.desc()).all()
        return jsonify([r.to_dict() for r in returns]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/recent-assessments', methods=['GET'])
def get_recent_assessments():
    """Get recent assessments for dashboard"""
    try:
        scores = GovernanceRiskScores.query.order_by(GovernanceRiskScores.computed_at.desc()).limit(10).all()
        assessments = []
        for score in scores:
            taxpayer = Taxpayer.query.get(score.taxpayer_id)
            risk_score = float(score.governance_risk_score) if score.governance_risk_score else 0
            risk_level = 'High Risk' if risk_score >= 70 else 'Medium Risk' if risk_score >= 40 else 'Low Risk'
            assessments.append({
                'taxpayer_id': score.taxpayer_id,
                'company_name': taxpayer.company_name if taxpayer else 'Unknown',
                'risk_score': f'{risk_score:.1f}',
                'risk_level': risk_level,
                'last_assessment': score.computed_at.strftime('%Y-%m-%d') if score.computed_at else 'N/A'
            })
        return jsonify(assessments), 200
    except Exception as e:
        return jsonify([]), 200


@bp.route('/risk-summary', methods=['GET'])
def get_risk_summary():
    """Get risk summary for dashboard"""
    try:
        scores = GovernanceRiskScores.query.filter_by(fiscal_year=2024).all()
        low_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) < 40)
        medium_risk = sum(1 for s in scores if s.governance_risk_score and 40 <= float(s.governance_risk_score) < 70)
        high_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) >= 70)
        return jsonify({'low_risk': low_risk, 'medium_risk': medium_risk, 'high_risk': high_risk}), 200
    except Exception as e:
        return jsonify({'low_risk': 0, 'medium_risk': 0, 'high_risk': 0}), 200


# ==================== VALIDATION ISSUES ====================

@bp.route('/validation-issues', methods=['GET'])
def get_validation_issues():
    """Get all validation issues"""
    try:
        status = request.args.get('status', 'Open')
        severity = request.args.get('severity')
        taxpayer_id = request.args.get('taxpayer_id')
        
        query = ValidationIssue.query
        if status and status != 'All':
            query = query.filter_by(status=status)
        if severity:
            query = query.filter_by(severity=severity)
        if taxpayer_id:
            query = query.filter_by(taxpayer_id=int(taxpayer_id))
        
        issues = query.order_by(ValidationIssue.created_at.desc()).all()
        result = []
        for issue in issues:
            taxpayer = Taxpayer.query.get(issue.taxpayer_id)
            result.append({
                'id': issue.id,
                'taxpayer_id': issue.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'fiscal_year': issue.fiscal_year,
                'issue_type': issue.issue_type,
                'severity': issue.severity,
                'description': issue.description,
                'field_name': issue.field_name,
                'expected_value': issue.expected_value,
                'actual_value': issue.actual_value,
                'status': issue.status,
                'created_at': issue.created_at.isoformat() if issue.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 200


@bp.route('/validation-issues/<int:issue_id>/resolve', methods=['PUT'])
def resolve_validation_issue(issue_id):
    """Resolve a validation issue"""
    try:
        issue = ValidationIssue.query.get_or_404(issue_id)
        issue.status = 'Resolved'
        issue.resolved_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'Issue resolved'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== RISK SCORES ====================

def get_risk_breakdown(taxpayer_id, fiscal_year):
    """Get detailed breakdown of all 7 risk categories"""
    tax_return = TaxReturn.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).first()
    payments = Payment.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).all()
    governance = GovernanceIndicators.query.get((taxpayer_id, fiscal_year))
    validation_issues = ValidationIssue.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year, status='Open').all()
    behavioral_alerts = BehavioralAlert.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year, status='New').all()
    audits = AuditOutcome.query.filter_by(taxpayer_id=taxpayer_id).all()
    
    breakdown = {
        'filing_compliance': {'status': 'Good', 'details': []},
        'payment_compliance': {'status': 'Good', 'details': []},
        'financial_reporting': {'status': 'Good', 'details': []},
        'audit': {'status': 'Good', 'details': []},
        'governance': {'status': 'Good', 'details': []},
        'behavioral': {'status': 'Good', 'details': []},
        'etr': {'status': 'Good', 'details': []}
    }
    
    # Filing compliance
    if tax_return and tax_return.filing_date:
        due_date = datetime(tax_return.fiscal_year, 4, 30)
        if tax_return.filing_date > due_date:
            breakdown['filing_compliance']['status'] = 'Warning'
            breakdown['filing_compliance']['details'].append(f"Filed {(tax_return.filing_date - due_date).days} days late")
    
    # Payment compliance
    if payments:
        late_count = sum(1 for p in payments if p.status == 'Late')
        if late_count > 0:
            breakdown['payment_compliance']['status'] = 'Warning' if late_count <= 2 else 'Critical'
            breakdown['payment_compliance']['details'].append(f"{late_count} late payment(s)")
        
        # Check for underpayment
        if tax_return and tax_return.tax_liability:
            total_paid = sum(float(p.amount) for p in payments)
            tax_liability = float(tax_return.tax_liability)
            if tax_liability > 0 and total_paid < tax_liability * 0.9:
                breakdown['payment_compliance']['status'] = 'Critical'
                breakdown['payment_compliance']['details'].append(f"Underpaid by ${tax_liability - total_paid:,.0f}")
    
    # Financial reporting
    if tax_return and tax_return.accounting_profit and tax_return.accounting_profit > 0:
        accounting_profit = float(tax_return.accounting_profit)
        taxable_income = float(tax_return.taxable_income) if tax_return.taxable_income else 0
        book_tax_ratio = taxable_income / accounting_profit
        if book_tax_ratio < 0.7:
            breakdown['financial_reporting']['status'] = 'Critical'
            breakdown['financial_reporting']['details'].append(f"Large book-tax difference: taxable income only {book_tax_ratio*100:.0f}% of profit")
        elif book_tax_ratio < 0.85:
            breakdown['financial_reporting']['status'] = 'Warning'
            breakdown['financial_reporting']['details'].append(f"Moderate book-tax difference: {book_tax_ratio*100:.0f}% of profit")
    
    # Audit
    non_compliant = [a for a in audits if a.outcome != 'Compliant']
    if non_compliant:
        breakdown['audit']['status'] = 'Critical'
        breakdown['audit']['details'].append(f"{len(non_compliant)} non-compliant audit(s)")
    
    # Governance
    if governance:
        independence = governance.independence_ratio or 0
        if independence < 30:
            breakdown['governance']['status'] = 'Critical'
            breakdown['governance']['details'].append(f"Low board independence: {independence:.1f}%")
        elif independence < 50:
            breakdown['governance']['status'] = 'Warning'
            breakdown['governance']['details'].append(f"Moderate independence: {independence:.1f}%")
        
        expertise = governance.expertise_score or 0
        if expertise < 20:
            breakdown['governance']['status'] = 'Warning'
            breakdown['governance']['details'].append(f"Insufficient financial expertise: {expertise:.1f}%")
        
        diversity = governance.diversity_index or 0
        if diversity < 10:
            breakdown['governance']['status'] = 'Warning'
            breakdown['governance']['details'].append(f"Low gender diversity: {diversity:.1f}%")
    
    # Behavioral
    if behavioral_alerts:
        breakdown['behavioral']['status'] = 'Warning'
        breakdown['behavioral']['details'].append(f"{len(behavioral_alerts)} behavioral alert(s)")
    
    if validation_issues:
        breakdown['behavioral']['status'] = 'Warning'
        breakdown['behavioral']['details'].append(f"{len(validation_issues)} validation issue(s)")
    
    # ETR
    if tax_return and tax_return.accounting_profit and tax_return.accounting_profit > 0:
        etr = (float(tax_return.tax_liability or 0) / float(tax_return.accounting_profit)) * 100
        statutory_rate = 25.0
        if etr < 15:
            breakdown['etr']['status'] = 'Critical'
            breakdown['etr']['details'].append(f"ETR: {etr:.1f}% (very low, statutory: {statutory_rate:.0f}%)")
        elif etr < 19:
            breakdown['etr']['status'] = 'Warning'
            breakdown['etr']['details'].append(f"ETR: {etr:.1f}% (below statutory rate of {statutory_rate:.0f}%)")
        elif etr > 30:
            breakdown['etr']['status'] = 'Warning'
            breakdown['etr']['details'].append(f"ETR: {etr:.1f}% (above statutory rate)")
    
    return breakdown


def generate_high_risk_interpretation(breakdown):
    """Generate comprehensive interpretation for high risk companies"""
    critical_areas = []
    warning_areas = []
    
    category_names = {
        'filing_compliance': 'Filing Compliance',
        'payment_compliance': 'Payment Compliance', 
        'financial_reporting': 'Financial Reporting',
        'audit': 'Audit History',
        'governance': 'Governance',
        'behavioral': 'Behavioral Patterns',
        'etr': 'Effective Tax Rate'
    }
    
    for category, data in breakdown.items():
        if data['status'] == 'Critical':
            critical_areas.append(category_names.get(category, category))
        elif data['status'] == 'Warning':
            warning_areas.append(category_names.get(category, category))
    
    interpretation = "⚠️ HIGH RISK - Immediate attention required. "
    
    if critical_areas:
        interpretation += f"Critical issues detected in: {', '.join(critical_areas)}. "
    if warning_areas:
        interpretation += f"Warning signs in: {', '.join(warning_areas)}. "
    
    # Add specific details from the most critical areas
    for category, data in breakdown.items():
        if data['status'] == 'Critical' and data['details']:
            interpretation += f" {category_names.get(category, category)}: {data['details'][0]}. "
            break
    
    interpretation += "Comprehensive audit recommended."
    
    return interpretation


def generate_medium_risk_interpretation(breakdown):
    """Generate comprehensive interpretation for medium risk companies"""
    warning_areas = []
    details_list = []
    
    category_names = {
        'filing_compliance': 'Filing Compliance',
        'payment_compliance': 'Payment Compliance',
        'financial_reporting': 'Financial Reporting', 
        'audit': 'Audit History',
        'governance': 'Governance',
        'behavioral': 'Behavioral Patterns',
        'etr': 'Effective Tax Rate'
    }
    
    for category, data in breakdown.items():
        if data['status'] == 'Warning' or data['status'] == 'Critical':
            warning_areas.append(category_names.get(category, category))
            if data['details']:
                details_list.append(f"{category_names.get(category, category)}: {data['details'][0]}")
    
    interpretation = "📊 MEDIUM RISK - Monitoring required. "
    
    if warning_areas:
        interpretation += f"Concerns detected in: {', '.join(warning_areas)}. "
    
    if details_list:
        interpretation += f" Specific issues: {details_list[0]}. "
    
    interpretation += "Schedule follow-up review and strengthen internal controls."
    
    return interpretation


def generate_low_risk_interpretation(breakdown):
    """Generate comprehensive interpretation for low risk companies"""
    interpretation = "✅ LOW RISK - Compliant. "
    interpretation += "No significant issues detected across all risk categories. "
    
    # Add positive feedback if available
    for category, data in breakdown.items():
        if data['status'] == 'Good' and data['details']:
            interpretation += f" {category.replace('_', ' ').title()} is satisfactory."
            break
    
    interpretation += " Continue current practices and maintain regular monitoring."
    
    return interpretation

@bp.route('/risk/<int:taxpayer_id>/<int:fiscal_year>', methods=['GET'])
def get_risk_score(taxpayer_id, fiscal_year):
    """Get comprehensive risk score with multi-factor interpretation"""
    try:
        risk_score = GovernanceRiskScores.query.get((taxpayer_id, fiscal_year))
        
        if not risk_score:
            return jsonify({'error': 'No risk score found'}), 404
        
        score = float(risk_score.governance_risk_score)
        
        # Get detailed risk breakdown from all 7 categories
        risk_breakdown = get_risk_breakdown(taxpayer_id, fiscal_year)
        
        # Generate comprehensive interpretation based on all risk factors
        if score >= 70:
            category = 'High Risk'
            interpretation = generate_high_risk_interpretation(risk_breakdown)
        elif score >= 40:
            category = 'Medium Risk'
            interpretation = generate_medium_risk_interpretation(risk_breakdown)
        else:
            category = 'Low Risk'
            interpretation = generate_low_risk_interpretation(risk_breakdown)
        
        return jsonify({
            'taxpayer_id': taxpayer_id,
            'fiscal_year': fiscal_year,
            'governance_risk_score': score,
            'risk_category': category,
            'interpretation': interpretation,
            'risk_breakdown': risk_breakdown
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
    

@bp.route('/risk-history', methods=['GET'])
def get_risk_history():
    """Get risk score history"""
    try:
        scores = GovernanceRiskScores.query.order_by(GovernanceRiskScores.computed_at.desc()).limit(50).all()
        result = []
        for score in scores:
            taxpayer = Taxpayer.query.get(score.taxpayer_id)
            risk_score = float(score.governance_risk_score) if score.governance_risk_score else 0
            category = 'High Risk' if risk_score >= 70 else 'Medium Risk' if risk_score >= 40 else 'Low Risk'
            result.append({
                'taxpayer_id': score.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'fiscal_year': score.fiscal_year,
                'governance_risk_score': f'{risk_score:.1f}',
                'risk_category': category
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 200


@bp.route('/risk/<int:taxpayer_id>/<int:fiscal_year>/refresh', methods=['POST'])
def refresh_risk_score(taxpayer_id, fiscal_year):
    """Force recompute risk score"""
    try:
        risk_score = GovernanceService.compute_risk_score(taxpayer_id, fiscal_year)
        if risk_score is not None:
            return jsonify({'message': 'Risk score recomputed', 'risk_score': risk_score}), 200
        return jsonify({'error': 'Could not compute risk score'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== BEHAVIORAL ALERTS ====================

@bp.route('/behavioral-alerts', methods=['GET'])
def get_behavioral_alerts():
    """Get all behavioral alerts"""
    try:
        status = request.args.get('status', 'New')
        severity = request.args.get('severity')
        taxpayer_id = request.args.get('taxpayer_id')
        
        query = BehavioralAlert.query
        if status and status != 'All':
            query = query.filter_by(status=status)
        if severity:
            query = query.filter_by(severity=severity)
        if taxpayer_id:
            query = query.filter_by(taxpayer_id=int(taxpayer_id))
        
        alerts = query.order_by(BehavioralAlert.created_at.desc()).all()
        result = []
        for alert in alerts:
            taxpayer = Taxpayer.query.get(alert.taxpayer_id)
            result.append({
                'id': alert.id,
                'taxpayer_id': alert.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'fiscal_year': alert.fiscal_year,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'description': alert.description,
                'confidence_score': float(alert.confidence_score) if alert.confidence_score else 0,
                'status': alert.status,
                'created_at': alert.created_at.isoformat() if alert.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 200


@bp.route('/behavioral-alerts/<int:alert_id>/dismiss', methods=['PUT'])
def dismiss_alert(alert_id):
    """Dismiss a behavioral alert"""
    try:
        alert = BehavioralAlert.query.get_or_404(alert_id)
        alert.status = 'Dismissed'
        db.session.commit()
        return jsonify({'message': 'Alert dismissed'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== ETR ALERTS ====================

@bp.route('/etr-alerts', methods=['GET'])
def get_etr_alerts():
    """Get all ETR alerts"""
    try:
        status = request.args.get('status', 'New')
        taxpayer_id = request.args.get('taxpayer_id')
        
        query = ETRAlert.query
        if status and status != 'All':
            query = query.filter_by(status=status)
        if taxpayer_id:
            query = query.filter_by(taxpayer_id=int(taxpayer_id))
        
        alerts = query.order_by(ETRAlert.created_at.desc()).all()
        result = []
        for alert in alerts:
            taxpayer = Taxpayer.query.get(alert.taxpayer_id)
            result.append({
                'id': alert.id,
                'taxpayer_id': alert.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'fiscal_year': alert.fiscal_year,
                'computed_etr': float(alert.computed_etr) if alert.computed_etr else 0,
                'statutory_rate': float(alert.statutory_rate) if alert.statutory_rate else 25,
                'variance': float(alert.variance) if alert.variance else 0,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'description': alert.description,
                'status': alert.status,
                'created_at': alert.created_at.isoformat() if alert.created_at else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 200


# ==================== ETR ANALYSIS ====================

@bp.route('/etr/calculate/<int:taxpayer_id>/<int:fiscal_year>', methods=['GET'])
def calculate_comprehensive_etr(taxpayer_id, fiscal_year):
    """Calculate comprehensive ETR analysis with forensic accounting metrics"""
    try:
        taxpayer = Taxpayer.query.get_or_404(taxpayer_id)
        tax_return = TaxReturn.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).first()
        
        if not tax_return:
            return simple_etr_calculation(taxpayer_id, fiscal_year)
        
        payments = Payment.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).all()
        governance = GovernanceIndicators.query.get((taxpayer_id, fiscal_year))
        historical_returns = TaxReturn.query.filter(
            TaxReturn.taxpayer_id == taxpayer_id,
            TaxReturn.fiscal_year < fiscal_year
        ).order_by(TaxReturn.fiscal_year.desc()).limit(3).all()
        
        analysis = perform_etr_analysis(tax_return, payments, governance, historical_returns, taxpayer)
        return jsonify(analysis), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def simple_etr_calculation(taxpayer_id, fiscal_year):
    """Fallback simple ETR calculation when full data is not available"""
    try:
        tax_return = TaxReturn.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).first()
        if not tax_return:
            return jsonify({'error': 'No tax return found for this year'}), 404
        
        tax_paid = float(tax_return.tax_liability) if tax_return.tax_liability else 0
        accounting_profit = float(tax_return.accounting_profit) if tax_return.accounting_profit else 0
        etr = (tax_paid / accounting_profit * 100) if accounting_profit > 0 else 0
        
        statutory_rate = 25.0
        variance = statutory_rate - etr
        
        if etr < statutory_rate * 0.7:
            risk_level = 'High Risk - Possible Tax Avoidance'
            recommendation = 'Review tax planning strategies and governance structure'
        elif etr < statutory_rate * 0.9:
            risk_level = 'Medium Risk - Requires Monitoring'
            recommendation = 'Monitor ETR trends and governance improvements'
        else:
            risk_level = 'Low Risk - Compliant'
            recommendation = 'Continue current practices'
        
        return jsonify({
            'taxpayer_id': taxpayer_id,
            'fiscal_year': fiscal_year,
            'etr': f'{etr:.1f}',
            'statutory_rate': statutory_rate,
            'variance': f'{variance:.1f}',
            'risk_level': risk_level,
            'recommendation': recommendation
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def perform_etr_analysis(tax_return, payments, governance, historical_returns, taxpayer):
    """Perform comprehensive ETR analysis using forensic accounting formulas"""
    total_income = float(tax_return.total_income) if tax_return.total_income else 0
    taxable_income = float(tax_return.taxable_income) if tax_return.taxable_income else 0
    tax_liability = float(tax_return.tax_liability) if tax_return.tax_liability else 0
    accounting_profit = float(tax_return.accounting_profit) if tax_return.accounting_profit else 0
    
    statutory_rate = 0.25
    statutory_etr = statutory_rate * 100
    
    if accounting_profit > 0:
        actual_etr = (tax_liability / accounting_profit) * 100
    else:
        actual_etr = 0
    
    total_payments = sum(float(p.amount) for p in payments) if payments else 0
    cash_etr = (total_payments / accounting_profit * 100) if accounting_profit > 0 else 0
    current_etr = (tax_liability / total_income * 100) if total_income > 0 else 0
    
    absolute_variance = actual_etr - statutory_etr
    relative_variance = (absolute_variance / statutory_etr * 100) if statutory_etr > 0 else 0
    
    industry_benchmark = taxpayer.get_industry_benchmark()
    industry_expected_etr = industry_benchmark.get('expected_etr', 0.20) * 100
    industry_variance = actual_etr - industry_expected_etr
    
    book_tax_difference = accounting_profit - taxable_income
    permanent_btd_ratio = (book_tax_difference / accounting_profit * 100) if accounting_profit > 0 else 0
    temporary_btd = tax_liability - total_payments
    etr_gap = statutory_etr - actual_etr
    tax_avoidance_score = min(max((etr_gap / statutory_etr) * 100, 0), 100) if statutory_etr > 0 else 0
    
    historical_etrs = []
    for hr in historical_returns:
        if hr.accounting_profit and hr.accounting_profit > 0:
            hr_etr = (float(hr.tax_liability) / float(hr.accounting_profit)) * 100
            historical_etrs.append({
                'year': hr.fiscal_year,
                'etr': hr_etr,
                'tax_liability': float(hr.tax_liability),
                'accounting_profit': float(hr.accounting_profit)
            })
    
    if len(historical_etrs) >= 2:
        avg_historical_etr = sum(h['etr'] for h in historical_etrs) / len(historical_etrs)
        etr_trend = actual_etr - avg_historical_etr
        trend_percentage = (etr_trend / avg_historical_etr * 100) if avg_historical_etr > 0 else 0
    else:
        avg_historical_etr = actual_etr
        etr_trend = 0
        trend_percentage = 0
    
    risk_indicators = []
    risk_score = 0
    
    if etr_gap > 10:
        risk_indicators.append(f'Large ETR gap of {etr_gap:.1f}% suggests possible tax avoidance')
        risk_score += 30
    elif etr_gap > 5:
        risk_indicators.append(f'Moderate ETR gap of {etr_gap:.1f}% requires monitoring')
        risk_score += 15
    
    if book_tax_difference > 0:
        risk_indicators.append(f'Positive book-tax difference of ${book_tax_difference:,.0f} indicates book income > taxable income')
        risk_score += 20
    elif book_tax_difference < 0:
        risk_indicators.append(f'Negative book-tax difference of ${abs(book_tax_difference):,.0f} requires investigation')
        risk_score += 25
    
    if abs(permanent_btd_ratio) > 20:
        risk_indicators.append(f'High permanent BTD ratio of {permanent_btd_ratio:.1f}% suggests aggressive tax planning')
        risk_score += 25
    elif abs(permanent_btd_ratio) > 10:
        risk_indicators.append(f'Moderate permanent BTD ratio of {permanent_btd_ratio:.1f}% requires review')
        risk_score += 10
    
    cash_etr_variance = abs(cash_etr - actual_etr)
    if cash_etr_variance > 10:
        risk_indicators.append(f'Large discrepancy between cash ETR ({cash_etr:.1f}%) and actual ETR ({actual_etr:.1f}%)')
        risk_score += 20
    elif cash_etr_variance > 5:
        risk_indicators.append(f'Moderate cash-ETR variance of {cash_etr_variance:.1f}%')
        risk_score += 10
    
    if trend_percentage < -15:
        risk_indicators.append(f'Declining ETR trend of {trend_percentage:.1f}% over {len(historical_etrs)} years')
        risk_score += 25
    elif trend_percentage < -5:
        risk_indicators.append(f'Moderate ETR decline of {trend_percentage:.1f}%')
        risk_score += 10
    
    if abs(industry_variance) > 10:
        risk_indicators.append(f'ETR deviates significantly from industry average ({industry_expected_etr:.1f}%)')
        risk_score += 15
    
    if governance:
        if governance.independence_ratio and governance.independence_ratio < 30:
            risk_indicators.append('Weak board independence (low oversight) increases tax risk')
            risk_score += 15
        if governance.ceo_duality:
            risk_indicators.append('CEO duality may reduce oversight effectiveness')
            risk_score += 10
    
    if risk_score >= 70:
        risk_level = 'High Risk'
        risk_color = 'red'
        recommendation = 'Immediate audit recommended. Significant tax avoidance indicators detected.'
    elif risk_score >= 40:
        risk_level = 'Medium Risk'
        risk_color = 'orange'
        recommendation = 'Further investigation recommended. Monitor tax positions closely.'
    elif risk_score >= 20:
        risk_level = 'Low Risk'
        risk_color = 'yellow'
        recommendation = 'Routine monitoring. Minor discrepancies noted.'
    else:
        risk_level = 'Compliant'
        risk_color = 'green'
        recommendation = 'No significant issues detected. Continue current practices.'
    
    return {
        'taxpayer': {
            'id': taxpayer.id,
            'name': taxpayer.company_name,
            'tin': taxpayer.tin,
            'industry': taxpayer.industry
        },
        'fiscal_year': tax_return.fiscal_year,
        'financial_data': {
            'total_income': round(total_income, 2),
            'taxable_income': round(taxable_income, 2),
            'accounting_profit': round(accounting_profit, 2),
            'tax_liability': round(tax_liability, 2),
            'total_payments': round(total_payments, 2),
            'payment_count': len(payments)
        },
        'etr_calculations': {
            'statutory_etr': round(statutory_etr, 2),
            'actual_etr': round(actual_etr, 2),
            'cash_etr': round(cash_etr, 2),
            'current_etr': round(current_etr, 2),
            'industry_benchmark_etr': round(industry_expected_etr, 2)
        },
        'variance_analysis': {
            'absolute_variance': round(absolute_variance, 2),
            'relative_variance': round(relative_variance, 2),
            'industry_variance': round(industry_variance, 2),
            'cash_etr_variance': round(cash_etr_variance, 2)
        },
        'forensic_metrics': {
            'etr_gap': round(etr_gap, 2),
            'book_tax_difference': round(book_tax_difference, 2),
            'permanent_btd_ratio': round(permanent_btd_ratio, 2),
            'temporary_btd': round(temporary_btd, 2),
            'tax_avoidance_score': round(tax_avoidance_score, 2),
            'cash_etr_variance': round(cash_etr_variance, 2),
            'industry_variance': round(industry_variance, 2),
            'trend_percentage': round(trend_percentage, 2)
        },
        'trend_analysis': {
            'historical_etrs': historical_etrs,
            'average_historical_etr': round(avg_historical_etr, 2),
            'etr_trend': round(etr_trend, 2),
            'trend_percentage': round(trend_percentage, 2)
        },
        'risk_assessment': {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'risk_indicators': risk_indicators,
            'recommendation': recommendation
        }
    }


@bp.route('/etr/companies', methods=['GET'])
def get_companies_for_etr():
    """Get list of companies for ETR analysis"""
    try:
        companies = Taxpayer.query.all()
        result = []
        for company in companies:
            years = [r.fiscal_year for r in company.returns]
            result.append({
                'id': company.id,
                'tin': company.tin,
                'company_name': company.company_name,
                'industry': company.industry,
                'available_years': sorted(years),
                'latest_year': max(years) if years else None
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== AUDIT CASES ====================

@bp.route('/audit-cases', methods=['GET'])
def get_audit_cases():
    """Get all audit cases"""
    try:
        outcome = request.args.get('status')
        query = AuditOutcome.query
        if outcome:
            query = query.filter_by(outcome=outcome)
        audits = query.order_by(AuditOutcome.audit_date.desc()).all()
        result = []
        for audit in audits:
            taxpayer = Taxpayer.query.get(audit.taxpayer_id)
            result.append({
                'id': audit.id,
                'taxpayer_id': audit.taxpayer_id,
                'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                'audit_date': audit.audit_date.isoformat() if audit.audit_date else None,
                'findings': audit.findings,
                'additional_assessment': float(audit.additional_assessment) if audit.additional_assessment else 0,
                'penalties': float(audit.penalties) if audit.penalties else 0,
                'outcome': audit.outcome,
                'recommendation': audit.recommendation
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 200

@bp.route('/audit/cases/export/<int:fiscal_year>', methods=['GET'])
def export_audit_cases_csv(fiscal_year):
    """Export audit cases as CSV file"""
    try:
        import csv
        from io import StringIO
        
        # Get audit cases for the fiscal year
        audits = AuditOutcome.query.filter(
            db.extract('year', AuditOutcome.audit_date) == fiscal_year
        ).all()
        
        export_data = []
        for audit in audits:
            taxpayer = Taxpayer.query.get(audit.taxpayer_id)
            
            # Get risk score for context
            risk_score = GovernanceRiskScores.query.filter_by(
                taxpayer_id=audit.taxpayer_id,
                fiscal_year=fiscal_year
            ).first()
            
            export_data.append({
                'Case ID': audit.id,
                'Taxpayer ID': audit.taxpayer_id,
                'Company Name': taxpayer.company_name if taxpayer else 'Unknown',
                'Industry': taxpayer.industry if taxpayer else 'N/A',
                'Audit Date': audit.audit_date.strftime('%Y-%m-%d') if audit.audit_date else 'N/A',
                'Risk Score': float(risk_score.governance_risk_score) if risk_score else 0,
                'Findings': audit.findings[:200] if audit.findings else 'No findings',
                'Additional Assessment': float(audit.additional_assessment) if audit.additional_assessment else 0,
                'Penalties': float(audit.penalties) if audit.penalties else 0,
                'Outcome': audit.outcome,
                'Recommendation': audit.recommendation[:100] if audit.recommendation else 'N/A',
                'Status': 'Closed' if audit.outcome != 'Compliant' else 'Resolved'
            })
        
        # Create CSV content
        output = StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        
        csv_content = output.getvalue()
        output.close()
        
        filename = f'audit_cases_export_{fiscal_year}.csv'
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"Error exporting audit cases: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== COMPLIANCE REPORTS ====================

@bp.route('/reports', methods=['GET'])
def get_reports():
    """Get all compliance reports"""
    try:
        reports = ComplianceReport.query.order_by(
            ComplianceReport.generated_at.desc()
        ).all()
        
        result = [{
            'id': r.id,
            'report_type': r.report_type,
            'fiscal_year': r.fiscal_year,
            'generated_at': r.generated_at.isoformat() if r.generated_at else None,
            'file_path': r.file_path
        } for r in reports]
        
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in reports: {e}")
        return jsonify([]), 200


@bp.route('/reports/generate', methods=['POST'])
def generate_compliance_report():
    """Generate a compliance report and return as PDF"""
    try:
        from weasyprint import HTML
        import tempfile
        
        data = request.get_json()
        report_type = data.get('report_type', 'risk-summary')
        fiscal_year = data.get('fiscal_year', 2024)
        
        # Collect data for the report
        companies = Taxpayer.query.all()
        report_data = []
        
        for company in companies:
            # Get risk score
            risk = GovernanceRiskScores.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year
            ).first()
            
            risk_score = float(risk.governance_risk_score) if risk else 0
            if risk_score >= 70:
                risk_level = 'High Risk'
            elif risk_score >= 40:
                risk_level = 'Medium Risk'
            else:
                risk_level = 'Low Risk'
            
            # Get validation issues count
            validation_count = ValidationIssue.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year,
                status='Open'
            ).count()
            
            # Get behavioral alerts count
            alert_count = BehavioralAlert.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year,
                status='New'
            ).count()
            
            # Get tax return data
            tax_return = TaxReturn.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year
            ).first()
            
            report_data.append({
                'company_name': company.company_name,
                'tin': company.tin,
                'industry': company.industry,
                'risk_score': round(risk_score, 1),
                'risk_level': risk_level,
                'validation_issues': validation_count,
                'behavioral_alerts': alert_count,
                'tax_liability': float(tax_return.tax_liability) if tax_return else 0,
                'tax_paid': float(tax_return.tax_liability) if tax_return else 0
            })
        
        # Sort by risk score (highest first)
        report_data.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Calculate summary statistics
        summary = {
            'total_companies': len(report_data),
            'high_risk': sum(1 for c in report_data if c['risk_level'] == 'High Risk'),
            'medium_risk': sum(1 for c in report_data if c['risk_level'] == 'Medium Risk'),
            'low_risk': sum(1 for c in report_data if c['risk_level'] == 'Low Risk'),
            'total_tax_liability': sum(c['tax_liability'] for c in report_data),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Generate HTML report
        html_content = generate_report_html(report_data, fiscal_year, report_type, summary)
        
        # Create PDF
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            f.write(html_content.encode('utf-8'))
            temp_html = f.name
        
        pdf_path = temp_html.replace('.html', '.pdf')
        HTML(temp_html).write_pdf(pdf_path)
        
        # Clean up temp file
        os.unlink(temp_html)
        
        # Save to database
        report = ComplianceReport(
            report_type=report_type,
            fiscal_year=fiscal_year,
            data=report_data,
            file_path=pdf_path
        )
        db.session.add(report)
        db.session.commit()
        
        # Send file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'compliance_report_{report_type}_{fiscal_year}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def generate_report_html(report_data, fiscal_year, report_type, summary):
    """Generate HTML content for the report"""
    
    # Report titles
    titles = {
        'risk-summary': 'Risk Assessment Summary',
        'validation-report': 'Validation Issues Report',
        'behavioral-report': 'Behavioral Analysis Report',
        'etr-report': 'ETR Analysis Report',
        'audit-report': 'Audit Outcomes Report'
    }
    
    title = titles.get(report_type, 'Compliance Report')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>CTCMS - {title} {fiscal_year}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ text-align: center; border-bottom: 2px solid #1a472a; margin-bottom: 30px; }}
            .header h1 {{ color: #1a472a; }}
            .summary-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 30px 0; }}
            .stat-card {{ background: #f8fafc; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-number {{ font-size: 28px; font-weight: bold; color: #1a472a; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8fafc; }}
            .risk-high {{ color: #dc2626; }}
            .risk-medium {{ color: #e67e22; }}
            .risk-low {{ color: #16a34a; }}
            .footer {{ text-align: center; font-size: 11px; margin-top: 40px; border-top: 1px solid #ddd; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ZIMRA - Corporate Tax Compliance Report</h1>
            <h2>{title}</h2>
            <p>Fiscal Year: {fiscal_year} | Generated: {summary['generated_at']}</p>
        </div>
        
        <div class="summary-stats">
            <div class="stat-card"><div class="stat-number">{summary['total_companies']}</div><div>Total Companies</div></div>
            <div class="stat-card"><div class="stat-number risk-high">{summary['high_risk']}</div><div>High Risk</div></div>
            <div class="stat-card"><div class="stat-number risk-medium">{summary['medium_risk']}</div><div>Medium Risk</div></div>
            <div class="stat-card"><div class="stat-number risk-low">{summary['low_risk']}</div><div>Low Risk</div></div>
        </div>
        
        <h2>Company Compliance Summary</h2>
        <table>
            <thead><tr><th>Company</th><th>Industry</th><th>Risk Score</th><th>Risk Level</th><th>Issues</th><th>Alerts</th></tr></thead>
            <tbody>
    """
    
    for company in report_data[:50]:
        risk_class = 'high' if company['risk_level'] == 'High Risk' else ('medium' if company['risk_level'] == 'Medium Risk' else 'low')
        html += f"""
                <tr>
                    <td>{company['company_name']}</td>
                    <td>{company['industry']}</td>
                    <td><strong>{company['risk_score']}%</strong></td>
                    <td class="risk-{risk_class}">{company['risk_level']}</td>
                    <td>{company['validation_issues']}</td>
                    <td>{company['behavioral_alerts']}</td>
                </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        
        <div class="footer">
            <p>Generated by CTCMS - ZIMRA Corporate Tax Compliance Monitoring System</p>
        </div>
    </body>
    </html>
    """
    
    return html


@bp.route('/reports/<int:report_id>/download', methods=['GET'])
def download_report_file(report_id):
    """Download a generated report"""
    try:
        report = ComplianceReport.query.get_or_404(report_id)
        
        if report.file_path and os.path.exists(report.file_path):
            return send_file(
                report.file_path,
                as_attachment=True,
                download_name=f'report_{report.report_type}_{report.fiscal_year}.pdf',
                mimetype='application/pdf'
            )
        else:
            return jsonify({'error': 'Report file not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/reports/export/<string:report_type>/<int:fiscal_year>', methods=['GET'])
def export_report_data(report_type, fiscal_year):
    """Export report data as CSV file"""
    try:
        import csv
        from io import StringIO
        
        # Collect data
        companies = Taxpayer.query.all()
        export_data = []
        
        for company in companies:
            risk = GovernanceRiskScores.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year
            ).first()
            
            risk_score = float(risk.governance_risk_score) if risk else 0
            if risk_score >= 70:
                risk_level = 'High Risk'
            elif risk_score >= 40:
                risk_level = 'Medium Risk'
            else:
                risk_level = 'Low Risk'
            
            validation_count = ValidationIssue.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year,
                status='Open'
            ).count()
            
            alert_count = BehavioralAlert.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year,
                status='New'
            ).count()
            
            # Get ETR data
            tax_return = TaxReturn.query.filter_by(
                taxpayer_id=company.id,
                fiscal_year=fiscal_year
            ).first()
            
            etr = None
            if tax_return and tax_return.accounting_profit and tax_return.accounting_profit > 0:
                tax_paid = float(tax_return.tax_liability) if tax_return.tax_liability else 0
                accounting_profit = float(tax_return.accounting_profit)
                etr = round((tax_paid / accounting_profit * 100), 2) if accounting_profit > 0 else 0
            
            export_data.append({
                'Company Name': company.company_name,
                'TIN': company.tin,
                'Industry': company.industry,
                'Risk Score': round(risk_score, 1),
                'Risk Level': risk_level,
                'ETR (%)': etr if etr else 'N/A',
                'Validation Issues': validation_count,
                'Behavioral Alerts': alert_count,
                'Status': 'Active'
            })
        
        # Sort by risk score (highest first)
        export_data.sort(key=lambda x: x['Risk Score'], reverse=True)
        
        # Create CSV content
        output = StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        
        # Create response
        csv_content = output.getvalue()
        output.close()
        
        # Create filename
        filename = f'compliance_export_{report_type}_{fiscal_year}.csv'
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"Error exporting report: {e}")
        return jsonify({'error': str(e)}), 500
    
# ==================== BEHAVIORAL PREDICTION ENDPOINTS ====================

class BehavioralRiskModel:
    """ML Model to detect risky tax behaviors - Prediction only"""
    
    REQUIRED_COLUMNS = ['Revenue', 'Expenses', 'Profit', 'Tax_Liability', 'Tax_Paid', 
                       'Late_Filings', 'Compliance_Violations', 'Tax_Compliance_Ratio', 
                       'Audit_Findings', 'Audit_to_Tax_Ratio']
    
    SELECTED_FEATURES = [
        'profit_margin', 'tax_burden', 'expense_ratio', 'payment_gap',
        'compliance_score', 'late_filing_penalty', 'violation_penalty',
        'audit_risk', 'tax_avoidance_index', 'Late_Filings', 
        'Compliance_Violations', 'Audit_Findings'
    ]
    
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                      'models', 'behavioral_model.pkl')
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.label_encoder = None
        self.load_model()
    
    def prepare_features(self, df):
        """Engineer features from raw data"""
        features = df.copy()
        
        for col in self.REQUIRED_COLUMNS:
            if col not in features.columns:
                features[col] = 0
        
        revenue_safe = features['Revenue'] + 1
        tax_liability_safe = features['Tax_Liability'] + 1
        
        features['profit_margin'] = features['Profit'] / revenue_safe
        features['tax_burden'] = features['Tax_Liability'] / revenue_safe
        features['expense_ratio'] = features['Expenses'] / revenue_safe
        features['payment_gap'] = (features['Tax_Liability'] - features['Tax_Paid']) / tax_liability_safe
        features['compliance_score'] = features['Tax_Compliance_Ratio']
        features['late_filing_penalty'] = features['Late_Filings'] * 0.1
        features['violation_penalty'] = features['Compliance_Violations'] * 0.15
        features['audit_risk'] = features['Audit_Findings'] / (features['Audit_to_Tax_Ratio'] + 1)
        features['tax_avoidance_index'] = abs(features['Tax_Compliance_Ratio'] - 1)
        
        available = [f for f in self.SELECTED_FEATURES if f in features.columns]
        result = features[available].fillna(0)
        
        return result
    
    def load_model(self):
        """Load pre-trained model"""
        try:
            if not os.path.exists(self.model_path):
                print(f"⚠️ Model not found at {self.model_path}")
                return False
            
            artifact = joblib.load(self.model_path)
            self.model = artifact['model']
            self.scaler = artifact['scaler']
            self.feature_names = artifact['feature_names']
            self.label_encoder = artifact['label_encoder']
            print(f"✅ Model loaded from {self.model_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def predict(self, company_data):
        """Predict behavior risk for a single company"""
        if self.model is None:
            raise ValueError("Model not loaded")
        
        df = pd.DataFrame([company_data])
        X = self.prepare_features(df)
        
        for feature in self.feature_names:
            if feature not in X.columns:
                X[feature] = 0
        
        X = X[self.feature_names]
        X_scaled = self.scaler.transform(X)
        
        proba = self.model.predict_proba(X_scaled)[0]
        pred_class = self.model.predict(X_scaled)[0]
        risk_level = self.label_encoder.inverse_transform([pred_class])[0]
        confidence = max(proba) * 100
        risk_score = proba[pred_class] * 100
        
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        risk_factors = []
        X_dict = X.iloc[0].to_dict()
        
        for i, feature in enumerate(self.feature_names):
            abs_deviation = abs(X_scaled[0][i])
            if abs_deviation > 0.5:
                value = company_data.get(feature)
                if value is None:
                    value = X_dict.get(feature, 0)
                risk_factors.append({
                    'feature': feature,
                    'value': float(value),
                    'importance': feature_importance[feature],
                    'deviation': round(abs_deviation, 4)
                })
        
        risk_factors.sort(key=lambda x: x['importance'], reverse=True)
        
        risk_probabilities = {}
        for i, prob in enumerate(proba):
            risk_probabilities[self.label_encoder.classes_[i]] = round(prob * 100, 2)
        
        return {
            'risk_level': risk_level,
            'confidence': confidence,
            'risk_score': risk_score,
            'risk_probabilities': risk_probabilities,
            'top_risk_factors': risk_factors[:5]
        }


@bp.route('/behavioral/check-model', methods=['GET'])
def check_behavioral_model():
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models', 'behavioral_model.pkl')
    if os.path.exists(model_path):
        return jsonify({'status': 'available', 'model_path': model_path, 'message': 'Model ready'}), 200
    return jsonify({'status': 'not_available', 'message': 'Model not found'}), 404


@bp.route('/behavioral/stats', methods=['GET'])
def get_behavioral_stats():
    try:
        behaviors = DetectedBehavior.query.all()
        stats = {
            'total_detections': len(behaviors),
            'by_type': {'High Risk': sum(1 for b in behaviors if b.behavior_type == 'High Risk'), 'Medium Risk': sum(1 for b in behaviors if b.behavior_type == 'Medium Risk'), 'Low Risk': sum(1 for b in behaviors if b.behavior_type == 'Low Risk')},
            'reviewed': sum(1 for b in behaviors if b.reviewed),
            'pending_review': sum(1 for b in behaviors if not b.reviewed),
            'avg_risk_score': sum(float(b.risk_score) for b in behaviors) / len(behaviors) if behaviors else 0
        }
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'total_detections': 0, 'by_type': {'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0}, 'reviewed': 0, 'pending_review': 0, 'avg_risk_score': 0}), 200


@bp.route('/behavioral/companies', methods=['GET'])
def get_behavioral_companies():
    try:
        companies = Taxpayer.query.all()
        result = [{'id': c.id, 'tin': c.tin, 'company_name': c.company_name, 'industry': c.industry, 'available_years': sorted([r.fiscal_year for r in c.returns]), 'latest_year': max([r.fiscal_year for r in c.returns]) if c.returns else None} for c in companies]
        return jsonify(result), 200
    except Exception as e:
        return jsonify([]), 500


@bp.route('/behavioral/analyze/<int:taxpayer_id>/<int:fiscal_year>', methods=['GET'])
def analyze_company_behavior(taxpayer_id, fiscal_year):
    """Analyze a specific company's behavior using pre-trained ML model with adjusted scoring"""
    try:
        taxpayer = Taxpayer.query.get_or_404(taxpayer_id)
        tax_return = TaxReturn.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).first()
        
        if not tax_return:
            return jsonify({'error': 'No tax return found'}), 404
        
        payments = Payment.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year).all()
        total_paid = sum(float(p.amount) for p in payments) if payments else 0
        late_filings = sum(1 for p in payments if p.status == 'Late')
        
        compliance_violations = ValidationIssue.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year, status='Open').count()
        behavioral_violations = BehavioralAlert.query.filter_by(taxpayer_id=taxpayer_id, fiscal_year=fiscal_year, status='New').count()
        total_violations = compliance_violations + behavioral_violations
        
        audit_count = AuditOutcome.query.filter_by(taxpayer_id=taxpayer_id).count()
        audit_findings = AuditOutcome.query.filter(AuditOutcome.taxpayer_id == taxpayer_id, AuditOutcome.outcome != 'Compliant').count()
        
        tax_paid = total_paid
        tax_liability = float(tax_return.tax_liability) if tax_return.tax_liability else 0
        tax_compliance_ratio = tax_paid / tax_liability if tax_liability > 0 else 0
        
        total_income = float(tax_return.total_income) if tax_return.total_income else 0
        accounting_profit = float(tax_return.accounting_profit) if tax_return.accounting_profit else 0
        expenses = total_income - accounting_profit
        
        company_data = {
            'Revenue': total_income,
            'Expenses': expenses,
            'Profit': accounting_profit,
            'Tax_Liability': tax_liability,
            'Tax_Paid': tax_paid,
            'Late_Filings': late_filings,
            'Compliance_Violations': total_violations,
            'Tax_Compliance_Ratio': tax_compliance_ratio,
            'Audit_Findings': audit_findings,
            'Audit_to_Tax_Ratio': audit_count / tax_liability if tax_liability > 0 else 0
        }
        
        print(f"\n=== Behavioral Analysis for {taxpayer.company_name} ({fiscal_year}) ===")
        print(f"Late Filings: {late_filings}")
        print(f"Compliance Violations: {total_violations}")
        print(f"Tax Compliance Ratio: {tax_compliance_ratio:.4f}")
        print(f"Tax Liability: ${tax_liability:,.2f}")
        print(f"Tax Paid: ${tax_paid:,.2f}")
        
        model = BehavioralRiskModel()
        if model.model is None:
            return jsonify({'error': 'Model not loaded. Please ensure model file exists.'}), 400
        
        prediction = model.predict(company_data)
        
        original_risk_score = prediction['risk_score']
        adjustment_multiplier = 1.0
        adjustment_factors = []
        
        if tax_compliance_ratio >= 0.98:
            adjustment_multiplier *= 0.3
            adjustment_factors.append("Full tax payment detected (98%+ compliance)")
        elif tax_compliance_ratio >= 0.95:
            adjustment_multiplier *= 0.5
            adjustment_factors.append("High tax payment detected (95%+ compliance)")
        elif tax_compliance_ratio >= 0.90:
            adjustment_multiplier *= 0.7
            adjustment_factors.append("Good tax payment detected (90%+ compliance)")
        
        if late_filings == 0:
            adjustment_multiplier *= 0.6
            adjustment_factors.append("No late filings detected")
        elif late_filings == 1:
            adjustment_multiplier *= 0.85
            adjustment_factors.append("Minor late filings (1 occurrence)")
        
        if total_violations == 0:
            adjustment_multiplier *= 0.7
            adjustment_factors.append("No compliance violations detected")
        elif total_violations <= 2:
            adjustment_multiplier *= 0.9
            adjustment_factors.append(f"Low violation count ({total_violations})")
        
        adjusted_risk_score = original_risk_score * adjustment_multiplier
        adjusted_risk_score = max(5, min(adjusted_risk_score, 95))
        
        if adjusted_risk_score >= 70:
            adjusted_risk_level = 'High Risk'
        elif adjusted_risk_score >= 40:
            adjusted_risk_level = 'Medium Risk'
        else:
            adjusted_risk_level = 'Low Risk'
        
        safe_score = 100 - adjusted_risk_score
        
        print(f"\n--- Risk Score Adjustment ---")
        print(f"Original Risk Score: {original_risk_score:.1f}%")
        print(f"Adjustment Multiplier: {adjustment_multiplier:.2f}")
        print(f"Adjusted Risk Score: {adjusted_risk_score:.1f}%")
        print(f"Adjusted Risk Level: {adjusted_risk_level}")
        print(f"Safe/Compliance Score: {safe_score:.1f}%")
        
        prediction['risk_score'] = adjusted_risk_score
        prediction['risk_level'] = adjusted_risk_level
        
        if adjusted_risk_level == 'Low Risk':
            prediction['risk_probabilities'] = {'High Risk': 5.0, 'Medium Risk': 15.0, 'Low Risk': 80.0}
        elif adjusted_risk_level == 'Medium Risk':
            prediction['risk_probabilities'] = {'High Risk': 25.0, 'Medium Risk': 55.0, 'Low Risk': 20.0}
        else:
            prediction['risk_probabilities'] = {'High Risk': 70.0, 'Medium Risk': 20.0, 'Low Risk': 10.0}
        
        detected = DetectedBehavior(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year,
            behavior_type=adjusted_risk_level,
            risk_score=Decimal(str(adjusted_risk_score)),
            confidence=Decimal(str(prediction['confidence'])),
            risk_factors=prediction['top_risk_factors'],
            predictions=prediction['risk_probabilities']
        )
        db.session.add(detected)
        db.session.commit()
        
        return jsonify({
            'taxpayer': taxpayer.to_dict(),
            'fiscal_year': fiscal_year,
            'financial_data': {
                'revenue': total_income,
                'expenses': expenses,
                'profit': accounting_profit,
                'tax_liability': tax_liability,
                'tax_paid': tax_paid,
                'tax_compliance_ratio': round(tax_compliance_ratio, 4),
                'late_filings': late_filings,
                'compliance_violations': total_violations
            },
            'behavioral_analysis': prediction,
            'adjustment_summary': {
                'original_risk_score': round(original_risk_score, 1),
                'adjusted_risk_score': round(adjusted_risk_score, 1),
                'safe_score': round(safe_score, 1),
                'adjustment_factors': adjustment_factors,
                'multiplier': round(adjustment_multiplier, 2)
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/behavioral/detections', methods=['GET'])
def get_detected_behaviors():
    try:
        behavior_type = request.args.get('behavior_type')
        reviewed = request.args.get('reviewed')
        query = DetectedBehavior.query
        if behavior_type:
            query = query.filter_by(behavior_type=behavior_type)
        if reviewed:
            query = query.filter_by(reviewed=reviewed == 'true')
        behaviors = query.order_by(DetectedBehavior.detected_at.desc()).all()
        return jsonify([b.to_dict() for b in behaviors]), 200
    except Exception as e:
        return jsonify([]), 500


@bp.route('/behavioral/detections/<int:detection_id>', methods=['GET'])
def get_behavior_detection_by_id(detection_id):
    try:
        detection = DetectedBehavior.query.get_or_404(detection_id)
        return jsonify(detection.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/behavioral/save/<int:behavior_id>', methods=['PUT'])
def save_behavior_notes(behavior_id):
    try:
        data = request.get_json()
        behavior = DetectedBehavior.query.get_or_404(behavior_id)
        behavior.notes = data.get('notes', behavior.notes)
        behavior.reviewed = data.get('reviewed', True)
        db.session.commit()
        return jsonify({'message': 'Behavior saved', 'behavior': behavior.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/behavioral/clear-detections', methods=['DELETE'])
def clear_detections():
    try:
        count = DetectedBehavior.query.delete()
        db.session.commit()
        return jsonify({'message': f'Cleared {count} detected behaviors'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== HELPER FUNCTIONS ====================

def generate_risk_summary_report(fiscal_year):
    scores = GovernanceRiskScores.query.filter_by(fiscal_year=fiscal_year).all()
    taxpayers = Taxpayer.query.count()
    high_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) >= 70)
    medium_risk = sum(1 for s in scores if s.governance_risk_score and 40 <= float(s.governance_risk_score) < 70)
    low_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) < 40)
    return {'fiscal_year': fiscal_year, 'total_taxpayers': taxpayers, 'high_risk_count': high_risk, 'medium_risk_count': medium_risk, 'low_risk_count': low_risk, 'compliance_rate': round((low_risk / taxpayers * 100) if taxpayers > 0 else 0, 1)}


def generate_validation_report(fiscal_year):
    issues = ValidationIssue.query.filter_by(fiscal_year=fiscal_year).all()
    return {
        'fiscal_year': fiscal_year,
        'total_issues': len(issues),
        'open_issues': sum(1 for i in issues if i.status == 'Open'),
        'resolved_issues': sum(1 for i in issues if i.status == 'Resolved'),
        'by_severity': {'high': sum(1 for i in issues if i.severity == 'High'), 'medium': sum(1 for i in issues if i.severity == 'Medium'), 'low': sum(1 for i in issues if i.severity == 'Low')}
    }


def generate_behavioral_report(fiscal_year):
    alerts = BehavioralAlert.query.filter_by(fiscal_year=fiscal_year).all()
    return {
        'fiscal_year': fiscal_year,
        'total_alerts': len(alerts),
        'by_type': {'under_declaration': sum(1 for a in alerts if 'Under' in a.alert_type), 'delayed_payment': sum(1 for a in alerts if 'Delayed' in a.alert_type), 'unusual_pattern': sum(1 for a in alerts if 'Unusual' in a.alert_type)},
        'by_severity': {'high': sum(1 for a in alerts if a.severity == 'High'), 'medium': sum(1 for a in alerts if a.severity == 'Medium'), 'low': sum(1 for a in alerts if a.severity == 'Low')}
    }


def generate_etr_report(fiscal_year):
    alerts = ETRAlert.query.filter_by(fiscal_year=fiscal_year).all()
    return {
        'fiscal_year': fiscal_year,
        'total_alerts': len(alerts),
        'by_type': {'high_risk_aggressive': sum(1 for a in alerts if 'HIGH_RISK' in a.alert_type), 'uncertain': sum(1 for a in alerts if 'UNCERTAIN' in a.alert_type), 'high_etr': sum(1 for a in alerts if 'HIGH_ETR' in a.alert_type)}
    }


def generate_audit_report(fiscal_year):
    audits = AuditOutcome.query.filter(db.extract('year', AuditOutcome.audit_date) == fiscal_year).all()
    return {
        'fiscal_year': fiscal_year,
        'total_audits': len(audits),
        'by_outcome': {'compliant': sum(1 for a in audits if a.outcome == 'Compliant'), 'non_compliant': sum(1 for a in audits if a.outcome == 'Non-Compliant'), 'under_declaration': sum(1 for a in audits if a.outcome == 'Under-Declaration')},
        'total_additional_assessment': sum(float(a.additional_assessment or 0) for a in audits),
        'total_penalties': sum(float(a.penalties or 0) for a in audits)
    }


@bp.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'status': 'Governance blueprint is working!'}), 200