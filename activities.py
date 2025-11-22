"""
Activity Matching Module - Social Activity Discovery
Allows users to post activities and find nearby people with similar plans
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from enum import Enum

# Activity Categories
ACTIVITY_TYPES = {
    "cafe": {"icon": "☕", "label": "Visiting a Café", "color": "#8D6E63"},
    "garden": {"icon": "🌳", "label": "Walk in Garden/Park", "color": "#4CAF50"},
    "restaurant": {"icon": "🍽️", "label": "Going to Restaurant", "color": "#FF5722"},
    "mall": {"icon": "🛍️", "label": "Shopping at Mall", "color": "#E91E63"},
    "library": {"icon": "📚", "label": "Studying at Library", "color": "#3F51B5"},
    "movie": {"icon": "🎬", "label": "Watching a Movie", "color": "#9C27B0"},
    "gym": {"icon": "💪", "label": "Going to Gym", "color": "#F44336"},
    "event": {"icon": "🎉", "label": "Attending an Event", "color": "#FF9800"},
    "coworking": {"icon": "💻", "label": "Co-working/Study Meetup", "color": "#00BCD4"},
    "other": {"icon": "📍", "label": "Other Activity", "color": "#607D8B"}
}

MOOD_TYPES = ["chill", "social", "study", "adventure", "networking", "casual"]

def get_db():
    """Get database instance from db module"""
    from db import db
    return db

def create_activity_indexes():
    """Create indexes for activities collection"""
    db = get_db()
    try:
        # Geospatial index for location-based queries
        db.activities.create_index([("location", "2dsphere")])
        print("✅ Activities geospatial index created")
        
        # Index for user queries
        db.activities.create_index("clerk_id")
        db.activities.create_index("activity_type")
        db.activities.create_index("status")
        db.activities.create_index("scheduled_time")
        
        # Compound index for matching queries
        db.activities.create_index([
            ("activity_type", 1),
            ("status", 1),
            ("scheduled_time", 1)
        ])
        print("✅ Activities indexes created")
    except Exception as e:
        print(f"⚠️ Activities index error: {e}")

def serialize_activity(doc) -> Optional[Dict]:
    """Convert activity document to JSON-serializable dict"""
    if not doc:
        return None
    result = {}
    for key, value in doc.items():
        if key == '_id':
            result['activity_id'] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = value
        elif isinstance(value, list):
            result[key] = value
        else:
            result[key] = value
    return result

# ============= ACTIVITY CRUD OPERATIONS =============

def create_activity(
    clerk_id: str,
    activity_type: str,
    lat: float,
    lon: float,
    place_name: Optional[str] = None,
    scheduled_time: Optional[datetime] = None,
    mood: Optional[str] = None,
    description: Optional[str] = None,
    max_participants: int = 5,
    is_public: bool = True
) -> Dict:
    """
    Create a new activity post
    """
    db = get_db()
    
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"Invalid activity type. Must be one of: {list(ACTIVITY_TYPES.keys())}")
    
    if mood and mood not in MOOD_TYPES:
        raise ValueError(f"Invalid mood. Must be one of: {MOOD_TYPES}")
    
    # Default scheduled time to now if not provided
    if not scheduled_time:
        scheduled_time = datetime.utcnow()
    
    activity = {
        "clerk_id": clerk_id,
        "activity_type": activity_type,
        "activity_info": ACTIVITY_TYPES[activity_type],
        "location": {
            "type": "Point",
            "coordinates": [lon, lat]  # GeoJSON format: [lon, lat]
        },
        "lat": lat,
        "lon": lon,
        "place_name": place_name,
        "scheduled_time": scheduled_time,
        "mood": mood,
        "description": description,
        "max_participants": max_participants,
        "participants": [clerk_id],  # Creator is first participant
        "participant_count": 1,
        "is_public": is_public,
        "status": "active",  # active, completed, cancelled
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "expires_at": scheduled_time + timedelta(hours=4)  # Auto-expire after 4 hours
    }
    
    result = db.activities.insert_one(activity)
    activity["activity_id"] = str(result.inserted_id)
    
    print(f"✅ Created activity: {activity_type} by {clerk_id}")
    return serialize_activity(activity)

def get_activity_by_id(activity_id: str) -> Optional[Dict]:
    """Get single activity by ID"""
    db = get_db()
    try:
        activity = db.activities.find_one({"_id": ObjectId(activity_id)})
        return serialize_activity(activity)
    except Exception as e:
        print(f"❌ Error getting activity: {e}")
        return None

def get_user_activities(clerk_id: str, status: Optional[str] = None) -> List[Dict]:
    """Get all activities created by a user"""
    db = get_db()
    query = {"clerk_id": clerk_id}
    if status:
        query["status"] = status
    
    activities = list(db.activities.find(query).sort("created_at", -1))
    return [serialize_activity(a) for a in activities]

def update_activity(activity_id: str, clerk_id: str, **updates) -> Optional[Dict]:
    """Update an activity (only by creator)"""
    db = get_db()
    
    # Verify ownership
    activity = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not activity or activity["clerk_id"] != clerk_id:
        return None
    
    allowed_fields = ["place_name", "scheduled_time", "mood", "description", 
                      "max_participants", "is_public", "status"]
    
    update_data = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    db.activities.update_one(
        {"_id": ObjectId(activity_id)},
        {"$set": update_data}
    )
    
    return get_activity_by_id(activity_id)

def cancel_activity(activity_id: str, clerk_id: str) -> bool:
    """Cancel an activity"""
    db = get_db()
    result = db.activities.update_one(
        {"_id": ObjectId(activity_id), "clerk_id": clerk_id},
        {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}}
    )
    return result.modified_count > 0

# ============= MATCHING & DISCOVERY =============

def find_nearby_activities(
    lat: float,
    lon: float,
    activity_type: Optional[str] = None,
    radius_km: float = 5.0,
    mood: Optional[str] = None,
    exclude_clerk_id: Optional[str] = None,
    limit: int = 20
) -> List[Dict]:
    """
    Find nearby activities matching criteria
    """
    db = get_db()
    
    # Base query - only active, non-expired activities
    query = {
        "status": "active",
        "is_public": True,
        "expires_at": {"$gt": datetime.utcnow()},
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
    
    # Optional filters
    if activity_type:
        query["activity_type"] = activity_type
    
    if mood:
        query["mood"] = mood
    
    if exclude_clerk_id:
        query["clerk_id"] = {"$ne": exclude_clerk_id}
    
    try:
        activities = list(db.activities.find(query).limit(limit))
        
        # Calculate distance for each activity
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Earth's radius in km
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        result = []
        for activity in activities:
            serialized = serialize_activity(activity)
            # Add distance
            act_lat = activity.get("lat", 0)
            act_lon = activity.get("lon", 0)
            serialized["distance_km"] = round(haversine(lat, lon, act_lat, act_lon), 2)
            result.append(serialized)
        
        print(f"📍 Found {len(result)} nearby activities")
        return result
        
    except Exception as e:
        print(f"❌ Error finding nearby activities: {e}")
        return []

def find_matching_activities(
    clerk_id: str,
    lat: float,
    lon: float,
    activity_type: str,
    radius_km: float = 3.0,
    time_window_hours: int = 2
) -> List[Dict]:
    """
    Find activities that match user's planned activity
    Best for showing "people doing the same thing nearby"
    """
    db = get_db()
    
    now = datetime.utcnow()
    time_start = now - timedelta(hours=1)
    time_end = now + timedelta(hours=time_window_hours)
    
    query = {
        "activity_type": activity_type,
        "status": "active",
        "is_public": True,
        "clerk_id": {"$ne": clerk_id},
        "scheduled_time": {"$gte": time_start, "$lte": time_end},
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "$maxDistance": radius_km * 1000
            }
        },
        # Ensure not at max capacity
        "$expr": {"$lt": ["$participant_count", "$max_participants"]}
    }
    
    try:
        activities = list(db.activities.find(query).limit(10))
        return [serialize_activity(a) for a in activities]
    except Exception as e:
        print(f"❌ Error finding matching activities: {e}")
        return []

# ============= PARTICIPATION =============

def join_activity(activity_id: str, clerk_id: str) -> Dict:
    """Request to join an activity"""
    db = get_db()
    
    activity = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not activity:
        raise ValueError("Activity not found")
    
    if activity["status"] != "active":
        raise ValueError("Activity is no longer active")
    
    if clerk_id in activity.get("participants", []):
        raise ValueError("Already participating in this activity")
    
    if activity["participant_count"] >= activity["max_participants"]:
        raise ValueError("Activity is at maximum capacity")
    
    # Add participant
    db.activities.update_one(
        {"_id": ObjectId(activity_id)},
        {
            "$push": {"participants": clerk_id},
            "$inc": {"participant_count": 1},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Create connection request
    create_connection_request(
        from_clerk_id=clerk_id,
        to_clerk_id=activity["clerk_id"],
        activity_id=activity_id
    )
    
    return get_activity_by_id(activity_id)

def leave_activity(activity_id: str, clerk_id: str) -> bool:
    """Leave an activity"""
    db = get_db()
    
    activity = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not activity:
        return False
    
    # Can't leave if you're the creator
    if activity["clerk_id"] == clerk_id:
        raise ValueError("Creator cannot leave. Cancel the activity instead.")
    
    if clerk_id not in activity.get("participants", []):
        return False
    
    db.activities.update_one(
        {"_id": ObjectId(activity_id)},
        {
            "$pull": {"participants": clerk_id},
            "$inc": {"participant_count": -1},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return True

# ============= CONNECTIONS & CHAT =============

def create_connection_request(from_clerk_id: str, to_clerk_id: str, activity_id: str) -> Dict:
    """Create a connection request between users"""
    db = get_db()
    
    # Check if connection already exists
    existing = db.connections.find_one({
        "$or": [
            {"from_clerk_id": from_clerk_id, "to_clerk_id": to_clerk_id},
            {"from_clerk_id": to_clerk_id, "to_clerk_id": from_clerk_id}
        ],
        "activity_id": activity_id
    })
    
    if existing:
        return serialize_connection(existing)
    
    connection = {
        "from_clerk_id": from_clerk_id,
        "to_clerk_id": to_clerk_id,
        "activity_id": activity_id,
        "status": "pending",  # pending, accepted, declined
        "chat_enabled": False,
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = db.connections.insert_one(connection)
    connection["connection_id"] = str(result.inserted_id)
    
    return serialize_connection(connection)

def serialize_connection(doc) -> Optional[Dict]:
    """Serialize connection document"""
    if not doc:
        return None
    result = {}
    for key, value in doc.items():
        if key == '_id':
            result['connection_id'] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result

def respond_to_connection(connection_id: str, clerk_id: str, accept: bool) -> Optional[Dict]:
    """Accept or decline a connection request"""
    db = get_db()
    
    connection = db.connections.find_one({"_id": ObjectId(connection_id)})
    if not connection or connection["to_clerk_id"] != clerk_id:
        return None
    
    new_status = "accepted" if accept else "declined"
    
    db.connections.update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$set": {
                "status": new_status,
                "chat_enabled": accept,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return get_connection_by_id(connection_id)

def get_connection_by_id(connection_id: str) -> Optional[Dict]:
    """Get connection by ID"""
    db = get_db()
    try:
        conn = db.connections.find_one({"_id": ObjectId(connection_id)})
        return serialize_connection(conn)
    except:
        return None

def get_user_connections(clerk_id: str, status: Optional[str] = None) -> List[Dict]:
    """Get all connections for a user"""
    db = get_db()
    
    query = {
        "$or": [
            {"from_clerk_id": clerk_id},
            {"to_clerk_id": clerk_id}
        ]
    }
    
    if status:
        query["status"] = status
    
    connections = list(db.connections.find(query).sort("updated_at", -1))
    return [serialize_connection(c) for c in connections]

def send_message(connection_id: str, clerk_id: str, message: str) -> Optional[Dict]:
    """Send a chat message (only if connection accepted)"""
    db = get_db()
    
    connection = db.connections.find_one({"_id": ObjectId(connection_id)})
    if not connection:
        return None
    
    if not connection.get("chat_enabled"):
        raise ValueError("Chat not enabled. Connection must be accepted first.")
    
    # Verify user is part of connection
    if clerk_id not in [connection["from_clerk_id"], connection["to_clerk_id"]]:
        raise ValueError("Not authorized to send messages in this connection")
    
    msg = {
        "sender_id": clerk_id,
        "message": message,
        "sent_at": datetime.utcnow().isoformat()
    }
    
    db.connections.update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$push": {"messages": msg},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return get_connection_by_id(connection_id)

def get_pending_requests(clerk_id: str) -> List[Dict]:
    """Get pending connection requests for user"""
    db = get_db()
    
    requests = list(db.connections.find({
        "to_clerk_id": clerk_id,
        "status": "pending"
    }).sort("created_at", -1))
    
    return [serialize_connection(r) for r in requests]

# ============= CLEANUP =============

def cleanup_expired_activities():
    """Mark expired activities as completed"""
    db = get_db()
    
    result = db.activities.update_many(
        {
            "status": "active",
            "expires_at": {"$lt": datetime.utcnow()}
        },
        {"$set": {"status": "completed"}}
    )
    
    if result.modified_count > 0:
        print(f"🧹 Cleaned up {result.modified_count} expired activities")
    
    return result.modified_count

def get_activity_participants(activity_id: str) -> List[Dict]:
    """Get list of participants for an activity with user details"""
    db = get_db()
    
    activity = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not activity:
        raise ValueError("Activity not found")
    
    participants = []
    for clerk_id in activity.get("participants", []):
        user = db.users.find_one({"clerk_id": clerk_id})
        if user:
            participants.append({
                "clerk_id": clerk_id,
                "name": user.get("name", "Unknown"),
                "is_creator": clerk_id == activity["clerk_id"]
            })
    
    return participants

def get_activity_stats() -> Dict:
    """Get overall activity statistics"""
    db = get_db()
    
    total = db.activities.count_documents({})
    active = db.activities.count_documents({
        "status": "active",
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$activity_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    by_type = list(db.activities.aggregate(pipeline))
    
    return {
        "total": total,
        "active": active,
        "by_type": {item["_id"]: item["count"] for item in by_type}
    }