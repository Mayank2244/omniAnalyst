"""
OmniRoute Analytics — Ingestion Engine
Loads the CSV dataset and streams it as real-time events.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

import pandas as pd

from app.config import CSV_PATH, STREAM_SPEED_MULTIPLIER
from app.dcli.scorer import compute_dcli, dcli_to_color, dcli_to_congestion_level


def load_dataset(sample_size: int = 5000) -> pd.DataFrame:
    """
    Load and clean the violations CSV dataset.
    Takes a sample for performance during the hackathon demo.
    """
    df = pd.read_csv(CSV_PATH, low_memory=False)

    # Clean columns
    df = df.dropna(subset=["latitude", "longitude", "created_datetime"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # Filter to Bangalore bounding box
    df = df[
        (df["latitude"] > 12.7)
        & (df["latitude"] < 13.2)
        & (df["longitude"] > 77.4)
        & (df["longitude"] < 77.8)
    ]

    # Parse datetime
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["created_datetime"])
    df = df.sort_values("created_datetime")

    # Fill missing values
    df["vehicle_type"] = df["vehicle_type"].fillna("CAR")
    df["violation_type"] = df["violation_type"].fillna("")
    df["junction_name"] = df["junction_name"].fillna("No Junction")
    df["police_station"] = df["police_station"].fillna("")
    df["location"] = df["location"].fillna("")
    df["vehicle_number"] = df["vehicle_number"].fillna("UNKNOWN")

    # Sample for demo (None = load all for training)
    if sample_size is not None and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).sort_values("created_datetime")

    df = df.reset_index(drop=True)
    return df


def prepare_violation_event(row: pd.Series, city_graph=None) -> dict:
    """Convert a DataFrame row to a violation event dict with DCLI score."""
    centrality = 1.0
    if city_graph:
        node = city_graph.nearest_node(row["latitude"], row["longitude"])
        if node is not None:
            centrality = city_graph.get_centrality(node)

    dcli = compute_dcli(
        lat=row["latitude"],
        lng=row["longitude"],
        vehicle_type=str(row.get("vehicle_type", "CAR")),
        timestamp=row["created_datetime"].to_pydatetime() if hasattr(row["created_datetime"], "to_pydatetime") else row["created_datetime"],
        violation_type=str(row.get("violation_type", "")),
        junction_name=str(row.get("junction_name", "")),
        centrality_score=centrality,
    )

    return {
        "id": str(row.get("id", "")),
        "lat": float(row["latitude"]),
        "lng": float(row["longitude"]),
        "location": str(row.get("location", "")),
        "vehicle_id": str(row.get("vehicle_number", "")),
        "vehicle_type": str(row.get("vehicle_type", "CAR")),
        "violation_type": str(row.get("violation_type", "")),
        "timestamp": str(row["created_datetime"]),
        "police_station": str(row.get("police_station", "")),
        "junction_name": str(row.get("junction_name", "")),
        "dcli_score": dcli,
        "congestion_level": dcli_to_congestion_level(dcli),
        "color": dcli_to_color(dcli),
    }


def load_all_violations_with_dcli(city_graph=None, sample_size: int = 5000) -> list[dict]:
    """Load dataset and compute DCLI for all violations. Returns list of event dicts."""
    df = load_dataset(sample_size=sample_size)
    events = []
    for _, row in df.iterrows():
        events.append(prepare_violation_event(row, city_graph))
    return events
