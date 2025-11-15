"""
Database module for MongoDB operations
Collections: tourism, restaurants, hotels, users
Fixed for MongoDB Atlas Cloud Connection
"""

from pymongo import MongoClient, GEOSPHERE
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from typing import List, Dict, Optional
import os
from datetime import datetime
from bson import ObjectId

# MongoDB Atlas connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jiyan:Jiyu5678@cluster0.h2c3adp.mongodb.net/")
DB_NAME = "wander_ease"

client = None
db = None

def init_db():
    """Initialize MongoDB Atlas connection and create indexes"""
    global client, db
    
    try:
        # Connect to MongoDB Atlas with proper configuration
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            retryWrites=True,
            w='majority'
        )
        
        # Test the connection
        client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas!")
        
        db = client[DB_NAME]
        print(f"✅ Using database: {DB_NAME}")
        
        # List existing collections
        existing_collections = db.list_collection_names()
        print(f"📁 Existing collections: {existing_collections}")
        
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB Atlas: {e}")
        raise
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise
    
    # Create geospatial indexes for location-based queries
    print("\n🔧 Setting up geospatial indexes...")
    try:
        db.tourism.create_index([("location", GEOSPHERE)])
        print("✅ Tourism geospatial index created")
    except Exception as e:
        print(f"⚠️ Tourism geospatial index: {e}")
    
    try:
        db.restaurants.create_index([("location", GEOSPHERE)])
        print("✅ Restaurants geospatial index created")
    except Exception as e:
        print(f"⚠️ Restaurants geospatial index: {e}")
    
    try:
        db.hotels.create_index([("location", GEOSPHERE)])
        print("✅ Hotels geospatial index created")
    except Exception as e:
        print(f"⚠️ Hotels geospatial index: {e}")
    
    # Create unique indexes on place_id/restaurant_id/hotel_id
    print("\n🔧 Setting up unique ID indexes...")
    try:
        db.tourism.create_index("place_id", unique=True)
        print("✅ Tourism place_id index created")
    except Exception as e:
        print(f"⚠️ Tourism place_id index: {e}")
    
    try:
        db.restaurants.create_index("restaurant_id", unique=True)
        print("✅ Restaurants restaurant_id index created")
    except Exception as e:
        print(f"⚠️ Restaurants restaurant_id index: {e}")
    
    try:
        db.hotels.create_index("hotel_id", unique=True)
        print("✅ Hotels hotel_id index created")
    except Exception as e:
        print(f"⚠️ Hotels hotel_id index: {e}")
    
    # Index on location_query for text search
    print("\n🔧 Setting up location query indexes...")
    try:
        db.tourism.create_index("location_query")
        db.restaurants.create_index("location_query")
        db.hotels.create_index("location_query")
        print("✅ Location query indexes created")
    except Exception as e:
        print(f"⚠️ Location query indexes: {e}")
    
    # ===== USERS COLLECTION SETUP =====
    print("\n👤 Setting up users collection...")
    
    # Clean up invalid users
    try:
        null_clerk_count = db.users.count_documents({"clerk_id": None})
        if null_clerk_count > 0:
            print(f"⚠️ Found {null_clerk_count} users with null clerk_id. Cleaning up...")
            result = db.users.delete_many({"clerk_id": None})
            print(f"✅ Removed {result.deleted_count} invalid user documents")
        
        empty_clerk_count = db.users.count_documents({"clerk_id": ""})
        if empty_clerk_count > 0:
            print(f"⚠️ Found {empty_clerk_count} users with empty clerk_id. Cleaning up...")
            result = db.users.delete_many({"clerk_id": ""})
            print(f"✅ Removed {result.deleted_count} invalid user documents")
    except Exception as e:
        print(f"⚠️ Error checking for invalid users: {e}")
    
    # Create indexes for users collection
    try:
        db.users.create_index("clerk_id", unique=True, sparse=True)
        print("✅ Users clerk_id index created")
    except Exception as e:
        print(f"⚠️ Users clerk_id index: {e}")
    
    try:
        db.users.create_index("email", unique=True, sparse=True)
        print("✅ Users email index created")
    except Exception as e:
        print(f"⚠️ Users email index: {e}")
    
    # Index on liked items for faster queries
    try:
        db.users.create_index("liked.tourism.item_id")
        db.users.create_index("liked.restaurants.item_id")
        db.users.create_index("liked.hotels.item_id")
        print("✅ Users liked items indexes created")
    except Exception as e:
        print(f"⚠️ Users liked items indexes: {e}")
    
    # Display current collection stats
    print("\n📊 Collection Statistics:")
    try:
        for collection_name in ['tourism', 'restaurants', 'hotels', 'users']:
            count = db[collection_name].count_documents({})
            print(f"   • {collection_name}: {count} documents")
    except Exception as e:
        print(f"⚠️ Error getting collection stats: {e}")
    
    print("\n✅ Database initialization complete!")
    print("="*60)

