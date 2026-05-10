#!/usr/bin/env python
"""
Completely independent training script for governance risk model
No Flask or database dependencies
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report, confusion_matrix

def prepare_features(df):
    """
    Prepare features for ML model from governance indicators
    This is a copy of the feature engineering function to avoid imports
    """
    features = df.copy()
    
    # Handle missing values
    features = features.fillna({
        'board_size': 0,
        'independence_ratio': 0,
        'expertise_score': 0,
        'diversity_index': 0,
        'ceo_duality': False
    })
    
    # Create derived features
    features['board_size_squared'] = features['board_size'] ** 2
    features['indep_expert_interaction'] = features['independence_ratio'] * features['expertise_score']
    features['board_diversity_product'] = features['board_size'] * features['diversity_index']
    features['independence_normalized'] = features['independence_ratio'] / 100
    features['expertise_normalized'] = features['expertise_score'] / 100
    features['diversity_normalized'] = features['diversity_index'] / 100
    
    # Final feature set
    final_features = [
        'board_size', 'independence_ratio', 'expertise_score', 'diversity_index',
        'ceo_duality', 'board_size_squared', 'indep_expert_interaction',
        'board_diversity_product', 'independence_normalized',
        'expertise_normalized', 'diversity_normalized'
    ]
    
    # Select only existing columns
    existing_features = [f for f in final_features if f in features.columns]
    
    return features[existing_features]

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
        
        # Calculate risk based on governance factors (rule-based for synthetic data)
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
    print(f"\nClass distribution:")
    print(df['tax_risk_flag'].value_counts())
    print(f"  Low Risk (0): {(df['tax_risk_flag'] == 0).sum()}")
    print(f"  High Risk (1): {(df['tax_risk_flag'] == 1).sum()}")
    
    return df

def train_model():
    """Train the governance risk model"""
    print("=" * 70)
    print(" " * 20 + "GOVERNANCE RISK MODEL TRAINING")
    print("=" * 70)
    
    # Generate data
    df = generate_synthetic_training_data(2000)
    
    # Prepare features
    print("\n" + "=" * 70)
    print("FEATURE ENGINEERING")
    print("=" * 70)
    X = prepare_features(df)
    y = df['tax_risk_flag']
    feature_names = X.columns.tolist()
    
    print(f"\nFeatures created: {len(feature_names)}")
    for i, feature in enumerate(feature_names, 1):
        print(f"  {i:2d}. {feature}")
    
    # Split data
    print("\n" + "=" * 70)
    print("MODEL TRAINING")
    print("=" * 70)
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
    print("\n" + "=" * 70)
    print("MODEL EVALUATION")
    print("=" * 70)
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    roc_auc = roc_auc_score(y_test, y_proba)
    print(f"\nROC-AUC Score: {roc_auc:.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Low Risk', 'High Risk']))
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(f"  True Negatives: {cm[0][0]}")
    print(f"  False Positives: {cm[0][1]}")
    print(f"  False Negatives: {cm[1][0]}")
    print(f"  True Positives: {cm[1][1]}")
    
    # Feature importance
    print("\n" + "=" * 70)
    print("FEATURE IMPORTANCE")
    print("=" * 70)
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for i, row in importance_df.head(10).iterrows():
        bar = "█" * int(row['importance'] * 50)
        print(f"  {row['feature']:<30}: {row['importance']:.4f} {bar}")
    
    # Save model
    print("\n" + "=" * 70)
    print("SAVING MODEL")
    print("=" * 70)
    
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
    
    # Also save as joblib files
    print("\n" + "=" * 70)
    print("MODEL SUMMARY")
    print("=" * 70)
    print(f"Model Type: Random Forest Classifier")
    print(f"Number of Trees: {model.n_estimators}")
    print(f"Max Depth: {model.max_depth}")
    print(f"Number of Features: {len(feature_names)}")
    print(f"ROC-AUC Score: {roc_auc:.4f}")
    
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE! 🎉")
    print("=" * 70)
    
    return model, scaler, feature_names, roc_auc

if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        import traceback
        traceback.print_exc()