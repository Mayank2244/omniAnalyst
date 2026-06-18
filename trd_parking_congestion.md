# 🛠️ Technical Requirement Document (TRD) — OmniRoute Analytics

> **Constraint:** 100% Free & Open-Source stack. Zero paid APIs. Python 3.11. MySQL.

---

## 1. System Overview

**Project:** OmniRoute Analytics (Flipkart Gridlock 2.0 Hackathon)
**Objective:** Build a real-time Urban Digital Twin that ingests parking violation + traffic data, calculates the Dynamic Congestion Liability Index (DCLI), predicts congestion propagation via a Spatiotemporal Graph Neural Network (ST-GNN), and serves a SmartPark API for Flipkart delivery fleet optimization.

**Architecture Philosophy:** Microservice-inspired monolith — single deployable FastAPI app with clearly separated internal modules, optimized for hackathon speed while maintaining clean boundaries.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Deck.gl)                   │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ 3D City  │  │ DCLI Live    │  │ SmartPark  │  │ CFO          │  │
│  │ Map View │  │ Ticker Panel │  │ Demo Panel │  │ Dashboard    │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └──────┬───────┘  │
│       └───────────┬────┴────────────────┴─────────────────┘         │
│                   │ WebSocket (ws://localhost:8000/ws/live)          │
└───────────────────┼─────────────────────────────────────────────────┘
                    │
┌───────────────────┼─────────────────────────────────────────────────┐
│                   │          BACKEND (FastAPI + Python 3.11)         │
│  ┌────────────────▼───────────────┐                                 │
│  │       WebSocket Hub            │                                 │
│  │  (broadcasts state to all UIs) │                                 │
│  └────────────────┬───────────────┘                                 │
│       ┌───────────┼───────────┬──────────────┐                      │
│  ┌────▼────┐ ┌────▼────┐ ┌───▼─────┐  ┌─────▼──────┐              │
│  │Ingestion│ │  DCLI   │ │ ST-GNN  │  │ SmartPark  │              │
│  │ Engine  │ │ Scorer  │ │Predictor│  │  Resolver  │              │
│  └────┬────┘ └────┬────┘ └───┬─────┘  └─────┬──────┘              │
│       └───────────┴──────────┴───────────────┘                      │
│                           │                                         │
│                    ┌──────▼──────┐                                   │
│                    │    MySQL    │                                   │
│                    │  Database   │                                   │
│                    └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
                    │
┌───────────────────┼─────────────────────────────────────────────────┐
│          EDGE CV LAYER (Optional Demo)                              │
│  ┌────────────────▼───────────────┐                                 │
│  │  YOLOv8-nano on local webcam   │                                 │
│  │  Detects parked vehicles →     │                                 │
│  │  POSTs to /api/events/violation│                                 │
│  └────────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack (100% Free / Open-Source)

| Layer | Technology | Version | Cost | Why This Choice |
|---|---|---|---|---|
| **Language** | Python | 3.11 | Free | Async perf, ML ecosystem, strict typing |
| **Backend Framework** | FastAPI | 0.110+ | Free | Native async, WebSocket support, auto-docs |
| **Database** | MySQL | 8.0+ | Free | Open source, runs locally or via free Aiven tier |
| **ORM** | SQLAlchemy + PyMySQL | 2.0+ | Free | Async MySQL driver, type-safe queries |
| **Frontend** | React.js (Vite) | 18+ | Free | Fast dev server, component-based UI |
| **3D Visualization** | Deck.gl + OpenStreetMap tiles | Latest | Free | No API key needed with free tile servers |
| **ML Framework** | PyTorch | 2.0+ | Free | ST-GNN implementation |
| **ML Fallback** | scikit-learn / XGBoost | Latest | Free | Lightweight alternative if ST-GNN is too slow |
| **Edge CV** | YOLOv8-nano (Ultralytics) | Latest | Free | Runs on CPU, no GPU required |
| **Data Processing** | Pandas + GeoPandas | Latest | Free | Spatial data wrangling |
| **Graph Library** | NetworkX + PyTorch Geometric | Latest | Free | City graph construction + GNN training |
| **Charts** | Recharts (React) | Latest | Free | CFO Dashboard charts |
| **Map Tiles** | OpenStreetMap / CartoDB Positron | N/A | Free | Zero API cost basemaps |
| **Hosting (Frontend)** | Vercel | Free Tier | Free | Auto-deploy from GitHub |
| **Hosting (Backend)** | Render / Local | Free Tier | Free | Or just run locally for demo |

**Total Cost: ₹0**

---

## 4. MySQL Database Schema

### 4.1. Entity Relationship

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  road_nodes  │       │   road_edges     │       │  violations      │
│──────────────│       │──────────────────│       │──────────────────│
│ id (PK)      │◄──┐   │ id (PK)          │   ┌──►│ id (PK)          │
│ lat          │   │   │ from_node (FK)   │───┘   │ edge_id (FK)     │
│ lng          │   │   │ to_node (FK)     │       │ lat              │
│ intersection │   │   │ road_name        │       │ lng              │
│ _name        │   └───│ length_m         │       │ vehicle_id       │
│ criticality  │       │ lanes            │       │ vehicle_type     │
│ _score       │       │ free_flow_speed  │       │ timestamp_start  │
└──────────────┘       │ current_speed    │       │ timestamp_end    │
                       │ congestion_level │       │ dcli_score       │
                       └──────────────────┘       │ is_active        │
                                                  └──────────────────┘

┌──────────────────┐       ┌──────────────────────┐
│ enforcement_     │       │ smartpark_requests    │
│ dispatches       │       │──────────────────────│
│──────────────────│       │ id (PK)              │
│ id (PK)          │       │ vehicle_id           │
│ violation_id(FK) │       │ requested_lat        │
│ dispatched_at    │       │ requested_lng        │
│ priority_rank    │       │ duration_mins        │
│ estimated_savings│       │ recommended_lat      │
│ status           │       │ recommended_lng      │
└──────────────────┘       │ dcli_impact_saved    │
                           │ created_at           │
                           └──────────────────────┘
```

### 4.2. DDL (MySQL 8.0)

```sql
CREATE DATABASE IF NOT EXISTS omniroute;
USE omniroute;

-- City road network nodes (intersections)
CREATE TABLE road_nodes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    lat             DECIMAL(10, 7) NOT NULL,
    lng             DECIMAL(10, 7) NOT NULL,
    intersection_name VARCHAR(255),
    criticality_score FLOAT DEFAULT 1.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_coords (lat, lng)
);

