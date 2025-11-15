"""
Hotels module with timeout fixes and retry logic
Handles fetching hotel data from MongoDB or OpenStreetMap
Now with Google Custom Search API for real images
"""

import requests
from typing import List, Dict, Optional
import time
from db import get_hotels_from_db, save_hotels_to_db
from utils import get_location_coordinates, build_address, fetch_google_image

# Multiple Overpass API servers (fallback if one is down)
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

async def get_hotels(location: str, limit: int = 20) -> List[Dict]:
    """
    Get hotels for a location
    1. First check MongoDB
    2. If not found or insufficient, fetch from OpenStreetMap
    3. Save to MongoDB for future queries
    """
    # Check MongoDB first
    hotels = get_hotels_from_db(location, limit)
    
    if hotels and len(hotels) >= limit:
        print(f"Found {len(hotels)} hotels in MongoDB for {location}")
        return hotels
    
    # Fetch from OpenStreetMap
    print(f"Fetching hotels from OpenStreetMap for {location}")
    hotels = await fetch_hotels_from_osm(location, limit)
    
    # Save to MongoDB
    if hotels:
        save_hotels_to_db(hotels, location)
    
    return hotels

async def fetch_hotels_from_osm(query: str, limit: int = 20) -> List[Dict]:
    """
    Fetch hotels from OpenStreetMap using Overpass API
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
        
        # Search radius (5km for better performance)
        radius = 50000
        
        # Simplified query for faster response
        overpass_query = f"""
        [out:json][timeout:90];
        (
          node["tourism"~"hotel|guest_house"](around:{radius},{lat},{lon});
          way["tourism"~"hotel|guest_house"](around:{radius},{lat},{lon});
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
                
                # Wait a bit before trying next server
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
        hotels = []
        seen_names = set()
        
        for element in data.get('elements', []):
            if len(hotels) >= limit:
                break
                
            tags = element.get('tags', {})
            name = tags.get('name', 'Unnamed Hotel')
            
            # Skip duplicates and unnamed
            if name in seen_names or name == 'Unnamed Hotel':
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
            
            # Fetch real image from Google Custom Search
            print(f"🖼️ Fetching image for hotel: {name}")
            try:
                image_url = await fetch_google_image(f"{name} hotel", query)
            except Exception as img_error:
                print(f"⚠️ Image fetch failed for {name}: {img_error}")
                image_url = None
            
            # Get hotel type
            hotel_type = tags.get('tourism', 'hotel')
            
            # Estimate stars
            stars = tags.get('stars', '3')
            try:
                star_count = int(stars)
            except:
                star_count = 3
            
            # Calculate price based on stars and location
            base_price = 1000
            price_per_night = base_price + (star_count * 1000) + (hash(name) % 500)
            
            # Get amenities
            amenities = []
            if tags.get('internet_access') in ['yes', 'wlan', 'wifi']:
                amenities.append('WiFi')
            if tags.get('swimming_pool') == 'yes':
                amenities.append('Pool')
            if tags.get('restaurant') == 'yes':
                amenities.append('Restaurant')
            if tags.get('bar') == 'yes':
                amenities.append('Bar')
            if tags.get('parking') == 'yes':
                amenities.append('Parking')
            if tags.get('air_conditioning') == 'yes':
                amenities.append('AC')
            
            hotel = {
                'hotel_id': f"H{element.get('id', 0)}",
                'name': name,
                'type': hotel_type.replace('_', ' ').title(),
                'stars': star_count,
                'location': {
                    'type': 'Point',
                    'coordinates': [place_lon, place_lat]
                },
                'lat': place_lat,
                'lon': place_lon,
                'image_url': image_url,
                'address': build_address(tags),
                'price_per_night': price_per_night,
                'rating': 3.0 + (star_count * 0.3) + (hash(name) % 10) / 10,
                'amenities': amenities,
                'rooms': tags.get('rooms', 'Not specified'),
                'opening_hours': tags.get('opening_hours', '24/7'),
                'website': tags.get('website', tags.get('contact:website', '')),
                'phone': tags.get('phone', tags.get('contact:phone', '')),
                'email': tags.get('email', tags.get('contact:email', ''))
            }
            
            hotels.append(hotel)
            print(f"🏨 Added: {name} ({star_count}⭐)")
        
        print(f"✅ Successfully fetched {len(hotels)} hotels")
        return hotels
        
    except Exception as e:
        print(f"❌ Error fetching hotels: {str(e)}")
        import traceback
        traceback.print_exc()
        return []