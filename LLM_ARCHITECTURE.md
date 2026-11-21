# CleverFund AI / LLM Architecture & Implementation Guide

## Overview

CleverFund AI is an explainability layer built on top of the Random Forest + SMOTE machine learning model. The AI system provides human-readable explanations, dataset-grounded insights, and conversational interaction without replacing or modifying the core ML prediction logic.

### Key Philosophy

**ML Model = Source of Truth** | **AI Layer = Explainability Only**

- The Random Forest model's success probability prediction is **immutable and non-negotiable**
- The LLM layer provides context, interpretation, and explanation
- Dataset statistics are facts; the LLM never invents numbers
- All AI features are non-fatal: if LLM fails, the ML prediction still returns successfully

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  (predictions.html, reports.html, ask-ai modal)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                    Flask API Routes
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
/api/ml-predict   /api/ai-question   /api/ai-dataset-insights
  (unchanged)       (multi-turn)        (structured)
    │                    │                    │
    │   ┌─────────────────┴────────────────┐  │
    │   │                                  │  │
    ▼   ▼                                  ▼  ▼
┌──────────────────────────────────────────────────────┐
│            Prediction Service (ML)                   │
│         (Random Forest + SMOTE Model)                │
│  ✓ IMMUTABLE: always returns success probability    │
└──────────────────────────────────────────────────────┘
    │
    └─────────┬──────────────────────────────────────────┐
              │                                          │
    ┌─────────▼─────────┐                    ┌──────────▼──────────┐
    │ Dataset Context   │                    │  Conversation Mem   │
    │ Service (RAG)     │                    │  Service (bounded)  │
    │                   │                    │                     │
    │ • Similar startups│                    │ • Max 10 exchanges  │
    │ • Aggregated stats│                    │ • Session-based     │
    │ • Industry/location                    │ • Auto-trim old     │
    └────────┬──────────┘                    └──────────┬──────────┘
             │                                          │
    ┌────────┴──────────────────────────────────────────┴────────┐
    │                                                              │
    ▼                                                              ▼
┌─────────────────────────────────────┐         ┌─────────────────────────┐
│   LLM Service (OpenAI gpt-4o-mini)  │         │  Conversation Context   │
│                                     │         │     Class               │
│ • System Prompt (data-grounding)    │         │ • startup_data          │
│ • answer_startup_question()         │         │ • ml_result             │
│ • answer_startup_question_with_()   │         │ • bounded messages list │
│ • generate_structured_insights()    │         │ • timestamps            │
│ • explain_feature_importance()      │         └─────────────────────────┘
│                                     │
│ ✓ Graceful fallback (None on fail)  │
└─────────────────────────────────────┘
    │
    │ HTTP
    ▼
┌─────────────────────────────────┐
│    OpenAI API (gpt-4o-mini)     │
│   (API Key: environment var)    │
└─────────────────────────────────┘
```

---

## Core Functionality

### 1. **Multi-Turn Conversation Memory** (`conversation_service.py`)

**Purpose**: Maintain bounded session-based conversation history for multi-turn interactions.

**Key Classes & Functions**:

```python
class ConversationContext:
    """Stores all context for one startup conversation."""
    startup_data: dict              # { startup_name, industry, location, etc. }
    ml_result: dict                 # { prediction, success_probability }
    dataset_context: dict           # { similar_count, success_rate, etc. }
    messages: list                  # Bounded list of {"role", "content"} messages
    created_at: str                 # ISO timestamp
    last_updated: str               # ISO timestamp
    
    def add_exchange(user_msg, assistant_msg):
        """Add user + assistant messages; auto-trim if exceeds MAX_CONVERSATION_TURNS."""
