"""
Tourism places module
Handles fetching tourism data from MongoDB or OpenStreetMap
"""

import requests
import time
from typing import List, Dict
from db import get_tourism_from_db, save_tourism_to_db
from utils import get_location_coordinates, get_place_image, build_address

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
        
        # Query for tourism places
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["tourism"~"attraction|museum|gallery|artwork|viewpoint|monument|zoo|theme_park"](around:{radius},{lat},{lon});
          way["tourism"~"attraction|museum|gallery|artwork|viewpoint|monument|zoo|theme_park"](around:{radius},{lat},{lon});
          node["historic"~"castle|monument|memorial|archaeological_site"](around:{radius},{lat},{lon});
          way["historic"~"castle|monument|memorial|archaeological_site"](around:{radius},{lat},{lon});
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
        
        places = []
        seen_names = set()
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            name = tags.get('name', tags.get('tourism', tags.get('historic', 'Unnamed Place')))
            
            # Skip duplicates and unnamed places
            if name in seen_names or name == 'Unnamed Place':
                continue
            seen_names.add(name)
            
            # Get coordinates
            place_lat = element.get('lat', lat)
            place_lon = element.get('lon', lon)
            
            # Get image using Google Custom Search (free tier)
            image_url = await get_place_image(name, query)
            
            # Build description
            tourism_type = tags.get('tourism', tags.get('historic', 'attraction'))
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
            
            if len(places) >= limit:
                break
        
        return places
        
    except Exception as e:
        print(f"Error fetching tourism places: {str(e)}")
        return []