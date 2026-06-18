"""
OmniRoute Analytics — SQLAlchemy ORM Models
Mapped to the omniroute MySQL database (TRD schema).
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, DECIMAL, TIMESTAMP,
    create_engine, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

from app.config import DATABASE_URL, USE_SQLITE

Base = declarative_base()


class RoadNode(Base):
    __tablename__ = "road_nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lat = Column(DECIMAL(10, 7), nullable=False)
    lng = Column(DECIMAL(10, 7), nullable=False)
    intersection_name = Column(String(255))
    criticality_score = Column(Float, default=1.0)
    created_at = Column(TIMESTAMP, server_default=func.now())


class RoadEdge(Base):
    __tablename__ = "road_edges"
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(Integer, ForeignKey("road_nodes.id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("road_nodes.id"), nullable=False)
    road_name = Column(String(255))
    length_m = Column(Float, nullable=False)
    lanes = Column(Integer, default=2)
    free_flow_speed = Column(Float, nullable=False)
    current_speed = Column(Float)
    congestion_level = Column(String(20), default="free")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Violation(Base):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    edge_id = Column(Integer, ForeignKey("road_edges.id"), nullable=True)
    lat = Column(DECIMAL(10, 7), nullable=False)
    lng = Column(DECIMAL(10, 7), nullable=False)
    location_text = Column(Text)
    vehicle_id = Column(String(50), nullable=False)
    vehicle_type = Column(String(30), default="CAR")
    violation_type = Column(Text)
    timestamp_start = Column(DateTime, nullable=False)
    timestamp_end = Column(DateTime)
    dcli_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    police_station = Column(String(100))
    junction_name = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())


class EnforcementDispatch(Base):
    __tablename__ = "enforcement_dispatches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    violation_id = Column(Integer, ForeignKey("violations.id"), nullable=False)
    dispatched_at = Column(TIMESTAMP, server_default=func.now())
    priority_rank = Column(Integer, nullable=False)
    estimated_savings = Column(Float, default=0.0)
    status = Column(String(20), default="dispatched")
    resolved_at = Column(TIMESTAMP)


class SmartParkRequest(Base):
    __tablename__ = "smartpark_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(50), nullable=False)
    requested_lat = Column(DECIMAL(10, 7), nullable=False)
    requested_lng = Column(DECIMAL(10, 7), nullable=False)
    duration_mins = Column(Integer, nullable=False, default=3)
    recommended_lat = Column(DECIMAL(10, 7))
    recommended_lng = Column(DECIMAL(10, 7))
    dcli_impact_saved = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP, server_default=func.now())


class CongestionPrediction(Base):
    __tablename__ = "congestion_predictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_violation_id = Column(Integer, ForeignKey("violations.id"), nullable=False)
    edge_id = Column(Integer, ForeignKey("road_edges.id"), nullable=False)
    predicted_speed = Column(Float, nullable=False)
    predicted_congestion = Column(String(20))
    prediction_time = Column(DateTime, nullable=False)
    confidence = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP, server_default=func.now())


# ── Engine ──
connect_args = {"check_same_thread": False} if USE_SQLITE else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_all_tables():
    """Auto-create all tables from ORM models (safe: IF NOT EXISTS semantics)."""
    Base.metadata.create_all(bind=engine)
    print("  ✅ All tables verified/created via SQLAlchemy.")


def init_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print("  ✅ MySQL (omniroute) connection verified.")
    create_all_tables()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
