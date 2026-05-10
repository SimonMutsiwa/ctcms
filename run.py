#!/usr/bin/env python
"""
Application entry point for CTCMS
"""

import os
import sys
from flask.cli import FlaskGroup

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the correct modules
from __init__ import create_app, db
from config import config

# Get environment
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(config[env])

@app.route('/init-db')
def init_db():
    try:
        from __init__ import db
        db.create_all()
        return "✅ Database tables created successfully! You can now remove this endpoint."
    except Exception as e:
        return f"❌ Error: {e}"

# Create CLI
cli = FlaskGroup(create_app=lambda: app)

@cli.command('init-db')
def init_db():
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")
        print("   Tables created:")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        for table in inspector.get_table_names():
            print(f"   - {table}")

@cli.command('drop-db')
def drop_db():
    """Drop all database tables (CAREFUL!)"""
    confirm = input("⚠️  This will delete all data. Type 'YES' to confirm: ")
    if confirm == 'YES':
        with app.app_context():
            db.drop_all()
            print("✅ Database tables dropped successfully!")
    else:
        print("❌ Operation cancelled.")

@cli.command('seed-governance')
def seed_governance():
    """Seed governance data for testing"""
    # Import using correct paths
    from blueprints.governance.services import GovernanceService
    from blueprints.governance.models import GovernanceRaw
    
    with app.app_context():
        # Check if data already exists
        if GovernanceRaw.query.count() > 0:
            print("⚠️  Governance data already exists. Skipping seed.")
            return
        
        # Seed sample data
        sample_data = [
            {
                'taxpayer_id': 1001,
                'fiscal_year': 2023,
                'board_size': 7,
                'independent_directors': 3,
                'financial_experts': 2,
                'female_directors': 1,
                'ceo_duality': True,
                'source': 'TaRMS'
            },
            {
                'taxpayer_id': 1002,
                'fiscal_year': 2023,
                'board_size': 9,
                'independent_directors': 5,
                'financial_experts': 4,
                'female_directors': 3,
                'ceo_duality': False,
                'source': 'TaRMS'
            },
            {
                'taxpayer_id': 1003,
                'fiscal_year': 2023,
                'board_size': 5,
                'independent_directors': 1,
                'financial_experts': 1,
                'female_directors': 0,
                'ceo_duality': True,
                'source': 'AnnualReport'
            },
            {
                'taxpayer_id': 1004,
                'fiscal_year': 2023,
                'board_size': 11,
                'independent_directors': 7,
                'financial_experts': 5,
                'female_directors': 4,
                'ceo_duality': False,
                'source': 'TaRMS'
            },
            {
                'taxpayer_id': 1005,
                'fiscal_year': 2023,
                'board_size': 6,
                'independent_directors': 2,
                'financial_experts': 2,
                'female_directors': 1,
                'ceo_duality': True,
                'source': 'Regulatory'
            },
            # Add more test data for different years
            {
                'taxpayer_id': 1001,
                'fiscal_year': 2024,
                'board_size': 8,
                'independent_directors': 4,
                'financial_experts': 3,
                'female_directors': 2,
                'ceo_duality': False,
                'source': 'TaRMS'
            },
            {
                'taxpayer_id': 1002,
                'fiscal_year': 2024,
                'board_size': 10,
                'independent_directors': 6,
                'financial_experts': 5,
                'female_directors': 4,
                'ceo_duality': False,
                'source': 'TaRMS'
            }
        ]
        
        print("Seeding governance data...")
        for data in sample_data:
            try:
                GovernanceService.store_raw(data)
                print(f"  ✓ Seeded: Taxpayer {data['taxpayer_id']}, Year {data['fiscal_year']}")
            except Exception as e:
                print(f"  ✗ Failed for taxpayer {data['taxpayer_id']}: {e}")
        
        print(f"\n✅ Seeded {len(sample_data)} governance records successfully!")
        
        # Process the seeded data to generate indicators and scores
        print("\nProcessing seeded data...")
        for data in sample_data:
            try:
                # Get raw data
                raw = GovernanceService.get_raw(data['taxpayer_id'], data['fiscal_year'])
                if raw:
                    # Compute and save indicators
                    indicators = GovernanceService.compute_indicators(raw)
                    GovernanceService.save_indicators(data['taxpayer_id'], data['fiscal_year'], indicators)
                    # Compute risk score
                    risk_score = GovernanceService.compute_risk_score(data['taxpayer_id'], data['fiscal_year'])
                    print(f"  ✓ Processed: Taxpayer {data['taxpayer_id']}, Year {data['fiscal_year']}, Score: {risk_score:.2f}")
            except Exception as e:
                print(f"  ✗ Failed to process taxpayer {data['taxpayer_id']}: {e}")
        
        print("\n✅ Data seeding and processing complete!")

