"""
Database module for MongoDB operations
Collections: tourism, restaurants, hotels, users, activities, connections
"""

from pymongo import MongoClient, GEOSPHERE
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from typing import List, Dict, Optional
import os
from datetime import datetime
from bson import ObjectId

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jiyan:Jiyu5678@cluster0.h2c3adp.mongodb.net/")
DB_NAME = "wander_ease"

client = None
db = None

def init_db():
    """Initialize MongoDB Atlas connection and create indexes"""
    global client, db
    
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            retryWrites=True,
            w='majority'
        )
        client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas!")
        
        db = client[DB_NAME]
        print(f"✅ Using database: {DB_NAME}")
        
        existing_collections = db.list_collection_names()
        print(f"📁 Existing collections: {existing_collections}")
        
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB Atlas: {e}")
        raise
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise
    
    # ===== GEOSPATIAL INDEXES =====
    print("\n🔧 Setting up geospatial indexes...")
    for coll in ['tourism', 'restaurants', 'hotels']:
        try:
            db[coll].create_index([("location", GEOSPHERE)])
            print(f"✅ {coll.capitalize()} geospatial index created")
        except Exception as e:
            print(f"⚠️ {coll} geospatial index: {e}")
    
    # ===== UNIQUE ID INDEXES =====
    print("\n🔧 Setting up unique ID indexes...")
    try:
        db.tourism.create_index("place_id", unique=True)
        db.restaurants.create_index("restaurant_id", unique=True)
        db.hotels.create_index("hotel_id", unique=True)
        print("✅ Unique ID indexes created")
    except Exception as e:
        print(f"⚠️ Unique ID indexes: {e}")
    
    # ===== LOCATION QUERY INDEXES =====
    print("\n🔧 Setting up location query indexes...")
    try:
        db.tourism.create_index("location_query")
        db.restaurants.create_index("location_query")
        db.hotels.create_index("location_query")
        print("✅ Location query indexes created")
    except Exception as e:
        print(f"⚠️ Location query indexes: {e}")
    
    # ===== USERS COLLECTION =====
    print("\n👤 Setting up users collection...")
    try:
        db.users.delete_many({"clerk_id": None})
        db.users.delete_many({"clerk_id": ""})
    except Exception as e:
        print(f"⚠️ Error cleaning invalid users: {e}")
    
    try:
        db.users.create_index("clerk_id", unique=True, sparse=True)
        db.users.create_index("email", unique=True, sparse=True)
        db.users.create_index("liked.tourism.item_id")
        db.users.create_index("liked.restaurants.item_id")
        db.users.create_index("liked.hotels.item_id")
        print("✅ Users indexes created")
    except Exception as e:
        print(f"⚠️ Users indexes: {e}")
    
    # ===== ACTIVITIES COLLECTION =====
    print("\n🎯 Setting up activities collection...")
    try:
        db.activities.create_index([("location", GEOSPHERE)])
        db.activities.create_index("clerk_id")
        db.activities.create_index("activity_type")
        db.activities.create_index("status")
        db.activities.create_index("scheduled_time")
        db.activities.create_index("expires_at")
        db.activities.create_index([
            ("activity_type", 1), ("status", 1), 
            ("is_public", 1), ("scheduled_time", 1)
        ])
        print("✅ Activities indexes created")
    except Exception as e:
        print(f"⚠️ Activities indexes: {e}")
    
    # ===== CONNECTIONS COLLECTION =====
    print("\n💬 Setting up connections collection...")
    try:
        db.connections.create_index("from_clerk_id")
        db.connections.create_index("to_clerk_id")
        db.connections.create_index("activity_id")
        db.connections.create_index("status")
        db.connections.create_index([
            ("from_clerk_id", 1), ("to_clerk_id", 1), ("activity_id", 1)
        ], unique=True)
        print("✅ Connections indexes created")
    except Exception as e:
        print(f"⚠️ Connections indexes: {e}")
    
    # ===== COLLECTION STATS =====
    print("\n📊 Collection Statistics:")
    try:
        for coll in ['tourism', 'restaurants', 'hotels', 'users', 'activities', 'connections']:
            count = db[coll].count_documents({})
            print(f"   • {coll}: {count} documents")
    except Exception as e:
        print(f"⚠️ Error getting stats: {e}")
    
    print("\n✅ Database initialization complete!")
    print("="*60)

