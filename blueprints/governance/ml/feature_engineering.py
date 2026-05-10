import pandas as pd

def prepare_features(indicators_df):
    """
    Prepare features for ML model from governance indicators
    """
    features = indicators_df.copy()
    
    features = features.fillna({
        'board_size': 0,
        'independence_ratio': 0,
        'expertise_score': 0,
        'diversity_index': 0,
        'ceo_duality': False
    })
    
    features['board_size_squared'] = features['board_size'] ** 2
    features['indep_expert_interaction'] = features['independence_ratio'] * features['expertise_score']
    features['board_diversity_product'] = features['board_size'] * features['diversity_index']
    features['independence_normalized'] = features['independence_ratio'] / 100
    features['expertise_normalized'] = features['expertise_score'] / 100
    features['diversity_normalized'] = features['diversity_index'] / 100
    
    final_features = [
        'board_size', 'independence_ratio', 'expertise_score', 'diversity_index',
        'ceo_duality', 'board_size_squared', 'indep_expert_interaction',
        'board_diversity_product', 'independence_normalized',
        'expertise_normalized', 'diversity_normalized'
    ]
    
    return features[final_features]