-- City road network edges (road segments)
CREATE TABLE road_edges (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    from_node_id    INT NOT NULL,
    to_node_id      INT NOT NULL,
    road_name       VARCHAR(255),
    length_m        FLOAT NOT NULL,
    lanes           INT DEFAULT 2,
    free_flow_speed FLOAT NOT NULL COMMENT 'km/h with no congestion',
    current_speed   FLOAT COMMENT 'km/h real-time',
    congestion_level ENUM('free', 'moderate', 'heavy', 'gridlock') DEFAULT 'free',
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (from_node_id) REFERENCES road_nodes(id),
    FOREIGN KEY (to_node_id)   REFERENCES road_nodes(id),
    INDEX idx_congestion (congestion_level)
);

-- Parking violations (core event table)
CREATE TABLE violations (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    edge_id         INT NOT NULL,
    lat             DECIMAL(10, 7) NOT NULL,
    lng             DECIMAL(10, 7) NOT NULL,
    vehicle_id      VARCHAR(20) NOT NULL,
    vehicle_type    ENUM('private', 'commercial', 'two_wheeler') DEFAULT 'private',
    timestamp_start DATETIME NOT NULL,
    timestamp_end   DATETIME,
    dcli_score      FLOAT DEFAULT 0.0 COMMENT 'Rupees per hour economic damage',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (edge_id) REFERENCES road_edges(id),
    INDEX idx_active (is_active),
    INDEX idx_time (timestamp_start)
);

-- Enforcement dispatch log
CREATE TABLE enforcement_dispatches (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    violation_id    INT NOT NULL,
    dispatched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority_rank   INT NOT NULL,
    estimated_savings FLOAT COMMENT 'Estimated rupees saved by resolving this',
    status          ENUM('dispatched', 'en_route', 'resolved', 'cancelled') DEFAULT 'dispatched',
    resolved_at     TIMESTAMP NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id)
);

