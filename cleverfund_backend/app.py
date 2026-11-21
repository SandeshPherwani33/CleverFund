"""
app.py  —  CleverFund Backend
==============================
Run with:
    python app.py            (development)
    gunicorn app:app         (production)

Environment variables:
    SESSION_SECRET        Secret key for Flask sessions
    DB_PATH               SQLite file path  (default: data/cleverfund.db)
    STARTUP_DATASET_PATH  dataset path  (default: data/ekdum_final_industry_fixed (1).xlsx)
    PORT                  Port number       (default: 5000)
"""

import os
from datetime import timedelta
from flask import Flask, url_for as _flask_url_for

from .models.database import init_db
from .routes.auth import auth_bp
from .routes.pages import pages_bp
from .routes.api import api_bp

# ---------------------------------------------------------------------------
# Create Flask app
# ---------------------------------------------------------------------------
def create_app():
    from dotenv import load_dotenv
    load_dotenv()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("SESSION_SECRET", "cleverfund-dev-secret-change-in-prod")
    app.permanent_session_lifetime = timedelta(days=7)

    app.register_blueprint(auth_bp)    # /login  /logout  /api/register
    app.register_blueprint(pages_bp)   # /  /reports  /analytics  /predictions  /compare
    app.register_blueprint(api_bp)     # /api/*  /predict

    # Jinja2 compatibility shim
    def _compat_url_for(endpoint, **values):
        """Resolve bare endpoint names used in the original frontend templates."""
        resolved = _ENDPOINT_ALIASES.get(endpoint, endpoint)
        return _flask_url_for(resolved, **values)

    app.jinja_env.globals["url_for"] = _compat_url_for

    with app.app_context():
        init_db()
        print("Database initialised (data/cleverfund.db)")

    return app


app = create_app()

# ---------------------------------------------------------------------------
# Jinja2 compatibility shim
#
# The original templates call url_for() with bare function names (no blueprint
# prefix).  After blueprint registration, endpoints are namespaced e.g.
# 'auth.login', 'pages.dashboard'.  We patch the Jinja2 global so every
# bare name still resolves correctly — zero frontend changes needed.
# ---------------------------------------------------------------------------
_ENDPOINT_ALIASES = {
    "login":            "auth.login",
    "logout":           "auth.logout",
    "dashboard":        "pages.dashboard",
    "reports_page":     "pages.reports_page",
    "analytics_page":   "pages.analytics_page",
    "predictions_page": "pages.predictions_page",
    "compare_page":     "pages.compare_page",
    # 'static' is a built-in Flask endpoint — keep it as-is
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] CleverFund backend starting on http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
