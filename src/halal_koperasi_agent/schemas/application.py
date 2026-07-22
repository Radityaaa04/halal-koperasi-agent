"""
Application and Koperasi schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


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


class AlamatLengkap(BaseModel):
    desa_kelurahan: str
    kecamatan: str
    kabupaten_kota: str
    provinsi: str
    kode_pos: str
    rincian: Optional[str] = None


class KontakKoperasi(BaseModel):
    telepon: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    cp_nama: Optional[str] = None
    cp_telepon: Optional[str] = None
    cp_email: Optional[str] = None


class ProfilUsaha(BaseModel):
    bidang_usaha: str
    kbli_utama: str
    kbli_detail: List[str] = Field(default_factory=list)
    produk_utama: List["ProdukItem"] = Field(default_factory=list)
    kapasitas_produksi_bulan: Dict[str, float] = Field(default_factory=dict)
    jumlah_anggota: int
    jumlah_karyawan: int
    tahun_berdiri: int
    modal_dasar: Optional[float] = None


class ProdukItem(BaseModel):
    nama: str
    sku: str
    kategori: Literal["makanan_olahan", "minuman", "bahan_baku", "jasa"]
    deskripsi: str
    bahan_baku_utama: List[str] = Field(default_factory=list)
    proses_singkat: str
    kemasan: str
    label_halal_saat_ini: bool = False
    sertifikat_halal_nomor: Optional[str] = None
    target_pasar: List[str] = Field(default_factory=list)


class FasilitasProduksi(BaseModel):
    unit_pengolahan_m2: float
    cold_storage_m3: Optional[float] = None
    area_pendingin_m2: Optional[float] = None
    area_kemasan_m2: Optional[float] = None
    kendaraan_distribusi: int = 0
    utilitas: List[str] = Field(default_factory=list)
    sertifikat_lain: List[str] = Field(default_factory=list)


class StatusHalal(BaseModel):
    bersertifikat: bool = False
    nomor_sertifikat: Optional[str] = None
    tanggal_terbit: Optional[datetime] = None
    tanggal_expired: Optional[datetime] = None
    penerbit_lph: Optional[str] = None
    pernah_mengajukan: bool = False
    alasan_belum: Optional[str] = None
    status_pengajuan_sekarang: Optional[Literal["draft", "submitted", "verification", "audit", "decision"]] = None


class KoperasiProfile(BaseModel):
    id: str
    nama: str
    nama_pimpinan: str
    nik_pimpinan: str
    alamat: AlamatLengkap
    kontak: KontakKoperasi
    profil_usaha: ProfilUsaha
    fasilitas: FasilitasProduksi
    status_halal: StatusHalal
    motivasi: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class KoperasiApplication(BaseModel):
    id: str
    koperasi_id: str
    koperasi_nama: str
    status: ApplicationStatus = ApplicationStatus.DRAFT
    current_step: str = "draft"
    progress_percentage: float = 0.0
    
    # Documents (populated by DocumentIntakeAgent)
    documents: Dict[str, Any] = Field(default_factory=dict)
    missing_required_docs: List[str] = Field(default_factory=list)
    document_completeness_score: float = 0.0
    
    # RAG Context
    regulatory_questions: List[str] = Field(default_factory=list)
    rag_answers: List[Any] = Field(default_factory=list)
    
    # Audit
    audit_result: Optional[Any] = None
    
    # Communication
    communication_output: Optional[Any] = None
    
    # Human-in-the-loop
    htl_log: List[Any] = Field(default_factory=list)
    pending_human_review: bool = False
    human_review_checkpoint: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    assigned_lph: Optional[str] = None
    assigned_auditor: Optional[str] = None
    
    # Evaluation
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("progress_percentage")
    @classmethod
    def validate_progress(cls, v: float) -> float:
        return max(0.0, min(100.0, v))