#!/usr/bin/env python
"""
Generate complete test data for 100 companies with data from 2015-2025
Includes realistic payment patterns, late filing penalties, and governance data
"""

import sys
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from __init__ import create_app, db
from blueprints.governance.models import (
    Taxpayer, TaxReturn, Payment, GovernanceIndicators, GovernanceRiskScores,
    AuditOutcome, ValidationIssue, BehavioralAlert, DetectedBehavior
)

# Zimbabwean company names (100 unique names)
COMPANY_NAMES = [
    # Large corporations
    "Delta Corporation", "Econet Wireless", "CBZ Holdings", "Innscor Africa", 
    "Old Mutual Zimbabwe", "NMB Bank", "Meikles Limited", "Astra Industries",
    "Seed Co International", "Zimplow Holdings", "Padenga Holdings", "Afrochine",
    "Proplastics", "Willdale Limited", "Hippo Valley Estates", "Star Africa",
    "Art Corporation", "Zimre Holdings", "FBC Holdings", "First Capital Bank",
    
    # Manufacturing
    "Cafca Limited", "Celsys", "Chemplex Corporation", "Dairibord Holdings",
    "Edgars Stores", "First Mutual Holdings", "GetBucks", "Glenara Estates",
    "Hunyani Holdings", "Interfresh", "Lafarge Cement", "Mashonaland Holdings",
    "Masimba Holdings", "MedTech", "National Foods", "OK Zimbabwe",
    "Pearl Properties", "Powerspeed Electrical", "RioZim", "Simbisa Brands",
    
    # Mining & Energy
    "Bindura Nickel", "Falgold", "Hwange Colliery", "Karoo Resources",
    "Mimosa Mining", "Murowa Diamonds", "Rio Tinto Zimbabwe", "Shamva Mine",
    "Unki Mine", "Zimasco", "Zimplats", "Caledonia Mining", "Blanket Mine",
    "Freda Rebecca", "Metallon Gold", "How Mine", "Turk Mine", "Eureka Mine",
    
    # Services & Technology
    "Cassava Technologies", "EcoCash", "NetOne", "Telecel", "TelOne",
    "Zarnet", "ZOL Zimbabwe", "AfriCash", "OneMoney", "Biztech",
    
    # Agriculture
    "Afriagri", "Agrifoods", "CFI Holdings", "Clover Leaf", "Cottco",
    "Fidelity Printers", "Grain Marketing Board", "Lion Brands", 
    "National Railways", "NSSA", "Postal Corporation", "RTG Holdings",
    "Sabina Trust", "Tanganda Tea", "Tongaat Hulett", "Zimbabwe Leaf Tobacco",
    
    # Banking & Finance
    "Agribank", "Bank ABC", "BancABC", "CABS", "Century Bank",
    "Ecobank", "Metropolitan Bank", "MBCA Bank", "Nedbank Zimbabwe",
    "People's Own Savings Bank", "Stanbic Bank", "StanChart Zimbabwe",
    "Steward Bank", "ZB Bank", "Afreximbank", "CBZ Building Society",
    
    # Retail & Distribution
    "Choppies Zimbabwe", "Pick n Pay", "Spar Zimbabwe", "TM Pick n Pay",
    "True Value", "Jumbo Foods", "N Richards Group", "Bon Marche",
    "Sable Chemicals", "Zimglass", "Capri Holdings"
]

INDUSTRIES = [
    "Manufacturing", "Banking & Finance", "Telecommunications", "Retail",
    "Agriculture", "Mining", "Construction", "Hospitality", "Transport",
    "Technology", "Healthcare", "Education", "Real Estate", "Energy",
    "Insurance", "Logistics", "Pharmaceuticals", "Textiles", "Automotive"
]

def generate_board_structure(risk_factor=1.0):
    """Generate realistic board structure based on risk factor (CEO duality removed)"""
    board_size = random.randint(5, 15)
    independent_directors = random.randint(int(board_size * 0.2), int(board_size * 0.8))
    financial_experts = random.randint(int(board_size * 0.1), int(board_size * 0.5))
    female_directors = random.randint(0, int(board_size * 0.4))
    
    # Higher risk companies have worse governance
    if risk_factor > 1.3:
        independent_directors = int(board_size * random.uniform(0.1, 0.3))
        financial_experts = int(board_size * random.uniform(0.05, 0.2))
    elif risk_factor < 0.7:
        independent_directors = int(board_size * random.uniform(0.5, 0.8))
        financial_experts = int(board_size * random.uniform(0.4, 0.6))
    
    return {
        'board_size': board_size,
        'independent_directors': independent_directors,
        'financial_experts': financial_experts,
        'female_directors': female_directors,
        'independence_ratio': (independent_directors / board_size * 100) if board_size > 0 else 0,
        'expertise_score': (financial_experts / board_size * 100) if board_size > 0 else 0,
        'diversity_index': (female_directors / board_size * 100) if board_size > 0 else 0
    }

def generate_financial_data(industry, year, risk_factor=1.0):
    """Generate realistic financial data with growth trends"""
    industry_multipliers = {
        "Manufacturing": 50, "Banking & Finance": 100, "Telecommunications": 80,
        "Retail": 30, "Agriculture": 25, "Mining": 150, "Construction": 40,
        "Hospitality": 15, "Transport": 20, "Technology": 60, "Healthcare": 35,
        "Education": 10, "Real Estate": 45, "Energy": 90, "Insurance": 55,
        "Logistics": 25, "Pharmaceuticals": 40, "Textiles": 20, "Automotive": 45
    }
    
    base_revenue = industry_multipliers.get(industry, 30) * 1000000
    
    # Year growth factor (2015 = base, 2025 = +50%)
    growth = 1 + (year - 2015) * 0.05
    revenue = base_revenue * growth * random.uniform(0.8, 1.2) * risk_factor
    
    # Profit margin varies by risk and industry
    base_margin = {
        "Manufacturing": 0.20, "Banking & Finance": 0.30, "Telecommunications": 0.25,
        "Retail": 0.12, "Agriculture": 0.15, "Mining": 0.35, "Construction": 0.18,
        "Technology": 0.22, "Healthcare": 0.17, "Real Estate": 0.28
    }.get(industry, 0.20)
    
    if risk_factor > 1.3:
        profit_margin = base_margin * random.uniform(0.5, 0.8)
    else:
        profit_margin = base_margin * random.uniform(0.9, 1.1)
    
    profit = revenue * profit_margin
    
    # Taxable income (accounting profit with adjustments)
    taxable_income = profit * random.uniform(0.85, 0.98)
    
    # Tax liability (25% statutory rate)
    statutory_rate = 0.25
    tax_liability = taxable_income * statutory_rate
    
    # Add tax planning variation
    if risk_factor > 1.3:
        tax_liability *= random.uniform(0.5, 0.7)  # High risk - tax avoidance
    elif risk_factor < 0.7:
        tax_liability *= random.uniform(0.95, 1.05)  # Low risk - compliant
    else:
        tax_liability *= random.uniform(0.8, 0.95)  # Medium risk
    
    return {
        'total_income': Decimal(str(round(revenue, 2))),
        'taxable_income': Decimal(str(round(taxable_income, 2))),
        'tax_liability': Decimal(str(round(tax_liability, 2))),
        'accounting_profit': Decimal(str(round(profit, 2))),
        'etr': (float(tax_liability) / profit * 100) if profit > 0 else 0
    }

def generate_payments(tax_liability, year, risk_factor, quarter):
    """Generate quarterly payments with late payment patterns"""
    due_date = datetime(year, quarter * 3, 25)
    
    # Determine if payment is late based on risk profile
    if risk_factor > 1.3:
        is_late = random.random() < 0.6  # High risk - often late
    elif risk_factor > 1.0:
        is_late = random.random() < 0.3  # Medium risk - sometimes late
    else:
        is_late = random.random() < 0.1  # Low risk - rarely late
    
    if is_late:
        payment_date = due_date + timedelta(days=random.randint(5, 60))
        status = 'Late'
        late_days = (payment_date - due_date).days
    else:
        payment_date = due_date - timedelta(days=random.randint(0, 10))
        status = 'On Time'
        late_days = 0
    
    # Calculate penalty (10% per annum on late amount)
    amount = tax_liability / 4
    penalty = amount * Decimal('0.10') * Decimal(str(late_days / 365)) if late_days > 0 else Decimal('0')
    total_amount = amount + penalty
    
    return {
        'payment_date': payment_date,
        'amount': total_amount,
        'payment_type': 'Provisional' if quarter < 4 else 'Final',
        'due_date': due_date,
        'status': status,
        'penalty': penalty,
        'late_days': late_days
    }

def generate_audit_history(taxpayer_id, years, risk_factor):
    """Generate audit outcomes for high-risk years"""
    audits = []
    for year in years:
        if risk_factor > 1.2 and random.random() < 0.4:  # High risk - more audits
            if risk_factor > 1.4:
                outcome = random.choice(['Under-Declaration', 'Non-Compliant'])
                additional_assessment = Decimal(str(random.uniform(50000, 500000)))
                penalties = additional_assessment * Decimal('0.25')
                findings = "Audit revealed significant under-reporting of income"
            else:
                outcome = random.choice(['Non-Compliant', 'Compliant'])
                additional_assessment = Decimal(str(random.uniform(10000, 100000))) if outcome != 'Compliant' else Decimal('0')
                penalties = additional_assessment * Decimal('0.25') if additional_assessment > 0 else Decimal('0')
                findings = "Minor discrepancies found during audit" if additional_assessment > 0 else "Fully compliant"
            
            audits.append({
                'audit_date': datetime(year, random.randint(1, 12), random.randint(1, 28)),
                'findings': findings,
                'additional_assessment': additional_assessment,
                'penalties': penalties,
                'outcome': outcome,
                'recommendation': "Implement stronger internal controls" if outcome != 'Compliant' else "Continue current practices"
            })
        elif random.random() < 0.1:  # Random audit for low risk
            audits.append({
                'audit_date': datetime(year, random.randint(1, 12), random.randint(1, 28)),
                'findings': "Random audit - fully compliant",
                'additional_assessment': Decimal('0'),
                'penalties': Decimal('0'),
                'outcome': 'Compliant',
                'recommendation': "Continue current practices"
            })
    
    return audits

def generate_validation_issues(taxpayer_id, fiscal_year, governance_data, risk_factor):
    """Generate validation issues based on governance and risk (CEO duality removed)"""
    issues = []
    
    # Issue 1: Board independence
    if governance_data['independence_ratio'] < 30:
        issues.append({
            'issue_type': 'Low Board Independence',
            'severity': 'High',
            'description': f"Board independence ratio of {governance_data['independence_ratio']:.1f}% is below recommended 30% threshold",
            'field_name': 'independence_ratio',
            'expected_value': '≥30%',
            'actual_value': f"{governance_data['independence_ratio']:.1f}%"
        })
    elif governance_data['independence_ratio'] < 50:
        issues.append({
            'issue_type': 'Moderate Board Independence',
            'severity': 'Medium',
            'description': f"Board independence ratio of {governance_data['independence_ratio']:.1f}% is below optimal 50%",
            'field_name': 'independence_ratio',
            'expected_value': '≥50%',
            'actual_value': f"{governance_data['independence_ratio']:.1f}%"
        })
    
    # Issue 2: Financial expertise
    if governance_data['expertise_score'] < 20:
        issues.append({
            'issue_type': 'Insufficient Financial Expertise',
            'severity': 'High',
            'description': f"Only {governance_data['expertise_score']:.1f}% of board members have financial expertise",
            'field_name': 'financial_experts',
            'expected_value': '≥20%',
            'actual_value': f"{governance_data['expertise_score']:.1f}%"
        })
    elif governance_data['expertise_score'] < 40:
        issues.append({
            'issue_type': 'Limited Financial Expertise',
            'severity': 'Medium',
            'description': f"Only {governance_data['expertise_score']:.1f}% of board has financial expertise",
            'field_name': 'financial_experts',
            'expected_value': '≥40%',
            'actual_value': f"{governance_data['expertise_score']:.1f}%"
        })
    
    # Issue 3: Gender diversity
    if governance_data['diversity_index'] < 10:
        issues.append({
            'issue_type': 'Lack of Gender Diversity',
            'severity': 'Medium',
            'description': f"Only {governance_data['diversity_index']:.1f}% female representation on board",
            'field_name': 'female_directors',
            'expected_value': '≥10%',
            'actual_value': f"{governance_data['diversity_index']:.1f}%"
        })
    
    # Issue 4: Board size issues
    if governance_data['board_size'] < 5:
        issues.append({
            'issue_type': 'Board Size Too Small',
            'severity': 'Medium',
            'description': f"Board size of {governance_data['board_size']} is below recommended minimum",
            'field_name': 'board_size',
            'expected_value': '≥5',
            'actual_value': str(governance_data['board_size'])
        })
    elif governance_data['board_size'] > 15:
        issues.append({
            'issue_type': 'Board Size Too Large',
            'severity': 'Low',
            'description': f"Board size of {governance_data['board_size']} may hinder effective decision-making",
            'field_name': 'board_size',
            'expected_value': '≤15',
            'actual_value': str(governance_data['board_size'])
        })
    
    return issues