def close_db():
    global client
    if client:
        client.close()
        print("✅ Database connection closed")

def normalize_location_query(location: str) -> str:
    return location.lower().strip()

def serialize_doc(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                result['id'] = str(value)
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = [serialize_doc(i) if isinstance(i, dict) else i for i in value]
            else:
                result[key] = value
        return result
    return doc

# ===== TOURISM OPERATIONS =====
def get_tourism_from_db(location: str, limit: int = 20) -> List[Dict]:
    try:
        places = list(db.tourism.find({"location_query": normalize_location_query(location)}).limit(limit))
        print(f"📍 Found {len(places)} tourism places for '{location}'")
        return [serialize_doc(p) for p in places]
    except Exception as e:
        print(f"❌ Error fetching tourism: {e}")
        return []

def save_tourism_to_db(places: List[Dict], location: str):
    try:
        norm_loc = normalize_location_query(location)
        for place in places:
            place["location_query"] = norm_loc
            place["created_at"] = datetime.utcnow()
            place["updated_at"] = datetime.utcnow()
            try:
                db.tourism.insert_one(place.copy())
            except DuplicateKeyError:
                place.pop('_id', None)
                db.tourism.update_one({"place_id": place["place_id"]}, {"$set": place})
    except Exception as e:
        print(f"❌ Error saving tourism: {e}")

def search_tourism_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    try:
        places = list(db.tourism.find({
            "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [lon, lat]}, "$maxDistance": radius_km * 1000}}
        }).limit(limit))
        return [serialize_doc(p) for p in places]
    except Exception as e:
        print(f"❌ Error in nearby tourism search: {e}")
        return []

# ===== RESTAURANT OPERATIONS =====
def get_restaurants_from_db(location: str, limit: int = 20) -> List[Dict]:
    try:
        restaurants = list(db.restaurants.find({"location_query": normalize_location_query(location)}).limit(limit))
        print(f"🍽️ Found {len(restaurants)} restaurants for '{location}'")
        return [serialize_doc(r) for r in restaurants]
    except Exception as e:
        print(f"❌ Error fetching restaurants: {e}")
        return []

def save_restaurants_to_db(restaurants: List[Dict], location: str):
    try:
        norm_loc = normalize_location_query(location)
        for rest in restaurants:
            rest["location_query"] = norm_loc
            rest["created_at"] = datetime.utcnow()
            rest["updated_at"] = datetime.utcnow()
            try:
                db.restaurants.insert_one(rest.copy())
            except DuplicateKeyError:
                rest.pop('_id', None)
                db.restaurants.update_one({"restaurant_id": rest["restaurant_id"]}, {"$set": rest})
    except Exception as e:
        print(f"❌ Error saving restaurants: {e}")

def search_restaurants_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    try:
        restaurants = list(db.restaurants.find({
            "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [lon, lat]}, "$maxDistance": radius_km * 1000}}
        }).limit(limit))
        return [serialize_doc(r) for r in restaurants]
    except Exception as e:
        print(f"❌ Error in nearby restaurants search: {e}")
        return []

# ===== HOTEL OPERATIONS =====
def get_hotels_from_db(location: str, limit: int = 20) -> List[Dict]:
    try:
        hotels = list(db.hotels.find({"location_query": normalize_location_query(location)}).limit(limit))
        print(f"🏨 Found {len(hotels)} hotels for '{location}'")
        return [serialize_doc(h) for h in hotels]
    except Exception as e:
        print(f"❌ Error fetching hotels: {e}")
        return []

def save_hotels_to_db(hotels: List[Dict], location: str):
    try:
        norm_loc = normalize_location_query(location)
        for hotel in hotels:
            hotel["location_query"] = norm_loc
            hotel["created_at"] = datetime.utcnow()
            hotel["updated_at"] = datetime.utcnow()
            try:
                db.hotels.insert_one(hotel.copy())
            except DuplicateKeyError:
                hotel.pop('_id', None)
                db.hotels.update_one({"hotel_id": hotel["hotel_id"]}, {"$set": hotel})
    except Exception as e:
        print(f"❌ Error saving hotels: {e}")

def search_hotels_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    try:
        hotels = list(db.hotels.find({
            "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [lon, lat]}, "$maxDistance": radius_km * 1000}}
        }).limit(limit))
        return [serialize_doc(h) for h in hotels]
    except Exception as e:
        print(f"❌ Error in nearby hotels search: {e}")
        return []