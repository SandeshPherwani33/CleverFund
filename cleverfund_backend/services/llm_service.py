"""LLM service wrapper using OpenAI SDK v1.0+.

Provides safe helpers to generate AI analysis and answers grounded
on supplied dataset context. Handles missing API key and errors
gracefully so the ML prediction always remains available.
"""
from __future__ import annotations

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    OpenAI = None  # type: ignore
    _HAS_OPENAI = False

logger = logging.getLogger(__name__)

_OPENAI_WARNING_SHOWN = False
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))


def _ollama_chat_completion(messages: List[Dict[str, str]], timeout: int = 10) -> Optional[dict]:
    """Call a local Ollama server as a no-cost fallback when OpenAI is unavailable or exhausted."""
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    logger.info("Calling local Ollama model %s", OLLAMA_MODEL)
    local_messages = [
        {
            **message,
            "content": (
                "You are CleverFund AI. Use only the supplied startup, Random Forest result, and dataset facts. "
                "Never change the ML prediction or invent statistics. Return valid JSON when requested."
                if message.get("role") == "system" else message.get("content", "")
            ),
        }
        for message in messages
    ]
    payload = {
        "model": OLLAMA_MODEL,
        "messages": local_messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": 260,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            if not content:
                return None
            logger.info("Ollama response received")
            return {
                "choices": [
                    {"message": {"content": content}}
                ]
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("Ollama fallback failed: %s", exc)
        return None


def _build_local_fallback_response(messages: List[Dict[str, str]]) -> Optional[dict]:
    """Generate a deterministic offline response when no external model is available.

    This preserves app functionality in demo/offline environments without paid API
    credits and provides useful startup analysis even when Ollama is unavailable.
    """
    try:
        latest_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user = msg.get("content", "")
                break

        startup_bits = []
        for token in ("Startup:", "Industry:", "Location:", "Funding:", "ML Prediction:"):
            if token in latest_user:
                startup_bits.append(token)

        summary = (
            "The local offline analysis mode is active. Based on the startup profile and model score, "
            "the business appears to need a stronger risk-control plan and clearer revenue validation."
        )
        if "Question:" in latest_user:
            q = latest_user.split("Question:", 1)[1].split("\n", 1)[0].strip()
            summary = f"Based on the current startup profile, the main focus for '{q}' is to validate the business model and improve operational resilience."

        return {
            "choices": [
                {
                    "message": {
                        "content": summary
                    }
                }
            ]
        }
    except Exception:
        return {
            "choices": [{"message": {"content": "The local offline model generated a response based on the available startup data."}}]
        }


def _safe_chat_completion(messages: List[Dict[str, str]], timeout: int = 10) -> Optional[dict]:
    global _OPENAI_WARNING_SHOWN
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    fallback_response = _build_local_fallback_response(messages)

    # Ollama is the default provider so local development does not depend on a cloud key.
    if LLM_PROVIDER == "ollama":
        ollama_resp = _ollama_chat_completion(messages, timeout=max(timeout, OLLAMA_TIMEOUT))
        if ollama_resp is not None:
            return ollama_resp

    if _HAS_OPENAI and openai_api_key:
        try:
            logger.info("Calling OpenAI model %s", OPENAI_MODEL)
            client = OpenAI(api_key=openai_api_key, timeout=timeout)
            resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
            logger.info("OpenAI response received")
            return {
                "choices": [
                    {
                        "message": {
                            "content": resp.choices[0].message.content
                        }
                    }
                ]
            }
        except Exception as exc:
            logger.warning("OpenAI LLM call failed: %s", exc)

    if not _OPENAI_WARNING_SHOWN:
        logger.warning(
            "LLM provider unavailable; using local Ollama or offline fallback."
        )
        _OPENAI_WARNING_SHOWN = True

    if LLM_PROVIDER != "ollama":
        ollama_resp = _ollama_chat_completion(messages, timeout=timeout)
        if ollama_resp is not None:
            return ollama_resp

    if LLM_PROVIDER == "ollama":
        logger.warning("Ollama is unavailable; returning offline fallback response.")
        if fallback_response is not None:
            return fallback_response
        return {
            "choices": [{"message": {"content": "The local offline model generated a response based on the available startup data."}}]
        }

    logger.warning("No external LLM available. Returning local offline fallback response.")
    return fallback_response or {
        "choices": [{"message": {"content": "The local offline model generated a response based on the available startup data."}}]
    }


SYSTEM_PROMPT = (
    "You are CleverFund AI, an intelligent startup analysis assistant grounded in historical data and ML models.\n"
    "\n"
    "YOUR CORE ROLE:\n"
    "- Explain ML predictions using actual historical startup evidence\n"
    "- Provide practical, evidence-based insights for startup founders and investors\n"
    "- Never replace or modify the ML model's prediction\n"
    "- Help users understand WHY a prediction was made, not WHAT to do\n"
    "\n"
    "CRITICAL RULES (DO NOT VIOLATE THESE):\n"
    "1. The Random Forest + SMOTE model prediction is the ONLY source of truth for success probability.\n"
    "   - Never change, round, or reinterpret the model's predicted percentage.\n"
    "   - Always state: 'The model predicts [X]% probability of success.'\n"
    "\n"
    "2. Dataset statistics are facts — NEVER invent numbers.\n"
    "   - Only use percentages, counts, and metrics explicitly provided to you.\n"
    "   - If a statistic is unavailable, say: 'Insufficient data' not a guess.\n"
    "   - Never calculate or derive new statistics from the data.\n"
    "\n"
    "3. Clearly distinguish ALWAYS:\n"
    "   - ML PREDICTION: 'The Random Forest model predicts success with [X]% confidence.'\n"
    "   - DATASET EVIDENCE: 'In the historical dataset, [X] similar startups showed a [Y]% success rate.'\n"
    "   - AI INTERPRETATION: 'This comparison suggests that [inference based on data].'\n"
    "   - RECOMMENDATIONS: 'To improve outcomes, you might consider [actionable suggestion].'\n"
    "\n"
    "4. Do NOT claim causation.\n"
    "   - Avoid: 'High funding CAUSES success.'\n"
    "   - Use: 'Startups with high funding in this dataset had a higher success rate.'\n"
    "\n"
    "5. Handle missing context gracefully.\n"
    "   - If dataset evidence is unavailable: 'Historical comparison data is not available.'\n"
    "   - If conversation context is insufficient: Acknowledge and ask clarifying questions.\n"
    "   - If a question is unanswerable: Say so honestly.\n"
    "\n"
    "6. For structured responses, always return valid JSON with these keys:\n"
    "   summary, prediction_explanation, strengths, risks, recommendations, next_steps, dataset_insight, disclaimer\n"
    "\n"
    "CONVERSATION MODE:\n"
    "- Remember the startup context (name, industry, location, metrics).\n"
    "- Reference previous conversation turns when relevant.\n"
    "- Provide follow-up insights based on earlier exchanges.\n"
    "- But always re-verify data consistency when context changes.\n"
)


def generate_startup_analysis(startup_data: dict, ml_result: dict, dataset_context: dict, timeout: int = 10) -> Optional[dict]:
    """Generate structured AI analysis for a startup grounded in dataset evidence.

    Returns the structured dict on success, or None on failure.
    """
    context_note = ""
    if dataset_context:
        if dataset_context.get("similar_count", 0) > 0:
            context_note = (
                f"Dataset evidence: {dataset_context.get('similar_count')} similar startups found. "
                f"Success rate among similar: {dataset_context.get('similar_success_rate')}%. "
                f"Industry success rate: {dataset_context.get('industry_success_rate')}%. "
                f"Median funding in similar group: ₹{dataset_context.get('median_funding')}. "
            )
        else:
            context_note = "Dataset evidence: Insufficient similar startups available for comparison."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyze this startup using the ML prediction and historical dataset evidence.\n\n"
                f"Startup: {startup_data.get('startup_name', 'Unknown')}\n"
                f"Industry: {startup_data.get('industry')}\n"
                f"Location: {startup_data.get('location')}\n"
                f"Funding: ₹{startup_data.get('funding_amount')}\n"
                f"Revenue: ₹{startup_data.get('revenue')}\n"
                f"Employees: {startup_data.get('employees')}\n\n"
                f"ML Prediction: {ml_result.get('prediction')} (Confidence: {ml_result.get('success_probability')}%)\n\n"
                f"Historical Context:\n{context_note}\n"
                f"Representative similar startups: {dataset_context.get('representative_startups', []) if dataset_context else []}\n\n"
                "Return JSON with: summary (2-3 sentences), prediction_explanation (why this prediction makes sense), "
                "strengths (array), risks (array), recommendations (array of {priority, title, description}), "
                "next_steps (array), dataset_insight (how this compares to similar startups), disclaimer."
            ),
        },
    ]

    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None

    try:
        content = resp["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            try:
                start = content.index('{')
                end = content.rindex('}')
                candidate = content[start:end+1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                summary_text = content.strip() or "The current startup profile suggests a need to improve traction and reduce execution risk."
                ml_prediction = ml_result.get("prediction", "Unknown")
                prob = ml_result.get("success_probability", 50)
                startup_name = startup_data.get("startup_name", "This startup")
                industry = startup_data.get("industry", "the selected industry")
                return {
                    "summary": f"{startup_name} is being evaluated in {industry} with a model prediction of {ml_prediction} ({prob}% success probability). {summary_text}",
                    "prediction_explanation": "The model balances funding, revenue, team size, and industry fit for the current startup profile before making its prediction.",
                    "strengths": ["Operational focus", "Market alignment", "Data-backed assessment"],
                    "risks": ["Limited traction", "Execution risk", "Funding pressure"],
                    "recommendations": [
                        {"priority": "High", "title": "Validate monetization", "description": "Convert early traction into repeatable revenue before scale-up."},
                        {"priority": "High", "title": "Strengthen team execution", "description": "Reduce critical-role gaps and improve delivery consistency."}
                    ],
                    "next_steps": ["Review funnel quality", "Tighten operating metrics", "Reassess capital need"],
                    "dataset_insight": context_note or "Historical comparison data for this startup is limited.",
                    "disclaimer": "Offline fallback analysis generated from the available startup profile and model result."
                }
    except Exception:
        logger.exception("Failed to extract LLM response content")
        return None


def _normalize_question_content(content: str) -> str:
    """Turn Ollama's occasional structured JSON answer into readable chat text."""
    text = (content or "").strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            answer = parsed.get("answer")
            if answer:
                return str(answer)
            parts = []
            for key in ("summary", "prediction_explanation", "recommendations", "next_steps"):
                value = parsed.get(key)
                if isinstance(value, list):
                    value = " ".join(str(item) for item in value)
                if value:
                    parts.append(str(value))
            if parts:
                return "\n\n".join(parts)
    except (TypeError, ValueError):
        pass
    return text


def answer_startup_question(question: str, startup_data: dict, ml_result: dict, dataset_context: dict, timeout: int = 8) -> Optional[dict]:
    """Answer a question about the startup using dataset context.
    
    Grounded in actual historical startup data, never inventing statistics.
    """
    context_summary = ""
    if dataset_context:
        similar = dataset_context.get("similar_count", 0)
        success_rate = dataset_context.get("similar_success_rate")
        industry_rate = dataset_context.get("industry_success_rate")
        if similar > 0:
            context_summary = (
                f"There are {similar} similar startups in our dataset. "
                f"Among them, {success_rate}% succeeded. "
            )
            if industry_rate:
                context_summary += f"Overall, {industry_rate}% of {startup_data.get('industry')} startups succeeded."
        else:
            context_summary = "Insufficient similar startup data is available for detailed comparison."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Startup: {startup_data.get('startup_name', 'Unnamed')}\n"
                f"Industry: {startup_data.get('industry')}, Location: {startup_data.get('location')}\n"
                f"Funding: ₹{startup_data.get('funding_amount')}, Revenue: ₹{startup_data.get('revenue')}\n"
                f"Team size: {startup_data.get('employees')} employees\n\n"
                f"ML Prediction: {ml_result.get('prediction')} ({ml_result.get('success_probability')}% confidence)\n\n"
                f"Historical Context:\n{context_summary}\n\n"
                "Answer the question using the ML prediction and historical data. "
                "Use specific numbers from the provided context only. Never invent statistics. "
                "Be practical and actionable."
            ),
        },
    ]

    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None

    try:
        content = resp["choices"][0]["message"]["content"]
        return {"answer": _normalize_question_content(content)}
    except Exception:
        logger.exception("Failed to extract LLM answer")
        default_question = question.strip() or "startup outlook"
        return {"answer": f"Based on the current profile, the key issue for '{default_question}' is to improve proof of traction and reduce execution risk before pushing for scale."}


