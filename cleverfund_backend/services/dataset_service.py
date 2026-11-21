"""
services/dataset_service.py
----------------------------
Reads the dataset (CSV or Excel, default: data/ekdum_final_industry_fixed (1).xlsx) and builds
the JSON payloads consumed by the dashboard and analytics pages.

This is a thin wrapper around pandas — all the heavy lifting
(column normalisation, aggregation) lives here so the routes
stay short and readable.
"""

import os
import io
from functools import lru_cache
from typing import Optional

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_CSV = os.environ.get(
    "STARTUP_DATASET_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "combined_dataset.csv"),
)

# We load the dataframe once and cache it for the lifetime of the process.
_cached_df: Optional[pd.DataFrame] = None
_cached_error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
def load_dataset(csv_path: str = DEFAULT_CSV) -> pd.DataFrame:
    """Load and normalise the dataset (CSV or Excel). Raises on error."""
    # Support both CSV and Excel data sources; prefer Excel when provided.
    lower = str(csv_path).lower()
    if lower.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(csv_path)
    else:
        df = pd.read_csv(csv_path, low_memory=False)

    # Normalise column names: lowercase + underscores
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Map 'startup_status' / 'success' columns → integer 0/1
    if "success" not in df.columns:
        status_col = next(
            (c for c in df.columns if "status" in c or "success" in c), None
        )
        if status_col:
            df["success"] = (
                df[status_col]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({"success": 1, "successful": 1, "1": 1, "true": 1})
                .fillna(0)
                .astype(int)
            )
        else:
            df["success"] = 0

    # Ensure numeric columns exist with safe defaults
    for col, default in [
        ("funding_amount", 0.0),
        ("num_employees",  0),
        ("revenue",        0.0),
    ]:
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

    # Ensure text columns exist
    for col in ("industry", "location", "startup_name"):
        if col not in df.columns:
            df[col] = "Unknown"
        else:
            df[col] = df[col].astype(str).str.strip()

    return df


