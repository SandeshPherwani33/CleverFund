# CleverFund Backend — Complete Documentation

## Project Overview

CleverFund is a **Startup Success Prediction** platform. This backend powers every
page and feature of the existing frontend: authentication, rule-based + ML
predictions, analytics charts, dataset reports, and prediction history.

---

## Folder Structure

```
cleverfund_backend/
│
├── app.py                        ← Flask entry point (run this)
├── requirements.txt              ← Python dependencies
├── .env.example                  ← Environment variable template
│
├── models/
│   ├── __init__.py
│   └── database.py               ← SQLite schema + connection helper
│
├── services/
│   ├── __init__.py
│   ├── auth_service.py           ← register / verify users (bcrypt hashing)
│   ├── prediction_service.py     ← rule-based scoring, ML wrapper, DB CRUD
│   └── dataset_service.py        ← CSV loading, dashboard/analytics payloads
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                   ← /login  /logout  /api/register
│   ├── pages.py                  ← / /reports /analytics /predictions /compare
│   └── api.py                    ← all /api/* and /predict endpoints
│
├── templates/                    ← (copy from frontend ZIP — do not modify)
│   ├── base.html
│   ├── login.html
│   ├── index.html
│   ├── reports.html
│   ├── analytics.html
│   ├── predictions.html
│   └── compare.html
│
├── static/                       ← (copy from frontend ZIP — do not modify)
│   ├── css/style.css
│   └── js/script.js  analytics.js  layout.js  reports.js
│
└── data/
    ├── cleverfund.db             ← SQLite database (auto-created on first run)
    ├── combined_dataset.csv      ← startup dataset (copy from ZIP)
    └── predictions/              ← (legacy JSON files — no longer used)
```

---

## Setup & Run Instructions

### 1. Prerequisites

- Python 3.9 or higher
- pip

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Copy frontend files

From the original `capstone front` ZIP, copy:

```
capstone front/templates/  →  cleverfund_backend/templates/
capstone front/static/     →  cleverfund_backend/static/
capstone front/data/combined_dataset.csv  →  cleverfund_backend/data/combined_dataset.csv
```

If you also want the ML model:
```
capstone front/models/startup_model.pkl       →  cleverfund_backend/models/startup_model.pkl
capstone front/models/preprocessing_info.pkl  →  cleverfund_backend/models/preprocessing_info.pkl
capstone front/predict_startup_success.py     →  cleverfund_backend/predict_startup_success.py
```

### 4. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env with your SESSION_SECRET
```

### 5. Run the server

```bash
# Development
python app.py

# Production
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

Open your browser at **http://localhost:5000**

### 6. First login

The system uses a real database now. Register an account via:

```bash
curl -X POST http://localhost:5000/api/register \
     -H "Content-Type: application/json" \
     -d '{"email": "you@example.com", "password": "yourpassword"}'
```

Then log in at `/login` with those credentials.

---

## Database

SQLite file: `data/cleverfund.db` (auto-created on startup)

### Tables

**`users`**
| Column        | Type    | Notes                       |
|---------------|---------|-----------------------------|
| id            | INTEGER | Primary key, autoincrement  |
| email         | TEXT    | Unique, lowercase           |
| password_hash | TEXT    | bcrypt hash                 |
| created_at    | TEXT    | ISO datetime                |

**`predictions`**
| Column         | Type    | Notes                          |
|----------------|---------|--------------------------------|
| id             | TEXT    | UUID primary key               |
| user_email     | TEXT    | Foreign key → users.email      |
| startup_name   | TEXT    | Optional                       |
| industry       | TEXT    |                                |
| location       | TEXT    |                                |
| funding_amount | REAL    |                                |
| employees      | INTEGER |                                |
| revenue        | REAL    |                                |
| funding_round  | TEXT    | Pre-seed / Seed / Series A+    |
| years_operation| REAL    | Optional                       |
| probability    | REAL    | 0–100                          |
| result         | TEXT    | 'Success' or 'Failure'         |
| scores_json    | TEXT    | JSON — score breakdown         |
| feature_json   | TEXT    | JSON — feature importance      |
| recs_json      | TEXT    | JSON — recommendations         |
| model_type     | TEXT    | 'rule-based' or 'ML-...'       |
| created_at     | TEXT    | ISO datetime                   |

---

## API Endpoints

### Authentication

#### `POST /api/register`
Create a new user account.

**Request**
```json
{ "email": "user@example.com", "password": "mypassword" }
```

**Response 200**
```json
{ "ok": true, "email": "user@example.com" }
```

**Response 400**
```json
{ "ok": false, "error": "An account with this email already exists." }
```

---

#### `POST /login`  *(form POST)*
Standard HTML form login. Used by `login.html`.

| Field    | Type   |
|----------|--------|
| email    | string |
| password | string |

Redirects to `/` on success; re-renders login with error on failure.

