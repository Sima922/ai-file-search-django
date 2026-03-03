import os
import logging
from django.conf import settings

def setup_logging():
    """
    Configure logging settings for the application
    
    Sets up file-based logging with error-level logging to a log file
    """
    # Ensure logs directory exists
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Full path for the log file
    log_file_path = os.path.join(log_dir, 'image_search.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler()  # Optional: also log to console
        ]
    )

    # Create a logger specific to the module
    logger = logging.getLogger('image_search')
    logger.setLevel(logging.INFO)
    
    return logger

# Create a module-level logger
logger = setup_logging()