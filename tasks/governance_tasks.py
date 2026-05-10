"""
Simple task functions for governance operations
(Without Celery for now)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def process_governance_data(taxpayer_id, fiscal_year):
    """Process raw governance data and compute indicators"""
    try:
        from blueprints.governance.services import GovernanceService
        
        print(f"Processing governance data for taxpayer {taxpayer_id}, year {fiscal_year}")
        
        # Get raw data
        raw = GovernanceService.get_raw(taxpayer_id, fiscal_year)
        if raw:
            # Compute indicators
            indicators = GovernanceService.compute_indicators(raw)
            # Save indicators
            GovernanceService.save_indicators(taxpayer_id, fiscal_year, indicators)
            # Compute risk score
            GovernanceService.compute_risk_score(taxpayer_id, fiscal_year)
            print(f"✅ Successfully processed taxpayer {taxpayer_id}")
            return True
        else:
            print(f"⚠️ No raw data found for taxpayer {taxpayer_id}, year {fiscal_year}")
            return False
    except Exception as e:
        print(f"❌ Error processing governance data: {e}")
        import traceback
        traceback.print_exc()
        return False


def compute_governance_risk_score(taxpayer_id, fiscal_year):
    """Compute risk score for a taxpayer"""
    try:
        from blueprints.governance.services import GovernanceService
        
        print(f"Computing risk score for taxpayer {taxpayer_id}, year {fiscal_year}")
        
        risk_score = GovernanceService.compute_risk_score(taxpayer_id, fiscal_year)
        
        if risk_score is not None:
            print(f"✅ Risk score computed: {risk_score:.2f}")
            return risk_score
        else:
            print(f"⚠️ Could not compute risk score for taxpayer {taxpayer_id}")
            return None
    except Exception as e:
        print(f"❌ Error computing risk score: {e}")
        import traceback
        traceback.print_exc()
        return None


# For compatibility with Celery if added later
def delay(func, *args, **kwargs):
    """Simple wrapper for async execution (sync for now)"""
    return func(*args, **kwargs)