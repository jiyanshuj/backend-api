"""
Database module for MongoDB operations
Collections: tourism, restaurants, hotels
"""

from pymongo import MongoClient, GEOSPHERE
from pymongo.errors import DuplicateKeyError
from typing import List, Dict, Optional
import os
from datetime import datetime
from bson import ObjectId

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "wander_ease"

client = None
db = None

def init_db():
    """Initialize MongoDB connection and create indexes"""
    global client, db
    
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # Create geospatial indexes for location-based queries
    db.tourism.create_index([("location", GEOSPHERE)])
    db.restaurants.create_index([("location", GEOSPHERE)])
    db.hotels.create_index([("location", GEOSPHERE)])
    
    # Create unique indexes on place_id/restaurant_id/hotel_id
    db.tourism.create_index("place_id", unique=True)
    db.restaurants.create_index("restaurant_id", unique=True)
    db.hotels.create_index("hotel_id", unique=True)
    
    # Index on location name for text search
    db.tourism.create_index("location_query")
    db.restaurants.create_index("location_query")
    db.hotels.create_index("location_query")
    
    print("Database initialized successfully")

def close_db():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("Database connection closed")

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
    normalized_location = normalize_location_query(location)
    
    places = list(db.tourism.find(
        {"location_query": normalized_location}
    ).limit(limit))
    
    # Serialize documents
    return [serialize_doc(place) for place in places]

def save_tourism_to_db(places: List[Dict], location: str):
    """Save tourism places to MongoDB"""
    normalized_location = normalize_location_query(location)
    
    for place in places:
        place["location_query"] = normalized_location
        place["created_at"] = datetime.utcnow()
        place["updated_at"] = datetime.utcnow()
        
        try:
            db.tourism.insert_one(place.copy())
        except DuplicateKeyError:
            # Update existing record
            place_copy = place.copy()
            place_copy.pop('_id', None)
            db.tourism.update_one(
                {"place_id": place["place_id"]},
                {"$set": {**place_copy, "updated_at": datetime.utcnow()}}
            )

def search_tourism_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search tourism places within radius (in kilometers)"""
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

# Restaurant Operations
def get_restaurants_from_db(location: str, limit: int = 20) -> List[Dict]:
    """Get restaurants from MongoDB by location"""
    normalized_location = normalize_location_query(location)
    
    restaurants = list(db.restaurants.find(
        {"location_query": normalized_location}
    ).limit(limit))
    
    return [serialize_doc(restaurant) for restaurant in restaurants]

def save_restaurants_to_db(restaurants: List[Dict], location: str):
    """Save restaurants to MongoDB"""
    normalized_location = normalize_location_query(location)
    
    for restaurant in restaurants:
        restaurant["location_query"] = normalized_location
        restaurant["created_at"] = datetime.utcnow()
        restaurant["updated_at"] = datetime.utcnow()
        
        try:
            db.restaurants.insert_one(restaurant.copy())
        except DuplicateKeyError:
            restaurant_copy = restaurant.copy()
            restaurant_copy.pop('_id', None)
            db.restaurants.update_one(
                {"restaurant_id": restaurant["restaurant_id"]},
                {"$set": {**restaurant_copy, "updated_at": datetime.utcnow()}}
            )

def search_restaurants_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search restaurants within radius"""
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

# Hotel Operations
def get_hotels_from_db(location: str, limit: int = 20) -> List[Dict]:
    """Get hotels from MongoDB by location"""
    normalized_location = normalize_location_query(location)
    
    hotels = list(db.hotels.find(
        {"location_query": normalized_location}
    ).limit(limit))
    
    return [serialize_doc(hotel) for hotel in hotels]

def save_hotels_to_db(hotels: List[Dict], location: str):
    """Save hotels to MongoDB"""
    normalized_location = normalize_location_query(location)
    
    for hotel in hotels:
        hotel["location_query"] = normalized_location
        hotel["created_at"] = datetime.utcnow()
        hotel["updated_at"] = datetime.utcnow()
        
        try:
            db.hotels.insert_one(hotel.copy())
        except DuplicateKeyError:
            hotel_copy = hotel.copy()
            hotel_copy.pop('_id', None)
            db.hotels.update_one(
                {"hotel_id": hotel["hotel_id"]},
                {"$set": {**hotel_copy, "updated_at": datetime.utcnow()}}
            )

def search_hotels_nearby(lat: float, lon: float, radius_km: float = 5, limit: int = 20) -> List[Dict]:
    """Search hotels within radius"""
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