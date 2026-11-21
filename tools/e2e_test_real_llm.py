import os
import requests
import json

BASE = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')

print('Base URL:', BASE)
print('OPENAI_API_KEY set:', bool(os.environ.get('OPENAI_API_KEY')))

s = requests.Session()

# 1. Login (any non-empty email/password accepted)
login_resp = s.post(f"{BASE}/login", data={'email': 'tester@example.com', 'password': 'password'})
print('Login status:', login_resp.status_code)

# 2. Generate ML prediction
payload = {
    'funding_amount': 250000,
    'employees': 8,
    'industry': 'Technology',
    'revenue': 40000,
    'location': 'Bengaluru',
    'startup_name': 'E2E Test Startup'
}
print('\nPosting /api/ml-predict with payload:')
print(json.dumps(payload, indent=2))
mlr = s.post(f"{BASE}/api/ml-predict", json=payload)
print('ML predict status:', mlr.status_code)
try:
    mlj = mlr.json()
except Exception:
    print('Failed to decode ML response body');
    print(mlr.text)
    raise

print('ML response keys:', list(mlj.keys()))
print('Prediction:', mlj.get('prediction'))
print('Success probability:', mlj.get('success_probability'))
print('Failure probability:', mlj.get('failure_probability'))

# 3. Call AI analysis endpoint
print('\nCalling /api/ai-analysis...')
ai_payload = {
    'startup_name': payload['startup_name'],
    'industry': payload['industry'],
    'location': payload['location'],
    'funding_amount': payload['funding_amount'],
    'employees': payload['employees'],
    'revenue': payload['revenue'],
    'ml_result': {
        'prediction': mlj.get('prediction'),
        'success_probability': mlj.get('success_probability'),
        'failure_probability': mlj.get('failure_probability')
    }
}
ai_resp = s.post(f"{BASE}/api/ai-analysis", json=ai_payload)
print('AI analysis status:', ai_resp.status_code)
print('AI analysis body:', ai_resp.text[:1000])

# 4. Ask follow-up question
print('\nCalling /api/ai-question...')
q_payload = {
    'question': 'Why is my startup predicted this way and what should I improve?',
    'startup_data': {
        'startup_name': payload['startup_name'],
        'industry': payload['industry'],
        'location': payload['location'],
        'funding_amount': payload['funding_amount'],
        'employees': payload['employees'],
        'revenue': payload['revenue']
    },
    'ml_result': {
        'prediction': mlj.get('prediction'),
        'success_probability': mlj.get('success_probability'),
        'failure_probability': mlj.get('failure_probability')
    }
}
q_resp = s.post(f"{BASE}/api/ai-question", json=q_payload)
print('AI question status:', q_resp.status_code)
print('AI question body:', q_resp.text[:1000])

# 5. Dataset insights
print('\nCalling /api/ai-dataset-insights...')
ds = s.get(f"{BASE}/api/ai-dataset-insights")
print('Dataset insights status:', ds.status_code)
print('Dataset insights body:', ds.text[:1000])

print('\nDone')