def generate_behavioral_alerts(taxpayer_id, fiscal_year, payments, risk_factor):
    """Generate behavioral alerts based on payment patterns"""
    alerts = []
    
    late_payments = [p for p in payments if p['status'] == 'Late']
    if len(late_payments) > 0:
        late_percentage = len(late_payments) / len(payments) * 100
        
        if late_percentage > 50:
            alerts.append({
                'alert_type': 'Persistent Late Payment Pattern',
                'severity': 'High',
                'description': f"{len(late_payments)} of {len(payments)} payments late",
                'confidence_score': Decimal('0.85')
            })
        elif late_percentage > 25:
            alerts.append({
                'alert_type': 'Frequent Late Payments',
                'severity': 'Medium',
                'description': f"{len(late_payments)} late payments detected",
                'confidence_score': Decimal('0.65')
            })
    
    # Underpayment detection
    total_paid = sum(float(p['amount']) for p in payments)
    expected_payment = float(payments[0]['amount']) * 4 if payments else 0
    if total_paid < expected_payment * 0.8:
        alerts.append({
            'alert_type': 'Significant Underpayment',
            'severity': 'High',
            'description': f"Total payments {((1 - total_paid/expected_payment)*100):.0f}% below expected",
            'confidence_score': Decimal('0.90')
        })
    
    return alerts

