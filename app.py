# app.py
from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from contextlib import asynccontextmanager
import os
import sys
import multiprocessing
from core.logger.app_logger import logger
from typing import AsyncGenerator
import uvicorn
from api.routes import documents, questions, metrics, health
from core.events.handlers import cleanup_resources
from core.events.watchers import DocumentWatcher
from core.rag.llama_rag import RAGEngine
from watchdog.observers import Observer
from security.security import SecurityConfig

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager"""
    try:
        # Initialize RAG system
        app.state.rag_engine = RAGEngine()
        await app.state.rag_engine.initialize()
        logger.info("RAG System initialized successfully")

        # Set up document watching
        directory = os.getenv("DOCUMENTS_DIRECTORY", "./data/documents")
        await initialize_documents(app.state.rag_engine, directory)
        setup_document_watcher(app.state.rag_engine, directory)

        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        cleanup_resources()
        raise
    finally:
        cleanup_resources()
        logger.info("Shutdown complete")

def create_app(security_config):
    """Application factory"""
    if sys.platform == 'darwin':
        try:
            multiprocessing.set_start_method('fork', force=True)
        except RuntimeError:
            logger.error("Unable to set start method to 'fork'")

    app = FastAPI(lifespan=lifespan)
    app.state.security_config = security_config

    if security_config.AUTH_MODE == "prod":
        app.add_middleware(HTTPSRedirectMiddleware)

    # Include routers
    app.include_router(documents.router)
    app.include_router(questions.router)
    app.include_router(metrics.router)
    app.include_router(health.router)

    return app

async def initialize_documents(rag_engine: RAGEngine, directory: str):
    """Initialize documents from directory"""
    for file in os.listdir(directory):
        if file.endswith(".pdf"):
            await rag_engine.process_document(f"{directory}/{file}")

def setup_document_watcher(rag_engine: RAGEngine, directory: str):
    """Set up document watcher"""
    event_handler = DocumentWatcher(directory, rag_engine)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()
    logger.info(f"Watching directory: {directory}")

def main():
    """Main entry point"""
    security_config = SecurityConfig()
    app = create_app(security_config)
    ssl_config = security_config.get_ssl_config()

    config = uvicorn.Config(
        app=app,
        host="localhost",
        port=8080,
        workers=1,
        loop="asyncio",
        reload=os.getenv("DEBUG", "false").lower() == "true",
        **ssl_config
    )

    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        cleanup_resources()
    finally:
        cleanup_resources()

if __name__ == "__main__":
    main()
    
