"""
Database models for governance module with calculation methods
"""

from datetime import datetime
import sys
import os
from decimal import Decimal
import math

import joblib
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from __init__ import db

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# ==================== GOVERNANCE MODELS (Original) ====================

class GovernanceRaw(db.Model):
    """Raw governance data from TaRMS and external sources"""
    __tablename__ = 'governance_raw'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    taxpayer_id = db.Column(db.Integer, nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    
    # Board attributes
    board_size = db.Column(db.Integer)
    independent_directors = db.Column(db.Integer)
    financial_experts = db.Column(db.Integer)
    female_directors = db.Column(db.Integer)
    ceo_duality = db.Column(db.Boolean)
    
    # Metadata
    source = db.Column(db.String(50))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('taxpayer_id', 'fiscal_year', name='unique_taxpayer_year'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'fiscal_year': self.fiscal_year,
            'board_size': self.board_size,
            'independent_directors': self.independent_directors,
            'financial_experts': self.financial_experts,
            'female_directors': self.female_directors,
            'ceo_duality': self.ceo_duality,
            'source': self.source,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None
        }


class GovernanceIndicators(db.Model):
    """Standardized governance indicators for analysis"""
    __tablename__ = 'governance_indicators'
    
    taxpayer_id = db.Column(db.Integer, primary_key=True, nullable=False)
    fiscal_year = db.Column(db.Integer, primary_key=True, nullable=False)
    
    board_size = db.Column(db.Integer)
    independence_ratio = db.Column(db.Numeric(5, 2))
    expertise_score = db.Column(db.Numeric(5, 2))
    diversity_index = db.Column(db.Numeric(5, 2))
    ceo_duality = db.Column(db.Boolean)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'taxpayer_id': self.taxpayer_id,
            'fiscal_year': self.fiscal_year,
            'board_size': self.board_size,
            'independence_ratio': float(self.independence_ratio) if self.independence_ratio else None,
            'expertise_score': float(self.expertise_score) if self.expertise_score else None,
            'diversity_index': float(self.diversity_index) if self.diversity_index else None,
            'ceo_duality': self.ceo_duality,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class GovernanceRiskScores(db.Model):
    """Governance risk scores with multi-factor calculation"""
    __tablename__ = 'governance_risk_scores'
    
    taxpayer_id = db.Column(db.Integer, primary_key=True, nullable=False)
    fiscal_year = db.Column(db.Integer, primary_key=True, nullable=False)
    governance_risk_score = db.Column(db.Numeric(5, 2))
    risk_probability = db.Column(db.Numeric(5, 4))
    risk_factors = db.Column(db.JSON)
    model_version = db.Column(db.String(20))
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'taxpayer_id': self.taxpayer_id,
            'fiscal_year': self.fiscal_year,
            'governance_risk_score': float(self.governance_risk_score) if self.governance_risk_score else None,
            'risk_probability': float(self.risk_probability) if self.risk_probability else None,
            'risk_factors': self.risk_factors,
            'model_version': self.model_version,
            'computed_at': self.computed_at.isoformat() if self.computed_at else None
        }
    
    @staticmethod
    def calculate_risk_score(taxpayer_id, fiscal_year):
        """
        Calculate comprehensive risk score based on 7 risk categories:
        1. Filing Compliance Risk
        2. Payment Compliance Risk
        3. Financial Reporting Risk
        4. Audit Risk
        5. Governance Risk
        6. Behavioral Risk
        7. ETR Risk
        """
        
        # Get tax return data
        tax_return = TaxReturn.query.filter_by(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year
        ).first()
        
        if not tax_return:
            return 50, {}, 0.5
        
        # Get payments
        payments = Payment.query.filter_by(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year
        ).all()
        
        # Get governance indicators
        governance = GovernanceIndicators.query.get((taxpayer_id, fiscal_year))
        
        # Get validation and behavioral issues
        validation_issues = ValidationIssue.query.filter_by(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year,
            status='Open'
        ).all()
        
        behavioral_alerts = BehavioralAlert.query.filter_by(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year,
            status='New'
        ).all()
        
        # Get audit history
        audits = AuditOutcome.query.filter_by(
            taxpayer_id=taxpayer_id
        ).all()
        
        # Calculate individual risk scores (0-100 scale, higher = more risk)
        # ================================================================
        
        risk_score = 0
        risk_factors = {}
        
        # ===== 1. FILING COMPLIANCE RISK (0-15 points) =====
        filing_risk = 0
        filing_risk_reasons = []
        
        # Check for late or missing filings
        if tax_return.filing_date:
            due_date = datetime(tax_return.fiscal_year, 4, 30)  # April 30 deadline
            if tax_return.filing_date > due_date:
                late_days = (tax_return.filing_date - due_date).days
                if late_days > 30:
                    filing_risk += 10
                    filing_risk_reasons.append(f"Filing {late_days} days late")
                elif late_days > 0:
                    filing_risk += 5
                    filing_risk_reasons.append(f"Filing {late_days} days late")
        
        # Check for incomplete filings (validation issues related to filing)
        filing_issues = [i for i in validation_issues if 'filing' in i.issue_type.lower() or 'return' in i.issue_type.lower()]
        if filing_issues:
            filing_risk += min(len(filing_issues) * 3, 10)
            filing_risk_reasons.append(f"{len(filing_issues)} filing-related validation issues")
        
        risk_score += filing_risk
        risk_factors['filing_compliance'] = {
            'score': filing_risk,
            'max_score': 15,
            'reasons': filing_risk_reasons
        }
        
        # ===== 2. PAYMENT COMPLIANCE RISK (0-20 points) =====
        payment_risk = 0
        payment_risk_reasons = []
        
        if payments:
            late_payments = [p for p in payments if p.status == 'Late']
            late_count = len(late_payments)
            
            if late_count > 0:
                late_percentage = late_count / len(payments) * 100
                if late_percentage > 50:
                    payment_risk += 12
                    payment_risk_reasons.append(f"{late_count} of {len(payments)} payments late (persistent)")
                elif late_percentage > 25:
                    payment_risk += 8
                    payment_risk_reasons.append(f"{late_count} of {len(payments)} payments late (frequent)")
                else:
                    payment_risk += 4
                    payment_risk_reasons.append(f"{late_count} late payment(s)")
            
            # Check for underpayment
            total_paid = sum(float(p.amount) for p in payments)
            tax_liability = float(tax_return.tax_liability) if tax_return.tax_liability else 0
            
            if tax_liability > 0:
                payment_ratio = total_paid / tax_liability
                if payment_ratio < 0.8:
                    payment_risk += 8
                    payment_risk_reasons.append(f"Underpayment: paid only {payment_ratio*100:.0f}% of liability")
                elif payment_ratio < 0.95:
                    payment_risk += 4
                    payment_risk_reasons.append(f"Minor underpayment: paid {payment_ratio*100:.0f}% of liability")
        
        risk_score += payment_risk
        risk_factors['payment_compliance'] = {
            'score': payment_risk,
            'max_score': 20,
            'reasons': payment_risk_reasons
        }
        
        # ===== 3. FINANCIAL REPORTING RISK (0-15 points) =====
        reporting_risk = 0
        reporting_risk_reasons = []
        
        # Calculate book-tax difference
        accounting_profit = float(tax_return.accounting_profit) if tax_return.accounting_profit else 0
        taxable_income = float(tax_return.taxable_income) if tax_return.taxable_income else 0
        
        if accounting_profit > 0:
            book_tax_ratio = taxable_income / accounting_profit
            if book_tax_ratio < 0.7:
                reporting_risk += 8
                reporting_risk_reasons.append(f"Large book-tax difference: taxable income only {book_tax_ratio*100:.0f}% of accounting profit")
            elif book_tax_ratio < 0.85:
                reporting_risk += 4
                reporting_risk_reasons.append(f"Moderate book-tax difference: {book_tax_ratio*100:.0f}% of accounting profit")
        
        # Check for unusual expense claims
        expense_ratio = float(tax_return.total_income - accounting_profit) / float(tax_return.total_income) if tax_return.total_income > 0 else 0
        if expense_ratio > 0.9:
            reporting_risk += 5
            reporting_risk_reasons.append(f"Unusually high expense ratio: {expense_ratio*100:.0f}%")
        
        # Check validation issues related to financial reporting
        reporting_validation = [i for i in validation_issues if 'expense' in i.issue_type.lower() or 'income' in i.issue_type.lower() or 'deduction' in i.issue_type.lower()]
        if reporting_validation:
            reporting_risk += min(len(reporting_validation) * 2, 5)
            reporting_risk_reasons.append(f"{len(reporting_validation)} financial reporting issues")
        
        risk_score += reporting_risk
        risk_factors['financial_reporting'] = {
            'score': reporting_risk,
            'max_score': 15,
            'reasons': reporting_risk_reasons
        }
        
        # ===== 4. AUDIT RISK (0-10 points) =====
        audit_risk = 0
        audit_risk_reasons = []
        
        non_compliant_audits = [a for a in audits if a.outcome != 'Compliant']
        if non_compliant_audits:
            audit_risk += min(len(non_compliant_audits) * 5, 10)
            audit_risk_reasons.append(f"{len(non_compliant_audits)} non-compliant audit(s)")
            total_penalties = sum(float(a.penalties or 0) for a in non_compliant_audits)
            if total_penalties > 0:
                audit_risk_reasons.append(f"Total penalties: ${total_penalties:,.2f}")
        
        risk_score += audit_risk
        risk_factors['audit'] = {
            'score': audit_risk,
            'max_score': 10,
            'reasons': audit_risk_reasons
        }
        
        # ===== 5. GOVERNANCE RISK (0-15 points) =====
        governance_risk = 0
        governance_risk_reasons = []
        
        if governance:
            # Board independence (low independence = higher risk)
            independence = governance.independence_ratio or 0
            if independence < 30:
                governance_risk += 6
                governance_risk_reasons.append(f"Low board independence: {independence:.1f}% (recommended ≥30%)")
            elif independence < 50:
                governance_risk += 3
                governance_risk_reasons.append(f"Moderate board independence: {independence:.1f}% (optimal ≥50%)")
            
            # Financial expertise (low expertise = higher risk)
            expertise = governance.expertise_score or 0
            if expertise < 20:
                governance_risk += 5
                governance_risk_reasons.append(f"Insufficient financial expertise: {expertise:.1f}% (recommended ≥20%)")
            elif expertise < 40:
                governance_risk += 2
                governance_risk_reasons.append(f"Limited financial expertise: {expertise:.1f}% (optimal ≥40%)")
            
            # Gender diversity (low diversity = higher risk)
            diversity = governance.diversity_index or 0
            if diversity < 10:
                governance_risk += 4
                governance_risk_reasons.append(f"Low gender diversity: {diversity:.1f}% female representation")
            elif diversity < 25:
                governance_risk += 2
                governance_risk_reasons.append(f"Moderate gender diversity: {diversity:.1f}% female representation")
        
        risk_score += governance_risk
        risk_factors['governance'] = {
            'score': governance_risk,
            'max_score': 15,
            'reasons': governance_risk_reasons
        }
        
        # ===== 6. BEHAVIORAL RISK (0-15 points) =====
        behavioral_risk = 0
        behavioral_risk_reasons = []
        
        # Analyze historical payment patterns (last 3 years)
        historical_payments = Payment.query.filter(
            Payment.taxpayer_id == taxpayer_id,
            Payment.fiscal_year < fiscal_year
        ).order_by(Payment.fiscal_year.desc()).limit(12).all()
        
        if len(historical_payments) >= 8:
            historical_late = [p for p in historical_payments if p.status == 'Late']
            if len(historical_late) > len(historical_payments) * 0.3:
                behavioral_risk += 5
                behavioral_risk_reasons.append("Persistent late payment pattern over multiple years")
        
        # Check for recurring under-declaration
        historical_returns = TaxReturn.query.filter(
            TaxReturn.taxpayer_id == taxpayer_id,
            TaxReturn.fiscal_year < fiscal_year
        ).order_by(TaxReturn.fiscal_year.desc()).limit(3).all()
        
        low_etr_count = 0
        for hr in historical_returns:
            if hr.accounting_profit and hr.accounting_profit > 0:
                hr_etr = float(hr.tax_liability) / float(hr.accounting_profit) * 100
                if hr_etr < 15:
                    low_etr_count += 1
        
        if low_etr_count >= 2:
            behavioral_risk += 5
            behavioral_risk_reasons.append(f"Recurring low ETR pattern ({low_etr_count} of last 3 years)")
        
        # Check for sudden changes in behavior
        if behavioral_alerts:
            behavioral_risk += min(len(behavioral_alerts) * 2, 5)
            alert_types = ', '.join(set(b.alert_type for b in behavioral_alerts[:3]))
            behavioral_risk_reasons.append(f"{len(behavioral_alerts)} behavioral alert(s): {alert_types}")
        
        risk_score += behavioral_risk
        risk_factors['behavioral'] = {
            'score': behavioral_risk,
            'max_score': 15,
            'reasons': behavioral_risk_reasons
        }
        
        # ===== 7. EFFECTIVE TAX RATE (ETR) RISK (0-10 points) =====
        etr_risk = 0
        etr_risk_reasons = []
        
        if accounting_profit > 0:
            actual_etr = (float(tax_return.tax_liability) / accounting_profit) * 100
            statutory_rate = 25.0
            
            if actual_etr < 15:
                etr_risk += 8
                etr_risk_reasons.append(f"Exceptionally low ETR: {actual_etr:.1f}% (statutory: {statutory_rate:.0f}%)")
            elif actual_etr < 19:
                etr_risk += 5
                etr_risk_reasons.append(f"Low ETR: {actual_etr:.1f}% below statutory rate")
            elif actual_etr > 30:
                etr_risk += 2
                etr_risk_reasons.append(f"High ETR: {actual_etr:.1f}% above statutory rate")
            
            # Industry benchmark comparison
            industry_benchmark = taxpayer.get_industry_benchmark() if hasattr(taxpayer, 'get_industry_benchmark') else {"expected_etr": 0.20}
            industry_expected = industry_benchmark.get('expected_etr', 0.20) * 100
            industry_variance = actual_etr - industry_expected
            if abs(industry_variance) > 10:
                etr_risk += 2
                etr_risk_reasons.append(f"Significant deviation from industry average ({industry_expected:.1f}%)")
        
        risk_score += etr_risk
        risk_factors['etr'] = {
            'score': etr_risk,
            'max_score': 10,
            'reasons': etr_risk_reasons
        }
        
        # Final risk score (0-100, higher = more risk)
        final_risk_score = min(risk_score, 100)
        risk_probability = final_risk_score / 100
        
        return final_risk_score, risk_factors, risk_probability
    
    
    

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='viewer')  # admin, auditor, compliance, viewer
    full_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role):
        """Check if user has a specific role"""
        roles_hierarchy = {
            'admin': ['admin', 'auditor', 'compliance', 'viewer'],
            'auditor': ['auditor', 'compliance', 'viewer'],
            'compliance': ['compliance', 'viewer'],
            'viewer': ['viewer']
        }
        return role in roles_hierarchy.get(self.role, [])
    
    def has_permission(self, permission):
        """Check if user has a specific permission"""
        permissions = {
            'admin': ['view_all', 'edit_all', 'delete_all', 'manage_users', 'train_models'],
            'auditor': ['view_all', 'edit_audit_cases', 'view_reports', 'export_data'],
            'compliance': ['view_all', 'edit_compliance', 'view_reports', 'generate_reports'],
            'viewer': ['view_dashboard', 'view_reports']
        }
        return permission in permissions.get(self.role, [])
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserSession(db.Model):
    """Track user sessions and activity"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(200), unique=True)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(300))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'login_time': self.login_time.isoformat() if self.login_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }


class AuditLog(db.Model):
    """Audit log for user actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100))
    resource = db.Column(db.String(100))
    resource_id = db.Column(db.String(100))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        user = User.query.get(self.user_id)
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': user.username if user else 'Unknown',
            'action': self.action,
            'resource': self.resource,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