```

**Configuration**:
- `MAX_CONVERSATION_TURNS = 10` (20 messages max; oldest auto-trimmed)
- Non-persistent (session-based in-memory storage)
- Keyed by: `f"{user_email}:{hash(startup_name + industry + location)}"`

**Public API**:

| Function | Purpose | Returns |
|----------|---------|---------|
| `get_or_create_conversation(user_email, startup, ml_result)` | Get or create conversation | ConversationContext |
| `add_message_to_conversation(user_email, startup, user_msg, assist_msg)` | Add exchange + auto-trim | None |
| `clear_conversation(user_email, startup)` | Clear one startup's history | None |
| `clear_all_conversations(user_email)` | Clear all user's conversations | None |

---

### 2. **Enhanced LLM Service** (`llm_service.py`)

**System Prompt Highlights**:

```
CRITICAL RULES (do not violate):
1. Random Forest + SMOTE model prediction is THE ONLY source of truth
   - Never modify, round, or reinterpret the probability
2. Dataset statistics are facts — NEVER invent numbers
3. Clearly distinguish ML PREDICTION | DATASET EVIDENCE | AI INTERPRETATION | RECOMMENDATIONS
4. Do NOT claim causation (avoid "CAUSES", use "is associated with")
5. Handle missing context gracefully
6. For structured responses, return JSON with keys:
   summary, prediction_explanation, strengths, risks, recommendations, next_steps, dataset_insight, disclaimer
