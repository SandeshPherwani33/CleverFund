"""
routes/auth.py
--------------
Handles login, logout, and registration.

The original login.html uses a simple form POST — we keep that intact.
We additionally expose a /api/register JSON endpoint for programmatic use.
"""

from functools import wraps
from flask import (
    Blueprint, redirect, render_template, request,
    session, url_for, jsonify,
)
from ..services.auth_service import verify_user, register_user

auth_bp = Blueprint("auth", __name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Decorator helpers (also used by other blueprints)
# ─────────────────────────────────────────────────────────────────────────────

def login_required_page(view):
    """Redirect unauthenticated requests to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            nxt = request.path
            if nxt and nxt != "/login":
                return redirect(url_for("auth.login", next=nxt))
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def login_required_api(view):
    """Return 401 JSON for unauthenticated API calls."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized", "login": url_for("auth.login")}), 401
        return view(*args, **kwargs)
    return wrapped


# ─────────────────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    GET  → render login form
    POST → verify credentials; on success set session and redirect
    """
    # Already logged in? Go to dashboard
    if session.get("user"):
        return redirect(url_for("pages.dashboard"))

    error = None
    if request.method == "POST":
        email    = (request.form.get("email")    or "").strip()
        password = (request.form.get("password") or "").strip()

        result = verify_user(email, password)
        if result["ok"]:
            session["user"] = result["email"]
            session.permanent = True
            nxt = request.args.get("next") or url_for("pages.dashboard")
            # Safety check — only allow relative redirects
            if not nxt.startswith("/"):
                nxt = url_for("pages.dashboard")
            return redirect(nxt)

        error = result["error"]

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    """
    JSON endpoint to create a new account.

    Body  : { "email": "...", "password": "..." }
    200   : { "ok": true, "email": "..." }
    400   : { "ok": false, "error": "..." }
    """
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip()
    password = (data.get("password") or "").strip()

    result = register_user(email, password)
    status = 200 if result["ok"] else 400
    return jsonify(result), status
