from deep_sort_realtime.deepsort_tracker import DeepSort

def initialize_tracker():
    """
    Initializes and returns a DeepSort tracker object.
    """
    # These parameters are tuned for a balance of performance and tracking accuracy.
    # max_age: How long to keep tracking a person without detecting them again.
    # n_init: How many initial detections are needed to confirm a new track.
    return DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)

def update_tracker_with_detections(tracker, detections, frame):
    """
    Updates the tracker with new detections and returns the active tracks.
    
    Args:
        tracker (DeepSort): The DeepSort tracker instance.
        detections (list): A list of detections from the YOLO model.
        frame (np.ndarray): The current video frame.
                           
    Returns:
        list: A list of the currently active tracks.
    """
    return tracker.update_tracks(detections, frame=frame)