@cli.command('train-model')
def train_model():
    """Train the governance risk model"""
    print("=" * 60)
    print("Starting governance model training...")
    print("=" * 60)
    
    try:
        # Check if train_independent.py exists
        train_script = os.path.join(os.path.dirname(__file__), 'train_independent.py')
        
        if not os.path.exists(train_script):
            print(f"⚠️ Training script not found at: {train_script}")
            print("Creating train_independent.py...")
            
            # Create a simple training script if it doesn't exist
            with open(train_script, 'w') as f:
                f.write("""#!/usr/bin/env python
\"\"\"
Simple training script for governance risk model
\"\"\"

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

def prepare_features(df):
    features = df.copy()
    features = features.fillna({'board_size': 0, 'independence_ratio': 0, 'expertise_score': 0, 'diversity_index': 0, 'ceo_duality': False})
    features['board_size_squared'] = features['board_size'] ** 2
    features['indep_expert_interaction'] = features['independence_ratio'] * features['expertise_score']
    features['board_diversity_product'] = features['board_size'] * features['diversity_index']
    features['independence_normalized'] = features['independence_ratio'] / 100
    features['expertise_normalized'] = features['expertise_score'] / 100
    features['diversity_normalized'] = features['diversity_index'] / 100
    
    final_features = ['board_size', 'independence_ratio', 'expertise_score', 'diversity_index',
                      'ceo_duality', 'board_size_squared', 'indep_expert_interaction',
                      'board_diversity_product', 'independence_normalized',
                      'expertise_normalized', 'diversity_normalized']
    return features[[f for f in final_features if f in features.columns]]

def generate_synthetic_data(n_samples=2000):
    np.random.seed(42)
    data = []
    for _ in range(n_samples):
        board_size = np.random.randint(3, 15)
        independence_ratio = np.random.uniform(0, 100)
        expertise_score = np.random.uniform(0, 100)
        diversity_index = np.random.uniform(0, 50)
        ceo_duality = np.random.choice([True, False], p=[0.4, 0.6])
        
        risk_score = 0
        if independence_ratio < 30: risk_score += 40
        elif independence_ratio < 50: risk_score += 20
        if expertise_score < 20: risk_score += 30
        elif expertise_score < 40: risk_score += 15
        if diversity_index < 10: risk_score += 20
        if ceo_duality: risk_score += 10
        
        tax_risk_flag = 1 if risk_score > 50 else 0
        data.append({'board_size': board_size, 'independence_ratio': independence_ratio,
                     'expertise_score': expertise_score, 'diversity_index': diversity_index,
                     'ceo_duality': int(ceo_duality), 'tax_risk_flag': tax_risk_flag})
    return pd.DataFrame(data)

def train_model():
    print("Generating synthetic data...")
    df = generate_synthetic_data(2000)
    X = prepare_features(df)
    y = df['tax_risk_flag']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    models_dir = Path(__file__).parent / 'blueprints' / 'governance' / 'ml' / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(model, models_dir / 'governance_risk_model.pkl')
    joblib.dump(scaler, models_dir / 'governance_scaler.pkl')
    joblib.dump(X.columns.tolist(), models_dir / 'governance_features.pkl')
    
    print(f"✅ Model saved to {models_dir}")
    return model

if __name__ == "__main__":
    train_model()
""")
            print("✅ Created train_independent.py")
        
        # Run the training script
        import subprocess
        result = subprocess.run(
            [sys.executable, train_script],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print("\n✅ Model training completed successfully!")
        else:
            print("\n❌ Model training failed!")
            
    except Exception as e:
        print(f"❌ Error during training: {e}")
        import traceback
        traceback.print_exc()

@cli.command('run-worker')
def run_worker():
    """Run Celery worker (if configured)"""
    try:
        from __init__ import celery
        print("Starting Celery worker...")
        argv = ['worker', '--loglevel=info']
        celery.worker_main(argv)
    except ImportError:
        print("❌ Celery not configured. Install celery and redis if needed.")
    except Exception as e:
        print(f"❌ Error starting worker: {e}")

@cli.command('list-routes')
def list_routes():
    """List all registered routes"""
    import urllib
    output = []
    with app.app_context():
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods)
            line = urllib.parse.unquote(f"{rule.endpoint:30s} {methods:20s} {rule}")
            output.append(line)
        
        print("\nRegistered Routes:")
        print("=" * 80)
        for line in sorted(output):
            print(line)
        print("=" * 80)

if __name__ == '__main__':
    cli()