# ==================== TAXPAYER MODELS ====================
class DetectedBehavior(db.Model):
    """Detected behaviors from ML model"""
    __tablename__ = 'detected_behaviors'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    behavior_type = db.Column(db.String(100))  # High Risk, Medium Risk, Low Risk
    risk_score = db.Column(db.Numeric(5, 2))
    confidence = db.Column(db.Numeric(5, 2))
    risk_factors = db.Column(db.JSON)  # Store top risk factors
    predictions = db.Column(db.JSON)  # Store all risk probabilities
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        taxpayer = Taxpayer.query.get(self.taxpayer_id)
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
            'fiscal_year': self.fiscal_year,
            'behavior_type': self.behavior_type,
            'risk_score': float(self.risk_score) if self.risk_score else 0,
            'confidence': float(self.confidence) if self.confidence else 0,
            'risk_factors': self.risk_factors,
            'predictions': self.predictions,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'reviewed': self.reviewed,
            'notes': self.notes
        }


class Taxpayer(db.Model):
    """Taxpayer information"""
    __tablename__ = 'taxpayers'
    
    id = db.Column(db.Integer, primary_key=True)
    tin = db.Column(db.String(50), unique=True, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    industry = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Active')
    
    # Relationships
    returns = db.relationship('TaxReturn', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    audits = db.relationship('AuditOutcome', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    validations = db.relationship('ValidationIssue', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    behavioral_alerts = db.relationship('BehavioralAlert', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    etr_alerts = db.relationship('ETRAlert', backref='taxpayer', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'tin': self.tin,
            'company_name': self.company_name,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'industry': self.industry,
            'status': self.status
        }
    
    def get_industry_benchmark(self):
        """Get industry benchmark for tax compliance"""
        benchmarks = {
            "Manufacturing": {"expected_etr": 0.22, "payment_ratio": 0.95},
            "Banking & Finance": {"expected_etr": 0.28, "payment_ratio": 0.98},
            "Telecommunications": {"expected_etr": 0.25, "payment_ratio": 0.97},
            "Retail": {"expected_etr": 0.20, "payment_ratio": 0.92},
            "Agriculture": {"expected_etr": 0.15, "payment_ratio": 0.88},
            "Mining": {"expected_etr": 0.30, "payment_ratio": 0.96},
            "Construction": {"expected_etr": 0.18, "payment_ratio": 0.85},
            "Hospitality": {"expected_etr": 0.19, "payment_ratio": 0.90},
            "Transport": {"expected_etr": 0.21, "payment_ratio": 0.89},
            "Technology": {"expected_etr": 0.23, "payment_ratio": 0.94},
            "Healthcare": {"expected_etr": 0.17, "payment_ratio": 0.91},
            "Education": {"expected_etr": 0.12, "payment_ratio": 0.87},
            "Real Estate": {"expected_etr": 0.24, "payment_ratio": 0.93},
            "Energy": {"expected_etr": 0.26, "payment_ratio": 0.95}
        }
        return benchmarks.get(self.industry, {"expected_etr": 0.20, "payment_ratio": 0.90})


class TaxReturn(db.Model):
    """Corporate tax returns with calculation methods"""
    __tablename__ = 'tax_returns'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    filing_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_income = db.Column(db.Numeric(15, 2))
    taxable_income = db.Column(db.Numeric(15, 2))
    tax_liability = db.Column(db.Numeric(15, 2))
    accounting_profit = db.Column(db.Numeric(15, 2))
    status = db.Column(db.String(20), default='Filed')
    
    __table_args__ = (db.UniqueConstraint('taxpayer_id', 'fiscal_year', name='unique_return'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'fiscal_year': self.fiscal_year,
            'filing_date': self.filing_date.isoformat() if self.filing_date else None,
            'total_income': float(self.total_income) if self.total_income else 0,
            'taxable_income': float(self.taxable_income) if self.taxable_income else 0,
            'tax_liability': float(self.tax_liability) if self.tax_liability else 0,
            'accounting_profit': float(self.accounting_profit) if self.accounting_profit else 0,
            'status': self.status
        }
    
    def calculate_etr(self):
        """Calculate Effective Tax Rate"""
        if self.accounting_profit and self.accounting_profit > 0:
            return float(self.tax_liability) / float(self.accounting_profit)
        return 0.0


class Payment(db.Model):
    """Payment history with calculation methods"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Numeric(15, 2))
    payment_type = db.Column(db.String(50))
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'fiscal_year': self.fiscal_year,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount) if self.amount else 0,
            'payment_type': self.payment_type,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status
        }
    
    def calculate_late_days(self):
        """Calculate number of days late"""
        if self.due_date and self.payment_date:
            if self.payment_date > self.due_date:
                return (self.payment_date - self.due_date).days
        return 0
    
    def is_late(self):
        """Check if payment is late"""
        return self.payment_date > self.due_date if self.due_date else False
    
    
    
    def calculate_penalty(self):
        """Calculate penalty for late payment"""
        late_days = self.calculate_late_days()
        if late_days > 0:
            annual_rate = 0.10
            daily_rate = annual_rate / 365
            penalty = float(self.amount) * daily_rate * late_days
            return penalty
        return 0.0


class AuditOutcome(db.Model):
    """Previous audit outcomes"""
    __tablename__ = 'audit_outcomes'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    audit_date = db.Column(db.DateTime, default=datetime.utcnow)
    findings = db.Column(db.Text)
    additional_assessment = db.Column(db.Numeric(15, 2), default=0)
    penalties = db.Column(db.Numeric(15, 2), default=0)
    outcome = db.Column(db.String(50))
    recommendation = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'audit_date': self.audit_date.isoformat() if self.audit_date else None,
            'findings': self.findings,
            'additional_assessment': float(self.additional_assessment) if self.additional_assessment else 0,
            'penalties': float(self.penalties) if self.penalties else 0,
            'outcome': self.outcome,
            'recommendation': self.recommendation
        }


class ValidationIssue(db.Model):
    """Validation issues with formula-based generation"""
    __tablename__ = 'validation_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    issue_type = db.Column(db.String(100))
    severity = db.Column(db.String(20))
    description = db.Column(db.Text)
    field_name = db.Column(db.String(100))
    expected_value = db.Column(db.String(200))
    actual_value = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    def to_dict(self):
        taxpayer = Taxpayer.query.get(self.taxpayer_id)
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
            'fiscal_year': self.fiscal_year,
            'issue_type': self.issue_type,
            'severity': self.severity,
            'description': self.description,
            'field_name': self.field_name,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def validate_tax_return(tax_return, governance_indicators):
        """Generate validation issues based on multiple risk factors"""
        issues = []
        
        if not tax_return:
            return issues
        
        # ===== 1. FILING COMPLIANCE ISSUES =====
        if tax_return.filing_date:
            due_date = datetime(tax_return.fiscal_year, 4, 30)
            if tax_return.filing_date > due_date:
                late_days = (tax_return.filing_date - due_date).days
                severity = 'High' if late_days > 30 else 'Medium'
                issues.append({
                    'issue_type': 'Late Filing',
                    'severity': severity,
                    'description': f'Tax return filed {late_days} days after the 30 April deadline',
                    'field_name': 'filing_date',
                    'expected_value': f'On or before {due_date.strftime("%Y-%m-%d")}',
                    'actual_value': tax_return.filing_date.strftime('%Y-%m-%d')
                })
        
        # ===== 2. FINANCIAL REPORTING ISSUES =====
        # Check tax-to-income ratio
        if tax_return.total_income and tax_return.tax_liability:
            tax_ratio = float(tax_return.tax_liability) / float(tax_return.total_income)
            expected_ratio = 0.25
            
            if tax_ratio < 0.15:
                issues.append({
                    'issue_type': 'Low Tax Burden',
                    'severity': 'High',
                    'description': f'Tax-to-income ratio ({tax_ratio:.1%}) is significantly below expected ({expected_ratio:.0%})',
                    'field_name': 'tax_liability',
                    'expected_value': f'~{expected_ratio:.0%} of income',
                    'actual_value': f'{tax_ratio:.1%}'
                })
            elif tax_ratio > 0.35:
                issues.append({
                    'issue_type': 'High Tax Burden',
                    'severity': 'Medium',
                    'description': f'Tax-to-income ratio ({tax_ratio:.1%}) is above expected ({expected_ratio:.0%})',
                    'field_name': 'tax_liability',
                    'expected_value': f'~{expected_ratio:.0%} of income',
                    'actual_value': f'{tax_ratio:.1%}'
                })
        
        # Check profit margin consistency
        if tax_return.total_income and tax_return.accounting_profit:
            profit_margin = float(tax_return.accounting_profit) / float(tax_return.total_income)
            
            if profit_margin > 0.40:
                issues.append({
                    'issue_type': 'Excessive Profit Margin',
                    'severity': 'High',
                    'description': f'Profit margin ({profit_margin:.1%}) is unusually high compared to industry norms',
                    'field_name': 'accounting_profit',
                    'expected_value': '≤40%',
                    'actual_value': f'{profit_margin:.1%}'
                })
            elif profit_margin < 0.05 and tax_return.total_income > 1000000:
                issues.append({
                    'issue_type': 'Low Profit Margin',
                    'severity': 'Medium',
                    'description': f'Profit margin ({profit_margin:.1%}) is unusually low for revenue level',
                    'field_name': 'accounting_profit',
                    'expected_value': '≥5%',
                    'actual_value': f'{profit_margin:.1%}'
                })
        
        # Check book-tax difference
        if tax_return.accounting_profit and tax_return.taxable_income:
            accounting_profit = float(tax_return.accounting_profit)
            taxable_income = float(tax_return.taxable_income)
            if accounting_profit > 0:
                btd_ratio = taxable_income / accounting_profit
                if btd_ratio < 0.7:
                    issues.append({
                        'issue_type': 'Large Book-Tax Difference',
                        'severity': 'High',
                        'description': f'Taxable income is only {btd_ratio*100:.0f}% of accounting profit, suggesting significant permanent differences',
                        'field_name': 'taxable_income',
                        'expected_value': f'≥70% of accounting profit',
                        'actual_value': f'{btd_ratio*100:.0f}%'
                    })
                elif btd_ratio < 0.85:
                    issues.append({
                        'issue_type': 'Moderate Book-Tax Difference',
                        'severity': 'Medium',
                        'description': f'Taxable income is {btd_ratio*100:.0f}% of accounting profit, requiring review',
                        'field_name': 'taxable_income',
                        'expected_value': f'≥85% of accounting profit',
                        'actual_value': f'{btd_ratio*100:.0f}%'
                    })
        
        # ===== 3. GOVERNANCE ISSUES (excluding CEO duality) =====
        if governance_indicators:
            # Board independence issue
            if governance_indicators.independence_ratio and governance_indicators.independence_ratio < 30:
                issues.append({
                    'issue_type': 'Low Board Independence',
                    'severity': 'High',
                    'description': f'Board independence ratio of {governance_indicators.independence_ratio:.1f}% is below recommended 30% threshold',
                    'field_name': 'independence_ratio',
                    'expected_value': '≥30%',
                    'actual_value': f"{governance_indicators.independence_ratio:.1f}%"
                })
            elif governance_indicators.independence_ratio and governance_indicators.independence_ratio < 50:
                issues.append({
                    'issue_type': 'Moderate Board Independence',
                    'severity': 'Medium',
                    'description': f'Board independence ratio of {governance_indicators.independence_ratio:.1f}% is below optimal 50%',
                    'field_name': 'independence_ratio',
                    'expected_value': '≥50%',
                    'actual_value': f"{governance_indicators.independence_ratio:.1f}%"
                })
            
            # Financial expertise issue
            if governance_indicators.expertise_score and governance_indicators.expertise_score < 20:
                issues.append({
                    'issue_type': 'Insufficient Financial Expertise',
                    'severity': 'High',
                    'description': f'Only {governance_indicators.expertise_score:.1f}% of board members have financial/accounting expertise',
                    'field_name': 'financial_experts',
                    'expected_value': '≥20%',
                    'actual_value': f"{governance_indicators.expertise_score:.1f}%"
                })
            elif governance_indicators.expertise_score and governance_indicators.expertise_score < 40:
                issues.append({
                    'issue_type': 'Limited Financial Expertise',
                    'severity': 'Medium',
                    'description': f'Only {governance_indicators.expertise_score:.1f}% of board has financial expertise (optimal ≥40%)',
                    'field_name': 'financial_experts',
                    'expected_value': '≥40%',
                    'actual_value': f"{governance_indicators.expertise_score:.1f}%"
                })
            
            # Gender diversity issue
            if governance_indicators.diversity_index and governance_indicators.diversity_index < 10:
                issues.append({
                    'issue_type': 'Lack of Gender Diversity',
                    'severity': 'Medium',
                    'description': f'Only {governance_indicators.diversity_index:.1f}% female representation on board',
                    'field_name': 'female_directors',
                    'expected_value': '≥10%',
                    'actual_value': f"{governance_indicators.diversity_index:.1f}%"
                })
            
            # Board size issues
            if governance_indicators.board_size and governance_indicators.board_size < 5:
                issues.append({
                    'issue_type': 'Board Size Too Small',
                    'severity': 'Medium',
                    'description': f'Board size of {governance_indicators.board_size} is below recommended minimum for effective oversight',
                    'field_name': 'board_size',
                    'expected_value': '≥5',
                    'actual_value': str(governance_indicators.board_size)
                })
            elif governance_indicators.board_size and governance_indicators.board_size > 15:
                issues.append({
                    'issue_type': 'Board Size Too Large',
                    'severity': 'Low',
                    'description': f'Board size of {governance_indicators.board_size} may hinder efficient decision-making',
                    'field_name': 'board_size',
                    'expected_value': '≤15',
                    'actual_value': str(governance_indicators.board_size)
                })
        
        return issues

class BehavioralAlert(db.Model):
    """Behavioral analytics alerts with formula-based detection"""
    __tablename__ = 'behavioral_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    alert_type = db.Column(db.String(100))
    severity = db.Column(db.String(20))
    description = db.Column(db.Text)
    confidence_score = db.Column(db.Numeric(5, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='New')
    
    def to_dict(self):
        taxpayer = Taxpayer.query.get(self.taxpayer_id)
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
            'fiscal_year': self.fiscal_year,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'description': self.description,
            'confidence_score': float(self.confidence_score) if self.confidence_score else 0,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def analyze_payment_behavior(payments, tax_return):
        """Analyze payment behavior and generate alerts"""
        alerts = []
        
        if not payments:
            return alerts
        
        # Formula 1: Late payment frequency
        late_payments = [p for p in payments if p.is_late()]
        if late_payments:
            late_percentage = len(late_payments) / len(payments) * 100
            avg_late_days = sum(p.calculate_late_days() for p in late_payments) / len(late_payments)
            
            if late_percentage > 50:
                confidence = 0.85
                severity = 'High'
                description = f'Persistent late payments: {len(late_payments)} of {len(payments)} payments late (avg {avg_late_days:.0f} days)'
            elif late_percentage > 25:
                confidence = 0.65
                severity = 'Medium'
                description = f'Frequent late payments: {len(late_payments)} of {len(payments)} payments late'
            else:
                confidence = 0.40
                severity = 'Low'
                description = f'Occasional late payments detected'
            
            alerts.append({
                'alert_type': 'Delayed Payment Pattern',
                'severity': severity,
                'description': description,
                'confidence_score': confidence
            })
        
        # Formula 2: Underpayment detection
        if tax_return and tax_return.tax_liability:
            total_paid = sum(float(p.amount) for p in payments)
            expected_payment = float(tax_return.tax_liability)
            
            if total_paid < expected_payment * 0.8:
                underpayment = expected_payment - total_paid
                alerts.append({
                    'alert_type': 'Significant Underpayment',
                    'severity': 'High',
                    'description': f'Total payments (${total_paid:,.0f}) are {underpayment:,.0f} ({(1 - total_paid/expected_payment)*100:.0f}%) below expected liability',
                    'confidence_score': 0.90
                })
            elif total_paid < expected_payment * 0.95:
                underpayment = expected_payment - total_paid
                alerts.append({
                    'alert_type': 'Minor Underpayment',
                    'severity': 'Medium',
                    'description': f'Payment shortfall of ${underpayment:,.0f} detected',
                    'confidence_score': 0.65
                })
        
        return alerts
    
# Define the same feature engineering class as in your notebook
class BehavioralRiskModel:
    """ML Model to detect risky tax behaviors - Prediction only"""
    
    REQUIRED_COLUMNS = [
        'Revenue', 'Expenses', 'Profit', 'Tax_Liability', 'Tax_Paid',
        'Late_Filings', 'Compliance_Violations', 'Tax_Compliance_Ratio',
        'Audit_Findings', 'Audit_to_Tax_Ratio'
    ]
    
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
        """Engineer features from raw data - same as training"""
        features = df.copy()
        
        for col in self.REQUIRED_COLUMNS:
            if col not in features.columns:
                features[col] = 0
        
        features['profit_margin'] = features['Profit'] / (features['Revenue'] + 1)
        features['tax_burden'] = features['Tax_Liability'] / (features['Revenue'] + 1)
        features['expense_ratio'] = features['Expenses'] / (features['Revenue'] + 1)
        features['payment_gap'] = (features['Tax_Liability'] - features['Tax_Paid']) / (features['Tax_Liability'] + 1)
        features['compliance_score'] = features['Tax_Compliance_Ratio']
        features['late_filing_penalty'] = features['Late_Filings'] * 0.1
        features['violation_penalty'] = features['Compliance_Violations'] * 0.15
        features['audit_risk'] = features['Audit_Findings'] / (features['Audit_to_Tax_Ratio'] + 1)
        features['tax_avoidance_index'] = abs(features['Tax_Compliance_Ratio'] - 1)
        
        available = [f for f in self.SELECTED_FEATURES if f in features.columns]
        return features[available].fillna(0)
    
    def load_model(self):
        """Load pre-trained model"""
        try:
            if not os.path.exists(self.model_path):
                print(f"Model not found at {self.model_path}. Please train first using the notebook.")
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
            raise ValueError("Model not loaded. Please ensure model exists at: " + self.model_path)
        
        # Prepare features
        df = pd.DataFrame([company_data])
        X = self.prepare_features(df)
        
        # Ensure all features exist
        for feature in self.feature_names:
            if feature not in X.columns:
                X[feature] = 0
        X = X[self.feature_names]
        
        # Scale
        X_scaled = self.scaler.transform(X)
        
        # Predict
        proba = self.model.predict_proba(X_scaled)[0]
        pred_class = self.model.predict(X_scaled)[0]
        risk_level = self.label_encoder.inverse_transform([pred_class])[0]
        confidence = max(proba) * 100
        
        # Get top risk factors
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        risk_factors = []
        for i, feature in enumerate(self.feature_names):
            abs_deviation = abs(X_scaled[0][i])
            if abs_deviation > 0.5:  # More than 0.5 standard deviation from mean
                risk_factors.append({
                    'feature': feature,
                    'value': float(company_data.get(feature, X.iloc[0][i])),
                    'importance': feature_importance[feature],
                    'deviation': round(abs_deviation, 4)
                })
        
        risk_factors.sort(key=lambda x: x['importance'], reverse=True)
        
        return {
            'risk_level': risk_level,
            'confidence': round(confidence, 2),
            'risk_score': proba[pred_class] * 100,
            'risk_probabilities': {
                self.label_encoder.classes_[i]: round(p * 100, 2) 
                for i, p in enumerate(proba)
            },
            'top_risk_factors': risk_factors[:5]
        }



class ETRAlert(db.Model):
    """Effective Tax Rate alerts with formula-based calculation"""
    __tablename__ = 'etr_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    taxpayer_id = db.Column(db.Integer, db.ForeignKey('taxpayers.id'), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    computed_etr = db.Column(db.Numeric(5, 2))
    statutory_rate = db.Column(db.Numeric(5, 2))
    variance = db.Column(db.Numeric(5, 2))
    alert_type = db.Column(db.String(50))
    severity = db.Column(db.String(20))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='New')
    
    def to_dict(self):
        taxpayer = Taxpayer.query.get(self.taxpayer_id)
        return {
            'id': self.id,
            'taxpayer_id': self.taxpayer_id,
            'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
            'fiscal_year': self.fiscal_year,
            'computed_etr': float(self.computed_etr) if self.computed_etr else 0,
            'statutory_rate': float(self.statutory_rate) if self.statutory_rate else 25,
            'variance': float(self.variance) if self.variance else 0,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def calculate_etr_alert(tax_return, governance_indicators, industry_benchmark):
        """Calculate ETR and determine if alert is needed"""
        
        if not tax_return or not tax_return.accounting_profit or tax_return.accounting_profit <= 0:
            return None
        
        # Formula 1: Calculate ETR
        etr = float(tax_return.tax_liability) / float(tax_return.accounting_profit)
        statutory_rate = 0.25
        variance = etr - statutory_rate
        
        # Formula 2: Get industry benchmark
        expected_etr = industry_benchmark.get('expected_etr', 0.20)
        industry_variance = etr - expected_etr
        
        # Determine alert based on multiple factors
        alert_type = None
        severity = None
        description = None
        
        # Formula 3: High risk aggressive avoidance
        if etr < statutory_rate * 0.6:
            severity = 'High'
            alert_type = 'HIGH_RISK_AGGRESSIVE_AVOIDANCE'
            description = f'ETR of {etr:.1%} is exceptionally low (only {etr/statutory_rate:.0%} of statutory rate)'
            
            if governance_indicators and governance_indicators.independence_ratio and governance_indicators.independence_ratio < 30:
                description += '. Weak board independence increases risk of aggressive tax planning.'
        
        # Formula 4: Medium risk - uncertain
        elif etr < statutory_rate * 0.8:
            severity = 'Medium'
            alert_type = 'LOW_ETR_UNCERTAIN'
            description = f'ETR of {etr:.1%} is below statutory rate of {statutory_rate:.0%}'
            
            if industry_variance < -0.05:
                description += f' Also {abs(industry_variance):.1%} below industry average of {expected_etr:.1%}.'
        
        # Formula 5: High ETR - possible overpayment
        elif etr > statutory_rate * 1.2:
            severity = 'Low'
            alert_type = 'HIGH_ETR'
            description = f'ETR of {etr:.1%} is above statutory rate, suggesting possible overpayment'
        
        if alert_type:
            return {
                'computed_etr': etr * 100,
                'statutory_rate': statutory_rate * 100,
                'variance': variance * 100,
                'alert_type': alert_type,
                'severity': severity,
                'description': description
            }
        
        return None


class ComplianceReport(db.Model):
    """Generated compliance reports"""
    __tablename__ = 'compliance_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(50))
    fiscal_year = db.Column(db.Integer)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    data = db.Column(db.JSON)
    file_path = db.Column(db.String(500))
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_type': self.report_type,
            'fiscal_year': self.fiscal_year,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'file_path': self.file_path
        }