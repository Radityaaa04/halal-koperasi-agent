#!/usr/bin/env python3
"""
Document Intake Agent for HALAL Koperasi Multi-Agent System
Parses, validates, and scores uploaded documents for halal certification readiness.
"""

import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple

import fitz  # PyMuPDF
from loguru import logger

from halal_koperasi_agent.config import settings
from halal_koperasi_agent.schemas.documents import (
    DocumentType,
    DocumentStatus,
    ValidationSeverity,
    ValidationIssue,
    DocumentMetadata,
    AktaPendirianFields,
    NPWPFields,
    NIBFields,
    SOPProduksiFields,
    LangkahProduksi,
    CCPPoint,
    DaftarBahanBakuFields,
    BahanBakuItem,
    RuteProduksiFields,
    AreaSegregasi,
    SertifikatHalalBahanFields,
    SertifikatHalalItem,
    LayoutFasilitasFields,
    AreaLayout,
    OrganogramHASFields,
    PersonelHAS,
    BuktiPelatihanHASFields,
    PelatihanItem,
)
from halal_koperasi_agent.llm_providers import (
    get_langchain_model,
    chat_completion,
    ChatMessage,
    LLMProviderFactory,
)
from halal_koperasi_agent.utils import create_jinja_env


class DocumentIntakeAgent:
    """
    Agent responsible for:
    1. Parsing PDF/image documents (PyMuPDF + PaddleOCR)
    2. Extracting structured fields based on document type
    3. Validating completeness against regulatory requirements
    4. Scoring document completeness (0.0 - 1.0)
    5. Flagging issues with regulatory references
    """

    # Regex patterns for Indonesian document validation
    PATTERNS = {
        "npwp": re.compile(r"^\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}$"),
        "nib": re.compile(r"^\d{13}$"),
        "nik": re.compile(r"^\d{16}$"),
        "nomor_akta": re.compile(r"^No\.\s*\d+/\d{4}$", re.IGNORECASE),
        "nomor_sertifikat_halal": re.compile(r"^[A-Z]{2,4}-\d{4,}-\d{4}$", re.IGNORECASE),
        "email": re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$"),
        "phone": re.compile(r"^(\+62|62|0)8\d{8,11}$"),
    }

    # Required fields per document type (subset of schema)
    REQUIRED_FIELDS = {
        DocumentType.AKTA_PENDIRIAN: [
            "notaris", "nomor_akta", "tanggal_akta", "nama_koperasi", 
            "alamat_koperasi", "pengurus"
        ],
        DocumentType.NPWP: ["npwp_number", "nama_wp", "alamat_wp"],
        DocumentType.NIB: ["nib_number", "nama_usaha", "alamat_usaha", "kbli_codes"],
        DocumentType.IZIN_USAHA: ["izin_nomor", "izin_tgl_terbit", "izin_tgl_berlaku", "izin_instansi"],
        DocumentType.SOP_PRODUKSI: ["versi", "tanggal_berlaku", "penanggung_jawab", "langkah_produksi", "ccp_points"],
        DocumentType.DAFTAR_BAHAN_BAKU: ["bahan_baku"],
        DocumentType.RUTE_PRODUKSI: ["flowchart_description", "area_segregasi", "cleaning_procedures"],
        DocumentType.SERTIFIKAT_HALAL_BAHAN: ["sertifikat_list"],
        DocumentType.LAYOUT_FASILITAS: ["legend", "area_list"],
        DocumentType.ORGANOGRAM_HAS: ["ketua_has", "anggota_has"],
        DocumentType.BUKTI_PELATIHAN_HAS: ["pelatihan_list"],
    }

    def __init__(self):
        self.ocr = None  # Lazy init PaddleOCR
        self.jinja_env = create_jinja_env(Path(settings.TEMPLATES_DIR))
        # LLM for extraction (lazy init)
        self._llm = None

    def _get_ocr(self):
        """Lazy initialize PaddleOCR"""
        if self.ocr is None:
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",  # Works for Indonesian Latin script
                    show_log=False,
                    use_gpu=False,
                )
                logger.info("PaddleOCR initialized")
            except Exception as e:
                logger.warning(f"PaddleOCR init failed: {e}. OCR will be unavailable.")
                self.ocr = False
        return self.ocr

    def _get_llm(self):
        """Lazy init LLM for extraction"""
        if self._llm is None:
            try:
                self._llm = get_langchain_model(
                    provider=settings.LLM_PROVIDER,
                    model=settings.LLM_MODEL,
                )
                logger.info(f"LLM initialized: {settings.LLM_PROVIDER}")
            except Exception as e:
                logger.warning(f"LLM init failed: {e}. Extraction will use regex only.")
                self._llm = False
        return self._llm

    # ============================================================
    # MAIN PIPELINE
    # ============================================================

    async def process_document(
        self,
        file_path: Path,
        doc_type: DocumentType,
        uploaded_by: str = "system",
    ) -> DocumentMetadata:
        """
        Full pipeline: parse -> extract -> validate -> score
        """
        logger.info(f"Processing {doc_type.value}: {file_path.name}")

        # 1. Parse document
        if file_path.suffix.lower() == ".pdf":
            parsed = self.parse_pdf(file_path)
        else:
            parsed = await self.parse_image(file_path)

        # 2. Extract structured fields
        extracted = await self.extract_fields(doc_type, parsed["full_text"], parsed["structured_text"])

        # 3. Validate
        completeness_score, issues = self.validate_document(doc_type, extracted)

        # 4. Build metadata
        metadata = DocumentMetadata(
            doc_type=doc_type,
            filename=file_path.name,
            original_filename=file_path.name,
            file_path=str(file_path),
            file_size_kb=parsed["file_size_kb"],
            mime_type=parsed["mime_type"],
            pages=parsed["page_count"],
            upload_timestamp=datetime.now(),
            uploaded_by=uploaded_by,
            ocr_text=parsed["full_text"] if len(parsed["full_text"]) < 50000 else parsed["full_text"][:50000] + "... [truncated]",
            ocr_confidence=parsed.get("ocr_confidence"),
            extracted_fields=extracted,
            extraction_method=parsed["extraction_method"],
            status=DocumentStatus.VALIDATED if completeness_score > 0.5 else DocumentStatus.INVALID,
            completeness_score=completeness_score,
            validation_issues=issues,
            validated_at=datetime.now(),
            validated_by="document_intake_agent_v1",
            regulatory_refs=self._get_regulatory_refs(doc_type, extracted, issues),
        )

        logger.success(
            f"  Completeness: {completeness_score:.1%}, "
            f"Issues: {len(issues)}, Status: {metadata.status.value}"
        )
        return metadata

    # ============================================================
    # PARSING
    # ============================================================

    def parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Extract text from PDF using PyMuPDF"""
        doc = fitz.open(str(file_path))
        pages = []
        full_text_parts = []
        structured_parts = []

        for page_num, page in enumerate(doc, 1):
            # Plain text
            text = page.get_text("text")
            full_text_parts.append(text)

            # Structured text (blocks with position)
            blocks = page.get_text("dict")["blocks"]
            structured = ""
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            structured += span["text"] + " "
                        structured += "\n"
                    structured += "\n"
            structured_parts.append(structured)

            pages.append({
                "page_number": page_num,
                "text": text,
                "structured_text": structured,
                "char_count": len(text),
            })

        doc.close()

        return {
            "pages": pages,
            "full_text": "\n\n".join(full_text_parts),
            "structured_text": "\n\n".join(structured_parts),
            "page_count": len(pages),
            "file_size_kb": file_path.stat().st_size // 1024,
            "mime_type": "application/pdf",
            "extraction_method": "pymupdf",
        }

    async def parse_image(self, file_path: Path) -> Dict[str, Any]:
        """OCR image using PaddleOCR"""
        ocr = self._get_ocr()
        if not ocr:
            raise RuntimeError("OCR not available")

        # Run OCR in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: ocr.ocr(str(file_path), cls=True)
        )

        pages = []
        full_text_parts = []
        total_conf = 0.0
        conf_count = 0

        for page_idx, page_result in enumerate(result, 1):
            if not page_result:
                pages.append({
                    "page_number": page_idx,
                    "text": "",
                    "confidence": 0.0,
                })
                continue

            page_text = ""
            for line in page_result:
                bbox, (text, conf) = line
                page_text += text + "\n"
                total_conf += conf
                conf_count += 1

            pages.append({
                "page_number": page_idx,
                "text": page_text.strip(),
                "confidence": total_conf / conf_count if conf_count > 0 else 0.0,
            })
            full_text_parts.append(page_text)

        avg_conf = total_conf / conf_count if conf_count > 0 else 0.0

        return {
            "pages": pages,
            "full_text": "\n".join(full_text_parts),
            "structured_text": "\n".join(full_text_parts),  # Same for images
            "page_count": len(pages),
            "file_size_kb": file_path.stat().st_size // 1024,
            "mime_type": "image/*",
            "extraction_method": "paddleocr",
            "ocr_confidence": avg_conf,
        }

    # ============================================================
    # EXTRACTION (LLM + Regex)
    # ============================================================

    async def extract_fields(
        self,
        doc_type: DocumentType,
        full_text: str,
        structured_text: str,
    ) -> Dict[str, Any]:
        """Extract structured fields using LLM + regex fallback"""
        # Try LLM first
        llm = self._get_llm()
        if llm:
            try:
                return await self._extract_with_llm(doc_type, full_text)
            except Exception as e:
                logger.warning(f"LLM extraction failed for {doc_type}: {e}. Falling back to regex.")

        # Fallback: Regex extraction
        return self._extract_with_regex(doc_type, full_text, structured_text)

    async def _extract_with_llm(self, doc_type: DocumentType, text: str) -> Dict[str, Any]:
        """Use LLM to extract structured fields"""
        prompt = self._build_extraction_prompt(doc_type, text)
        
        messages = [
            ChatMessage(role="system", content=prompt["system"]),
            ChatMessage(role="user", content=prompt["user"]),
        ]
        
        response = await chat_completion(
            messages=messages,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            temperature=0.0,  # Deterministic extraction
        )
        
        # Parse JSON from response
        import json
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            
            # Ensure it's a dict, not a list
            if not isinstance(result, dict):
                logger.warning(f"LLM returned non-dict for {doc_type}: {type(result)}")
                raise ValueError("LLM returned non-object JSON")
            
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM extraction JSON: {e}")
            raise

    def _build_extraction_prompt(self, doc_type: DocumentType, text: str) -> Dict[str, str]:
        """Build extraction prompt for specific document type"""
        
        field_definitions = self._get_field_definitions(doc_type)
        
        system = f"""Anda adalah ekstraktor data dokumen sertifikasi halal Indonesia.
        Ekstrak field-field berikut dari teks dokumen {doc_type.value.upper()}:

        {field_definitions}

        ATURAN KETAT:
        1. Hanya kembalikan JSON OBJECT valid (bukan array), tanpa penjelasan tambahan
        2. Jika field tidak ditemukan, gunakan null
        3. Tanggal format: YYYY-MM-DD
        4. Nomor NIK: 16 digit, NPWP: XX.XXX.XXX.X-XXX.XXX, NIB: 13 digit
        5. Boolean gunakan true/false
        6. Array kosong [] jika tidak ada data
        7. JANGAN kembalikan array/list - hanya object JSON
        8. Tidak boleh ada komentar atau teks di luar JSON

        CONTOH FORMAT:
        {{
          "notaris": "Nama Notaris",
          "nomor_akta": "No. 123/2024",
          "tanggal_akta": "2024-01-15",
          "nama_koperasi": "Koperasi Contoh",
          "alamat_koperasi": "Jl. Contoh No. 123",
          "pengurus": [
            {{"jabatan": "Ketua", "nama": "Budi", "nik": "1234567890123456", "alamat": "Jl. A", "pekerjaan": "Wiraswasta"}}
          ]
        }}"""
        
        user = f"TEKS DOKUMEN:\n{text[:15000]}"
        
        return {"system": system, "user": user}

    def _get_field_definitions(self, doc_type: DocumentType) -> str:
        """Get field definitions for LLM prompt"""
        definitions = {
            DocumentType.AKTA_PENDIRIAN: """
