"""
Startup Success Prediction — Flask backend.
Charts and reports read from your dataset (data/ekdum_final_industry_fixed (1).xlsx or STARTUP_DATASET_PATH).
Prediction endpoint uses the same rule-based scorer as before.
"""

import os
from pathlib import Path
from functools import wraps
from typing import Optional, Tuple
import json
import uuid
from datetime import datetime
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from document_input import MAX_UPLOAD_SIZE, extract_uploaded_document

from dataset import (
    DEFAULT_CSV,
    build_analytics_payload,
    build_dashboard_payload,
    dataframe_to_csv_bytes,
    load_startup_dataset,
    prepare_report_rows,
)

# Import export utilities
try:
    from export_utils import generate_pdf_report, generate_share_url, get_shared_report
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    print("Warning: Export utilities not available")

# Import ML prediction module
try:
    import predict_startup_success as ml_predictor
    ML_AVAILABLE = True
except Exception as e:
    ML_AVAILABLE = False
    print(f"Warning: ML predictor not available: {e}")

try:
    from cleverfund_backend.services.ai_context_service import build_dataset_context
    from cleverfund_backend.services.llm_service import (
        answer_startup_question,
        answer_startup_question_with_history,
        generate_dataset_insights,
        generate_startup_analysis,
    )
    LLM_AVAILABLE = True
except Exception as e:
    LLM_AVAILABLE = False
    print(f"Warning: LLM service not available: {e}")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-cleverfund-secret-change-me")

# Prediction history storage
PREDICTIONS_DIR = Path("data/predictions")
PREDICTIONS_DIR.mkdir(exist_ok=True)

_df = None
_df_error: Optional[str] = None


def get_dataframe():
    """Lazy-load CSV once; cache error message if missing."""
    global _df, _df_error
    if _df_error is not None:
        return None
    if _df is None:
        try:
            _df = load_startup_dataset()
        except Exception as exc:  # noqa: BLE001
            _df_error = str(exc)
            return None
    return _df


def reset_dataframe():
    """Reset cached dataframe and error for testing/reloading."""
    global _df, _df_error
    _df = None
    _df_error = None


def predict_startup_success(
    funding_amount: float,
    employees: int,
    industry: str,
    revenue: float,
    location: str,
) -> Tuple[int, str, dict, list]:
    """
    Rule-based 'prediction': weighted score → probability % and label.
    Returns (probability 0–100, 'Success' or 'Failure', scores dict, feature_importance list).
    """
    funding_score = min(funding_amount / 5_000_000, 1.0) * 25
    team_score = min(employees / 200, 1.0) * 20
    revenue_score = min(max(revenue, 0) / 10_000_000, 1.0) * 25

    industry_lower = (industry or "").lower()
    industry_bonus = 10
    if "tech" in industry_lower or "software" in industry_lower or "ai" in industry_lower:
        industry_bonus = 20
    elif "health" in industry_lower or "finance" in industry_lower:
        industry_bonus = 15
    elif "retail" in industry_lower or "e-commerce" in industry_lower or "commerce" in industry_lower:
        industry_bonus = 8

    loc_lower = (location or "").lower()
    location_bonus = 5
    if any(
        x in loc_lower
        for x in (
            "san francisco",
            "new york",
            "boston",
            "austin",
            "bengaluru",
            "mumbai",
            "delhi",
            "hyderabad",
            "pune",
            "gurugram",
            "ahmedabad",
            "kolkata",
        )
    ):
        location_bonus = 10

    raw = funding_score + team_score + revenue_score + industry_bonus + location_bonus
    probability = int(round(min(100, max(5, raw))))

    result = "Success" if probability >= 50 else "Failure"

    # Calculate scores dict
    scores = {
        'funding': funding_score,
        'team': team_score,
        'revenue': revenue_score,
        'industry': industry_bonus,
        'location': location_bonus,
        'total': raw
    }

    # Calculate feature importance (normalized percentages)
    total_score = sum([funding_score, team_score, revenue_score, industry_bonus, location_bonus])
    if total_score > 0:
        feature_importance = [
            {'feature': 'Funding', 'value': (funding_score / total_score) * 100, 'score': funding_score},
            {'feature': 'Team Size', 'value': (team_score / total_score) * 100, 'score': team_score},
            {'feature': 'Revenue', 'value': (revenue_score / total_score) * 100, 'score': revenue_score},
            {'feature': 'Industry', 'value': (industry_bonus / total_score) * 100, 'score': industry_bonus},
            {'feature': 'Location', 'value': (location_bonus / total_score) * 100, 'score': location_bonus}
        ]
    else:
        feature_importance = [
            {'feature': 'Funding', 'value': 0, 'score': 0},
            {'feature': 'Team Size', 'value': 0, 'score': 0},
            {'feature': 'Revenue', 'value': 0, 'score': 0},
            {'feature': 'Industry', 'value': 0, 'score': 0},
            {'feature': 'Location', 'value': 0, 'score': 0}
        ]

    return probability, result, scores, feature_importance


