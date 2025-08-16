import logging
from logging.handlers import RotatingFileHandler
import os



LOG_DIR = os.environ.get("LOG_DIR", "logs")  
LOG_FILE_NAME = "app.log"
LOG_FILE = os.environ.get("LOG_FILE", os.path.join(LOG_DIR, LOG_FILE_NAME))
MAX_LOG_SIZE = int(os.environ.get("MAX_LOG_SIZE", 5 * 1024 * 1024))  
BACKUP_COUNT = int(os.environ.get("BACKUP_COUNT", 5)) 

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

#  ure log formatter
log_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(filename)s:%(module)s:%(lineno)d - %(message)s")

# Setup rotating file handler (Log rotation enabled)
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes= MAX_LOG_SIZE, backupCount= BACKUP_COUNT
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)  # Adjust level as needed

# Setup console handler (For real-time debugging)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

# Create logger instance
logger = logging.getLogger(" -management-service")
logger.setLevel(logging.DEBUG)  # Capture all levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Test logging
logger.info("Logger initialized successfully!")