```

**New Functions**:

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `answer_startup_question_with_history()` | Multi-turn Q&A with bounded history | question, startup, ml_result, dataset_context, history | {"answer": "...", "timestamp": "..."} or None |
| `generate_structured_dataset_insights()` | Generate structured JSON insights from stats | stats_dict | {"summary": "...", "key_findings": [...], ...} or None |
| `explain_feature_importance()` | Explain why ML model weighted certain features | startup, ml_result, feature_importance_dict | {"explanation": "...", "features": [...]} or None |

**Timeout & Failure Handling**:
- All functions have `timeout` parameter (default 8-10 seconds)
- Return `None` on failure (timeout, API error, invalid API key)
- Never raise exceptions; graceful degradation

---

### 3. **Dataset-Grounded RAG Context** (`ai_context_service.py` - unchanged)

**Retrieval Flow**:
1. Find similar startups based on: industry + location + funding range
2. Compute aggregated statistics: success rate, median funding/revenue/employees
3. Prepare 5-row sample comparison for LLM context
4. Never send raw dataset; only aggregates + sample

**Statistics Computed**:
- Similar startup count, success rate in similar group
- Industry-level success rate
- Location-level success rate
- Median funding/revenue/employees in similar group

---

## API Endpoints

### Multi-Turn Conversation Support

#### `POST /api/ai-question` (Enhanced)

**Request**:
```json
{
  "question": "What should I focus on next?",
  "startup_data": {
    "startup_name": "TechCorp",
    "industry": "B2B SaaS",
    "location": "NYC",
    "funding_amount": 500000,
    "revenue": 50000,
    "num_employees": 5
  },
  "ml_result": {
    "prediction": "Success",
    "success_probability": 72,
    "feature_importance": {"Funding": 0.35, ...}
  },
  "conversation_history": [
    {"role": "user", "content": "What is my biggest risk?"},
    {"role": "assistant", "content": "Based on..."}
  ]
}
```

**Response**:
```json
{
  "answer": "AI-generated explanation with historical context...",
  "timestamp": "2024-01-15T10:30:00Z",
  "sources": ["dataset_comparison", "feature_importance"],
  "success": true
}
```

**Behavior**:
- If `conversation_history` provided: uses `answer_startup_question_with_history()` (multi-turn aware)
- If no history: uses regular `answer_startup_question()` (single turn)
- Automatically stores exchange via `add_message_to_conversation()`
- Next request for same startup will include this exchange in history

---

#### `GET /api/ai-dataset-insights`

**Response**:
```json
{
  "stats": {
    "total_startups": 1234,
    "overall_success_rate": 65.5,
    "successful_startups": 809,
    "failed_startups": 425,
    "top_industries_by_success": {
      "B2B SaaS": {"mean": 0.72, "count": 150},
      "E-commerce": {"mean": 0.68, "count": 120}
    },
    "median_funding_overall": 500000,
    "median_funding_successful": 650000,
    "median_revenue_successful": 250000,
    ...
  },
  "ai_insights": {
    "summary": "The dataset reveals strong performance in SaaS...",
    "key_findings": ["Finding 1", "Finding 2", ...],
    "industry_insights": ["SaaS shows highest success rate..."],
    "funding_insights": ["Startups with >$500k funding..."],
    "revenue_insights": ["Successful startups median revenue..."],
    "recommendations": ["Consider B2B SaaS market...", ...],
    "disclaimer": "AI-generated insights based on historical data..."
  },
  "success": true
}
```

**Computation Flow**:
1. Load dataset via pandas
2. Compute 20+ statistics (all Python/Pandas; no LLM calls)
3. Call `generate_structured_dataset_insights(stats)` for LLM interpretation
4. Return both raw stats and AI insights

---

#### `POST /api/ai-explain-features`

**Request**:
```json
{
  "startup_data": {...},
  "ml_result": {...},
  "feature_importance": {
    "Funding": 0.35,
    "Employees": 0.25,
    "Revenue": 0.20
  }
}
```

**Response**:
```json
{
  "explanation": "The model weighted funding most heavily (35%) because...",
  "features": [
    {"name": "Funding", "weight": 0.35, "interpretation": "Strongly predictive of success..."},
    {"name": "Employees", "weight": 0.25, "interpretation": "Team size correlates with..."}
  ],
  "disclaimer": "Feature importance shows ML correlation, not causation.",
  "success": true
}
```

---

#### `POST /api/conversation/clear`

**Request**:
```json
{
  "startup_data": {...}
}
```

**Response**:
```json
{
  "success": true,
  "message": "Conversation cleared for TechCorp"
}
```

---

#### `POST /api/conversation/clear-all`

**Response**:
```json
{
  "success": true,
  "message": "All conversations cleared for user"
}
```

---

## Security & Safety

### 1. **API Key Protection**
- API key loaded from `OPENAI_API_KEY` environment variable
- `.env` file added to `.gitignore`
- Never logged or sent to client
- Terminal always shows only `"..."` for key value

### 2. **No Data Leakage**
- Raw dataset never sent to LLM
- Only aggregated statistics and 5-row sample shared
- Dataset comparison includes only anonymized counts (no user data)
- All statistics computed server-side before LLM call

### 3. **Hallucination Prevention**
- Strict system prompt with rule #2: "Dataset statistics are facts — NEVER invent numbers"
- Only pre-computed statistics passed to LLM
- LLM explicitly forbidden from calculating/deriving new stats
- Structured JSON response requires specific schema (easier to validate)

### 4. **Graceful Degradation**
- All LLM functions return `None` on failure
- API endpoints handle `None` gracefully (return user-friendly fallback)
- ML prediction always succeeds even if LLM fails
- Error logging (server-side) without exposing details to client

### 5. **Token Management**
- Bounded conversation history (max 20 messages = ~10 exchanges)
- Prevents token count explosion
- Auto-trims oldest messages when limit exceeded

---

## Testing

### Unit Tests

**File**: `tests/test_conversation_service.py` (22 tests)
- Conversation context creation and serialization
- Message bounds enforcement
- Conversation retrieval and clearing
- Hash stability

**File**: `tests/test_llm_service_enhanced.py` (28 tests)
- Structured insights JSON parsing
- Conversation history injection
- Feature importance explanation
- LLM failure handling and timeouts
- API key missing scenarios

### Integration Tests

**File**: `tests/test_api_endpoints_context.py` (subset)
- Full endpoint request/response cycles
- Error handling and graceful degradation
- Missing context scenarios

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run only LLM tests
pytest tests/test_llm_service_enhanced.py tests/test_conversation_service.py -v

# Run with coverage
pytest tests/ --cov=cleverfund_backend --cov-report=html
```

