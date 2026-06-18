"""
OmniRoute Analytics — City Graph Builder
Constructs a road network graph from violation data using NetworkX.
Computes betweenness centrality for DCLI scoring.
"""
import math
from collections import defaultdict
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd
from geopy.distance import geodesic


class CityGraph:
    """
    Builds a synthetic city road graph from violation GPS clusters.
    Nodes = violation hotspot centroids.
    Edges = inferred road connections between nearby clusters.
    """

    def __init__(self):
        self.graph = nx.Graph()
        self._node_coords: dict[int, tuple[float, float]] = {}
        self._centrality: dict[int, float] = {}
        self._edge_data: dict[tuple[int, int], dict] = {}

    def build_from_violations(self, df: pd.DataFrame, grid_size: float = 0.003):
        """
        Build a graph by gridding the city into cells based on violation density.

        Args:
            df: DataFrame with 'latitude' and 'longitude' columns.
            grid_size: Grid cell size in degrees (~300m at Bangalore latitude).
        """
        # Grid the violations
        df = df.dropna(subset=["latitude", "longitude"])
        df["grid_lat"] = (df["latitude"] / grid_size).astype(int)
        df["grid_lng"] = (df["longitude"] / grid_size).astype(int)

        # Each grid cell with violations becomes a node
        groups = df.groupby(["grid_lat", "grid_lng"])
        node_id = 0
        grid_to_node = {}

        for (glat, glng), group in groups:
            centroid_lat = group["latitude"].mean()
            centroid_lng = group["longitude"].mean()
            violation_count = len(group)

            self.graph.add_node(
                node_id,
                lat=centroid_lat,
                lng=centroid_lng,
                violation_count=violation_count,
                name=group["junction_name"].mode().iloc[0] if "junction_name" in group.columns and len(group["junction_name"].mode()) > 0 else f"Zone-{node_id}",
            )
            self._node_coords[node_id] = (centroid_lat, centroid_lng)
            grid_to_node[(glat, glng)] = node_id
            node_id += 1

        # Connect adjacent grid cells (8-connectivity)
        for (glat, glng), nid in grid_to_node.items():
            for dlat in [-1, 0, 1]:
                for dlng in [-1, 0, 1]:
                    if dlat == 0 and dlng == 0:
                        continue
                    neighbor_key = (glat + dlat, glng + dlng)
                    if neighbor_key in grid_to_node:
                        neighbor_id = grid_to_node[neighbor_key]
                        if not self.graph.has_edge(nid, neighbor_id):
                            coord_a = self._node_coords[nid]
                            coord_b = self._node_coords[neighbor_id]
                            dist = geodesic(coord_a, coord_b).meters
                            self.graph.add_edge(
                                nid, neighbor_id,
                                length_m=dist,
                                free_flow_speed=40.0,
                                current_speed=40.0,
                                congestion_level="free",
                            )

        # Compute betweenness centrality
        if len(self.graph.nodes) > 1:
            raw = nx.betweenness_centrality(self.graph)
            max_c = max(raw.values()) if max(raw.values()) > 0 else 1.0
            self._centrality = {n: (v / max_c) * 99.0 + 1.0 for n, v in raw.items()}
        else:
            self._centrality = {n: 1.0 for n in self.graph.nodes}

    def get_centrality(self, node_id: int) -> float:
        """Get betweenness centrality score (1-100) for a node."""
        return self._centrality.get(node_id, 1.0)

    def nearest_node(self, lat: float, lng: float) -> Optional[int]:
        """Find the nearest node to a given lat/lng."""
        min_dist = float("inf")
        best_node = None
        for nid, (nlat, nlng) in self._node_coords.items():
            dist = (nlat - lat) ** 2 + (nlng - lng) ** 2
            if dist < min_dist:
                min_dist = dist
                best_node = nid
        return best_node

    def get_neighbors_with_distances(self, node_id: int, hops: int = 3):
        """Get nodes within N hops and their distances (for shockwave propagation)."""
        result = []
        visited = set()
        queue = [(node_id, 0, 0.0)]
        visited.add(node_id)

        while queue:
            current, hop, dist = queue.pop(0)
            if hop > 0:
                result.append({
                    "node_id": current,
                    "hops": hop,
                    "distance_m": dist,
                    "coords": self._node_coords.get(current, (0, 0)),
                    "centrality": self.get_centrality(current),
                })
            if hop < hops:
                for neighbor in self.graph.neighbors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        edge_dist = self.graph[current][neighbor].get("length_m", 300)
                        queue.append((neighbor, hop + 1, dist + edge_dist))

        return result

    def get_graph_data(self):
        """Export graph data for frontend visualization."""
        nodes = []
        for nid in self.graph.nodes:
            data = self.graph.nodes[nid]
            nodes.append({
                "id": nid,
                "lat": data["lat"],
                "lng": data["lng"],
                "name": data.get("name", ""),
                "violation_count": data.get("violation_count", 0),
                "centrality": round(self.get_centrality(nid), 2),
            })

        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "from_lat": self._node_coords[u][0],
                "from_lng": self._node_coords[u][1],
                "to_lat": self._node_coords[v][0],
                "to_lng": self._node_coords[v][1],
                "length_m": round(data.get("length_m", 0), 1),
                "congestion_level": data.get("congestion_level", "free"),
            })

        return {"nodes": nodes, "edges": edges}

    def nodes_within_radius(self, lat: float, lng: float, radius_m: float = 500):
        """Find all nodes within a radius of a point."""
        result = []
        for nid, (nlat, nlng) in self._node_coords.items():
            dist = geodesic((lat, lng), (nlat, nlng)).meters
            if dist <= radius_m:
                result.append({
                    "node_id": nid,
                    "lat": nlat,
                    "lng": nlng,
                    "distance_m": dist,
                    "centrality": self.get_centrality(nid),
                })
        return sorted(result, key=lambda x: x["distance_m"])
