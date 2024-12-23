from fastapi import Depends, Request
from core.rag.rag_engine import RAGEngine

async def get_rag_system(request: Request) -> RAGEngine:
    return request.app.state.rag_engine

async def verify_auth(request: Request) -> bool:
    return await request.app.state.security_config.authenticate(request)