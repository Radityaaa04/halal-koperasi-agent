"""
Regulatory and RAG schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class RegulatorySource(str, Enum):
    UU_33_2014 = "UU_33_2014"
    PP_39_2021 = "PP_39_2021"
    BPJPH_1_2023 = "BPJPH_1_2023"
    BPJPH_2_2023 = "BPJPH_2_2023"
    MUI_FATWA = "MUI_FATWA"
    LPH_PANDUAN = "LPH_PANDUAN"
    SNI_HALAL = "SNI_HALAL"
    KOMINFO_9_2023 = "KOMINFO_9_2023"


class RegulatoryChunk(BaseModel):
    chunk_id: str
    source: RegulatorySource
    document_title: str
    chapter: Optional[str] = None
    article: Optional[str] = None
    verse: Optional[str] = None
    text: str
    keywords: List[str] = Field(default_factory=list)
    effective_date: Optional[datetime] = None
    category: str
    language: str = "id"
    
    # Vector store metadata
    embedding_model: str = "bge-m3"
    vector_id: Optional[str] = None


class RegulatoryCitation(BaseModel):
    chunk_id: str
    source: RegulatorySource
    article: str
    verse: Optional[str] = None
    text_snippet: str
    relevance_score: float
    page_number: Optional[int] = None


class RAGAnswer(BaseModel):
    question: str
    answer: str
    citations: List[RegulatoryCitation] = Field(default_factory=list)
    confidence: float = 0.0
    needs_human_verification: bool = False
    verification_reason: Optional[str] = None
    retrieved_chunks: List[str] = Field(default_factory=list)
    retrieval_strategy: str = "hybrid_rrf_rerank"
    generated_at: datetime = Field(default_factory=datetime.now)
    model_used: str = "llama3.1:8b"


class RAGQuestion(BaseModel):
    question: str
    category: str
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    context_application_id: Optional[str] = None
    expected_answer_type: Literal["yes_no", "list", "procedure", "reference", "explanation"] = "explanation"