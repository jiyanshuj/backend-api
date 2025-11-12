"""
WanderEase Backend - Main API Server
FastAPI application for tourism, restaurants, hotels, and user management
Now with Google Custom Search API integration for real images
"""

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional
from pydantic import BaseModel, EmailStr
import uvicorn

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

from contextlib import asynccontextmanager

# Pydantic models for user requests
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    print("🚀 Starting WanderEase API Server...")
    print("📸 Google Custom Search API: ENABLED")
    print("🔑 API Key Status: Active")
    print("👤 User Management: ENABLED")
    init_db()
    yield
    # Shutdown
    print("👋 Shutting down WanderEase API Server...")
    close_db()

# Initialize FastAPI app
app = FastAPI(
    title="WanderEase API",
    version="2.1.0",
    description="Tourism API with real images and user management",
    lifespan=lifespan
)

# CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "WanderEase API",
        "version": "2.1.0",
        "features": {
            "google_images": "enabled",
            "real_time_search": "enabled",
            "mongodb_caching": "enabled",
            "user_management": "enabled"
        },
        "endpoints": {
            "tourism": "/api/tourism",
            "restaurants": "/api/restaurants",
            "hotels": "/api/hotels",
            "map": "/api/map",
            "map_html": "/api/map/html",
            "users": "/api/users",
            "health": "/health"
        },
        "documentation": "/docs"
    }

# ============= EXISTING ENDPOINTS (UNCHANGED) =============

