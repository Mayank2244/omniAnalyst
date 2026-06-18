#!/usr/bin/env python3
"""
OmniRoute Analytics — Database Seeder
Populates road_nodes, road_edges, and violations tables from CSV data.
Usage: python -m scripts.seed_data  (from backend/ directory)
   OR: python scripts/seed_data.py  (from project root)
"""
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

import pandas as pd
import numpy as np
from datetime import datetime
from geopy.distance import geodesic
from collections import defaultdict

from app.config import CSV_PATH, DATABASE_URL
from app.models.db_models import (
    engine, SessionLocal, Base,
    RoadNode, RoadEdge, Violation, EnforcementDispatch,
)
from app.dcli.scorer import compute_dcli, dcli_to_congestion_level


def load_and_clean_csv(sample_size=5000):
    """Load CSV and clean for Bangalore bounding box."""
    print(f"📂 Loading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"   Raw records: {len(df)}")

    df = df.dropna(subset=["latitude", "longitude", "created_datetime"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # Bangalore bounding box
    df = df[
        (df["latitude"] > 12.7)
        & (df["latitude"] < 13.2)
        & (df["longitude"] > 77.4)
        & (df["longitude"] < 77.8)
    ]

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

    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).sort_values("created_datetime")

    df = df.reset_index(drop=True)
    print(f"   Cleaned records: {len(df)}")
    return df


def seed_road_network(df, grid_size=0.003):
    """Build road nodes and edges from GPS clusters, insert into MySQL."""
    print("\n🔧 Building road network from violation clusters...")
    db = SessionLocal()

    try:
        # Check if already seeded
        existing_nodes = db.query(RoadNode).count()
        if existing_nodes > 0:
            print(f"   ⚠️  road_nodes already has {existing_nodes} records. Skipping network seed.")
            return

        # Grid the violations
        df["grid_lat"] = (df["latitude"] / grid_size).astype(int)
        df["grid_lng"] = (df["longitude"] / grid_size).astype(int)

        groups = df.groupby(["grid_lat", "grid_lng"])
        node_map = {}  # (grid_lat, grid_lng) -> RoadNode
        nodes_created = 0

        for (glat, glng), group in groups:
            centroid_lat = group["latitude"].mean()
            centroid_lng = group["longitude"].mean()
            violation_count = len(group)

            # Criticality based on violation density
            criticality = min(100.0, max(1.0, violation_count / 2.0))

            name = "No Junction"
            if "junction_name" in group.columns:
                mode = group["junction_name"].mode()
                if len(mode) > 0 and mode.iloc[0] != "No Junction":
                    name = mode.iloc[0]

            node = RoadNode(
                lat=round(centroid_lat, 7),
                lng=round(centroid_lng, 7),
                intersection_name=name[:255] if name else "",
                criticality_score=round(criticality, 2),
            )
            db.add(node)
            db.flush()  # Get the ID
            node_map[(glat, glng)] = node
            nodes_created += 1

        db.commit()
        print(f"   ✅ Created {nodes_created} road_nodes")

        # Connect adjacent grid cells (8-connectivity)
        edges_created = 0
        seen_edges = set()

        for (glat, glng), node in node_map.items():
            for dlat in [-1, 0, 1]:
                for dlng in [-1, 0, 1]:
                    if dlat == 0 and dlng == 0:
                        continue
                    neighbor_key = (glat + dlat, glng + dlng)
                    if neighbor_key in node_map:
                        neighbor = node_map[neighbor_key]
                        edge_key = tuple(sorted([node.id, neighbor.id]))
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            dist = geodesic(
                                (float(node.lat), float(node.lng)),
                                (float(neighbor.lat), float(neighbor.lng))
                            ).meters

                            edge = RoadEdge(
                                from_node_id=node.id,
                                to_node_id=neighbor.id,
                                road_name=f"Road {node.id}-{neighbor.id}",
                                length_m=round(dist, 1),
                                lanes=2,
                                free_flow_speed=40.0,
                                current_speed=40.0,
                                congestion_level="free",
                            )
                            db.add(edge)
                            edges_created += 1

        db.commit()
        print(f"   ✅ Created {edges_created} road_edges")

    except Exception as e:
        db.rollback()
        print(f"   ❌ Error seeding road network: {e}")
        raise
    finally:
        db.close()


def seed_violations(df, max_violations=1000):
    """Insert sample violations with DCLI scores into MySQL."""
    print(f"\n📍 Seeding {max_violations} violations into MySQL...")
    db = SessionLocal()

    try:
        existing = db.query(Violation).count()
        if existing > 0:
            print(f"   ⚠️  violations table already has {existing} records. Skipping.")
            return

        sample = df.head(max_violations)
        seeded = 0

        for _, row in sample.iterrows():
            try:
                ts = row["created_datetime"]
                if hasattr(ts, 'to_pydatetime'):
                    ts = ts.to_pydatetime()
                # Make timezone-naive for MySQL
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)

                dcli = compute_dcli(
                    lat=float(row["latitude"]),
                    lng=float(row["longitude"]),
                    vehicle_type=str(row.get("vehicle_type", "CAR")),
                    timestamp=ts,
                    violation_type=str(row.get("violation_type", "")),
                    junction_name=str(row.get("junction_name", "")),
                    centrality_score=1.0,
                )

                v = Violation(
                    lat=round(float(row["latitude"]), 7),
                    lng=round(float(row["longitude"]), 7),
                    location_text=str(row.get("location", ""))[:500],
                    vehicle_id=str(row.get("vehicle_number", "UNKNOWN"))[:50],
                    vehicle_type=str(row.get("vehicle_type", "CAR"))[:30],
                    violation_type=str(row.get("violation_type", "")),
                    timestamp_start=ts,
                    dcli_score=dcli,
                    is_active=True,
                    police_station=str(row.get("police_station", ""))[:100],
                    junction_name=str(row.get("junction_name", ""))[:255],
                )
                db.add(v)
                seeded += 1

                if seeded % 200 == 0:
                    db.commit()
                    print(f"   ... {seeded}/{max_violations} violations seeded")

            except Exception as e:
                continue

        db.commit()
        print(f"   ✅ Seeded {seeded} violations with DCLI scores")

    except Exception as e:
        db.rollback()
        print(f"   ❌ Error seeding violations: {e}")
        raise
    finally:
        db.close()


def seed_enforcement_dispatches():
    """Create sample enforcement dispatches from high-DCLI violations."""
    print("\n🚔 Seeding enforcement dispatches...")
    db = SessionLocal()

    try:
        existing = db.query(EnforcementDispatch).count()
        if existing > 0:
            print(f"   ⚠️  enforcement_dispatches already has {existing} records. Skipping.")
            return

        # Get top violations by DCLI
        top_violations = (
            db.query(Violation)
            .filter(Violation.is_active == True)
            .order_by(Violation.dcli_score.desc())
            .limit(20)
            .all()
        )

        for rank, v in enumerate(top_violations, 1):
            dispatch = EnforcementDispatch(
                violation_id=v.id,
                priority_rank=rank,
                estimated_savings=round(float(v.dcli_score) * 0.6, 2) if v.dcli_score else 0,
                status="dispatched" if rank <= 5 else "en_route" if rank <= 10 else "dispatched",
            )
            db.add(dispatch)

        db.commit()
        print(f"   ✅ Created {len(top_violations)} enforcement dispatches")

    except Exception as e:
        db.rollback()
        print(f"   ❌ Error: {e}")
    finally:
        db.close()


def main():
    print("=" * 60)
    print("  OmniRoute Analytics — Database Seeder")
    print(f"  Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("=" * 60)

    # Create tables if they don't exist
    print("\n🗄️  Ensuring tables exist...")
    Base.metadata.create_all(bind=engine)
    print("   ✅ Tables verified")

    # Load CSV data
    df = load_and_clean_csv(sample_size=5000)

    # Seed road network
    seed_road_network(df)

    # Seed violations
    seed_violations(df, max_violations=1000)

    # Seed enforcement dispatches
    seed_enforcement_dispatches()

    # Summary
    print("\n" + "=" * 60)
    db = SessionLocal()
    print("  📊 Database Summary:")
    print(f"     road_nodes:              {db.query(RoadNode).count()}")
    print(f"     road_edges:              {db.query(RoadEdge).count()}")
    print(f"     violations:              {db.query(Violation).count()}")
    print(f"     enforcement_dispatches:  {db.query(EnforcementDispatch).count()}")
    db.close()
    print("=" * 60)
    print("  ✅ Seeding complete!")


if __name__ == "__main__":
    main()
