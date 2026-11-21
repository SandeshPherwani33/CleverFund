"""
routes/api.py
-------------
All JSON API endpoints consumed by the frontend JavaScript.

Endpoints
---------
  GET  /api/dashboard-data          → dashboard charts + stats
  GET  /api/analytics-data          → analytics charts + KPIs
  GET  /api/dataset/export          → download CSV
  POST /predict                     → rule-based prediction (main form)
  POST /api/ml-predict              → ML-based prediction (toggle)
  POST /api/ml-batch-predict        → batch ML predictions
  GET  /api/prediction-history      → user's past predictions
  DEL  /api/prediction-history/<id> → delete one prediction
  GET  /api/predictions             → alias (used in some JS paths)
  POST /api/ai-question             → ask AI a question (multi-turn support)
  GET  /api/ai-dataset-insights     → dataset-level insights
  POST /api/ai-analysis             → structured AI analysis
  POST /api/conversation/clear      → clear conversation history
"""

from flask import Blueprint, Response, jsonify, request, session
import logging

logger = logging.getLogger(__name__)
from .auth import login_required_api
from ..services.dataset_service import (
    get_dataframe,
    build_dashboard_payload,
    build_analytics_payload,
    prepare_report_rows,
    dataframe_to_csv_bytes,
    DEFAULT_CSV,
)
from pathlib import Path
from ..services.prediction_service import (
    rule_based_predict,
    generate_recommendations,
    ml_predict,
    ml_batch_predict,
    save_prediction,
    get_user_predictions,
    delete_prediction,
    ML_AVAILABLE,
)
from ..services.llm_service import (
    generate_startup_analysis,
    answer_startup_question,
    generate_dataset_insights,
    answer_startup_question_with_history,
    generate_structured_dataset_insights,
    explain_feature_importance,
)
from ..services import ai_context_service
from ..services.ai_context_service import build_dataset_context

_ORIGINAL_BUILD_DATASET_CONTEXT = build_dataset_context
from ..services.conversation_service import (
    get_or_create_conversation,
    add_message_to_conversation,
    clear_conversation,
    clear_all_conversations,
)

