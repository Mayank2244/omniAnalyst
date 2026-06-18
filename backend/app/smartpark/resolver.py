"""
OmniRoute Analytics — SmartPark Resolver
Recommends lowest-impact parking zones for Flipkart delivery vehicles.
"""
from datetime import datetime
from typing import Optional

from app.dcli.scorer import compute_dcli


def recommend_parking(
    lat: float,
    lng: float,
    duration_mins: int,
    city_graph,
    timestamp: Optional[datetime] = None,
) -> list[dict]:
    """
    Find top-3 nearby spots where parking causes minimum DCLI impact.

    For each candidate node within 500m, simulates DCLI if a commercial vehicle
    parks there. Returns the 3 lowest-impact options.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    candidates = city_graph.nodes_within_radius(lat, lng, radius_m=500)

    if not candidates:
        # Fallback: use wider radius
        candidates = city_graph.nodes_within_radius(lat, lng, radius_m=1000)

    scored = []
    for node in candidates[:20]:  # Limit computation
        simulated_dcli = compute_dcli(
            lat=node["lat"],
            lng=node["lng"],
            vehicle_type="commercial",
            timestamp=timestamp,
            violation_type="",
            junction_name="",
            centrality_score=node["centrality"],
        )
        # Scale by duration — longer parking = more damage
        impact = simulated_dcli * (duration_mins / 3.0)

        scored.append({
            "lat": round(node["lat"], 7),
            "lng": round(node["lng"], 7),
            "distance_m": round(node["distance_m"], 1),
            "dcli_impact": round(impact, 2),
            "centrality": round(node["centrality"], 2),
            "zone_safety": "safe" if impact < 500 else ("caution" if impact < 2000 else "danger"),
        })

    # Sort by impact (lowest first) and return top 3
    scored.sort(key=lambda x: x["dcli_impact"])
    return scored[:3]
