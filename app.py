import cv2
import time
from flask import Flask, Response

# Correctly import modules from the 'src' directory.
from src.detection import detect_persons
from src.tracking import initialize_tracker, update_tracker_with_detections
from src.face_recognition_util import load_known_faces, recognize_face
from src.alerting import trigger_alert
from src.video_stream import VideoStream

# --- 1. APPLICATION SETUP ---
app = Flask(__name__)

# --- 2. CONFIGURATION ---
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720
TIME_THRESHOLD_SECONDS = 10.0
FRAME_PROCESSING_INTERVAL = 3
RE_RECOGNITION_INTERVAL_FRAMES = 15
# --- NEW: Time To Live (TTL) for tracks without updates ---
TRACK_TTL_SECONDS = 2.0 
ZONE_START_X, ZONE_START_Y, ZONE_WIDTH, ZONE_HEIGHT = 0, 0, 350, 720
FORBIDDEN_ZONE = (ZONE_START_X, ZONE_START_Y, ZONE_START_X + ZONE_WIDTH, ZONE_START_Y + ZONE_HEIGHT)

# --- 3. GLOBAL INITIALIZATION ---
print("Initializing resources...")
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
tracker = initialize_tracker()
known_face_encodings, known_face_names = load_known_faces("registered_faces")

print("Starting threaded video stream...")
vs = VideoStream(src=0, width=FRAME_WIDTH, height=FRAME_HEIGHT).start()
time.sleep(2.0)
print("\n--- Initialization Complete. Starting Web Server. ---")
print("Press CTRL+C to exit.")

# --- 4. MAIN VIDEO PROCESSING LOGIC (DEFINITIVE FIX) ---
def process_video_frames():
    frame_count = 0
    last_alert_time = 0
    tracked_persons = {}

    while True:
        frame = vs.read()
        if frame is None or vs.stopped:
            break

        frame_count += 1
        current_time = time.time()
        
        if frame_count % FRAME_PROCESSING_INTERVAL == 0:
            processing_frame = frame.copy()
            detections = detect_persons(model, processing_frame)
            tracks = update_tracker_with_detections(tracker, detections, processing_frame)
            
            active_track_ids = set()
            for track in tracks:
                # --- BUG FIX: Only process tracks that were updated in this frame ---
                if not track.is_confirmed() or track.time_since_update > 0:
                    continue
                
                track_id = track.track_id
                active_track_ids.add(track_id)
                ltrb = track.to_ltrb()

                if track_id not in tracked_persons:
                    tracked_persons[track_id] = {
                        "box": ltrb, "name": "Unknown", "distance": 0.0,
                        "loiter_start_time": None, "alert_triggered": False,
                        "last_seen_time": current_time # NEW: Track last seen time
                    }
                
                person_state = tracked_persons[track_id]
                person_state.update({"box": ltrb, "last_seen_time": current_time})

                if person_state["name"] == "Unknown" and frame_count % RE_RECOGNITION_INTERVAL_FRAMES == 0:
                    x1, y1, x2, y2 = map(int, ltrb)
                    person_crop = processing_frame[y1:y2, x1:x2]
                    if person_crop.size > 0:
                        name, distance = recognize_face(known_face_encodings, known_face_names, person_crop)
                        if name != "Unknown":
                            person_state.update({"name": name, "distance": distance, "loiter_start_time": None, "alert_triggered": False})
                
                is_in_zone = False
                if person_state["name"] == "Unknown":
                    person_center_x = (ltrb[0] + ltrb[2]) / 2
                    is_in_zone = (person_center_x > FORBIDDEN_ZONE[0] and person_center_x < FORBIDDEN_ZONE[2])

                if is_in_zone:
                    if person_state["loiter_start_time"] is None:
                        person_state["loiter_start_time"] = current_time
                    else:
                        loiter_duration = current_time - person_state["loiter_start_time"]
                        if loiter_duration > TIME_THRESHOLD_SECONDS and not person_state["alert_triggered"]:
                            last_alert_time = trigger_alert(frame, last_alert_time)
                            person_state["alert_triggered"] = True
                else:
                    person_state["loiter_start_time"] = None
                    person_state["alert_triggered"] = False
            
            # --- BUG FIX: Enforce a Time-To-Live (TTL) on all tracks ---
            inactive_track_ids = set(tracked_persons.keys()) - active_track_ids
            stale_track_ids = {
                tid for tid, p in tracked_persons.items()
                if current_time - p["last_seen_time"] > TRACK_TTL_SECONDS
            }
            ids_to_remove = inactive_track_ids.union(stale_track_ids)
            
            for inactive_id in ids_to_remove:
                if inactive_id in tracked_persons:
                    del tracked_persons[inactive_id]

        for track_id, person in tracked_persons.items():
            x1, y1, x2, y2 = map(int, person["box"])
            identity = person["name"]
            box_color = (255, 0, 0) if identity != "Unknown" else (0, 255, 0)
            label = f"{identity} (ID: {track_id})"

            if identity != "Unknown":
                label += f" D:{person['distance']:.2f}"
            else:
                if person["loiter_start_time"] is not None:
                    box_color = (0, 0, 255)
                    loiter_duration = current_time - person["loiter_start_time"]
                    label += f" | T: {loiter_duration:.0f}s"
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

        cv2.rectangle(frame, (FORBIDDEN_ZONE[0], FORBIDDEN_ZONE[1]), (FORBIDDEN_ZONE[2], FORBIDDEN_ZONE[3]), (0, 0, 255), 2)
        cv2.putText(frame, "Restricted Zone", (FORBIDDEN_ZONE[0] + 10, FORBIDDEN_ZONE[1] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret: yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- 5. FLASK WEB ROUTES (Unchanged) ---
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
        print("Shutdown signal received. Stopping video stream...")
    finally:
        vs.stop()
        print("Video stream stopped. Exiting.")