- notaris (string)
- nomor_akta (string, format: No. XX/YYYY)
- tanggal_akta (date: YYYY-MM-DD)
- nama_koperasi (string)
- alamat_koperasi (string)
- pengurus (array of: {jabatan, nama, nik, alamat, pekerjaan})""",
            DocumentType.NPWP: """
- npwp_number (string, format: XX.XXX.XXX.X-XXX.XXX)
- nama_wp (string)
- alamat_wp (string)
- kpp (string, optional)
- status_wp (aktif/non_aktif/tidak_ditemukan)""",
            DocumentType.NIB: """
- nib_number (string, 13 digit)
- nama_usaha (string)
- alamat_usaha (string)
- kbli_codes (array of strings)
- status_nib (aktif/tidak_aktif/dibatalkan)
- tanggal_terbit (date)""",
            DocumentType.IZIN_USAHA: """
- izin_nomor (string)
- izin_tgl_terbit (date)
- izin_tgl_berlaku (date)
- izin_instansi (string)""",
            DocumentType.SOP_PRODUKSI: """
- versi (string)
- tanggal_berlaku (date)
- penanggung_jawab (string)
- jabatan_penanggung_jawab (string)
- langkah_produksi (array of: {urutan, nama_tahap, deskripsi, peralatan[], bahan_masuk[], bahan_keluar[], parameter_kontrol[], risiko_kontaminasi, kontrol_pencegahan, is_ccp, ccp_number})
- ccp_points (array of: {ccp_id, nama, parameter_kritis, batas_kritis, pemantauan, tindakan_koreksi, verifikasi, pencatatan})""",
            DocumentType.DAFTAR_BAHAN_BAKU: """
