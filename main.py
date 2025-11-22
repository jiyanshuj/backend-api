"""
WanderEase Backend - Main API Server v3.0
With Activity Matching & Social Discovery
"""

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import uvicorn
from contextlib import asynccontextmanager

from db import init_db, close_db
from tourism import get_tourism_places
from restaurants import get_restaurants
from hotels import get_hotels
from maps import generate_map_image
from users import (
    create_user, get_user_by_clerk_id, update_user,
    add_liked_item, remove_liked_item, get_user_liked_items,
    is_item_liked, get_user_stats, delete_user
)
from activities import (
    ACTIVITY_TYPES, MOOD_TYPES,
    create_activity, get_activity_by_id, get_user_activities,
    update_activity, cancel_activity, find_nearby_activities,
    find_matching_activities, join_activity, leave_activity,
    get_user_connections, get_pending_requests, respond_to_connection,
    send_message, cleanup_expired_activities, get_activity_participants
)

# ============= PYDANTIC MODELS =============

class UserCreate(BaseModel):
    clerk_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class LikedItem(BaseModel):
    item_id: str
    name: str
    image_url: Optional[str] = None
    type: Optional[str] = None

class ActivityCreate(BaseModel):
    activity_type: str = Field(..., description="Type: cafe, garden, restaurant, mall, library, movie, gym, event, coworking")
    lat: float
    lon: float
    place_name: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    mood: Optional[str] = Field(None, description="Mood: chill, social, study, adventure, networking, casual")
    description: Optional[str] = Field(None, max_length=500)
    max_participants: int = Field(5, ge=2, le=20)
    is_public: bool = True

class ActivityUpdate(BaseModel):
    place_name: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    mood: Optional[str] = None
    description: Optional[str] = None
    max_participants: Optional[int] = None
    is_public: Optional[bool] = None

class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)

# ============= APP SETUP =============

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting WanderEase API Server v3.0...")
    print("🎯 Activity Matching: ENABLED")
    print("💬 Social Connections: ENABLED")
    init_db()
    yield
    print("👋 Shutting down WanderEase API Server...")
    close_db()