def close_db():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("✅ Database connection closed")

def normalize_location_query(location: str) -> str:
    """Normalize location string for consistent querying"""
    return location.lower().strip()

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                continue  # Skip MongoDB _id field
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = [serialize_doc(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result
    return doc

# Tourism Places Operations
def get_tourism_from_db(location: str, limit: int = 20) -> List[Dict]:
    """Get tourism places from MongoDB by location"""
    try:
        normalized_location = normalize_location_query(location)
        
        places = list(db.tourism.find(
            {"location_query": normalized_location}
        ).limit(limit))
        
        print(f"📍 Found {len(places)} tourism places for '{location}' in database")
        return [serialize_doc(place) for place in places]
    except Exception as e:
        print(f"❌ Error fetching tourism from DB: {e}")
        return []

def save_tourism_to_db(places: List[Dict], location: str):
    """Save tourism places to MongoDB Atlas"""
    try:
        normalized_location = normalize_location_query(location)
        saved_count = 0
        updated_count = 0
        
        for place in places:
            place["location_query"] = normalized_location
            place["created_at"] = datetime.utcnow()
            place["updated_at"] = datetime.utcnow()
            
            try:
                result = db.tourism.insert_one(place.copy())
                saved_count += 1
                print(f"✅ Saved tourism place: {place.get('name', 'Unknown')} (ID: {result.inserted_id})")
            except DuplicateKeyError:
                # Update existing record
                place_copy = place.copy()
                place_copy.pop('_id', None)
                result = db.tourism.update_one(
                    {"place_id": place["place_id"]},
                    {"$set": {**place_copy, "updated_at": datetime.utcnow()}}
                )
                updated_count += 1
                print(f"🔄 Updated tourism place: {place.get('name', 'Unknown')}")
            except Exception as e:
                print(f"❌ Error saving tourism place {place.get('name', 'Unknown')}: {e}")
        
        print(f"💾 Tourism saved: {saved_count} new, {updated_count} updated for '{location}'")
    except Exception as e:
        print(f"❌ Error in save_tourism_to_db: {e}")

def search_tourism_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search tourism places within radius (in kilometers)"""
    try:
        places = list(db.tourism.find(
            {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "$maxDistance": radius_km * 1000  # Convert to meters
                    }
                }
            }
        ).limit(limit))
        
        return [serialize_doc(place) for place in places]
    except Exception as e:
        print(f"❌ Error in nearby tourism search: {e}")
        return []

# Restaurant Operations
def get_restaurants_from_db(location: str, limit: int = 20) -> List[Dict]:
    """Get restaurants from MongoDB by location"""
    try:
        normalized_location = normalize_location_query(location)
        
        restaurants = list(db.restaurants.find(
            {"location_query": normalized_location}
        ).limit(limit))
        
        print(f"🍽️ Found {len(restaurants)} restaurants for '{location}' in database")
        return [serialize_doc(restaurant) for restaurant in restaurants]
    except Exception as e:
        print(f"❌ Error fetching restaurants from DB: {e}")
        return []

def save_restaurants_to_db(restaurants: List[Dict], location: str):
    """Save restaurants to MongoDB Atlas"""
    try:
        normalized_location = normalize_location_query(location)
        saved_count = 0
        updated_count = 0
        
        for restaurant in restaurants:
            restaurant["location_query"] = normalized_location
            restaurant["created_at"] = datetime.utcnow()
            restaurant["updated_at"] = datetime.utcnow()
            
            try:
                result = db.restaurants.insert_one(restaurant.copy())
                saved_count += 1
                print(f"✅ Saved restaurant: {restaurant.get('name', 'Unknown')} (ID: {result.inserted_id})")
            except DuplicateKeyError:
                restaurant_copy = restaurant.copy()
                restaurant_copy.pop('_id', None)
                result = db.restaurants.update_one(
                    {"restaurant_id": restaurant["restaurant_id"]},
                    {"$set": {**restaurant_copy, "updated_at": datetime.utcnow()}}
                )
                updated_count += 1
                print(f"🔄 Updated restaurant: {restaurant.get('name', 'Unknown')}")
            except Exception as e:
                print(f"❌ Error saving restaurant {restaurant.get('name', 'Unknown')}: {e}")
        
        print(f"💾 Restaurants saved: {saved_count} new, {updated_count} updated for '{location}'")
    except Exception as e:
        print(f"❌ Error in save_restaurants_to_db: {e}")

def search_restaurants_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search restaurants within radius"""
    try:
        restaurants = list(db.restaurants.find(
            {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "$maxDistance": radius_km * 1000
                    }
                }
            }
        ).limit(limit))
        
        return [serialize_doc(restaurant) for restaurant in restaurants]
    except Exception as e:
        print(f"❌ Error in nearby restaurants search: {e}")
        return []

