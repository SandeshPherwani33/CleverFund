"""Quick smoke tests for backend endpoints."""
import requests
import json
import time
import sys

# Give server time to start
time.sleep(2)

BASE_URL = 'http://127.0.0.1:5000'

print('=== BACKEND SMOKE TESTS ===\n')

# Test 1: Login page
print('[TEST 1] Login page access:')
try:
    r = requests.get(f'{BASE_URL}/login', timeout=5)
    print(f'  Status: {r.status_code}')
    print(f'  Success: {"YES" if r.status_code == 200 else "NO"}')
except Exception as e:
    print(f'  Error: {str(e)[:80]}')

# Test 2: Dashboard (should redirect or 401 without auth)
print('\n[TEST 2] Dashboard data endpoint (no auth):')
try:
    r = requests.get(f'{BASE_URL}/api/dashboard-data', timeout=5)
    print(f'  Status: {r.status_code}')
    is_protected = r.status_code in [302, 401, 403]
    print(f'  Protected: {"YES" if is_protected else "NO"} (auth working)')
except Exception as e:
    print(f'  Error: {str(e)[:80]}')

# Test 3: ML predict (should require auth)
print('\n[TEST 3] ML predict endpoint (no auth):')
try:
    payload = {
        'startup_name': 'TestCorp',
        'industry': 'Technology',
        'location': 'Bengaluru',
        'funding_amount': 5000000,
        'revenue': 1000000,
        'employees': 50
    }
    r = requests.post(f'{BASE_URL}/api/ml-predict', json=payload, timeout=5)
    print(f'  Status: {r.status_code}')
    is_protected = r.status_code in [302, 401, 403]
    print(f'  Protected: {"YES" if is_protected else "NO"} (auth working)')
except Exception as e:
    print(f'  Error: {str(e)[:80]}')

print('\n=== SMOKE TEST COMPLETE ===')
