"""
WanderEase Backend - Main API Server
FastAPI application for tourism, restaurants, and hotels
Now with Google Custom Search API integration for real images
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional
import uvicorn

from db import init_db, close_db
from tourism import get_tourism_places
from restaurants import get_restaurants
from hotels import get_hotels
from maps import generate_map_image

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    print("🚀 Starting WanderEase API Server...")
    print("📸 Google Custom Search API: ENABLED")
    print("🔑 API Key Status: Active")
    init_db()
    yield
    # Shutdown
    print("👋 Shutting down WanderEase API Server...")
    close_db()

# Initialize FastAPI app
app = FastAPI(
    title="WanderEase API",
    version="2.0.0",
    description="Tourism API with real images powered by Google Custom Search",
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
        "version": "2.0.0",
        "features": {
            "google_images": "enabled",
            "real_time_search": "enabled",
            "mongodb_caching": "enabled"
        },
        "endpoints": {
            "tourism": "/api/tourism",
            "restaurants": "/api/restaurants",
            "hotels": "/api/hotels",
            "map": "/api/map",
            "map_html": "/api/map/html",
            "health": "/health"
        },
        "documentation": "/docs"
    }

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
    """
    Generate interactive OpenStreetMap with markers and nearby places
    Returns JSON with map HTML, center coordinates, and marker data
    
    Examples:
    - /api/map?location=Indore
    - /api/map?location=Indore&show_nearby=tourism
    - /api/map?location=Indore&show_nearby=restaurant&nearby_radius=1500
    - /api/map?location=Paris&markers=48.8566,2.3522&show_nearby=hotel
    """
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
    """
    Generate interactive OpenStreetMap - returns HTML directly for embedding
    Opens directly in browser as a full interactive map
    
    Examples:
    - /api/map/html?location=Indore&show_nearby=tourism
    - /api/map/html?location=New York&show_nearby=restaurant&nearby_radius=2000
    """
    try:
        map_data = await generate_map_image(
            location=location,
            markers=markers,
            show_nearby=show_nearby,
            nearby_radius=nearby_radius,
            nearby_limit=nearby_limit
        )
        # Return HTML directly for browser viewing
        return map_data["map_html"]
    except Exception as e:
        import traceback
        print(f"❌ Map HTML error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint with API status"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "features": {
            "google_images": "enabled",
            "database": "connected"
        }
    }

if __name__ == "__main__":
    # Use 127.0.0.1 for local development (works better with localhost)
    # Use 0.0.0.0 for production/network access
    print("\n" + "="*60)
    print("🚀 WanderEase API Server Starting...")
    print("="*60)
    print("\n📸 Image Features:")
    print("   ✅ Google Custom Search API: ENABLED")
    print("   ✅ Real-time image fetching: ACTIVE")
    print("   ✅ Fallback to Wikimedia: ENABLED")
    print("\n📍 Quick Links:")
    print("   • API Docs: http://127.0.0.1:8000/docs")
    print("   • Health Check: http://127.0.0.1:8000/health")
    print("   • Interactive Map: http://127.0.0.1:8000/api/map/html?location=Indore")
    print("\n🔍 Example Searches:")
    print("   • Tourism: http://127.0.0.1:8000/api/tourism?location=Paris&limit=10")
    print("   • Restaurants: http://127.0.0.1:8000/api/restaurants?location=Tokyo&limit=10")
    print("   • Hotels: http://127.0.0.1:8000/api/hotels?location=London&limit=10")
    print("\n⚠️ API Rate Limits:")
    print("   • Google Custom Search: 100 queries/day (free tier)")
    print("   • Tip: Results are cached in MongoDB to reduce API calls")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)