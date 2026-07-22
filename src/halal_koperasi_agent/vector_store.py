"""
Vector Store utilities for HALAL Koperasi Agent
NVIDIA NIM Embeddings, Reranker, and ChromaDB client
"""

import os
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from halal_koperasi_agent.config import settings


_chroma_client = None
_embeddings = None
_reranker = None


def get_chroma_client():
    """Get ChromaDB HTTP client"""
    global _chroma_client
    if _chroma_client is None:
        host = settings.CHROMA_HOST.replace("http://", "").split(":")[0]
        port = int(settings.CHROMA_HOST.split(":")[-1]) if ":" in settings.CHROMA_HOST else 8000
        _chroma_client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_embeddings():
    """Get NVIDIA NIM embeddings model"""
    global _embeddings
    if _embeddings is None:
        from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
        _embeddings = NVIDIAEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
        )
    return _embeddings


def get_reranker():
    """Get NVIDIA NIM reranker model"""
    global _reranker
    if _reranker is None:
        from langchain_nvidia_ai_endpoints import NVIDIARerank
        _reranker = NVIDIARerank(
            model=settings.RERANKER_MODEL,
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
        )
    return _reranker


def get_chroma_client_sync():
    """Synchronous ChromaDB client for scripts"""
    host = settings.CHROMA_HOST.replace("http://", "").split(":")[0]
    port = int(settings.CHROMA_HOST.split(":")[-1]) if ":" in settings.CHROMA_HOST else 8000
    return chromadb.HttpClient(
        host=host,
        port=port,
    )


def get_embeddings_sync():
    """Synchronous embeddings for scripts"""
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
    from halal_koperasi_agent.config import settings
    return NVIDIAEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.NVIDIA_API_KEY,
        base_url=settings.NVIDIA_BASE_URL,
    )


def get_reranker_sync():
    """Synchronous reranker for scripts"""
    from langchain_nvidia_ai_endpoints import NVIDIARerank
    from halal_koperasi_agent.config import settings
    return NVIDIARerank(
        model=settings.RERANKER_MODEL,
        api_key=settings.NVIDIA_API_KEY,
        base_url=settings.NVIDIA_BASE_URL,
    )