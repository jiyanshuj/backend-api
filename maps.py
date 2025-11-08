"""
Enhanced Maps Module - With Improved Geoapify API Integration
Generates interactive map HTML using Leaflet.js with Geoapify tiles
Includes enhanced location accuracy with bias parameters
"""

from typing import Dict, List, Optional
import aiohttp
import json

# Geoapify API Key
GEOAPIFY_API_KEY = "872520433e264a4ea93c5e7f5db329a5"


async def get_location_coordinates(location: str, bias_country: Optional[str] = None) -> Optional[Dict]:
    """
    Get coordinates using Geoapify Geocoding API with enhanced accuracy
    
    Args:
        location: Location name or address
        bias_country: Optional country code to bias results (e.g., 'in' for India)
    
    Returns:
        Dict with lat, lon, display_name, or None if not found
    """
    try:
        # Geoapify Geocoding API with enhanced parameters
        url = "https://api.geoapify.com/v1/geocode/search"
        params = {
            'text': location,
            'format': 'json',
            'limit': 5,  # Get multiple results to choose best match
            'apiKey': GEOAPIFY_API_KEY
        }
        
        # Add bias parameters for better accuracy
        # Remove default auto-detection and let user location be prioritized
        if bias_country:
            params['filter'] = f'countrycode:{bias_country}'
        else:
            # Set bias to none to avoid auto country detection issues
            params['bias'] = 'countrycode:none'
        
        print(f"Geocoding request for: {location}")
        print(f"Parameters: {params}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
                    
                    if results and len(results) > 0:
                        # Log all results for debugging
                        print(f"Found {len(results)} results:")
                        for i, result in enumerate(results):
                            formatted = result.get('formatted', 'N/A')
                            rank = result.get('rank', {}).get('popularity', 0)
                            confidence = result.get('rank', {}).get('confidence', 0)
                            print(f"  {i+1}. {formatted}")
                            print(f"      Rank: {rank}, Confidence: {confidence}")
                            print(f"      Lat: {result.get('lat')}, Lon: {result.get('lon')}")
                        
                        # Smart result selection - prioritize more specific matches
                        best_result = results[0]  # Default to first
                        
                        # Search for the most specific match (contains more location keywords)
                        location_keywords = location.lower().split(',')
                        location_keywords = [k.strip() for k in location_keywords]
                        
                        max_matches = 0
                        for result in results:
                            formatted_lower = result.get('formatted', '').lower()
                            city = result.get('city', '').lower()
                            state = result.get('state', '').lower()
                            
                            # Count how many keywords from query appear in this result
                            matches = 0
                            for keyword in location_keywords:
                                if keyword in formatted_lower or keyword in city or keyword in state:
                                    matches += 1
                            
                            # Bonus for having "City" or specific district in the name
                            if 'city' in formatted_lower or 'district' in formatted_lower:
                                matches += 0.5
                            
                            # Prefer results with lower rank (more popular) as tiebreaker
                            rank_penalty = result.get('rank', {}).get('popularity', 1)
                            
                            # Calculate score (higher is better)
                            score = matches - (rank_penalty * 0.1)
                            
                            if score > max_matches:
                                max_matches = score
                                best_result = result
                        
                        result = best_result
                        print(f"\n✅ Best match selected: {result.get('formatted', 'N/A')}")
                        
                        coords = {
                            'lat': result['lat'],
                            'lon': result['lon'],
                            'display_name': result.get('formatted', location),
                            'address': result,
                            'boundingbox': [
                                result.get('bbox', {}).get('lat1'),
                                result.get('bbox', {}).get('lat2'),
                                result.get('bbox', {}).get('lon1'),
                                result.get('bbox', {}).get('lon2')
                            ]
                        }
                        
                        print(f"Selected location: {coords['display_name']}")
                        print(f"Coordinates: {coords['lat']}, {coords['lon']}")
                        
                        return coords
                else:
                    print(f"Geocoding API error: {response.status}")
        
        return None
    except Exception as e:
        print(f"Error getting coordinates from Geoapify: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def get_nearby_places(lat: float, lon: float, place_type: str, 
                           radius: int = 1000, limit: int = 20) -> List[Dict]:
    """
    Fetch nearby places using Geoapify Places API
    
    Args:
        lat: Latitude of center point
        lon: Longitude of center point
        place_type: Type of place (tourism, restaurant, hotel, cafe)
        radius: Search radius in meters (default 1000m = 1km)
        limit: Maximum number of results
    
    Returns:
        List of place dictionaries with name, lat, lon, type
    """
    try:
        # Map place types to Geoapify categories
        type_mapping = {
            'tourism': 'tourism.attraction,tourism.sights',
            'restaurant': 'catering.restaurant',
            'hotel': 'accommodation.hotel',
            'cafe': 'catering.cafe'
        }
        
        if place_type not in type_mapping:
            print(f"Unknown place type: {place_type}")
            return []
        
        categories = type_mapping[place_type]
        
        # Geoapify Places API
        url = "https://api.geoapify.com/v2/places"
        params = {
            'categories': categories,
            'filter': f'circle:{lon},{lat},{radius}',
            'limit': limit,
            'apiKey': GEOAPIFY_API_KEY
        }
        
        print(f"Fetching nearby {place_type} within {radius}m at ({lat}, {lon})...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    places = []
                    
                    for feature in data.get('features', []):
                        properties = feature.get('properties', {})
                        coordinates = feature.get('geometry', {}).get('coordinates', [])
                        
                        if len(coordinates) >= 2:
                            place_lon, place_lat = coordinates[0], coordinates[1]
                            
                            name = properties.get('name') or properties.get('address_line1', f'Unnamed {place_type}')
                            
                            places.append({
                                'name': name,
                                'lat': place_lat,
                                'lon': place_lon,
                                'type': place_type,
                                'tags': properties
                            })
                    
                    print(f"Found {len(places)} nearby {place_type}")
                    return places[:limit]
                else:
                    print(f"Places API error: {response.status}")
        
        return []
    except Exception as e:
        print(f"Error fetching nearby places from Geoapify: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def generate_map_image(location: str, markers: Optional[str] = None, 
                            show_nearby: Optional[str] = None,
                            nearby_radius: int = 1000,
                            nearby_limit: int = 20,
                            bias_country: Optional[str] = None) -> Dict:
    """
    Generate an interactive map HTML with markers using Geoapify
    
    Args:
        location: Location name or address
        markers: Comma-separated lat,lon pairs (e.g., "28.6139,77.2090,28.7041,77.1025")
        show_nearby: Type of nearby places to show (tourism, restaurant, hotel, cafe)
        nearby_radius: Search radius for nearby places in meters (default 1000)
        nearby_limit: Max number of nearby places to show (default 20)
        bias_country: Optional ISO country code to bias results (e.g., 'in' for India)
    
    Returns:
        Dict with HTML map and center coordinates
    """
    try:
        # Auto-detect country bias from location if it contains country indicators
        detected_country = None
        location_lower = location.lower()
        
        # Common country detection patterns
        country_patterns = {
            'in': ['india', 'indore', 'mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai'],
            'us': ['usa', 'united states', 'new york', 'los angeles', 'chicago'],
            'fr': ['france', 'paris', 'lyon', 'marseille'],
            'gb': ['uk', 'united kingdom', 'london', 'manchester'],
            'de': ['germany', 'berlin', 'munich', 'hamburg'],
            'jp': ['japan', 'tokyo', 'osaka', 'kyoto'],
            'cn': ['china', 'beijing', 'shanghai', 'guangzhou'],
        }
        
        for country_code, keywords in country_patterns.items():
            if any(keyword in location_lower for keyword in keywords):
                detected_country = country_code
                print(f"Detected country: {country_code} from location: {location}")
                break
        
        # Use provided bias or detected country
        final_bias = bias_country or detected_country
        
        # Get center coordinates using Geoapify Geocoding with bias
        print(f"Fetching coordinates for location: {location}")
        loc = await get_location_coordinates(location, final_bias)
        
        if not loc:
            raise Exception(f"Location '{location}' not found in Geoapify")
        
        center_lat = loc['lat']
        center_lon = loc['lon']
        display_name = loc.get('display_name', location)
        
        print(f"Found coordinates: {center_lat}, {center_lon}")
        print(f"Display name: {display_name}")
        
        # Parse custom marker coordinates if provided
        marker_list = []
        if markers:
            marker_pairs = markers.strip().split(',')
            print(f"Parsing {len(marker_pairs)} marker values")
            for i in range(0, len(marker_pairs) - 1, 2):
                try:
                    lat = float(marker_pairs[i].strip())
                    lon = float(marker_pairs[i + 1].strip())
                    marker_list.append({
                        'lat': lat, 
                        'lon': lon, 
                        'name': f'Marker {len(marker_list) + 1}',
                        'type': 'custom'
                    })
                    print(f"Added custom marker: {lat}, {lon}")
                except (ValueError, IndexError) as e:
                    print(f"Error parsing marker at index {i}: {e}")
                    continue
        
        # Fetch nearby places if requested
        nearby_places = []
        if show_nearby:
            nearby_places = await get_nearby_places(
                center_lat, center_lon, 
                show_nearby, 
                nearby_radius, 
                nearby_limit
            )
            marker_list.extend(nearby_places)
        
        # Generate interactive map HTML
        map_html = generate_leaflet_map(
            center_lat, center_lon, 
            display_name, 
            marker_list,
            loc.get('boundingbox', []),
            show_nearby
        )
        
        return {
            "map_html": map_html,
            "center": {
                "lat": center_lat,
                "lon": center_lon,
                "display_name": display_name
            },
            "markers": marker_list,
            "nearby_count": len(nearby_places) if show_nearby else 0
        }
        
    except Exception as e:
        print(f"Error generating map: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_leaflet_map(lat: float, lon: float, location_name: str, 
                         markers: List[Dict], boundingbox: List = None,
                         show_nearby: Optional[str] = None) -> str:
    """
    Generate interactive Leaflet.js map HTML with Geoapify tiles
    Supports different marker types with custom icons and colors
    """
    
    # Marker styling by type
    marker_styles = {
        'custom': {
            'icon': '📌',
            'color': '#2196F3',
            'number': True
        },
        'tourism': {
            'icon': '🏛️',
            'color': '#9C27B0',
            'number': False
        },
        'restaurant': {
            'icon': '🍽️',
            'color': '#FF5722',
            'number': False
        },
        'hotel': {
            'icon': '🏨',
            'color': '#00BCD4',
            'number': False
        },
        'cafe': {
            'icon': '☕',
            'color': '#8D6E63',
            'number': False
        }
    }
    
    # Build markers JavaScript grouped by type
    markers_by_type = {}
    for marker in markers:
        marker_type = marker.get('type', 'custom')
        if marker_type not in markers_by_type:
            markers_by_type[marker_type] = []
        markers_by_type[marker_type].append(marker)
    
    markers_js = ""
    marker_counter = 1
    
    for marker_type, type_markers in markers_by_type.items():
        style = marker_styles.get(marker_type, marker_styles['custom'])
        
        for marker in type_markers:
            marker_name = marker.get('name', f'Marker {marker_counter}')
            # Use HTML entities for escaping in template literals
            marker_name_escaped = marker_name.replace("'", "&#39;").replace('"', '&quot;').replace('`', '&#96;')
            
            if style['number'] and marker_type == 'custom':
                icon_html = f'{marker_counter}'
                marker_counter += 1
            else:
                icon_html = style['icon']
            
            markers_js += f"""
        L.marker([{marker['lat']}, {marker['lon']}], {{
            icon: L.divIcon({{
                className: 'custom-marker-{marker_type}',
                html: '<div style="background: {style["color"]}; color: white; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid white; box-shadow: 0 3px 8px rgba(0,0,0,0.35); font-size: {"14px" if style["number"] else "20px"};">{icon_html}</div>',
                iconSize: [36, 36]
            }})
        }}).addTo(map).bindPopup(`
            <div style="min-width: 180px;">
                <strong style="font-size: 15px;">{marker_name_escaped}</strong><br><br>
                <span style="background: {style["color"]}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{marker_type.upper()}</span><br><br>
                📍 {marker['lat']:.5f}, {marker['lon']:.5f}
            </div>
        `);
            """
    
    # Main marker at center (escape location name first)
    escaped_location = location_name.replace("'", "&#39;").replace('"', '&quot;')[:50]
    center_marker = f"""
    L.marker([{lat}, {lon}], {{
        icon: L.divIcon({{
            className: 'center-marker',
            html: '<div style="background: #E91E63; color: white; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; border: 4px solid white; box-shadow: 0 4px 12px rgba(233,30,99,0.5); animation: pulse 2s infinite;">📍</div>',
            iconSize: [48, 48]
        }})
    }}).addTo(map).bindPopup(`
        <div style="min-width: 220px;">
            <strong style="font-size: 17px; color: #E91E63;">📍 {escaped_location}</strong><br><br>
            <strong>Coordinates:</strong><br>
            Lat: {lat:.6f}<br>
            Lon: {lon:.6f}
        </div>
    `);
    """
    
    # JavaScript location name (truncated for display)
    js_location_name = location_name.replace("'", "&#39;").replace('"', '&quot;')
    display_location = js_location_name[:50] + ('...' if len(js_location_name) > 50 else '')
    
    # Marker statistics
    marker_stats = ""
    for marker_type, type_markers in markers_by_type.items():
        style = marker_styles.get(marker_type, marker_styles['custom'])
        marker_stats += f'<span style="background: {style["color"]}; color: white; padding: 4px 10px; border-radius: 6px; margin: 4px; display: inline-block; font-size: 0.85rem;">{style["icon"]} {marker_type.title()}: {len(type_markers)}</span>'
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Map - {location_name}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" 
          crossorigin=""/>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
        }}
        #map {{
            width: 100%;
            height: 100vh;
            background: #f0f0f0;
        }}
        .map-controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            max-width: 340px;
            backdrop-filter: blur(10px);
            max-height: 90vh;
            overflow-y: auto;
        }}
        .map-controls h3 {{
            margin-bottom: 15px;
            color: #667eea;
            font-size: 1.3rem;
            font-weight: 700;
        }}
        .map-controls p {{
            margin: 8px 0;
            font-size: 0.95rem;
            color: #555;
            line-height: 1.5;
        }}
        .map-controls strong {{
            color: #333;
        }}
        .marker-legend {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid #f0f0f0;
        }}
        .marker-legend h4 {{
            font-size: 1rem;
            color: #667eea;
            margin-bottom: 10px;
        }}
        .leaflet-popup-content {{
            font-size: 14px;
            line-height: 1.8;
        }}
        .zoom-info {{
            position: absolute;
            bottom: 35px;
            left: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 18px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            font-size: 0.9rem;
            color: #333;
            font-weight: 600;
        }}
        .attribution {{
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255,255,255,0.95);
            padding: 8px 15px;
            font-size: 0.85rem;
            z-index: 999;
            border-radius: 8px 8px 0 0;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.1);
        }}
        .attribution a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }}
        .attribution a:hover {{
            text-decoration: underline;
        }}
        .info-section {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid #f0f0f0;
            font-size: 0.85rem;
            color: #888;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}
    </style>
</head>
<body>
    <div class="map-controls">
        <h3>🗺️ Location Details</h3>
        <p><strong>Location:</strong><br>{display_location}</p>
        <p><strong>Data Source:</strong> Geoapify</p>
        <p><strong>Coordinates:</strong><br>Lat: {lat:.6f}<br>Lon: {lon:.6f}</p>
        <p><strong>Total Markers:</strong> {len(markers) + 1}</p>
        
        {"<p><strong>Showing Nearby:</strong> " + show_nearby.title() + "</p>" if show_nearby else ""}
        
        <div class="marker-legend">
            <h4>📍 Marker Types</h4>
            {marker_stats}
        </div>
        
        <div class="info-section">
            🔍 Scroll to zoom<br>
            🖱️ Drag to pan<br>
            📍 Click markers for details
        </div>
    </div>
    
    <div id="map"></div>
    
    <div class="zoom-info">
        <strong>Zoom:</strong> <span id="zoom-level">13</span>
    </div>
    
    <div class="attribution">
        Powered by <a href="https://www.geoapify.com/" target="_blank">Geoapify</a>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""></script>
    <script>
        console.log('🗺️ Initializing Geoapify Map...');
        
        var map = L.map('map').setView([{lat}, {lon}], 13);
        
        // Geoapify Map Tiles - Multiple styles available
        L.tileLayer('https://maps.geoapify.com/v1/tile/osm-bright/{{z}}/{{x}}/{{y}}.png?apiKey={GEOAPIFY_API_KEY}', {{
            attribution: 'Powered by <a href="https://www.geoapify.com/" target="_blank">Geoapify</a> | © OpenStreetMap contributors',
            maxZoom: 20,
            minZoom: 2
        }}).addTo(map);
        
        console.log('✅ Geoapify tile layer loaded');

        // Add center marker with pulse animation
        {center_marker}
        
        console.log('✅ Center marker added');

        // Add all categorized markers
        {markers_js if markers_js else '// No additional markers'}
        
        console.log('✅ Added {len(markers)} markers');

        // Fit bounds to show all markers
        var bounds = L.latLngBounds();
        bounds.extend([{lat}, {lon}]);
        
        {f'''
        {"".join([f"bounds.extend([{m['lat']}, {m['lon']}]);" for m in markers])}
        ''' if markers else ''}
        
        if ({len(markers)} > 0) {{
            map.fitBounds(bounds, {{padding: [100, 100]}});
            console.log('✅ Map bounds fitted');
        }}

        // Update zoom level display
        map.on('zoomend', function() {{
            document.getElementById('zoom-level').textContent = map.getZoom();
        }});

        // Add scale control
        L.control.scale({{
            imperial: false,
            metric: true,
            position: 'bottomleft'
        }}).addTo(map);
        
        console.log('🎉 Map initialization complete!');
        console.log('Center:', map.getCenter());
        console.log('Zoom:', map.getZoom());
        console.log('Total markers:', {len(markers) + 1});
    </script>
</body>
</html>"""
    
    return html