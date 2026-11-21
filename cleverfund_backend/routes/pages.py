"""
routes/pages.py
---------------
Renders the HTML templates that the browser navigates to.
Each view is protected by login_required_page.
"""

from flask import Blueprint, render_template, session
from .auth import login_required_page
from ..services.dataset_service import get_dataframe, prepare_report_rows, build_reports_summary

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
@login_required_page
def dashboard():
    return render_template(
        "index.html",
        user_email=session.get("user"),
        active_page="dashboard",
    )


@pages_bp.route("/reports")
@login_required_page
def reports_page():
    df, df_error = get_dataframe()

    report_rows = []
    summary     = {"quarter_total": "—", "avg_prob": "—", "success_share": "—"}

    if df is not None:
        report_rows = prepare_report_rows(df, limit=300)
        summary     = build_reports_summary(df)

    return render_template(
        "reports.html",
        user_email=session.get("user"),
        active_page="reports",
        report_rows=report_rows,
        summary=summary,
        dataset_error=df_error,
    )


@pages_bp.route("/analytics")
@login_required_page
def analytics_page():
    return render_template(
        "analytics.html",
        user_email=session.get("user"),
        active_page="analytics",
    )


@pages_bp.route("/predictions")
@login_required_page
def predictions_page():
    return render_template(
        "predictions.html",
        user_email=session.get("user"),
        active_page="predictions",
    )


@pages_bp.route("/compare")
@login_required_page
def compare_page():
    return render_template(
        "compare.html",
        user_email=session.get("user"),
        active_page="compare",
    )
