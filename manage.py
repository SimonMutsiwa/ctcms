#!/usr/bin/env python
"""
Management script for CTCMS
"""

import click
from flask.cli import FlaskGroup
from blueprints import create_app, db
from config import config
import os

app = create_app(config[os.environ.get('FLASK_ENV', 'development')])

@click.group(cls=FlaskGroup, create_app=lambda: app)
def cli():
    """CTCMS Management CLI"""
    pass

@cli.command()
def init_db():
    """Initialize database"""
    with app.app_context():
        db.create_all()
        click.echo("Database initialized successfully!")

@cli.command()
def train_governance_model():
    """Train governance risk model"""
    from blueprints.governance.ml.train import train_governance_model
    with app.app_context():
        click.echo("Starting governance model training...")
        model, metrics = train_governance_model()
        click.echo(f"Training complete! ROC-AUC: {metrics['roc_auc']:.4f}")

@cli.command()
def seed_data():
    """Seed database with test data"""
    from blueprints.governance.services import GovernanceService
    
    with app.app_context():
        test_data = [
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
            # Add more test data as needed
        ]
        
        for data in test_data:
            GovernanceService.store_raw(data)
            click.echo(f"Seeded data for taxpayer {data['taxpayer_id']}")
        
        click.echo("Data seeding complete!")

@cli.command()
def run_worker():
    """Run Celery worker"""
    from blueprints import celery
    argv = ['worker', '--loglevel=info']
    celery.worker_main(argv)

if __name__ == '__main__':
    cli()