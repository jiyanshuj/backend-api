"""
WanderEase Backend - Main API Server
FastAPI application for tourism, restaurants, and hotels
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn

from db import init_db, close_db
from tourism import get_tourism_places
from restaurants import get_restaurants
from hotels import get_hotels
from maps import generate_map_image

# We'll create the FastAPI app later with a lifespan handler and then attach CORS middleware to it.

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    init_db()
    yield
    # Shutdown
    close_db()

# Replace the app initialization
app = FastAPI(title="WanderEase API", version="1.0.0", lifespan=lifespan)

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
        "version": "1.0.0",
        "endpoints": {
            "tourism": "/api/tourism",
            "restaurants": "/api/restaurants",
            "hotels": "/api/hotels",
            "map": "/api/map"
        }
    }

@app.get("/api/tourism")
async def search_tourism(
    location: str = Query(..., description="Location to search (city, area, country)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search tourism places by location
    First checks MongoDB, then fetches from OpenStreetMap if needed
    """
    try:
        places = await get_tourism_places(location, limit)
        return {
            "success": True,
            "location": location,
            "count": len(places),
            "data": places
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restaurants")
async def search_restaurants(
    location: str = Query(..., description="Location to search"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search restaurants by location
    First checks MongoDB, then fetches from OpenStreetMap if needed
    """
    try:
        restaurants = await get_restaurants(location, limit)
        return {
            "success": True,
            "location": location,
            "count": len(restaurants),
            "data": restaurants
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hotels")
async def search_hotels(
    location: str = Query(..., description="Location to search"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return")
):
    """
    Search hotels by location
    First checks MongoDB, then fetches from OpenStreetMap if needed
    """
    try:
        hotels = await get_hotels(location, limit)
        return {
            "success": True,
            "location": location,
            "count": len(hotels),
            "data": hotels
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/map")
async def get_map(
    location: str = Query(..., description="Location for map"),
    markers: Optional[str] = Query(None, description="Comma-separated lat,lon pairs"),
    show_nearby: Optional[str] = Query(None, description="Show nearby places (not implemented yet)")
):
    """
    Generate interactive OpenStreetMap with markers
    Returns HTML map content using OSM Nominatim and Leaflet.js
    """
    try:
        map_data = await generate_map_image(location, markers, show_nearby)
        return {
            "success": True,
            "location": location,
            "map_html": map_data["map_html"],
            "center": map_data["center"],
            "markers": map_data.get("markers", [])
        }
    except Exception as e:
        import traceback
        print(f"Map error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    # Use 127.0.0.1 for local development (works better with localhost)
    # Use 0.0.0.0 for production/network access
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)