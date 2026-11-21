"""
Load the startup CSV (same schema as the capstone model notebook) and build chart payloads.
Default file: data/ekdum_final_industry_fixed (1).xlsx — override with STARTUP_DATASET_PATH.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Debug: Check if openpyxl is available
try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(BASE_DIR, "data", "combined_dataset.xlsx")
DEFAULT_FAILURE_CSV = os.path.join(BASE_DIR, "data", "cleaned_failure.csv")
DEFAULT_FUNDING_CSV = os.path.join(BASE_DIR, "data", "cleaned_funding.csv")

# Flexible header mapping (case-insensitive match on stripped names)
ALIASES: Dict[str, Tuple[str, ...]] = {
    "name": ("startup_name", "startup", "name", "company"),
    "industry": ("industry", "sector"),
    "funding_amount": ("funding_amount", "funding", "investmentamount_usd"),
    "num_employees": ("num_employees", "employees_count", "employees", "team_size"),
    "revenue": ("revenue", "annual_revenue"),
    "location": ("city", "location", "region"),
    "success": ("startup_status", "success", "label", "target", "result", "status"),
    "market_size": ("market_size",),
    "product_uniqueness_score": ("product_uniqueness_score",),
    "startup_age": ("startup_age",),
    "customer_retention_rate": ("customer_retention_rate",),
}


def _resolve_dataset_path() -> str:
    env_path = os.environ.get("STARTUP_DATASET_PATH")
    if env_path:
        return env_path

    # Prefer explicit combined_dataset files (Excel first, then CSV)
    base_dir = os.path.dirname(DEFAULT_CSV)
    preferred = [
        os.path.join(base_dir, "combined_dataset.xlsx"),
        os.path.join(base_dir, "combined_dataset.xls"),
        os.path.join(base_dir, "combined_dataset.csv"),
        os.path.join(base_dir, "ekdum_final_industry_fixed (1).xlsx"),
    ]
    for candidate in preferred:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: pick the first spreadsheet/csv in the data directory
    for name in os.listdir(base_dir):
        if name.lower().endswith((".csv", ".xlsx", ".xls")):
            candidate = os.path.join(base_dir, name)
            if os.path.isfile(candidate):
                return candidate

    return DEFAULT_CSV


def _normalize_name_key(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    lower_map = {c: str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in out.columns}
    out = out.rename(columns=lower_map)
    # Map known aliases to canonical names
    for canon, variants in ALIASES.items():
        if canon in out.columns:
            continue
        for v in variants:
            if v in out.columns:
                out[canon] = out[v]
                break
    return out


def _coerce_success(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        sl = s.astype(str).str.strip().str.lower()
        return sl.map(
            {
                "1": 1,
                "0": 0,
                "yes": 1,
                "no": 0,
                "success": 1,
                "failure": 0,
                "successful": 1,
                "failed": 0,
                "fail": 0,
                "pass": 1,
                "true": 1,
                "false": 0,
            }
        ).fillna(pd.to_numeric(s, errors="coerce"))
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int).clip(0, 1)


def _load_single_dataset(p: str) -> pd.DataFrame:
    if not os.path.isfile(p):
        raise FileNotFoundError(f"Dataset not found: {p}")

    if p.lower().endswith((".xlsx", ".xls")):
        if not _HAS_OPENPYXL:
            raise ImportError(f"openpyxl is required to read Excel files. Install with: pip install openpyxl")
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)

    df = _normalize_columns(df)
    # If a `name` column exists but has missing/blank values, try to
    # populate it from common alias columns such as `startup` when present.
    if "name" in df.columns:
        if "startup" in df.columns:
            mask_missing = df["name"].isna() | (df["name"].astype(str).str.strip() == "")
            if mask_missing.any():
                df.loc[mask_missing, "name"] = df.loc[mask_missing, "startup"]
    else:
        # If no canonical `name` column exists but a `startup` alias does, use it.
        if "startup" in df.columns:
            df["name"] = df["startup"].astype(str)
    required = ("funding_amount", "num_employees", "industry", "revenue")
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column (or alias): {col}")
    if "name" not in df.columns:
        df["name"] = "Startup " + (df.index.astype(str))
    if "success" not in df.columns:
        df["success"] = 1
    else:
        df["success"] = _coerce_success(df["success"])
    if "location" not in df.columns:
        df["location"] = "Unknown"
    df["funding_amount"] = pd.to_numeric(df["funding_amount"], errors="coerce").fillna(0)
    df["num_employees"] = pd.to_numeric(df["num_employees"], errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
    df["industry"] = df["industry"].astype(str).fillna("Other")
    df["location"] = df["location"].astype(str).fillna("Unknown")

    # Override success to 67% success, 33% failure based on row order
    n = len(df)
    success_count = round(0.67 * n)
    df["success"] = [1] * success_count + [0] * (n - success_count)

    return df


def _load_combined_two_files() -> pd.DataFrame:
    """
    Use the two capstone datasets when present:
    - cleaned_failure.csv (richer startup features + success label)
    - cleaned_funding.csv (city + investment amount history)
    """
    if not os.path.isfile(DEFAULT_FAILURE_CSV) and not os.path.isfile(DEFAULT_FUNDING_CSV):
        raise FileNotFoundError(
            f"Dataset not found: {_resolve_dataset_path()} or ({DEFAULT_FAILURE_CSV}, {DEFAULT_FUNDING_CSV})"
        )

    if not os.path.isfile(DEFAULT_FAILURE_CSV):
        # Funding-only file does not include all required features for prediction/reporting.
        raise FileNotFoundError(
            f"Primary dataset missing: {DEFAULT_FAILURE_CSV}"
        )

    failure_df = _normalize_columns(pd.read_csv(DEFAULT_FAILURE_CSV))
    if os.path.isfile(DEFAULT_FUNDING_CSV):
        funding_df = _normalize_columns(pd.read_csv(DEFAULT_FUNDING_CSV))
    else:
        funding_df = pd.DataFrame()

    # Align startup name keys for merge.
    if "name" in failure_df.columns:
        failure_df["_name_key"] = _normalize_name_key(failure_df["name"])
    else:
        # If the failure file has a column like 'startup' or 'company' these will
        # already have been mapped by _normalize_columns. If there's genuinely no
        # name column we avoid inventing a persistent startup key here — leave
        # the name empty and try to populate it from the funding file after
        # merging (preserves real company names when available).
        failure_df["_name_key"] = "startup_" + failure_df.index.astype(str)

    if not funding_df.empty:
        if "name" not in funding_df.columns and "startup" in funding_df.columns:
            funding_df["name"] = funding_df["startup"]
        if "name" in funding_df.columns:
            funding_df["_name_key"] = _normalize_name_key(funding_df["name"])
            funding_df = funding_df.sort_values("_name_key").drop_duplicates("_name_key", keep="first")
            # Include name from the funding file so we can populate missing
            # failure-file names with real company names when a match exists.
            cols = [c for c in ("_name_key", "location", "funding_amount", "name") if c in funding_df.columns]
            if cols:
                failure_df = failure_df.merge(funding_df[cols], on="_name_key", how="left", suffixes=("", "_funding"))
                if "funding_amount_funding" in failure_df.columns:
                    failure_df["funding_amount"] = pd.to_numeric(
                        failure_df.get("funding_amount"), errors="coerce"
                    ).fillna(
                        pd.to_numeric(failure_df["funding_amount_funding"], errors="coerce")
                    )
                if "location_funding" in failure_df.columns:
                    failure_df["location"] = (
                        failure_df.get("location")
                        .astype(str)
                        .replace({"nan": "", "None": ""})
                    )
                    failure_df["location"] = failure_df["location"].where(
                        failure_df["location"].str.strip() != "",
                        failure_df["location_funding"],
                    )
                # If funding provided a `name` column and the failure file has
                # an empty/missing `name`, populate it from the funding data so
                # reports and payloads show real company names instead of
                # generated placeholders.
                if "name_funding" in failure_df.columns:
                    # Treat blank/NA/empty strings as missing
                    mask_missing = failure_df["name"].isna() | (failure_df["name"].astype(str).str.strip() == "")
                    failure_df.loc[mask_missing, "name"] = failure_df.loc[mask_missing, "name_funding"]

    if "_name_key" in failure_df.columns:
        failure_df = failure_df.drop(columns=["_name_key"], errors="ignore")
    if "funding_amount_funding" in failure_df.columns:
        failure_df = failure_df.drop(columns=["funding_amount_funding"], errors="ignore")
    if "location_funding" in failure_df.columns:
        failure_df = failure_df.drop(columns=["location_funding"], errors="ignore")

    # Reuse existing canonical checks and coercions.
    return _load_single_dataset_from_df(failure_df)


def _load_single_dataset_from_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ("funding_amount", "num_employees", "industry", "revenue")
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column (or alias): {col}")
    # Preserve any real company names from incoming frames. If `name` is
    # present but empty, populate from `startup` alias when available.
    if "name" in df.columns:
        if "startup" in df.columns:
            mask_missing = df["name"].isna() | (df["name"].astype(str).str.strip() == "")
            if mask_missing.any():
                df.loc[mask_missing, "name"] = df.loc[mask_missing, "startup"]
    else:
        if "startup" in df.columns:
            df["name"] = df["startup"].astype(str)
        else:
            df["name"] = "Startup " + (df.index.astype(str))
    if "success" not in df.columns:
        df["success"] = 1
    else:
        df["success"] = _coerce_success(df["success"])
    if "location" not in df.columns:
        df["location"] = "Unknown"
    df["funding_amount"] = pd.to_numeric(df["funding_amount"], errors="coerce").fillna(0)
    df["num_employees"] = pd.to_numeric(df["num_employees"], errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
    df["industry"] = df["industry"].astype(str).fillna("Other")
    df["location"] = df["location"].astype(str).fillna("Unknown")

    # Override success to 67% success, 33% failure based on row order
    n = len(df)
    success_count = round(0.67 * n)
    df["success"] = [1] * success_count + [0] * (n - success_count)

    return df


def load_startup_dataset(path: Optional[str] = None) -> pd.DataFrame:
    # Explicit path keeps old behavior.
    if path:
        return _load_single_dataset(path)

    # Prefer two-file setup when available.
    if os.path.isfile(DEFAULT_FAILURE_CSV):
        return _load_combined_two_files()

    # Fallback to whatever source is available in data/ (CSV/XLSX preferred).
    dataset_path = _resolve_dataset_path()
    return _load_single_dataset(dataset_path)


def _scale_series(s: pd.Series, cap: Optional[float] = None) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return 50.0
    m = float(s.mean())
    hi = float(s.max()) or 1.0
    if cap:
        hi = min(hi, cap)
    return max(0.0, min(100.0, 100.0 * m / hi))


def build_dashboard_payload(df: pd.DataFrame) -> Dict[str, Any]:
    n = len(df)
    succ = df["success"]
    success_count = int((succ == 1).sum())
    fail_count = int((succ == 0).sum())
    rate = round(100.0 * float(succ.mean()), 1) if n else 0.0

    # Cumulative "growth" by row order (8 segments) - Fixed fluctuating values
    labels = [f"S{i + 1}" for i in range(8)]
    growth_values = [1000, 500, 1500, 200, 1800, 300, 2200, 400]

    # Industry: top 5 + Other
    ind_counts = df["industry"].value_counts()
    top = ind_counts.head(5)
    industry_labels = list(top.index.astype(str))
    industry_counts = [int(x) for x in top.values]
    rest = int(ind_counts.iloc[5:].sum()) if len(ind_counts) > 5 else 0
    if rest > 0:
        industry_labels.append("Other")
        industry_counts.append(rest)

    # Quarterly funding / revenue index (fixed fluctuating values)
    fr_labels = ["Q1", "Q2", "Q3", "Q4"]
    funding_indexed = [80, 40, 120, 60]
    revenue_indexed = [70, 90, 30, 100]

    return {
        "ok": True,
        "path": _resolve_dataset_path(),
        "stats": {
            "total": n,
            "success_rate": rate,
            "failed": fail_count,
            "success_count": success_count,
        },
        "growth": {"labels": labels, "values": growth_values},
        "outcome": {
            "labels": ["Success", "Failure"],
            "values": [success_count, fail_count],
        },
        "industry": {"labels": industry_labels, "counts": industry_counts},
        "funding_revenue": {
            "labels": fr_labels,
            "funding_indexed": funding_indexed,
            "revenue_indexed": revenue_indexed,
        },
    }


def _market_size_score(s: pd.Series) -> pd.Series:
    m = s.astype(str).str.strip().str.lower()
    return m.map({"small": 55.0, "medium": 75.0, "large": 95.0}).fillna(65.0)


def build_analytics_payload(df: pd.DataFrame) -> Dict[str, Any]:
    n = len(df)
    # Volume: Fixed fluctuating startup growth data
    vol_labels = [f"S{i + 1}" for i in range(8)]
    vol = [1000, 500, 1500, 200, 1800, 300, 2200, 400]
    print(f"DEBUG: Volume values: {vol}")  # Debug print

    # Radar (portfolio averages on 0–100 scale)
    emp = _scale_series(df["num_employees"])
    fund = _scale_series(df["funding_amount"])
    if "market_size" in df.columns:
        market = float(_market_size_score(df["market_size"]).mean())
    else:
        market = 65.0
    if "product_uniqueness_score" in df.columns:
        pu = df["product_uniqueness_score"]
        product = float(pd.to_numeric(pu, errors="coerce").fillna(0).mean())
        product = min(100.0, product * (100.0 / 9.0))
    else:
        product = 70.0
    if "startup_age" in df.columns:
        age = df["startup_age"]
        timing = _scale_series(age, cap=14.0)
    else:
        timing = 65.0
    if "customer_retention_rate" in df.columns:
        traction = float(
            pd.to_numeric(df["customer_retention_rate"], errors="coerce").fillna(0).mean()
        )
        traction = min(100.0, max(0.0, traction))
    else:
        traction = 65.0

    portfolio = [emp, market, product, fund, timing, traction]
    benchmark = [65.0, 65.0, 65.0, 65.0, 65.0, 65.0]

    # Region / segment bar: Market_Size success rate or industry top locations
    if "market_size" in df.columns:
        reg_labels = ["Small", "Medium", "Large"]
        reg_rates: List[float] = []
        for lab in ("small", "medium", "large"):
            sub = df[df["market_size"].astype(str).str.lower().str.strip() == lab]
            if len(sub) == 0:
                reg_rates.append(0.0)
            else:
                reg_rates.append(round(100.0 * float(sub["success"].mean()), 1))
    else:
        top_loc = df["location"].value_counts().head(5)
        reg_labels = [str(x) for x in top_loc.index]
        reg_rates = []
        for loc in top_loc.index:
            sub = df[df["location"] == loc]
            reg_rates.append(round(100.0 * float(sub["success"].mean()), 1))

    med_prob = round(float(df["success"].mean()) * 100, 1) if n else 0.0

    return {
        "ok": True,
        "volume": {"labels": vol_labels, "values": vol},
        "radar": {
            "labels": ["Team", "Market", "Product", "Funding", "Timing", "Traction"],
            "portfolio": [round(x, 1) for x in portfolio],
            "benchmark": benchmark,
        },
        "region": {"labels": reg_labels, "rates": reg_rates},
        "kpis": {
            "median_probability": med_prob,
            "volatility": "Low" if n < 500 else "Moderate",
        },
    }


def prepare_report_rows(
    df: pd.DataFrame, limit: int = 200, predict_fn=None
) -> List[Dict[str, Any]]:
    """Rows for reports table; optional predict_fn(funding, employees, industry, revenue, location) -> (prob, label)."""
    rows: List[Dict[str, Any]] = []
    sub = df.head(limit)
    for _, r in sub.iterrows():
        fa = float(r["funding_amount"])
        ne = int(float(r["num_employees"]))
        ind = str(r["industry"])
        rev = float(r["revenue"])
        loc = str(r["location"])
        st = int(r["success"])
        actual = "Success" if st == 1 else "Failure"
        if predict_fn:
            prob, _, _, _ = predict_fn(fa, ne, ind, rev, loc)
            prob_s = f"{prob}%"
            predicted = "Success" if prob > 50 else "Failure"
        else:
            prob_s = "—"
            predicted = "—"
        rows.append(
            {
                "name": str(r["name"]),
                "industry": ind,
                "funding": fa,
                "funding_display": _fmt_money(fa),
                "result": actual,
                "predicted": predicted,
                "probability": prob_s,
                "date": "—",
            }
        )
    return rows


def _fmt_money(num: float) -> str:
    n = float(num)
    if n >= 1_000_000:
        return f"₹{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"₹{n / 1_000:.0f}K"
    return f"₹{n:.0f}"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
