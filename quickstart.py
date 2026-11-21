#!/usr/bin/env python3
"""
Quick Start Script - Startup Success Prediction ML System
Run this to verify everything is set up correctly
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """Check if all required packages are installed"""
    print("\n✓ Checking dependencies...")
    required = [
        'flask', 'pandas', 'numpy', 'sklearn', 'imblearn', 
        'joblib', 'matplotlib', 'seaborn'
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg} (MISSING)")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    return True

def check_data():
    """Check if training data exists"""
    print("\n✓ Checking data files...")
    
    data_paths = [
        'data/combined_dataset.xlsx',
        'data/cleaned_failure.csv',
        'data/cleaned_funding.csv'
    ]
    
    found = False
    for path in data_paths:
        if os.path.exists(path):
            print(f"  ✓ {path} (found)")
            found = True
    
    if not found:
        print("  ⚠ No training data found")
        print("  Place CSV file in 'data/' directory")
        return False
    return True

def check_models():
    """Check if models are trained"""
    print("\n✓ Checking trained models...")
    
    model_files = [
        'models/startup_model.pkl',
        'models/preprocessing_info.pkl'
    ]
    
    for path in model_files:
        if os.path.exists(path):
            print(f"  ✓ {path} (found)")
        else:
            print(f"  ✗ {path} (NOT FOUND)")
            return False
    
    print("\n✓ Models ready for predictions!")
    return True

def display_api_examples():
    """Display API usage examples"""
    print("\n" + "="*60)
    print("API EXAMPLES")
    print("="*60)
    
    print("\n1. RULE-BASED PREDICTION (Legacy)")
    print("   curl -X POST http://localhost:5000/predict \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"funding_amount": 2500000, "employees": 25, ')
    print('     "industry": "Technology", "revenue": 500000, ')
    print('     "location": "San Francisco"}\'')
    
    print("\n2. ML PREDICTION (New - with SMOTE)")
    print("   curl -X POST http://localhost:5000/api/ml-predict \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"funding_amount": 2500000, "employees": 25, ')
    print('     "industry": "Technology", "revenue": 500000, ')
    print('     "location": "San Francisco"}\'')
    
    print("\n3. BATCH PREDICTIONS")
    print("   curl -X POST http://localhost:5000/api/ml-batch-predict \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"startups": [{...}, {...}]}\'')

def display_features():
    """Display key features"""
    print("\n" + "="*60)
    print("KEY FEATURES")
    print("="*60)
    
    features = [
        ("SMOTE Balancing", "Handles class imbalance in training"),
        ("Cold Start Handling", "Fills missing values intelligently"),
        ("Dual Models", "Switch between Rule-Based and ML"),
        ("Feature Importance", "See what drives predictions"),
        ("Batch Processing", "Predict multiple startups"),
        ("Recommendations", "Get AI-powered suggestions"),
        ("Visualizations", "Charts for SMOTE and features"),
        ("Logging", "Detailed training and prediction logs"),
    ]
    
    for feature, description in features:
        print(f"\n✓ {feature}")
        print(f"  {description}")

def display_next_steps():
    """Display next steps"""
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    
    steps = [
        ("1. Install dependencies", "pip install -r requirements.txt"),
        ("2. Train model", "python train.py"),
        ("3. Run server", "python app.py"),
        ("4. Open browser", "http://localhost:5000"),
        ("5. Toggle to ML mode", "Click 'Model' toggle in dashboard"),
        ("6. Make predictions", "Fill form and submit"),
    ]
    
    for step, command in steps:
        print(f"\n{step}")
        if command:
            print(f"  $ {command}")

def main():
    """Main quick start check"""
    print("\n" + "="*60)
    print("STARTUP SUCCESS PREDICTION - QUICK START CHECK")
    print("="*60)
    
    all_good = True
    
    if not check_dependencies():
        all_good = False
    
    if not check_data():
        all_good = False
    
    if not check_models():
        print("\n⚠ Models not yet trained")
        print("Run: python train.py")
        all_good = False
    
    display_features()
    display_api_examples()
    display_next_steps()
    
    print("\n" + "="*60)
    if all_good:
        print("✓ EVERYTHING IS READY!")
        print("="*60)
        print("\nYou can now:")
        print("  1. Run the server: python app.py")
        print("  2. Open http://localhost:5000 in your browser")
        print("  3. Toggle to 'ML (SMOTE+RF)' model in the dashboard")
        print("  4. Make predictions with ML or Rule-Based methods")
    else:
        print("⚠ SETUP INCOMPLETE")
        print("="*60)
        print("\nPlease follow the Next Steps above")
    
    print("\n")

if __name__ == "__main__":
    main()
