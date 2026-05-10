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

# ============================================================
# TEMPORARY ROUTE FOR DATABASE INITIALIZATION (via browser)
# Remove these after running once!
# ============================================================

@app.route('/init-db')
def init_db_route():
    """Initialize database tables via browser"""
    try:
        db.create_all()
        return "✅ Database tables created successfully! You can now remove this endpoint."
    except Exception as e:
        return f"❌ Error: {e}"

@app.route('/seed-data')
def seed_data_route():
    """Seed sample data via browser"""
    try:
        from blueprints.governance.models import GovernanceRaw
        
        if GovernanceRaw.query.count() > 0:
            return "⚠️ Data already exists. Skipping seed."
        
        sample_data = [
            {'taxpayer_id': 1, 'fiscal_year': 2024, 'board_size': 7, 'independent_directors': 3, 'financial_experts': 2, 'female_directors': 1, 'ceo_duality': True, 'source': 'TaRMS'},
            {'taxpayer_id': 2, 'fiscal_year': 2024, 'board_size': 9, 'independent_directors': 5, 'financial_experts': 4, 'female_directors': 3, 'ceo_duality': False, 'source': 'TaRMS'},
            {'taxpayer_id': 3, 'fiscal_year': 2024, 'board_size': 5, 'independent_directors': 1, 'financial_experts': 1, 'female_directors': 0, 'ceo_duality': True, 'source': 'AnnualReport'},
        ]
        
        for data in sample_data:
            raw = GovernanceRaw(**data)
            db.session.add(raw)
        
        db.session.commit()
        return f"✅ Seeded {len(sample_data)} governance records successfully!"
    except Exception as e:
        return f"❌ Error seeding data: {e}"

# ============================================================
# END OF TEMPORARY ROUTES
# ============================================================

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
    from blueprints.governance.services import GovernanceService
    from blueprints.governance.models import GovernanceRaw
    
    with app.app_context():
        if GovernanceRaw.query.count() > 0:
            print("⚠️  Governance data already exists. Skipping seed.")
            return
        
        sample_data = [
            {'taxpayer_id': 1001, 'fiscal_year': 2023, 'board_size': 7, 'independent_directors': 3, 'financial_experts': 2, 'female_directors': 1, 'ceo_duality': True, 'source': 'TaRMS'},
            {'taxpayer_id': 1002, 'fiscal_year': 2023, 'board_size': 9, 'independent_directors': 5, 'financial_experts': 4, 'female_directors': 3, 'ceo_duality': False, 'source': 'TaRMS'},
            {'taxpayer_id': 1001, 'fiscal_year': 2024, 'board_size': 8, 'independent_directors': 4, 'financial_experts': 3, 'female_directors': 2, 'ceo_duality': False, 'source': 'TaRMS'},
            {'taxpayer_id': 1002, 'fiscal_year': 2024, 'board_size': 10, 'independent_directors': 6, 'financial_experts': 5, 'female_directors': 4, 'ceo_duality': False, 'source': 'TaRMS'},
        ]
        
        print("Seeding governance data...")
        for data in sample_data:
            try:
                GovernanceService.store_raw(data)
                print(f"  ✓ Seeded: Taxpayer {data['taxpayer_id']}, Year {data['fiscal_year']}")
            except Exception as e:
                print(f"  ✗ Failed: {e}")
        
        print(f"\n✅ Seeded {len(sample_data)} governance records!")

@cli.command('train-model')
def train_model():
    """Train the governance risk model"""
    print("=" * 60)
    print("Starting governance model training...")
    print("=" * 60)
    try:
        train_script = os.path.join(os.path.dirname(__file__), 'train_independent.py')
        if not os.path.exists(train_script):
            print(f"⚠️ Training script not found at: {train_script}")
            return
        
        import subprocess
        subprocess.run([sys.executable, train_script], check=True)
        print("\n✅ Model training completed successfully!")
    except Exception as e:
        print(f"❌ Error during training: {e}")

@cli.command('run-worker')
def run_worker():
    """Run Celery worker (if configured)"""
    try:
        from __init__ import celery
        print("Starting Celery worker...")
        argv = ['worker', '--loglevel=info']
        celery.worker_main(argv)
    except ImportError:
        print("❌ Celery not configured.")
    except Exception as e:
        print(f"❌ Error: {e}")

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