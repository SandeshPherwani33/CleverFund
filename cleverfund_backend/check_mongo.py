"""Quick script to check MongoDB connection and data."""
from pymongo import MongoClient

try:
    c = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
    # Force a connection test
    c.admin.command("ping")
    print("MongoDB connection: OK")

    db = c["cleverfund"]
    print(f"Database: cleverfund")
    print(f"Collections: {db.list_collection_names()}")
    print(f"Users count: {db.users.count_documents({})}")
    print(f"Predictions count: {db.predictions.count_documents({})}")

    print("\nRegistered users:")
    for u in db.users.find({}, {"email": 1, "_id": 0}):
        print(f"  - {u['email']}")

    print("\nRecent predictions:")
    for p in db.predictions.find({}, {"user_email": 1, "industry": 1, "result": 1, "probability": 1, "_id": 0}).limit(5):
        print(f"  - {p}")

except Exception as e:
    print(f"MongoDB connection FAILED: {e}")
    print("\nMake sure MongoDB is running on localhost:27017")
    print("Start it with: mongod  (or via MongoDB Compass / Windows Services)")
