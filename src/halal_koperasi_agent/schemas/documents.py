"""
Document-related schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    # Wajib (Mandatory per PP 39/2021 & BPJPH Peraturan 1/2023)
    AKTA_PENDIRIAN = "akta_pendirian"
    ANGGARAN_DASAR = "anggaran_dasar"
    NPWP = "npwp"
    NIB = "nib"
    IZIN_USAHA = "izin_usaha"
    SOP_PRODUKSI = "sop_produksi"
    DAFTAR_BAHAN_BAKU = "daftar_bahan_baku"
    RUTE_PRODUKSI = "rute_produksi"
    SERTIFIKAT_HALAL_BAHAN = "sertifikat_halal_bahan"
    LAYOUT_FASILITAS = "layout_fasilitas"
    ORGANOGRAM_HAS = "organogram_has"
    BUKTI_PELATIHAN_HAS = "bukti_pelatihan_has"
    
    # Kondisional / Tambahan
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
    
    @field_validator("completeness_score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# Per-document-type extraction schemas
class AktaPendirianFields(BaseModel):
    notaris: str
    nomor_akta: str
    tanggal_akta: datetime
    nama_koperasi: str
    alamat_koperasi: str
    pengurus: List[Dict[str, str]]
    anggaran_dasar_ref: Optional[str] = None


class NPWPFields(BaseModel):
    npwp_number: str
    nama_wp: str
    alamat_wp: str
    kpp: Optional[str] = None
    status_wp: Literal["aktif", "non_aktif", "tidak_ditemukan"] = "aktif"


class NIBFields(BaseModel):
    nib_number: str
    nama_usaha: str
    alamat_usaha: str
    kbli_codes: List[str]
    status_nib: Literal["aktif", "tidak_aktif", "dibatalkan"] = "aktif"
    tanggal_terbit: datetime


class SOPProduksiFields(BaseModel):
    versi: str
    tanggal_berlaku: datetime
    penanggung_jawab: str
    jabatan_penanggung_jawab: str
    langkah_produksi: List["LangkahProduksi"]
    ccp_points: List["CCPPoint"]
    catatan: Optional[str] = None


class LangkahProduksi(BaseModel):
    urutan: int
    nama_tahap: str
    deskripsi: str
    peralatan: List[str] = Field(default_factory=list)
    bahan_masuk: List[str] = Field(default_factory=list)
    bahan_keluar: List[str] = Field(default_factory=list)
    parameter_kontrol: List[str] = Field(default_factory=list)
    risiko_kontaminasi: Optional[str] = None
    kontrol_pencegahan: Optional[str] = None
    is_ccp: bool = False
    ccp_number: Optional[str] = None


class CCPPoint(BaseModel):
    ccp_id: str
    nama: str
    parameter_kritis: str
    batas_kritis: str
    pemantauan: str
    tindakan_koreksi: str
    verifikasi: str
    pencatatan: str


class DaftarBahanBakuFields(BaseModel):
    bahan_baku: List["BahanBakuItem"]


class BahanBakuItem(BaseModel):
    nama: str
    kode_internal: Optional[str] = None
    supplier: str
    alamat_supplier: Optional[str] = None
    kategori: Literal["kritis", "menerikan", "rendah"] = "menerikan"
    sertifikat_halal_nomor: Optional[str] = None
    sertifikat_halal_penerbit: Optional[str] = None
    sertifikat_halal_tanggal_terbit: Optional[datetime] = None
    sertifikat_halal_expired: Optional[datetime] = None
    jumlah_penggunaan_bulan_kg: Optional[float] = None
    unit: str = "kg"
    catatan: Optional[str] = None


class RuteProduksiFields(BaseModel):
    flowchart_description: str
    area_segregasi: List["AreaSegregasi"]
    titik_kritis_lintas: List[str]
    cleaning_procedures: List[str]


class AreaSegregasi(BaseModel):
    nama_area: str
    tipe: Literal["halal", "non_halal", "shared", "buffer"]
    lokasi: str
    peralatan_dedicated: bool = False
    peralatan_list: List[str] = Field(default_factory=list)
    prosedur_pembersihan: Optional[str] = None


class SertifikatHalalBahanFields(BaseModel):
    sertifikat_list: List["SertifikatHalalItem"]


class SertifikatHalalItem(BaseModel):
    nomor_sertifikat: str
    nama_produk_bahan: str
    penerbit_lph: str
    tanggal_terbit: datetime
    tanggal_expired: datetime
    scope: str
    status: Literal["valid", "expired", "akan_expired", "tidak_valid"] = "valid"


class LayoutFasilitasFields(BaseModel):
    gambar_base64: Optional[str] = None
    gambar_path: Optional[str] = None
    legend: Dict[str, str] = Field(default_factory=dict)
    skala: Optional[str] = None
    area_list: List["AreaLayout"] = Field(default_factory=list)


class AreaLayout(BaseModel):
    kode: str
    nama: str
    fungsi: str
    luas_m2: Optional[float] = None
    tipe_area: Literal["halal", "non_halal", "shared", "buffer", "utility"]
    peralatan: List[str] = Field(default_factory=list)


class OrganogramHASFields(BaseModel):
    ketua_has: "PersonelHAS"
    anggota_has: List["PersonelHAS"] = Field(default_factory=list)
    struktur_organisasi: Optional[str] = None


class PersonelHAS(BaseModel):
    nama: str
    nik: str
    jabatan: str
    jabatan_has: Literal["Ketua HAS", "Koordinator Produksi", "Koordinator Gudang", "Koordinator QC", "Anggota"]
    pelatihan_has_terakhir: Optional[datetime] = None
    sertifikat_pelatihan_nomor: Optional[str] = None
    sertifikat_pelatihan_penerbit: Optional[str] = None
    masa_berlaku_pelatihan: Optional[datetime] = None
    tugas_tanggung_jawab: List[str] = Field(default_factory=list)


class BuktiPelatihanHASFields(BaseModel):
    pelatihan_list: List["PelatihanItem"] = Field(default_factory=list)


class PelatihanItem(BaseModel):
    nama_pelatihan: str
    penyelenggara: str
    tanggal: datetime
    peserta: List[str]
    sertifikat_nomor: Optional[str] = None
    masa_berlaku: Optional[datetime] = None
    topik: List[str] = Field(default_factory=list)


# Forward references
LangkahProduksi.model_rebuild()
CCPPoint.model_rebuild()
BahanBakuItem.model_rebuild()
AreaSegregasi.model_rebuild()
SertifikatHalalItem.model_rebuild()
AreaLayout.model_rebuild()
PersonelHAS.model_rebuild()
PelatihanItem.model_rebuild()