import cv2
import time
import os
from datetime import datetime
from flask import Flask, Response
import logging

# Correctly import modules from the 'src' directory.
from src.detection import detect_persons
from src.tracking import initialize_tracker, update_tracker_with_detections
from src.face_recognition_util import load_known_faces, recognize_face
from src.alerting import trigger_alert, trigger_banned_person_alert
from src.video_stream import VideoStream
from src.event_logger import setup_logger

logger = setup_logger()
app = Flask(__name__)

# --- CONFIGURATION (Unchanged) ---
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720
FRAME_PROCESSING_INTERVAL = 3
RE_RECOGNITION_INTERVAL_FRAMES = 15 
TIME_THRESHOLD_SECONDS = 10.0
TRACK_TTL_SECONDS = 2.0
ZONE_START_X, ZONE_START_Y, ZONE_WIDTH, ZONE_HEIGHT = 0, 0, 350, 720
FORBIDDEN_ZONE = (ZONE_START_X, ZONE_START_Y, ZONE_START_X + ZONE_WIDTH, ZONE_START_Y + ZONE_HEIGHT)
UNKNOWN_SIGHTINGS_DIR = "unknown_person_sightings"
if not os.path.exists(UNKNOWN_SIGHTINGS_DIR): os.makedirs(UNKNOWN_SIGHTINGS_DIR)

# --- GLOBAL INITIALIZATION ---
logger.info("Initializing resources...")
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
tracker = initialize_tracker()
known_face_encodings, known_face_identities = load_known_faces("registered_faces")

logger.info("Starting threaded video stream...")
vs = VideoStream(src=0, width=FRAME_WIDTH, height=FRAME_HEIGHT).start()
time.sleep(2.0)
logger.info("Initialization Complete. Starting Web Server.")

