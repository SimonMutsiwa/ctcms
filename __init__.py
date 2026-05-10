"""
Forensic - Corporate Tax Compliance Monitoring System (CTCMS)
"""

from flask import Flask, render_template, jsonify, send_from_directory, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import os
from datetime import timedelta
import secrets

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_object=None):
    """Application factory pattern"""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Create instance directory
    instance_path = os.path.join(os.path.dirname(__file__), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
        print(f"📁 Created instance directory: {instance_path}")
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(instance_path, 'forensic.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = True
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['REMEMBER_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    
    print(f"🗄️  Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, supports_credentials=True)
    
    # Register blueprints
    try:
        from blueprints.governance import bp as governance_bp
        app.register_blueprint(governance_bp)
        print("✅ Governance blueprint registered")
    except Exception as e:
        print(f"⚠️ Could not register governance blueprint: {e}")
        import traceback
        traceback.print_exc()
    
    # ==================== PAGE ROUTES ====================
    
    @app.route('/')
    def index():
        """Main UI page"""
        return render_template('index.html')
    
    @app.route('/login')
    def login_page():
        """Login page"""
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        """Logout endpoint - clears session and redirects to login"""
        # Create response that redirects to login
        response = redirect(url_for('login_page'))
        # Delete the session cookie
        response.delete_cookie('session_token')
        return response

    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files"""
        return send_from_directory('static', filename)
    
    # ==================== API ENDPOINTS ====================
    
    @app.route('/api/v1/governance/risk-summary', methods=['GET'])
    def get_risk_summary():
        """Get risk summary for dashboard"""
        try:
            from blueprints.governance.models import GovernanceRiskScores
            
            scores = GovernanceRiskScores.query.all()
            
            low_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) < 40)
            medium_risk = sum(1 for s in scores if s.governance_risk_score and 40 <= float(s.governance_risk_score) < 70)
            high_risk = sum(1 for s in scores if s.governance_risk_score and float(s.governance_risk_score) >= 70)
            
            return jsonify({
                'low_risk': low_risk,
                'medium_risk': medium_risk,
                'high_risk': high_risk
            }), 200
        except Exception as e:
            return jsonify({'low_risk': 0, 'medium_risk': 0, 'high_risk': 0}), 200
    
    @app.route('/api/v1/governance/recent-assessments', methods=['GET'])
    def get_recent_assessments():
        """Get recent assessments for dashboard"""
        try:
            from blueprints.governance.models import GovernanceRiskScores, Taxpayer
            
            scores = GovernanceRiskScores.query.order_by(
                GovernanceRiskScores.computed_at.desc()
            ).limit(10).all()
            
            assessments = []
            for score in scores:
                risk_score = float(score.governance_risk_score) if score.governance_risk_score else 0
                if risk_score >= 70:
                    risk_level = 'High Risk'
                elif risk_score >= 40:
                    risk_level = 'Medium Risk'
                else:
                    risk_level = 'Low Risk'
                
                taxpayer = Taxpayer.query.get(score.taxpayer_id)
                assessments.append({
                    'taxpayer_id': score.taxpayer_id,
                    'company_name': taxpayer.company_name if taxpayer else f'Company {score.taxpayer_id}',
                    'risk_score': f'{risk_score:.1f}',
                    'risk_level': risk_level,
                    'last_assessment': score.computed_at.strftime('%Y-%m-%d') if score.computed_at else 'N/A'
                })
            
            return jsonify(assessments), 200
        except Exception as e:
            return jsonify([]), 200
    
    
    @app.route('/api/v1/user/info', methods=['GET'])
    def get_user_info():
        """Get current user information (simplified for frontend)"""
        # Return demo user info since authentication is handled by frontend
        return jsonify({
            'id': 1,
            'username': 'admin',
            'email': 'admin@zimra.gov.zw',
            'full_name': 'System Administrator',
            'role': 'admin',
            'permissions': {
                'can_view_all': True,
                'can_edit': True,
                'can_delete': True,
                'can_manage_users': True,
                'can_train_models': True,
                'can_export': True
            }
        }), 200
        
    @app.route('/api/v1/governance/recent-alerts', methods=['GET'])
    def get_recent_alerts():
        """Get recent alerts for dashboard"""
        try:
            from blueprints.governance.models import BehavioralAlert, ValidationIssue, Taxpayer
            
            alerts = []
            
            # Get recent behavioral alerts
            behavioral = BehavioralAlert.query.order_by(
                BehavioralAlert.created_at.desc()
            ).limit(3).all()
            
            for alert in behavioral:
                taxpayer = Taxpayer.query.get(alert.taxpayer_id)
                alerts.append({
                    'taxpayer_id': alert.taxpayer_id,
                    'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                    'message': alert.description[:100] if alert.description else alert.alert_type,
                    'level': alert.severity.lower() if alert.severity else 'info',
                    'created_at': alert.created_at.strftime('%Y-%m-%d') if alert.created_at else 'N/A',
                    'type': 'behavioral'
                })
            
            # Get recent validation issues
            validations = ValidationIssue.query.order_by(
                ValidationIssue.created_at.desc()
            ).limit(2).all()
            
            for issue in validations:
                taxpayer = Taxpayer.query.get(issue.taxpayer_id)
                alerts.append({
                    'taxpayer_id': issue.taxpayer_id,
                    'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                    'message': issue.description[:100] if issue.description else issue.issue_type,
                    'level': issue.severity.lower() if issue.severity else 'info',
                    'created_at': issue.created_at.strftime('%Y-%m-%d') if issue.created_at else 'N/A',
                    'type': 'validation'
                })
            
            return jsonify(alerts[:5]), 200
        except Exception as e:
            return jsonify([]), 200
    
    @app.route('/api/v1/governance/risk-history', methods=['GET'])
    def get_risk_history():
        """Get risk score history for all taxpayers"""
        try:
            from blueprints.governance.models import GovernanceRiskScores, Taxpayer
            
            scores = GovernanceRiskScores.query.order_by(
                GovernanceRiskScores.computed_at.desc()
            ).limit(50).all()
            
            history = []
            for score in scores:
                risk_score = float(score.governance_risk_score) if score.governance_risk_score else 0
                if risk_score >= 70:
                    risk_category = 'High Risk'
                elif risk_score >= 40:
                    risk_category = 'Medium Risk'
                else:
                    risk_category = 'Low Risk'
                
                taxpayer = Taxpayer.query.get(score.taxpayer_id)
                history.append({
                    'taxpayer_id': score.taxpayer_id,
                    'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                    'fiscal_year': score.fiscal_year,
                    'governance_risk_score': f'{risk_score:.1f}',
                    'risk_category': risk_category
                })
            
            return jsonify(history), 200
        except Exception as e:
            return jsonify([]), 200
    
    @app.route('/api/v1/audit/cases', methods=['GET'])
    def get_audit_cases():
        """Get audit cases"""
        try:
            from blueprints.governance.models import AuditOutcome, Taxpayer
            
            audits = AuditOutcome.query.order_by(
                AuditOutcome.audit_date.desc()
            ).limit(20).all()
            
            cases = []
            for audit in audits:
                taxpayer = Taxpayer.query.get(audit.taxpayer_id)
                cases.append({
                    'id': audit.id,
                    'case_id': f'AUDIT-{audit.id:04d}',
                    'taxpayer_id': audit.taxpayer_id,
                    'taxpayer_name': taxpayer.company_name if taxpayer else 'Unknown',
                    'audit_date': audit.audit_date.strftime('%Y-%m-%d') if audit.audit_date else 'N/A',
                    'findings': audit.findings[:100] if audit.findings else 'No findings',
                    'additional_assessment': float(audit.additional_assessment) if audit.additional_assessment else 0,
                    'penalties': float(audit.penalties) if audit.penalties else 0,
                    'outcome': audit.outcome,
                    'status': 'Closed' if audit.outcome != 'Compliant' else 'Resolved',
                    'recommendation': audit.recommendation
                })
            
            return jsonify(cases), 200
        except Exception as e:
            return jsonify([]), 200
    
    # ==================== HEALTH CHECK ====================
    
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy', 
            'service': 'CTCMS - Governance Module',
            'database': 'SQLite'
        }, 200
    
    return app