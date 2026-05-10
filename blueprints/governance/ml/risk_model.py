"""
ML Model for governance risk prediction
"""

import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import os
import logging

logger = logging.getLogger(__name__)

class GovernanceRiskModel:
    """ML model for predicting governance-related tax risk"""
    
    def __init__(self, model_dir='blueprints/governance/ml/models'):
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, 'governance_risk_model.pkl')
        self.scaler_path = os.path.join(model_dir, 'governance_scaler.pkl')
        self.features_path = os.path.join(model_dir, 'governance_features.pkl')
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
    
    def train(self, X, y, feature_names):
        """
        Train the risk prediction model
        
        Args:
            X: Feature matrix (DataFrame or numpy array)
            y: Target labels (1 = high risk, 0 = low risk)
            feature_names: List of feature names
        
        Returns:
            dict: Training metrics
        """
        self.feature_names = feature_names
        
        # Convert to numpy if DataFrame
        if hasattr(X, 'values'):
            X = X.values
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1
        )
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)[:, 1]
        
        roc_auc = roc_auc_score(y_test, y_proba)
        
        # Feature importance
        feature_importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_.tolist()
        ))
        
        metrics = {
            'roc_auc': roc_auc,
            'feature_importance': feature_importance,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'class_distribution': {
                '0': int((y_train == 0).sum()),
                '1': int((y_train == 1).sum())
            }
        }
        
        logger.info(f"Model trained with ROC-AUC: {roc_auc:.4f}")
        logger.info(f"Feature importance: {feature_importance}")
        
        return metrics
    
    def predict(self, X):
        """Predict risk probability for new data"""
        if self.model is None or self.scaler is None:
            raise ValueError("Model not trained. Call train() first or load saved model.")
        
        # Convert to numpy if DataFrame
        if hasattr(X, 'values'):
            X = X.values
        
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[:, 1]
        return proba
    
    def predict_batch(self, X, threshold=0.5):
        """Predict risk class for batch data"""
        probabilities = self.predict(X)
        predictions = (probabilities >= threshold).astype(int)
        return predictions, probabilities
    
    def save(self):
        """Save model and scaler to disk"""
        if self.model is None or self.scaler is None:
            raise ValueError("No model to save. Train first.")
        
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        joblib.dump(self.feature_names, self.features_path)
        
        logger.info(f"Model saved to {self.model_path}")
        logger.info(f"Scaler saved to {self.scaler_path}")
        logger.info(f"Features saved to {self.features_path}")
    
    def load(self):
        """Load saved model and scaler"""
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            self.feature_names = joblib.load(self.features_path)
            logger.info("Model loaded successfully")
            return True
        except FileNotFoundError as e:
            logger.warning(f"Model files not found: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def get_feature_importance(self):
        """Get feature importance as DataFrame"""
        if self.model is None:
            return None
        
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance_df