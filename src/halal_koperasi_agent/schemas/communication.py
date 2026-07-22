"""
Communication and report schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class ReportFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"


class EmailDraft(BaseModel):
    to: List[str]
    cc: List[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: str
    attachments: List[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    agent_name: str
    step: str
    input_summary: str
    output_summary: str
    confidence: float
    reasoning: str
    tools_used: List[str] = Field(default_factory=list)
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.now)


class HallucinationCheck(BaseModel):
    checked: bool = False
    risk_score: float = 0.0
    unverified_claims: List[str] = Field(default_factory=list)
    missing_citations: List[str] = Field(default_factory=list)
    checker_model: str = "llama3.1:8b"


class RAGTrace(BaseModel):
    question: str
    retrieved_chunks: List[str]
    reranked_chunks: List[str]
    final_context_chunks: List[str]
    answer: str
    citations: List[Any]
    confidence: float
    hallucination_check: HallucinationCheck


class ExplainabilityTrace(BaseModel):
    application_id: str
    trace_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    
    agent_traces: List[AgentTrace] = Field(default_factory=list)
    rag_traces: List[RAGTrace] = Field(default_factory=list)
    human_reviews: List[Any] = Field(default_factory=list)
    
    overall_confidence: float = 0.0
    hallucination_risk_score: float = 0.0


class CommunicationOutput(BaseModel):
    application_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    generated_by: str = "communication_agent_v1"
    
    pdf_report_path: str
    html_report_path: str
    json_report_path: str
    
    email_to_lph: EmailDraft
    email_to_koperasi: EmailDraft
    email_to_bpjs: Optional[EmailDraft] = None
    
    checklist_koperasi_path: str
    checklist_lph_path: str
    
    explainability_trace: ExplainabilityTrace