- bahan_baku (array of: {nama, kode_internal, supplier, alamat_supplier, kategori, sertifikat_halal_nomor, sertifikat_halal_penerbit, sertifikat_halal_tanggal_terbit, sertifikat_halal_expired, jumlah_penggunaan_bulan_kg, unit, catatan})""",
            DocumentType.RUTE_PRODUKSI: """
- flowchart_description (string)
- area_segregasi (array of: {nama_area, tipe, lokasi, peralatan_dedicated, peralatan_list[], prosedur_pembersihan})
- titik_kritis_lintas (array of strings)
- cleaning_procedures (array of strings)""",
            DocumentType.SERTIFIKAT_HALAL_BAHAN: """
- sertifikat_list (array of: {nomor_sertifikat, nama_produk_bahan, penerbit_lph, tanggal_terbit, tanggal_expired, scope, status})""",
            DocumentType.LAYOUT_FASILITAS: """
- gambar_base64 (string, optional)
- gambar_path (string, optional)
- legend (object: {kode: nama})
- skala (string)
- area_list (array of: {kode, nama, fungsi, luas_m2, tipe_area, peralatan[]})""",
            DocumentType.ORGANOGRAM_HAS: """
- ketua_has (object: {nama, nik, jabatan, jabatan_has, pelatihan_has_terakhir, sertifikat_pelatihan_nomor, sertifikat_pelatihan_penerbit, masa_berlaku_pelatihan, tugas_tanggung_jawab[]})
- anggota_has (array of same object structure)
- struktur_organisasi (string, optional)""",
            DocumentType.BUKTI_PELATIHAN_HAS: """