-- SmartPark (V2I) request/response log
CREATE TABLE smartpark_requests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id      VARCHAR(50) NOT NULL,
    requested_lat   DECIMAL(10, 7) NOT NULL,
    requested_lng   DECIMAL(10, 7) NOT NULL,
    duration_mins   INT NOT NULL DEFAULT 3,
    recommended_lat DECIMAL(10, 7),
    recommended_lng DECIMAL(10, 7),
    dcli_impact_saved FLOAT COMMENT 'Rupees saved vs worst-case parking',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prediction log (ST-GNN outputs)
CREATE TABLE congestion_predictions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    trigger_violation_id INT NOT NULL,
    edge_id         INT NOT NULL,
    predicted_speed FLOAT NOT NULL,
    predicted_congestion ENUM('free', 'moderate', 'heavy', 'gridlock'),
    prediction_time DATETIME NOT NULL COMMENT 'The future time this prediction is for',
    confidence      FLOAT DEFAULT 0.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_violation_id) REFERENCES violations(id),
    FOREIGN KEY (edge_id) REFERENCES road_edges(id)
);
```

---

## 5. Core Modules — Technical Specification

### Module 1: Ingestion Engine (`/app/ingestion/`)

**Purpose:** Replays CSV dataset as a real-time event stream and persists events to MySQL.

```python
# Pseudocode — Python 3.11 asyncio
async def stream_csv(filepath: str, speed_multiplier: float = 10.0):
    """Reads CSV rows sorted by timestamp, emits them at accelerated real-time pace."""
    df = pd.read_csv(filepath, parse_dates=["timestamp_start"])
    df = df.sort_values("timestamp_start")
    
    for i, row in df.iterrows():
        event = ViolationEvent(
            lat=row.lat, lng=row.lng,
            vehicle_id=row.vehicle_id,
            timestamp=row.timestamp_start
        )
        await persist_to_mysql(event)       # Write to violations table
        dcli = compute_dcli(event)          # Score it
        predictions = predict_propagation(event)  # ST-GNN forward pass
        await websocket_hub.broadcast({
            "type": "new_violation",
            "event": event.dict(),
            "dcli": dcli,
            "propagation": predictions
        })
        await asyncio.sleep(time_delta / speed_multiplier)
```

### Module 2: DCLI Scoring Algorithm (`/app/dcli/`)

**Purpose:** Computes real-time economic impact score for each violation.

**Inputs:**
- Violation location (lat/lng → mapped to nearest `road_edge`)
- Current traffic speed on that edge vs free-flow speed
- Road criticality (betweenness centrality of the edge in the city graph)
- Time of day

**Algorithm:**
```python
def compute_dcli(violation: Violation, graph: CityGraph) -> float:
    edge = graph.nearest_edge(violation.lat, violation.lng)
    
    # Base delay: how much this violation slows traffic
    speed_reduction = edge.free_flow_speed - edge.current_speed
    vehicles_per_hour = edge.traffic_volume  # estimated from historical data
    avg_delay_minutes = speed_reduction / edge.free_flow_speed * edge.length_m / 1000 * 60
    
    # Economic value of delay (₹2/min/vehicle — conservative estimate)
    base_cost = vehicles_per_hour * avg_delay_minutes * 2.0
    
    # Road criticality — betweenness centrality normalized to [1, 100]
    criticality = graph.betweenness_centrality(edge.id)  # 1x to 100x
    
    # Time-of-day multiplier
    hour = violation.timestamp.hour
    time_mult = 3.0 if 8 <= hour <= 10 or 17 <= hour <= 20 else 1.0
    
    dcli = base_cost * criticality * time_mult
    return round(dcli, 2)
```

**Output:** `dcli_score` (₹/hour) persisted to `violations.dcli_score`.

### Module 3: ST-GNN Propagation Predictor (`/app/model/`)

**Purpose:** Predicts how congestion from a violation will ripple through the road network over the next 15 minutes.

**Architecture (Lightweight, hackathon-safe):**
```
Input: [N × F × T] tensor
  N = number of road nodes
  F = features per node (current_speed, free_flow_speed, active_violations, centrality)
  T = last 6 time steps (5-min intervals = 30 min history)

Model:
  → Graph Convolution (GCN layer, captures spatial adjacency)
  → Temporal Convolution (1D Conv, captures time trends)
  → Fully Connected → Output: predicted speed for each edge at T+5, T+10, T+15

