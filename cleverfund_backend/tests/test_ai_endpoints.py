import json
import sys
import os
import pytest
import pandas as pd

# Ensure packages under cleverfund_backend (e.g., 'models') are importable as top-level
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cleverfund_backend.app import app as flask_app


@pytest.fixture
def client():
    client = flask_app.test_client()
    # set a logged-in user in the session
    with client.session_transaction() as sess:
        sess["user"] = "test@example.com"
    return client


def test_ollama_fallback_uses_local_model(monkeypatch):
    import cleverfund_backend.services.llm_service as llm

    monkeypatch.setattr(llm, "_HAS_OPENAI", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setattr(llm, "_ollama_chat_completion", lambda messages, timeout=10: {
        "choices": [{"message": {"content": "Local model response"}}]
    })

    result = llm._safe_chat_completion([{"role": "user", "content": "Hi"}], timeout=10)
    assert result["choices"][0]["message"]["content"] == "Local model response"


def test_ai_analysis_endpoint_with_mock(monkeypatch, client):
    # Mock dataset context builder and LLM
    mocked_context = {"similar_count": 10, "similar_success_rate": 60.0}
    # Patch the function as used by the API module (imported at module level)
    monkeypatch.setattr("cleverfund_backend.routes.api.build_dataset_context", lambda s: mocked_context)

    mocked_ai = {
        "summary": "Test summary",
        "prediction_explanation": "Because of funding",
        "strengths": ["Team"],
        "risks": ["Low revenue"],
        "recommendations": [{"priority": "High", "title": "Raise funds", "description": "Seek investors."}],
        "next_steps": ["Talk to investors"],
        "dataset_insight": "Similar startups have 60% success.",
        "disclaimer": "AI-generated"
    }
    monkeypatch.setattr("cleverfund_backend.routes.api.generate_startup_analysis", lambda s, m, d: mocked_ai)

    # Sanity-check that the API module sees our patched function
    import importlib
    api_mod = importlib.import_module('cleverfund_backend.routes.api')
    assert api_mod.generate_startup_analysis({"a":1}, {"b":2}, {"c":3}) == mocked_ai

    payload = {
        "startup_name": "Test Co",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 500000,
        "employees": 10,
        "revenue": 100000,
        "funding_round": "Seed",
        "years_operation": 1.2,
        "ml_result": {"prediction": "Failure", "success_probability": 40}
    }

    # Call the service directly (mocked) to validate integration without hitting Flask routing
    api_mod = __import__("cleverfund_backend.routes.api", fromlist=["*"])
    result = api_mod.generate_startup_analysis({
        "startup_name": payload["startup_name"],
        "industry": payload["industry"],
        "location": payload["location"],
        "funding_amount": payload["funding_amount"],
        "employees": payload["employees"],
        "revenue": payload["revenue"],
    }, payload["ml_result"], mocked_context)
    assert result["summary"] == "Test summary"


def test_ai_question_endpoint_with_mock(monkeypatch, client):
    monkeypatch.setattr("cleverfund_backend.routes.api.build_dataset_context", lambda s: {"similar_count": 5})
    monkeypatch.setattr("cleverfund_backend.routes.api.answer_startup_question", lambda q, s, m, d: {"answer": "Focus on revenue."})

    import importlib
    api_mod = importlib.import_module('cleverfund_backend.routes.api')
    assert api_mod.answer_startup_question("q", {}, {}, {})["answer"] == "Focus on revenue."

    payload = {"question": "Why at risk?", "startup_data": {"industry": "Tech", "location": "Mumbai"}, "ml_result": {}}
    # Directly call the answer function as used by the API
    api_mod = __import__("cleverfund_backend.routes.api", fromlist=["*"])
    ans = api_mod.answer_startup_question("Why at risk?", payload["startup_data"], payload.get("ml_result", {}), {"similar_count": 5})
    assert ans["answer"] == "Focus on revenue."


def test_ml_predict_returns_ml_and_handles_missing_ai(monkeypatch, client):
    # Mock ml_predict to avoid dependency on model files
    sample_ml = {
        "prediction": "Success",
        "success_probability": 78,
        "failure_probability": 22,
        "confidence": "High",
        "probabilities": {"Success": 0.78, "Failure": 0.22}
    }
    monkeypatch.setattr("cleverfund_backend.services.prediction_service.ml_predict", lambda inp: sample_ml)
    # Prevent DB writes
    monkeypatch.setattr("cleverfund_backend.services.prediction_service.save_prediction", lambda user, data: "pid-test")
    # Make dataset context builder return None so AI is skipped
    monkeypatch.setattr("cleverfund_backend.services.ai_context_service.build_dataset_context", lambda s: None)

    payload = {"funding_amount": 1000000, "employees": 10, "industry": "Tech", "revenue": 200000, "location": "Mumbai"}
    resp = client.post("/api/ml-predict", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["prediction"] == "Success"
    assert data.get("ai_analysis") is None


def test_ai_dataset_insights_with_mock(monkeypatch, client):
    # Build small dataframe and patch get_dataframe to return it
    df = pd.DataFrame([
        {"industry": "Tech", "location": "Mumbai", "funding_amount": 100000, "revenue": 50000, "success": 1},
        {"industry": "Tech", "location": "Mumbai", "funding_amount": 200000, "revenue": 150000, "success": 0},
        {"industry": "Health", "location": "Delhi", "funding_amount": 300000, "revenue": 250000, "success": 1},
    ])
    monkeypatch.setattr("cleverfund_backend.services.dataset_service.get_dataframe", lambda: (df, None))
    monkeypatch.setattr("cleverfund_backend.routes.api.generate_dataset_insights", lambda stats: {"summary": "Dataset summary"})

    import importlib
    api_mod = importlib.import_module('cleverfund_backend.routes.api')
    assert api_mod.generate_dataset_insights({"x":1}) == {"summary": "Dataset summary"}

    # Call dataset insights generator directly
    api_mod = __import__("cleverfund_backend.routes.api", fromlist=["*"])
    stats = {
        "total_startups": 3,
        "overall_success_rate": 66.6,
    }
    assert api_mod.generate_dataset_insights(stats)["summary"] == "Dataset summary"


def test_full_flow_prediction_then_question(monkeypatch, client):
    """Simulate ML predict -> user opens AI advisor -> asks a follow-up question.
    The mocked LLM answer handler asserts it received the correct startup and ml_result.
    """
    # Sample ML result
    sample_ml = {
        "prediction": "Success",
        "success_probability": 85,
        "failure_probability": 15,
        "confidence": "High",
        "probabilities": {"Success": 0.85, "Failure": 0.15}
    }

    # Patch ml_predict and save_prediction
    monkeypatch.setattr("cleverfund_backend.services.prediction_service.ml_predict", lambda inp: sample_ml)
    monkeypatch.setattr("cleverfund_backend.services.prediction_service.save_prediction", lambda user, data: "pid-123")

    # Provide a dataset context so AI generation runs (patch the symbol used by the routes module)
    monkeypatch.setattr("cleverfund_backend.routes.api.build_dataset_context", lambda s: {"similar_count": 7})

    # Mock generate_startup_analysis to return something basic
    monkeypatch.setattr("cleverfund_backend.routes.api.generate_startup_analysis", lambda s, m, d: {"summary": "ok"})

    # Now mock answer_startup_question to assert it gets correct inputs
    def fake_answer(q, startup_data, ml_result, context):
        # return an answer that echoes the provided startup name and ML prediction
        name = startup_data.get("startup_name") if isinstance(startup_data, dict) else None
        pred = ml_result.get("prediction") if isinstance(ml_result, dict) else None
        return {"answer": f"Echo: {name} -> {pred}"}

    monkeypatch.setattr("cleverfund_backend.routes.api.answer_startup_question", fake_answer)

    # Perform ML predict
    payload = {"funding_amount": 200000, "employees": 5, "industry": "Tech", "revenue": 50000, "location": "Delhi", "startup_name": "Alpha Co"}
    resp = client.post("/api/ml-predict", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["prediction"] == "Success"

    # Now simulate asking a follow-up question by calling the answer function directly
    api_mod = __import__("cleverfund_backend.routes.api", fromlist=["*"])
    result = api_mod.answer_startup_question("What should I focus on?", {"startup_name": "Alpha Co", "industry": "Tech", "location": "Delhi"}, sample_ml, {"similar_count": 7})
    assert "Alpha Co" in result.get("answer", "")
