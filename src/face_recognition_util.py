import face_recognition
import os
import cv2
import numpy as np

# --- MODIFIED: Function to load faces and their statuses ---
def load_known_faces(base_dir):
    """
    Loads face encodings and their corresponding identities (name, status)
    from subdirectories in the base directory.

    Directory structure should be:
    - base_dir/allowed/person_a.jpg
    - base_dir/banned/person_b.jpg
    - base_dir/person_c.jpg  (for neutral/known status)
    """
    known_face_encodings = []
    # This dictionary will store {name: status}
    known_face_identities = {}

    print("Loading known faces...")
    for status in os.listdir(base_dir):
        status_path = os.path.join(base_dir, status)
        
        # Handle images directly in the root folder (neutral status)
        if os.path.isfile(status_path):
            person_name = os.path.splitext(status)[0]
            if person_name in known_face_identities: continue # Avoid duplicates
            
            image = face_recognition.load_image_file(status_path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_identities[person_name] = "known" # Neutral status
                print(f"  - Loaded '{person_name}' (Status: Known)")
            continue

        # Handle 'allowed' and 'banned' subdirectories
        if os.path.isdir(status_path):
            for filename in os.listdir(status_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    person_name = os.path.splitext(filename)[0]
                    if person_name in known_face_identities: continue

                    image_path = os.path.join(status_path, filename)
                    image = face_recognition.load_image_file(image_path)
                    encodings = face_recognition.face_encodings(image)
                    if encodings:
                        known_face_encodings.append(encodings[0])
                        known_face_identities[person_name] = status # 'allowed' or 'banned'
                        print(f"  - Loaded '{person_name}' (Status: {status.capitalize()})")

    return known_face_encodings, known_face_identities

# --- MODIFIED: Function to return name, status, and distance ---
def recognize_face(known_face_encodings, known_face_identities, frame_crop):
    """
    Finds the best match for a face in a cropped frame and returns their
    name, status, and the face distance.
    """
    if frame_crop.size == 0:
        return "Unknown", "unknown", 0.0

    # Convert BGR (OpenCV) to RGB (face_recognition)
    rgb_frame_crop = cv2.cvtColor(frame_crop, cv2.COLOR_BGR2RGB)
    
    face_locations = face_recognition.face_locations(rgb_frame_crop)
    if not face_locations:
        return "Unknown", "unknown", 0.0

    face_encodings = face_recognition.face_encodings(rgb_frame_crop, face_locations)
    if not face_encodings:
        return "Unknown", "unknown", 0.0

    face_distances = face_recognition.face_distance(known_face_encodings, face_encodings[0])
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        # Threshold for recognition; lower is stricter. Default is ~0.6
        if face_distances[best_match_index] < 0.6:
            # Get the name from the dictionary keys based on the index
            name = list(known_face_identities.keys())[best_match_index]
            # Get the status using the name
            status = known_face_identities[name]
            distance = face_distances[best_match_index]
            return name, status, distance

    return "Unknown", "unknown", 0.0