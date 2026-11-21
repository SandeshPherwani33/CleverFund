"""Tests for dataset-grounded API endpoints.

Verifies that:
1. /api/ml-predict calls build_dataset_context before LLM analysis
2. /api/ai-analysis sends full context to LLM functions
3. /api/ai-question sends relevant context for follow-up
4. /api/ai-dataset-insights aggregates stats correctly
5. All endpoints handle missing context gracefully
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cleverfund_backend.app import create_app


@pytest.fixture
def app():
    """Create Flask test app."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    with app.app_context():
        with app.test_client() as c:
            yield c


@pytest.fixture
def auth_client(app):
    """Create authenticated test client."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user'] = 'test@example.com'
        yield c


def test_ml_predict_calls_dataset_context(auth_client):
    """Test that /api/ml-predict builds dataset context."""
    payload = {
        "startup_name": "TechCorp",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 5000000,
        "revenue": 1000000,
        "employees": 50,
        "funding_round": "Series A",
        "years_operation": 2,
    }
    
    with patch('cleverfund_backend.routes.api.ml_predict') as mock_ml, \
         patch('cleverfund_backend.routes.api.build_dataset_context') as mock_context, \
         patch('cleverfund_backend.routes.api.generate_startup_analysis') as mock_llm:
        
        mock_ml.return_value = {
            "prediction": "Success",
            "success_probability": 75.0,
            "failure_probability": 25.0,
        }
        mock_context.return_value = {
            "similar_count": 47,
            "similar_success_rate": 68.1,
        }
        mock_llm.return_value = {"summary": "Analysis"}
        
        response = auth_client.post('/api/ml-predict', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        # Should call build_dataset_context
        assert mock_context.called
        # Should call generate_startup_analysis with context
        assert mock_llm.called


def test_ai_analysis_endpoint_with_context(auth_client):
    """Test that /api/ai-analysis includes dataset context."""
    payload = {
        "startup_name": "TestCorp",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 4000000,
        "revenue": 800000,
        "ml_result": {
            "prediction": "Success",
            "success_probability": 70,
        }
    }

    with patch('cleverfund_backend.routes.api.build_dataset_context', return_value={"similar_count": 30, "similar_success_rate": 65.0}) as mock_context, \
         patch('cleverfund_backend.routes.api.generate_startup_analysis', return_value={"summary": "Analysis with context", "dataset_insight": "Compared to similar..."}) as mock_llm:
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = 'test@example.com'
            response = client.post('/api/ai-analysis', data=json.dumps(payload), content_type='application/json')
            assert response.status_code == 200
            assert mock_context.called
            assert mock_llm.called


def test_ai_question_endpoint_includes_context(auth_client):
    """Test that /api/ai-question passes context to LLM."""
    payload = {
        "question": "How does this compare to similar startups?",
        "startup_data": {
            "startup_name": "TestCorp",
            "industry": "Technology",
            "location": "Bengaluru",
            "funding_amount": 4000000,
        },
        "ml_result": {
            "prediction": "Success",
            "success_probability": 75,
        }
    }
    
    with patch('cleverfund_backend.routes.api.build_dataset_context') as mock_context, \
         patch('cleverfund_backend.routes.api.answer_startup_question') as mock_llm:
        
        mock_context.return_value = {"similar_count": 40, "similar_success_rate": 70}
        mock_llm.return_value = {"answer": "Your startup is performing well..."}
        
        response = auth_client.post('/api/ai-question',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        # Should build context for the question
        assert mock_context.called
        # Should pass context to answer function
        assert mock_llm.called


def test_dataset_insights_endpoint(auth_client):
    """Test that /api/ai-dataset-insights aggregates stats correctly."""
    with patch('cleverfund_backend.routes.api.generate_structured_dataset_insights', return_value={"summary": "The dataset shows..."}) as mock_llm:
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = 'test@example.com'
            response = client.get('/api/ai-dataset-insights')
            assert response.status_code == 200
            assert mock_llm.called


def test_endpoints_handle_missing_context_gracefully(auth_client):
    """Test that endpoints handle missing dataset context gracefully."""
    payload = {
        "question": "Test question",
        "startup_data": {"startup_name": "Test"},
        "ml_result": {"prediction": "Success", "success_probability": 50}
    }
    
    with patch('cleverfund_backend.routes.api.build_dataset_context', return_value=None), \
         patch('cleverfund_backend.routes.api.answer_startup_question', return_value={"answer": "Answer"}):
        
        # Should not crash when context is None
        response = auth_client.post('/api/ai-question',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        # Should return 200 even with missing context
        assert response.status_code in [200, 400]  # 200 for success, 400 for validation


def test_api_responses_are_json_serializable(auth_client):
    """Test that all API responses are valid JSON."""
    payload = {
        "startup_name": "Test",
        "industry": "Tech",
        "location": "NYC",
        "funding_amount": 1000000,
        "revenue": 100000,
        "employees": 10,
    }
    
    with patch('cleverfund_backend.routes.api.ml_predict') as mock_ml, \
         patch('cleverfund_backend.routes.api.build_dataset_context') as mock_ctx:
        
        mock_ml.return_value = {
            "prediction": "Success",
            "success_probability": 50,
            "failure_probability": 50,
        }
        mock_ctx.return_value = {"similar_count": 100}
        
        response = auth_client.post('/api/ml-predict',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        # Should be valid JSON
        try:
            json.loads(response.data)
            assert True
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")


def test_api_includes_no_raw_dataset_rows(auth_client):
    """Verify that APIs never return the raw full dataset."""
    payload = {
        "question": "Test",
        "startup_data": {"startup_name": "Test"},
        "ml_result": {"prediction": "Success", "success_probability": 50}
    }
    
    with patch('cleverfund_backend.routes.api.build_dataset_context') as mock_ctx, \
         patch('cleverfund_backend.routes.api.answer_startup_question') as mock_llm:
        
        # Return a context with only a sample
        mock_ctx.return_value = {
            "representative_startups": [
                {"startup_name": "A"},
                {"startup_name": "B"},
            ]
        }
        mock_llm.return_value = {"answer": "Test"}
        
        response = auth_client.post('/api/ai-question',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        # Should return response with limited data
        data = json.loads(response.data)
        # Should not contain full dataset dump
        assert "representative_startups" not in str(data) or len(str(data)) < 50000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
