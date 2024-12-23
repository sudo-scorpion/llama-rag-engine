import torch
import sys
from core.logger.app_logger import logger

def cleanup_resources():
    """Cleanup function to handle resource release"""
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal. Cleaning up...")
    cleanup_resources()
    sys.exit(0)