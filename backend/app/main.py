"""
OmniRoute Analytics — FastAPI Main Application
CSV → Train ML Models → Serve Model Predictions
Connected to MySQL (omniroute database).
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_TITLE, APP_VERSION, CORS_ORIGINS, CSV_PATH, DATABASE_URL
from app.dcli.scorer import compute_dcli, dcli_to_color, dcli_to_congestion_level
from app.ingestion.stream import load_dataset
from app.model.graph import CityGraph
from app.smartpark.resolver import recommend_parking
from app.ml.trainer import ml_engine
from app.models.db_models import (
    engine, SessionLocal, get_db, init_db,
    RoadNode, RoadEdge, Violation, EnforcementDispatch,
    SmartParkRequest, CongestionPrediction,
)

# ── Global ──
city_graph = CityGraph()
raw_df: Optional[pd.DataFrame] = None
model_stats: dict = {}
connected_ws: list[WebSocket] = []
streaming_task: Optional[asyncio.Task] = None
streaming_active: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global raw_df, model_stats

    # 1. Connect MySQL
    print(f"🔌 Connecting to MySQL (omniroute)...")
    init_db()

    # 2. Load CSV as TRAINING data (sample for speed, still learns real patterns)
    print(f"📂 Loading training data: {CSV_PATH}")
    raw_df = load_dataset(sample_size=20000)  # 20K sample for fast ML training
    print(f"✅ Training dataset: {len(raw_df)} records")

    # 3. Build city graph from training data
    print("🔧 Building city graph from training data...")
    city_graph.build_from_violations(raw_df)
    gd = city_graph.get_graph_data()
    print(f"✅ Graph: {len(gd['nodes'])} nodes, {len(gd['edges'])} edges")

    # 4. TRAIN ML MODELS
    print("🧠 Training ML models on dataset...")
    training_summary = ml_engine.train(raw_df)
    print(f"✅ ML training complete!")

    # 5. Compute model stats
    zone_analysis = ml_engine.get_zone_analysis()
    temporal = ml_engine.get_temporal_analysis()

    model_stats = {
        'training': training_summary,
        'total_training_records': len(raw_df),
        'graph_nodes': len(gd['nodes']),
        'graph_edges': len(gd['edges']),
        'hotspot_clusters': len(ml_engine.zone_clusters or []),
        'risk_zones': len(zone_analysis),
        'peak_hours': temporal.get('peak_hours', []),
    }

    print(f"🌐 Server ready at http://localhost:8000")
    print(f"📖 API Docs: http://localhost:8000/docs")
    yield
    print("👋 Shutting down")


# ── App ──
app = FastAPI(title=APP_TITLE, version=APP_VERSION,
              description="Urban Digital Twin — ML-Powered Congestion Intelligence",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ═══════════════════ API ENDPOINTS ═══════════════════

@app.get("/")
async def root():
    return {
        "name": APP_TITLE, "version": APP_VERSION, "status": "operational",
        "database": "omniroute (MySQL)",
        "ml_status": "trained" if ml_engine.trained else "untrained",
        "training_records": model_stats.get('total_training_records', 0),
        "models_active": 5 if ml_engine.lstm_trained else 4,
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "ml_status": "trained" if ml_engine.trained else "untrained",
        "streaming": streaming_active,
        "websocket_clients": len(connected_ws),
    }


# ═══════════════════ LIVE STREAMING ═══════════════════

async def _stream_csv_replay(speed_multiplier: float = 50.0, batch_size: int = 500):
    """Background task: replay CSV violations as live events through WebSocket."""
    global streaming_active
    streaming_active = True
    try:
        from app.ingestion.stream import load_dataset, prepare_violation_event
        df = load_dataset(sample_size=batch_size)
        print(f"🎬 Streaming {len(df)} violations (speed: {speed_multiplier}x)")

        for i, (_, row) in enumerate(df.iterrows()):
            if not streaming_active:
                break

            event = prepare_violation_event(row, city_graph)
            # Persist to MySQL
            db = SessionLocal()
            try:
                v = Violation(
                    lat=event["lat"], lng=event["lng"],
                    vehicle_id=event["vehicle_id"],
                    vehicle_type=event["vehicle_type"],
                    timestamp_start=pd.to_datetime(event["timestamp"]),
                    dcli_score=event["dcli_score"],
                    is_active=True,
                    police_station=event.get("police_station", ""),
                    junction_name=event.get("junction_name", ""),
                    location_text=event.get("location", ""),
                    violation_type=event.get("violation_type", ""),
                )
                db.add(v)
                db.commit()
                event["violation_db_id"] = v.id
            except Exception:
                db.rollback()
            finally:
                db.close()

            # Broadcast to WebSocket clients
            payload = {"type": "new_violation", "data": event, "index": i + 1, "total": len(df)}
            for ws in list(connected_ws):
                try:
                    await ws.send_json(payload)
                except Exception:
                    if ws in connected_ws:
                        connected_ws.remove(ws)

            # Simulate time delay between events
            await asyncio.sleep(max(0.05, 1.0 / speed_multiplier))

        print(f"✅ Streaming complete: {i + 1} events broadcast")
    except Exception as e:
        print(f"❌ Streaming error: {e}")
    finally:
        streaming_active = False


@app.post("/api/stream/start")
async def start_streaming(
    speed: float = Query(50.0, description="Speed multiplier"),
    count: int = Query(500, description="Number of violations to stream"),
):
    """Start live CSV replay streaming through WebSocket."""
    global streaming_task, streaming_active
    if streaming_active:
        return {"status": "already_running", "clients": len(connected_ws)}
    streaming_task = asyncio.create_task(_stream_csv_replay(speed, count))
    return {"status": "started", "speed": speed, "count": count, "clients": len(connected_ws)}


@app.post("/api/stream/stop")
async def stop_streaming():
    """Stop live streaming."""
    global streaming_active
    streaming_active = False
    return {"status": "stopped"}


@app.get("/api/stream/status")
async def stream_status():
    """Check streaming status."""
    return {"active": streaming_active, "clients": len(connected_ws)}


@app.get("/api/ml/forecast")
async def lstm_forecast():
    """LSTM Deep Learning: 24-hour violation count forecast."""
    forecast = ml_engine.predict_lstm_forecast()
    return {
        "model": "LSTM (PyTorch)" if ml_engine.lstm_trained else "Statistical Fallback",
        "forecast_hours": 24,
        "generated_at": datetime.utcnow().isoformat(),
        "forecast": forecast,
    }


@app.get("/api/ml/status")
async def ml_status():
    """ML model training summary — what was trained and how."""
    return model_stats.get('training', {})


@app.get("/api/ml/predict/hotspots")
async def predict_hotspots(hours: int = Query(24, description="Hours ahead to predict")):
    """ML Prediction: Where will violations happen next?"""
    predictions = ml_engine.predict_hotspots(hours_ahead=hours)
    return {
        "model": "KMeans Hotspot Clustering + Temporal Analysis",
        "prediction_window": f"Next {hours} hours",
        "generated_at": datetime.utcnow().isoformat(),
        "predictions": predictions,
    }


@app.get("/api/ml/predict/dcli")
async def predict_dcli(
    lat: float = Query(...), lng: float = Query(...),
    hour: int = Query(12), zone: str = Query("Unknown"),
    vehicle_type: str = Query("CAR"),
):
    """ML Prediction: What DCLI impact will a violation at this location cause?"""
    dcli = ml_engine.predict_dcli(lat, lng, hour, zone, vehicle_type)
    level = dcli_to_congestion_level(dcli)
    return {
        "model": "GradientBoosting Congestion Predictor",
        "input": {"lat": lat, "lng": lng, "hour": hour, "zone": zone, "vehicle_type": vehicle_type},
        "predicted_dcli": dcli,
        "congestion_level": level,
        "color": dcli_to_color(dcli),
        "economic_impact": f"₹{dcli:,.0f}/hour",
    }


@app.get("/api/ml/zones")
async def get_zone_analysis():
    """ML Analysis: Risk profiles for all zones (trained from data)."""
    zones = ml_engine.get_zone_analysis()
    return {
        "model": "Zone Risk Classifier",
        "total_zones": len(zones),
        "zones": zones,
    }


@app.get("/api/ml/temporal")
async def get_temporal_analysis():
    """ML Analysis: Learned time patterns (hourly, daily, peak hours)."""
    return {
        "model": "Temporal Pattern Analysis",
        **ml_engine.get_temporal_analysis(),
    }


@app.get("/api/ml/clusters")
async def get_clusters():
    """ML Output: Hotspot cluster centers from KMeans."""
    return {
        "model": "KMeans Clustering",
        "clusters": ml_engine.zone_clusters or [],
    }


# ── Graph & SmartPark (model-based) ──

@app.get("/api/map/state")
async def get_map_state():
    """City graph for visualization + cluster overlays."""
    return {
        "graph": city_graph.get_graph_data(),
        "clusters": ml_engine.zone_clusters or [],
    }


@app.get("/api/smartpark/recommend")
async def smartpark_recommend(
    lat: float = Query(...), lng: float = Query(...),
    duration_mins: int = Query(3), db=Depends(get_db),
):
    """SmartPark V2I: ML-powered parking recommendations."""
    recs = recommend_parking(lat=lat, lng=lng, duration_mins=duration_mins, city_graph=city_graph)

    # Enhance with ML predictions
    for r in recs:
        r['ml_predicted_dcli'] = ml_engine.predict_dcli(
            r['lat'], r['lng'], datetime.utcnow().hour, 'Unknown', 'CAR'
        )

    if recs:
        best = recs[0]
        db.add(SmartParkRequest(
            vehicle_id="flipkart-demo", requested_lat=lat, requested_lng=lng,
            duration_mins=duration_mins, recommended_lat=best["lat"],
            recommended_lng=best["lng"], dcli_impact_saved=best["dcli_impact"],
        ))
        db.commit()

    return {"model": "SmartPark + GBR DCLI Predictor", "recommendations": recs}


@app.get("/api/propagation/simulate")
async def simulate_propagation(
    lat: float = Query(...), lng: float = Query(...), hops: int = Query(3),
):
    """Simulate congestion shockwave propagation from a point."""
    node = city_graph.nearest_node(lat, lng)
    if node is None:
        return {"shockwave": []}
    neighbors = city_graph.get_neighbors_with_distances(node, hops=hops)
    return {"source": {"lat": lat, "lng": lng}, "shockwave": [{
        "lat": n["coords"][0], "lng": n["coords"][1], "hops": n["hops"],
        "distance_m": round(n["distance_m"], 1),
        "intensity": round(max(0.1, 1.0 - (n["hops"] / (hops + 1))), 2),
        "delay_minutes": round(5 * max(0.1, 1.0 - (n["hops"] / (hops + 1))) * n["centrality"] / 50, 1),
    } for n in neighbors]}


# ── Violation Ingestion (model-scored) ──

@app.post("/api/events/violation")
async def ingest_violation(
    vehicle_id: str = Query(...), vehicle_type: str = Query("CAR"),
    lat: float = Query(...), lng: float = Query(...),
    zone: str = Query("Unknown"), timestamp: str = Query(None),
    db=Depends(get_db),
):
    """Ingest a new violation — scored by trained ML model."""
    ts = pd.to_datetime(timestamp) if timestamp else datetime.utcnow()

    # ML-predicted DCLI
    predicted_dcli = ml_engine.predict_dcli(lat, lng, ts.hour, zone, vehicle_type)

    # Save to MySQL
    v = Violation(
        lat=lat, lng=lng, vehicle_id=vehicle_id, vehicle_type=vehicle_type,
        timestamp_start=ts, dcli_score=predicted_dcli, is_active=True,
        police_station=zone,
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    response_data = {
        "status": "ingested",
        "violation_id": v.id,
        "ml_predicted_dcli": predicted_dcli,
        "congestion_level": dcli_to_congestion_level(predicted_dcli),
        "model_used": "GradientBoosting Congestion Predictor",
        "vehicle_type": vehicle_type,
        "zone": zone,
        "lat": lat,
        "lng": lng,
    }

    # Broadcast to all connected WebSockets
    for ws in list(connected_ws):
        try:
            # We use a background task or just await since we're in an async func
            # But await is tricky inside a loop, so we'll do it sequentially
            import asyncio
            asyncio.create_task(ws.send_json({
                "type": "new_violation",
                "data": response_data
            }))
        except Exception:
            connected_ws.remove(ws)

    return response_data


# ── Dashboard (model-driven) ──

@app.get("/api/dashboard/summary")
async def get_dashboard_summary(db=Depends(get_db)):
    """CFO Dashboard — all data from trained ML models."""
    db_count = db.query(Violation).count()
    zones = ml_engine.get_zone_analysis()[:5]
    temporal = ml_engine.get_temporal_analysis()
    predictions = ml_engine.predict_hotspots(hours_ahead=6)[:3]

    critical_zones = [z for z in zones if z['risk_level'] in ('CRITICAL', 'HIGH')]

    return {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "database": "omniroute (MySQL)",
        "ml_status": "trained",
        "training_records": model_stats.get('total_training_records', 0),
        "db_violation_count": db_count,
        "models_active": 4,
        "risk_zones": {
            "total": len(zones),
            "critical": len([z for z in ml_engine.get_zone_analysis() if z['risk_level'] == 'CRITICAL']),
            "high": len([z for z in ml_engine.get_zone_analysis() if z['risk_level'] == 'HIGH']),
            "top_zones": zones,
        },
        "temporal": {
            "peak_hours": temporal.get('peak_hours', []),
            "hourly_distribution": temporal.get('hourly_distribution', []),
        },
        "upcoming_predictions": predictions,
        "congestion_clusters": len(ml_engine.zone_clusters or []),
    }


@app.get("/api/db/stats")
async def get_db_stats(db=Depends(get_db)):
    return {
        "database": "omniroute", "engine": "MySQL", "status": "connected",
        "tables": {
            "road_nodes": db.query(RoadNode).count(),
            "road_edges": db.query(RoadEdge).count(),
            "violations": db.query(Violation).count(),
            "enforcement_dispatches": db.query(EnforcementDispatch).count(),
            "smartpark_requests": db.query(SmartParkRequest).count(),
            "congestion_predictions": db.query(CongestionPrediction).count(),
        },
    }


# ── TRD Required: Active Violations ──

@app.get("/api/violations/active")
async def get_active_violations(
    limit: int = Query(50), db=Depends(get_db),
):
    """List all currently active violations with DCLI scores — TRD §6."""
    violations = (
        db.query(Violation)
        .filter(Violation.is_active == True)
        .order_by(Violation.dcli_score.desc())
        .limit(limit)
        .all()
    )

    # If no DB violations, generate from ML model for demo
    if not violations:
        return {
            "source": "ml_generated",
            "count": len(ml_engine.zone_clusters or []),
            "violations": [{
                "id": i + 1,
                "lat": c["lat"], "lng": c["lng"],
                "zone": c["zone"],
                "vehicle_type": "CAR",
                "dcli_score": ml_engine.predict_dcli(c["lat"], c["lng"], datetime.utcnow().hour, c["zone"], "CAR"),
                "congestion_level": dcli_to_congestion_level(
                    ml_engine.predict_dcli(c["lat"], c["lng"], datetime.utcnow().hour, c["zone"], "CAR")
                ),
                "is_active": True,
                "peak_hour": c["peak_hour"],
            } for i, c in enumerate(ml_engine.zone_clusters or [])],
        }

    return {
        "source": "mysql",
        "count": len(violations),
        "violations": [{
            "id": v.id,
            "lat": float(v.lat), "lng": float(v.lng),
            "vehicle_id": v.vehicle_id, "vehicle_type": v.vehicle_type,
            "dcli_score": float(v.dcli_score) if v.dcli_score else 0,
            "congestion_level": dcli_to_congestion_level(float(v.dcli_score) if v.dcli_score else 0),
            "timestamp": str(v.timestamp_start),
            "is_active": v.is_active,
        } for v in violations],
    }


@app.get("/api/violations/{violation_id}")
async def get_violation(violation_id: int, db=Depends(get_db)):
    """CRUD: Read a single violation by ID."""
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        return {"error": "Violation not found"}
    return {
        "id": v.id, "lat": float(v.lat), "lng": float(v.lng),
        "vehicle_id": v.vehicle_id, "vehicle_type": v.vehicle_type,
        "dcli_score": float(v.dcli_score) if v.dcli_score else 0,
        "is_active": v.is_active, "police_station": v.police_station,
    }


@app.put("/api/violations/{violation_id}")
async def update_violation(
    violation_id: int, 
    vehicle_type: str = Query(None),
    is_active: bool = Query(None),
    db=Depends(get_db)
):
    """CRUD: Update a violation."""
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        return {"error": "Violation not found"}
    
    if vehicle_type:
        v.vehicle_type = vehicle_type
        # Re-score DCLI using ML model based on new vehicle type
        v.dcli_score = ml_engine.predict_dcli(v.lat, v.lng, v.timestamp_start.hour, v.police_station, vehicle_type)
    
    if is_active is not None:
        v.is_active = is_active
        if not is_active:
            v.timestamp_end = datetime.utcnow()
            
    db.commit()
    db.refresh(v)
    return {"status": "updated", "id": v.id, "new_dcli_score": v.dcli_score, "is_active": v.is_active}


@app.delete("/api/violations/{violation_id}")
async def delete_violation(violation_id: int, db=Depends(get_db)):
    """CRUD: Delete a violation."""
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        return {"error": "Violation not found"}
    
    db.delete(v)
    db.commit()
    return {"status": "deleted", "id": violation_id}




# ── TRD Required: Enforcement Priority Queue ──

@app.get("/api/enforcement/queue")
async def get_enforcement_queue(
    limit: int = Query(10), db=Depends(get_db),
):
    """Priority-ranked enforcement dispatch queue — TRD §6.
    Ranks zones by DCLI damage to enable targeted enforcement."""
    zone_analysis = ml_engine.get_zone_analysis()

    queue = []
    for rank, zone in enumerate(zone_analysis[:limit], 1):
        dcli = ml_engine.predict_dcli(
            zone["center_lat"], zone["center_lng"],
            datetime.utcnow().hour, zone["zone"], "CAR"
        )
        queue.append({
            "rank": rank,
            "zone": zone["zone"],
            "lat": zone["center_lat"],
            "lng": zone["center_lng"],
            "risk_level": zone["risk_level"],
            "risk_score": zone["risk_score"],
            "predicted_dcli": dcli,
            "congestion_level": dcli_to_congestion_level(dcli),
            "economic_damage": f"₹{dcli:,.0f}/hr",
            "violations_count": zone["total_violations"],
            "peak_hour": zone["peak_hour"],
            "estimated_savings": round(dcli * 0.6, 2),  # 60% recovery if enforced
            "action": "DISPATCH" if zone["risk_level"] in ("CRITICAL", "HIGH") else "MONITOR",
        })

    total_damage = sum(q["predicted_dcli"] for q in queue)
    total_savings = sum(q["estimated_savings"] for q in queue)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "model": "GBR DCLI Predictor + Zone Risk Classifier",
        "total_zones": len(queue),
        "total_economic_damage": f"₹{total_damage:,.0f}/hr",
        "potential_savings": f"₹{total_savings:,.0f}/hr",
        "queue": queue,
    }


# ── TRD Required: Predictions Heatmap ──

@app.get("/api/predictions/heatmap")
async def get_predictions_heatmap():
    """Predicted violation hotspots for next 24h — TRD §6.
    Combines LSTM forecast + spatial clusters into heatmap grid."""
    forecast = ml_engine.predict_lstm_forecast()
    hotspots = ml_engine.predict_hotspots(hours_ahead=24)
    clusters = ml_engine.zone_clusters or []

    # Build spatial-temporal grid
    heatmap = []
    for hour_data in forecast:
        h = hour_data["hour"]
        hour_hotspots = [p for p in hotspots if p["predicted_hour"] == h]

        if hour_hotspots:
            for hs in hour_hotspots[:3]:
                heatmap.append({
                    "hour": h,
                    "lat": hs["lat"], "lng": hs["lng"],
                    "zone": hs["zone"],
                    "predicted_violations": hour_data["predicted_violations"],
                    "confidence": hs["confidence"],
                    "risk_level": hs["risk_level"],
                    "intensity": round(hs["confidence"] * hour_data["predicted_violations"] / max(1, forecast[0]["predicted_violations"]), 2),
                })
        else:
            # Use top cluster for this hour
            for c in clusters[:2]:
                heatmap.append({
                    "hour": h,
                    "lat": c["lat"], "lng": c["lng"],
                    "zone": c["zone"],
                    "predicted_violations": hour_data["predicted_violations"],
                    "confidence": 0.4,
                    "risk_level": "MEDIUM",
                    "intensity": 0.4,
                })

    return {
        "model": "LSTM + KMeans Spatial-Temporal Heatmap",
        "generated_at": datetime.utcnow().isoformat(),
        "forecast_hours": 24,
        "total_points": len(heatmap),
        "heatmap": heatmap,
    }


# ═══════════════════ WebSocket ═══════════════════

@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_ws.append(ws)
    try:
        await ws.send_json({
            "type": "initial_state",
            "ml_status": "trained" if ml_engine.trained else "training",
            "models_count": 5 if ml_engine.lstm_trained else 4,
            "clusters": ml_engine.zone_clusters or [],
            "graph": city_graph.get_graph_data(),
            "streaming": streaming_active,
        })
        while True:
            data = await ws.receive_text()
            # Handle client commands
            if data == "ping":
                await ws.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        if ws in connected_ws:
            connected_ws.remove(ws)
    except Exception:
        if ws in connected_ws:
            connected_ws.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
