"""
State management for HALAL Koperasi Agent using LangGraph
"""

from typing import TypedDict, List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class DocumentType(str, Enum):
    """Jenis dokumen wajib untuk sertifikasi halal (per PP 39/2021 & BPJPH Peraturan 1/2023)"""
    AKTA_PENDIRIAN = "akta_pendirian"
    ANGGARAN_DASAR = "anggaran_dasar"
    NPWP = "npwp"
    NIB = "nib"
    IZIN_USAHA = "izin_usaha"  # SKTU / Izin Usaha Mikro/Kecil
    SOP_PRODUKSI = "sop_produksi"
    DAFTAR_BAHAN_BAKU = "daftar_bahan_baku"
    RUTE_PRODUKSI = "rute_produksi"
    SERTIFIKAT_HALAL_BAHAN = "sertifikat_halal_bahan"
    LAYOUT_FASILITAS = "layout_fasilitas"
    ORGANOGRAM_HAS = "organogram_has"
    BUKTI_PELATIHAN_HAS = "bukti_pelatihan_has"
    SERTIFIKAT_HALAL_SEBELUMNYA = "sertifikat_halal_sebelumnya"
    HASIL_AUDIT_INTERNAL = "hasil_audit_internal"
    MANAJEMEN_REVIEW = "manajemen_review"
    LAINNYA = "lainnya"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VALIDATED = "validated"
    INVALID = "invalid"
    MISSING = "missing"
    EXPIRED = "expired"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    field: str
    severity: ValidationSeverity
    message: str
    regulatory_ref: Optional[str] = None
    suggested_fix: Optional[str] = None


class DocumentMetadata(BaseModel):
    doc_type: DocumentType
    filename: str
    original_filename: str
    file_path: str
    file_size_kb: int
    mime_type: str
    pages: int
    upload_timestamp: datetime = Field(default_factory=datetime.now)
    uploaded_by: str = "system"
    
    # OCR & Extraction Results
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    extraction_method: Literal["pymupdf", "paddleocr", "manual", "template"] = "pymupdf"
    
    # Validation Results
    status: DocumentStatus = DocumentStatus.UPLOADED
    completeness_score: float = 0.0
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    
    # Regulatory Mapping
    regulatory_refs: List[str] = Field(default_factory=list)
    
    # Versioning
    version: int = 1
    previous_version_id: Optional[str] = None


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    DOCUMENT_INTAKE = "document_intake"
    REGULATORY_REVIEW = "regulatory_review"
    AUDIT_SIMULATION = "audit_simulation"
    HUMAN_REVIEW = "human_review"
    READY_FOR_SUBMISSION = "ready_for_submission"
    SUBMITTED_TO_LPH = "submitted_to_lph"
    UNDER_LPH_AUDIT = "under_lph_audit"
    CERTIFIED = "certified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RegulatorySource(str, Enum):
    UU_33_2014 = "UU_33_2014"
    PP_39_2021 = "PP_39_2021"
    BPJPH_1_2023 = "BPJPH_1_2023"
    BPJPH_2_2023 = "BPJPH_2_2023"
    MUI_FATWA = "MUI_FATWA"
    LPH_PANDUAN = "LPH_PANDUAN"
    SNI_HALAL = "SNI_HALAL"
    KOMINFO_9_2023 = "KOMINFO_9_2023"


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


class AuditCategory(str, Enum):
    ADMINISTRASI = "A. Persyaratan Administrasi"
    HAS = "B. Halal Assurance System (HAS)"
    BAHAN_BAKU = "C. Bahan Baku & Bahan Penolong"
    PROSES_PRODUKSI = "D. Proses Produksi"
    FASILITAS = "E. Fasilitas & Peralatan"
    KEMASAN = "F. Kemasan & Pelabelan"
    NON_HALAL = "G. Penanganan Produk Non-Halal"
    DOKUMEN = "H. Dokumen & Pencatatan"


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
    regulatory_citations: List[RegulatoryCitation] = Field(default_factory=list)
    agent_reasoning: str = ""


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
    priority_actions: List[Dict[str, Any]] = Field(default_factory=list)
    
    agent_version: str = "1.0"
    rag_context_used: List[str] = Field(default_factory=list)


class HTLLogEntry(BaseModel):
    """Human-in-the-loop log for explainability & hallucination tracking"""
    step: str
    agent: str
    input_summary: str
    output_summary: str
    human_action: Optional[Literal["APPROVED", "MODIFIED", "REJECTED", "REQUESTED_INFO"]] = None
    human_feedback: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence_at_step: float


class ApplicationState(TypedDict):
    # Identity
    application_id: str
    koperasi_name: str
    koperasi_location: str
    produk_utama: List[str]
    
    # Status & Progress
    status: ApplicationStatus
    current_step: str
    progress_percentage: float
    started_at: datetime
    updated_at: datetime
    deadline: Optional[datetime]
    
    # Documents
    documents: Dict[DocumentType, DocumentMetadata]
    missing_required_docs: List[DocumentType]
    document_completeness_score: float
    
    # RAG Context
    regulatory_questions: List[str]
    rag_answers: List[RAGAnswer]
    rag_context_used: List[str]
    
    # Audit
    audit_result: Optional[AuditSimulationResult]
    
    # Communication
    communication_output: Optional[Dict[str, Any]]
    
    # Human-in-the-loop
    htl_log: List[HTLLogEntry]
    pending_human_review: bool
    human_review_checkpoint: Optional[str]
    bypass_human_review: bool  # For automated test runs
    
    # Evaluation
    evaluation_metrics: Dict[str, Any]
    
    # Messages (for LangGraph streaming)
    messages: List[Dict[str, Any]]


def create_initial_state(
    application_id: str,
    koperasi_name: str,
    koperasi_location: str,
    produk_utama: List[str]
) -> ApplicationState:
    """Create initial application state"""
    now = datetime.now()
    return ApplicationState(
        application_id=application_id,
        koperasi_name=koperasi_name,
        koperasi_location=koperasi_location,
        produk_utama=produk_utama,
        status=ApplicationStatus.DRAFT,
        current_step="initialized",
        progress_percentage=0.0,
        started_at=now,
        updated_at=now,
        deadline=None,
        documents={},
        missing_required_docs=list(DocumentType)[:12],  # First 12 are mandatory
        document_completeness_score=0.0,
        regulatory_questions=[],
        rag_answers=[],
        rag_context_used=[],
        audit_result=None,
        communication_output=None,
        htl_log=[],
        pending_human_review=False,
        human_review_checkpoint=None,
        bypass_human_review=False,
        evaluation_metrics={},
        messages=[]
    )


def add_message(state: ApplicationState, role: str, content: str, metadata: Dict = None) -> ApplicationState:
    """Add a message to the state for streaming"""
    msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
    if metadata:
        msg["metadata"] = metadata
    state["messages"].append(msg)
    return state


def log_htl(
    state: ApplicationState,
    step: str,
    agent: str,
    input_summary: str,
    output_summary: str,
    confidence: float,
    human_action: str = None,
    human_feedback: str = None
) -> ApplicationState:
    """Log human-in-the-loop interaction"""
    entry = HTLLogEntry(
        step=step,
        agent=agent,
        input_summary=input_summary,
        output_summary=output_summary,
        human_action=human_action,
        human_feedback=human_feedback,
        confidence_at_step=confidence
    )
    state["htl_log"].append(entry)
    return state


def update_progress(state: ApplicationState, step: str, progress: float) -> ApplicationState:
    """Update application progress"""
    state["current_step"] = step
    state["progress_percentage"] = progress
    state["updated_at"] = datetime.now()
    return state