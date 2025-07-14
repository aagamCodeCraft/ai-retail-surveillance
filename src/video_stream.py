import cv2
import time
from threading import Thread

class VideoStream:
    """A class to read frames from a camera in a dedicated thread."""
    def __init__(self, src=0, width=960, height=540):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        """Starts the thread to read frames from the video stream."""
        # --- THIS IS THE FIX ---
        # Create the thread and set it as a daemon thread
        t = Thread(target=self.update, args=())
        t.daemon = True # This ensures the thread will exit when the main program does
        t.start()
        return self

    def update(self):
        """The main loop of the thread that continuously reads frames."""
        while not self.stopped:
            (self.grabbed, self.frame) = self.stream.read()
        # When the loop is stopped, release the camera
        self.stream.release()

    def read(self):
        """Returns the most recent frame read by the thread."""
        return self.frame

    def stop(self):
        """Signals the thread to stop."""
        self.stopped = True