"""
Core schemas for HALAL Koperasi Agent
"""

from .documents import *
from .application import *
from .regulatory import *
from .audit import *
from .communication import *

__all__ = [
    # documents
    "DocumentType",
    "DocumentStatus",
    "ValidationSeverity",
    "ValidationIssue",
    "DocumentMetadata",
    "AktaPendirianFields",
    "NPWPFields",
    "NIBFields",
    "SOPProduksiFields",
    "LangkahProduksi",
    "CCPPoint",
    "DaftarBahanBakuFields",
    "BahanBakuItem",
    "RuteProduksiFields",
    "AreaSegregasi",
    "SertifikatHalalBahanFields",
    "SertifikatHalalItem",
    "LayoutFasilitasFields",
    "AreaLayout",
    "OrganogramHASFields",
    "PersonelHAS",
    "BuktiPelatihanHASFields",
    "PelatihanItem",
    # application
    "KoperasiProfile",
    "AlamatLengkap",
    "KontakKoperasi",
    "ProfilUsaha",
    "ProdukItem",
    "FasilitasProduksi",
    "StatusHalal",
    "ApplicationStatus",
    "KoperasiApplication",
    # regulatory
    "RegulatorySource",
    "RegulatoryChunk",
    "RegulatoryCitation",
    "RAGAnswer",
    "RAGQuestion",
    # audit
    "AuditCategory",
    "AuditChecklistItem",
    "AuditFinding",
    "AuditSimulationResult",
    "PriorityAction",
    # communication
    "ReportFormat",
    "CommunicationOutput",
    "EmailDraft",
    "ExplainabilityTrace",
    "AgentTrace",
    "RAGTrace",
    "HallucinationCheck",
]