def get_dataframe() -> tuple:
    """
    Return (df, error_message).
    df is None if loading failed; error_message is None on success.
    Caches result for process lifetime.
    """
    global _cached_df, _cached_error
    if _cached_error is not None:
        return None, _cached_error
    if _cached_df is None:
        try:
            _cached_df = load_dataset()
        except Exception as exc:
            _cached_error = str(exc)
            return None, _cached_error
    return _cached_df, None


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard payload
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard_payload(df: pd.DataFrame) -> dict:
    """
    Build the JSON object consumed by /api/dashboard-data.

    Shape
    -----
    {
      ok: true,
      stats: { total, success_rate, failed },
      growth: { labels, values },
      outcome: { labels, values },
      industry: { labels, counts },
      funding_revenue: { labels, funding_indexed, revenue_indexed }
    }
    """
    n       = len(df)
    success = int(df["success"].sum())
    failed  = n - success
    rate    = round(100 * success / n, 2) if n else 0.0

    # Growth trend — success rate % across 8 funding-level segments
    # Sorting by funding creates a natural upward trend (more funding → more success)
    df_sorted = df.sort_values("funding_amount", ascending=True).reset_index(drop=True)
    chunk = max(1, n // 8)
    growth_values = []
    for i in range(0, min(n, chunk * 8), chunk):
        seg = df_sorted.iloc[i : i + chunk]
        seg_total = len(seg)
        seg_success = int(seg["success"].sum())
        rate_pct = round(100 * seg_success / seg_total, 1) if seg_total else 0
        growth_values.append(rate_pct)
    growth_labels = [f"S{i+1}" for i in range(len(growth_values))]

    # Industry distribution (top 5)
    ind_counts = (
        df["industry"]
        .value_counts()
        .head(5)
    )
    industry_labels = ind_counts.index.tolist()
    industry_counts = ind_counts.values.tolist()

    # Funding vs revenue — 4 equal groups, indexed to 0–100
    df2 = df.copy()
    df2["group"] = pd.qcut(df2.index, q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
    grp = df2.groupby("group", observed=True)[["funding_amount", "revenue"]].mean()
    f_max = grp["funding_amount"].max() or 1
    r_max = grp["revenue"].max() or 1
    fr_labels         = grp.index.astype(str).tolist()
    funding_indexed   = [round(v / f_max * 100, 1) for v in grp["funding_amount"]]
    revenue_indexed   = [round(v / r_max * 100, 1) for v in grp["revenue"]]

    return {
        "ok": True,
        "stats": {
            "total":        n,
            "success_rate": rate,
            "failed":       failed,
        },
        "growth": {
            "labels": growth_labels,
            "values": growth_values,
        },
        "outcome": {
            "labels": ["Success", "Failure"],
            "values": [success, failed],
        },
        "industry": {
            "labels": industry_labels,
            "counts": industry_counts,
        },
        "funding_revenue": {
            "labels":           fr_labels,
            "funding_indexed":  funding_indexed,
            "revenue_indexed":  revenue_indexed,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Analytics payload
# ─────────────────────────────────────────────────────────────────────────────

def build_analytics_payload(df: pd.DataFrame) -> dict:
    """
    Build the JSON object consumed by /api/analytics-data.

    Shape
    -----
    {
      ok: true,
      kpis: { median_probability, volatility },
      volume: { labels, values },
      radar: { labels, portfolio, benchmark },
      region: { labels, rates }
    }
    """
    n = len(df)
    success_rate = df["success"].mean() * 100 if n else 0.0

    # KPIs
    median_prob = round(success_rate, 1)
    volatility  = "Low" if n > 5000 else ("Medium" if n > 1000 else "High")

    # Volume (same as dashboard growth)
    chunk = max(1, n // 8)
    vol_values = [
        int(df.iloc[i : i + chunk].shape[0])
        for i in range(0, min(n, chunk * 8), chunk)
    ]
    vol_labels = [f"S{i+1}" for i in range(len(vol_values))]

    # Radar — scale feature averages to 0-100
    def scale(series, max_val):
        m = series.mean()
        return round(min(100, m / max_val * 100), 1) if max_val else 50.0

    radar_data = {
        "labels":    ["Funding", "Team", "Revenue", "Success Rate", "Scale", "Diversity"],
        "portfolio": [
            scale(df["funding_amount"], 10_000_000),
            scale(df["num_employees"],  500),
            scale(df["revenue"],        20_000_000),
            round(success_rate, 1),
            min(100, round(n / 100, 1)),
            min(100, round(df["industry"].nunique() * 10, 1)),
        ],
        "benchmark": [60, 55, 60, 50, 70, 65],
    }

    # Region — top-5 locations by success rate (min 5 samples)
    region_df = (
        df.groupby("location")["success"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "successes", "count": "total"})
        .query("total >= 5")
        .assign(rate=lambda d: (d["successes"] / d["total"] * 100).round(1))
        .sort_values("rate", ascending=False)
        .head(5)
    )
    region_data = {
        "labels": region_df.index.tolist() or ["Unknown"],
        "rates":  region_df["rate"].tolist() or [0],
    }

    return {
        "ok":     True,
        "kpis":   {"median_probability": median_prob, "volatility": volatility},
        "volume": {"labels": vol_labels, "values": vol_values},
        "radar":  radar_data,
        "region": region_data,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Reports helpers
# ─────────────────────────────────────────────────────────────────────────────

def prepare_report_rows(df: pd.DataFrame, limit: int = 300) -> list:
    """
    Return up to `limit` rows formatted for the reports table.
    Each item: { name, funding_display, result, probability }
    """
    from .prediction_service import rule_based_predict

    sample  = df.head(limit)
    results = []

    for _, row in sample.iterrows():
        try:
            prob, res, _, _ = rule_based_predict(
                float(row["funding_amount"]),
                int(row["num_employees"]),
                str(row["industry"]),
                float(row["revenue"]),
                str(row["location"]),
            )
        except Exception:
            prob, res = 0.0, "Unknown"

        funding = float(row["funding_amount"])
        if funding >= 1_000_000:
            f_display = f"₹{funding/1_000_000:.1f}M"
        elif funding >= 1_000:
            f_display = f"₹{funding/1_000:.0f}K"
        else:
            f_display = f"₹{funding:.0f}"

        results.append({
            "name":            str(row.get("startup_name", "Unknown")),
            "funding_display": f_display,
            "result":          res,
            "probability":     f"{prob:.1f}%",
        })

    return results


def build_reports_summary(df: pd.DataFrame) -> dict:
    """Return the three KPI cards shown on the reports page."""
    n = len(df)
    succ = int(df["success"].sum())
    success_share = f"{round(100 * succ / n)}%" if n else "—"

    # Average probability across first 400 rows
    from .prediction_service import rule_based_predict
    sample = df.head(400)
    probs  = []
    for _, row in sample.iterrows():
        try:
            p, _, _, _ = rule_based_predict(
                float(row["funding_amount"]),
                int(row["num_employees"]),
                str(row["industry"]),
                float(row["revenue"]),
                str(row["location"]),
            )
            probs.append(p)
        except Exception:
            pass

    avg_prob = f"{round(sum(probs)/len(probs))}%" if probs else "—"

    return {
        "quarter_total": str(n),
        "avg_prob":      avg_prob,
        "success_share": success_share,
    }


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise the dataframe to UTF-8 CSV bytes for download."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