# Hotel Operations
def get_hotels_from_db(location: str, limit: int = 20) -> List[Dict]:
    """Get hotels from MongoDB by location"""
    try:
        normalized_location = normalize_location_query(location)
        
        hotels = list(db.hotels.find(
            {"location_query": normalized_location}
        ).limit(limit))
        
        print(f"🏨 Found {len(hotels)} hotels for '{location}' in database")
        return [serialize_doc(hotel) for hotel in hotels]
    except Exception as e:
        print(f"❌ Error fetching hotels from DB: {e}")
        return []

def save_hotels_to_db(hotels: List[Dict], location: str):
    """Save hotels to MongoDB Atlas"""
    try:
        normalized_location = normalize_location_query(location)
        saved_count = 0
        updated_count = 0
        
        for hotel in hotels:
            hotel["location_query"] = normalized_location
            hotel["created_at"] = datetime.utcnow()
            hotel["updated_at"] = datetime.utcnow()
            
            try:
                result = db.hotels.insert_one(hotel.copy())
                saved_count += 1
                print(f"✅ Saved hotel: {hotel.get('name', 'Unknown')} (ID: {result.inserted_id})")
            except DuplicateKeyError:
                hotel_copy = hotel.copy()
                hotel_copy.pop('_id', None)
                result = db.hotels.update_one(
                    {"hotel_id": hotel["hotel_id"]},
                    {"$set": {**hotel_copy, "updated_at": datetime.utcnow()}}
                )
                updated_count += 1
                print(f"🔄 Updated hotel: {hotel.get('name', 'Unknown')}")
            except Exception as e:
                print(f"❌ Error saving hotel {hotel.get('name', 'Unknown')}: {e}")
        
        print(f"💾 Hotels saved: {saved_count} new, {updated_count} updated for '{location}'")
    except Exception as e:
        print(f"❌ Error in save_hotels_to_db: {e}")

def search_hotels_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search hotels within radius"""
    try:
        hotels = list(db.hotels.find(
            {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "$maxDistance": radius_km * 1000
                    }
                }
            }
        ).limit(limit))
        
        return [serialize_doc(hotel) for hotel in hotels]
    except Exception as e:
        print(f"❌ Error in nearby hotels search: {e}")
        return []