api_bp = Blueprint("api", __name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard & Analytics data
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/dashboard-data")
@login_required_api
def api_dashboard_data():
    """
    Returns stats + chart data for the dashboard page.

    Response shape:
      { ok, stats, growth, outcome, industry, funding_revenue, recent_activity }
    """
    df, err = get_dataframe()
    if df is None:
        return jsonify({"ok": False, "error": err or "Dataset unavailable"}), 200

    payload = build_dashboard_payload(df)

    # Add recent activity rows (last 8 from dataset)
    recent = prepare_report_rows(df, limit=8)
    payload["recent_activity"] = [
        {
            "name":        r["name"],
            "funding":     r["funding_display"],
            "result":      r["result"],
            "probability": r["probability"],
        }
        for r in recent
    ]
    return jsonify(payload)


@api_bp.route("/api/analytics-data")
@login_required_api
def api_analytics_data():
    """
    Returns KPIs + chart data for the analytics page.

    Response shape:
      { ok, kpis, volume, radar, region }
    """
    df, err = get_dataframe()
    if df is None:
        return jsonify({"ok": False, "error": err or "Dataset unavailable"}), 200
    return jsonify(build_analytics_payload(df))


# ─────────────────────────────────────────────────────────────────────────────
#  Dataset export
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/dataset/export")
@login_required_api
def export_dataset_csv():
    """Download the loaded dataset as a CSV file."""
    df, err = get_dataframe()
    if df is None:
        return jsonify({"error": err or "Dataset unavailable"}), 404

    data = dataframe_to_csv_bytes(df)
    filename = Path(DEFAULT_CSV).name
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Rule-based prediction  (POST /predict)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/predict", methods=["POST"])
@login_required_api
def predict():
    """
    Run the weighted-score (rule-based) prediction.

    Request body (JSON):
      {
        "funding_amount": 5000000,
        "employees":      50,
        "industry":       "Technology / Software",
        "revenue":        2000000,
        "location":       "Bangalore",
        "startup_name":   "Velocity AI",   // optional
        "funding_round":  "Seed",           // optional
        "years_operation": 2.5              // optional
      }

    Response:
      {
        "probability":        75.0,
        "result":             "Success",
        "scores":             { funding, team, revenue, industry, location, total },
        "feature_importance": [ { feature, value, score } ... ],
        "recommendations":    [ { type, priority, title, description, suggestion } ... ],
        "prediction_id":      "uuid-string"
      }
    """
    body = request.get_json(silent=True) or {}

    try:
        funding_amount  = float(body.get("funding_amount", 0))
        employees       = int(body.get("employees", 0))
        industry        = str(body.get("industry", "")).strip() or "Other"
        revenue         = float(body.get("revenue", 0))
        location        = str(body.get("location", "")).strip() or "Unknown"
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input — check numeric fields."}), 400

    probability, result, scores, feature_importance = rule_based_predict(
        funding_amount, employees, industry, revenue, location
    )
    recommendations = generate_recommendations(scores)

    user_email = session["user"]
    pid = save_prediction(user_email, {
        "startup_name":    body.get("startup_name"),
        "industry":        industry,
        "location":        location,
        "funding_amount":  funding_amount,
        "employees":       employees,
        "revenue":         revenue,
        "funding_round":   body.get("funding_round"),
        "years_operation": body.get("years_operation"),
        "probability":     probability,
        "result":          result,
        "scores":          scores,
        "feature_importance": feature_importance,
        "recommendations": recommendations,
        "model_type":      "rule-based",
    })

    return jsonify({
        "probability":        probability,
        "result":             result,
        "scores":             scores,
        "feature_importance": feature_importance,
        "recommendations":    recommendations,
        "prediction_id":      pid,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  ML prediction  (POST /api/ml-predict)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/ml-predict", methods=["POST"])
@login_required_api
def api_ml_predict():
    """
    Run the trained RandomForest+SMOTE model.

    Request body: same as /predict
    Response:
      {
        "prediction":         "Success",
        "confidence":         "High",
        "success_probability": 78,
        "failure_probability": 22,
        "recommendations":    [...],
        "prediction_id":      "uuid"
      }

    Returns 503 if model files are not trained yet.
    """
    if not ML_AVAILABLE:
        return jsonify({
            "error":    "ML model not available.",
            "hint":     "Run 'python train.py' to train the model first.",
            "fallback": "Use the rule-based /predict endpoint instead.",
        }), 503

    body = request.get_json(silent=True) or {}

    try:
        input_data = {
            "funding_amount": float(body.get("funding_amount", 0)),
            "num_employees":  int(body.get("employees", 1)),
            "industry":       str(body.get("industry", "")).strip() or "Unknown",
            "revenue":        float(body.get("revenue", 0)),
            "location":       str(body.get("location", "")).strip() or "Unknown",
        }
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input types."}), 400

    try:
        ml_result = ml_predict(input_data)
    except FileNotFoundError:
        return jsonify({
            "error": "ML model not trained yet.",
            "hint":  "Run 'python train.py'.",
        }), 503
    except Exception as exc:
        return jsonify({"error": "Prediction error.", "message": str(exc)}), 500

    # Build simple scores dict for recommendations
    p = ml_result.get("success_probability", 50)
    pseudo_scores = {k: p / 5 for k in ("funding", "team", "revenue", "industry", "location")}
    recommendations = generate_recommendations(pseudo_scores)

    user_email = session["user"]
    pid = save_prediction(user_email, {
        "startup_name":    body.get("startup_name"),
        "industry":        input_data["industry"],
        "location":        input_data["location"],
        "funding_amount":  input_data["funding_amount"],
        "employees":       input_data["num_employees"],
        "revenue":         input_data["revenue"],
        "probability":     int(ml_result.get("success_probability", 0)),
        "result":          ml_result.get("prediction", "Unknown"),
        "recommendations": recommendations,
        "model_type":      "ML-RandomForest-SMOTE",
        # placeholder — AI generation status will be updated separately
        "ai_analysis_generated": False,
    })

    # Attempt to generate AI analysis (non-fatal)
    ai_analysis = None
    try:
        context_builder = build_dataset_context
        if context_builder is _ORIGINAL_BUILD_DATASET_CONTEXT:
            context_builder = ai_context_service.build_dataset_context
        context = context_builder({
            "startup_name": body.get("startup_name"),
            "industry": input_data.get("industry"),
            "location": input_data.get("location"),
            "funding_amount": input_data.get("funding_amount"),
            "employees": input_data.get("num_employees"),
            "revenue": input_data.get("revenue"),
            "funding_round": body.get("funding_round"),
            "years_operation": body.get("years_operation"),
        })
        if context is not None:
            ai_analysis = generate_startup_analysis(
                {
                    "startup_name": body.get("startup_name"),
                    "industry": input_data.get("industry"),
                    "location": input_data.get("location"),
                    "funding_amount": input_data.get("funding_amount"),
                    "employees": input_data.get("num_employees"),
                    "revenue": input_data.get("revenue"),
                    "funding_round": body.get("funding_round"),
                    "years_operation": body.get("years_operation"),
                },
                ml_result,
                context,
            )
    except Exception:
        ai_analysis = None

    # If AI produced analysis, update the saved prediction document with a flag.
    try:
        if ai_analysis:
            # best-effort: mark the saved prediction as having AI analysis
            db_update = {"$set": {"ai_analysis_generated": True}}
            # access DB via prediction service model
            from ..models import database as _dbmod  # type: ignore
            # if database module provides get_db, try to update
            try:
                db = _dbmod.get_db()
                db.predictions.update_one({"id": pid}, db_update)
            except Exception:
                pass
    except Exception:
        pass

    return jsonify({
        "prediction":          ml_result.get("prediction"),
        "confidence":          ml_result.get("confidence"),
        "success_probability": ml_result.get("success_probability"),
        "failure_probability": ml_result.get("failure_probability"),
        "probabilities":       ml_result.get("probabilities"),
        "recommendations":     recommendations,
        "prediction_id":       pid,
        "model_type":          "ML-RandomForest-SMOTE",
        "ai_analysis":         ai_analysis,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Batch ML prediction  (POST /api/ml-batch-predict)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/ml-batch-predict", methods=["POST"])
@login_required_api
def api_ml_batch_predict():
    """
    Predict for multiple startups at once.

    Request body:
      { "startups": [ { same fields as /predict }, ... ] }

    Response:
      { "results": [...], "count": N, "model_type": "ML-RandomForest-SMOTE" }
    """
    if not ML_AVAILABLE:
        return jsonify({"error": "ML model not available."}), 503

    body     = request.get_json(silent=True) or {}
    startups = body.get("startups", [])

    if not startups or not isinstance(startups, list):
        return jsonify({"error": "Expected 'startups' array in request body."}), 400

    try:
        input_list = [
            {
                "funding_amount": float(s.get("funding_amount", 0)),
                "num_employees":  int(s.get("employees", 1)),
                "industry":       str(s.get("industry", "")).strip() or "Unknown",
                "revenue":        float(s.get("revenue", 0)),
                "location":       str(s.get("location", "")).strip() or "Unknown",
            }
            for s in startups
        ]
        results = ml_batch_predict(input_list)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "results":    results,
        "count":      len(results),
        "model_type": "ML-RandomForest-SMOTE",
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Prediction history  (GET/DELETE)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/prediction-history")
@login_required_api
def api_get_prediction_history():
    """
    Return the logged-in user's prediction history.

    Response:
      { "predictions": [ { id, name, industry, location, funding, employees,
                            revenue, probability, result, timestamp, ... } ] }
    """
    user_email = session["user"]
    limit      = min(int(request.args.get("limit", 100)), 500)
    try:
        predictions = get_user_predictions(user_email, limit)
        return jsonify({"predictions": predictions})
    except Exception as exc:
        return jsonify({"error": f"Failed to load history: {exc}"}), 500


@api_bp.route("/api/prediction-history/<prediction_id>", methods=["DELETE"])
@login_required_api
def api_delete_prediction(prediction_id):
    """
    Delete a specific prediction.

    200 : { "success": true }
    404 : { "error": "Prediction not found" }
    """
    user_email = session["user"]
    try:
        ok = delete_prediction(user_email, prediction_id)
        if ok:
            return jsonify({"success": True})
        return jsonify({"error": "Prediction not found."}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Alias used in some JS paths
@api_bp.route("/api/predictions")
@login_required_api
def api_predictions_alias():
    """Alias → same as /api/prediction-history."""
    return api_get_prediction_history()



@api_bp.route("/api/ai-analysis", methods=["POST"])
@login_required_api
def api_ai_analysis():
    """Generate AI Startup Advisor output for a given startup and ML result.

    Expects JSON body with startup fields and an `ml_result` object.
    Returns structured AI analysis or a friendly null if LLM unavailable.
    """
    body = request.get_json(silent=True) or {}
    required = ("startup_name", "industry", "location", "funding_amount", "revenue", "ml_result")
    if not all(k in body for k in required):
        return jsonify({"error": "Missing required fields."}), 400

    startup = {
        "startup_name": body.get("startup_name"),
        "industry": body.get("industry"),
        "location": body.get("location"),
        "funding_amount": body.get("funding_amount"),
        "employees": body.get("employees", body.get("num_employees")),
        "revenue": body.get("revenue"),
        "funding_round": body.get("funding_round"),
        "years_operation": body.get("years_operation"),
    }
    ml_result = body.get("ml_result")

    # Build dataset context
    try:
        context = build_dataset_context(startup)
    except Exception:
        context = None

    # Call LLM service; non-fatal
    try:
        ai_out = generate_startup_analysis(startup, ml_result, context or {})
    except Exception:
        ai_out = None

    if ai_out is None:
        return jsonify({"ai_analysis": None, "message": "AI analysis temporarily unavailable."}), 200
    return jsonify({"ai_analysis": ai_out}), 200



@api_bp.route("/api/ai-question", methods=["POST"])
@login_required_api
def api_ai_question():
    """Answer a natural-language question about a startup with optional multi-turn context.
    
    Request body:
    {
        "question": "...",
        "startup_data": {...},
        "ml_result": {...},
        "conversation_history": [...]  # optional: previous exchanges
    }
    
    Returns:
    {
        "answer": "...",
        "message": "..." or error
    }
    """
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    startup = body.get("startup_data") or {}
    ml_result = body.get("ml_result") or {}
    conversation_history = body.get("conversation_history", [])
    
    if not question:
        return jsonify({"error": "Question is required."}), 400
    
    if not startup or not startup.get("startup_name"):
        return jsonify({"error": "Startup data is required (at minimum: startup_name)."}), 400
    
    user_email = session["user"]
    
    # Get or create conversation context
    try:
        conv = get_or_create_conversation(
            user_email,
            startup,
            ml_result,
            None  # dataset context will be built as needed
        )
    except Exception as exc:
        logger.exception(f"Failed to get/create conversation: {exc}")
        conv = None
    
    # Build dataset context if available
    try:
        context = build_dataset_context(startup)
    except Exception:
        context = None
    
    # Answer the question with conversation history if available
    try:
        if conversation_history and len(conversation_history) > 0:
            # Use conversation-aware mode
            ans = answer_startup_question_with_history(
                question,
                startup,
                ml_result,
                context or {},
                conversation_history
            )
        else:
            # Use regular mode
            ans = answer_startup_question(question, startup, ml_result, context or {})
    except Exception as exc:
        logger.exception(f"LLM call failed: {exc}")
        ans = None
    
    if ans is None:
        return jsonify({"answer": None, "message": "AI is temporarily unavailable. Please try again."}), 200
    
    # Store exchange in conversation memory
    if conv and ans:
        try:
            add_message_to_conversation(
                user_email,
                startup,
                question,
                ans.get("answer", "")
            )
        except Exception as exc:
            logger.warning(f"Failed to store conversation: {exc}")
    
    return jsonify(ans), 200




@api_bp.route("/api/ai-dataset-insights", methods=["GET"])
@login_required_api
def api_ai_dataset_insights():
    """Compute dataset statistics and provide LLM-generated structured insights.
    
    Returns:
    {
        "stats": { all dataset statistics },
        "ai_insights": {
            "summary": "...",
            "key_findings": [...],
            "industry_insights": [...],
            "funding_insights": [...],
            "revenue_insights": [...],
            "recommendations": [...],
            "disclaimer": "..."
        }
    }
    """
    df, err = get_dataframe()
    if df is None:
        return jsonify({"error": err or "Dataset unavailable"}), 200

    try:
        # Compute all dataset statistics (Python/Pandas only)
        stats = {
            "total_startups": int(len(df)),
            "overall_success_rate": float(df["success"].mean() * 100) if len(df) else 0.0,
            "successful_startups": int((df["success"] == 1).sum()) if "success" in df.columns else 0,
            "failed_startups": int((df["success"] == 0).sum()) if "success" in df.columns else 0,
            
            # Industry breakdown
            "top_industries_by_success": (
                df.groupby("industry")["success"].agg(["mean", "count"])
                .sort_values("mean", ascending=False)
                .head(10)
                .to_dict("index") if "industry" in df.columns else {}
            ),
            
            # Location breakdown
            "top_locations_by_success": (
                df.groupby("location")["success"].agg(["mean", "count"])
                .sort_values("mean", ascending=False)
                .head(10)
                .to_dict("index") if "location" in df.columns else {}
            ),
            
            # Funding statistics
            "median_funding_overall": float(df["funding_amount"].median() or 0) if "funding_amount" in df.columns else 0,
            "median_funding_successful": float(df[df["success"] == 1]["funding_amount"].median() or 0) if "funding_amount" in df.columns and "success" in df.columns else 0,
            "median_funding_failed": float(df[df["success"] == 0]["funding_amount"].median() or 0) if "funding_amount" in df.columns and "success" in df.columns else 0,
            
            # Revenue statistics
            "median_revenue_overall": float(df["revenue"].median() or 0) if "revenue" in df.columns else 0,
            "median_revenue_successful": float(df[df["success"] == 1]["revenue"].median() or 0) if "revenue" in df.columns and "success" in df.columns else 0,
            "median_revenue_failed": float(df[df["success"] == 0]["revenue"].median() or 0) if "revenue" in df.columns and "success" in df.columns else 0,
            
            # Employee statistics
            "median_employees_overall": float(df["num_employees"].median() or 0) if "num_employees" in df.columns else 0,
            "median_employees_successful": float(df[df["success"] == 1]["num_employees"].median() or 0) if "num_employees" in df.columns and "success" in df.columns else 0,
            
            # Burn rate if available
            "median_burn_rate_successful": float(
                df[df["success"] == 1].get("burn_rate", df[df["success"] == 1].get("Burn_Rate")).median() or 0
            ) if ("burn_rate" in df.columns or "Burn_Rate" in df.columns) and "success" in df.columns else None,
            
            # Customer retention if available
            "avg_customer_retention_successful": float(
                df[df["success"] == 1].get("customer_retention_rate", df[df["success"] == 1].get("Customer_Retention_Rate")).mean() or 0
            ) if ("customer_retention_rate" in df.columns or "Customer_Retention_Rate" in df.columns) and "success" in df.columns else None,
        }
        
        # Remove None values for cleaner JSON
        stats = {k: v for k, v in stats.items() if v is not None}
        
    except Exception as exc:
        logger.exception(f"Failed to compute statistics: {exc}")
        stats = {"error": "Could not compute statistics"}

    # Generate LLM insights from the statistics
    ai_insights = None
    try:
        ai_insights = generate_structured_dataset_insights(stats)
    except Exception as exc:
        logger.exception(f"Failed to generate AI insights: {exc}")

    return jsonify({
        "stats": stats,
        "ai_insights": ai_insights,
        "success": ai_insights is not None
    }), 200



# ─────────────────────────────────────────────────────────────────────────────
#  Conversation Management
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/conversation/clear", methods=["POST"])
@login_required_api
def api_clear_conversation():
    """Clear conversation history for a specific startup.
    
    Request body:
    {
        "startup_data": {...}  # startup to clear history for
    }
    
    Returns:
    {
        "success": true
    }
    """
    body = request.get_json(silent=True) or {}
    startup = body.get("startup_data") or {}
    
    if not startup or not startup.get("startup_name"):
        return jsonify({"error": "Startup data is required."}), 400
    
    user_email = session["user"]
    
    try:
        clear_conversation(user_email, startup)
        return jsonify({"success": True}), 200
    except Exception as exc:
        logger.exception(f"Failed to clear conversation: {exc}")
        return jsonify({"error": "Failed to clear conversation."}), 500


@api_bp.route("/api/conversation/clear-all", methods=["POST"])
@login_required_api
def api_clear_all_conversations():
    """Clear ALL conversation history for the user.
    
    Returns:
    {
        "success": true
    }
    """
    user_email = session["user"]
    
    try:
        clear_all_conversations(user_email)
        return jsonify({"success": True}), 200
    except Exception as exc:
        logger.exception(f"Failed to clear all conversations: {exc}")
        return jsonify({"error": "Failed to clear conversations."}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Feature Importance Explanation
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/api/ai-explain-features", methods=["POST"])
@login_required_api
def api_explain_features():
    """Explain which features the ML model weighted most heavily.
    
    Request body:
    {
        "startup_data": {...},
        "ml_result": {...},
        "feature_importance": {
            "Funding": 0.28,
            "Employees": 0.21,
            ...
        }
    }
    
    Returns:
    {
        "explanation": "..."
    }
    """
    body = request.get_json(silent=True) or {}
    startup = body.get("startup_data") or {}
    ml_result = body.get("ml_result") or {}
    feature_importance = body.get("feature_importance")
    
    if not startup or not ml_result:
        return jsonify({"error": "Startup data and ML result are required."}), 400
    
    if not feature_importance:
        return jsonify({
            "explanation": "No feature importance data available. The model prediction is still valid."
        }), 200
    
    try:
        result = explain_feature_importance(startup, ml_result, feature_importance)
        if result is None:
            return jsonify({"explanation": "Explanation temporarily unavailable."}), 200
        return jsonify(result), 200
    except Exception as exc:
        logger.exception(f"Failed to explain features: {exc}")
        return jsonify({"explanation": "Could not generate explanation."}), 500
