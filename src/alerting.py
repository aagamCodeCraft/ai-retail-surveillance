import time
import os
try:
    import simpleaudio as sa
except ImportError:
    print("Warning: 'simpleaudio' library not found. Pip install simpleaudio for audio alerts.")
    sa = None

# Path to the siren sound file in the 'assets' folder
SIREN_PATH = "assets/siren.wav"
ALERT_COOLDOWN_SECONDS = 10.0

def trigger_alert(last_alert_time):
    """
    Triggers a siren sound alert if the cooldown period has passed.
    
    Args:
        last_alert_time (float): The timestamp of the last alert.

    Returns:
        float: The updated timestamp of the last alert.
    """
    current_time = time.time()
    if (current_time - last_alert_time) > ALERT_COOLDOWN_SECONDS:
        print(f"ALERT: Unknown person in restricted zone at {time.ctime()}")
        
        if sa and os.path.exists(SIREN_PATH):
            try:
                wave_obj = sa.WaveObject.from_wave_file(SIREN_PATH)
                wave_obj.play()
            except Exception as e:
                print(f"ERROR: Could not play siren sound: {e}")
                print("Please ensure 'assets/siren.wav' is a valid WAV file.")
        else:
            # Fallback if simpleaudio is not installed or file is missing
            print("\a" * 3) # Beep 3 times as a fallback
            if not os.path.exists(SIREN_PATH):
                print(f"Warning: Siren file not found at '{SIREN_PATH}'")

        return current_time
        
    return last_alert_time