---

#### `GET /logout`
Clears session and redirects to `/login`.

---

### Prediction

#### `POST /predict`  🔒
Run the **rule-based** weighted-score prediction.

**Request body**
```json
{
  "funding_amount":  5000000,
  "employees":       50,
  "industry":        "Technology / Software",
  "revenue":         2000000,
  "location":        "Bangalore",
  "startup_name":    "Velocity AI",
  "funding_round":   "Seed",
  "years_operation": 2.5
}
```

**Response 200**
```json
{
  "probability": 65.0,
  "result": "Success",
  "scores": {
    "funding":  25.0,
    "team":     5.0,
    "revenue":  5.0,
    "industry": 20.0,
    "location": 10.0,
    "total":    65.0
  },
  "feature_importance": [
    { "feature": "Funding",   "value": 38.5, "score": 25.0 },
    { "feature": "Team Size", "value": 7.7,  "score": 5.0  },
    { "feature": "Revenue",   "value": 7.7,  "score": 5.0  },
    { "feature": "Industry",  "value": 30.8, "score": 20.0 },
    { "feature": "Location",  "value": 15.4, "score": 10.0 }
  ],
  "recommendations": [
    {
      "type":        "team",
      "priority":    "high",
      "title":       "Expand Team Size",
      "description": "Team size is below optimal levels for your industry.",
      "suggestion":  "Aim for 50+ employees to strengthen operational capacity."
    }
  ],
  "prediction_id": "3f7a1b2c-..."
}
```

**Scoring formula**
```
funding_score  = min(funding / ₹5M, 1.0) × 25
team_score     = min(employees / 200, 1.0) × 20
revenue_score  = min(revenue / ₹10M, 1.0) × 25
industry_bonus = Tech/AI → 20 | Health/Finance → 15 | Retail → 8 | Other → 10
location_bonus = Major hub (SF, NYC, Bangalore, Mumbai…) → 10 | Other → 5

probability = max(5, min(100, sum of all scores))
result      = "Success" if probability >= 50 else "Failure"
```

---

#### `POST /api/ml-predict`  🔒
Run the trained **RandomForest + SMOTE** ML model.

**Request body** — same fields as `/predict`

**Response 200**
```json
{
  "prediction":          "Success",
  "confidence":          "High",
  "success_probability": 78,
  "failure_probability": 22,
  "probabilities":       { "Success": 0.78, "Failure": 0.22 },
  "recommendations":     [...],
  "prediction_id":       "uuid",
  "model_type":          "ML-RandomForest-SMOTE"
}
```

**Response 503** (model not trained)
```json
{
  "error":    "ML model not available.",
  "hint":     "Run 'python train.py' to train the model first.",
  "fallback": "Use the rule-based /predict endpoint instead."
}
```

---

#### `POST /api/ml-batch-predict`  🔒
Predict for multiple startups at once.

**Request body**
```json
{
  "startups": [
    { "funding_amount": 5000000, "employees": 50, "industry": "Technology / Software", "revenue": 2000000, "location": "Bangalore" },
    { "funding_amount": 1000000, "employees": 10, "industry": "Retail",                "revenue": 300000,  "location": "Delhi"     }
  ]
}
```

**Response 200**
```json
{ "results": [...], "count": 2, "model_type": "ML-RandomForest-SMOTE" }
```

---

### Prediction History

#### `GET /api/prediction-history`  🔒
Return the logged-in user's prediction history (newest first).

Query params:
- `limit` — max records to return (default 100, max 500)

**Response 200**
```json
{
  "predictions": [
    {
      "id":               "uuid",
      "name":             "Technology / Software Startup #1",
      "industry":         "Technology / Software",
      "location":         "Bangalore",
      "funding":          5000000,
      "employees":        50,
      "revenue":          2000000,
      "probability":      65.0,
      "result":           "Success",
      "scores":           { ... },
      "feature_importance": [ ... ],
      "recommendations":  [ ... ],
      "model_type":       "rule-based",
      "timestamp":        "2025-04-26T10:30:00"
    }
  ]
}
```

---

#### `DELETE /api/prediction-history/<prediction_id>`  🔒
Delete a specific prediction.

**Response 200**
```json
{ "success": true }
```

**Response 404**
```json
{ "error": "Prediction not found." }
```

---

### Dashboard & Analytics

#### `GET /api/dashboard-data`  🔒
Returns all data needed to render the dashboard page charts.

