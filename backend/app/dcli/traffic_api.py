import os
import requests
import logging

logger = logging.getLogger(__name__)

class TrafficAPIIntegration:
    """
    Real-Time Traffic & Map API Integration.
    Solves the 'synthetic data' problem by pulling real road characteristics
    and live traffic speeds.
    """
    def __init__(self):
        # TomTom Traffic API (Requires Key)
        self.tomtom_api_key = os.getenv("TOMTOM_API_KEY")
        # Overpass API (OpenStreetMap) - 100% Free & Open Source
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Cache to prevent spamming the free OSM API
        self._osm_cache = {}

    def get_real_road_data(self, lat: float, lng: float) -> dict:
        """
        Fetch REAL road data from OpenStreetMap for the exact violation coordinates.
        Returns road type, speed limit, and lane count.
        """
        cache_key = f"{round(lat, 3)}_{round(lng, 3)}"
        if cache_key in self._osm_cache:
            return self._osm_cache[cache_key]

        query = f"""
        [out:json];
        way(around:50,{lat},{lng})[highway];
        out tags;
        """
        try:
            response = requests.get(self.overpass_url, params={'data': query}, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('elements'):
                    tags = data['elements'][0].get('tags', {})
                    road_data = {
                        "highway": tags.get("highway", "unclassified"),
                        "lanes": int(tags.get("lanes", 2)),
                        "maxspeed": int(tags.get("maxspeed", 40)),
                        "name": tags.get("name", "Unknown Road"),
                    }
                    self._osm_cache[cache_key] = road_data
                    return road_data
        except Exception as e:
            logger.warning(f"OSM API fallback used: {e}")
            pass

        # Fallback if OSM fails or times out
        return {"highway": "unclassified", "lanes": 2, "maxspeed": 40, "name": "Unknown Road"}

    def get_live_traffic_speed(self, lat: float, lng: float, free_flow_speed: int) -> float:
        """
        Fetch LIVE traffic speed. Uses TomTom API if key exists, otherwise
        simulates realistic congestion based on OSM road type and time of day.
        """
        if self.tomtom_api_key:
            # Production: Real TomTom API Call
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lng}&key={self.tomtom_api_key}"
            try:
                res = requests.get(url, timeout=2).json()
                return res['flowSegmentData']['currentSpeed']
            except:
                pass
        
        # Free Tier / Hackathon Fallback: Simulate realistic congestion 
        # reduction based on road capacity (lanes) and time
        from datetime import datetime
        hour = datetime.utcnow().hour
        
        # Rush hour penalty
        congestion_factor = 1.0
        if 8 <= hour <= 10 or 17 <= hour <= 20:
            congestion_factor = 0.4  # 60% reduction in speed
        elif 11 <= hour <= 16:
            congestion_factor = 0.7  # 30% reduction in speed
            
        return max(5.0, free_flow_speed * congestion_factor)

traffic_api = TrafficAPIIntegration()
