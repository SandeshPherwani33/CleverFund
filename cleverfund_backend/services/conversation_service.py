"""Lightweight conversation memory management for multi-turn AI interactions.

Maintains bounded conversation context (last 5-10 exchanges) per startup.
Tracks startup_data, ml_result, dataset context, and recent messages.

Not persistent — memory is session-based only.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory conversation store: {user_email: {startup_hash: ConversationContext}}
_CONVERSATIONS: Dict[str, Dict[str, 'ConversationContext']] = {}

MAX_CONVERSATION_TURNS = 10  # Keep last 10 exchanges (20 messages total)


class ConversationContext:
    """Bounded conversation context for a specific startup analysis."""
    
    def __init__(self, startup_data: dict, ml_result: dict, dataset_context: Optional[dict] = None):
        self.startup_data = startup_data
        self.ml_result = ml_result
        self.dataset_context = dataset_context or {}
        self.messages: List[Dict[str, str]] = []
        self.created_at = datetime.utcnow().isoformat()
        self.last_updated = self.created_at
    
    def add_exchange(self, user_message: str, assistant_message: str):
        """Add a user question and assistant response to the conversation."""
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": assistant_message})
        
        # Trim to bounded history
        if len(self.messages) > MAX_CONVERSATION_TURNS * 2:
            # Keep the most recent MAX_CONVERSATION_TURNS exchanges
            self.messages = self.messages[-(MAX_CONVERSATION_TURNS * 2):]
        
        self.last_updated = datetime.utcnow().isoformat()
    
    def get_bounded_history(self, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """Return the bounded conversation history for LLM context."""
        if max_messages is None:
            max_messages = MAX_CONVERSATION_TURNS * 2
        
        if len(self.messages) <= max_messages:
            return self.messages.copy()
        
        # Return the most recent N messages
        return self.messages[-max_messages:]
    
    def to_dict(self) -> dict:
        """Serialize conversation context to a dict."""
        return {
            "startup_data": self.startup_data,
            "ml_result": self.ml_result,
            "dataset_context": self.dataset_context,
            "messages": self.get_bounded_history(),
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }


def _hash_startup(startup_data: dict) -> str:
    """Create a stable hash key for a startup (for deduplication)."""
    # Use startup name + industry + location as the key
    name = str(startup_data.get("startup_name", "unknown")).lower().strip()
    industry = str(startup_data.get("industry", "unknown")).lower().strip()
    location = str(startup_data.get("location", "unknown")).lower().strip()
    return f"{name}_{industry}_{location}".replace(" ", "_")


def get_or_create_conversation(user_email: str, startup_data: dict, ml_result: dict, dataset_context: Optional[dict] = None) -> ConversationContext:
    """Get or create a conversation context for the given user and startup.
    
    If the conversation already exists, it is returned with existing message history.
    Otherwise, a new conversation is created.
    """
    if user_email not in _CONVERSATIONS:
        _CONVERSATIONS[user_email] = {}
    
    startup_hash = _hash_startup(startup_data)
    
    if startup_hash not in _CONVERSATIONS[user_email]:
        # Create new conversation
        _CONVERSATIONS[user_email][startup_hash] = ConversationContext(
            startup_data, ml_result, dataset_context
        )
        logger.info(f"Created new conversation for {user_email} / {startup_hash}")
    
    return _CONVERSATIONS[user_email][startup_hash]


def add_message_to_conversation(user_email: str, startup_data: dict, user_message: str, assistant_message: str):
    """Add a user question and assistant response to the conversation."""
    conv = get_or_create_conversation(user_email, startup_data, {}, None)
    conv.add_exchange(user_message, assistant_message)


def clear_conversation(user_email: str, startup_data: dict):
    """Clear the conversation history for a given startup."""
    if user_email not in _CONVERSATIONS:
        return
    
    startup_hash = _hash_startup(startup_data)
    if startup_hash in _CONVERSATIONS[user_email]:
        del _CONVERSATIONS[user_email][startup_hash]
        logger.info(f"Cleared conversation for {user_email} / {startup_hash}")


def clear_all_conversations(user_email: str):
    """Clear all conversations for a user."""
    if user_email in _CONVERSATIONS:
        del _CONVERSATIONS[user_email]
        logger.info(f"Cleared all conversations for {user_email}")
