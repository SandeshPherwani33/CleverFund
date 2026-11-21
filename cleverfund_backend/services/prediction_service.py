"""
services/prediction_service.py
-------------------------------
All prediction logic lives here:
  • rule_based_predict()   — weighted-score formula (always available)
  • generate_recommendations()
  • save_prediction()      — persists to SQLite
  • get_user_predictions() — loads from SQLite
  • delete_prediction()    — removes from SQLite

The ML model (RandomForest + SMOTE) is imported lazily; if the model
files are missing we fall back to the rule-based scorer gracefully.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Tuple

from ..models.database import get_db

# ── Optional ML model ────────────────────────────────────────────────────────
try:
    import predict_startup_success as _ml          # from the original project
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
#  Core scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

def rule_based_predict(
    funding_amount: float,
    employees: int,
    industry: str,
    revenue: float,
    location: str,
) -> Tuple[float, str, dict, list]:
    """
    Weighted-score formula.

    Returns
    -------
    (probability 0-100, 'Success'|'Failure', scores_dict, feature_importance_list)
    """
    funding_score  = min(funding_amount / 5_000_000, 1.0) * 25
    team_score     = min(employees / 200, 1.0) * 20
    revenue_score  = min(max(revenue, 0) / 10_000_000, 1.0) * 25

    industry_lower = (industry or "").lower()
    if any(x in industry_lower for x in ("tech", "software", "ai", "saas")):
        industry_bonus = 20
    elif any(x in industry_lower for x in ("health", "finance", "fintech")):
        industry_bonus = 15
    elif any(x in industry_lower for x in ("retail", "e-commerce", "commerce")):
        industry_bonus = 8
    else:
        industry_bonus = 10

    loc_lower = (location or "").lower()
    if any(
        x in loc_lower
        for x in (
            "san francisco", "new york", "boston", "austin",
            "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad",
            "pune", "gurugram", "ahmedabad", "kolkata",
        )
    ):
        location_bonus = 10
    else:
        location_bonus = 5

    raw = funding_score + team_score + revenue_score + industry_bonus + location_bonus
    probability = float(min(100, max(5, raw)))
    result      = "Success" if probability >= 50 else "Failure"

    scores = {
        "funding":  funding_score,
        "team":     team_score,
        "revenue":  revenue_score,
        "industry": float(industry_bonus),
        "location": float(location_bonus),
        "total":    raw,
    }

    total = sum([funding_score, team_score, revenue_score, industry_bonus, location_bonus])
    if total > 0:
        feature_importance = [
            {"feature": "Funding",   "value": (funding_score  / total) * 100, "score": funding_score},
            {"feature": "Team Size", "value": (team_score     / total) * 100, "score": team_score},
            {"feature": "Revenue",   "value": (revenue_score  / total) * 100, "score": revenue_score},
            {"feature": "Industry",  "value": (industry_bonus / total) * 100, "score": float(industry_bonus)},
            {"feature": "Location",  "value": (location_bonus / total) * 100, "score": float(location_bonus)},
        ]
    else:
        feature_importance = [
            {"feature": f, "value": 0.0, "score": 0.0}
            for f in ("Funding", "Team Size", "Revenue", "Industry", "Location")
        ]

    return probability, result, scores, feature_importance


def generate_recommendations(scores: dict) -> list:
    """
    Return up to 3 actionable recommendations sorted by priority.
    Each item: {type, priority, title, description, suggestion}
    """
    recs = []

    if scores.get("funding", 0) < 15:
        recs.append({
            "type": "funding", "priority": "high",
            "title": "Increase Funding",
            "description": "Your funding score is low. Consider raising more capital.",
            "suggestion":  "Target at least ₹2.5M in funding for better market positioning.",
        })
    if scores.get("team", 0) < 10:
        recs.append({
            "type": "team", "priority": "high",
            "title": "Expand Team Size",
            "description": "Team size is below optimal levels for your industry.",
            "suggestion":  "Aim for 50+ employees to strengthen operational capacity.",
        })
    if scores.get("revenue", 0) < 15:
        recs.append({
            "type": "revenue", "priority": "high",
            "title": "Revenue Growth",
            "description": "Focus on revenue generation to improve financial stability.",
            "suggestion":  "Implement aggressive customer acquisition and monetisation strategies.",
        })
    if scores.get("industry", 0) <= 10:
        recs.append({
            "type": "industry", "priority": "medium",
            "title": "Industry Focus",
            "description": "Consider pivoting to high-growth sectors.",
            "suggestion":  "Tech and Healthcare sectors show higher success rates in our data.",
        })
    if scores.get("location", 0) <= 5:
        recs.append({
            "type": "location", "priority": "medium",
            "title": "Strategic Location",
            "description": "Your location may not be optimal for startup success.",
            "suggestion":  "Consider relocating to major tech hubs like Bangalore or Mumbai.",
        })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 3))
    return recs[:3]


# ─────────────────────────────────────────────────────────────────────────────
#  ML wrapper
# ─────────────────────────────────────────────────────────────────────────────

def ml_predict(input_data: dict) -> dict:
    """
    Run the trained RandomForest+SMOTE model.
    Raises RuntimeError if model files are missing.
    Returns the raw dict from predict_startup_success.predict().
    """
    if not ML_AVAILABLE:
        raise RuntimeError("ML model unavailable. Run 'python train.py' first.")
    return _ml.predict(input_data)


def ml_batch_predict(input_list: list) -> list:
    """Batch version of ml_predict()."""
    if not ML_AVAILABLE:
        raise RuntimeError("ML model unavailable.")
    return _ml.batch_predict(input_list)


# ─────────────────────────────────────────────────────────────────────────────
#  Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_prediction(user_email: str, data: dict) -> str:
    """
    Persist a prediction to the MongoDB database.

    Parameters
    ----------
    user_email : the logged-in user's email
    data       : dict containing all prediction fields

    Returns
    -------
    The UUID string of the new prediction document.
    """
    prediction_id = str(uuid.uuid4())
    db = get_db()
    
    doc = {
        "id": prediction_id,
        "user_email": user_email,
        "startup_name": data.get("startup_name"),
        "industry": data.get("industry"),
        "location": data.get("location"),
        "funding_amount": data.get("funding_amount", 0),
        "employees": data.get("employees", 0),
        "revenue": data.get("revenue", 0),
        "funding_round": data.get("funding_round"),
        "years_operation": data.get("years_operation"),
        "probability": data.get("probability", 0),
        "result": data.get("result", "Unknown"),
        "scores_json": data.get("scores", {}),
        "feature_json": data.get("feature_importance", []),
        "recs_json": data.get("recommendations", []),
        "model_type": data.get("model_type", "rule-based"),
        "created_at": datetime.utcnow().isoformat(),
        # Optional flag indicating whether an AI analysis was generated
        "ai_analysis_generated": bool(data.get("ai_analysis_generated", False)),
    }
    
    db.predictions.insert_one(doc)
    return prediction_id


def get_user_predictions(user_email: str, limit: int = 100) -> list:
    """
    Return the user's prediction history as a list of dicts,
    newest first.
    """
    db = get_db()
    cursor = db.predictions.find({"user_email": user_email}).sort("created_at", -1).limit(limit)
    
    result = []
    for i, row in enumerate(cursor):
        result.append({
            "id":               row.get("id"),
            "name":             row.get("startup_name") or f"{row.get('industry') or 'Unknown'} Startup #{i+1}",
            "industry":         row.get("industry") or "Unknown",
            "location":         row.get("location") or "Unknown",
            "funding":          row.get("funding_amount", 0),
            "employees":        row.get("employees", 0),
            "revenue":          row.get("revenue", 0),
            "probability":      row.get("probability", 0),
            "result":           row.get("result", "Unknown"),
            "scores":           row.get("scores_json", {}),
            "feature_importance": row.get("feature_json", []),
            "recommendations":  row.get("recs_json", []),
            "model_type":       row.get("model_type", "rule-based"),
            "timestamp":        row.get("created_at", ""),
        })
    return result


def delete_prediction(user_email: str, prediction_id: str) -> bool:
    """
    Delete a prediction that belongs to user_email.
    Returns True if a document was actually deleted, False otherwise.
    """
    db = get_db()
    result = db.predictions.delete_one({"id": prediction_id, "user_email": user_email})
    return result.deleted_count > 0


# ─────────────────────────────────────────────────────────────────────────────
#  Utility
# ─────────────────────────────────────────────────────────────────────────────

def _safe_json(text: Optional[str]):
    """Safely parse a JSON string; return empty list/dict on failure."""
    if not text:
        return []
    try:
        return json.loads(text)
    except Exception:
        return []
