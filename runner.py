#!/usr/bin/env python3

import subprocess
import time
import sys
import os
import signal
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CodeChangeHandler(FileSystemEventHandler):
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_restart = 0
        self.restart_cooldown = 5  # Minimum seconds between restarts

    def on_modified(self, event):
        if event.is_directory:
            return
            
        if not event.src_path.endswith(('.py', '.env')):
            return
            
        current_time = time.time()
        if current_time - self.last_restart > self.restart_cooldown:
            logger.info(f"Change detected in {event.src_path}")
            self.last_restart = current_time
            self.restart_callback()

class ApplicationSupervisor:
    def __init__(self):
        self.process = None
        self.should_run = True
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_cooldown = 60  # Reset restart count after 60 seconds
        self.last_restart_time = 0

    def start_application(self):
        """Start the main application"""
        try:
            # Environment setup
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            # Start the application with reload enabled
            self.process = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                universal_newlines=True
            )
            
            logger.info(f"Application started with PID: {self.process.pid}")
            
            # Reset restart count if enough time has passed
            current_time = time.time()
            if current_time - self.last_restart_time > self.restart_cooldown:
                self.restart_count = 0
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            return False

    def stop_application(self):
        """Stop the main application"""
        if self.process:
            try:
                # Try graceful shutdown first
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    self.process.kill()
                    self.process.wait()
                
                logger.info("Application stopped")
                
            except Exception as e:
                logger.error(f"Error stopping application: {e}")
            
            self.process = None

    def restart_application(self):
        """Restart the main application"""
        logger.info("Restarting application...")
        self.stop_application()
        
        # Check restart limits
        current_time = time.time()
        if current_time - self.last_restart_time <= self.restart_cooldown:
            self.restart_count += 1
            if self.restart_count >= self.max_restarts:
                logger.error("Too many restarts in short period. Waiting for cooldown...")
                time.sleep(self.restart_cooldown)
                self.restart_count = 0
        
        self.last_restart_time = current_time
        return self.start_application()

    def monitor_logs(self):
        """Monitor application logs"""
        if self.process:
            while True:
                output = self.process.stdout.readline()
                if output:
                    print(output.strip())
                error = self.process.stderr.readline()
                if error:
                    print(error.strip(), file=sys.stderr)
                
                # Check if process is still running
                if self.process.poll() is not None:
                    break

    def run(self):
        """Main supervisor loop"""
        # Set up file system watcher
        event_handler = CodeChangeHandler(self.restart_application)
        observer = Observer()
        observer.schedule(event_handler, path=".", recursive=True)
        observer.start()

        try:
            while self.should_run:
                if not self.process or self.process.poll() is not None:
                    if not self.start_application():
                        logger.error("Failed to start application, retrying in 5 seconds...")
                        time.sleep(5)
                        continue
                    
                self.monitor_logs()
                
                if self.should_run:  # If not stopped by signal
                    logger.warning("Application crashed, restarting...")
                    time.sleep(1)  # Prevent rapid restart loops
                
        except KeyboardInterrupt:
            logger.info("Supervisor shutting down...")
        finally:
            self.should_run = False
            self.stop_application()
            observer.stop()
            observer.join()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.should_run = False
        self.stop_application()
        sys.exit(0)

if __name__ == "__main__":
    supervisor = ApplicationSupervisor()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, supervisor.signal_handler)
    signal.signal(signal.SIGTERM, supervisor.signal_handler)
    
    # Start supervision
    supervisor.run()