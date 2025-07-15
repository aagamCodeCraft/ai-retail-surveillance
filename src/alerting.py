import time
import os
import cv2
from datetime import datetime
import requests  # ADDED: For sending HTTP requests

try:
    import simpleaudio as sa
except ImportError:
    print("Warning: 'simpleaudio' library not found. Pip install simpleaudio for audio alerts.")
    sa = None

# --- CONFIGURATION ---
SIREN_PATH = "assets/siren.wav"
ALERT_SNAPSHOT_DIR = "alert_snapshots"
ALERT_COOLDOWN_SECONDS = 10.0

# --- NEW: Phone Notification Setup ---
# This is your unique topic name from the ntfy URL you provided.
NTFY_TOPIC = "aiRetailSurveillance"

def send_phone_notification(image_path):
    """Sends a push notification with an image to your ntfy.sh topic."""
    # This function will only be called if an image was successfully saved.
    try:
        with open(image_path, 'rb') as image_file:
            # We send the image data directly to your ntfy topic
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=image_file,
                headers={
                    "Title": "ALERT: Person Detected in Restricted Zone!",
                    "Priority": "high",
                    "Tags": "warning,person",
                    "Filename": os.path.basename(image_path) # Helps display the image correctly
                }
            )
        print(f"Notification sent to ntfy topic: {NTFY_TOPIC}")
    except Exception as e:
        print(f"ERROR: Could not send notification. Is 'pip install requests' done? Error: {e}")

# --- MODIFIED: trigger_alert now sends a notification ---
def trigger_alert(frame, last_alert_time):
    """
    Triggers siren, saves snapshot, and sends phone notification.
    """
    current_time = time.time()
    if (current_time - last_alert_time) > ALERT_COOLDOWN_SECONDS:
        print(f"ALERT: Unknown person in restricted zone at {time.ctime()} by {os.getlogin()}")

        # --- Snapshot Logic (Unchanged) ---
        snapshot_filename = ""
        try:
            if not os.path.exists(ALERT_SNAPSHOT_DIR):
                os.makedirs(ALERT_SNAPSHOT_DIR)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            snapshot_filename = os.path.join(ALERT_SNAPSHOT_DIR, f"alert_{timestamp}.jpg")
            cv2.imwrite(snapshot_filename, frame)
            print(f"Snapshot saved: {snapshot_filename}")
        except Exception as e:
            print(f"ERROR: Could not save snapshot: {e}")

        # --- Siren Logic (Unchanged) ---
        if sa and os.path.exists(SIREN_PATH):
            try:
                wave_obj = sa.WaveObject.from_wave_file(SIREN_PATH)
                wave_obj.play()
            except Exception as e:
                print(f"ERROR: Could not play siren sound: {e}")
        else:
            print("\a" * 3)
        
        # --- NEW: Phone Notification Call ---
        # If the snapshot was saved, we call the notification function.
        if snapshot_filename:
            send_phone_notification(snapshot_filename)

        return current_time
    return last_alert_time