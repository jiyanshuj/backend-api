"""
Utility functions for location, images, and helpers
Now with integrated Google Custom Search API
"""

import requests
import time
import os
from typing import Dict, Optional

# Google Custom Search API credentials
GOOGLE_API_KEY = "AIzaSyCLqG3mulQb5YHtWCQyDm6yyutxbsr5g2g"
GOOGLE_SEARCH_ENGINE_ID = "f28e39dbb2a6b418e"

# Gemini API Key (for future use)
GEMINI_API_KEY = "AIzaSyDW4lWmREnqeVcHXrpfogMRMRcUNHCjZd4"

def get_location_coordinates(query: str) -> Optional[Dict]:
    """
    Get location coordinates using LocationIQ (more reliable than Nominatim)
    """
    try:
        url = "https://us1.locationiq.com/v1/search"
        params = {
            'key': 'pk.aa244b676b5add11553e0e269d464ba9',
            'q': query,
            'format': 'json',
            'limit': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"No location found for: {query}")
            return None
        
        location_info = {
            'lat': float(data[0]['lat']),
            'lon': float(data[0]['lon']),
            'name': data[0]['display_name']
        }
        
        print(f"✅ Found location: {location_info['name']}")
        return location_info
        
    except Exception as e:
        print(f"❌ Error getting location: {str(e)}")
        return None

async def fetch_google_image(place_name: str, location_context: str = "") -> str:
    """
    Fetch real images using Google Custom Search API
    
    Args:
        place_name: Name of the place (hotel, restaurant, tourism spot)
        location_context: Location for better search results
    
    Returns:
        Image URL from Google or placeholder if not found
    """
    try:
        # Construct optimized search query
        search_query = f"{place_name} {location_context}".strip()
        
        # Google Custom Search API endpoint
        url = "https://www.googleapis.com/customsearch/v1"
        
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': search_query,
            'searchType': 'image',
            'num': 1,  # Get only the best result
            'imgSize': 'large',
            'safe': 'active',
            'fileType': 'jpg,png'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items and 'link' in items[0]:
                image_url = items[0]['link']
                print(f"✅ Found image: {image_url[:80]}...")
                return image_url
            else:
                print(f"⚠️ No image found in Google results for: {place_name}")
        else:
            print(f"⚠️ Google API error: {response.status_code}")
            if response.status_code == 429:
                print("⚠️ Rate limit reached! Consider caching images in MongoDB")
        
        # Fallback to Wikimedia
        return await get_wikimedia_image(place_name)
        
    except Exception as e:
        print(f"❌ Error fetching Google image: {str(e)}")
        return await get_placeholder_image(place_name)

async def get_wikimedia_image(place_name: str) -> str:
    """
    Fallback: Try to get image from Wikimedia Commons (free)
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
                print(f"✅ Found Wikimedia image for: {place_name}")
                return imageinfo[0]['thumburl']
        
        return await get_placeholder_image(place_name)
        
    except Exception as e:
        print(f"⚠️ Wikimedia search failed: {str(e)}")
        return await get_placeholder_image(place_name)

async def get_placeholder_image(place_name: str) -> str:
    """
    Generate placeholder image URL with better styling
    """
    # Use placeholder.com with custom styling
    encoded_name = place_name.replace(' ', '+')
    return f"https://via.placeholder.com/800x600/667eea/ffffff?text={encoded_name}"

# Legacy function for backward compatibility
async def get_place_image(place_name: str, location_context: str = "") -> str:
    """
    Legacy wrapper - now uses Google Custom Search
    """
    return await fetch_google_image(place_name, location_context)

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