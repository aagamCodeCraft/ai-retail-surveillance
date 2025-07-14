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
# -- General Video Settings --
FRAME_WIDTH = 1520
FRAME_HEIGHT = 700

# -- Alerting & Performance --
TIME_THRESHOLD_SECONDS = 10.0
FRAME_PROCESSING_INTERVAL = 2 
RE_RECOGNITION_INTERVAL_FRAMES = 10 

# --- NEW: RESTRICTED ZONE CONFIGURATION ---
# Customize the zone by changing these four values.
# The coordinates start from the top-left corner (0,0).
ZONE_START_X = 0      # X-pixel to start the zone (e.g., 0 for far left)
ZONE_START_Y = 0      # Y-pixel to start the zone (e.g., 0 for the top)
ZONE_WIDTH = 350      # Width of the zone in pixels
ZONE_HEIGHT = 720     # Height of the zone in pixels

# The application will automatically calculate the zone's rectangle from your settings.
# (x1, y1, x2, y2)
FORBIDDEN_ZONE = (ZONE_START_X, ZONE_START_Y, ZONE_START_X + ZONE_WIDTH, ZONE_START_Y + ZONE_HEIGHT)
# --- END OF NEW SECTION ---

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

# --- 4. MAIN VIDEO PROCESSING LOGIC ---
def process_video_frames():
    frame_count = 0
    track_identities = {}
    loitering_timers = {}
    last_alert_time = 0
    
    while True:
        frame = vs.read()
        if frame is None or vs.stopped:
            break

        frame_count += 1
        
        if frame_count % FRAME_PROCESSING_INTERVAL == 0:
            processing_frame = frame.copy()
            detections = detect_persons(model, processing_frame)
            tracks = update_tracker_with_detections(tracker, detections, processing_frame)
            
            active_track_ids = {track.track_id for track in tracks if track.is_confirmed()}

            for track in tracks:
                if not track.is_confirmed(): continue
                track_id = track.track_id
                ltrb = track.to_ltrb()
                x1_person, y1_person, x2_person, y2_person = map(int, ltrb)
                
                if track_id not in track_identities or \
                   (track_identities[track_id]["name"] == "Unknown" and frame_count % RE_RECOGNITION_INTERVAL_FRAMES == 0):
                    person_crop = processing_frame[y1_person:y2_person, x1_person:x2_person]
                    if person_crop.size > 0:
                        name, distance = recognize_face(known_face_encodings, known_face_names, person_crop)
                        track_identities[track_id] = {"name": name, "distance": distance}
                
                identity_info = track_identities.get(track_id, {"name": "Unknown", "distance": 0.0})
                identity = identity_info["name"]
                
                if identity == "Unknown":
                    # --- UPDATED ZONE CHECK LOGIC ---
                    # Check if the center of the person is inside the forbidden zone rectangle.
                    person_center_x = (x1_person + x2_person) / 2
                    is_in_zone = (person_center_x > FORBIDDEN_ZONE[0] and person_center_x < FORBIDDEN_ZONE[2])

                    if is_in_zone:
                        if track_id not in loitering_timers: loitering_timers[track_id] = time.time()
                        loiter_duration = time.time() - loitering_timers[track_id]
                        if loiter_duration > TIME_THRESHOLD_SECONDS: last_alert_time = trigger_alert(last_alert_time)
                    elif track_id in loitering_timers: del loitering_timers[track_id]
                elif track_id in loitering_timers: del loitering_timers[track_id]

            inactive_timers = set(loitering_timers.keys()) - active_track_ids
            for inactive_id in inactive_timers: del loitering_timers[inactive_id]

        if 'tracks' in locals():
            for track in tracks:
                if not track.is_confirmed(): continue
                track_id, ltrb = track.track_id, track.to_ltrb()
                x1, y1, x2, y2 = map(int, ltrb)
                identity_info = track_identities.get(track_id, {"name": "Unknown"})
                identity = identity_info["name"]
                box_color = (255, 0, 0) if identity != "Unknown" else (0, 255, 0)
                label = f"{identity} (ID: {track_id})"
                if identity != "Unknown": label += f" D:{identity_info.get('distance', 0.0):.2f}"
                else:
                    person_center_x = (x1 + x2) / 2
                    if track_id in loitering_timers and (person_center_x > FORBIDDEN_ZONE[0] and person_center_x < FORBIDDEN_ZONE[2]):
                        box_color = (0, 0, 255)
                        loiter_duration = time.time() - loitering_timers[track_id]
                        label += f" | T: {loiter_duration:.0f}s"
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

        # Draw the restricted zone using the calculated coordinates
        cv2.rectangle(frame, (FORBIDDEN_ZONE[0], FORBIDDEN_ZONE[1]), (FORBIDDEN_ZONE[2], FORBIDDEN_ZONE[3]), (0, 0, 255), 2)
        cv2.putText(frame, "Restricted Zone", (FORBIDDEN_ZONE[0] + 10, FORBIDDEN_ZONE[1] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret: yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- 5. FLASK WEB ROUTES ---
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