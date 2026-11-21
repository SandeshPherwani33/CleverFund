"""
Prediction script with cold start handling
Loads trained model and applies same preprocessing as training
"""

import logging
from pathlib import Path
from typing import Dict, Tuple, Any
import numpy as np
import pandas as pd
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "startup_model.pkl"
PREPROCESSING_PATH = MODEL_DIR / "preprocessing_info.pkl"

# Global model cache
_model = None
_preprocessing_data = None


def load_model():
    """Load model and preprocessing info"""
    global _model, _preprocessing_data
    
    if _model is not None and _preprocessing_data is not None:
        return _model, _preprocessing_data
    
    if not MODEL_PATH.exists() or not PREPROCESSING_PATH.exists():
        raise FileNotFoundError(
            f"Model files not found. Please run train.py first.\n"
            f"Expected: {MODEL_PATH}, {PREPROCESSING_PATH}"
        )
    
    logger.info(f"Loading model from {MODEL_PATH}")
    _model = joblib.load(MODEL_PATH)
    
    logger.info(f"Loading preprocessing info from {PREPROCESSING_PATH}")
    _preprocessing_data = joblib.load(PREPROCESSING_PATH)
    
    logger.info("Model and preprocessing data loaded successfully")
    return _model, _preprocessing_data


def handle_cold_start(input_data: Dict[str, Any], preprocessing_info: Dict) -> pd.DataFrame:
    """
    Handle cold start: fill missing values intelligently
    
    For numeric columns: fill with median from training data
    For categorical columns: fill with 'unknown'
    
    Args:
        input_data: Dictionary with startup features
        preprocessing_info: Contains median values from training
    
    Returns:
        DataFrame with handled missing values
    """
    logger.info("\n=== HANDLING COLD START ===")
    
    # Convert input to DataFrame
    df = pd.DataFrame([input_data])
    
    # Standardize column names
    df.columns = [col.strip().lower().replace(" ", "_").replace("-", "_") for col in df.columns]
    
    logger.info(f"Input data shape: {df.shape}")
    logger.info(f"Columns: {df.columns.tolist()}")
    
    # Handle each column
    for col in df.columns:
        if df[col].isnull().any():
            # Check if it's numeric
            if pd.api.types.is_numeric_dtype(df[col]) or isinstance(df[col].iloc[0], (int, float)):
                # Fill with median from training data
                median_key = f"{col}_median"
                if median_key in preprocessing_info.get('preprocessing_info', {}):
                    median_val = preprocessing_info['preprocessing_info'][median_key]
                    df[col].fillna(median_val, inplace=True)
                    logger.info(f"Filled {col} with training median: {median_val}")
                else:
                    df[col].fillna(0, inplace=True)
                    logger.info(f"Filled {col} with 0 (no training median available)")
            else:
                # Fill with 'unknown'
                df[col].fillna('unknown', inplace=True)
                logger.info(f"Filled {col} with 'unknown'")
    
    # Replace empty strings with unknown
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).replace({'nan': 'unknown', 'None': 'unknown'})
            if df[col].iloc[0] == '':
                df[col] = 'unknown'
    
    logger.info("Cold start handling completed")
    return df


def encode_input_features(
    df: pd.DataFrame,
    label_encoders: Dict,
    feature_cols: list
) -> np.ndarray:
    """
    Encode categorical features using trained label encoders
    """
    logger.info("\n=== ENCODING INPUT FEATURES ===")
    
    # Ensure all required columns exist
    for col in feature_cols:
        if col not in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]) if col in df else True:
                df[col] = 0
            else:
                df[col] = 'unknown'
            logger.warning(f"Added missing column {col} with default value")
    
    df = df[feature_cols].copy()
    
    # Encode categorical columns
    categorical_cols = ['industry', 'location']
    for col in categorical_cols:
        if col in df.columns and col in label_encoders:
            try:
                # Try to encode with trained encoder
                df[col] = label_encoders[col].transform(df[col].astype(str))
                logger.info(f"Encoded {col}")
            except ValueError as e:
                # Handle unknown categories
                logger.warning(f"Unknown category in {col}: {e}")
                df[col] = label_encoders[col].transform([label_encoders[col].classes_[0]])[0]
                logger.info(f"Used default class for {col}")
    
    X = df.values
    logger.info(f"Features shape: {X.shape}")
    return X


def predict(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make prediction for startup success
    
    Args:
        input_data: Dictionary with keys like:
            - funding_amount: float
            - num_employees: int
            - industry: str
            - revenue: float
            - location: str
    
    Returns:
        Dictionary with prediction, probability, and confidence
    """
    logger.info("\n" + "="*70)
    logger.info("MAKING PREDICTION")
    logger.info("="*70)
    
    try:
        # Load model
        model, preprocessing_data = load_model()
        
        label_encoders = preprocessing_data['label_encoders']
        feature_cols = preprocessing_data['feature_cols']
        preprocessing_info = preprocessing_data
        
        logger.info("Input feature names: %s", sorted(input_data))
        
        # Handle cold start
        df = handle_cold_start(input_data, preprocessing_info)
        
        # Encode features
        X = encode_input_features(df, label_encoders, feature_cols)
        
        # Make prediction
        logger.info("\n=== MAKING PREDICTION ===")
        prediction = model.predict(X)[0]
        probability = model.predict_proba(X)[0]
        
        success_prob = probability[1] * 100  # Probability of success
        failure_prob = probability[0] * 100  # Probability of failure
        
        result = {
            'prediction': 'Success' if prediction == 1 else 'Failure',
            'confidence': max(success_prob, failure_prob),
            'success_probability': success_prob,
            'failure_probability': failure_prob,
            'raw_prediction': int(prediction),
            'probabilities': {
                'success': float(success_prob),
                'failure': float(failure_prob)
            }
        }
        
        logger.info(f"Prediction: {result['prediction']}")
        logger.info(f"Success Probability: {success_prob:.2f}%")
        logger.info(f"Failure Probability: {failure_prob:.2f}%")
        logger.info(f"Confidence: {result['confidence']:.2f}%")
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}", exc_info=True)
        raise


def batch_predict(input_list: list) -> list:
    """
    Make predictions for multiple startups
    
    Args:
        input_list: List of dictionaries, each with startup data
    
    Returns:
        List of prediction results
    """
    logger.info(f"\nMaking batch predictions for {len(input_list)} startups")
    results = []
    
    for idx, startup_data in enumerate(input_list):
        try:
            logger.info(f"\nBatch prediction {idx + 1}/{len(input_list)}")
            result = predict(startup_data)
            result['index'] = idx
            results.append(result)
        except Exception as e:
            logger.error(f"Error predicting for startup {idx}: {str(e)}")
            results.append({
                'index': idx,
                'error': str(e),
                'prediction': None
            })
    
    return results


if __name__ == "__main__":
    # Example usage
    test_startup = {
        'funding_amount': 2500000,
        'num_employees': 25,
        'industry': 'Tech',
        'revenue': 500000,
        'location': 'San Francisco'
    }
    
    result = predict(test_startup)
    print(f"\nFinal Result: {result}")