def generate_all_data():
    """Main function to generate all test data"""
    
    app = create_app()
    with app.app_context():
        
        print("=" * 70)
        print("GENERATING COMPLETE DATA FOR 100 COMPANIES (2015-2025)")
        print("=" * 70)
        
        # Clear existing data
        print("\n1. Clearing existing data...")
        db.session.query(DetectedBehavior).delete()
        db.session.query(BehavioralAlert).delete()
        db.session.query(ValidationIssue).delete()
        db.session.query(AuditOutcome).delete()
        db.session.query(Payment).delete()
        db.session.query(TaxReturn).delete()
        db.session.query(GovernanceRiskScores).delete()
        db.session.query(GovernanceIndicators).delete()
        db.session.query(Taxpayer).delete()
        db.session.commit()
        print("   ✓ Existing data cleared")
        
        # Generate 100 companies
        print("\n2. Creating 100 companies...")
        companies = []
        years_range = list(range(2015, 2026))  # 2015-2025
        
        for i in range(100):
            company_name = COMPANY_NAMES[i % len(COMPANY_NAMES)]
            if i >= len(COMPANY_NAMES):
                company_name = f"{company_name} {i//len(COMPANY_NAMES) + 1}"
            
            taxpayer = Taxpayer(
                tin=f"{random.randint(100, 999)}-{random.randint(100000, 999999)}",
                company_name=company_name,
                registration_date=datetime(random.randint(2000, 2015), random.randint(1, 12), random.randint(1, 28)),
                industry=random.choice(INDUSTRIES),
                status='Active'
            )
            db.session.add(taxpayer)
            db.session.flush()
            companies.append(taxpayer)
            
            if (i + 1) % 20 == 0:
                db.session.commit()
                print(f"   ✓ Created {i + 1} companies...")
        
        db.session.commit()
        print(f"   ✓ Generated {len(companies)} companies")
        
        # Generate data for each company
        print("\n3. Generating financial, governance, and compliance data (2015-2025)...")
        
        total_companies = len(companies)
        for idx, taxpayer in enumerate(companies):
            # Determine risk profile for this company
            risk_profile = random.uniform(0.5, 1.8)
            
            for year in years_range:
                # Generate governance data (CEO duality removed)
                governance = generate_board_structure(risk_profile)
                
                # Generate financial data
                financial = generate_financial_data(taxpayer.industry, year, risk_profile)
                
                # Calculate risk score based on governance and financials
                risk_score = 50
                if governance['independence_ratio'] < 30:
                    risk_score += 30
                elif governance['independence_ratio'] < 50:
                    risk_score += 15
                
                if governance['expertise_score'] < 20:
                    risk_score += 25
                elif governance['expertise_score'] < 40:
                    risk_score += 12
                
                if governance['diversity_index'] < 10:
                    risk_score += 15
                elif governance['diversity_index'] < 25:
                    risk_score += 8
                
                if financial['etr'] < 15:
                    risk_score += 20
                elif financial['etr'] < 20:
                    risk_score += 10
                
                risk_score = min(max(risk_score * risk_profile / 1.2, 0), 100)
                
                # Save governance indicators
                indicators = GovernanceIndicators(
                    taxpayer_id=taxpayer.id,
                    fiscal_year=year,
                    board_size=governance['board_size'],
                    independence_ratio=Decimal(str(round(governance['independence_ratio'], 2))),
                    expertise_score=Decimal(str(round(governance['expertise_score'], 2))),
                    diversity_index=Decimal(str(round(governance['diversity_index'], 2)))
                )
                db.session.add(indicators)
                
                # Save risk score
                risk_record = GovernanceRiskScores(
                    taxpayer_id=taxpayer.id,
                    fiscal_year=year,
                    governance_risk_score=Decimal(str(round(risk_score, 2))),
                    risk_probability=Decimal(str(round(risk_score / 100, 4))),
                    model_version='v2.0'
                )
                db.session.add(risk_record)
                
                # Create tax return
                tax_return = TaxReturn(
                    taxpayer_id=taxpayer.id,
                    fiscal_year=year,
                    filing_date=datetime(year, random.randint(3, 5), random.randint(1, 28)),
                    total_income=financial['total_income'],
                    taxable_income=financial['taxable_income'],
                    tax_liability=financial['tax_liability'],
                    accounting_profit=financial['accounting_profit'],
                    status='Filed'
                )
                db.session.add(tax_return)
                
                # Create quarterly payments
                payments_data = []
                for quarter in range(1, 5):
                    payment = generate_payments(financial['tax_liability'], year, risk_profile, quarter)
                    payments_data.append(payment)
                    
                    payment_record = Payment(
                        taxpayer_id=taxpayer.id,
                        fiscal_year=year,
                        payment_date=payment['payment_date'],
                        amount=payment['amount'],
                        payment_type=payment['payment_type'],
                        due_date=payment['due_date'],
                        status=payment['status']
                    )
                    db.session.add(payment_record)
                
                # Generate validation issues
                issues = generate_validation_issues(taxpayer.id, year, governance, risk_profile)
                for issue_data in issues:
                    issue = ValidationIssue(
                        taxpayer_id=taxpayer.id,
                        fiscal_year=year,
                        **issue_data,
                        status='Open',
                        created_at=datetime(year, random.randint(1, 12), random.randint(1, 28))
                    )
                    db.session.add(issue)
                
                # Generate behavioral alerts
                alerts = generate_behavioral_alerts(taxpayer.id, year, payments_data, risk_profile)
                for alert_data in alerts:
                    alert = BehavioralAlert(
                        taxpayer_id=taxpayer.id,
                        fiscal_year=year,
                        **alert_data,
                        status='New',
                        created_at=datetime(year, random.randint(1, 12), random.randint(1, 28))
                    )
                    db.session.add(alert)
            
            # Generate audit history (random years)
            audit_years = random.sample(years_range, min(3, len(years_range)))
            audits = generate_audit_history(taxpayer.id, audit_years, risk_profile)
            for audit_data in audits:
                audit = AuditOutcome(
                    taxpayer_id=taxpayer.id,
                    **audit_data
                )
                db.session.add(audit)
            
            # Progress indicator
            if (idx + 1) % 10 == 0:
                db.session.commit()
                print(f"   ✓ Processed {idx + 1} of {total_companies} companies...")
        
        # Final commit
        db.session.commit()
        
        # Summary statistics
        print("\n" + "=" * 70)
        print("DATA GENERATION COMPLETE - SUMMARY")
        print("=" * 70)
        print(f"Taxpayers: {Taxpayer.query.count()}")
        print(f"Tax Returns: {TaxReturn.query.count()}")
        print(f"Payments: {Payment.query.count()}")
        print(f"Governance Indicators: {GovernanceIndicators.query.count()}")
        print(f"Risk Scores: {GovernanceRiskScores.query.count()}")
        print(f"Validation Issues: {ValidationIssue.query.count()}")
        print(f"Behavioral Alerts: {BehavioralAlert.query.count()}")
        print(f"Audit Outcomes: {AuditOutcome.query.count()}")
        print("=" * 70)
        
        # Years coverage
        years_with_data = db.session.query(TaxReturn.fiscal_year.distinct()).order_by(TaxReturn.fiscal_year).all()
        print(f"\nYears with data: {[y[0] for y in years_with_data]}")
        
        # Late payment statistics
        late_payments_count = Payment.query.filter_by(status='Late').count()
        total_payments = Payment.query.count()
        late_percentage = (late_payments_count / total_payments * 100) if total_payments > 0 else 0
        print(f"\nLate Payments: {late_payments_count} / {total_payments} ({late_percentage:.1f}%)")
        
        print("\n✅ Complete data generation successful!")
        print("\nYou can now:")
        print("  - Run the Flask app: python run.py run")
        print("  - Access ETR Analysis with 100 companies from 2015-2025")
        print("  - View Behavioral Analysis with realistic late payment patterns")

if __name__ == "__main__":
    generate_all_data()