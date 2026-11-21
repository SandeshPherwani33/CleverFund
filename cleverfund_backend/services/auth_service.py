"""
services/auth_service.py
------------------------
Handles user registration, login verification, and password hashing.

We use werkzeug's built-in password hashing (already a Flask dependency),
so no extra pip install is needed.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from ..models.database import get_db
from pymongo.errors import DuplicateKeyError
from datetime import datetime

def register_user(email: str, password: str) -> dict:
    """
    Create a new user account.

    Returns
    -------
    {"ok": True, "email": email}          on success
    {"ok": False, "error": "...message"}  on failure (e.g. duplicate email)
    """
    if not email or not password:
        return {"ok": False, "error": "Email and password are required."}

    if len(password) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters."}

    password_hash = generate_password_hash(password)
    email = email.strip().lower()

    try:
        db = get_db()
        db.users.insert_one({
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        })
        return {"ok": True, "email": email}
    except DuplicateKeyError:
        return {"ok": False, "error": "An account with this email already exists."}
    except Exception as exc:
        return {"ok": False, "error": f"Registration failed: {exc}"}


def verify_user(email: str, password: str) -> dict:
    """
    Check email + password against the database.

    Returns
    -------
    {"ok": True, "email": email}          on success
    {"ok": False, "error": "...message"}  on failure
    """
    if not email or not password:
        return {"ok": False, "error": "Please enter both email and password."}

    email = email.strip().lower()
    db = get_db()
    user = db.users.find_one({"email": email})

    if user is None:
        # Don't reveal whether the email exists (security best-practice)
        return {"ok": False, "error": "Invalid email or password."}

    if not check_password_hash(user["password_hash"], password):
        return {"ok": False, "error": "Invalid email or password."}

    return {"ok": True, "email": user["email"]}


def user_exists(email: str) -> bool:
    """Return True if the email is already registered."""
    email = email.strip().lower()
    db = get_db()
    user = db.users.find_one({"email": email})
    return user is not None
