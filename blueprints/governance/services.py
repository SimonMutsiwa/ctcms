"""
Service layer for governance operations
"""
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

# Import db from main app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from __init__ import db

# Import models
from blueprints.governance.models import (
    GovernanceRaw, GovernanceIndicators, GovernanceRiskScores
)

# Import ML feature engineering
from blueprints.governance.ml import feature_engineering

class GovernanceService:
    """Service class for governance data operations"""
    
    _model = None
    _scaler = None
    
    @classmethod
    def load_ml_models(cls):
        """Load ML models from ml folder"""
        if cls._model is None:
            try:
                # Get the directory of the current file
                current_dir = Path(__file__).parent
                model_path = current_dir / 'ml' / 'models' / 'governance_risk_model.pkl'
                scaler_path = current_dir / 'ml' / 'models' / 'governance_scaler.pkl'
                
                if model_path.exists() and scaler_path.exists():
                    cls._model = joblib.load(str(model_path))
                    cls._scaler = joblib.load(str(scaler_path))
                    print(f"✅ Models loaded from {model_path}")
                else:
                    print(f"⚠️ Model files not found at {model_path}")
                    print("   Run python train_independent.py to train the model first")
                    cls._model = None
                    cls._scaler = None
            except Exception as e:
                print(f"❌ Error loading models: {e}")
                cls._model = None
                cls._scaler = None
        return cls._model, cls._scaler
    
    @staticmethod
    def store_raw(data):
        """Store raw governance data"""
        raw = GovernanceRaw(
            taxpayer_id=data['taxpayer_id'],
            fiscal_year=data['fiscal_year'],
            board_size=data.get('board_size'),
            independent_directors=data.get('independent_directors'),
            financial_experts=data.get('financial_experts'),
            female_directors=data.get('female_directors'),
            ceo_duality=data.get('ceo_duality', False),
            source=data.get('source', 'TaRMS')
        )
        db.session.add(raw)
        db.session.commit()
        return raw.id
    
    @staticmethod
    def compute_indicators(raw_data):
        """Convert raw data to standardized indicators"""
        board_size = raw_data.get('board_size', 0)
        
        independence_ratio = (raw_data.get('independent_directors', 0) / board_size * 100) if board_size > 0 else 0
        expertise_score = (raw_data.get('financial_experts', 0) / board_size * 100) if board_size > 0 else 0
        diversity_index = (raw_data.get('female_directors', 0) / board_size * 100) if board_size > 0 else 0
        
        return {
            'board_size': board_size,
            'independence_ratio': round(independence_ratio, 2),
            'expertise_score': round(expertise_score, 2),
            'diversity_index': round(diversity_index, 2),
            'ceo_duality': raw_data.get('ceo_duality', False)
        }
    
    @staticmethod
    def save_indicators(taxpayer_id, fiscal_year, indicators):
        """Save computed indicators to database"""
        record = GovernanceIndicators.query.get((taxpayer_id, fiscal_year))
        if record:
            for key, value in indicators.items():
                setattr(record, key, value)
        else:
            record = GovernanceIndicators(
                taxpayer_id=taxpayer_id,
                fiscal_year=fiscal_year,
                **indicators
            )
            db.session.add(record)
        db.session.commit()
    
    @staticmethod
    def get_indicators(taxpayer_id, fiscal_year):
        """Retrieve governance indicators"""
        record = GovernanceIndicators.query.get((taxpayer_id, fiscal_year))
        if record:
            return {
                'board_size': record.board_size,
                'independence_ratio': float(record.independence_ratio) if record.independence_ratio else 0,
                'expertise_score': float(record.expertise_score) if record.expertise_score else 0,
                'diversity_index': float(record.diversity_index) if record.diversity_index else 0,
                'ceo_duality': record.ceo_duality
            }
        return None
    
    @staticmethod
    def get_raw(taxpayer_id, fiscal_year):
        """Retrieve raw governance data"""
        record = GovernanceRaw.query.filter_by(
            taxpayer_id=taxpayer_id,
            fiscal_year=fiscal_year
        ).first()
        
        if record:
            return {
                'board_size': record.board_size,
                'independent_directors': record.independent_directors,
                'financial_experts': record.financial_experts,
                'female_directors': record.female_directors,
                'ceo_duality': record.ceo_duality
            }
        return None
    
    @staticmethod
    def compute_risk_score(taxpayer_id, fiscal_year):
        """Compute governance risk score using ML model"""
        indicators = GovernanceService.get_indicators(taxpayer_id, fiscal_year)
        if not indicators:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame([indicators])
        features_df = feature_engineering.prepare_features(df)
        
        model, scaler = GovernanceService.load_ml_models()
        if model is None or scaler is None:
            risk_score = GovernanceService._rule_based_risk_score(indicators)
            GovernanceService.save_risk_score(taxpayer_id, fiscal_year, risk_score)
            return risk_score
        
        features_scaled = scaler.transform(features_df)
        prob_high_risk = model.predict_proba(features_scaled)[0][1]
        risk_score = prob_high_risk * 100
        
        GovernanceService.save_risk_score(taxpayer_id, fiscal_year, risk_score, prob_high_risk)
        
        return risk_score
    
    @staticmethod
    def _rule_based_risk_score(indicators):
        """Fallback rule-based scoring"""
        score = 0
        
        if indicators['independence_ratio'] < 30:
            score += 40
        elif indicators['independence_ratio'] < 50:
            score += 20
        elif indicators['independence_ratio'] < 70:
            score += 10
        
        if indicators['expertise_score'] < 20:
            score += 30
        elif indicators['expertise_score'] < 40:
            score += 15
        
        if indicators['diversity_index'] < 10:
            score += 20
        elif indicators['diversity_index'] < 25:
            score += 10
        
        if indicators['ceo_duality']:
            score += 10
        
        return min(score, 100)
    
    @staticmethod
    def save_risk_score(taxpayer_id, fiscal_year, risk_score, probability=None, factors=None):
        """Save risk score to database"""
        record = GovernanceRiskScores.query.get((taxpayer_id, fiscal_year))
        if record:
            record.governance_risk_score = risk_score
            record.risk_probability = probability
            record.risk_factors = factors
        else:
            record = GovernanceRiskScores(
                taxpayer_id=taxpayer_id,
                fiscal_year=fiscal_year,
                governance_risk_score=risk_score,
                risk_probability=probability,
                risk_factors=factors,
                model_version='v1.0'
            )
            db.session.add(record)
        db.session.commit()
    
    @staticmethod
    def get_risk_score(taxpayer_id, fiscal_year):
        """Retrieve existing risk score"""
        record = GovernanceRiskScores.query.get((taxpayer_id, fiscal_year))
        if record:
            return float(record.governance_risk_score)
        return None