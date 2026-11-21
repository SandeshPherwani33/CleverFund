import json
import os
import importlib.util

# Load the root `app.py` module explicitly to avoid import name collisions
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("root_app", os.path.join(ROOT, "app.py"))
root_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_app)

client = root_app.app.test_client()

# 1. Login
login_resp = client.post('/login', data={'email': 'admin@example.com', 'password': 'password123'})
print("Login Status:", login_resp.status_code)

# 2. Predict
predict_resp = client.post('/predict', 
    data=json.dumps({
        "funding_amount": 5000000,
        "employees": 50,
        "industry": "Technology / Software",
        "revenue": 2000000,
        "location": "Bangalore"
    }),
    content_type='application/json'
)
print("Predict Status:", predict_resp.status_code)
print("Predict Body:", predict_resp.data.decode('utf-8'))