Training Data: Historical traffic + violation data (or synthetic if unavailable)
Framework: PyTorch Geometric
Fallback: If training time is too long → use XGBoost with hand-crafted graph features
```

### Module 4: SmartPark Resolver (`/app/smartpark/`)

**Purpose:** Recommends lowest-impact parking zones for delivery vehicles.

**Algorithm:**
```python
def recommend_parking(lat: float, lng: float, duration_mins: int) -> list[ParkingSpot]:
    """Find top-3 nearby spots where parking causes minimum DCLI impact."""
    candidate_edges = graph.edges_within_radius(lat, lng, radius_m=200)
    
    scored = []
    for edge in candidate_edges:
        # Simulate: "what if a vehicle parks here for N minutes?"
        simulated_dcli = compute_dcli_simulated(edge, duration_mins)
        scored.append(ParkingSpot(
            lat=edge.midpoint_lat,
            lng=edge.midpoint_lng,
            dcli_impact=simulated_dcli,
            road_name=edge.road_name
        ))
    
    # Return top 3 lowest-impact spots
    return sorted(scored, key=lambda s: s.dcli_impact)[:3]
```

### Module 5: Predictive Heat Calendar (`/app/predictions/`)

**Purpose:** Forecasts violation hotspots for the next 24 hours using historical patterns.

**Algorithm:** Time-series clustering on historical violations grouped by (hour_of_day, day_of_week, zone). Uses scikit-learn KMeans + simple regression. Outputs a JSON heatmap for the frontend.

---

## 6. API Specifications

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/events/violation` | Ingest a new parking violation |
| `GET` | `/api/violations/active` | List all currently active violations with DCLI scores |
| `GET` | `/api/map/state` | Full city graph state (edges + congestion levels) |
| `GET` | `/api/smartpark/recommend` | SmartPark: get best parking spots |
| `GET` | `/api/enforcement/queue` | Priority-ranked enforcement dispatch queue |
| `GET` | `/api/dashboard/summary` | CFO Dashboard: today's stats, savings, hotspots |
| `GET` | `/api/predictions/heatmap` | Predicted violation hotspots for next 24h |

### WebSocket

| Endpoint | Description |
|---|---|
| `WS /ws/live` | Streams: new violations, DCLI updates, propagation predictions, enforcement dispatches |

### Sample Payloads

**POST `/api/events/violation`**
```json
{
  "vehicle_id": "KA-01-AB-1234",
  "vehicle_type": "commercial",
  "location": { "lat": 12.9716, "lng": 77.5946 },
  "timestamp": "2026-06-17T10:00:00Z"
}
```

**GET `/api/smartpark/recommend?lat=12.97&lng=77.59&duration_mins=3`**
```json
{
  "recommendations": [
    { "lat": 12.9705, "lng": 77.5938, "road": "5th Cross Road", "dcli_impact": 12.50 },
    { "lat": 12.9712, "lng": 77.5951, "road": "Service Lane A",  "dcli_impact": 45.80 },
    { "lat": 12.9720, "lng": 77.5960, "road": "Park Avenue",     "dcli_impact": 89.20 }
  ]
}
```

**GET `/api/dashboard/summary`**
```json
{
  "date": "2026-06-17",
  "active_violations": 47,
  "total_dcli_damage_today": 284500.00,
  "enforcements_dispatched": 12,
  "estimated_savings": 156200.00,
  "top_chronic_zones": [
    { "zone": "MG Road - Brigade Junction", "monthly_cost": 2100000 },
    { "zone": "Silk Board Flyover",         "monthly_cost": 1850000 }
  ]
}
```

---

## 7. Frontend Component Architecture

