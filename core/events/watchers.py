import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.logger.app_logger import logger
from core.rag.rag_engine import RAGEngine

class DocumentWatcher(FileSystemEventHandler):
    def __init__(self, directory: str, rag_engine: RAGEngine):
        self.directory = directory
        self.rag_engine = rag_engine

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".pdf"):
            logger.info(f"New document detected: {event.src_path}")
            asyncio.run(self.rag_engine.process_document(event.src_path))