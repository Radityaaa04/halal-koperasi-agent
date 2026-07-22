"""Unit tests for HALAL Koperasi Multi-Agent System"""
import pytest
import asyncio
from pathlib import Path

from src.halal_koperasi_agent.schemas.documents import (
    DocumentType, DocumentStatus, DocumentMetadata, ValidationIssue, ValidationSeverity
)
from src.halal_koperasi_agent.schemas.audit import (
    AuditCategory, AuditFinding, AuditSimulationResult, PriorityAction
)
from src.halal_koperasi_agent.schemas.regulatory import (
    RegulatorySource, RegulatoryCitation, RAGAnswer
)


# ============================================================
# TEST: Document Intake Agent - Schema Validation
# ============================================================

def test_document_type_enum():
    """Test all required document types are defined"""
    required_types = [
        'AKTA_PENDIRIAN', 'ANGGARAN_DASAR', 'NPWP', 'NIB', 'IZIN_USAHA',
        'SOP_PRODUKSI', 'DAFTAR_BAHAN_BAKU', 'RUTE_PRODUKSI',
        'SERTIFIKAT_HALAL_BAHAN', 'LAYOUT_FASILITAS',
        'ORGANOGRAM_HAS', 'BUKTI_PELATIHAN_HAS'
    ]
    for dt in required_types:
        assert hasattr(DocumentType, dt), f"Missing DocumentType: {dt}"

def test_document_metadata_creation():
    """Test DocumentMetadata can be created with all fields"""
    metadata = DocumentMetadata(
        doc_type=DocumentType.NPWP,
        filename="test_npwp.pdf",
        original_filename="test_npwp.pdf",
        file_path="data/synthetic_docs/kmbj/NPWP.pdf",
        file_size_kb=4,
        mime_type="application/pdf",
        pages=1,
        completeness_score=1.0,
        status=DocumentStatus.VALIDATED,
        extracted_fields={"npwp_number": "01.234.567.8-901.000", "nama_wp": "KOPERASI TEST"},
        validation_issues=[
            ValidationIssue(
                field="npwp_number",
                severity=ValidationSeverity.WARNING,
                message="Format may be invalid",
                regulatory_ref="UU 28/2007"
            )
        ]
    )
    assert metadata.doc_type == DocumentType.NPWP
    assert metadata.completeness_score == 1.0
    assert len(metadata.validation_issues) == 1
    assert metadata.validation_issues[0].severity == ValidationSeverity.WARNING

def test_document_status_enum():
    """Test all document statuses exist"""
    statuses = ['UPLOADED', 'PROCESSING', 'VALIDATED', 'INVALID', 'MISSING', 'EXPIRED']
    for s in statuses:
        assert hasattr(DocumentStatus, s)


# ============================================================
# TEST: Audit Simulation Agent - Schema & Logic
# ============================================================

def test_audit_category_enum():
    """Test all 8 audit categories defined"""
    categories = [
        'ADMINISTRASI', 'HAS', 'BAHAN_BAKU', 'PROSES_PRODUKSI',
        'FASILITAS', 'KEMASAN', 'NON_HALAL', 'DOKUMEN'
    ]
    for c in categories:
        assert hasattr(AuditCategory, c), f"Missing AuditCategory: {c}"

def test_audit_finding_creation():
    """Test AuditFinding can be created with all fields"""
    finding = AuditFinding(
        checklist_item_id="B01",
        checklist_item="Ketua HAS Terpenuhi",
        category=AuditCategory.HAS,
        requirement_source="BPJPH Peraturan 1/2023 Pasal 11, SNI 99001:2023 4.2",
        status="FAIL",
        evidence_found="ORGANOGRAM_HAS.pdf (77%) - Sertifikat pelatihan missing",
        evidence_expected="Sertifikat pelatihan Ketua HAS",
        gap_description="Ketua HAS tidak memiliki sertifikat pelatihan valid",
        recommended_action="Daftarkan Ketua HAS ke pelatihan BPJPH/LPH terdekat",
        severity="CRITICAL",
        auto_fixable=False,
        estimated_fix_days=30,
        responsible_party="Ketua Koperasi",
        regulatory_citations=[],
        agent_reasoning="Mandatory requirement per BPJPH 1/2023"
    )
    assert finding.checklist_item_id == "B01"
    assert finding.status == "FAIL"
    assert finding.severity == "CRITICAL"

def test_audit_simulation_result():
    """Test AuditSimulationResult aggregation"""
    result = AuditSimulationResult(
        application_id="TEST-001",
        koperasi_nama="Koperasi Test",
        overall_readiness_score=45.0,
        total_checks=81,
        passed=20,
        failed=40,
        warnings=15,
        not_applicable=6,
        findings=[],
        critical_gaps=["Gap 1", "Gap 2"],
        high_priority_gaps=["Gap 3"],
        category_scores={
            "A. Persyaratan Administrasi": 80.0,
            "B. Halal Assurance System (HAS)": 25.0
        },
        submission_recommendation="NEEDS_MAJOR_WORK",
        estimated_time_to_fix_days=60,
        priority_actions=[
            PriorityAction(
                priority=1,
                action="Daftarkan Ketua HAS ke pelatihan",
                checklist_item_id="B01",
                responsible="Ketua Koperasi",
                deadline_days=30,
                estimated_cost="Rp 5 Juta - Rp 15 Juta"
            )
        ]
    )
    assert result.total_checks == 81
    assert result.overall_readiness_score == 45.0
    assert result.submission_recommendation == "NEEDS_MAJOR_WORK"
    assert len(result.critical_gaps) == 2


