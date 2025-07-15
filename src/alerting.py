import time
import os
import cv2
from datetime import datetime

try:
    import simpleaudio as sa
except ImportError:
    print("Warning: 'simpleaudio' library not found. Pip install simpleaudio for audio alerts.")
    sa = None

SIREN_PATH = "assets/siren.wav"
ALERT_SNAPSHOT_DIR = "alert_snapshots"
ALERT_COOLDOWN_SECONDS = 10.0

def trigger_alert(frame, last_alert_time):
    current_time = time.time()
    if (current_time - last_alert_time) > ALERT_COOLDOWN_SECONDS:
        print(f"ALERT: Unknown person in restricted zone at {time.ctime()} by aagamCodeCraft")

        try:
            if not os.path.exists(ALERT_SNAPSHOT_DIR):
                os.makedirs(ALERT_SNAPSHOT_DIR)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = os.path.join(ALERT_SNAPSHOT_DIR, f"alert_{timestamp}.jpg")
            cv2.imwrite(filename, frame)
            print(f"Snapshot saved: {filename}")
        except Exception as e:
            print(f"ERROR: Could not save snapshot: {e}")

        if sa and os.path.exists(SIREN_PATH):
            try:
                wave_obj = sa.WaveObject.from_wave_file(SIREN_PATH)
                wave_obj.play()
            except Exception as e:
                print(f"ERROR: Could not play siren sound: {e}")
        else:
            print("\a" * 3)

        return current_time
    return last_alert_time