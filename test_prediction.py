#!/usr/bin/env python3
"""
Test script for prediction formula and score breakdown.
"""

import os
import importlib.util

# Load the root `app.py` module explicitly to avoid import name collisions
ROOT = os.path.abspath(os.path.dirname(__file__))
spec = importlib.util.spec_from_file_location("root_app", os.path.join(ROOT, "app.py"))
root_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_app)
predict_startup_success = root_app.predict_startup_success

def test_prediction():
    # Test data
    funding = 2000000  # $2M
    employees = 50
    industry = "Technology / Software"
    revenue = 1000000  # $1M
    location = "San Francisco, CA"

    # Calculate scores manually (same logic as in JavaScript)
    funding_score = min(funding / 5000000, 1.0) * 25
    team_score = min(employees / 200, 1.0) * 20
    revenue_score = min(revenue / 10000000, 1.0) * 25

    industry_bonus = 0
    if industry.lower().find('technology') >= 0 or industry.lower().find('software') >= 0:
        industry_bonus = 20
    elif industry.lower().find('healthcare') >= 0 or industry.lower().find('biotech') >= 0:
        industry_bonus = 15
    elif industry.lower().find('finance') >= 0 or industry.lower().find('fintech') >= 0:
        industry_bonus = 10

    location_bonus = 0
    if location.lower().find('san francisco') >= 0 or location.lower().find('silicon valley') >= 0:
        location_bonus = 10
    elif location.lower().find('new york') >= 0 or location.lower().find('boston') >= 0:
        location_bonus = 8
    elif location.lower().find('austin') >= 0 or location.lower().find('seattle') >= 0:
        location_bonus = 5

    total_score = funding_score + team_score + revenue_score + industry_bonus + location_bonus

    print("=== Prediction Test ===")
    print(f"Input: funding=${funding:,}, employees={employees}, industry='{industry}', revenue=${revenue:,}, location='{location}'")
    print()
    print("Score Breakdown:")
    print(f"Funding Score: {funding_score:.1f}")
    print(f"Team Score: {team_score:.1f}")
    print(f"Revenue Score: {revenue_score:.1f}")
    print(f"Industry Bonus: {industry_bonus:.1f}")
    print(f"Location Bonus: {location_bonus:.1f}")
    print(f"Total Score: {total_score:.1f}")
    print()

    # Test the actual function
    probability, result, scores, feature_importance = predict_startup_success(funding, employees, industry, revenue, location)
    print(f"Backend Result: {probability}% probability, {result}")

if __name__ == "__main__":
    test_prediction()