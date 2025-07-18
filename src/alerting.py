import time
import os
import cv2
from datetime import datetime
import requests
import logging

try:
    import simpleaudio as sa
except ImportError:
    sa = None

logger = logging.getLogger(__name__)

# --- CONFIGURATION (Unchanged) ---
SIREN_PATH = "assets/siren.wav"
ALERT_SNAPSHOT_DIR = "alert_snapshots"
ALERT_COOLDOWN_SECONDS = 10.0
NTFY_TOPIC = "aiRetailSurveillance"

def send_phone_notification(title, image_path):
    """Sends a push notification with a custom title and an image."""
    try:
        with open(image_path, 'rb') as image_file:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=image_file,
                headers={
                    "Title": title, # MODIFIED: Use custom title
                    "Priority": "high", "Tags": "warning,person",
                    "Filename": os.path.basename(image_path)
                }
            )
        logger.info(f"Notification sent to ntfy topic: {NTFY_TOPIC}")
    except Exception as e:
        logger.error(f"Could not send notification: {e}")

# --- NEW: Alert function specifically for Banned Persons ---
def trigger_banned_person_alert(frame, person_name):
    """Triggers an immediate alert for a banned person."""
    logger.critical(f"BANNED PERSON ALERT: '{person_name}' detected in restricted zone!")

    snapshot_filename = ""
    try:
        if not os.path.exists(ALERT_SNAPSHOT_DIR): os.makedirs(ALERT_SNAPSHOT_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = os.path.join(ALERT_SNAPSHOT_DIR, f"banned_{person_name}_{timestamp}.jpg")
        cv2.imwrite(snapshot_filename, frame)
        logger.info(f"Banned person snapshot saved: {snapshot_filename}")
    except Exception as e:
        logger.error(f"Could not save banned person snapshot: {e}")

    # Play siren
    if sa and os.path.exists(SIREN_PATH):
        try: sa.WaveObject.from_wave_file(SIREN_PATH).play()
        except Exception as e: logger.error(f"Could not play siren sound: {e}")
    else: print("\a" * 3)
    
    # Send notification
    if snapshot_filename:
        notification_title = f"BANNED PERSON: {person_name} Detected!"
        send_phone_notification(notification_title, snapshot_filename)

# --- Loitering Alert (largely unchanged) ---
def trigger_alert(frame, last_alert_time):
    """Triggers a loitering alert for an unknown person."""
    current_time = time.time()
    if (current_time - last_alert_time) > ALERT_COOLDOWN_SECONDS:
        logger.critical("LOITERING ALERT: Unknown person in restricted zone.")
        
        snapshot_filename = ""
        try:
            if not os.path.exists(ALERT_SNAPSHOT_DIR): os.makedirs(ALERT_SNAPSHOT_DIR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_filename = os.path.join(ALERT_SNAPSHOT_DIR, f"loitering_alert_{timestamp}.jpg")
            cv2.imwrite(snapshot_filename, frame)
            logger.info(f"Loitering snapshot saved: {snapshot_filename}")
        except Exception as e: logger.error(f"Could not save loitering snapshot: {e}")

        if sa and os.path.exists(SIREN_PATH):
            try: sa.WaveObject.from_wave_file(SIREN_PATH).play()
            except Exception as e: logger.error(f"Could not play siren sound: {e}")
        else: print("\a" * 3)
        
        if snapshot_filename:
            send_phone_notification("Loitering Alert: Unknown Person!", snapshot_filename)

        return current_time
    return last_alert_time