app = FastAPI(
    title="WanderEase API",
    version="3.0.0",
    description="Tourism API with Activity Matching & Social Discovery",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

def ensure_user_exists(clerk_id: str, name: Optional[str] = None, email: Optional[str] = None) -> dict:
    user = get_user_by_clerk_id(clerk_id)
    if not user:
        print(f"🆕 Auto-creating user: {clerk_id}")
        if not email:
            email = clerk_id if '@' in clerk_id else f"{clerk_id}@wander-ease.app"
        if not name:
            name = clerk_id.split('@')[0] if '@' in clerk_id else clerk_id
        try:
            user = create_user(clerk_id=clerk_id, name=name, email=email, phone=None)
            print(f"✅ Auto-created user: {clerk_id}")
        except ValueError:
            user = get_user_by_clerk_id(clerk_id)
            if not user:
                raise
    return user

@app.get("/")
async def root():
    return {
        "message": "WanderEase API",
        "version": "3.0.0",
        "features": {
            "google_images": "enabled",
            "activity_matching": "enabled",
            "social_discovery": "enabled",
            "real_time_chat": "enabled"
        },
        "endpoints": {
            "tourism": "/api/tourism",
            "restaurants": "/api/restaurants",
            "hotels": "/api/hotels",
            "map": "/api/map",
            "activities": "/api/activities",
            "connections": "/api/connections",
            "users": "/api/users"
        },
        "documentation": "/docs"
    }

# ============= TOURISM ENDPOINTS =============

@app.get("/api/tourism")
async def search_tourism(
    location: str = Query(...),
    limit: int = Query(20, ge=1, le=50)
):
    try:
        places = await get_tourism_places(location, limit)
        return {"success": True, "location": location, "count": len(places), "data": places}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restaurants")
async def search_restaurants(
    location: str = Query(...),
    limit: int = Query(20, ge=1, le=50)
):
    try:
        restaurants = await get_restaurants(location, limit)
        return {"success": True, "location": location, "count": len(restaurants), "data": restaurants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hotels")
async def search_hotels(
    location: str = Query(...),
    limit: int = Query(20, ge=1, le=50)
):
    try:
        hotels = await get_hotels(location, limit)
        return {"success": True, "location": location, "count": len(hotels), "data": hotels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= MAP ENDPOINTS =============

@app.get("/api/map")
async def get_map(
    location: str = Query(...),
    markers: Optional[str] = Query(None),
    show_nearby: Optional[str] = Query(None),
    nearby_radius: int = Query(1000, ge=100, le=5000),
    nearby_limit: int = Query(20, ge=1, le=50)
):
    try:
        map_data = await generate_map_image(
            location=location, markers=markers, show_nearby=show_nearby,
            nearby_radius=nearby_radius, nearby_limit=nearby_limit
        )
        return {"success": True, "location": location, **map_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/map/html", response_class=HTMLResponse)
async def get_map_html(
    location: str = Query(...),
    markers: Optional[str] = Query(None),
    show_nearby: Optional[str] = Query(None),
    nearby_radius: int = Query(1000),
    nearby_limit: int = Query(20)
):
    try:
        map_data = await generate_map_image(
            location=location, markers=markers, show_nearby=show_nearby,
            nearby_radius=nearby_radius, nearby_limit=nearby_limit
        )
        return map_data["map_html"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= USER ENDPOINTS =============

@app.post("/api/users")
async def register_user(user: UserCreate):
    try:
        new_user = create_user(clerk_id=user.clerk_id, name=user.name, email=user.email, phone=user.phone)
        return {"success": True, "message": "User registered", "user": new_user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/users/{clerk_id}")
async def get_user(clerk_id: str):
    try:
        user = ensure_user_exists(clerk_id)
        return {"success": True, "user": user}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{clerk_id}")
async def update_user_profile(clerk_id: str, updates: UserUpdate):
    try:
        ensure_user_exists(clerk_id)
        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        updated = update_user(clerk_id, **update_data)
        return {"success": True, "user": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{clerk_id}")
async def delete_user_account(clerk_id: str):
    try:
        if delete_user(clerk_id):
            return {"success": True, "message": "User deleted"}
        raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{clerk_id}/likes/{category}")
async def like_item(clerk_id: str, category: str, item: LikedItem = Body(...)):
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(status_code=400, detail="Invalid category")
        ensure_user_exists(clerk_id)
        updated = add_liked_item(clerk_id, category, item.item_id, item.dict())
        return {"success": True, "liked": updated.get("liked", {})}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{clerk_id}/likes/{category}/{item_id}")
async def unlike_item(clerk_id: str, category: str, item_id: str):
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(status_code=400, detail="Invalid category")
        updated = remove_liked_item(clerk_id, category, item_id)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "liked": updated.get("liked", {})}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/likes")
async def get_liked_items(clerk_id: str, category: Optional[str] = Query(None)):
    try:
        ensure_user_exists(clerk_id)
        liked = get_user_liked_items(clerk_id, category)
        return {"success": True, "liked": liked or {"tourism": [], "restaurants": [], "hotels": []}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/likes/{category}/{item_id}/check")
async def check_if_liked(clerk_id: str, category: str, item_id: str):
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(status_code=400, detail="Invalid category")
        user = get_user_by_clerk_id(clerk_id)
        is_liked = is_item_liked(clerk_id, category, item_id) if user else False
        return {"success": True, "is_liked": is_liked}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/stats")
async def get_user_statistics(clerk_id: str):
    try:
        ensure_user_exists(clerk_id)
        stats = get_user_stats(clerk_id)
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= ACTIVITY ENDPOINTS =============

@app.get("/api/activities/types")
async def get_activity_types():
    """Get all available activity types and moods"""
    return {"success": True, "activity_types": ACTIVITY_TYPES, "mood_types": MOOD_TYPES}

@app.post("/api/activities")
async def create_new_activity(clerk_id: str = Query(...), activity: ActivityCreate = Body(...)):
    """Create a new activity - auto-creates user if needed"""
    try:
        ensure_user_exists(clerk_id)
        new_activity = create_activity(
            clerk_id=clerk_id,
            activity_type=activity.activity_type,
            lat=activity.lat,
            lon=activity.lon,
            place_name=activity.place_name,
            scheduled_time=activity.scheduled_time,
            mood=activity.mood,
            description=activity.description,
            max_participants=activity.max_participants,
            is_public=activity.is_public
        )
        return {"success": True, "message": "Activity created", "activity": new_activity}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/activities/nearby")
async def search_nearby_activities(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    activity_type: Optional[str] = Query(None, description="Filter by type"),
    radius_km: float = Query(5.0, ge=0.5, le=50),
    mood: Optional[str] = Query(None),
    clerk_id: Optional[str] = Query(None, description="Exclude own activities"),
    limit: int = Query(20, ge=1, le=50)
):
    """Find nearby activities - main discovery endpoint"""
    try:
        activities = find_nearby_activities(
            lat=lat, lon=lon, activity_type=activity_type,
            radius_km=radius_km, mood=mood,
            exclude_clerk_id=clerk_id, limit=limit
        )
        return {
            "success": True,
            "search_center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "count": len(activities),
            "activities": activities
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/activities/match")
async def find_activity_matches(
    clerk_id: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
    activity_type: str = Query(..., description="What you're planning to do"),
    radius_km: float = Query(3.0, ge=0.5, le=20),
    time_window_hours: int = Query(2, ge=1, le=8)
):
    """Find people doing the same activity nearby right now"""
    try:
        matches = find_matching_activities(
            clerk_id=clerk_id, lat=lat, lon=lon,
            activity_type=activity_type, radius_km=radius_km,
            time_window_hours=time_window_hours
        )
        return {
            "success": True,
            "your_activity": activity_type,
            "your_location": {"lat": lat, "lon": lon},
            "matches_found": len(matches),
            "matches": matches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/activities/user/{clerk_id}")
async def get_activities_by_user(clerk_id: str, status: Optional[str] = Query(None)):
    """Get all activities created by a user"""
    activities = get_user_activities(clerk_id, status)
    return {"success": True, "count": len(activities), "activities": activities}

@app.get("/api/activities/{activity_id}")
async def get_activity(activity_id: str):
    """Get activity details by ID"""
    activity = get_activity_by_id(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {"success": True, "activity": activity}

@app.get("/api/activities/{activity_id}/participants")
async def get_participants(activity_id: str):
    """Get participants of an activity"""
    try:
        participants = get_activity_participants(activity_id)
        return {"success": True, "participants": participants}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/api/activities/{activity_id}")
async def update_activity_endpoint(activity_id: str, clerk_id: str = Query(...), updates: ActivityUpdate = Body(...)):
    """Update an activity (only by creator)"""
    try:
        updated = update_activity(activity_id, clerk_id, **updates.dict(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=403, detail="Not authorized")
        return {"success": True, "activity": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/activities/{activity_id}")
async def cancel_activity_endpoint(activity_id: str, clerk_id: str = Query(...)):
    """Cancel an activity (only by creator)"""
    if cancel_activity(activity_id, clerk_id):
        return {"success": True, "message": "Activity cancelled"}
    raise HTTPException(status_code=403, detail="Not authorized")

@app.post("/api/activities/{activity_id}/join")
async def join_activity_endpoint(activity_id: str, clerk_id: str = Query(...)):
    """Join an activity"""
    try:
        ensure_user_exists(clerk_id)
        updated = join_activity(activity_id, clerk_id)
        return {"success": True, "message": "Joined activity", "activity": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/activities/{activity_id}/leave")
async def leave_activity_endpoint(activity_id: str, clerk_id: str = Query(...)):
    """Leave an activity"""
    try:
        if leave_activity(activity_id, clerk_id):
            return {"success": True, "message": "Left activity"}
        raise HTTPException(status_code=400, detail="Not in activity")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============= CONNECTION ENDPOINTS =============

@app.get("/api/connections")
async def get_all_connections(clerk_id: str = Query(...), status: Optional[str] = Query(None)):
    """Get all connections for a user"""
    connections = get_user_connections(clerk_id, status)
    return {"success": True, "count": len(connections), "connections": connections}

@app.get("/api/connections/pending")
async def get_pending_connection_requests(clerk_id: str = Query(...)):
    """Get pending connection requests"""
    requests = get_pending_requests(clerk_id)
    return {"success": True, "count": len(requests), "pending_requests": requests}

@app.post("/api/connections/{connection_id}/respond")
async def respond_to_connection_request(connection_id: str, clerk_id: str = Query(...), accept: bool = Query(...)):
    """Accept or decline a connection request"""
    result = respond_to_connection(connection_id, clerk_id, accept)
    if not result:
        raise HTTPException(status_code=403, detail="Not authorized")
    action = "accepted" if accept else "declined"
    return {"success": True, "message": f"Connection {action}", "connection": result}

@app.post("/api/connections/{connection_id}/message")
async def send_chat_message(connection_id: str, clerk_id: str = Query(...), msg: MessageCreate = Body(...)):
    """Send a message in a connection chat"""
    try:
        result = send_message(connection_id, clerk_id, msg.message)
        if not result:
            raise HTTPException(status_code=404, detail="Connection not found")
        return {"success": True, "connection": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============= ADMIN ENDPOINTS =============

@app.post("/api/admin/cleanup")
async def cleanup_expired():
    """Cleanup expired activities"""
    count = cleanup_expired_activities()
    return {"success": True, "cleaned_up": count}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "features": ["tourism", "restaurants", "hotels", "activities", "connections", "chat"]
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 WanderEase API Server v3.0")
    print("="*60)
    print("\n🎯 Activity Matching Features:")
    print("   • Create & discover activities")
    print("   • Location-based matching")
    print("   • Social connections & chat")
    print("\n📍 API Docs: http://127.0.0.1:8000/docs")
    print("="*60 + "\n")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)