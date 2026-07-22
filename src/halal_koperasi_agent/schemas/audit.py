"""
Audit simulation schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class AuditCategory(str, Enum):
    ADMINISTRASI = "A. Persyaratan Administrasi"
    HAS = "B. Halal Assurance System (HAS)"
    BAHAN_BAKU = "C. Bahan Baku & Bahan Penolong"
    PROSES_PRODUKSI = "D. Proses Produksi"
    FASILITAS = "E. Fasilitas & Peralatan"
    KEMASAN = "F. Kemasan & Pelabelan"
    NON_HALAL = "G. Penanganan Produk Non-Halal"
    DOKUMEN = "H. Dokumen & Pencatatan"


class AuditChecklistItem(BaseModel):
    id: str
    category: AuditCategory
    sub_category: str
    checklist_item: str
    description: str
    regulatory_refs: List[str] = Field(default_factory=list)
    is_mandatory: bool = True
    severity_weight: float = 1.0
    evidence_required: List[str] = Field(default_factory=list)
    applicable_to: List[str] = Field(default_factory=["all"])


class AuditFinding(BaseModel):
    checklist_item_id: str
    checklist_item: str
    category: AuditCategory
    requirement_source: str
    status: Literal["PASS", "FAIL", "WARNING", "NOT_APPLICABLE", "PENDING"]
    evidence_found: str
    evidence_expected: str
    gap_description: Optional[str] = None
    recommended_action: Optional[str] = None
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    auto_fixable: bool = False
    estimated_fix_days: int = 0
    responsible_party: Optional[str] = None
    regulatory_citations: List[Any] = Field(default_factory=list)
    agent_reasoning: str


class PriorityAction(BaseModel):
    priority: int
    action: str
    checklist_item_id: str
    responsible: str
    deadline_days: int
    dependencies: List[str] = Field(default_factory=list)
    estimated_cost: Optional[str] = None


class AuditSimulationResult(BaseModel):
    application_id: str
    koperasi_nama: str
    simulated_at: datetime = Field(default_factory=datetime.now)
    simulated_by: str = "audit_simulation_agent_v1"
    
    overall_readiness_score: float = 0.0
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    not_applicable: int = 0
    pending: int = 0
    
    findings: List[AuditFinding] = Field(default_factory=list)
    critical_gaps: List[str] = Field(default_factory=list)
    high_priority_gaps: List[str] = Field(default_factory=list)
    
    category_scores: Dict[str, float] = Field(default_factory=dict)
    
    submission_recommendation: Literal["READY", "NEEDS_MINOR_FIXES", "NEEDS_MAJOR_WORK", "NOT_READY"]
    estimated_time_to_fix_days: int = 0
    priority_actions: List[PriorityAction] = Field(default_factory=list)
    
    agent_version: str = "1.0"
    rag_context_used: List[str] = Field(default_factory=list)