- pelatihan_list (array of: {nama_pelatihan, penyelenggara, tanggal, peserta[], sertifikat_nomor, masa_berlaku, topik[]})""",
        }
        return definitions.get(doc_type, "Tidak ada definisi field untuk tipe dokumen ini.")

    def _extract_with_regex(
        self,
        doc_type: DocumentType,
        full_text: str,
        structured_text: str,
    ) -> Dict[str, Any]:
        """Regex-based extraction fallback"""
        # Use the first 10000 chars for speed
        text = full_text[:10000]
        
        extractors = {
            DocumentType.AKTA_PENDIRIAN: self._extract_akta,
            DocumentType.NPWP: self._extract_npwp,
            DocumentType.NIB: self._extract_nib,
            DocumentType.IZIN_USAHA: self._extract_izin_usaha,
            DocumentType.SOP_PRODUKSI: self._extract_sop,
            DocumentType.DAFTAR_BAHAN_BAKU: self._extract_bahan_baku,
            DocumentType.RUTE_PRODUKSI: self._extract_rute,
            DocumentType.SERTIFIKAT_HALAL_BAHAN: self._extract_sertifikat_halal,
            DocumentType.LAYOUT_FASILITAS: self._extract_layout,
            DocumentType.ORGANOGRAM_HAS: self._extract_organogram,
            DocumentType.BUKTI_PELATIHAN_HAS: self._extract_pelatihan,
        }
        
        extractor = extractors.get(doc_type)
        if extractor:
            return extractor(text)
        return {}

    # ============================================================
    # REGEX EXTRACTORS (Simplified - Production would be more robust)
    # ============================================================

    def _extract_akta(self, text: str) -> Dict[str, Any]:
        data = {}
        m = re.search(r"Notaris\s*[:\\-]?\s*([^\n]+)", text, re.IGNORECASE)
        if m: data["notaris"] = m.group(1).strip()
        m = re.search(r"No\.\s*(\d+/\d{4})", text, re.IGNORECASE)
        if m: data["nomor_akta"] = m.group(1)
        m = re.search(r"Tanggal\s*[:\\-]?\s*(\d{1,2}\s+\w+\s+\d{4})", text, re.IGNORECASE)
        if m:
            try:
                data["tanggal_akta"] = datetime.strptime(m.group(1), "%d %B %Y").date().isoformat()
            except: data["tanggal_akta"] = m.group(1)
        m = re.search(r"Nama\s+Koperasi\s*[:\\-]?\s*([^\n]+)", text, re.IGNORECASE)
        if m: data["nama_koperasi"] = m.group(1).strip()
        m = re.search(r"Alamat\s*[:\\-]?\s*([^\n]+(?:\n[^\n]+){0,2})", text, re.IGNORECASE)
        if m: data["alamat_koperasi"] = m.group(1).strip()
        return data

    def _extract_npwp(self, text: str) -> Dict[str, Any]:
        data = {}
        m = re.search(self.PATTERNS["npwp"], text)
        if m: data["npwp_number"] = m.group(0)
        m = re.search(r"Nama\s*(?:WP|Wajib\s*Pajak)\s*[:\\-]?\s*([^\n]+)", text, re.IGNORECASE)
        if m: data["nama_wp"] = m.group(1).strip()
        m = re.search(r"Alamat\s*(?:WP|Wajib\s*Pajak)\s*[:\\-]?\s*([^\n]+)", text, re.IGNORECASE)
        if m: data["alamat_wp"] = m.group(1).strip()
        return data

    def _extract_nib(self, text: str) -> Dict[str, Any]:
        data = {}
        m = re.search(self.PATTERNS["nib"], text)
        if m: data["nib_number"] = m.group(0)
        m = re.search(r"Nama\s*Usaha\s*[:\\-]?\s*([^\n]+)", text, re.IGNORECASE)
        if m: data["nama_usaha"] = m.group(1).strip()
        return data

    def _extract_izin_usaha(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_sop(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_bahan_baku(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_rute(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_sertifikat_halal(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_layout(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_organogram(self, text: str) -> Dict[str, Any]:
        return {}

    def _extract_pelatihan(self, text: str) -> Dict[str, Any]:
        return {}

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate_document(
        self,
        doc_type: DocumentType,
        extracted: Dict[str, Any],
    ) -> Tuple[float, List[ValidationIssue]]:
        """Validate extracted fields against requirements"""
        issues = []
        required = self.REQUIRED_FIELDS.get(doc_type, [])

        # Check required fields
        for field in required:
            value = extracted.get(field)
            if value is None or value == "" or (isinstance(value, list) and len(value) == 0):
                issues.append(ValidationIssue(
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field}' is missing or empty",
                    regulatory_ref=self._get_field_regulatory_ref(doc_type, field),
                    suggested_fix=f"Provide {field} in the document",
                ))

        # Type-specific validation
        issues.extend(self._validate_specific(doc_type, extracted))

        # Calculate completeness score
        total_fields = len(required) + len(self._get_optional_fields(doc_type))
        present_fields = sum(
            1 for f in required if extracted.get(f) not in (None, "", [])
        )
        present_fields += sum(
            1 for f in self._get_optional_fields(doc_type) 
            if extracted.get(f) not in (None, "", [])
        )
        
        completeness = (present_fields / total_fields * 0.7) + (present_fields / max(1, len(required)) * 0.3)
        completeness = max(0.0, min(1.0, completeness))

        return completeness, issues

    def _validate_specific(self, doc_type: DocumentType, extracted: Dict[str, Any]) -> List[ValidationIssue]:
        """Type-specific validation rules"""
        issues = []

        if doc_type == DocumentType.NPWP:
            npwp = extracted.get("npwp_number", "")
            if npwp and not self.PATTERNS["npwp"].match(npwp):
                issues.append(ValidationIssue(
                    field="npwp_number",
                    severity=ValidationSeverity.WARNING,
                    message=f"NPWP format may be invalid: {npwp}",
                    regulatory_ref="UU No. 28/2007 Pasal 2",
                    suggested_fix="Format: XX.XXX.XXX.X-XXX.XXX",
                ))

        elif doc_type == DocumentType.NIB:
            nib = extracted.get("nib_number", "")
            if nib and not self.PATTERNS["nib"].match(nib):
                issues.append(ValidationIssue(
                    field="nib_number",
                    severity=ValidationSeverity.WARNING,
                    message=f"NIB should be 13 digits: {nib}",
                    suggested_fix="13 digit numeric",
                ))

        elif doc_type == DocumentType.AKTA_PENDIRIAN:
            pengurus = extracted.get("pengurus", [])
            if len(pengurus) < 3:
                issues.append(ValidationIssue(
                    field="pengurus",
                    severity=ValidationSeverity.WARNING,
                    message=f"Only {len(pengurus)} pengurus found, minimum 3 required (Ketua, Sekretaris, Bendahara)",
                    regulatory_ref="UU No. 25/2008 Pasal 43",
                ))

        elif doc_type == DocumentType.SOP_PRODUKSI:
            ccp_points = extracted.get("ccp_points", [])
            if len(ccp_points) < 2:
                issues.append(ValidationIssue(
                    field="ccp_points",
                    severity=ValidationSeverity.WARNING,
                    message=f"Only {len(ccp_points)} CCP points found, HACCP typically requires 2-4 CCPs",
                    regulatory_ref="SNI 99001:2023, HACCP Principle 2",
                ))

        elif doc_type == DocumentType.ORGANOGRAM_HAS:
            ketua = extracted.get("ketua_has", {})
            if not ketua.get("sertifikat_pelatihan_nomor"):
                issues.append(ValidationIssue(
                    field="ketua_has.sertifikat_pelatihan_nomor",
                    severity=ValidationSeverity.ERROR,
                    message="Ketua HAS must have valid HAS training certificate",
                    regulatory_ref="BPJPH Peraturan 1/2023 Pasal 11",
                    suggested_fix="Attach HAS training certificate for Ketua HAS",
                ))

        elif doc_type == DocumentType.SERTIFIKAT_HALAL_BAHAN:
            sertifikat_list = extracted.get("sertifikat_list", [])
            expired_count = 0
            for sert in sertifikat_list:
                exp = sert.get("tanggal_expired")
                if exp:
                    try:
                        exp_date = datetime.fromisoformat(exp).date()
                        if exp_date < datetime.now().date():
                            expired_count += 1
                    except: pass
            if expired_count > 0:
                issues.append(ValidationIssue(
                    field="sertifikat_list",
                    severity=ValidationSeverity.ERROR,
                    message=f"{expired_count} sertifikat halal bahan baku sudah expired",
                    regulatory_ref="PP 39/2021 Pasal 16",
                    suggested_fix="Perbarui sertifikat halal bahan baku yang expired",
                ))

        return issues

    def _get_optional_fields(self, doc_type: DocumentType) -> List[str]:
        """Optional fields per document type"""
        optional_map = {
            DocumentType.AKTA_PENDIRIAN: ["anggaran_dasar_ref"],
            DocumentType.NPWP: ["kpp", "status_wp"],
            DocumentType.NIB: ["status_nib", "tanggal_terbit"],
            DocumentType.SOP_PRODUKSI: ["catatan"],
            DocumentType.LAYOUT_FASILITAS: ["gambar_base64", "gambar_path", "skala"],
            DocumentType.ORGANOGRAM_HAS: ["struktur_organisasi"],
        }
        return optional_map.get(doc_type, [])

    def _get_field_regulatory_ref(self, doc_type: DocumentType, field: str) -> str:
        """Get regulatory reference for a field"""
        refs = {
            DocumentType.AKTA_PENDIRIAN: "UU No. 25/2008",
            DocumentType.NPWP: "UU No. 28/2007",
            DocumentType.NIB: "UU No. 11/2020",
            DocumentType.SOP_PRODUKSI: "PP 39/2021 Pasal 15, BPJPH Peraturan 1/2023 Pasal 8",
            DocumentType.DAFTAR_BAHAN_BAKU: "PP 39/2021 Pasal 16",
            DocumentType.RUTE_PRODUKSI: "PP 39/2021 Pasal 15-16",
            DocumentType.SERTIFIKAT_HALAL_BAHAN: "PP 39/2021 Pasal 16, BPJPH Peraturan 2/2023",
            DocumentType.LAYOUT_FASILITAS: "PP 39/2021 Pasal 15, SNI 99001:2023",
            DocumentType.ORGANOGRAM_HAS: "BPJPH Peraturan 1/2023 Pasal 10-11, SNI 99001:2023 4.2",
            DocumentType.BUKTI_PELATIHAN_HAS: "BPJPH Peraturan 1/2023 Pasal 11, SNI 99001:2023 7.2",
        }
        return refs.get(doc_type, "")

    def _get_regulatory_refs(
        self,
        doc_type: DocumentType,
        extracted: Dict[str, Any],
        issues: List[ValidationIssue],
    ) -> List[str]:
        """Collect regulatory references from validation"""
        refs = set()
        for issue in issues:
            if issue.regulatory_ref:
                refs.add(issue.regulatory_ref)
        # Add base refs for doc type
        base = self._get_field_regulatory_ref(doc_type, "")
        if base:
            refs.add(base)
        return list(refs)


# CLI for testing
if __name__ == "__main__":
    import sys
    agent = DocumentIntakeAgent()
    
    if len(sys.argv) < 3:
        print("Usage: python document_intake.py <file_path> <doc_type>")
        print(f"Doc types: {[d.value for d in DocumentType]}")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    doc_type = DocumentType(sys.argv[2])
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    # Run async
    metadata = asyncio.run(agent.process_document(file_path, doc_type))
    
    print(f"\nResult:")
    print(f"  Status: {metadata.status.value}")
    print(f"  Completeness: {metadata.completeness_score:.1%}")
    print(f"  Issues: {len(metadata.validation_issues)}")
    for issue in metadata.validation_issues:
        print(f"    [{issue.severity.value}] {issue.field}: {issue.message}")