# ============================================================
# TEST: Regulatory RAG Agent - Schema
# ============================================================

def test_regulatory_source_enum():
    """Test all regulatory sources defined"""
    sources = [
        'UU_33_2014', 'PP_39_2021', 'BPJPH_1_2023', 'BPJPH_2_2023',
        'MUI_FATWA', 'LPH_PANDUAN', 'SNI_HALAL', 'KOMINFO_9_2023'
    ]
    for s in sources:
        assert hasattr(RegulatorySource, s), f"Missing RegulatorySource: {s}"

def test_regulatory_citation():
    """Test RegulatoryCitation structure"""
    citation = RegulatoryCitation(
        chunk_id="CHUNK-001",
        source=RegulatorySource.PP_39_2021,
        article="Pasal 12 Ayat 3",
        verse="",
        text_snippet="Setiap produk yang beredar di wilayah Indonesia wajib memiliki sertifikat halal...",
        relevance_score=0.95,
        page_number=15
    )
    assert citation.source == RegulatorySource.PP_39_2021
    assert citation.article == "Pasal 12 Ayat 3"
    assert citation.relevance_score == 0.95

def test_rag_answer():
    """Test RAGAnswer structure"""
    answer = RAGAnswer(
        question="Apa syarat sertifikat halal untuk koperasi mikro?",
        answer="Koperasi mikro memerlukan: AKTA pendirian sah, NPWP aktif, NIB via OSS, izin usaha valid, profil usaha & produk, surat kuasa pengurus, surat pernyataan kebersamaan halal, daftar anggota & pengurus lengkap.",
        citations=[
            RegulatoryCitation(
                chunk_id="CHUNK-001",
                source=RegulatorySource.BPJPH_1_2023,
                article="Pasal 7",
                verse="",
                text_snippet="Pengajuan sertifikat halal dilakukan oleh pengurus koperasi...",
                relevance_score=0.9
            ),
            RegulatoryCitation(
                chunk_id="CHUNK-002",
                source=RegulatorySource.PP_39_2021,
                article="Pasal 14",
                verse="",
                text_snippet="Koperasi mikro dan kecil mendapat kemudahan prosedur...",
                relevance_score=0.85
            )
        ],
        confidence=0.92,
        needs_human_verification=False,
        verification_reason=None,
        retrieved_chunks=["CHUNK-001", "CHUNK-002"],
        retrieval_strategy="hybrid_rrf_rerank",
        model_used="meta/llama-3.1-8b-instruct"
    )
    assert answer.confidence == 0.92
    assert len(answer.citations) == 2
    assert answer.citations[0].source == RegulatorySource.BPJPH_1_2023
    assert answer.needs_human_verification is False


# ============================================================
# TEST: Integration - Document Intake Flow
# ============================================================

def test_document_intake_import():
    """Test document intake agent module structure (lightweight, no heavy deps)"""
    from pathlib import Path
    agent_path = Path("src/halal_koperasi_agent/agents/document_intake.py")
    assert agent_path.exists(), "document_intake.py not found"
    content = agent_path.read_text(encoding="utf-8")
    assert "class DocumentIntakeAgent" in content, "DocumentIntakeAgent class not found"
    assert "def process_document" in content, "process_document method not found"
    assert "def _get_llm" in content, "_get_llm method not found"

def test_regulatory_rag_import():
    """Test regulatory RAG agent module structure (lightweight, no heavy deps)"""
    from pathlib import Path
    agent_path = Path("src/halal_koperasi_agent/agents/regulatory_rag.py")
    assert agent_path.exists(), "regulatory_rag.py not found"
    content = agent_path.read_text(encoding="utf-8")
    assert "class RegulatoryRAGAgent" in content, "RegulatoryRAGAgent class not found"
    assert "def answer_question" in content, "answer_question method not found"
    assert "def _rerank" in content, "_rerank method not found"

def test_audit_simulation_import():
    """Test audit simulation agent module structure (lightweight, no heavy deps)"""
    from pathlib import Path
    agent_path = Path("src/halal_koperasi_agent/agents/audit_simulation.py")
    assert agent_path.exists(), "audit_simulation.py not found"
    content = agent_path.read_text(encoding="utf-8")
    assert "class AuditSimulationAgent" in content, "AuditSimulationAgent class not found"
    assert "def run_audit" in content, "run_audit method not found"
    assert "def _check_field_requirements" in content, "_check_field_requirements method not found"


# ============================================================
# TEST: State Management
# ============================================================

def test_create_initial_state():
    """Test initializes_all_fields"""
    from src.halal_koperasi_agent.state import create_initial_state
    
    state = create_initial_state(
        application_id="TEST-001",
        koperasi_name="Koperasi Test",
        koperasi_location="Jakarta",
        produk_utama=["Produk A", "Produk B"]
    )
    
    assert state["application_id"] == "TEST-001"
    assert state["koperasi_name"] == "Koperasi Test"
    assert state["status"] == "draft"
    assert state["progress_percentage"] == 0.0
    assert state["documents"] == {}
    assert state["document_completeness_score"] == 0.0
    assert state["pending_human_review"] is False
    assert state["bypass_human_review"] is False  # New field from P4
    assert isinstance(state["messages"], list)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])