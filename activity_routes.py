"""
Activity API Routes - FastAPI endpoints for activity matching
Add these routes to your main.py
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from activities import (
    ACTIVITY_TYPES, MOOD_TYPES,
    create_activity, get_activity_by_id, get_user_activities,
    update_activity, cancel_activity,
    find_nearby_activities, find_matching_activities,
    join_activity, leave_activity,
    create_connection_request, respond_to_connection,
    get_user_connections, get_pending_requests,
    send_message, cleanup_expired_activities
)
from main import ensure_user_exists

router = APIRouter(prefix="/api/activities", tags=["Activities"])

# ============= PYDANTIC MODELS =============

class ActivityCreate(BaseModel):
    activity_type: str = Field(..., description="Type of activity")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    place_name: Optional[str] = Field(None, description="Name of place")
    scheduled_time: Optional[datetime] = Field(None, description="When activity is planned")
    mood: Optional[str] = Field(None, description="Activity mood")
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
    status: Optional[str] = None

class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)

class ConnectionResponse(BaseModel):
    accept: bool

# ============= METADATA ENDPOINTS =============

@router.get("/types")
async def get_activity_types():
    """Get all available activity types"""
    return {
        "success": True,
        "activity_types": ACTIVITY_TYPES,
        "mood_types": MOOD_TYPES
    }

# ============= ACTIVITY CRUD =============

@router.post("")
async def create_new_activity(
    clerk_id: str = Query(..., description="User's Clerk ID"),
    activity: ActivityCreate = Body(...)
):
    """
    Create a new activity post
    Auto-creates user if doesn't exist
    """
    try:
        # Ensure user exists
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
        
        return {
            "success": True,
            "message": "Activity created successfully",
            "activity": new_activity
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Create activity error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{activity_id}")
async def get_activity(activity_id: str):
    """Get activity by ID"""
    activity = get_activity_by_id(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return {"success": True, "activity": activity}

@router.get("/user/{clerk_id}")
async def get_activities_by_user(
    clerk_id: str,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get all activities by a user"""
    activities = get_user_activities(clerk_id, status)
    return {
        "success": True,
        "count": len(activities),
        "activities": activities
    }

@router.put("/{activity_id}")
async def update_activity_endpoint(
    activity_id: str,
    clerk_id: str = Query(...),
    updates: ActivityUpdate = Body(...)
):
    """Update an activity (only by creator)"""
    try:
        updated = update_activity(
            activity_id, 
            clerk_id, 
            **updates.dict(exclude_unset=True)
        )
        if not updated:
            raise HTTPException(status_code=403, detail="Not authorized or activity not found")
        
        return {"success": True, "activity": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{activity_id}")
async def cancel_activity_endpoint(
    activity_id: str,
    clerk_id: str = Query(...)
):
    """Cancel an activity"""
    success = cancel_activity(activity_id, clerk_id)
    if not success:
        raise HTTPException(status_code=403, detail="Not authorized or activity not found")
    
    return {"success": True, "message": "Activity cancelled"}

# ============= DISCOVERY & MATCHING =============

@router.get("/nearby/search")
async def search_nearby_activities(
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    radius_km: float = Query(5.0, ge=0.5, le=50, description="Search radius in km"),
    mood: Optional[str] = Query(None, description="Filter by mood"),
    clerk_id: Optional[str] = Query(None, description="Exclude own activities"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Find nearby activities
    Main discovery endpoint for map view
    """
    try:
        activities = find_nearby_activities(
            lat=lat,
            lon=lon,
            activity_type=activity_type,
            radius_km=radius_km,
            mood=mood,
            exclude_clerk_id=clerk_id,
            limit=limit
        )
        
        return {
            "success": True,
            "search_center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "count": len(activities),
            "activities": activities
        }
    except Exception as e:
        print(f"❌ Nearby search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/match/find")
async def find_activity_matches(
    clerk_id: str = Query(..., description="User's Clerk ID"),
    lat: float = Query(...),
    lon: float = Query(...),
    activity_type: str = Query(..., description="What user is planning to do"),
    radius_km: float = Query(3.0, ge=0.5, le=20),
    time_window_hours: int = Query(2, ge=1, le=8)
):
    """
    Find people planning the same activity nearby
    Best for "who else is doing X near me right now?"
    """
    try:
        matches = find_matching_activities(
            clerk_id=clerk_id,
            lat=lat,
            lon=lon,
            activity_type=activity_type,
            radius_km=radius_km,
            time_window_hours=time_window_hours
        )
        
        return {
            "success": True,
            "your_activity": activity_type,
            "matches_found": len(matches),
            "matches": matches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= PARTICIPATION =============

@router.post("/{activity_id}/join")
async def join_activity_endpoint(
    activity_id: str,
    clerk_id: str = Query(...)
):
    """Request to join an activity"""
    try:
        ensure_user_exists(clerk_id)
        updated = join_activity(activity_id, clerk_id)
        return {
            "success": True,
            "message": "Joined activity successfully",
            "activity": updated
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{activity_id}/leave")
async def leave_activity_endpoint(
    activity_id: str,
    clerk_id: str = Query(...)
):
    """Leave an activity"""
    try:
        success = leave_activity(activity_id, clerk_id)
        if not success:
            raise HTTPException(status_code=400, detail="Not in this activity")
        return {"success": True, "message": "Left activity"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============= CONNECTIONS =============

@router.get("/connections/pending")
async def get_pending_connection_requests(
    clerk_id: str = Query(...)
):
    """Get pending connection requests"""
    requests = get_pending_requests(clerk_id)
    return {
        "success": True,
        "count": len(requests),
        "pending_requests": requests
    }

@router.get("/connections/all")
async def get_all_connections(
    clerk_id: str = Query(...),
    status: Optional[str] = Query(None)
):
    """Get all connections for a user"""
    connections = get_user_connections(clerk_id, status)
    return {
        "success": True,
        "count": len(connections),
        "connections": connections
    }

@router.post("/connections/{connection_id}/respond")
async def respond_to_connection_request(
    connection_id: str,
    clerk_id: str = Query(...),
    response: ConnectionResponse = Body(...)
):
    """Accept or decline a connection request"""
    result = respond_to_connection(connection_id, clerk_id, response.accept)
    if not result:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    action = "accepted" if response.accept else "declined"
    return {
        "success": True,
        "message": f"Connection {action}",
        "connection": result
    }

@router.post("/connections/{connection_id}/message")
async def send_chat_message(
    connection_id: str,
    clerk_id: str = Query(...),
    msg: MessageCreate = Body(...)
):
    """Send a message in a connection chat"""
    try:
        result = send_message(connection_id, clerk_id, msg.message)
        if not result:
            raise HTTPException(status_code=404, detail="Connection not found")
        return {"success": True, "connection": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============= ADMIN/MAINTENANCE =============

@router.post("/cleanup")
async def cleanup_expired():
    """Cleanup expired activities (admin endpoint)"""
    count = cleanup_expired_activities()
    return {"success": True, "cleaned_up": count}