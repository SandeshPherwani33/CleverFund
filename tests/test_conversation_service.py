"""Tests for multi-turn conversation memory and management."""
import pytest
from cleverfund_backend.services.conversation_service import (
    ConversationContext,
    get_or_create_conversation,
    add_message_to_conversation,
    clear_conversation,
    clear_all_conversations,
    _hash_startup,
    MAX_CONVERSATION_TURNS,
)


class TestConversationContext:
    """Test ConversationContext class."""
    
    def test_init_creates_empty_messages(self):
        """Test that new conversation has empty messages."""
        startup = {"startup_name": "TestCorp", "industry": "Tech"}
        ml_result = {"prediction": "Success", "success_probability": 75}
        
        conv = ConversationContext(startup, ml_result)
        
        assert conv.startup_data == startup
        assert conv.ml_result == ml_result
        assert conv.messages == []
        assert conv.dataset_context == {}
    
    def test_add_exchange_stores_messages(self):
        """Test adding user and assistant messages."""
        startup = {"startup_name": "TestCorp"}
        ml_result = {"prediction": "Success"}
        
        conv = ConversationContext(startup, ml_result)
        conv.add_exchange("What is my risk?", "Your risk is moderate.")
        
        assert len(conv.messages) == 2
        assert conv.messages[0]["role"] == "user"
        assert conv.messages[1]["role"] == "assistant"
        assert conv.messages[0]["content"] == "What is my risk?"
        assert conv.messages[1]["content"] == "Your risk is moderate."
    
    def test_bounded_history_respects_max_messages(self):
        """Test that conversation history is bounded."""
        startup = {"startup_name": "TestCorp"}
        ml_result = {"prediction": "Success"}
        
        conv = ConversationContext(startup, ml_result)
        
        # Add more exchanges than MAX_CONVERSATION_TURNS
        for i in range(MAX_CONVERSATION_TURNS + 5):
            conv.add_exchange(f"Question {i}", f"Answer {i}")
        
        # Should be bounded to MAX_CONVERSATION_TURNS * 2 messages
        assert len(conv.messages) <= MAX_CONVERSATION_TURNS * 2
    
    def test_get_bounded_history_returns_recent_messages(self):
        """Test that bounded history returns the most recent messages."""
        startup = {"startup_name": "TestCorp"}
        ml_result = {"prediction": "Success"}
        
        conv = ConversationContext(startup, ml_result)
        
        # Add 5 exchanges
        for i in range(5):
            conv.add_exchange(f"Q{i}", f"A{i}")
        
        history = conv.get_bounded_history(max_messages=4)
        
        assert len(history) == 4
        assert history[-2]["content"] == "Q4"
        assert history[-1]["content"] == "A4"
    
    def test_to_dict_serializes_context(self):
        """Test that conversation context serializes to dict."""
        startup = {"startup_name": "TestCorp", "industry": "Tech"}
        ml_result = {"prediction": "Success"}
        dataset_context = {"similar_count": 50}
        
        conv = ConversationContext(startup, ml_result, dataset_context)
        conv.add_exchange("Test Q", "Test A")
        
        result = conv.to_dict()
        
        assert result["startup_data"] == startup
        assert result["ml_result"] == ml_result
        assert result["dataset_context"] == dataset_context
        assert len(result["messages"]) == 2
        assert "created_at" in result
        assert "last_updated" in result


class TestConversationManagement:
    """Test conversation management functions."""
    
    def test_hash_startup_is_consistent(self):
        """Test that startup hash is stable."""
        startup1 = {"startup_name": "TestCorp", "industry": "Tech", "location": "NYC"}
        startup2 = {"startup_name": "TestCorp", "industry": "Tech", "location": "NYC"}
        
        hash1 = _hash_startup(startup1)
        hash2 = _hash_startup(startup2)
        
        assert hash1 == hash2
    
    def test_hash_startup_differs_for_different_startups(self):
        """Test that different startups have different hashes."""
        startup1 = {"startup_name": "CorpA", "industry": "Tech"}
        startup2 = {"startup_name": "CorpB", "industry": "Tech"}
        
        hash1 = _hash_startup(startup1)
        hash2 = _hash_startup(startup2)
        
        assert hash1 != hash2
    
    def test_get_or_create_conversation_creates_new(self):
        """Test creating a new conversation."""
        startup = {"startup_name": "New Corp"}
        ml_result = {"prediction": "Success"}
        
        conv = get_or_create_conversation("user@example.com", startup, ml_result)
        
        assert conv is not None
        assert conv.startup_data == startup
        assert len(conv.messages) == 0
    
    def test_get_or_create_conversation_retrieves_existing(self):
        """Test retrieving an existing conversation."""
        startup = {"startup_name": "Existing Corp"}
        ml_result = {"prediction": "Success"}
        
        conv1 = get_or_create_conversation("user@example.com", startup, ml_result)
        conv1.add_exchange("Q1", "A1")
        
        conv2 = get_or_create_conversation("user@example.com", startup, ml_result)
        
        assert len(conv2.messages) == 2
        assert conv2.messages[0]["content"] == "Q1"
    
    def test_add_message_to_conversation(self):
        """Test adding a message to conversation."""
        startup = {"startup_name": "Test Corp"}
        
        add_message_to_conversation("user@example.com", startup, "Q1", "A1")
        
        conv = get_or_create_conversation("user@example.com", startup, {})
        assert len(conv.messages) == 2
    
    def test_clear_conversation(self):
        """Test clearing a specific conversation."""
        startup = {"startup_name": "Clear Test"}
        
        add_message_to_conversation("user@example.com", startup, "Q1", "A1")
        clear_conversation("user@example.com", startup)
        
        conv = get_or_create_conversation("user@example.com", startup, {})
        assert len(conv.messages) == 0  # New conversation
    
    def test_clear_all_conversations(self):
        """Test clearing all conversations for a user."""
        startup1 = {"startup_name": "Corp1"}
        startup2 = {"startup_name": "Corp2"}
        
        add_message_to_conversation("user@example.com", startup1, "Q1", "A1")
        add_message_to_conversation("user@example.com", startup2, "Q2", "A2")
        
        clear_all_conversations("user@example.com")
        
        conv1 = get_or_create_conversation("user@example.com", startup1, {})
        conv2 = get_or_create_conversation("user@example.com", startup2, {})
        
        # Both should be new (empty)
        assert len(conv1.messages) == 0
        assert len(conv2.messages) == 0
