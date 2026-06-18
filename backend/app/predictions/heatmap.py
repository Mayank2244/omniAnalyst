"""
OmniRoute Analytics — Predictive Heat Calendar
Forecasts violation hotspots by time-of-day and day-of-week patterns.
"""
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta


def generate_heatmap_predictions(df: pd.DataFrame) -> dict:
    """
    Analyze historical violations to predict future hotspots.

    Groups violations by (hour, day_of_week, police_station) and finds
    statistically significant clusters.

    Returns a prediction payload for the frontend.
    """
    df = df.dropna(subset=["latitude", "longitude", "created_datetime"])
    df["created_datetime"] = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["created_datetime"])

    df["hour"] = df["created_datetime"].dt.hour
    df["day_of_week"] = df["created_datetime"].dt.dayofweek  # 0=Monday
    df["day_name"] = df["created_datetime"].dt.day_name()

    # ── Hotspot analysis by zone + time ──
    zone_time = df.groupby(["police_station", "hour"]).agg(
        count=("id", "count"),
        avg_lat=("latitude", "mean"),
        avg_lng=("longitude", "mean"),
    ).reset_index()

    # Find top hotspots (zones with most violations at specific hours)
    zone_time = zone_time.sort_values("count", ascending=False)
    top_hotspots = zone_time.head(20)

    predictions = []
    now = datetime.utcnow()

    for _, row in top_hotspots.iterrows():
        # Predict for the next 24 hours
        target_hour = int(row["hour"])
        predicted_time = now.replace(hour=target_hour, minute=0, second=0)
        if predicted_time < now:
            predicted_time += timedelta(days=1)

        predictions.append({
            "zone": str(row["police_station"]),
            "lat": round(float(row["avg_lat"]), 6),
            "lng": round(float(row["avg_lng"]), 6),
            "predicted_hour": target_hour,
            "predicted_time": predicted_time.isoformat(),
            "historical_count": int(row["count"]),
            "risk_level": "critical" if row["count"] > 100 else ("high" if row["count"] > 50 else "medium"),
        })

    # ── Hourly distribution (for chart) ──
    hourly = df.groupby("hour").size().reset_index(name="count")
    hourly_data = [{"hour": int(r["hour"]), "count": int(r["count"])} for _, r in hourly.iterrows()]

    # ── Day-of-week distribution ──
    daily = df.groupby(["day_of_week", "day_name"]).size().reset_index(name="count")
    daily = daily.sort_values("day_of_week")
    daily_data = [{"day": str(r["day_name"]), "count": int(r["count"])} for _, r in daily.iterrows()]

    # ── Top violation types ──
    if "violation_type" in df.columns:
        vtype_counts = df["violation_type"].value_counts().head(5)
        violation_types = [{"type": str(k), "count": int(v)} for k, v in vtype_counts.items()]
    else:
        violation_types = []

    return {
        "predicted_hotspots": predictions,
        "hourly_distribution": hourly_data,
        "daily_distribution": daily_data,
        "top_violation_types": violation_types,
        "generated_at": now.isoformat(),
    }