# --- MAIN VIDEO PROCESSING LOGIC (Unchanged) ---
def process_video_frames():
    frame_count = 0
    last_alert_time = 0
    tracked_persons = {}

    while True:
        frame = vs.read()
        if frame is None: break
        frame_count += 1
        current_time = time.time()
        
        if frame_count % FRAME_PROCESSING_INTERVAL == 0:
            processing_frame = frame.copy()
            detections = detect_persons(model, processing_frame)
            tracks = update_tracker_with_detections(tracker, detections, processing_frame)
            
            active_track_ids = set()
            for track in tracks:
                if not track.is_confirmed() or track.time_since_update > 0: continue
                
                track_id, ltrb = track.track_id, track.to_ltrb()
                active_track_ids.add(track_id)

                is_new_person = track_id not in tracked_persons
                if is_new_person:
                    x1, y1, x2, y2 = map(int, ltrb)
                    person_crop = processing_frame[y1:y2, x1:x2]
                    name, status, distance = "Unknown", "unknown", 0.0
                    if person_crop.size > 0:
                        name, status, distance = recognize_face(known_face_encodings, known_face_identities, person_crop)

                    tracked_persons[track_id] = {
                        "box": ltrb, "name": name, "status": status, "distance": distance,
                        "loiter_start_time": None, "alert_triggered": False, "last_seen_time": current_time
                    }
                    log_message = f"Person '{name}' (ID: {track_id}, Status: {status.capitalize()}) detected."
                    if status == 'unknown': logger.warning(log_message)
                    else: logger.info(log_message)
                    
                    if status == 'unknown':
                        try:
                            sighting_filename = os.path.join(UNKNOWN_SIGHTINGS_DIR, f"sighting_id-{track_id}.jpg")
                            cv2.imwrite(sighting_filename, person_crop)
                        except Exception: pass
                
                person_state = tracked_persons[track_id]
                person_state.update({"box": ltrb, "last_seen_time": current_time})

                if person_state["status"] == "unknown" and frame_count % RE_RECOGNITION_INTERVAL_FRAMES == 0 and not is_new_person:
                    x1, y1, x2, y2 = map(int, ltrb)
                    person_crop = processing_frame[y1:y2, x1:x2]
                    if person_crop.size > 0:
                        name, status, dist = recognize_face(known_face_encodings, known_face_identities, person_crop)
                        if status != "unknown":
                            logger.info(f"Person ID {track_id} re-identified as '{name}' (Status: {status.capitalize()}).")
                            person_state.update({"name": name, "status": status, "distance": dist, "loiter_start_time": None, "alert_triggered": False})
                
                person_center_x = (ltrb[0] + ltrb[2]) / 2
                is_in_zone = (person_center_x > FORBIDDEN_ZONE[0] and person_center_x < FORBIDDEN_ZONE[2])

                if is_in_zone and not person_state["alert_triggered"]:
                    status = person_state["status"]
                    if status == "banned":
                        trigger_banned_person_alert(frame, person_state["name"])
                        person_state["alert_triggered"] = True
                    elif status == "unknown":
                        if person_state["loiter_start_time"] is None:
                            person_state["loiter_start_time"] = current_time
                        else:
                            loiter_duration = current_time - person_state["loiter_start_time"]
                            if loiter_duration > TIME_THRESHOLD_SECONDS:
                                last_alert_time = trigger_alert(frame, last_alert_time)
                                person_state["alert_triggered"] = True
                elif not is_in_zone:
                    person_state["loiter_start_time"] = None
            
            inactive_ids = set(tracked_persons.keys()) - active_track_ids
            stale_ids = {tid for tid, p in tracked_persons.items() if current_time - p["last_seen_time"] > TRACK_TTL_SECONDS}
            for inactive_id in inactive_ids.union(stale_ids):
                if inactive_id in tracked_persons: del tracked_persons[inactive_id]
        
        # --- MODIFIED: Drawing Logic with Corrected Color Scheme ---
        for track_id, person in tracked_persons.items():
            x1, y1, x2, y2 = map(int, person["box"])
            status = person["status"]
            label = f"{person['name']} (ID: {track_id})"

            # Set box color based on your specified scheme
            if status == "banned":
                box_color = (0, 165, 255)  # Orange for Banned
            elif status == "allowed" or status == "known":
                box_color = (255, 0, 0)    # Blue for Allowed and Known
            else: # Unknown
                box_color = (0, 255, 0)    # Green for Unknown

            # If unknown is loitering, override color to Red
            if status == "unknown" and person["loiter_start_time"] is not None:
                box_color = (0, 0, 255)    # Red for Loitering
                loiter_duration = current_time - person["loiter_start_time"]
                label += f" | T: {loiter_duration:.0f}s"
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

        # Draw Restricted Zone in Red (Unchanged, already correct)
        cv2.rectangle(frame, (FORBIDDEN_ZONE[0], FORBIDDEN_ZONE[1]), (FORBIDDEN_ZONE[2], FORBIDDEN_ZONE[3]), (0, 0, 255), 2)
        cv2.putText(frame, "Restricted Zone", (FORBIDDEN_ZONE[0] + 10, FORBIDDEN_ZONE[1] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret: yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- FLASK WEB ROUTES (Unchanged) ---
@app.route('/')
def index():
    return f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>AI Surveillance Feed</title>
    <style>
        * {{ box-sizing: border-box; }}
        body{{background-color:#111;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;}}
        .container{{width:{FRAME_WIDTH}px;height:{FRAME_HEIGHT}px;border:2px solid #444;position:relative;}}
        img{{width:100%;height:100%;display:block;}}
        h1{{position:absolute;top:10px;left:10px;color:white;background-color:rgba(0,0,0,0.5);padding:10px;border-radius:5px;font-size:16px;z-index:10;}}
    </style></head>
    <body><div class="container"><h1>AI Surveillance Feed</h1><img src="/video_feed" alt="Live Feed"></div></body></html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(process_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    finally:
        vs.stop()