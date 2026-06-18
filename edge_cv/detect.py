import cv2
import requests
import time
import random
import argparse
import sys
import os
from ultralytics import YOLO

# ── OmniRoute Edge CV Layer (YOLOv8-nano) ── #
# This script simulates an edge camera running YOLOv8 locally on an uploaded image.
# When a vehicle is detected, it sends an event to the FastApi backend.

API_URL = "http://localhost:8000/api/events/violation"
ZONE_NAME = "ImageUpload_Zone_01"

# YOLO COCO class IDs for vehicles:
# 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASSES = {2: 'car', 3: 'two_wheeler', 5: 'bus', 7: 'commercial'}

def main():
    parser = argparse.ArgumentParser(description="OmniRoute Edge CV Image Detector")
    parser.add_argument("image_path", help="Path to the image file to analyze")
    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        print(f"[ERROR] File not found: {args.image_path}")
        sys.exit(1)

    print("[INFO] Loading YOLOv8-nano model...")
    model = YOLO('yolov8n.pt')

    print(f"[INFO] Analyzing image: {args.image_path}")
    frame = cv2.imread(args.image_path)
    
    if frame is None:
        print("[ERROR] Could not read image.")
        sys.exit(1)

    # Run YOLOv8 inference on the frame
    results = model(frame, verbose=False)
    
    detected_vehicles = []
    
    for result in results:
        boxes = result.boxes
        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            
            # If it's a vehicle and confidence is > 40%
            if cls_id in VEHICLE_CLASSES and conf > 0.4:
                v_type = VEHICLE_CLASSES[cls_id]
                detected_vehicles.append((v_type, conf))
                
                # Draw bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"{v_type} {conf:.2f}", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if not detected_vehicles:
        print("[INFO] No illegally parked vehicles detected in this image.")
    else:
        print(f"\n[ALERT] Detected {len(detected_vehicles)} vehicles!")
        
        # We send the primary detected vehicle to the backend for the demo
        primary_vehicle = detected_vehicles[0][0]
        print(f"[API] Sending {primary_vehicle.upper()} violation to OmniRoute API...")
        
        # Simulate coordinates near the center of our map
        sim_lat = 12.975 + random.uniform(-0.01, 0.01)
        sim_lng = 77.575 + random.uniform(-0.01, 0.01)
        
        try:
            res = requests.post(
                f"{API_URL}",
                params={
                    "vehicle_id": f"IMG-{int(time.time())}",
                    "vehicle_type": primary_vehicle.upper(),
                    "lat": sim_lat,
                    "lng": sim_lng,
                    "zone": ZONE_NAME
                }
            )
            print(f"[API] Success: {res.json()}")
        except Exception as e:
            print(f"[API] Failed to connect to backend: {e}")

    print("\n[INFO] Displaying results. Press any key in the image window to close.")
    
    # Scale down if image is too large to fit on screen
    h, w = frame.shape[:2]
    if w > 1200 or h > 800:
        scale = min(1200/w, 800/h)
        frame = cv2.resize(frame, (int(w*scale), int(h*scale)))
        
    cv2.imshow("OmniRoute Edge CV - Image Analysis", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