@app.get("/api/tourism")
async def search_tourism(
    location: str = Query(..., description="Location to search (city, area, country)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search tourism places by location with real Google images
    First checks MongoDB, then fetches from OpenStreetMap if needed
    Images are fetched from Google Custom Search API
    """
    try:
        print(f"\n🏛️ Searching tourism places for: {location}")
        places = await get_tourism_places(location, limit)
        
        return {
            "success": True,
            "location": location,
            "count": len(places),
            "data": places,
            "image_source": "Google Custom Search API"
        }
    except Exception as e:
        print(f"❌ Tourism search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restaurants")
async def search_restaurants(
    location: str = Query(..., description="Location to search"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search restaurants by location with real Google images
    First checks MongoDB, then fetches from OpenStreetMap if needed
    Images are fetched from Google Custom Search API
    """
    try:
        print(f"\n🍽️ Searching restaurants for: {location}")
        restaurants = await get_restaurants(location, limit)
        
        return {
            "success": True,
            "location": location,
            "count": len(restaurants),
            "data": restaurants,
            "image_source": "Google Custom Search API"
        }
    except Exception as e:
        print(f"❌ Restaurant search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hotels")
async def search_hotels(
    location: str = Query(..., description="Location to search"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search hotels by location with real Google images
    First checks MongoDB, then fetches from OpenStreetMap if needed
    Images are fetched from Google Custom Search API
    """
    try:
        print(f"\n🏨 Searching hotels for: {location}")
        hotels = await get_hotels(location, limit)
        
        return {
            "success": True,
            "location": location,
            "count": len(hotels),
            "data": hotels,
            "image_source": "Google Custom Search API"
        }
    except Exception as e:
        print(f"❌ Hotel search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/map")
async def get_map(
    location: str = Query(..., description="Location for map center"),
    markers: Optional[str] = Query(None, description="Comma-separated lat,lon pairs (e.g., '22.7196,75.8577,22.7242,75.8652')"),
    show_nearby: Optional[str] = Query(None, description="Show nearby places: tourism, restaurant, hotel, cafe"),
    nearby_radius: int = Query(1000, ge=100, le=5000, description="Search radius in meters (100-5000)"),
    nearby_limit: int = Query(20, ge=1, le=50, description="Maximum nearby places to show (1-50)")
):
    """Generate interactive OpenStreetMap with markers and nearby places"""
    try:
        print(f"\n🗺️ Generating map for: {location}")
        map_data = await generate_map_image(
            location=location,
            markers=markers,
            show_nearby=show_nearby,
            nearby_radius=nearby_radius,
            nearby_limit=nearby_limit
        )
        return {
            "success": True,
            "location": location,
            "map_html": map_data["map_html"],
            "center": map_data["center"],
            "markers": map_data.get("markers", []),
            "nearby_count": map_data.get("nearby_count", 0)
        }
    except Exception as e:
        import traceback
        print(f"❌ Map error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/map/html", response_class=HTMLResponse)
async def get_map_html(
    location: str = Query(..., description="Location for map center"),
    markers: Optional[str] = Query(None, description="Comma-separated lat,lon pairs"),
    show_nearby: Optional[str] = Query(None, description="Show nearby places: tourism, restaurant, hotel, cafe"),
    nearby_radius: int = Query(1000, ge=100, le=5000, description="Search radius in meters"),
    nearby_limit: int = Query(20, ge=1, le=50, description="Maximum nearby places to show")
):
    """Generate interactive OpenStreetMap - returns HTML directly for embedding"""
    try:
        map_data = await generate_map_image(
            location=location,
            markers=markers,
            show_nearby=show_nearby,
            nearby_radius=nearby_radius,
            nearby_limit=nearby_limit
        )
        return map_data["map_html"]
    except Exception as e:
        import traceback
        print(f"❌ Map HTML error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============= NEW USER ENDPOINTS =============

@app.post("/api/users")
async def register_user(user: UserCreate):
    """
    Register a new user
    
    Required fields:
    - clerk_id: Unique Clerk authentication ID (primary key)
    - name: User's full name
    - email: User's email address
    - phone: User's phone number (optional)
    """
    try:
        new_user = create_user(
            clerk_id=user.clerk_id,
            name=user.name,
            email=user.email,
            phone=user.phone
        )
        return {
            "success": True,
            "message": "User registered successfully",
            "user": new_user
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ User registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}")
async def get_user(clerk_id: str):
    """Get user profile by Clerk ID"""
    try:
        user = get_user_by_clerk_id(clerk_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "user": user
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{clerk_id}")
async def update_user_profile(clerk_id: str, updates: UserUpdate):
    """
    Update user profile
    
    Optional fields to update:
    - name
    - email
    - phone
    """
    try:
        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updated_user = update_user(clerk_id, **update_data)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "message": "User updated successfully",
            "user": updated_user
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Update user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{clerk_id}")
async def delete_user_account(clerk_id: str):
    """Delete user account"""
    try:
        deleted = delete_user(clerk_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Delete user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{clerk_id}/likes/{category}")
async def like_item(
    clerk_id: str,
    category: str,
    item: LikedItem = Body(...)
):
    """
    Add an item to user's liked list
    
    Categories: tourism, restaurants, hotels
    
    Required in request body:
    - item_id: ID of the item
    - name: Name of the item
    - image_url: Image URL (optional)
    - type: Type of item (optional)
    """
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid category. Must be tourism, restaurants, or hotels"
            )
        
        updated_user = add_liked_item(
            clerk_id=clerk_id,
            category=category,
            item_id=item.item_id,
            item_data=item.dict()
        )
        
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "message": f"Item added to {category} likes",
            "liked": updated_user.get("liked", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Like item error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{clerk_id}/likes/{category}/{item_id}")
async def unlike_item(clerk_id: str, category: str, item_id: str):
    """
    Remove an item from user's liked list
    
    Categories: tourism, restaurants, hotels
    """
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid category. Must be tourism, restaurants, or hotels"
            )
        
        updated_user = remove_liked_item(clerk_id, category, item_id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "message": f"Item removed from {category} likes",
            "liked": updated_user.get("liked", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unlike item error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/likes")
async def get_liked_items(
    clerk_id: str,
    category: Optional[str] = Query(None, description="Filter by category: tourism, restaurants, hotels")
):
    """
    Get all liked items for a user
    
    Optional query parameter:
    - category: Filter by specific category (tourism, restaurants, hotels)
    """
    try:
        liked_items = get_user_liked_items(clerk_id, category)
        if liked_items is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "clerk_id": clerk_id,
            "liked": liked_items
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get liked items error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/likes/{category}/{item_id}/check")
async def check_if_liked(clerk_id: str, category: str, item_id: str):
    """
    Check if a specific item is liked by the user
    
    Categories: tourism, restaurants, hotels
    """
    try:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid category. Must be tourism, restaurants, or hotels"
            )
        
        is_liked = is_item_liked(clerk_id, category, item_id)
        
        return {
            "success": True,
            "clerk_id": clerk_id,
            "category": category,
            "item_id": item_id,
            "is_liked": is_liked
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Check liked error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{clerk_id}/stats")
async def get_user_statistics(clerk_id: str):
    """Get user statistics (liked counts, member since, etc.)"""
    try:
        stats = get_user_stats(clerk_id)
        if not stats:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint with API status"""
    return {
        "status": "healthy",
        "version": "2.1.0",
        "features": {
            "google_images": "enabled",
            "database": "connected",
            "user_management": "enabled"
        }
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 WanderEase API Server Starting...")
    print("="*60)
    print("\n📸 Image Features:")
    print("   ✅ Google Custom Search API: ENABLED")
    print("   ✅ Real-time image fetching: ACTIVE")
    print("   ✅ Fallback to Wikimedia: ENABLED")
    print("\n👤 User Management:")
    print("   ✅ User Registration & Authentication")
    print("   ✅ Liked Items (Tourism, Restaurants, Hotels)")
    print("   ✅ User Profile Management")
    print("\n📍 Quick Links:")
    print("   • API Docs: http://127.0.0.1:8000/docs")
    print("   • Health Check: http://127.0.0.1:8000/health")
    print("   • Interactive Map: http://127.0.0.1:8000/api/map/html?location=Indore")
    print("\n🔍 Example Searches:")
    print("   • Tourism: http://127.0.0.1:8000/api/tourism?location=Paris&limit=10")
    print("   • Restaurants: http://127.0.0.1:8000/api/restaurants?location=Tokyo&limit=10")
    print("   • Hotels: http://127.0.0.1:8000/api/hotels?location=London&limit=10")
    print("\n👤 User Endpoints:")
    print("   • Register User: POST /api/users")
    print("   • Get User: GET /api/users/{clerk_id}")
    print("   • Like Item: POST /api/users/{clerk_id}/likes/{category}")
    print("   • Get Likes: GET /api/users/{clerk_id}/likes")
    print("\n⚠️ API Rate Limits:")
    print("   • Google Custom Search: 100 queries/day (free tier)")
    print("   • Tip: Results are cached in MongoDB to reduce API calls")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)