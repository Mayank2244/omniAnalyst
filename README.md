# 🛣️ OmniRoute Analytics

### AI-Powered Urban Digital Twin for Congestion Intelligence

> **Flipkart Gridlock 2.0 Hackathon** — Predict. Quantify. Re-Route.

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue.svg)](https://react.dev)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://mysql.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Problem Statement

Illegal parking in Bangalore costs the city **₹2.84 Lakh+ per hour** in economic damage through cascading traffic congestion. Current enforcement is reactive, untargeted, and unable to quantify the downstream ripple effects.

## 💡 Our Solution

**OmniRoute Analytics** is a real-time Urban Digital Twin that:

1. **Ingests** parking violation data (500K+ real records from Bangalore PD)
2. **Scores** each violation with DCLI (Dynamic Congestion Liability Index) — economic damage in ₹/hour
3. **Predicts** congestion propagation using trained ML models (LSTM + GradientBoosting)
4. **Optimizes** Flipkart delivery fleet parking via SmartPark V2I API
5. **Visualizes** everything on a live 3D Deck.gl city map

**Total Cost: ₹0** — 100% free & open-source stack.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Deck.gl + Recharts)            │
│   3D City Map │ DCLI Live Ticker │ SmartPark Demo │ CFO Dashboard   │
└───────────────────────┬─────────────────────────────────────────────┘
                        │ REST + WebSocket
┌───────────────────────┼─────────────────────────────────────────────┐
│                       │       BACKEND (FastAPI + Python 3.11)       │
│   Ingestion Engine  ←─┤─→  DCLI Scorer  ←→  ML Predictor           │
│   (CSV Replay)        │    (OSM-powered)     (LSTM + GBR)           │
│                       │                                             │
│   SmartPark Resolver ←┘─→  City Graph (NetworkX)                   │
│                              │                                      │
│                        ┌─────▼─────┐                                │
│                        │   MySQL   │                                │
│                        └───────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│              EDGE CV (YOLOv8-nano) — Optional Demo                  │
│              Detects vehicles → POSTs to /api/events/violation       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 ML Models (Trained on Real Data)

| # | Model | Type | Purpose |
|---|---|---|---|
| 1 | **Hotspot Clustering** | KMeans | Identifies spatial violation clusters |
| 2 | **Zone Risk Scorer** | Statistical | Ranks zones by historical danger level |
| 3 | **DCLI Predictor** | GradientBoosting | Predicts economic damage for new violations |
| 4 | **Congestion Forecaster** | LSTM (PyTorch) | 24-hour violation count forecast |
| 5 | **Temporal Analyzer** | Pattern Analysis | Peak hours, daily/weekly trends |

All models train on **20,000 real violation records** at startup — no pre-trained weights needed.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MySQL 8.0+ (running locally)

### One-Command Start
```bash
chmod +x run.sh
./run.sh
```

### Manual Setup

#### 1. Database
```sql
CREATE DATABASE IF NOT EXISTS omniroute;
```
Then run the schema:
```bash
mysql -u root -p omniroute < backend/scripts/init_db.sql
```

#### 2. Backend
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env
cp .env.example .env  # Edit with your MySQL credentials

# Seed database
cd ..
python scripts/seed_data.py

# Start server
cd backend
uvicorn app.main:app --reload --port 8000
```

#### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

#### 4. Edge CV (Optional)
```bash
cd edge_cv
python detect.py path/to/image.jpg
```

### Access Points
| Service | URL |
|---|---|
| **Frontend Dashboard** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **WebSocket** | ws://localhost:8000/ws/live |

---

## 📡 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/events/violation` | Ingest a new parking violation |
| `GET` | `/api/violations/active` | List active violations with DCLI scores |
| `GET` | `/api/map/state` | Full city graph state |
| `GET` | `/api/smartpark/recommend` | SmartPark: find lowest-impact parking |
| `GET` | `/api/enforcement/queue` | Priority-ranked enforcement queue |
| `GET` | `/api/dashboard/summary` | CFO Dashboard stats |
| `GET` | `/api/predictions/heatmap` | 24h predicted violation heatmap |
| `GET` | `/api/ml/forecast` | LSTM 24h forecast |
| `GET` | `/api/ml/zones` | Zone risk analysis |
| `GET` | `/api/ml/temporal` | Temporal patterns |
| `GET` | `/api/ml/predict/dcli` | Predict DCLI for a location |
| `POST` | `/api/stream/start` | Start live CSV replay |
| `POST` | `/api/stream/stop` | Stop live streaming |

