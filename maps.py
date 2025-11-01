"""
Maps module - Self-contained version
Generates interactive map HTML using Leaflet.js (OpenStreetMap)
No external dependencies on utils module
"""

from typing import Dict, List, Optional
import aiohttp

async def get_location_coordinates(location: str) -> Optional[Dict]:
    """
    Get coordinates using OpenStreetMap Nominatim API
    
    Args:
        location: Location name or address
    
    Returns:
        Dict with lat, lon, display_name, or None if not found
    """
    try:
        # OpenStreetMap Nominatim API for geocoding
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': location,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'WanderEase/1.0 (Travel Application)'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        result = data[0]
                        return {
                            'lat': float(result['lat']),
                            'lon': float(result['lon']),
                            'display_name': result.get('display_name', location),
                            'address': result.get('address', {}),
                            'boundingbox': result.get('boundingbox', [])
                        }
        return None
    except Exception as e:
        print(f"Error getting coordinates from Nominatim: {str(e)}")
        return None

async def generate_map_image(location: str, markers: Optional[str] = None, 
                            show_nearby: Optional[str] = None) -> Dict:
    """
    Generate an interactive map HTML with markers using OpenStreetMap
    
    Args:
        location: Location name or address
        markers: Comma-separated lat,lon pairs (e.g., "28.6139,77.2090,28.7041,77.1025")
        show_nearby: Type of nearby places to show (tourism, restaurant, hotel) - NOT IMPLEMENTED YET
    
    Returns:
        Dict with HTML map and center coordinates
    """
    try:
        # Get center coordinates using OpenStreetMap Nominatim
        print(f"Fetching coordinates for location: {location}")
        loc = await get_location_coordinates(location)
        
        if not loc:
            raise Exception(f"Location '{location}' not found in OpenStreetMap Nominatim")
        
        center_lat = loc['lat']
        center_lon = loc['lon']
        display_name = loc.get('display_name', location)
        
        print(f"Found coordinates: {center_lat}, {center_lon}")
        print(f"Display name: {display_name}")
        
        # Parse marker coordinates if provided
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
                        'name': f'Marker {len(marker_list) + 1}'
                    })
                    print(f"Added marker: {lat}, {lon}")
                except (ValueError, IndexError) as e:
                    print(f"Error parsing marker at index {i}: {e}")
                    continue
        
        # Generate interactive map HTML
        map_html = generate_leaflet_map(
            center_lat, center_lon, 
            display_name, 
            marker_list,
            loc.get('boundingbox', [])
        )
        
        return {
            "map_html": map_html,
            "center": {
                "lat": center_lat,
                "lon": center_lon,
                "display_name": display_name
            },
            "markers": marker_list
        }
        
    except Exception as e:
        print(f"Error generating map: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def generate_leaflet_map(lat: float, lon: float, location_name: str, 
                         markers: List[Dict], boundingbox: List = None) -> str:
    """
    Generate interactive Leaflet.js map HTML with OpenStreetMap tiles
    """
    
    # Build custom markers JavaScript
    markers_js = ""
    for i, marker in enumerate(markers):
        markers_js += f"""
        L.marker([{marker['lat']}, {marker['lon']}], {{
            icon: L.divIcon({{
                className: 'custom-marker',
                html: '<div style="background: #2196F3; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-size: 14px;">{i+1}</div>',
                iconSize: [32, 32]
            }})
        }}).addTo(map).bindPopup('<strong>{marker.get("name", f"Marker {i+1}")}</strong><br>Lat: {marker["lat"]:.4f}<br>Lon: {marker["lon"]:.4f}');
        """
    
    # Main marker at center
    center_marker = f"""
    L.marker([{lat}, {lon}], {{
        icon: L.divIcon({{
            className: 'custom-marker',
            html: '<div style="background: #E91E63; color: white; width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 26px; border: 4px solid white; box-shadow: 0 3px 8px rgba(0,0,0,0.4);">📍</div>',
            iconSize: [44, 44]
        }})
    }}).addTo(map).bindPopup('<div style="min-width: 200px;"><strong style="font-size: 16px;">{location_name}</strong><br><br>📍 Lat: {lat:.4f}<br>📍 Lon: {lon:.4f}</div>');
    """
    
    # Escape location name for JavaScript
    js_location_name = location_name.replace("'", "\\'").replace('"', '\\"')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenStreetMap - {location_name}</title>
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
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.25);
            max-width: 320px;
            backdrop-filter: blur(10px);
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
            background: rgba(255,255,255,0.9);
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
    </style>
</head>
<body>
    <div class="map-controls">
        <h3>🗺️ Location Details</h3>
        <p><strong>Location:</strong><br>{js_location_name[:60] + '...' if len(js_location_name) > 60 else js_location_name}</p>
        <p><strong>Data Source:</strong> OpenStreetMap</p>
        <p><strong>Coordinates:</strong><br>Lat: {lat:.6f}<br>Lon: {lon:.6f}</p>
        <p><strong>Markers:</strong> {len(markers) + 1} total</p>
        
        <div class="info-section">
            🔍 Scroll to zoom<br>
            🖱️ Drag to pan<br>
            📍 Click markers for details
        </div>
    </div>
    
    <div id="map"></div>
    
    <div class="zoom-info">
        <strong>Zoom Level:</strong> <span id="zoom-level">13</span>
    </div>
    
    <div class="attribution">
        Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""></script>
    <script>
        console.log('Initializing OpenStreetMap...');
        
        // Initialize map with OpenStreetMap tiles
        var map = L.map('map').setView([{lat}, {lon}], 13);
        
        console.log('Map created, adding tile layer...');

        // Add OpenStreetMap tiles (Standard layer)
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19,
            minZoom: 2
        }}).addTo(map);
        
        console.log('Tile layer added, adding markers...');

        // Add center marker
        {center_marker}
        
        console.log('Center marker added');

        // Add custom markers
        {markers_js if markers_js else '// No additional markers'}
        
        console.log('Custom markers added: {len(markers)}');

        // Fit bounds to show all markers
        var bounds = L.latLngBounds();
        bounds.extend([{lat}, {lon}]);
        
        {f'''
        {"".join([f"bounds.extend([{m['lat']}, {m['lon']}]);" for m in markers])}
        ''' if markers else ''}
        
        if ({len(markers)} > 0) {{
            map.fitBounds(bounds, {{padding: [80, 80]}});
            console.log('Map bounds fitted to include all markers');
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
        
        console.log('Map initialization complete!');
        
        // Log map info
        console.log('Center:', map.getCenter());
        console.log('Zoom:', map.getZoom());
    </script>
</body>
</html>"""
    
    return html