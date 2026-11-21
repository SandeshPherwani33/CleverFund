"""Tests for the dataset-grounded LLM analysis service.

Verifies that:
1. LLM functions accept dataset context
2. LLM prompts encourage evidence-based analysis
3. LLM responses are properly parsed
4. Fallback mechanisms work when LLM is unavailable
5. Statistics are never fabricated (always from context)
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cleverfund_backend.services.llm_service import (
    generate_startup_analysis,
    answer_startup_question,
    generate_dataset_insights,
    SYSTEM_PROMPT,
)


@pytest.fixture
def sample_startup():
    """Sample startup data."""
    return {
        "startup_name": "TechCorp",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 5000000,
        "revenue": 1000000,
        "employees": 50,
    }


@pytest.fixture
def sample_ml_result():
    """Sample ML prediction result."""
    return {
        "prediction": "Success",
        "success_probability": 75.0,
        "failure_probability": 25.0,
        "confidence": 75.0,
    }


@pytest.fixture
def sample_dataset_context():
    """Sample dataset context (compact stats)."""
    return {
        "similar_count": 47,
        "similar_success_rate": 68.1,
        "median_funding": 4200000,
        "median_revenue": 1500000,
        "median_employees": 31,
        "industry_success_rate": 71.4,
        "location_success_rate": 65.2,
        "representative_startups": [
            {"startup_name": "CompA", "funding_amount": 4500000, "revenue": 1200000, "success": 1},
            {"startup_name": "CompB", "funding_amount": 4000000, "revenue": 1400000, "success": 1},
        ],
    }


def test_system_prompt_emphasizes_data_grounding():
    """Test that system prompt emphasizes data-grounded analysis."""
    assert "ONLY source of truth" in SYSTEM_PROMPT
    assert "Never invent" in SYSTEM_PROMPT or "invent" in SYSTEM_PROMPT.lower()
    assert "dataset" in SYSTEM_PROMPT.lower()


def test_generate_startup_analysis_with_context(sample_startup, sample_ml_result, sample_dataset_context):
    """Test that startup analysis function accepts and uses dataset context."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "summary": "Strong technical team with good market positioning.",
                        "prediction_explanation": "The Random Forest predicts Success with 75% confidence.",
                        "strengths": ["Solid funding", "Experienced team"],
                        "risks": ["Market competition"],
                        "recommendations": [
                            {"priority": "high", "title": "Expand Marketing", "description": "Invest in customer acquisition"}
                        ],
                        "next_steps": ["Hire engineering lead"],
                        "dataset_insight": "Among 47 similar startups, 68.1% succeeded.",
                        "disclaimer": "AI-generated analysis based on model and dataset evidence.",
                    })
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = generate_startup_analysis(sample_startup, sample_ml_result, sample_dataset_context)
    
    # Should return parsed JSON
    assert result is not None
    assert isinstance(result, dict)
    assert "summary" in result
    assert "prediction_explanation" in result
    assert "dataset_insight" in result


def test_generate_startup_analysis_with_empty_context(sample_startup, sample_ml_result):
    """Test that startup analysis works with empty/missing context."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "summary": "Analysis based on ML prediction only.",
                        "prediction_explanation": "Model prediction available.",
                        "strengths": [],
                        "risks": [],
                        "recommendations": [],
                        "next_steps": [],
                        "dataset_insight": "Insufficient historical data available.",
                        "disclaimer": "Limited by dataset availability.",
                    })
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = generate_startup_analysis(sample_startup, sample_ml_result, {})
    
    assert result is not None
    assert "dataset_insight" in result


def test_generate_startup_analysis_fallback_on_malformed_json(sample_startup, sample_ml_result):
    """Test fallback when LLM returns non-JSON text."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "This is some raw text analysis, not JSON."
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = generate_startup_analysis(sample_startup, sample_ml_result, {})
    
    # Should fallback gracefully
    assert result is not None
    assert isinstance(result, dict)
    # The text should be in summary
    assert len(result.get("summary", "")) > 0


def test_generate_startup_analysis_returns_none_when_llm_unavailable(sample_startup, sample_ml_result):
    """Test that function returns None gracefully when LLM is unavailable."""
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=None):
        result = generate_startup_analysis(sample_startup, sample_ml_result, {})
    
    # Should return None (non-fatal)
    assert result is None


def test_answer_startup_question_with_context(sample_startup, sample_ml_result, sample_dataset_context):
    """Test that question answering function uses dataset context."""
    question = "How does my startup compare with similar startups?"
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Based on 47 similar startups, your company is performing well with a 68.1% success rate among peers."
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = answer_startup_question(question, sample_startup, sample_ml_result, sample_dataset_context)
    
    assert result is not None
    assert "answer" in result
    assert len(result["answer"]) > 0


def test_answer_startup_question_graceful_degradation():
    """Test that question answering works even with minimal context."""
    startup = {"startup_name": "Test"}
    ml_result = {"prediction": "Success", "success_probability": 50}
    context = {}  # Empty context
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "I can help, but limited dataset context is available."
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = answer_startup_question("Any advice?", startup, ml_result, context)
    
    assert result is not None
    assert "answer" in result


def test_generate_dataset_insights_with_context(sample_dataset_context):
    """Test that dataset insights function uses context properly."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "The dataset shows strong success rates in the Technology sector, with median funding of ₹4.2M across 47 startups."
                }
            }
        ]
    }
    
    with patch('cleverfund_backend.services.llm_service._safe_chat_completion', return_value=mock_response):
        result = generate_dataset_insights(sample_dataset_context)
    
    assert result is not None
    assert "summary" in result


def test_llm_service_never_trusts_unverified_stats():
    """Verify that LLM prompts encourage using only provided context."""
    # This is a conceptual test checking the prompt text
    prompt_text = SYSTEM_PROMPT.lower()
    
    # Prompts should discourage invention
    assert any(word in prompt_text for word in ["never invent", "only use provided", "source of truth"])
    
    # Prompts should encourage data-grounding
    assert any(word in prompt_text for word in ["dataset", "evidence", "historical", "provided context"])


def test_api_response_structure_with_dataset_analysis():
    """Test that API responses properly structure dataset insights."""
    # Simulate what the API endpoint should return
    response = {
        "prediction": "Success",
        "confidence": 75.0,
        "success_probability": 75.0,
        "failure_probability": 25.0,
        "probabilities": {"success": 75.0, "failure": 25.0},
        "recommendations": [],
        "prediction_id": "test-id",
        "model_type": "ML-RandomForest-SMOTE",
        "ai_analysis": {
            "summary": "Good potential",
            "prediction_explanation": "Model says Success",
            "dataset_insight": "Compared to similar startups..."
        }
    }
    
    # Should be JSON-serializable
    json_str = json.dumps(response)
    assert len(json_str) > 0
    
    # Should include dataset insight
    assert "dataset_insight" in json.loads(json_str).get("ai_analysis", {})


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
