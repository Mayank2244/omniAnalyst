-- ============================================
-- OmniRoute Analytics — MySQL Schema
-- Run this in MySQL Workbench to create the DB
-- ============================================

CREATE DATABASE IF NOT EXISTS omniroute;
USE omniroute;

-- City road network nodes (intersections)
CREATE TABLE IF NOT EXISTS road_nodes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    lat             DECIMAL(10, 7) NOT NULL,
    lng             DECIMAL(10, 7) NOT NULL,
    intersection_name VARCHAR(255) DEFAULT '',
    criticality_score FLOAT DEFAULT 1.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_coords (lat, lng)
) ENGINE=InnoDB;

-- City road network edges (road segments)
CREATE TABLE IF NOT EXISTS road_edges (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    from_node_id    INT NOT NULL,
    to_node_id      INT NOT NULL,
    road_name       VARCHAR(255) DEFAULT '',
    length_m        FLOAT NOT NULL DEFAULT 100.0,
    lanes           INT DEFAULT 2,
    free_flow_speed FLOAT NOT NULL DEFAULT 40.0,
    current_speed   FLOAT DEFAULT 40.0,
    congestion_level VARCHAR(20) DEFAULT 'free',
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (from_node_id) REFERENCES road_nodes(id),
    FOREIGN KEY (to_node_id)   REFERENCES road_nodes(id),
    INDEX idx_congestion (congestion_level)
) ENGINE=InnoDB;

-- Parking violations (core event table)
CREATE TABLE IF NOT EXISTS violations (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    edge_id         INT,
    lat             DECIMAL(10, 7) NOT NULL,
    lng             DECIMAL(10, 7) NOT NULL,
    location_text   TEXT,
    vehicle_id      VARCHAR(50) NOT NULL,
    vehicle_type    VARCHAR(30) DEFAULT 'private',
    violation_type  TEXT,
    timestamp_start DATETIME NOT NULL,
    timestamp_end   DATETIME,
    dcli_score      FLOAT DEFAULT 0.0,
    is_active       BOOLEAN DEFAULT TRUE,
    police_station  VARCHAR(100) DEFAULT '',
    junction_name   VARCHAR(255) DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (edge_id) REFERENCES road_edges(id),
    INDEX idx_active (is_active),
    INDEX idx_time (timestamp_start),
    INDEX idx_dcli (dcli_score)
) ENGINE=InnoDB;

-- Enforcement dispatch log
CREATE TABLE IF NOT EXISTS enforcement_dispatches (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    violation_id    INT NOT NULL,
    dispatched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority_rank   INT NOT NULL,
    estimated_savings FLOAT DEFAULT 0.0,
    status          VARCHAR(20) DEFAULT 'dispatched',
    resolved_at     TIMESTAMP NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id)
) ENGINE=InnoDB;

-- SmartPark (V2I) request/response log
CREATE TABLE IF NOT EXISTS smartpark_requests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id      VARCHAR(50) NOT NULL,
    requested_lat   DECIMAL(10, 7) NOT NULL,
    requested_lng   DECIMAL(10, 7) NOT NULL,
    duration_mins   INT NOT NULL DEFAULT 3,
    recommended_lat DECIMAL(10, 7),
    recommended_lng DECIMAL(10, 7),
    dcli_impact_saved FLOAT DEFAULT 0.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ST-GNN prediction log
CREATE TABLE IF NOT EXISTS congestion_predictions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    trigger_violation_id INT NOT NULL,
    edge_id         INT NOT NULL,
    predicted_speed FLOAT NOT NULL,
    predicted_congestion VARCHAR(20) DEFAULT 'free',
    prediction_time DATETIME NOT NULL,
    confidence      FLOAT DEFAULT 0.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_violation_id) REFERENCES violations(id),
    FOREIGN KEY (edge_id) REFERENCES road_edges(id)
) ENGINE=InnoDB;

SELECT 'OmniRoute Analytics database created successfully!' AS status;