### WebSocket
```
WS ws://localhost:8000/ws/live
← initial_state (clusters, graph, ml_status)
← new_violation (live events during streaming)
```

### Example: SmartPark
```bash
curl "http://localhost:8000/api/smartpark/recommend?lat=12.97&lng=77.59&duration_mins=3"
```
```json
{
  "recommendations": [
    { "lat": 12.9705, "lng": 77.5938, "dcli_impact": 12.50, "zone_safety": "safe" },
    { "lat": 12.9712, "lng": 77.5951, "dcli_impact": 45.80, "zone_safety": "caution" }
  ]
}
```

---

## 📂 Project Structure

```
OmniRoute-Analytics/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app (all routes)
│   │   ├── config.py            # DB config, env vars
│   │   ├── models/db_models.py  # SQLAlchemy ORM models
│   │   ├── ingestion/stream.py  # CSV → event streamer
│   │   ├── dcli/scorer.py       # DCLI computation engine
│   │   ├── dcli/traffic_api.py  # OSM road data integration
│   │   ├── model/graph.py       # City graph (NetworkX)
│   │   ├── ml/trainer.py        # ML training (KMeans, GBR, LSTM)
│   │   ├── smartpark/resolver.py# V2I parking recommendation
│   │   └── predictions/heatmap.py
│   ├── scripts/init_db.sql      # MySQL schema
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Full dashboard with Deck.gl
│   │   ├── index.css            # White premium design system
│   │   ├── hooks/useWebSocket.js
│   │   └── utils/colorScale.js
│   ├── package.json
│   └── vite.config.js
├── edge_cv/
│   ├── detect.py                # YOLOv8-nano vehicle detector
│   └── yolov8n.pt
├── scripts/
│   └── seed_data.py             # Database seeder
├── run.sh                       # One-command startup
└── README.md
```

---

## 🔬 Key Innovation: DCLI (Dynamic Congestion Liability Index)

```
DCLI = Base_Impact × Road_Criticality × Time_Multiplier × Severity × Junction_Bonus × Lane_Blockage × Congestion_Penalty
```

- **Base Impact**: Vehicle type damage (bus > truck > car > auto > scooter)
- **Road Criticality**: Betweenness centrality from NetworkX graph (1-100)
- **Time Multiplier**: 3x during rush hour (8-10am, 5-8pm)
- **Severity**: Violation type (junction blocking = 3x, main road = 2.5x)
- **Lane Blockage**: 1/lanes (blocking 50% of 2-lane road > 25% of 4-lane)
- **Congestion Penalty**: Real-time speed reduction from OSM data

---

## 🏆 Hackathon Differentiators

1. **Real ML Models** — Not just visualizations. 4 production models trained on 20K real records.
2. **DCLI Innovation** — Novel economic scoring metric that quantifies parking violations in ₹/hour.
3. **SmartPark V2I** — Actionable API for Flipkart fleet: "Park here, not there" with economic justification.
4. **Real Road Data** — OSM-powered lane counts, speed limits, and road classification.
5. **LSTM Forecasting** — PyTorch deep learning predicts violation patterns 24 hours ahead.
6. **Edge CV** — YOLOv8-nano runs on CPU, detects vehicles from images and feeds the pipeline.
7. **Full-Stack** — 3D Deck.gl map, WebSocket live updates, MySQL persistence, FastAPI async backend.

---

## 👥 Team

Built for **Flipkart Gridlock 2.0 Hackathon**

## 📄 License

MIT License — Free for educational and commercial use.
