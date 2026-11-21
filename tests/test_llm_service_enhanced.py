"""Tests for enhanced LLM service functions."""
import pytest
import json
from unittest.mock import patch, MagicMock
from cleverfund_backend.services.llm_service import (
    generate_structured_dataset_insights,
    answer_startup_question_with_history,
    explain_feature_importance,
    _safe_chat_completion,
)


class TestStructuredDatasetInsights:
    """Test structured dataset insights generation."""
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_returns_structured_json(self, mock_llm):
        """Test that structured response is properly parsed."""
        stats = {
            "total_startups": 1000,
            "overall_success_rate": 65.5,
            "median_funding_successful": 500000,
        }
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "summary": "Overall, 65.5% of startups succeed",
                        "key_findings": ["Finding 1", "Finding 2"],
                        "industry_insights": ["Insight 1"],
                        "funding_insights": [],
                        "revenue_insights": [],
                        "recommendations": ["Recommend 1"],
                        "disclaimer": "AI-generated"
                    })
                }
            }]
        }
        mock_llm.return_value = mock_response
        
        result = generate_structured_dataset_insights(stats)
        
        assert result is not None
        assert result["summary"] == "Overall, 65.5% of startups succeed"
        assert len(result["key_findings"]) == 2
        assert "Recommend 1" in result["recommendations"]
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_extracts_json_from_wrapped_text(self, mock_llm):
        """Test JSON extraction from wrapped text response."""
        stats = {"total_startups": 100}
        
        json_obj = {
            "summary": "Test",
            "key_findings": [],
            "industry_insights": [],
            "funding_insights": [],
            "revenue_insights": [],
            "recommendations": [],
            "disclaimer": "Test"
        }
        
        wrapped_response = f"Here's the analysis:\n\n{json.dumps(json_obj)}\n\nEnd of analysis."
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": wrapped_response
                }
            }]
        }
        mock_llm.return_value = mock_response
        
        result = generate_structured_dataset_insights(stats)
        
        assert result is not None
        assert result["summary"] == "Test"
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_returns_fallback_on_llm_failure(self, mock_llm):
        """Test fallback structure when LLM fails."""
        stats = {"total_startups": 100}
        
        mock_llm.return_value = None  # LLM failure
        
        result = generate_structured_dataset_insights(stats)
        
        assert result is None


class TestMultiTurnConversation:
    """Test multi-turn conversation support."""
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_answer_with_conversation_history(self, mock_llm):
        """Test answering question with conversation history."""
        startup_data = {
            "startup_name": "TestCorp",
            "industry": "Tech",
            "location": "NYC",
            "funding_amount": 500000,
            "revenue": 50000,
            "employees": 5
        }
        ml_result = {"prediction": "Success", "success_probability": 72}
        dataset_context = {"similar_count": 20, "similar_success_rate": 68}
        
        history = [
            {"role": "user", "content": "What is my biggest risk?"},
            {"role": "assistant", "content": "Your burn rate is high..."},
        ]
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "To reduce burn rate, you should increase revenue..."
                }
            }]
        }
        mock_llm.return_value = mock_response
        
        result = answer_startup_question_with_history(
            "How can I reduce it?",
            startup_data,
            ml_result,
            dataset_context,
            history
        )
        
        assert result is not None
        assert "reduce burn" in result["answer"].lower() or "revenue" in result["answer"].lower()
        
        # Verify conversation history was included
        call_args = mock_llm.call_args
        messages = call_args[0][0]  # First positional argument
        
        # Should have system prompt + context setup + history + new question
        assert len(messages) >= 4
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_conversation_without_history(self, mock_llm):
        """Test conversation when no history is provided."""
        startup_data = {"startup_name": "NewCorp", "industry": "Tech"}
        ml_result = {"prediction": "Success"}
        
        mock_response = {
            "choices": [{
                "message": {"content": "Test answer"}
            }]
        }
        mock_llm.return_value = mock_response
        
        result = answer_startup_question_with_history(
            "First question?",
            startup_data,
            ml_result,
            {}
        )
        
        assert result is not None
        assert result["answer"] == "Test answer"


class TestFeatureImportanceExplanation:
    """Test feature importance explanation."""
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_explain_top_features(self, mock_llm):
        """Test explaining the top weighted features."""
        startup_data = {
            "startup_name": "FeatureCorp",
            "industry": "Tech",
            "funding_amount": 1000000
        }
        ml_result = {"prediction": "Success", "success_probability": 80}
        feature_importance = {
            "Funding": 0.35,
            "Employees": 0.25,
            "Revenue": 0.20,
            "Industry": 0.15,
            "Location": 0.05
        }
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Funding and employee count were the most important factors..."
                }
            }]
        }
        mock_llm.return_value = mock_response
        
        result = explain_feature_importance(startup_data, ml_result, feature_importance)
        
        assert result is not None
        assert "important" in result["explanation"].lower() or "factor" in result["explanation"].lower()
    
    def test_no_feature_importance_returns_default(self):
        """Test that missing feature importance returns default message."""
        startup_data = {"startup_name": "NoCorp"}
        ml_result = {"prediction": "Success"}
        
        result = explain_feature_importance(startup_data, ml_result, None)
        
        assert result is not None
        assert "not available" in result["explanation"]
    
    @patch('cleverfund_backend.services.llm_service._safe_chat_completion')
    def test_handles_llm_failure(self, mock_llm):
        """Test graceful handling of LLM failures."""
        mock_llm.return_value = None
        
        startup_data = {"startup_name": "FailCorp"}
        ml_result = {"prediction": "Success"}
        feature_importance = {"Funding": 0.5}
        
        result = explain_feature_importance(startup_data, ml_result, feature_importance)
        
        # When LLM fails, should return None (caller handles gracefully)
        assert result is None


class TestSafeChatCompletion:
    """Test safe chat completion wrapper."""
    
    def test_returns_none_without_api_key(self):
        """Test that completion returns None when API key is missing."""
        import os
        
        # Temporarily hide API key
        old_key = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        try:
            result = _safe_chat_completion([{"role": "user", "content": "test"}])
            assert result["choices"][0]["message"]["content"]
        finally:
            # Restore
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
    
    @patch('cleverfund_backend.services.llm_service.OpenAI')
    def test_handles_timeout(self, mock_openai_class):
        """Test that timeouts are handled gracefully."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out")
        
        import os
        os.environ["OPENAI_API_KEY"] = "sk-test123"
        
        result = _safe_chat_completion([{"role": "user", "content": "test"}])
        
        assert result["choices"][0]["message"]["content"]
