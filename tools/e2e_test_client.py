import os, sys
from pathlib import Path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load .env into this process so LLM calls will have OPENAI_API_KEY
# Check root .env first, then fall back to cleverfund_backend/.env
env_paths = [
    Path(ROOT) / '.env',  # root .env
    Path(ROOT) / 'cleverfund_backend' / '.env',  # backend .env
]

for env_path in env_paths:
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)

# Debug: confirm key is loaded
has_key = bool(os.environ.get('OPENAI_API_KEY'))
print(f'DEBUG: OPENAI_API_KEY present in os.environ: {has_key}')

# Ensure cleverfund_backend package modules (models, routes, services) are importable
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(ROOT, 'cleverfund_backend'))

from cleverfund_backend import app as clever_app
from cleverfund_backend.routes import api as api_mod

flask_app = getattr(clever_app, 'app')
client = flask_app.test_client()

# set a logged-in user
with client.session_transaction() as sess:
    sess['user'] = 'tester@example.com'

import json

print('Using Flask test client for E2E test')

# ML predict
payload = {
    'funding_amount': 250000,
    'employees': 8,
    'industry': 'Technology',
    'revenue': 40000,
    'location': 'Bengaluru',
    'startup_name': 'E2E Test Startup'
}
resp = client.post('/api/ml-predict', json=payload)
print('/api/ml-predict status:', resp.status_code)
ml = resp.get_json()
print('body keys:', list(ml.keys()) if ml else None)
if ml:
    print('  prediction:', ml.get('prediction'))
    print('  success_probability:', ml.get('success_probability'))
    print('  ai_analysis:', ml.get('ai_analysis'))

# AI analysis
ai_payload = {
    'startup_name': payload['startup_name'],
    'industry': payload['industry'],
    'location': payload['location'],
    'funding_amount': payload['funding_amount'],
    'employees': payload['employees'],
    'revenue': payload['revenue'],
    'ml_result': {
        'prediction': ml.get('prediction'),
        'success_probability': ml.get('success_probability'),
        'failure_probability': ml.get('failure_probability')
    }
}
ai_resp = client.post('/api/ai-analysis', json=ai_payload)
print('/api/ai-analysis status:', ai_resp.status_code)
print('body:', ai_resp.get_json())

# AI question
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
        'prediction': ml.get('prediction'),
        'success_probability': ml.get('success_probability'),
        'failure_probability': ml.get('failure_probability')
    }
}
q_resp = client.post('/api/ai-question', json=q_payload)
print('/api/ai-question status:', q_resp.status_code)
print('body:', q_resp.get_json())

# Dataset insights
ds_resp = client.get('/api/ai-dataset-insights')
print('/api/ai-dataset-insights status:', ds_resp.status_code)
print('body keys:', list(ds_resp.get_json().keys()))
print('E2E test complete')
