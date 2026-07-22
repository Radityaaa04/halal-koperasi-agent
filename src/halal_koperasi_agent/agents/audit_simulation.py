#!/usr/bin/env python3
"""
Audit Simulation Agent for HALAL Koperasi Multi-Agent System
Simulates LPH audit using 80-item checklist from Indonesian halal regulations.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from halal_koperasi_agent.config import settings
from halal_koperasi_agent.schemas.audit import (
    AuditCategory,
    AuditChecklistItem,
    AuditFinding,
    AuditSimulationResult,
    PriorityAction,
)
from halal_koperasi_agent.schemas.documents import DocumentType, DocumentMetadata
from halal_koperasi_agent.agents.regulatory_rag import RegulatoryRAGAgent
from halal_koperasi_agent.llm_providers import chat_completion, ChatMessage


class AuditSimulationAgent:
    """
    Agent responsible for:
    1. Loading 80-item audit checklist from regulations
    2. Mapping extracted document fields to checklist items
    3. Scoring readiness (0-100) with critical/major/minor gaps
    4. Outputting recommendation: READY / NEEDS_MINOR_FIXES / NEEDS_MAJOR_WORK / NOT_READY
    """

    def __init__(self):
        self.checklist: List[AuditChecklistItem] = []
        self.rag_agent = RegulatoryRAGAgent()
        self._initialized = False

    async def initialize(self):
        """Initialize RAG agent and load checklist"""
        if self._initialized:
            return

        logger.info("Initializing Audit Simulation Agent...")
        await self.rag_agent.initialize()
        await self._load_checklist()
        self._initialized = True
        logger.success(f"Audit Simulation Agent initialized with {len(self.checklist)} checklist items")

    async def _load_checklist(self):
        """Load audit checklist from JSON file or generate from regulations"""
        checklist_path = Path(settings.DATA_DIR) / "audit_checklist.json"
        
        if checklist_path.exists():
            with open(checklist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.checklist = [AuditChecklistItem(**item) for item in data]
            logger.info(f"Loaded {len(self.checklist)} checklist items from file")
        else:
            # Generate default checklist from regulations
            self.checklist = self._generate_default_checklist()
            # Save for future use
            checklist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(checklist_path, 'w', encoding='utf-8') as f:
                json.dump([item.model_dump(mode='json') for item in self.checklist], f, indent=2, ensure_ascii=False)
            logger.info(f"Generated {len(self.checklist)} default checklist items")

    def _generate_default_checklist(self) -> List[AuditChecklistItem]:
        """Generate 80-item checklist based on Indonesian halal regulations"""
        items = []

        # A. PERSYARATAN ADMINISTRASI (10 items)
        admin_items = [
            ("A01", "Akta Pendirian Koperasi", "Akta pendirian sah dan tercatat di Kemenkumham", 
             ["UU 25/2008 Pasal 43", "BPJPH Peraturan 1/2023 Pasal 7"]),
            ("A02", "Anggaran Dasar Koperasi", "AD mencakup tujuan usaha halal", 
             ["UU 25/2008 Pasal 12", "PP 39/2021 Pasal 14"]),
            ("A03", "NPWP Koperasi", "NPWP aktif dan sesuai identitas", 
             ["UU 28/2007 Pasal 2"]),
            ("A04", "NIB (Nomor Induk Berusaha)", "NIB aktif via OSS", 
             ["UU 11/2020", "PP 39/2021 Pasal 14"]),
            ("A05", "Izin Usaha / SIUP", "Izin usaha valid dan belum expired", 
             ["UU 20/2008", "PP 39/2021"]),
            ("A06", "SKTU / Sertifikat Koperasi", "Sah dan berlaku", 
             ["UU 25/2008 Pasal 47"]),
            ("A07", "Daftar Anggota & Pengurus", "Lengkap dengan NIK, alamat, jabatan", 
             ["UU 25/2008 Pasal 43"]),
            ("A08", "Surat Kuasa Pengurus", "Untuk mengurus sertifikasi halal", 
             ["BPJPH Peraturan 1/2023 Pasal 7"]),
            ("A09", "Surat Pernyataan Kebersamaan", "Komitmen halal dari semua pengurus", 
             ["PP 39/2021 Pasal 14"]),
            ("A10", "Profil Usaha & Produk", "Deskripsi usaha, produk, kapasitas produksi", 
             ["BPJPH Peraturan 1/2023 Pasal 8"]),
        ]

        for idx, (cid, item, desc, refs) in enumerate(admin_items):
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.ADMINISTRASI,
                sub_category="Administrasi Umum",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        # B. HALAL ASSURANCE SYSTEM (HAS) - 12 items
        has_items = [
            ("B01", "Ketua HAS Terpenuhi", "Ketua HAS memiliki sertifikat pelatihan valid", 
             ["BPJPH Peraturan 1/2023 Pasal 11", "SNI 99001:2023 4.2"]),
            ("B02", "Anggota HAS Lengkap", "Minimal 3 anggota (Ketua, Sekretaris, Audit Internal)", 
             ["SNI 99001:2023 4.2"]),
            ("B03", "Pelatihan HAS Terbaru", "Semua anggota HAS lulus pelatihan BPJPH/LPH", 
             ["BPJPH Peraturan 1/2023 Pasal 11"]),
            ("B04", "Manual HAS (MHAS)", "Terdapat manual HAS versi terbaru", 
             ["SNI 99001:2023 4.3"]),
            ("B05", "Prosedur Operasional HAS", "SOP untuk setiap aktivitas HAS", 
             ["SNI 99001:2023 4.4"]),
            ("B06", "Tim Verifikasi Internal", "Terdapat tim verifikasi internal berkala", 
             ["SNI 99001:2023 8.2"]),
            ("B07", "Audit Internal HAS", "Audit internal minimal 1x/tahun", 
             ["SNI 99001:2023 9.2"]),
            ("B08", "Manajemen Perubahan", "Prosedur perubahan bahan/proses/fasilitas", 
             ["SNI 99001:2023 7.4"]),
            ("B09", "Penanganan Ketidaksesuaian", "Prosedur non-conformance & koreksi", 
             ["SNI 99001:2023 10.2"]),
            ("B10", "Pencatatan & Dokumentasi HAS", "Semua aktivitas HAS terdokumen", 
             ["SNI 99001:2023 7.5"]),
            ("B11", "Management Review", "Review manajemen HAS berkala", 
             ["SNI 99001:2023 9.3"]),
            ("B12", "Komunikasi Internal/Eksternal", "Saluran komunikasi halal jelas", 
             ["SNI 99001:2023 7.4"]),
        ]

        for cid, item, desc, refs in has_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.HAS,
                sub_category="Struktur & SDM HAS" if cid in ["B01", "B02", "B03"] else "Sistem HAS",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if cid in ["B01", "B03", "B04"] else 1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        # C. BAHAN BAKU & BAHAN PENOLONG (14 items)
        bahan_items = [
            ("C01", "Daftar Bahan Baku Lengkap", "Semua bahan baku terdaftar dengan kode internal", 
             ["PP 39/2021 Pasal 16", "BPJPH Peraturan 2/2023"]),
            ("C02", "Sertifikat Halal Bahan Baku", "Setiap bahan baku kritis punya sertifikat halal valid", 
             ["PP 39/2021 Pasal 16", "BPJPH Peraturan 2/2023 Pasal 5"]),
            ("C03", "Sertifikat Halal Tidak Expired", "Tidak ada sertifikat halal bahan baku yang expired", 
             ["PP 39/2021 Pasal 16"]),
            ("C04", "Supplier Bahan Baku Terverifikasi", "Supplier memiliki sertifikat halal/LPH terdaftar", 
             ["BPJPH Peraturan 2/2023 Pasal 6"]),
            ("C05", "Bahan Penolong Produksi", "Enzim, mikroba, dll memiliki sertifikat halal", 
             ["MUI Fatwa No. 4/2003", "BPJPH Peraturan 2/2023"]),
            ("C06", "Segregasi Bahan Halal/Non-Halal", "Gudang & penanganan terpisah", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.2"]),
            ("C07", "Penerimaan Bahan Baku", "Prosedur penerimaan dengan verifikasi halal", 
             ["SNI 99001:2023 8.4"]),
            ("C08", "Identifikasi & Traceability", "Setiap batch bahan baku traceable", 
             ["SNI 99001:2023 8.5.2"]),
            ("C09", "Kontrol Bahan Non-Halal", "Kontrol ketat bahan non-halal (jika ada)", 
             ["PP 39/2021 Pasal 15", "MUI Fatwa"]),
            ("C10", "Bahan Baku Hewan", "Jika ada bahan hewan: sertifikat halal & rantai pasokan", 
             ["MUI Fatwa No. 12/2010", "BPJPH Peraturan 2/2023"]),
            ("C11", "Bahan Baku Minuman", "Jika ada minuman: bebas alkohol/khamer", 
             ["MUI Fatwa No. 10/2018", "PP 39/2021"]),
            ("C12", "Bahan Kimia & Aditif", "Semua aditif food-grade & halal certified", 
             ["BPOM Peraturan", "MUI Fatwa"]),
            ("C13", "Kontrak/Jaminan Supplier", "Surat jaminan halal dari supplier", 
             ["BPJPH Peraturan 2/2023 Pasal 7"]),
            ("C14", "Monitoring Berkala Supplier", "Evaluasi supplier minimal 1x/tahun", 
             ["SNI 99001:2023 8.4"]),
        ]

        for cid, item, desc, refs in bahan_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.BAHAN_BAKU,
                sub_category="Sertifikasi Bahan" if cid in ["C02", "C03", "C04", "C05"] else "Manajemen Bahan",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if cid in ["C02", "C03", "C06"] else 1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        # D. PROSES PRODUKSI (15 items)
        proses_items = [
            ("D01", "SOP Produksi Lengkap", "SOP mencakup semua tahap produksi", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.1"]),
            ("D02", "Identifikasi CCP (Critical Control Points)", "CCP teridentifikasi per prinsip HACCP", 
             ["SNI 99001:2023", "HACCP Principle 2"]),
            ("D03", "Batas Kritis (Critical Limits) CCP", "Setiap CCP punya batas kritis terukur", 
             ["HACCP Principle 3"]),
            ("D04", "Sistem Pemantauan CCP", "Monitoring CCP real-time/terjadwal", 
             ["HACCP Principle 4"]),
            ("D05", "Tindakan Koreksi CCP", "Prosedur koreksi jika CCP melampaui batas", 
             ["HACCP Principle 5"]),
            ("D06", "Verifikasi CCP", "Verifikasi efektivitas CCP berkala", 
             ["HACCP Principle 6"]),
            ("D06", "Dokumentasi CCP", "Rekaman pemantauan CCP lengkap", 
             ["HACCP Principle 7", "SNI 99001:2023 7.5"]),
            ("D07", "Segregasi Proses Halal/Non-Halal", "Jalur produksi & peralatan terpisah", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.2"]),
            ("D08", "Pembersihan Antara Produk", "Prosedur cleaning & validasi kebersihan", 
             ["SNI 99001:2023 8.5.2"]),
            ("D09", "Penggunaan Air & Utilitas", "Air & utilitas bebas kontaminan non-halal", 
             ["SNI 99001:2023 8.5.3"]),
            ("D10", "Kontrol Kontaminasi Silang", "Pencegahan cross-contamination lengkap", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.2"]),
            ("D11", "Manajemen Limbah", "Limbah tidak mencemari produk halal", 
             ["SNI 99001:2023 8.5.4"]),
            ("D12", "Kalibrasi Alat Ukur", "Semua alat CCP terkalibrasi berkala", 
             ["SNI 99001:2023 7.1.5"]),
            ("D13", "Pelatihan Operator CCP", "Operator CCP terlatih & kompeten", 
             ["SNI 99001:2023 7.2"]),
            ("D14", "Validasi Proses Produksi", "Validasi awal & periodik proses", 
             ["SNI 99001:2023 8.5.1"]),
            ("D15", "Rekaman Produksi Harian", "Log produksi lengkap & traceable", 
             ["SNI 99001:2023 7.5"]),
        ]

        for idx, (cid, item, desc, refs) in enumerate(proses_items):
            # Fix duplicate D06
            actual_cid = f"D{idx+1:02d}"
            items.append(AuditChecklistItem(
                id=actual_cid,
                category=AuditCategory.PROSES_PRODUKSI,
                sub_category="SOP & HACCP" if idx < 7 else "Kontrol Proses",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if idx < 7 else 1.0,
                evidence_required=[f"{actual_cid}_document"],
                applicable_to=["all"]
            ))

        # E. FASILITAS & PERALATAN (10 items)
        fasilitas_items = [
            ("E01", "Layout Fasilitas (Gambar Teknis)", "Layout lengkap dengan zona halal/non-halal", 
             ["PP 39/2021 Pasal 15", "BPJPH Peraturan 1/2023 Pasal 9"]),
            ("E02", "Zonasi Area Halal", "Area produksi, penyimpanan, kemasan terpisah", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.2"]),
            ("E03", "Fasilitas Pencucian & Sanitasi", "Cukup & terpisah untuk halal/non-halal", 
             ["SNI 99001:2023 8.5.2"]),
            ("E04", "Peralatan Khusus Halal", "Peralatan dedicated untuk produksi halal", 
             ["PP 39/2021 Pasal 15"]),
            ("E05", "Identifikasi Peralatan", "Label/tanda peralatan halal vs non-halal", 
             ["SNI 99001:2023 8.5.2"]),
            ("E06", "Kondisi Kebersihan Fasilitas", "Kebersihan memenuhi standar GMP", 
             ["SNI 99001:2023 8.5"]),
            ("E07", "Pengendalian Hama (Pest Control)", "Program pest control terdocumentasi", 
             ["SNI 99001:2023 8.5.4"]),
            ("E08", "Manajemen Air & Limbah", "Sistem air bersih & limbah terpisah", 
             ["SNI 99001:2023 8.5.3"]),
            ("E09", "Ventilasi & Pencahayaan", "Memenuhi kebutuhan produksi & higiene", 
             ["SNI 99001:2023 8.5"]),
            ("E10", "Maintenance Preventif", "Jadwal maintenance peralatan terencana", 
             ["SNI 99001:2023 7.1.5"]),
        ]

        for cid, item, desc, refs in fasilitas_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.FASILITAS,
                sub_category="Layout & Zonasi" if cid in ["E01", "E02"] else "Fasilitas Fisik",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if cid in ["E01", "E02", "E04"] else 1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        # F. KEMASAN & PELABELAN (8 items)
        kemasan_items = [
            ("F01", "Logo Halal pada Kemasan", "Logo halal Indonesia per Kominfo 9/2023", 
             ["Kominfo 9/2023", "PP 39/2021 Pasal 20"]),
            ("F02", "Kesesuaian Logo Halal", "Ukuran, warna, posisi logo sesuai ketentuan", 
             ["Kominfo 9/2023 Pasal 4"]),
            ("F03", "Informasi Wajib Label", "Nama produk, bahan, netto, expired, dll", 
             ["BPOM Peraturan 27/2017", "PP 39/2021"]),
            ("F04", "Nomor Sertifikat Halal pada Label", "Nomor sertifikat tertera", 
             ["PP 39/2021 Pasal 20"]),
            ("F05", "Kemasan Primer Halal", "Material kemasan bebas kontaminan non-halal", 
             ["SNI 99001:2023 8.5.5", "MUI Fatwa"]),
            ("F06", "Kemasan Sekunder/Tersier", "Segregasi kemasan halal/non-halal", 
             ["SNI 99001:2023 8.5.5"]),
            ("F07", "Label Digital (E-Commerce)", "Logo halal digital per Kominfo 9/2023", 
             ["Kominfo 9/2023 Pasal 5"]),
            ("F08", "Verifikasi Label Sebelum Cetak", "Proses approval label sebelum produksi", 
             ["SNI 99001:2023 8.5.5"]),
        ]

        for cid, item, desc, refs in kemasan_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.KEMASAN,
                sub_category="Pelabelan" if cid in ["F01", "F02", "F03", "F04"] else "Kemasan",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if cid in ["F01", "F02", "F04"] else 1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        # G. PENANGANAN PRODUK NON-HALAL (6 items)
        nonhalal_items = [
            ("G01", "Identifikasi Produk Non-Halal", "Daftar produk/jalur non-halal jelas", 
             ["PP 39/2021 Pasal 15", "MUI Fatwa"]),
            ("G02", "Segregasi Fisik Non-Halal", "Area, peralatan, gudang terpisah total", 
             ["PP 39/2021 Pasal 15", "SNI 99001:2023 8.5.2"]),
            ("G03", "Prosedur Pembersihan Non-Halal", "Cleaning validated setelah non-halal", 
             ["SNI 99001:2023 8.5.2"]),
            ("G04", "Pencatatan Produk Non-Halal", "Log produksi non-halal terpisah", 
             ["SNI 99001:2023 7.5"]),
            ("G05", "Pelatihan Personel Non-Halal", "Personel paham risiko kontaminasi", 
             ["SNI 99001:2023 7.2"]),
            ("G06", "Audit Internal Non-Halal", "Pemeriksaan berkala segregasi", 
             ["SNI 99001:2023 9.2"]),
        ]

        for cid, item, desc, refs in nonhalal_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.NON_HALAL,
                sub_category="Segregasi & Prosedur",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.5 if cid in ["G01", "G02"] else 1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["mixed"]  # Only if facility handles non-halal too
            ))

        # H. DOKUMEN & PENCATATAN (5 items)
        dokumen_items = [
            ("H01", "Master List Dokumen HAS", "Daftar master semua dokumen HAS versi terkini", 
             ["SNI 99001:2023 7.5.2"]),
            ("H02", "Kontrol Dokumen", "Prosedur review, approval, distribusi dokumen", 
             ["SNI 99001:2023 7.5.3"]),
            ("H03", "Rekaman HAS Lengkap", "Semua rekaman HAS tersimpan & traceable", 
             ["SNI 99001:2023 7.5.1"]),
            ("H04", "Retensi Dokumen", "Kebijakan retensi minimal 3 tahun", 
             ["SNI 99001:2023 7.5.4"]),
            ("H05", "Akses & Keamanan Dokumen", "Kontrol akses dokumen sensitif", 
             ["SNI 99001:2023 7.5.3"]),
        ]

        for cid, item, desc, refs in dokumen_items:
            items.append(AuditChecklistItem(
                id=cid,
                category=AuditCategory.DOKUMEN,
                sub_category="Manajemen Dokumen",
                checklist_item=item,
                description=desc,
                regulatory_refs=refs,
                is_mandatory=True,
                severity_weight=1.0,
                evidence_required=[f"{cid}_document"],
                applicable_to=["all"]
            ))

        return items

    async def run_audit(
        self,
        application_id: str,
        koperasi_nama: str,
        documents: Dict[DocumentType, DocumentMetadata],
    ) -> AuditSimulationResult:
        """Run full audit simulation"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"Running audit simulation for {application_id} ({koperasi_nama})")

        # Map documents to evidence
        evidence_map = self._map_evidence(documents)
        
        # Evaluate each checklist item
        findings = []
        for item in self.checklist:
            finding = await self._evaluate_item(item, evidence_map, documents)
            findings.append(finding)

        # Calculate scores
        result = self._calculate_result(
            application_id=application_id,
            koperasi_nama=koperasi_nama,
            findings=findings,
        )

        logger.success(
            f"Audit complete: Score={result.overall_readiness_score:.1f}%, "
            f"Recommendation={result.submission_recommendation}"
        )
        return result

    def _map_evidence(self, documents: Dict[DocumentType, DocumentMetadata]) -> Dict[str, Any]:
        """Map document types to checklist evidence keys with field-level validation"""
        mapping = {
            DocumentType.AKTA_PENDIRIAN: ["A01", "A02", "A07", "A08", "A09"],
            DocumentType.ANGGARAN_DASAR: ["A02"],
            DocumentType.NPWP: ["A03"],
            DocumentType.NIB: ["A04"],
            DocumentType.IZIN_USAHA: ["A05"],
            DocumentType.SOP_PRODUKSI: ["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D15"],
            DocumentType.DAFTAR_BAHAN_BAKU: ["C01", "C02", "C03", "C04", "C05", "C07", "C08", "C13"],
            DocumentType.RUTE_PRODUKSI: ["D07", "D08", "D10", "E01", "E02", "G02"],
            DocumentType.SERTIFIKAT_HALAL_BAHAN: ["C02", "C03", "C04", "C05", "C10", "C11", "C12", "C13"],
            DocumentType.LAYOUT_FASILITAS: ["E01", "E02", "E03", "E04", "E05", "G02"],
            DocumentType.ORGANOGRAM_HAS: ["B01", "B02", "B03", "B12"],
            DocumentType.BUKTI_PELATIHAN_HAS: ["B03", "B12", "D13"],
        }
        
        evidence = {}
        for doc_type, keys in mapping.items():
            if doc_type in documents:
                meta = documents[doc_type]
                extracted = meta.extracted_fields or {}
                
                # Field-level validation for each checklist item
                for key in keys:
                    if key not in evidence:
                        evidence[key] = []
                    
                    # Check specific fields required for this checklist item
                    field_validation = self._validate_fields_for_checklist(key, extracted)
                    
                    evidence[key].append({
                        "doc_type": doc_type.value,
                        "status": meta.status.value,
                        "completeness": meta.completeness_score,
                        "fields": extracted,
                        "field_validation": field_validation,
                        "issues": meta.validation_issues,
                    })
        return evidence

    def _validate_fields_for_checklist(self, checklist_id: str, extracted: Dict[str, Any]) -> Dict[str, bool]:
        """Validate specific fields required for each checklist item"""
        # Define required fields per checklist item
        field_requirements = {
            "A01": ["notaris", "nomor_akta", "tanggal_akta", "nama_koperasi", "alamat_koperasi", "pengurus"],
            "A02": ["nama_koperasi"],  # From Anggaran Dasar
            "A03": ["npwp_number", "nama_wp", "alamat_wp"],
            "A04": ["nib_number", "nama_usaha", "alamat_usaha", "kbli_codes"],
            "A05": ["izin_nomor", "izin_tgl_terbit", "izin_tgl_berlaku", "izin_instansi"],
            "A07": ["pengurus"],  # From AKTA
            "A08": [],  # Surat kuasa - not in extracted fields yet
            "A09": [],  # Pernyataan kesediaan
            "A10": ["nama_koperasi", "produk_utama"],  # Profil usaha
            
            "B01": ["ketua_has", "sertifikat_pelatihan_nomor", "sertifikat_pelatihan_penerbit", "masa_berlaku_pelatihan"],
            "B02": ["anggota_has"],
            "B03": ["anggota_has", "pelatihan_list"],
            
            "C01": ["bahan_baku"],
            "C02": ["bahan_baku", "sertifikat_halal_nomor", "sertifikat_halal_penerbit", "sertifikat_halal_expired"],
            "C03": ["bahan_baku", "sertifikat_halal_expired"],
            
            "D01": ["versi", "tanggal_berlaku", "penanggung_jawab", "langkah_produksi", "ccp_points"],
            "D02": ["ccp_points"],
            "D07": ["langkah_produksi"],  # segregasi
            "D08": ["langkah_produksi"],
            "D15": ["langkah_produksi"],  # rekaman produksi
            
            "E01": ["legend", "area_list"],
            "E02": ["area_list"],  # zonasi
            
            "F01": [],  # Logo - visual check
            "F04": [],  # Nomor sertifikat di label
            
            "H01": [],  # Master list dokumen
            "H03": [],  # Rekaman HAS
        }
        
        required = field_requirements.get(checklist_id, [])
        if not required:
            return {}
        
        validation = {}
        for field in required:
            value = extracted.get(field)
            validation[field] = value is not None and value != "" and value != [] and value != {}
        
        return validation

    async def _evaluate_item(
        self,
        item: AuditChecklistItem,
        evidence_map: Dict[str, Any],
        documents: Dict[DocumentType, DocumentMetadata],
    ) -> AuditFinding:
        """Evaluate single checklist item using evidence + RAG"""
        
        # Get evidence for this item
        item_evidence = evidence_map.get(item.id, [])
        
        # Quick check: if no evidence at all for mandatory item
        if not item_evidence and item.is_mandatory:
            return AuditFinding(
                checklist_item_id=item.id,
                checklist_item=item.checklist_item,
                category=item.category,
                requirement_source=", ".join(item.regulatory_refs),
                status="FAIL",
                evidence_found="Tidak ada dokumen pendukung",
                evidence_expected=", ".join(item.evidence_required),
                gap_description=f"Item wajib {item.checklist_item} tidak memiliki bukti dokumen",
                recommended_action=f"Siapkan dokumen: {', '.join(item.evidence_required)}",
                severity="CRITICAL",
                auto_fixable=False,
                estimated_fix_days=14,
                responsible_party="Manajemen Koperasi",
                regulatory_citations=[],
                agent_reasoning="No supporting documents found for mandatory checklist item",
            )

        # If evidence exists, evaluate completeness
        if item_evidence:
            # Calculate average completeness from evidence
            avg_completeness = sum(e.get("completeness", 0) for e in item_evidence) / len(item_evidence)
            
            # Check for validation errors in evidence
            has_errors = any(
                any(i.severity.value == "ERROR" for i in e.get("issues", []))
                for e in item_evidence
            )
            
            # NEW: Check specific field requirements for this checklist item
            field_match_score = self._check_field_requirements(item, item_evidence)
            avg_completeness = (avg_completeness + field_match_score) / 2
            
            if avg_completeness >= 0.9 and not has_errors:
                status = "PASS"
                severity = "INFO"
            elif avg_completeness >= 0.7 and not has_errors:
                status = "WARNING"
                severity = "LOW"
            elif avg_completeness >= 0.5:
                status = "WARNING"
                severity = "MEDIUM"
            else:
                status = "FAIL"
                severity = "HIGH" if item.severity_weight >= 1.5 else "MEDIUM"

            # Build evidence summary
            evidence_found = "; ".join(
                f"{e['doc_type']} ({e['completeness']:.0%})" for e in item_evidence
            )
            
            gap = None
            action = None
            if status in ["FAIL", "WARNING"]:
                missing = item.evidence_required[0] if item.evidence_required else "dokumen pendukung"
                gap = f"Kelengkapan dokumen {avg_completeness:.0%}, "
                gap += "ada error validasi" if has_errors else "perlu perbaikan"
                action = f"Perbaiki {missing} hingga kelengkapan >90%"

            return AuditFinding(
                checklist_item_id=item.id,
                checklist_item=item.checklist_item,
                category=item.category,
                requirement_source=", ".join(item.regulatory_refs),
                status=status,
                evidence_found=evidence_found or "Dokumen tersedia tapi tidak lengkap",
                evidence_expected=", ".join(item.evidence_required),
                gap_description=gap,
                recommended_action=action,
                severity=severity,
                auto_fixable=status == "WARNING" and avg_completeness > 0.5,
                estimated_fix_days=7 if status == "WARNING" else 14,
                responsible_party="Manajemen Koperasi",
                regulatory_citations=[],
                agent_reasoning=f"Evaluasi berbasis evidence mapping: {len(item_evidence)} dokumen, avg completeness={avg_completeness:.0%}",
            )

        # Not applicable
        return AuditFinding(
            checklist_item_id=item.id,
            checklist_item=item.checklist_item,
            category=item.category,
            requirement_source=", ".join(item.regulatory_refs),
            status="NOT_APPLICABLE",
            evidence_found="Tidak berlaku untuk koperasi ini",
            evidence_expected="",
            gap_description=None,
            recommended_action=None,
            severity="INFO",
            auto_fixable=False,
            estimated_fix_days=0,
            responsible_party="",
            regulatory_citations=[],
            agent_reasoning="Item tidak applicable (mis. hanya untuk fasilitas campur halal/non-halal)",
        )

    def _check_field_requirements(self, item: AuditChecklistItem, item_evidence: List[Dict[str, Any]]) -> float:
        """Check if extracted fields meet the specific requirements for this checklist item"""
        if not item_evidence:
            return 0.0
        
        # Define required fields per checklist item
        field_requirements = {
            "A01": ["notaris", "nomor_akta", "tanggal_akta", "nama_koperasi", "alamat_koperasi", "pengurus"],
            "A02": ["nama_koperasi"],
            "A03": ["npwp_number", "nama_wp", "alamat_wp"],
            "A04": ["nib_number", "nama_usaha", "alamat_usaha", "kbli_codes"],
            "A05": ["izin_nomor", "izin_tgl_terbit", "izin_tgl_berlaku", "izin_instansi"],
            "A07": ["pengurus"],
            "A10": ["nama_koperasi", "produk_utama"],
            "B01": ["ketua_has", "sertifikat_pelatihan_nomor", "sertifikat_pelatihan_penerbit", "masa_berlaku_pelatihan"],
            "B02": ["anggota_has"],
            "B03": ["anggota_has", "pelatihan_list"],
            "C01": ["bahan_baku"],
            "C02": ["bahan_baku", "sertifikat_halal_nomor", "sertifikat_halal_penerbit", "sertifikat_halal_expired"],
            "C03": ["bahan_baku", "sertifikat_halal_expired"],
            "D01": ["versi", "tanggal_berlaku", "penanggung_jawab", "langkah_produksi", "ccp_points"],
            "D02": ["ccp_points"],
            "D07": ["langkah_produksi"],
            "D08": ["langkah_produksi"],
            "D15": ["langkah_produksi"],
            "E01": ["legend", "area_list"],
            "E02": ["area_list"],
        }
        
        required = field_requirements.get(item.id, [])
        if not required:
            return 1.0  # No specific field requirements
        
        # Check across all evidence documents
        total_fields = 0
        matched_fields = 0
        
        for evidence in item_evidence:
            extracted = evidence.get("fields", {})
            for field in required:
                total_fields += 1
                value = extracted.get(field)
                if value is not None and value != "" and value != [] and value != {}:
                    matched_fields += 1
        
        return matched_fields / total_fields if total_fields > 0 else 1.0

    def _calculate_result(
        self,
        application_id: str,
        koperasi_nama: str,
        findings: List[AuditFinding],
    ) -> AuditSimulationResult:
        """Calculate overall audit result"""
        
        total = len(findings)
        passed = sum(1 for f in findings if f.status == "PASS")
        failed = sum(1 for f in findings if f.status == "FAIL")
        warnings = sum(1 for f in findings if f.status == "WARNING")
        not_applicable = sum(1 for f in findings if f.status == "NOT_APPLICABLE")
        pending = sum(1 for f in findings if f.status == "PENDING")

        applicable = total - not_applicable
        if applicable > 0:
            # Weighted score: PASS=100, WARNING=70, FAIL=0, PENDING=30
            score_sum = (
                passed * 100 +
                warnings * 70 +
                pending * 30 +
                failed * 0
            )
            overall_score = score_sum / applicable
        else:
            overall_score = 0.0

        # Category scores
        category_scores = {}
        for cat in AuditCategory:
            cat_findings = [f for f in findings if f.category == cat]
            if cat_findings:
                cat_applicable = [f for f in cat_findings if f.status != "NOT_APPLICABLE"]
                if cat_applicable:
                    cat_score = sum(
                        100 if f.status == "PASS" else 70 if f.status == "WARNING" else 30 if f.status == "PENDING" else 0
                        for f in cat_applicable
                    ) / len(cat_applicable)
                    category_scores[cat.value] = round(cat_score, 1)

        # Critical gaps (CRITICAL severity FAIL)
        critical_gaps = [
            f.checklist_item for f in findings 
            if f.status == "FAIL" and f.severity == "CRITICAL"
        ]

        # High priority gaps (HIGH severity FAIL or WARNING with weight>=1.5)
        high_priority_gaps = [
            f.checklist_item for f in findings
            if (f.status == "FAIL" and f.severity == "HIGH") or
               (f.status == "WARNING" and f.severity in ["MEDIUM", "HIGH"])
        ]

        # Determine recommendation
        if failed == 0 and warnings <= 3:
            recommendation = "READY"
        elif failed == 0 and warnings > 3:
            recommendation = "NEEDS_MINOR_FIXES"
        elif failed <= 2 and critical_gaps == []:
            recommendation = "NEEDS_MINOR_FIXES"
        elif failed <= 5:
            recommendation = "NEEDS_MAJOR_WORK"
        else:
            recommendation = "NOT_READY"

        # Estimated time to fix
        fix_days = sum(
            f.estimated_fix_days for f in findings 
            if f.status in ["FAIL", "WARNING"]
        )
        fix_days = min(fix_days, 90)  # Cap at 90 days

        # Priority actions
        priority_actions = []
        priority = 1
        for f in sorted(findings, key=lambda x: (
            0 if x.severity == "CRITICAL" else 
            1 if x.severity == "HIGH" else 
            2 if x.severity == "MEDIUM" else 3
        )):
            if f.status in ["FAIL", "WARNING"] and f.recommended_action:
                priority_actions.append(PriorityAction(
                    priority=priority,
                    action=f.recommended_action,
                    checklist_item_id=f.checklist_item_id,
                    responsible=f.responsible_party,
                    deadline_days=f.estimated_fix_days,
                    estimated_cost="Rp 0 - Rp 50 Juta" if f.estimated_fix_days <= 14 else "Rp 50 Juta - Rp 200 Juta",
                ))
                priority += 1
                if priority > 10:
                    break

        return AuditSimulationResult(
            application_id=application_id,
            koperasi_nama=koperasi_nama,
            overall_readiness_score=round(overall_score, 1),
            total_checks=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            not_applicable=not_applicable,
            pending=pending,
            findings=findings,
            critical_gaps=critical_gaps,
            high_priority_gaps=high_priority_gaps,
            category_scores=category_scores,
            submission_recommendation=recommendation,
            estimated_time_to_fix_days=fix_days,
            priority_actions=priority_actions,
            agent_version="1.0",
            rag_context_used=[],
        )

    def export_report(self, result: AuditSimulationResult, output_path: Path):
        """Export audit report as JSON"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.model_dump(mode='json'), f, indent=2, ensure_ascii=False)
        logger.info(f"Audit report exported to {output_path}")


# CLI for testing
if __name__ == "__main__":
    import sys
    from halal_koperasi_agent.schemas.documents import DocumentType, DocumentStatus, ValidationIssue, ValidationSeverity
    
    async def test():
        agent = AuditSimulationAgent()
        await agent.initialize()
        
        # Create mock documents for testing
        mock_docs = {
            DocumentType.NPWP: DocumentMetadata(
                doc_type=DocumentType.NPWP,
                filename="NPWP.pdf",
                file_path="data/synthetic_docs/kmbj/NPWP.pdf",
                file_size_kb=4,
                mime_type="application/pdf",
                pages=1,
                completeness_score=1.0,
                status=DocumentStatus.VALIDATED,
                extracted_fields={"npwp_number": "01.234.567.8-901.000", "nama_wp": "KOPERASI MINA BAHARI JAYA"},
            ),
            DocumentType.AKTA_PENDIRIAN: DocumentMetadata(
                doc_type=DocumentType.AKTA_PENDIRIAN,
                filename="AKTA_PENDIRIAN.pdf",
                file_path="data/synthetic_docs/kmbj/AKTA_PENDIRIAN.pdf",
                file_size_kb=7,
                mime_type="application/pdf",
                pages=2,
                completeness_score=0.75,
                status=DocumentStatus.VALIDATED,
                extracted_fields={"notaris": "Notaris Test", "nama_koperasi": "KOPERASI MINA BAHARI JAYA"},
            ),
            DocumentType.NIB: DocumentMetadata(
                doc_type=DocumentType.NIB,
                filename="NIB.pdf",
                file_path="data/synthetic_docs/kmbj/NIB.pdf",
                file_size_kb=7,
                mime_type="application/pdf",
                pages=1,
                completeness_score=1.0,
                status=DocumentStatus.VALIDATED,
                extracted_fields={"nib_number": "1234567890123", "nama_usaha": "KOPERASI MINA BAHARI JAYA"},
            ),
        }
        
        result = await agent.run_audit(
            application_id="KMBJ-001-2025-001",
            koperasi_nama="Koperasi Mina Bahari Jaya",
            documents=mock_docs,
        )
        
        print(f"\n=== AUDIT RESULT ===")
        print(f"Score: {result.overall_readiness_score:.1f}%")
        print(f"Recommendation: {result.submission_recommendation}")
        print(f"Total: {result.total_checks}, Pass: {result.passed}, Fail: {result.failed}, Warn: {result.warnings}, NA: {result.not_applicable}")
        print(f"Critical gaps: {len(result.critical_gaps)}")
        print(f"Category scores:")
        for cat, score in result.category_scores.items():
            print(f"  {cat}: {score:.1f}%")
        print(f"Priority actions: {len(result.priority_actions)}")
        for pa in result.priority_actions[:5]:
            print(f"  [{pa.priority}] {pa.action} ({pa.deadline_days} days)")
        
        # Export
        agent.export_report(result, Path("output/audit_report.json"))
    
    asyncio.run(test())