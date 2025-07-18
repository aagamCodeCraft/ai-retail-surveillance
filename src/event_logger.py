import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "events.log")

def setup_logger():
    """Configures the logger to write to a file and the console."""
    # Create log directory if it doesn't exist
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set the lowest level of messages to handle

    # Create a file handler to write to events.log
    # This handler will write all messages (INFO and above)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    
    # Create a console handler to print to the terminal
    # This handler will also write all messages (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Define the format for the log messages
    formatter = logging.Formatter('[%(asctime)s] - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    # Check if handlers already exist to avoid duplicate logs
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger