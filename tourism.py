"""
Tourism places module with timeout fixes and retry logic
Handles fetching tourism data from MongoDB or OpenStreetMap
Now with Google Custom Search API for real images
"""

import requests
import time
from typing import List, Dict
from db import get_tourism_from_db, save_tourism_to_db
from utils import get_location_coordinates, build_address, fetch_google_image

# Multiple Overpass API servers (fallback if one is down)
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

async def get_tourism_places(location: str, limit: int = 20) -> List[Dict]:
    """
    Get tourism places for a location
    1. First check MongoDB
    2. If not found or insufficient, fetch from OpenStreetMap
    3. Save to MongoDB for future queries
    """
    # Check MongoDB first
    places = get_tourism_from_db(location, limit)
    
    if places and len(places) >= limit:
        print(f"Found {len(places)} tourism places in MongoDB for {location}")
        return places
    
    # Fetch from OpenStreetMap
    print(f"Fetching tourism places from OpenStreetMap for {location}")
    places = await fetch_tourism_from_osm(location, limit)
    
    # Save to MongoDB
    if places:
        save_tourism_to_db(places, location)
    
    return places

async def fetch_tourism_from_osm(query: str, limit: int = 20) -> List[Dict]:
    """
    Fetch tourism places from OpenStreetMap using Overpass API
    Enhanced with retry logic and multiple servers
    """
    try:
        # Get location coordinates
        location = get_location_coordinates(query)
        if not location:
            print(f"❌ Could not geocode location: {query}")
            return []
        
        lat = location['lat']
        lon = location['lon']
        print(f"📍 Coordinates for {query}: {lat}, {lon}")
        
        # Search radius (5km)
        radius = 50000
        
        # Simplified query for faster response
        overpass_query = f"""
        [out:json][timeout:90];
        (
          node["tourism"~"attraction|museum|gallery|viewpoint|monument"](around:{radius},{lat},{lon});
          way["tourism"~"attraction|museum|gallery|viewpoint|monument"](around:{radius},{lat},{lon});
          node["historic"~"castle|monument|memorial"](around:{radius},{lat},{lon});
          way["historic"~"castle|monument|memorial"](around:{radius},{lat},{lon});
        );
        out center {limit * 2};
        """
        
        # Try each server until one works
        data = None
        last_error = None
        
        for server_idx, overpass_url in enumerate(OVERPASS_SERVERS):
            try:
                print(f"🔄 Attempt {server_idx + 1}/{len(OVERPASS_SERVERS)}: Trying {overpass_url}")
                
                response = requests.post(
                    overpass_url,
                    data={'data': overpass_query},
                    timeout=90,  # Increased to 90 seconds
                    headers={'User-Agent': 'WanderEase/2.0'}
                )
                response.raise_for_status()
                data = response.json()
                
                print(f"✅ Successfully got response from {overpass_url}")
                break  # Success! Exit retry loop
                
            except requests.exceptions.Timeout:
                last_error = "Timeout"
                print(f"⏱️ Timeout on {overpass_url} after 90s")
                
                # Wait before trying next server
                if server_idx < len(OVERPASS_SERVERS) - 1:
                    time.sleep(2)
                continue
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                print(f"⚠️ Error with {overpass_url}: {e}")
                
                # Wait before trying next server
                if server_idx < len(OVERPASS_SERVERS) - 1:
                    time.sleep(2)
                continue
        
        # If all servers failed
        if data is None:
            print(f"❌ All Overpass servers failed. Last error: {last_error}")
            print("💡 Tip: The Overpass API might be overloaded. Try again in a few minutes.")
            return []
        
        # Process results
        places = []
        seen_names = set()
        
        for element in data.get('elements', []):
            if len(places) >= limit:
                break
                
            tags = element.get('tags', {})
            name = tags.get('name', tags.get('tourism', tags.get('historic', 'Unnamed Place')))
            
            # Skip duplicates and unnamed places
            if name in seen_names or name == 'Unnamed Place':
                continue
            seen_names.add(name)
            
            # Get coordinates
            if element.get('type') == 'node':
                place_lat = element.get('lat', lat)
                place_lon = element.get('lon', lon)
            else:
                # For ways, use center
                center = element.get('center', {})
                place_lat = center.get('lat', lat)
                place_lon = center.get('lon', lon)
            
            # Build tourism type
            tourism_type = tags.get('tourism', tags.get('historic', 'attraction'))
            
            # Fetch real image from Google Custom Search
            print(f"🖼️ Fetching image for tourism place: {name}")
            try:
                image_url = await fetch_google_image(f"{name} {tourism_type}", query)
            except Exception as img_error:
                print(f"⚠️ Image fetch failed for {name}: {img_error}")
                image_url = None
            
            # Build description
            description = tags.get('description', f"{tourism_type.replace('_', ' ').title()}")
            
            place = {
                'place_id': f"T{element.get('id', 0)}",
                'name': name,
                'description': description,
                'type': tourism_type,
                'location': {
                    'type': 'Point',
                    'coordinates': [place_lon, place_lat]
                },
                'lat': place_lat,
                'lon': place_lon,
                'image_url': image_url,
                'address': build_address(tags),
                'rating': 4.0 + (hash(name) % 10) / 10,
                'opening_hours': tags.get('opening_hours', 'Not available'),
                'website': tags.get('website', tags.get('contact:website', '')),
                'phone': tags.get('phone', tags.get('contact:phone', ''))
            }
            
            places.append(place)
            print(f"🏛️ Added: {name} ({tourism_type})")
        
        print(f"✅ Successfully fetched {len(places)} tourism places")
        return places
        
    except Exception as e:
        print(f"❌ Error fetching tourism places: {str(e)}")
        import traceback
        traceback.print_exc()
        return []