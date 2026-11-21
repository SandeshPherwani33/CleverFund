import requests
r = requests.get('http://localhost:5000/api/analytics-data')
print(r.json())