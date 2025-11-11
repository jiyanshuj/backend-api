"""
Restaurants module
Handles fetching restaurant data from MongoDB or OpenStreetMap
Now with Google Custom Search API for real images
"""

import requests
from typing import List, Dict
from db import get_restaurants_from_db, save_restaurants_to_db
from utils import get_location_coordinates, build_address, fetch_google_image

async def get_restaurants(location: str, limit: int = 20) -> List[Dict]:
    """
    Get restaurants for a location
    1. First check MongoDB
    2. If not found or insufficient, fetch from OpenStreetMap
    3. Save to MongoDB for future queries
    """
    # Check MongoDB first
    restaurants = get_restaurants_from_db(location, limit)
    
    if restaurants and len(restaurants) >= limit:
        print(f"Found {len(restaurants)} restaurants in MongoDB for {location}")
        return restaurants
    
    # Fetch from OpenStreetMap
    print(f"Fetching restaurants from OpenStreetMap for {location}")
    restaurants = await fetch_restaurants_from_osm(location, limit)
    
    # Save to MongoDB
    if restaurants:
        save_restaurants_to_db(restaurants, location)
    
    return restaurants

async def fetch_restaurants_from_osm(query: str, limit: int = 20) -> List[Dict]:
    """
    Fetch restaurants from OpenStreetMap using Overpass API
    Enhanced with Google Custom Search for real images
    """
    try:
        # Get location coordinates
        location = get_location_coordinates(query)
        if not location:
            return []
        
        lat = location['lat']
        lon = location['lon']
        
        # Overpass API endpoint
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Search radius (5km)
        radius = 5000
        
        # Query for restaurants
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"restaurant|cafe|fast_food|food_court|bar|pub"](around:{radius},{lat},{lon});
          way["amenity"~"restaurant|cafe|fast_food|food_court|bar|pub"](around:{radius},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        response = requests.post(
            overpass_url,
            data={'data': overpass_query},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        restaurants = []
        seen_names = set()
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            name = tags.get('name', 'Unnamed Restaurant')
            
            # Skip duplicates and unnamed
            if name in seen_names or name == 'Unnamed Restaurant':
                continue
            seen_names.add(name)
            
            # Get coordinates
            place_lat = element.get('lat', lat)
            place_lon = element.get('lon', lon)
            
            # Get amenity type
            amenity_type = tags.get('amenity', 'restaurant')
            
            # Fetch real image from Google Custom Search
            print(f"🔍 Fetching image for restaurant: {name}")
            image_url = await fetch_google_image(f"{name} {amenity_type}", query)
            
            # Get cuisine
            cuisine = tags.get('cuisine', 'Multi-cuisine')
            cuisine = cuisine.replace('_', ' ').replace(';', ', ').title()
            
            restaurant = {
                'restaurant_id': f"R{element.get('id', 0)}",
                'name': name,
                'type': amenity_type.replace('_', ' ').title(),
                'cuisine': cuisine,
                'location': {
                    'type': 'Point',
                    'coordinates': [place_lon, place_lat]
                },
                'lat': place_lat,
                'lon': place_lon,
                'image_url': image_url,
                'address': build_address(tags),
                'rating': 3.5 + (hash(name) % 15) / 10,
                'price_range': tags.get('payment:coins', '$$'),
                'opening_hours': tags.get('opening_hours', 'Not available'),
                'delivery': tags.get('delivery', 'unknown'),
                'takeaway': tags.get('takeaway', 'unknown'),
                'outdoor_seating': tags.get('outdoor_seating', 'unknown'),
                'website': tags.get('website', tags.get('contact:website', '')),
                'phone': tags.get('phone', tags.get('contact:phone', ''))
            }
            
            restaurants.append(restaurant)
            
            if len(restaurants) >= limit:
                break
        
        print(f"✅ Successfully fetched {len(restaurants)} restaurants with Google images")
        return restaurants
        
    except Exception as e:
        print(f"❌ Error fetching restaurants: {str(e)}")
        return []