---

## Environment Configuration

### Required Variables

```bash
# .env or .env.local
OPENAI_API_KEY=sk-...           # Your OpenAI API key
OPENAI_MODEL=gpt-4o-mini         # Model name (default if omitted)
PORT=5000                         # Flask port (optional)
SESSION_SECRET=your-secret-here  # Session encryption (optional)
```

### Configuration Priority

1. `.env.local` (if exists, highest priority)
2. `.env` in project root or backend folder
3. Environment variables
4. Code defaults (e.g., `gpt-4o-mini` for model)

---

## Performance Considerations

### LLM Latency
- **Single turn**: ~2-4 seconds
- **Multi-turn**: ~1-3 seconds (context already cached in conversation)
- **Dataset insights**: ~3-5 seconds (computing 20+ stats + LLM)
- **Feature explanation**: ~2-3 seconds

### Optimization Tips
1. **Reuse conversation memory**: Multi-turn conversations are cheaper (less context setup)
2. **Cache dataset statistics**: Consider caching `/api/ai-dataset-insights` for 1 hour
3. **Batch requests**: Combine feature importance queries into single endpoint call
4. **Use timeouts**: Default 10s; adjust lower if network is fast

### Cost Estimation
- Single prediction explanation: ~500-700 tokens (gpt-4o-mini: $0.00015)
- Full dataset insights: ~2000-3000 tokens ($0.0005)
- Multi-turn conversation (10 exchanges): ~5000-7000 tokens total ($0.0015)

---

## Limitations & Known Issues

### Intentional Limitations
1. **No raw data to LLM**: By design, to protect privacy
2. **No persistent conversation**: Sessions cleared on server restart
3. **No custom model fine-tuning**: Uses base gpt-4o-mini model
4. **No multi-user conversation sharing**: Each user has separate conversation store

### Known Limitations
1. **Datetime deprecation warnings**: Use `datetime.now(datetime.UTC)` instead of `utcnow()` in Python 3.13+
2. **Large dataset performance**: Computing stats on 10k+ rows may take 5+ seconds
3. **No offline mode**: Requires OpenAI API connectivity

### Future Improvements
1. Persistent conversation database (MongoDB/PostgreSQL)
2. Conversation export/sharing
3. Custom system prompts per user/organization
4. Support for other LLM providers (Azure, Anthropic, etc.)

---

## Debugging

### Enable Verbose Logging

```python
# In llm_service.py or api.py
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `"OPENAI_API_KEY not set"` | Missing env var | Set `export OPENAI_API_KEY=sk-...` |
| `"None returned from LLM"` | Timeout or API error | Check OpenAI status, increase timeout |
| `"Invalid JSON response"` | LLM hallucinated non-JSON | System prompt should prevent; add validation |
| `"Conversation lost after refresh"` | Session-based (non-persistent) | Expected behavior; will be persistent in v2 |

### Verify Integration

```bash
# Check API key is loaded
python -c "import os; print('Key set!' if os.getenv('OPENAI_API_KEY') else 'Key missing!')"

# Test LLM connectivity
python -c "from cleverfund_backend.services.llm_service import _safe_chat_completion; print(_safe_chat_completion([{'role':'user','content':'test'}]))"

# Test conversation service
python -c "from cleverfund_backend.services.conversation_service import get_or_create_conversation; conv = get_or_create_conversation('test@ex.com', {'startup_name':'Test'}, {}); print(f'Conversation created: {conv is not None}')"
```

---

## Conclusion

CleverFund AI augments the Random Forest model with human-readable, data-grounded explanations. The architecture maintains a strict separation between immutable ML predictions and interpretive AI insights, ensuring reliability, transparency, and security.

For questions or issues, refer to the inline code comments in `llm_service.py`, `conversation_service.py`, and API endpoint docstrings.
