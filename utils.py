"""
Utility functions for location, images, and helpers
"""

import requests
import time
import os
from typing import Dict, Optional

# Google Custom Search API credentials (Free tier: 100 queries/day)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

def get_location_coordinates(query: str) -> Optional[Dict]:
    """
    Get location coordinates from query using Nominatim (OpenStreetMap)
    Free and no API key required
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'WanderEase/1.0 (wanderease@example.com)'
        }
        
        # Rate limiting - be nice to Nominatim
        time.sleep(1)
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None
        
        return {
            'lat': float(data[0]['lat']),
            'lon': float(data[0]['lon']),
            'name': data[0]['display_name']
        }
        
    except Exception as e:
        print(f"Error getting location: {str(e)}")
        return None

async def get_place_image(place_name: str, location_context: str = "") -> str:
    """
    Get place image using Google Custom Search API (free tier)
    Falls back to placeholder if not available
    
    Args:
        place_name: Name of the place
        location_context: Additional location context for better results
    
    Returns:
        Image URL
    """
    try:
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            return await get_placeholder_image(place_name)
        
        # Build search query
        search_query = f"{place_name} {location_context}".strip()
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_CSE_ID,
            'q': search_query,
            'searchType': 'image',
            'num': 1,
            'imgSize': 'large',
            'safe': 'active'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items and 'link' in items[0]:
                return items[0]['link']
        
        # Fallback to Wikimedia if Google fails
        return await get_wikimedia_image(place_name)
        
    except Exception as e:
        print(f"Error getting place image: {str(e)}")
        return await get_placeholder_image(place_name)

async def get_wikimedia_image(place_name: str) -> str:
    """
    Try to get image from Wikimedia Commons (free)
    """
    try:
        # Search Wikimedia Commons
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'search',
            'gsrsearch': place_name,
            'gsrlimit': 1,
            'prop': 'imageinfo',
            'iiprop': 'url',
            'iiurlwidth': 800
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        pages = data.get('query', {}).get('pages', {})
        if pages:
            page = next(iter(pages.values()))
            imageinfo = page.get('imageinfo', [])
            if imageinfo and 'thumburl' in imageinfo[0]:
                return imageinfo[0]['thumburl']
        
        return await get_placeholder_image(place_name)
        
    except Exception as e:
        print(f"Error getting Wikimedia image: {str(e)}")
        return await get_placeholder_image(place_name)

async def get_placeholder_image(place_name: str) -> str:
    """
    Generate placeholder image URL
    """
    # Use placeholder.com or similar service
    encoded_name = place_name.replace(' ', '+')
    return f"https://via.placeholder.com/800x600.png?text={encoded_name}"

def build_address(tags: Dict) -> str:
    """
    Build address string from OpenStreetMap tags
    """
    parts = []
    
    # House number and street
    if 'addr:housenumber' in tags:
        parts.append(tags['addr:housenumber'])
    if 'addr:street' in tags:
        parts.append(tags['addr:street'])
    
    # City/Town
    if 'addr:city' in tags:
        parts.append(tags['addr:city'])
    elif 'addr:town' in tags:
        parts.append(tags['addr:town'])
    elif 'addr:village' in tags:
        parts.append(tags['addr:village'])
    
    # State/Province
    if 'addr:state' in tags:
        parts.append(tags['addr:state'])
    elif 'addr:province' in tags:
        parts.append(tags['addr:province'])
    
    # Postal code
    if 'addr:postcode' in tags:
        parts.append(tags['addr:postcode'])
    
    # Country
    if 'addr:country' in tags:
        parts.append(tags['addr:country'])
    
    return ', '.join(parts) if parts else 'Address not available'

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates in kilometers
    Using Haversine formula
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance