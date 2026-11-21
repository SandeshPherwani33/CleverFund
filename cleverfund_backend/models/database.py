"""
models/database.py
------------------
Defines the MongoDB database connection and initialization.

Collections
  users       : registered accounts (email + hashed password)
  predictions : every prediction a user has ever run
"""

import os
from pymongo import MongoClient

# MongoDB connection settings
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "cleverfund")

_client = None

def get_db():
    """Return the MongoDB database object."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client[MONGO_DB_NAME]

def init_db():
    """Create collections and indexes if they don't exist yet. Called once at app startup."""
    db = get_db()
    
    # -- users --
    # Create unique index on email
    db.users.create_index("email", unique=True)
    
    # -- predictions --
    # Create index for fast per-user lookups
    db.predictions.create_index([("user_email", 1), ("created_at", -1)])
