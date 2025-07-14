def detect_persons(model, frame):
    """
    Detects persons in a frame using the provided YOLO model.
    
    Args:
        model: The loaded YOLOv8 model instance.
        frame: The video frame to process.

    Returns:
        list: A list of detections formatted for the DeepSort tracker.
              Format: [([x, y, w, h], confidence, class_id), ...]
    """
    # Predict objects in the frame, filtering for 'person' class (ID 0)
    # with a confidence threshold of 0.5.
    results = model.predict(frame, classes=[0], conf=0.5, verbose=False)
    
    detections_for_tracker = []
    if results and results[0].boxes:
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1
            confidence = float(box.conf[0])
            # The class_id is always 0 since we filtered for it.
            detections_for_tracker.append(([x1, y1, w, h], confidence, 0))
            
    return detections_for_tracker