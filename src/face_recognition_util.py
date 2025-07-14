import face_recognition
import os
import numpy as np
import cv2

# Lower tolerance means stricter matching. 0.5 is a good default.
FACE_RECOGNITION_TOLERANCE = 0.5

def load_known_faces(faces_dir="registered_faces"):
    """
    Loads face images and their encodings from the specified directory.
    """
    known_face_encodings, known_face_names = [], []
    print(f"Looking for face images in: {os.path.abspath(faces_dir)}")
    if not os.path.exists(faces_dir):
        os.makedirs(faces_dir)
    
    for filename in os.listdir(faces_dir):
        if filename.lower().endswith((".jpg", ".png", ".jpeg")):
            try:
                name = os.path.splitext(filename)[0].replace("_", " ").title()
                image = face_recognition.load_image_file(os.path.join(faces_dir, filename))
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(name)
                    print(f"Loaded face: {name}")
            except Exception as e:
                print(f"Error loading face {filename}: {e}")
    print(f"Total known faces loaded: {len(known_face_names)}")
    return known_face_encodings, known_face_names

def recognize_face(known_face_encodings, known_face_names, frame_crop):
    """
    Recognizes a face from a cropped frame against known faces with strict matching.
    
    Returns:
        tuple: (name, distance) where name is "Unknown" if no match is found.
    """
    if not known_face_encodings:
        return "Unknown", 0.0

    rgb_crop = cv2.cvtColor(frame_crop, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_crop)
    
    if not face_locations:
        return "Unknown", 0.0

    face_encodings = face_recognition.face_encodings(rgb_crop, face_locations)
    if not face_encodings:
        return "Unknown", 0.0

    # Compare the found face with all known faces
    face_distances = face_recognition.face_distance(known_face_encodings, face_encodings[0])
    
    if len(face_distances) == 0:
        return "Unknown", 0.0

    # Find the best match (the one with the smallest distance)
    best_match_index = np.argmin(face_distances)
    best_match_distance = face_distances[best_match_index]

    # If the best match is within our tolerance, we have a confident match
    if best_match_distance < FACE_RECOGNITION_TOLERANCE:
        name = known_face_names[best_match_index]
        return name, best_match_distance

    return "Unknown", 0.0