def generate_dataset_insights(dataset_context: dict, timeout: int = 10) -> Optional[dict]:
    """Ask the LLM to summarise dataset-level statistics already computed."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Summarise the following dataset statistics and provide short insights, bullets, and a one-line disclaimer.\n\n{json.dumps(dataset_context)}"},
    ]

    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None
    try:
        content = resp["choices"][0]["message"]["content"]
        return {"summary": content}
    except Exception:
        logger.exception("Failed to parse dataset insight")
        return None


def answer_startup_question_with_history(
    question: str,
    startup_data: dict,
    ml_result: dict,
    dataset_context: dict,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    timeout: int = 10
) -> Optional[dict]:
    """Answer a startup question with optional multi-turn conversation history.
    
    Supports contextual follow-up questions while maintaining data consistency.
    Bounded conversation history prevents token explosion.
    """
    if conversation_history is None:
        conversation_history = []
    
    # Build context note from dataset
    context_note = ""
    if dataset_context:
        similar = dataset_context.get("similar_count", 0)
        success_rate = dataset_context.get("similar_success_rate")
        industry_rate = dataset_context.get("industry_success_rate")
        location_rate = dataset_context.get("location_success_rate")
        
        if similar > 0:
            context_note = (
                f"Dataset: {similar} similar startups. Success rate: {success_rate}%. "
                f"Industry ({startup_data.get('industry')}): {industry_rate}%. "
                f"Location ({startup_data.get('location')}): {location_rate}%."
            )
        else:
            context_note = "Dataset: Insufficient historical comparison data."
    
    # Build startup context
    startup_context = (
        f"Startup: {startup_data.get('startup_name', 'Unnamed')}\n"
        f"Industry: {startup_data.get('industry')}\n"
        f"Location: {startup_data.get('location')}\n"
        f"Funding: ₹{startup_data.get('funding_amount', 0)}\n"
        f"Revenue: ₹{startup_data.get('revenue', 0)}\n"
        f"Employees: {startup_data.get('employees', 0)}\n"
        f"ML Prediction: {ml_result.get('prediction', 'Unknown')} "
        f"({ml_result.get('success_probability', 50)}% confidence)\n\n"
        f"Historical Context: {context_note}"
    )
    
    # Build messages with conversation history
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    
    # Add startup context as first user message if no history
    if not conversation_history:
        messages.append({
            "role": "user",
            "content": f"Analyze this startup:\n\n{startup_context}\n\nContext provided for follow-up questions."
        })
        messages.append({
            "role": "assistant",
            "content": "I have loaded the startup context. I am ready to answer questions about this startup using the ML prediction and historical data."
        })
    else:
        # Add conversation history
        messages.extend(conversation_history)
    
    # Add the current question
    messages.append({"role": "user", "content": question})
    
    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None
    
    try:
        content = resp["choices"][0]["message"]["content"]
        return {"answer": _normalize_question_content(content)}
    except Exception:
        logger.exception("Failed to extract LLM answer with history")
        return None


def generate_structured_dataset_insights(stats: dict, timeout: int = 10) -> Optional[dict]:
    """Generate structured dataset insights from pre-computed statistics.
    
    Expects stats dict with:
    - total_startups
    - overall_success_rate
    - top_industries
    - top_locations
    - median_funding
    - median_revenue
    - etc.
    
    Returns structured JSON with:
    - summary
    - key_findings
    - industry_insights
    - funding_insights
    - revenue_insights
    - recommendations
    - disclaimer
    """
    stats_summary = json.dumps(stats, indent=2)
    
    user_prompt = (
        "Analyze and summarize the following startup dataset statistics. "
        "Return a JSON object with these exact keys:\n"
        "- summary (2-3 sentences overall assessment)\n"
        "- key_findings (array of 3-5 bullet points)\n"
        "- industry_insights (array of insights by industry)\n"
        "- funding_insights (array of insights about funding levels)\n"
        "- revenue_insights (array of insights about revenue patterns)\n"
        "- recommendations (array of actionable recommendations)\n"
        "- disclaimer (one-line risk/limitation statement)\n\n"
        "REMEMBER:\n"
        "- Use ONLY the numbers provided below.\n"
        "- Never invent statistics.\n"
        "- Distinguish data facts from interpretations.\n"
        "- Be concise and actionable.\n\n"
        f"Dataset Statistics:\n{stats_summary}"
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None
    
    try:
        content = resp["choices"][0]["message"]["content"]
        # Try direct JSON parse first
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            # Try to extract JSON from within text
            try:
                start = content.index('{')
                end = content.rindex('}')
                candidate = content[start:end+1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                # Fallback to text summary
                return {
                    "summary": content,
                    "key_findings": [],
                    "industry_insights": [],
                    "funding_insights": [],
                    "revenue_insights": [],
                    "recommendations": [],
                    "disclaimer": "AI-generated summary from provided statistics"
                }
    except Exception:
        logger.exception("Failed to generate structured dataset insights")
        return None


def explain_feature_importance(
    startup_data: dict,
    ml_result: dict,
    feature_importance: Optional[Dict[str, float]] = None,
    timeout: int = 8
) -> Optional[dict]:
    """Explain which factors the ML model weighted most heavily.
    
    Helps users understand WHY the prediction was made.
    Only uses feature importance values supplied — does not invent them.
    """
    if not feature_importance:
        return {"explanation": "Feature importance data not available for this prediction."}
    
    # Sort by importance
    sorted_features = sorted(
        feature_importance.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )[:5]  # Top 5 features
    
    feature_list = "\n".join([
        f"- {name}: {value:.2%}" for name, value in sorted_features
    ])
    
    user_prompt = (
        "The following features were most important to the ML model's prediction:\n\n"
        f"{feature_list}\n\n"
        f"Startup Details:\n"
        f"- Name: {startup_data.get('startup_name')}\n"
        f"- Industry: {startup_data.get('industry')}\n"
        f"- Funding: ₹{startup_data.get('funding_amount')}\n"
        f"- Revenue: ₹{startup_data.get('revenue')}\n"
        f"- Employees: {startup_data.get('employees')}\n\n"
        f"ML Prediction: {ml_result.get('prediction')} ({ml_result.get('success_probability')}% confidence)\n\n"
        "In 2-3 sentences, explain why these factors matter for startup success. "
        "Do NOT claim causation. Use only the provided feature importance values. "
        "Return plain text (not JSON)."
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    resp = _safe_chat_completion(messages, timeout=timeout)
    if not resp:
        return None
    
    try:
        content = resp["choices"][0]["message"]["content"]
        return {"explanation": content}
    except Exception:
        logger.exception("Failed to explain feature importance")
        return None

