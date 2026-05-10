#!/usr/bin/env python
"""
Simplified training script for governance risk model
This script doesn't require database connection
"""

import sys
import os
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only what we need
from blueprints.governance.ml.feature_engineering import prepare_features
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report

def generate_synthetic_training_data(n_samples=2000):
    """Generate synthetic training data"""
    print(f"Generating {n_samples} synthetic training samples...")
    np.random.seed(42)
    
    data = []
    for _ in range(n_samples):
        board_size = np.random.randint(3, 15)
        independence_ratio = np.random.uniform(0, 100)
        expertise_score = np.random.uniform(0, 100)
        diversity_index = np.random.uniform(0, 50)
        ceo_duality = np.random.choice([True, False], p=[0.4, 0.6])
        
        # Calculate risk based on governance factors
        risk_score = 0
        if independence_ratio < 30:
            risk_score += 40
        elif independence_ratio < 50:
            risk_score += 20
        if expertise_score < 20:
            risk_score += 30
        elif expertise_score < 40:
            risk_score += 15
        if diversity_index < 10:
            risk_score += 20
        if ceo_duality:
            risk_score += 10
        
        tax_risk_flag = 1 if risk_score > 50 else 0
        
        data.append({
            'board_size': board_size,
            'independence_ratio': independence_ratio,
            'expertise_score': expertise_score,
            'diversity_index': diversity_index,
            'ceo_duality': int(ceo_duality),
            'tax_risk_flag': tax_risk_flag
        })
    
    df = pd.DataFrame(data)
    print(f"Dataset created with {len(df)} samples")
    print(f"Class distribution:\n{df['tax_risk_flag'].value_counts()}")
    return df

def train_model():
    """Train the governance risk model"""
    print("=" * 60)
    print("GOVERNANCE RISK MODEL TRAINING")
    print("=" * 60)
    
    # Generate data
    df = generate_synthetic_training_data(2000)
    
    # Prepare features
    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING")
    print("=" * 60)
    X = prepare_features(df)
    y = df['tax_risk_flag']
    feature_names = X.columns.tolist()
    
    print(f"\nFeatures created: {len(feature_names)}")
    for i, feature in enumerate(feature_names, 1):
        print(f"  {i}. {feature}")
    
    # Split data
    print("\n" + "=" * 60)
    print("MODEL TRAINING")
    print("=" * 60)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    
    print("\nTraining Random Forest classifier...")
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    print("\n" + "=" * 60)
    print("MODEL EVALUATION")
    print("=" * 60)
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    roc_auc = roc_auc_score(y_test, y_proba)
    print(f"\nROC-AUC Score: {roc_auc:.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Low Risk', 'High Risk']))
    
    # Feature importance
    print("\n" + "=" * 60)
    print("FEATURE IMPORTANCE")
    print("=" * 60)
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for i, row in importance_df.head(10).iterrows():
        print(f"  {row['feature']:<30}: {row['importance']:.4f}")
    
    # Save model
    print("\n" + "=" * 60)
    print("SAVING MODEL")
    print("=" * 60)
    
    # Create models directory
    models_dir = Path(__file__).parent / 'blueprints' / 'governance' / 'ml' / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = models_dir / 'governance_risk_model.pkl'
    scaler_path = models_dir / 'governance_scaler.pkl'
    features_path = models_dir / 'governance_features.pkl'
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    joblib.dump(feature_names, features_path)
    
    print(f"✓ Model saved to: {model_path}")
    print(f"✓ Scaler saved to: {scaler_path}")
    print(f"✓ Features saved to: {features_path}")
    
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE!")
    print("=" * 60)
    
    return model, scaler, feature_names, roc_auc

if __name__ == "__main__":
    train_model()