```
src/
├── App.jsx                     # Main layout, WebSocket connection
├── components/
│   ├── CityMap/
│   │   ├── CityMap.jsx         # Deck.gl + OpenStreetMap 3D map
│   │   ├── ViolationLayer.jsx  # Red dots with DCLI labels
│   │   ├── PropagationLayer.jsx# Animated shockwave arcs
│   │   └── SmartParkLayer.jsx  # Green/red zone overlays
│   ├── Dashboard/
│   │   ├── DCLITicker.jsx      # Live ₹ ticking counter
│   │   ├── EnforcementQueue.jsx# Priority dispatch list
│   │   ├── CFOPanel.jsx        # Summary stats + charts
│   │   └── HeatCalendar.jsx    # Predicted hotspot timeline
│   └── SmartPark/
│       └── SmartParkDemo.jsx   # Flipkart van simulation panel
├── hooks/
│   ├── useWebSocket.js         # WebSocket connection manager
│   └── useMapState.js          # Map state store (Zustand)
├── utils/
│   └── colorScale.js           # DCLI → color gradient mapping
└── styles/
    └── index.css               # Dark mode, glassmorphism, animations
```

---

## 8. Project Directory Structure

```
OmniRoute-Analytics/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # DB connection, env vars
│   │   ├── models/
│   │   │   └── db_models.py    # SQLAlchemy ORM models
│   │   ├── ingestion/
│   │   │   └── stream.py       # CSV → real-time event streamer
│   │   ├── dcli/
│   │   │   └── scorer.py       # DCLI computation engine
│   │   ├── model/
│   │   │   ├── graph.py        # City graph (NetworkX)
│   │   │   ├── stgnn.py        # ST-GNN model (PyTorch Geometric)
│   │   │   └── fallback.py     # XGBoost fallback predictor
│   │   ├── smartpark/
│   │   │   └── resolver.py     # V2I parking recommendation
│   │   ├── predictions/
│   │   │   └── heatmap.py      # Predictive heat calendar
│   │   ├── routes/
│   │   │   ├── events.py       # /api/events/* endpoints
│   │   │   ├── map.py          # /api/map/* endpoints
│   │   │   ├── smartpark.py    # /api/smartpark/* endpoints
│   │   │   ├── dashboard.py    # /api/dashboard/* endpoints
│   │   │   └── ws.py           # WebSocket handler
│   │   └── utils/
│   │       └── geo.py          # Geospatial helpers
│   ├── data/
│   │   └── sample_violations.csv
│   ├── requirements.txt
│   └── Dockerfile              # Optional containerization
├── frontend/
│   ├── src/                    # (See component architecture above)
│   ├── package.json
│   └── vite.config.js
├── edge_cv/
│   └── detect.py               # YOLOv8-nano webcam script
├── scripts/
│   ├── init_db.sql             # MySQL schema initialization
│   └── seed_data.py            # Populate mock road network
├── docs/
│   ├── prd_parking_congestion.md
│   └── trd_parking_congestion.md
└── README.md
```

---

## 9. Development Milestones (48 Hours)

| Phase | Hours | Deliverable | Owner Focus |
|---|---|---|---|
| **1 — Foundation** | 0-6 | MySQL schema live. FastAPI skeleton running. CSV data cleaned. | Backend |
| **2 — Core Engine** | 6-14 | Ingestion engine streaming events. DCLI scorer functional. City graph built in NetworkX. | Backend + Data |
| **3 — Intelligence** | 14-22 | ST-GNN or XGBoost predictor trained on sample data. Propagation predictions flowing via WebSocket. | ML |
| **4 — Visualization** | 14-22 | Deck.gl 3D map rendering with dark mode, violation dots, DCLI labels, shockwave animations. | Frontend |
| **5 — Integration** | 22-32 | Full pipeline connected: violation → DCLI → prediction → WebSocket → map update. SmartPark API live. | Full-stack |
| **6 — Dashboard** | 32-40 | CFO Dashboard, Enforcement Queue, Heat Calendar, SmartPark demo panel. | Frontend |
| **7 — Polish & Pitch** | 40-48 | Edge CV demo. UI micro-animations. Demo script rehearsed. Pitch deck finalized. | Everyone |

---

## 10. Risk Mitigation

| Risk | Mitigation |
|---|---|
| ST-GNN too complex to train in 48h | XGBoost fallback with hand-crafted graph features (betweenness centrality, degree, historical speed) |
| No real traffic data for training | Generate synthetic data using statistical distributions from open TomTom speed data |
| MySQL latency for real-time queries | Keep active violations in-memory (Python dict), persist to MySQL async |
| Deck.gl rendering performance | Limit visible violations to top-100 by DCLI score; use level-of-detail rendering |
| Team member unavailability | Each module is independently testable with mock data |
