"""
Startup Success Prediction Model Training with SMOTE
Handles class imbalance and trains a RandomForest classifier
"""

import os
import logging
from pathlib import Path
from typing import Tuple, Dict

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from imblearn.over_sampling import SMOTE
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import visualization module
try:
    from visualizations import (
        plot_class_distribution,
        plot_feature_importance,
        plot_confusion_matrix,
        generate_training_report
    )
    VIZ_AVAILABLE = True
except ImportError:
    VIZ_AVAILABLE = False
    logger.warning("Visualization module not available")

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Default CSV paths
DEFAULT_CSV = DATA_DIR / "ekdum_final_industry_fixed (1).xlsx"
DEFAULT_FAILURE_CSV = DATA_DIR / "cleaned_failure.csv"


def load_dataset(csv_path: str = None) -> pd.DataFrame:
    """
    Load startup dataset from CSV or Excel
    Handle missing values (median for numeric, mode for categorical)
    """
    if csv_path is None:
        csv_path = str(DEFAULT_CSV)
    
    logger.info(f"Loading dataset from: {csv_path}")
    
    # Try to load from provided path
    if os.path.exists(csv_path):
        if csv_path.endswith('.xlsx') or csv_path.endswith('.xls'):
            df = pd.read_excel(csv_path)
        else:
            df = pd.read_csv(csv_path)
        logger.info(f"Dataset shape: {df.shape}")
        logger.info(f"Columns: {df.columns.tolist()}")
        return df
    
    # If CSV doesn't exist, look for Excel files in the data directory
    data_dir = DATA_DIR
    if os.path.isdir(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith(('.xlsx', '.xls')):
                xlsx_path = os.path.join(data_dir, file)
                logger.info(f"CSV not found, loading Excel file: {xlsx_path}")
                df = pd.read_excel(xlsx_path)
                logger.info(f"Dataset shape: {df.shape}")
                logger.info(f"Columns: {df.columns.tolist()}")
                return df
    
    raise FileNotFoundError(f"Dataset not found: {csv_path} (also checked for .xlsx files in {data_dir})")


def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Preprocess data: handle missing values, normalize columns
    Returns: cleaned dataframe and preprocessing metadata
    """
    df = df.copy()
    preprocessing_info = {}
    
    logger.info("\n=== DATA PREPROCESSING ===")
    logger.info(f"Initial missing values:\n{df.isnull().sum()}")
    
    # Standardize column names
    df.columns = [col.strip().lower().replace(" ", "_").replace("-", "_") for col in df.columns]
    
    # Handle missing values for numeric columns (fill with median)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if df[col].isnull().any():
            median_val = df[col].median()
            df[col].fillna(median_val, inplace=True)
            preprocessing_info[f"{col}_median"] = median_val
            logger.info(f"Filled {col} missing values with median: {median_val}")
    
    # Handle missing values for categorical columns (fill with mode)
    categorical_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in categorical_cols:
        if df[col].isnull().any():
            mode_val = df[col].mode()[0] if not df[col].mode().empty else "Unknown"
            df[col].fillna(mode_val, inplace=True)
            preprocessing_info[f"{col}_mode"] = mode_val
            logger.info(f"Filled {col} missing values with mode: {mode_val}")
    
    logger.info(f"\nMissing values after handling:\n{df.isnull().sum()}")
    
    return df, preprocessing_info


def encode_features(df: pd.DataFrame, label_encoders: Dict = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Encode categorical variables using LabelEncoder
    If label_encoders provided, use existing encoders (for prediction)
    Otherwise, create and fit new encoders (for training)
    """
    df = df.copy()
    if label_encoders is None:
        label_encoders = {}
    
    logger.info("\n=== FEATURE ENCODING ===")
    
    # Find all object/string columns and encode them
    categorical_cols = df.select_dtypes(include=['object', 'string']).columns
    
    for col in categorical_cols:
        # Skip columns that should not be encoded (like names, startup names, etc)
        skip_cols = ['startup_name', 'investor', 'date']
        col_lower = col.lower()
        
        if any(skip in col_lower for skip in skip_cols):
            logger.info(f"Skipping {col} (skip list)")
            continue
        
        if col not in label_encoders:
            label_encoders[col] = LabelEncoder()
            df[col] = label_encoders[col].fit_transform(df[col].astype(str))
            logger.info(f"Encoded {col} - classes: {len(label_encoders[col].classes_)}")
        else:
            # Use existing encoder
            df[col] = label_encoders[col].transform(df[col].astype(str))
            logger.info(f"Applied existing encoder to {col}")
    
    return df, label_encoders


def prepare_features_and_target(
    df: pd.DataFrame,
    feature_cols: list = None,
    target_col: str = 'success'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare X (features) and y (target)
    Automatically maps column names to available features
    Encodes categorical target if needed
    """
    df = df.copy()
    
    # Normalize column names for matching
    df_cols_lower = {col.lower(): col for col in df.columns}
    
    # Try to find target column from alternatives
    target_alternatives = ['success', 'startup_status', 'status', 'label', 'target', 'result']
    actual_target_col = None
    
    for alt in target_alternatives:
        if alt in df_cols_lower:
            actual_target_col = df_cols_lower[alt]
            logger.info(f"Using target column: {actual_target_col}")
            break
    
    if actual_target_col is None:
        raise ValueError(f"Target column not found. Available columns: {df.columns.tolist()}")
    
    # Encode target if it's categorical
    if df[actual_target_col].dtype == 'object' or df[actual_target_col].dtype == 'string':
        target_encoder = LabelEncoder()
        y_encoded = target_encoder.fit_transform(df[actual_target_col].astype(str))
        logger.info(f"Encoded target {actual_target_col} - classes: {target_encoder.classes_}")
    else:
        y_encoded = df[actual_target_col].values
    
    # Map feature column names to available columns
    feature_mapping = {
        'funding_amount': ['funding_amount', 'fundingramount', 'investmentamount_usd', 'funding'],
        'num_employees': ['employees_count', 'num_employees', 'employee_count'],
        'industry': ['industry', 'sector'],
        'revenue': ['revenue', 'annual_revenue'],
        'location': ['city', 'location', 'region'],
        'founder_experience': ['founder_experience', 'experience'],
        'market_size': ['market_size'],
        'product_uniqueness_score': ['product_uniqueness_score'],
        'startup_age': ['startup_age'],
        'customer_retention_rate': ['customer_retention_rate'],
        'marketing_expense': ['marketing_expense'],
        'burn_rate': ['burn_rate'],
        'number_of_founders': ['number_of_founders', 'num_founders'],
    }
    
    # Find available feature columns
    available_cols = []
    for category, alternatives in feature_mapping.items():
        for alt in alternatives:
            if alt.lower() in df_cols_lower:
                available_cols.append(df_cols_lower[alt.lower()])
                logger.info(f"Using feature: {df_cols_lower[alt.lower()]}")
                break
    
    if not available_cols:
        # Fallback: use all numeric columns except target
        available_cols = [col for col in df.columns 
                         if df[col].dtype in [np.number] and col != actual_target_col]
        logger.info(f"Using fallback features (numeric columns): {available_cols}")
    
    X = df[available_cols].values
    
    logger.info(f"Features shape: {X.shape}")
    logger.info(f"Target shape: {y_encoded.shape}")
    
    return X, y_encoded, available_cols


def print_class_distribution(y: np.ndarray, label: str = ""):
    """Print class distribution statistics"""
    unique, counts = np.unique(y, return_counts=True)
    total = len(y)
    logger.info(f"\n{'='*50}")
    logger.info(f"Class Distribution {label}")
    logger.info(f"{'='*50}")
    for cls, count in zip(unique, counts):
        percentage = (count / total) * 100
        logger.info(f"Class {int(cls)}: {count} samples ({percentage:.2f}%)")
    logger.info(f"Total: {total} samples")


def train_model(
    csv_path: str = None,
    test_size: float = 0.2,
    random_state: int = 42
) -> Dict:
    """
    Full training pipeline:
    1. Load and preprocess data
    2. Encode categorical variables
    3. Train/test split
    4. Apply SMOTE on training data
    5. Train RandomForest
    6. Save model and preprocessing info
    """
    logger.info("\n" + "="*70)
    logger.info("STARTUP SUCCESS PREDICTION - MODEL TRAINING PIPELINE")
    logger.info("="*70)
    
    # Step 1: Load and preprocess
    df = load_dataset(csv_path)
    df, preprocessing_info = preprocess_data(df)
    
    # Step 2: Encode features
    df, label_encoders = encode_features(df)
    
    # Step 3: Prepare features and target
    X, y, feature_cols = prepare_features_and_target(df)
    
    # Step 4: Train/test split
    logger.info(f"\n=== TRAIN/TEST SPLIT (80/20) ===")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    logger.info(f"Training set: {X_train.shape}")
    logger.info(f"Test set: {X_test.shape}")
    
    # Print class distribution BEFORE SMOTE
    print_class_distribution(y_train, "BEFORE SMOTE (Training Set)")
    print_class_distribution(y_test, "TEST SET")
    
    # Step 5: Apply SMOTE on training data ONLY
    logger.info(f"\n=== APPLYING SMOTE ===")
    logger.info("SMOTE parameters: random_state=42")
    
    smote = SMOTE(random_state=random_state)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    
    logger.info("SMOTE applied successfully!")
    
    # Print class distribution AFTER SMOTE
    print_class_distribution(y_train_res, "AFTER SMOTE (Training Set)")
    
    # Step 6: Train RandomForest
    logger.info(f"\n=== TRAINING RANDOM FOREST ===")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1,
        class_weight='balanced'
    )
    
    model.fit(X_train_res, y_train_res)
    logger.info("Model training completed!")
    
    # Step 7: Evaluate on test set
    logger.info(f"\n=== MODEL EVALUATION ===")
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    logger.info(f"\nClassification Report:\n{classification_report(y_test, y_pred)}")
    logger.info(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    logger.info(f"ROC-AUC Score: {roc_auc_score(y_test, y_pred_proba):.4f}")
    
    # Step 8: Feature importance
    logger.info(f"\n=== FEATURE IMPORTANCE ===")
    for feature, importance in zip(feature_cols, model.feature_importances_):
        logger.info(f"{feature}: {importance:.4f}")
    
    # Step 9: Generate visualizations
    if VIZ_AVAILABLE:
        logger.info(f"\n=== GENERATING VISUALIZATIONS ===")
        try:
            plot_class_distribution(y_train, y_train_res, "Class Distribution: Before and After SMOTE")
            plot_feature_importance(feature_cols, model.feature_importances_)
            plot_confusion_matrix(y_test, y_pred)
            generate_training_report({
                'test_accuracy': (y_pred == y_test).mean(),
                'roc_auc': roc_auc_score(y_test, y_pred_proba),
                'y_test': y_test,
                'y_pred': y_pred,
                'y_pred_proba': y_pred_proba
            })
            logger.info("Visualizations generated successfully!")
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
    
    # Step 10: Save model and metadata
    logger.info(f"\n=== SAVING ARTIFACTS ===")
    
    model_path = MODEL_DIR / "startup_model.pkl"
    joblib.dump(model, model_path)
    logger.info(f"Model saved: {model_path}")
    
    # Save preprocessing info
    preprocessing_path = MODEL_DIR / "preprocessing_info.pkl"
    preprocessing_data = {
        'label_encoders': label_encoders,
        'feature_cols': feature_cols,
        'preprocessing_info': preprocessing_info,
        'smote_random_state': random_state
    }
    joblib.dump(preprocessing_data, preprocessing_path)
    logger.info(f"Preprocessing info saved: {preprocessing_path}")
    
    logger.info("\n" + "="*70)
    logger.info("TRAINING PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("="*70)
    
    return {
        'model': model,
        'label_encoders': label_encoders,
        'feature_cols': feature_cols,
        'preprocessing_info': preprocessing_info,
        'metrics': {
            'test_accuracy': (y_pred == y_test).mean(),
            'roc_auc': roc_auc_score(y_test, y_pred_proba),
            'y_test': y_test,
            'y_pred': y_pred,
            'y_pred_proba': y_pred_proba
        }
    }


if __name__ == "__main__":
    # Train the model
    results = train_model()
