"""
Hotels module
Handles fetching hotel data from MongoDB or OpenStreetMap
Now with Google Custom Search API for real images
"""

import requests
from typing import List, Dict, Optional
from db import get_hotels_from_db, save_hotels_to_db
from utils import get_location_coordinates, build_address, fetch_google_image

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
        
        # Query for hotels
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["tourism"~"hotel|motel|hostel|guest_house|apartment|chalet|resort"](around:{radius},{lat},{lon});
          way["tourism"~"hotel|motel|hostel|guest_house|apartment|chalet|resort"](around:{radius},{lat},{lon});
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
        
        hotels = []
        seen_names = set()
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            name = tags.get('name', 'Unnamed Hotel')
            
            # Skip duplicates and unnamed
            if name in seen_names or name == 'Unnamed Hotel':
                continue
            seen_names.add(name)
            
            # Get coordinates
            place_lat = element.get('lat', lat)
            place_lon = element.get('lon', lon)
            
            # Fetch real image from Google Custom Search
            print(f"🔍 Fetching image for hotel: {name}")
            image_url = await fetch_google_image(f"{name} hotel", query)
            
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
            if tags.get('internet_access') == 'yes' or tags.get('internet_access') == 'wlan':
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
            
            if len(hotels) >= limit:
                break
        
        print(f"✅ Successfully fetched {len(hotels)} hotels with Google images")
        return hotels
        
    except Exception as e:
        print(f"❌ Error fetching hotels: {str(e)}")
        return []