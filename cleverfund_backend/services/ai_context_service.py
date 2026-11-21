"""Lightweight dataset retrieval and context builder for RAG.

Loads the dataset via the existing dataset service and returns a compact
context object containing aggregate stats and a few representative similar
records. Avoids sending raw rows to the LLM beyond a small sample.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import logging

from .dataset_service import load_dataset

logger = logging.getLogger(__name__)


def _similarity_filter(df: pd.DataFrame, startup: Dict[str, Any]) -> pd.DataFrame:
    """Return subset of df with similar startups based on key fields.
    
    Uses industry, location, and funding/revenue/employee proximity.
    """
    df2 = df.copy()
    
    # Start with no filter (all rows)
    mask = pd.Series([True] * len(df2))
    
    # Industry filter (exact match, case-insensitive)
    ind = str(startup.get("industry", "")).strip().lower()
    if ind and ind != "unknown":
        industry_mask = df2.get("industry", "").astype(str).str.lower().str.contains(ind, na=False)
        if industry_mask.any():
            mask = mask & industry_mask
    
    # Location / City filter (exact match, case-insensitive)
    loc = str(startup.get("location", "")).strip().lower()
    if loc and loc != "unknown":
        location_mask = df2.get("location", "").astype(str).str.lower().str.contains(loc, na=False)
        if location_mask.any():
            mask = mask & location_mask
    
    # Funding proximity: within 50% to 200% of input
    try:
        fund = float(startup.get("funding_amount") or 0)
        if fund > 0:
            lower = fund * 0.5
            upper = fund * 2.0
            mask = mask & (df2["funding_amount"] >= lower) & (df2["funding_amount"] <= upper)
    except Exception:
        pass
    
    # Revenue proximity: within 50% to 200% of input
    try:
        rev = float(startup.get("revenue") or 0)
        if rev > 0:
            lower = rev * 0.5
            upper = rev * 2.0
            mask = mask & (df2["revenue"] >= lower) & (df2["revenue"] <= upper)
    except Exception:
        pass
    
    # Employees: within ±50%
    try:
        emp = int(startup.get("employees", 0) or 0)
        if emp > 0:
            lower = max(1, emp // 2)
            upper = int(emp * 1.5)
            mask = mask & (df2["num_employees"] >= lower) & (df2["num_employees"] <= upper)
    except Exception:
        pass
    
    subset = df2[mask]
    
    # If too restrictive, relax to just industry + funding range
    if subset.empty and ind and ind != "unknown":
        subset = df2[df2["industry"].astype(str).str.lower().str.contains(ind, na=False)]
    
    # If still empty, return all
    if subset.empty:
        subset = df2
    
    return subset


def build_dataset_context(startup: Dict[str, Any], sample_n: int = 5) -> Optional[Dict[str, Any]]:
    """Build compact context: aggregates and a small sample of similar startups.
    
    Returns a dict with dataset statistics ready for the LLM, or None on error.
    Statistics are computed locally; never sends raw dataset to LLM.
    """
    try:
        df = load_dataset()
    except Exception as exc:
        logger.exception("Failed to load dataset: %s", exc)
        return None
    
    if df.empty:
        logger.warning("Dataset is empty")
        return None
    
    # Find similar startups
    sim = _similarity_filter(df, startup)
    
    # Calculate aggregates for similar startups
    similar_count = int(len(sim))
    
    if similar_count > 0:
        success_rate = float(sim["success"].mean() * 100) if "success" in sim.columns else 0.0
        median_funding = float(sim["funding_amount"].median()) if "funding_amount" in sim.columns else 0.0
        median_revenue = float(sim["revenue"].median()) if "revenue" in sim.columns else 0.0
        median_employees = float(sim["num_employees"].median()) if "num_employees" in sim.columns else 0.0
        median_burn = float(sim.get("burn_rate", sim.get("Burn_Rate")).median()) if "burn_rate" in sim.columns or "Burn_Rate" in sim.columns else None
        avg_retention = float(sim.get("customer_retention_rate", sim.get("Customer_Retention_Rate")).mean()) if "customer_retention_rate" in sim.columns or "Customer_Retention_Rate" in sim.columns else None
    else:
        success_rate = 0.0
        median_funding = 0.0
        median_revenue = 0.0
        median_employees = 0.0
        median_burn = None
        avg_retention = None
    
    # Industry level statistics (minimum 3 samples)
    industry = str(startup.get("industry", "")).strip()
    industry_rate = None
    if industry and industry.lower() != "unknown":
        try:
            industry_df = df[df["industry"].astype(str).str.lower().str.contains(industry.lower(), na=False)]
            if len(industry_df) >= 3:
                industry_rate = float(industry_df["success"].mean() * 100)
        except Exception:
            pass
    
    # Location level statistics (minimum 3 samples)
    location = str(startup.get("location", "")).strip()
    location_rate = None
    if location and location.lower() != "unknown":
        try:
            location_df = df[df["location"].astype(str).str.lower().str.contains(location.lower(), na=False)]
            if len(location_df) >= 3:
                location_rate = float(location_df["success"].mean() * 100)
        except Exception:
            pass
    
    # Representative sample (limited to sample_n rows)
    sample_rows = []
    try:
        for _, r in sim.head(sample_n).iterrows():
            sample_rows.append({
                "startup_name": str(r.get("startup_name", r.get("Startup_Name", ""))).strip(),
                "funding_amount": float(r.get("funding_amount", 0) or 0),
                "revenue": float(r.get("revenue", 0) or 0),
                "num_employees": int(r.get("num_employees", 0) or 0),
                "industry": str(r.get("industry", r.get("Industry", ""))).strip(),
                "location": str(r.get("location", r.get("City", ""))).strip(),
                "success": int(r.get("success", 0) or 0),
            })
    except Exception as exc:
        logger.warning("Failed to extract representative samples: %s", exc)
    
    # Build compact context object
    context = {
        "similar_count": similar_count,
        "similar_success_rate": round(success_rate, 1) if success_rate >= 0 else None,
        "median_funding": int(median_funding) if median_funding > 0 else None,
        "median_revenue": int(median_revenue) if median_revenue > 0 else None,
        "median_employees": int(median_employees) if median_employees > 0 else None,
        "median_burn_rate": int(median_burn) if median_burn and median_burn > 0 else None,
        "avg_customer_retention": round(avg_retention, 1) if avg_retention and avg_retention >= 0 else None,
        "industry_success_rate": round(industry_rate, 1) if industry_rate and industry_rate >= 0 else None,
        "location_success_rate": round(location_rate, 1) if location_rate and location_rate >= 0 else None,
        "representative_startups": sample_rows,
    }
    
    return context
