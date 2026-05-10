"""
Machine Learning Model for Behavioral Analytics
Predicts tax compliance behaviors based on financial and governance patterns
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import joblib
import os
from pathlib import Path

class BehavioralRiskModel:
    """
    ML Model to detect risky tax behaviors
    """
    
    def __init__(self, model_path=None):
        if model_path is None:
            # Get the absolute path to the models directory
            current_dir = Path(__file__).parent
            self.model_path = str(current_dir / 'models' / 'behavioral_model.pkl')
        else:
            self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.label_encoder = None
        
    def prepare_features(self, df):
        """
        Prepare features from raw data
        """
        features = df.copy()
        
        # Ensure all required columns exist
        required_columns = ['Revenue', 'Expenses', 'Profit', 'Tax_Liability', 'Tax_Paid',
                           'Late_Filings', 'Compliance_Violations', 'Tax_Compliance_Ratio',
                           'Audit_Findings', 'Audit_to_Tax_Ratio']
        
        for col in required_columns:
            if col not in features.columns:
                features[col] = 0
        
        # Financial ratios
        features['profit_margin'] = features['Profit'] / (features['Revenue'] + 1)
        features['tax_burden'] = features['Tax_Liability'] / (features['Revenue'] + 1)
        features['expense_ratio'] = features['Expenses'] / (features['Revenue'] + 1)
        features['payment_gap'] = (features['Tax_Liability'] - features['Tax_Paid']) / (features['Tax_Liability'] + 1)
        
        # Compliance metrics
        features['compliance_score'] = features['Tax_Compliance_Ratio']
        features['late_filing_penalty'] = features['Late_Filings'] * 0.1
        features['violation_penalty'] = features['Compliance_Violations'] * 0.15
        
        # Audit risk indicators
        features['audit_risk'] = features['Audit_Findings'] / (features['Audit_to_Tax_Ratio'] + 1)
        features['tax_avoidance_index'] = abs(features['Tax_Compliance_Ratio'] - 1)
        
        # Selected features
        selected_features = [
            'profit_margin', 'tax_burden', 'expense_ratio', 'payment_gap',
            'compliance_score', 'late_filing_penalty', 'violation_penalty',
            'audit_risk', 'tax_avoidance_index', 'Late_Filings', 
            'Compliance_Violations', 'Audit_Findings'
        ]
        
        # Ensure all features exist
        available_features = [f for f in selected_features if f in features.columns]
        
        return features[available_features].fillna(0)
    
    def train(self, data_path):
        """
        Train the behavioral risk model using CSV data
        """
        print("=" * 60)
        print("Training Behavioral Risk Model")
        print("=" * 60)
        
        # Check if file exists
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Training data not found at: {data_path}")
        
        # Load data
        df = pd.read_csv(data_path)
        print(f"Loaded {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
        
        # Prepare features
        X = self.prepare_features(df)
        self.feature_names = X.columns.tolist()
        print(f"\nFeatures created: {self.feature_names}")
        
        # Target variable (Risk_Label)
        if 'Risk_Label' not in df.columns:
            raise ValueError("Risk_Label column not found in dataset")
        
        y = df['Risk_Label']
        
        # Encode target
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)
        
        print(f"\nTarget classes: {self.label_encoder.classes_.tolist()}")
        print(f"Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train Random Forest model
        print("\nTraining Random Forest Classifier...")
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1
        )
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)
        
        print("\n" + "=" * 60)
        print("Model Evaluation")
        print("=" * 60)
        print(classification_report(y_test, y_pred, target_names=self.label_encoder.classes_))
        
        # Calculate accuracy
        accuracy = (y_pred == y_test).mean()
        print(f"\nAccuracy: {accuracy:.4f}")
        
        # Calculate ROC AUC (for binary or multi-class)
        try:
            if len(self.label_encoder.classes_) == 2:
                auc = roc_auc_score(y_test, y_proba[:, 1])
                print(f"ROC AUC: {auc:.4f}")
        except:
            pass
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        print(f"\nCross-validation scores: {cv_scores}")
        print(f"Mean CV score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        
        # Feature importance
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Feature Importances:")
        for i, row in importance_df.head(10).iterrows():
            print(f"  {row['feature']:<25}: {row['importance']:.4f}")
        
        # Save model
        self.save_model()
        
        return {
            'accuracy': accuracy,
            'feature_importance': importance_df.to_dict('records'),
            'classes': self.label_encoder.classes_.tolist(),
            'cv_score_mean': cv_scores.mean(),
            'cv_score_std': cv_scores.std()
        }
    
    def predict_behavior(self, company_data):
        """
        Predict behavior risk for a single company
        """
        if self.model is None:
            if not self.load_model():
                raise ValueError("Model not loaded. Please train the model first.")
        
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
        risk_proba = self.model.predict_proba(X_scaled)[0]
        risk_class = self.model.predict(X_scaled)[0]
        
        # Get risk level
        risk_level = self.label_encoder.inverse_transform([risk_class])[0]
        
        # Calculate confidence
        confidence = max(risk_proba) * 100
        
        # Get top risk factors
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        # Identify which features contribute to risk
        risk_factors = []
        for i, feature in enumerate(self.feature_names):
            abs_deviation = abs(X_scaled[0][i])
            if abs_deviation > 0.5:  # More than 0.5 standard deviation from mean
                risk_factors.append({
                    'feature': feature,
                    'value': float(company_data.get(feature, 0)),
                    'importance': feature_importance[feature],
                    'deviation': abs_deviation
                })
        
        risk_factors.sort(key=lambda x: x['importance'], reverse=True)
        
        return {
            'risk_level': risk_level,
            'confidence': confidence,
            'risk_score': risk_proba[risk_class] * 100,
            'risk_probabilities': {
                self.label_encoder.classes_[i]: prob 
                for i, prob in enumerate(risk_proba)
            },
            'top_risk_factors': risk_factors[:5]
        }
    
    def save_model(self):
        """Save model and scaler to disk"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'label_encoder': self.label_encoder
        }, self.model_path)
        
        print(f"\n✅ Model saved to {self.model_path}")
    
    def load_model(self):
        """Load saved model"""
        try:
            if os.path.exists(self.model_path):
                data = joblib.load(self.model_path)
                self.model = data['model']
                self.scaler = data['scaler']
                self.feature_names = data['feature_names']
                self.label_encoder = data['label_encoder']
                print(f"✅ Model loaded from {self.model_path}")
                return True
            else:
                print(f"⚠️ Model file not found at {self.model_path}")
                return False
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False