**Response 200**
```json
{
  "ok": true,
  "stats": {
    "total":        5000,
    "success_rate": 62.4,
    "failed":       1880
  },
  "growth": {
    "labels": ["S1","S2","S3","S4","S5","S6","S7","S8"],
    "values": [625, 625, 625, 625, 625, 625, 625, 625]
  },
  "outcome": {
    "labels": ["Success","Failure"],
    "values": [3120, 1880]
  },
  "industry": {
    "labels": ["Technology / Software","Healthcare","Finance","Retail","Other"],
    "counts": [1200, 800, 600, 500, 1900]
  },
  "funding_revenue": {
    "labels":          ["Q1","Q2","Q3","Q4"],
    "funding_indexed": [80.0, 60.0, 100.0, 90.0],
    "revenue_indexed": [70.0, 80.0, 65.0, 100.0]
  },
  "recent_activity": [
    { "name": "TechCo", "funding": "₹5.0M", "result": "Success", "probability": "72.0%" }
  ]
}
```

---

#### `GET /api/analytics-data`  🔒
Returns KPIs and chart data for the analytics page.

**Response 200**
```json
{
  "ok": true,
  "kpis": {
    "median_probability": 62.4,
    "volatility":         "Low"
  },
  "volume": {
    "labels": ["S1","S2","S3","S4","S5","S6","S7","S8"],
    "values": [625, 625, 625, 625, 625, 625, 625, 625]
  },
  "radar": {
    "labels":    ["Funding","Team","Revenue","Success Rate","Scale","Diversity"],
    "portfolio": [50.0, 30.0, 20.0, 62.4, 50.0, 70.0],
    "benchmark": [60, 55, 60, 50, 70, 65]
  },
  "region": {
    "labels": ["Bangalore","Mumbai","Delhi","Hyderabad","Pune"],
    "rates":  [71.2, 68.5, 65.0, 63.4, 60.1]
  }
}
```

---

#### `GET /api/dataset/export`  🔒
Download the loaded CSV dataset.

Returns `text/csv` with `Content-Disposition: attachment`.

---

### Page Routes (HTML)

All require login — redirect to `/login?next=<url>` if unauthenticated.

| Route          | Template          | Description                  |
|----------------|-------------------|------------------------------|
| `GET /`        | index.html        | Dashboard + prediction form  |
| `GET /reports` | reports.html      | Dataset table + KPIs         |
| `GET /analytics` | analytics.html  | Chart analytics              |
| `GET /predictions` | predictions.html | User's prediction history |
| `GET /compare` | compare.html      | Side-by-side comparison      |

---

## Environment Variables

| Variable             | Default                        | Description                      |
|----------------------|--------------------------------|----------------------------------|
| `SESSION_SECRET`     | `cleverfund-dev-secret-...`    | Flask session signing key        |
| `DB_PATH`            | `data/cleverfund.db`           | SQLite database file path        |
| `STARTUP_DATASET_PATH` | `data/combined_dataset.csv` | Startup dataset CSV path         |
| `PORT`               | `5000`                         | HTTP port                        |

---

## Connecting Frontend to Backend

The frontend is already wired to the correct API endpoints. Here's the mapping:

| Frontend action              | JS file       | API call                          |
|------------------------------|---------------|-----------------------------------|
| Dashboard charts load        | script.js     | `GET /api/dashboard-data`         |
| Submit prediction form       | script.js     | `POST /predict`                   |
| Toggle ML model              | script.js     | `POST /api/ml-predict`            |
| Analytics charts load        | analytics.js  | `GET /api/analytics-data`         |
| Load prediction history      | predictions.html | `GET /api/prediction-history`  |
| Delete a prediction          | predictions.html | `DELETE /api/prediction-history/<id>` |
| Export CSV                   | reports.html  | `GET /api/dataset/export`         |
| Login form submit            | login.html    | `POST /login`                     |
| Logout link                  | base.html     | `GET /logout`                     |

**No changes to any frontend file are required.**  
Just run the backend and open `http://localhost:5000`.

---

## Optional: Enable ML Model

1. Copy `predict_startup_success.py` and the `models/` folder from the original ZIP.
2. Install extra deps:
   ```bash
   pip install scikit-learn imbalanced-learn joblib
   ```
3. Train the model (if `.pkl` files are missing):
   ```bash
   python train.py
   ```
4. The toggle switch on the prediction form will now use the ML endpoint.

---

## Architecture Diagram

```
Browser
  │
  ├── GET /login          → routes/auth.py   → render login.html
  ├── POST /login         → routes/auth.py   → services/auth_service.py → SQLite
  │
  ├── GET /               → routes/pages.py  → render index.html
  ├── GET /reports        → routes/pages.py  → services/dataset_service.py → CSV
  │
  ├── POST /predict       → routes/api.py    → services/prediction_service.py → SQLite
  ├── POST /api/ml-predict→ routes/api.py    → predict_startup_success.py (optional)
  │
  ├── GET /api/dashboard-data  → routes/api.py → services/dataset_service.py → CSV
  ├── GET /api/analytics-data  → routes/api.py → services/dataset_service.py → CSV
  │
  └── GET /api/prediction-history → routes/api.py → services/prediction_service.py → SQLite
```