def generate_recommendations(scores: dict, funding_amount: float, employees: int, industry: str, location: str) -> list:
    """Generate smart recommendations based on prediction scores."""
    recommendations = []

    # Funding recommendations
    if scores['funding'] < 15:
        recommendations.append({
            "type": "funding",
            "priority": "high",
            "title": "Increase Funding",
            "description": "Your funding score is low. Consider raising more capital to improve success chances.",
            "suggestion": "Target at least ₹2.5M in funding for better market positioning."
        })

    # Team recommendations
    if scores['team'] < 10:
        recommendations.append({
            "type": "team",
            "priority": "high",
            "title": "Expand Team Size",
            "description": "Team size is below optimal levels for your industry.",
            "suggestion": "Aim for 50+ employees to strengthen your operational capacity."
        })

    # Industry recommendations
    if scores['industry'] <= 10:
        recommendations.append({
            "type": "industry",
            "priority": "medium",
            "title": "Industry Focus",
            "description": "Consider pivoting to high-growth industries like Technology or Healthcare.",
            "suggestion": "Tech and Healthcare sectors show higher success rates in our data."
        })

    # Location recommendations
    if scores['location'] <= 5:
        recommendations.append({
            "type": "location",
            "priority": "medium",
            "title": "Strategic Location",
            "description": "Your location may not be optimal for startup success.",
            "suggestion": "Consider relocating to major tech hubs like San Francisco, New York, or Bangalore."
        })

    # Revenue recommendations
    if scores['revenue'] < 15:
        recommendations.append({
            "type": "revenue",
            "priority": "high",
            "title": "Revenue Growth",
            "description": "Focus on revenue generation to improve financial stability.",
            "suggestion": "Implement aggressive customer acquisition and monetization strategies."
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return recommendations[:3]  # Return top 3 recommendations


def save_prediction_history(user_id: str, prediction_data: dict) -> str:
    """Save prediction to user's history file."""
    prediction_id = str(uuid.uuid4())
    prediction_entry = {
        "id": prediction_id,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "data": prediction_data
    }

    user_file = PREDICTIONS_DIR / f"{user_id}.json"
    try:
        if user_file.exists():
            with open(user_file, 'r') as f:
                history = json.load(f)
        else:
            history = []

        history.append(prediction_entry)

        # Keep only last 100 predictions
        if len(history) > 100:
            history = history[-100:]

        with open(user_file, 'w') as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        print(f"Error saving prediction history: {e}")

    return prediction_id


def get_prediction_history(user_id: str, limit: int = 50) -> list:
    """Get user's prediction history."""
    user_file = PREDICTIONS_DIR / f"{user_id}.json"
    try:
        if user_file.exists():
            with open(user_file, 'r') as f:
                history = json.load(f)
            # Sort by timestamp (newest first)
            history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return history[:limit]
    except Exception as e:
        print(f"Error loading prediction history: {e}")
    return []


def load_prediction_history(user_id: str) -> list:
    """Load and format user's prediction history for API response."""
    history = get_prediction_history(user_id)
    formatted_predictions = []

    for entry in history:
        data = entry.get('data', {})
        formatted_predictions.append({
            "id": entry.get('id'),
            # Prefer an explicit `name` from the saved data; fall back to the
            # previous industry-based synthetic name when absent.
            "name": data.get('name') or f"{data.get('industry', 'Unknown')} Startup #{len(formatted_predictions) + 1}",
            "industry": data.get('industry', 'Unknown'),
            "location": data.get('location', 'Unknown'),
            "funding": data.get('funding_amount', 0),
            "employees": data.get('employees', 0),
            "revenue": data.get('revenue', 0),
            "probability": data.get('probability', 0),
            "result": data.get('result', 'Unknown'),
            "timestamp": entry.get('timestamp', ''),
            "scores": data.get('scores', {}),
            "feature_importance": data.get('feature_importance', []),
            "recommendations": data.get('recommendations', [])
        })

    return formatted_predictions


def delete_prediction_from_history(user_id: str, prediction_id: str) -> bool:
    """Delete a specific prediction from user's history."""
    user_file = PREDICTIONS_DIR / f"{user_id}.json"
    try:
        if user_file.exists():
            with open(user_file, 'r') as f:
                history = json.load(f)

            # Find and remove the prediction
            original_length = len(history)
            history = [entry for entry in history if entry.get('id') != prediction_id]

            if len(history) < original_length:
                with open(user_file, 'w') as f:
                    json.dump(history, f, indent=2)
                return True
    except Exception as e:
        print(f"Error deleting prediction: {e}")
    return False





def login_required_page(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            nxt = request.path
            if nxt and nxt != "/login":
                return redirect(url_for("login", next=nxt))
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def login_required_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized", "login": url_for("login")}), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()
        if email and password:
            session["user"] = email
            session.permanent = True
            nxt = request.args.get("next") or url_for("dashboard")
            if not nxt.startswith("/"):
                nxt = url_for("dashboard")
            return redirect(nxt)
        error = "Please enter both email and password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required_page
def dashboard():
    return render_template(
        "index.html",
        user_email=session.get("user"),
        active_page="dashboard",
    )


@app.route("/reports")
@login_required_page
def reports_page():
    df = get_dataframe()
    report_rows = []
    summary = {"quarter_total": "—", "avg_prob": "—", "success_share": "—"}
    if df is not None:
        n = len(df)
        report_rows = prepare_report_rows(df, limit=n, predict_fn=predict_startup_success)
        succ = int(df["success"].sum())
        fail = int((df["success"] == 0).sum())
        summary["quarter_total"] = str(n)
        summary["success_share"] = f"{round(100 * succ / n) if n else 0}%"
        sample = df.head(min(400, n))
        probs = []
        for _, r in sample.iterrows():
            p, _, _, _ = predict_startup_success(
                float(r["funding_amount"]),
                int(r["num_employees"]),
                str(r["industry"]),
                float(r["revenue"]),
                str(r["location"]),
            )
            probs.append(p)
        summary["avg_prob"] = f"{round(sum(probs) / len(probs))}%" if probs else "—"

    return render_template(
        "reports.html",
        user_email=session.get("user"),
        active_page="reports",
        report_rows=report_rows,
        summary=summary,
        dataset_error=_df_error,
    )


@app.route("/analytics")
@login_required_page
def analytics_page():
    return render_template(
        "analytics.html",
        user_email=session.get("user"),
        active_page="analytics",
    )


@app.route("/api/dashboard-data", methods=["GET"])
@login_required_api
def api_dashboard_data():
    df = get_dataframe()
    if df is None:
        return jsonify({"ok": False, "error": _df_error or "Dataset unavailable"})
    payload = build_dashboard_payload(df)
    recent = prepare_report_rows(df, limit=8, predict_fn=predict_startup_success)
    payload["recent_activity"] = [
        {
            "name": r["name"],
            "funding": r["funding_display"],
            "result": r["result"],
            "probability": r["probability"],
        }
        for r in recent
    ]
    return jsonify(payload)


@app.route("/api/analytics-data", methods=["GET"])
@login_required_api
def api_analytics_data():
    df = get_dataframe()
    if df is None:
        return jsonify({"ok": False, "error": _df_error or "Dataset unavailable"})
    return jsonify(build_analytics_payload(df))


@app.route("/api/dataset/export")
@login_required_api
def export_dataset_csv():
    df = get_dataframe()
    if df is None:
        return jsonify({"error": _df_error or "Dataset unavailable"}), 404
    data = dataframe_to_csv_bytes(df)
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={Path(DEFAULT_CSV).name}"},
    )


@app.route("/api/predictions", methods=["GET"])
@login_required_api
def get_user_predictions():
    """Get user's prediction history."""
    user_id = session.get("user", "anonymous")
    limit = int(request.args.get("limit", 50))
    history = get_prediction_history(user_id, limit)
    return jsonify({"predictions": history})


@app.route("/predictions")
@login_required_page
def predictions_page():
    """User predictions history page."""
    return render_template(
        "predictions.html",
        user_email=session.get("user"),
        active_page="predictions",
    )







@app.route("/predict", methods=["POST"])
@login_required_api
def predict():
    data, document_fields, error = _get_prediction_request_data()
    if error:
        return jsonify({"error": error}), 400

    try:
        funding_amount = float(data.get("funding_amount", 0))
        employees = int(data.get("employees", 0))
        industry = str(data.get("industry", "")).strip() or "Other"
        revenue = float(data.get("revenue", 0))
        location = str(data.get("location", "")).strip() or "Unknown"
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input types"}), 400

    probability, result, scores, feature_importance = predict_startup_success(
        funding_amount, employees, industry, revenue, location
    )

    # Generate recommendations based on scores
    recommendations = generate_recommendations(scores, funding_amount, employees, industry, location)

    # Save prediction to history
    user_id = session.get("user", "anonymous")
    prediction_data = {
        "funding_amount": funding_amount,
        "employees": employees,
        "industry": industry,
        "revenue": revenue,
        "location": location,
        "probability": probability,
        "result": result,
        "scores": scores,
        "feature_importance": feature_importance,
        "recommendations": recommendations
    }
    prediction_id = save_prediction_history(user_id, prediction_data)

    response_data = {
        "probability": probability,
        "result": result,
        "scores": scores,
        "feature_importance": feature_importance,
        "recommendations": recommendations,
        "prediction_id": prediction_id
    }
    if document_fields:
        response_data["startup_data"] = _document_startup_data(data)
    return jsonify(response_data)


def _get_prediction_request_data():
    if request.mimetype == "multipart/form-data":
        if request.content_length and request.content_length > MAX_UPLOAD_SIZE + 1024 * 1024:
            return None, None, "Files must be 10 MB or smaller."
        data = request.form.to_dict()
        upload = request.files.get("document")
        if upload is None or not upload.filename:
            return data, None, None
        try:
            extracted = extract_uploaded_document(
                upload.filename,
                upload.content_type,
                upload.stream.read(MAX_UPLOAD_SIZE + 1),
            )
        except ValueError as exc:
            return None, None, str(exc)
        data.update(extracted["fields"])
        required_fields = ("funding_amount", "employees", "industry", "revenue", "location")
        missing_fields = [
            field.replace("_", " ")
            for field in required_fields
            if data.get(field) is None or not str(data.get(field)).strip()
        ]
        if missing_fields:
            return None, None, "Missing required startup information: " + ", ".join(missing_fields) + "."
        return data, extracted["fields"], None
    return request.get_json(silent=True) or {}, None, None


def _document_startup_data(data):
    return {
        "startup_name": str(data.get("startup_name", "")).strip(),
        "funding_amount": float(data.get("funding_amount", 0)),
        "employees": int(data.get("employees", 0)),
        "industry": str(data.get("industry", "")).strip() or "Other",
        "revenue": float(data.get("revenue", 0)),
        "location": str(data.get("location", "")).strip() or "Unknown",
        "funding_round": data.get("funding_round"),
        "years_operation": data.get("years_operation"),
    }


def _document_model_contract():
    _, preprocessing = ml_predictor.load_model()
    feature_cols = preprocessing.get("feature_cols", [])
    label_encoders = preprocessing.get("label_encoders", {})
    if not feature_cols:
        raise ValueError("The trained model does not define its input features.")
    fields = []
    for name in feature_cols:
        encoder = label_encoders.get(name)
        fields.append({
            "name": name,
            "type": "category" if encoder else "number",
            "categories": [str(value) for value in encoder.classes_] if encoder else [],
        })
    return feature_cols, label_encoders, fields


def _validate_document_record(record, feature_cols, label_encoders):
    import math

    values = dict(record)
    prediction_input = {}
    issues = []
    integer_fields = {"employees_count", "number_of_founders"}
    for field in feature_cols:
        value = values.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append({"field": field, "message": "This model feature is required."})
            continue

        encoder = label_encoders.get(field)
        if encoder:
            categories = [str(category) for category in encoder.classes_]
            category = next((item for item in categories if item.casefold() == str(value).strip().casefold()), None)
            if category is None:
                issues.append({
                    "field": field,
                    "message": "Choose one of the supported categories: " + ", ".join(categories) + ".",
                })
                continue
            values[field] = category
            if field == "industry":
                prediction_input[field] = category
            else:
                prediction_input[field] = int(encoder.transform([category])[0])
            continue

        if isinstance(value, bool):
            issues.append({"field": field, "message": "Enter a valid number."})
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            issues.append({"field": field, "message": "Enter a valid number."})
            continue
        if not math.isfinite(number):
            issues.append({"field": field, "message": "Enter a finite number."})
            continue
        if number < 0:
            issues.append({"field": field, "message": "Enter a non-negative number."})
            continue
        if field in integer_fields and not number.is_integer():
            issues.append({"field": field, "message": "Enter a whole number."})
            continue
        values[field] = int(number) if field in integer_fields else number
        prediction_input[field] = values[field]

    values["startup_name"] = str(values.get("startup_name", "")).strip()
    return values, prediction_input, issues


def _document_preview(records, source, feature_cols, label_encoders, fields):
    preview = []
    for record in records:
        values, _, issues = _validate_document_record(record, feature_cols, label_encoders)
        preview.append({"values": values, "issues": issues})
    return jsonify({
        "preview": preview,
        "fields": fields,
        "source": {key: value for key, value in source.items() if key != "tables"},
    })


def _predict_document_records(records):
    if not isinstance(records, list) or not records or len(records) > 100:
        return jsonify({"error": "Upload between 1 and 100 startup records at a time."}), 400
    try:
        feature_cols, label_encoders, _ = _document_model_contract()
    except FileNotFoundError:
        return jsonify({"error": "The trained ML model is not available."}), 503
    except Exception:
        logger.exception("Unable to load document prediction metadata")
        return jsonify({"error": "Model feature metadata could not be loaded."}), 503

    prediction_inputs = []
    display_records = []
    validation_issues = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            validation_issues.append({"record_index": index, "field": "record", "message": "Invalid record."})
            continue
        values, prediction_input, issues = _validate_document_record(record, feature_cols, label_encoders)
        prediction_inputs.append(prediction_input)
        display_records.append(values)
        validation_issues.extend({"record_index": index, **issue} for issue in issues)
    if validation_issues:
        return jsonify({
            "error": "Correct the highlighted fields before predicting.",
            "validation_issues": validation_issues,
        }), 400

    try:
        results = ml_predictor.batch_predict(prediction_inputs)
    except Exception:
        logger.exception("Document batch prediction failed")
        return jsonify({"error": "The model could not process these records."}), 500

    failures = [
        {"record_index": index, "message": "The model could not predict this record."}
        for index, result in enumerate(results)
        if result.get("error") or not result.get("prediction")
    ]
    if failures:
        return jsonify({"error": "One or more records could not be predicted.", "prediction_issues": failures}), 422

    model, _ = ml_predictor.load_model()
    importance_values = getattr(model, "feature_importances_", None)
    feature_importance = []
    if importance_values is not None and len(importance_values) == len(feature_cols):
        feature_importance = [
            {"feature": feature, "value": float(importance) * 100}
            for feature, importance in zip(feature_cols, importance_values)
        ]

    document_results = []
    for index, result in enumerate(results):
        values = display_records[index]
        probability = float(result.get("success_probability", 0))
        employees = int(values["employees_count"])
        industry = str(values["industry"])
        location = str(values["city"])
        funding_amount = float(values["funding_amount"])
        revenue = float(values["revenue"])
        recommendations = generate_recommendations(
            {"funding": probability / 5, "team": probability / 5, "revenue": probability / 5,
             "industry": probability / 5, "location": probability / 5},
            funding_amount,
            employees,
            industry,
            location,
        )
        document_results.append({
            "startup_name": values.get("startup_name") or f"Record {index + 1}",
            "prediction": result["prediction"],
            "success_probability": probability,
            "failure_probability": float(result.get("failure_probability", 100 - probability)),
            "confidence": float(result.get("confidence", 0)),
            "recommendations": recommendations,
            "startup_data": {
                "startup_name": values.get("startup_name") or f"Record {index + 1}",
                "industry": industry,
                "location": location,
                "funding_amount": funding_amount,
                "employees": employees,
                "revenue": revenue,
                "funding_round": values.get("funding_round"),
                "years_operation": values.get("startup_age"),
                "founder_experience": values.get("founder_experience"),
                "market_size": values.get("market_size"),
            },
        })

    logger.info("Document batch prediction completed for %d records", len(results))
    return jsonify({
        "document_results": document_results,
        "feature_importance": feature_importance,
        "probability_available": True,
        "model_type": "ML-RandomForest-SMOTE",
    })


@app.route("/api/ml-predict", methods=["POST"])
@login_required_api
def ml_predict():
    """
    ML-based prediction using trained RandomForest model with SMOTE.
    Handles cold start and class imbalance.
    """
    if not ML_AVAILABLE:
        return jsonify({
            "error": "ML model not available. Please train the model first by running: python train.py",
            "fallback": "Using rule-based prediction instead"
        }), 503

    if request.mimetype == "multipart/form-data":
        if request.content_length and request.content_length > MAX_UPLOAD_SIZE + 1024 * 1024:
            return jsonify({"error": "Files must be 10 MB or smaller."}), 413
        upload = request.files.get("document")
        if upload is None or not upload.filename:
            return jsonify({"error": "Choose an Excel or PDF file to upload."}), 400
        try:
            extracted = extract_uploaded_document(
                upload.filename,
                upload.content_type,
                upload.stream.read(MAX_UPLOAD_SIZE + 1),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            feature_cols, label_encoders, fields = _document_model_contract()
        except FileNotFoundError:
            return jsonify({"error": "The trained ML model is not available."}), 503
        except Exception:
            logger.exception("Unable to load document preview metadata")
            return jsonify({"error": "Model feature metadata could not be loaded."}), 503
        if request.form.get("preview_only") == "1":
            return _document_preview(
                extracted["records"], extracted["source"], feature_cols, label_encoders, fields
            )
        return _predict_document_records(extracted["records"])

    request_data = request.get_json(silent=True) or {}
    if isinstance(request_data, dict) and "document_records" in request_data:
        return _predict_document_records(request_data["document_records"])
    
    data, document_fields, error = _get_prediction_request_data()
    if error:
        return jsonify({"error": error}), 400
    
    try:
        # Prepare input data for ML model
        input_data = {
            'funding_amount': float(data.get("funding_amount", 0)),
            'num_employees': int(data.get("employees", 1)),
            'industry': str(data.get("industry", "")).strip() or "Unknown",
            'revenue': float(data.get("revenue", 0)),
            'location': str(data.get("location", "")).strip() or "Unknown"
        }
        
        logger.info(f"ML Prediction request: {input_data}")
        
        # Get ML prediction
        ml_result = ml_predictor.predict(input_data)
        
        # Combine with rule-based recommendations
        recommendations = generate_recommendations(
            {'funding': ml_result['success_probability']/5, 
             'team': ml_result['success_probability']/5,
             'revenue': ml_result['success_probability']/5,
             'industry': ml_result['success_probability']/5,
             'location': ml_result['success_probability']/5},
            input_data['funding_amount'],
            input_data['num_employees'],
            input_data['industry'],
            input_data['location']
        )
        
        # Save to prediction history
        user_id = session.get("user", "anonymous")
        prediction_data = {
            "funding_amount": input_data['funding_amount'],
            "employees": input_data['num_employees'],
            "industry": input_data['industry'],
            "revenue": input_data['revenue'],
            "location": input_data['location'],
            "probability": int(ml_result['success_probability']),
            "result": ml_result['prediction'],
            "confidence": ml_result['confidence'],
            "model_type": "ML-RandomForest-SMOTE",
            "recommendations": recommendations
        }
        prediction_id = save_prediction_history(user_id, prediction_data)
        
        response_data = {
            "prediction": ml_result['prediction'],
            "confidence": ml_result['confidence'],
            "success_probability": ml_result['success_probability'],
            "failure_probability": ml_result['failure_probability'],
            "probabilities": ml_result['probabilities'],
            "recommendations": recommendations,
            "prediction_id": prediction_id,
            "model_type": "ML-RandomForest-SMOTE"
        }
        if document_fields:
            response_data["startup_data"] = _document_startup_data(data)
        return jsonify(response_data)
        
    except FileNotFoundError as e:
        logger.error(f"Model files not found: {e}")
        return jsonify({
            "error": "ML model not trained yet",
            "message": str(e),
            "hint": "Run 'python train.py' to train the model"
        }), 503
    except Exception as e:
        logger.error(f"ML prediction error: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Prediction error",
            "message": str(e)
        }), 500


@app.route("/api/ml-batch-predict", methods=["POST"])
@login_required_api
def ml_batch_predict():
    """
    Batch ML-based predictions for multiple startups
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML model not available"}), 503
    
    data = request.get_json(silent=True) or {}
    startups = data.get("startups", [])
    
    if not startups or not isinstance(startups, list):
        return jsonify({"error": "Invalid input: expected 'startups' array"}), 400
    
    try:
        input_list = []
        for startup in startups:
            input_list.append({
                'funding_amount': float(startup.get("funding_amount", 0)),
                'num_employees': int(startup.get("employees", 1)),
                'industry': str(startup.get("industry", "")).strip() or "Unknown",
                'revenue': float(startup.get("revenue", 0)),
                'location': str(startup.get("location", "")).strip() or "Unknown"
            })
        
        # Get batch predictions
        results = ml_predictor.batch_predict(input_list)
        
        return jsonify({
            "results": results,
            "count": len(results),
            "model_type": "ML-RandomForest-SMOTE"
        })
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/prediction-history", methods=["GET"])
@login_required_api
def api_get_prediction_history():
    """Get user's prediction history."""
    user_id = session.get("user", "anonymous")
    try:
        predictions = load_prediction_history(user_id)
        return jsonify({"predictions": predictions})
    except Exception as e:
        return jsonify({"error": f"Failed to load prediction history: {str(e)}"}), 500


@app.route("/api/prediction-history/<prediction_id>", methods=["DELETE"])
@login_required_api
def delete_prediction(prediction_id):
    """Delete a specific prediction from history."""
    user_id = session.get("user", "anonymous")
    try:
        success = delete_prediction_from_history(user_id, prediction_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Prediction not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to delete prediction: {str(e)}"}), 500


@app.route("/api/export-pdf", methods=["POST"])
@login_required_api
def export_pdf_route():
    """Export predictions as PDF report."""
    if not EXPORT_AVAILABLE:
        return jsonify({"error": "PDF export not available. Install reportlab: pip install reportlab"}), 501
    
    try:
        data = request.get_json(silent=True) or {}
        predictions = data.get('predictions', [])
        stats = data.get('stats', {})
        
        # Generate PDF
        pdf_bytes = generate_pdf_report(predictions, stats)
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=startup-report-{datetime.now().strftime("%Y%m%d")}.pdf'}
        )
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/share-report", methods=["POST"])
@login_required_api
def share_report_route():
    """Create a shareable report link."""
    try:
        data = request.get_json(silent=True) or {}
        predictions = data.get('predictions', [])
        stats = data.get('stats', {})
        
        # Generate share URL
        share_url = generate_share_url(predictions, stats)
        
        return jsonify({
            "share_url": share_url,
            "url": share_url,
            "success": True
        })
    except Exception as e:
        logger.error(f"Share report error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/shared-report/<report_id>", methods=["GET"])
def get_shared_report_route(report_id):
    """Retrieve a shared report (no auth required)."""
    try:
        report_data = get_shared_report(report_id)
        
        if not report_data:
            return jsonify({"error": "Report not found"}), 404
        
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"Get shared report error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-analysis", methods=["POST"])
@login_required_api
def ai_analysis():
    if not LLM_AVAILABLE:
        return jsonify({"ai_analysis": None, "message": "AI analysis temporarily unavailable."}), 200

    logger.info("AI analysis request received")
    data = request.get_json(silent=True) or {}
    required = ("startup_name", "industry", "location", "funding_amount", "revenue", "ml_result")
    if not all(key in data for key in required):
        return jsonify({"error": "Missing required fields."}), 400

    startup = {
        "startup_name": data.get("startup_name"),
        "industry": data.get("industry"),
        "location": data.get("location"),
        "funding_amount": data.get("funding_amount"),
        "employees": data.get("employees", data.get("num_employees")),
        "revenue": data.get("revenue"),
        "funding_round": data.get("funding_round"),
        "years_operation": data.get("years_operation"),
    }
    try:
        context = build_dataset_context(startup) or {}
        logger.info("Calling LLM for startup analysis")
        result = generate_startup_analysis(startup, data["ml_result"], context)
        logger.info("AI analysis generated: %s", bool(result))
        return jsonify({"ai_analysis": result})
    except Exception as exc:
        logger.warning("AI analysis unavailable: %s", exc)
        return jsonify({"ai_analysis": None, "message": "AI analysis temporarily unavailable."}), 200


@app.route("/api/ai-question", methods=["POST"])
@login_required_api
def ai_question():
    """Answer a startup question using bounded client-provided history."""
    if not LLM_AVAILABLE:
        return jsonify({"answer": None, "message": "AI is temporarily unavailable."}), 200

    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    startup = data.get("startup_data") or {}
    ml_result = data.get("ml_result") or {}
    history = data.get("conversation_history") or []
    if not question or not isinstance(startup, dict) or not isinstance(ml_result, dict):
        return jsonify({"error": "Question, startup_data, and ml_result are required."}), 400
    if not isinstance(history, list):
        return jsonify({"error": "conversation_history must be an array."}), 400
    history = [item for item in history[-20:] if isinstance(item, dict) and item.get("role") in ("user", "assistant")]

    try:
        context = build_dataset_context(startup) or {}
        logger.info("Calling LLM for startup question")
        if history:
            result = answer_startup_question_with_history(question, startup, ml_result, context, history)
        else:
            result = answer_startup_question(question, startup, ml_result, context)
        return jsonify(result or {"answer": None, "message": "AI is temporarily unavailable."})
    except Exception as exc:
        logger.warning("AI question unavailable: %s", exc)
        return jsonify({"answer": None, "message": "AI is temporarily unavailable."}), 200


@app.route("/api/ai-dataset-insights", methods=["GET"])
@login_required_api
def ai_dataset_insights():
    """Return calculated dataset facts plus an optional AI interpretation."""
    if not LLM_AVAILABLE:
        return jsonify({"stats": {}, "ai_insights": None, "success": False}), 200
    frame = get_dataframe()
    if frame is None:
        return jsonify({"error": "Dataset unavailable", "stats": {}, "ai_insights": None}), 200
    stats = {
        "total_startups": int(len(frame)),
        "overall_success_rate": float(frame["success"].mean() * 100) if len(frame) else 0.0,
        "successful_startups": int((frame["success"] == 1).sum()),
        "failed_startups": int((frame["success"] == 0).sum()),
        "median_funding_overall": float(frame["funding_amount"].median()),
        "median_revenue_overall": float(frame["revenue"].median()),
        "median_employees_overall": float(frame["num_employees"].median()),
    }
    try:
        insights = generate_dataset_insights(stats)
    except Exception as exc:
        logger.warning("Dataset AI insights unavailable: %s", exc)
        insights = None
    return jsonify({"stats": stats, "ai_insights": insights, "success": insights is not None})


# Reset cache on module load to clear any stale errors from previous failed attempts
reset_dataframe()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
