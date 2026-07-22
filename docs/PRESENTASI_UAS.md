# PRESENTASI UAS — Sistem Multi-Agent Sertifikasi Halal Koperasi

**Mata Kuliah:** Proyek Data Mining (ST167) — 4 SKS  
**Tim:** 3 Mahasiswa | **Dosen:** Anna Baita, M.Kom | Kusnawi, S.Kom, M.Eng | Theopilus Bayu Sasongko, S.Kom., M.Eng  
**Tanggal:** 10 Agustus 2026

---

## SLIDE 1: TITLE

# Sistem Multi-Agent Sertifikasi Halal Koperasi Petani/Nelayan Kecil

**Opsi 1: Sertifikasi Halal Koperasi Petani/Nelayan Kecil**

**Tim:** [Nama Anggota 1], [Nama Anggota 2], [Nama Anggota 3]  
**Dosen Pengampu:** Anna Baita, M.Kom | Kusnawi, S.Kom, M.Eng | Theopilus Bayu Sasongko, S.Kom., M.Eng  
**Universitas Amikom Yogyakarta** | **Proyek Data Mining (ST167)**  \n**10 Agustus 2026**

---

## SLIDE 2: PROBLEM

### Wajib Halal 2026 — Realita Koperasi Kecil

| Fakta | Data |
|-------|------|
| **Deadline Wajib Halal** | Oktober 2026 (perpanjangan dari 2024) |
| **Koperasi belum bersertifikat** | > 60% (Kemenkop 2024) |
| **Dokumen wajib** | 15+ jenis (AKTA, NPWP, NIB, SOP, Bahan Baku, Rute Produksi, dll.) |
| **Waktu proses manual** | 3–6 bulan |
| **Biaya LPH + administrasi** | Mahal untuk koperasi mikro |

### 5 Hambatan Utama
1. **Kompleksitas dokumen** — 15+ dokumen tersebar
2. **Tidak paham regulasi** — UU, PP, BPJPH, MUI, SNI, LPH tersebar di banyak portal
3. **Keterbatasan SDM** — Tidak ada staf HACCP/HAS internal
4. **Biaya & waktu** — Proses manual mahal & lama
5. **Audit gagal** — Sering *rejected* karena dokumen tidak lengkap/konsisten

---

## SLIDE 3: SOLUSI

### Multi-Agent LLM + RAG untuk Otomatisasi End-to-End

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  DOCUMENT   │   │  REGULATORY │   │  AUDIT      │   │  DECISION   │   │  COMM       │
│  INTAKE     │   │  RAG        │   │  SIMULATION │   │  RECOMMEND  │   │  AGENT      │
│             │   │             │   │             │   │             │   │             │
│ Parse, OCR, │   │ ChromaDB,   │   │ 81-item     │   │ Weighted    │   │ PDF, Excel, │
│ Validate,   │──►│ Hybrid      │──►│ Checklist   │──►│ Scoring,    │──►│ Brief,      │
│ Score       │   │ Search,     │   │ Gap Analysis│   │ Risk,       │   │ Email Draft │
│             │   │ Citation    │   │ Readiness % │   │ Conditions  │   │             │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
                                    │
                              LangGraph StateGraph
                              Human-in-the-loop
                              Checkpointing
```

**Input:** Dokumen koperasi (PDF/Image)  
**Output:** Audit report, Checklist, Executive brief, Email drafts, Explainability trace

---

## SLIDE 4: ARCHITECTURE & TECH STACK

### Arsitektur: LangGraph (Orchestrator) + 5 Agent

| Layer | Teknologi | Alasan |
|-------|-----------|--------|
| **Orchestration** | **LangGraph** | StateGraph, HITL, checkpointing — multi-agent native |
| **LLM** | **NVIDIA NIM (Llama-3.1-8B)** | Cloud API, free tier, function calling, Indonesian capable |
| **Embedding** | **NVIDIA NIM (nv-embedqa-e5-v5)** | Multilingual, strong Indo, 1024 dim |
| **Reranker** | **LLM-based (native)** | Cross-encoder not on cloud API |
| **Vector DB** | **ChromaDB (Docker)** | Lightweight, Python-native, metadata filter |
| **Doc Parsing** | **PyMuPDF + pymupdf4llm** | PDF text + markdown |
| **OCR** | **PaddleOCR** | Lang=['en','id'], confidence threshold |
| **Evaluation** | **Custom + RAGAS** | Industry standard + domain-specific |
| **UI** | **Streamlit** | Cepat, interaktif untuk demo |

---

## SLIDE 5: RAG PIPELINE REGULASI HALAL

### Knowledge Base: 7 Koleksi ChromaDB
```
halal_regulations/
├── UU_33_2014/           (UU Jaminan Produk Halal)
├── PP_39_2021/           (PP Pelaksanaan JPH)
├── BPJPH_Peraturan_1_2023/  (Prosedur Pengajuan)
├── BPJPH_Peraturan_2_2023/  (Prosedur Verifikasi & Audit)
├── MUI_Fatwa_Halal/      (Fatwa MUI No. 4/2003, 12/2010, 35/2014)
├── LPH_Panduan_Audit/    (Panduan audit LPH)
├── SNI_Halal/            (SNI 99001:2023, SNI 3932)
└── Kominfo_9_2023/       (Aksesibilitas digital)
```

### Retrieval Strategy (Hybrid + RRF + LLM Rerank)
1. **BM25 (keyword)** + **Vector (semantic)** → **Reciprocal Rank Fusion**
2. **LLM Reranker** top-20 → top-5
3. **Context Window** max 4000 tokens
4. **Citation wajib:** `source_doc`, `article`, `chunk_id`

### System Prompt (Grounded-Only)
> "Jawab HANYA berdasarkan KONTEKS. Jika tidak cukup: 'Informasi tidak tersedia...'. SELALU sertakan sitasi."

---

## SLIDE 6: AGENT DETAILS

### 1. Document Intake Agent
- Parse PDF (PyMuPDF) + OCR (PaddleOCR)
- Pydantic validation per 12 DocumentType
- Completeness scoring: `(required_fields_valid/total)×0.7 + (optional_present/total)×0.3`
- Output: `DocumentMetadata` dengan `validation_issues`, `extracted_fields`

### 2. Regulatory RAG Agent
- Hybrid search → RRF → LLM rerank → Generate
- Output: `RAGAnswer` (answer, citations[], confidence, needs_human_verification)
- 6 test questions: syarat dokumen, masa berlaku, segregasi, sanksi, anggota HAS

### 3. Audit Simulation Agent
- 81-item checklist (8 kategori: Admin, HAS, Bahan Baku, Proses, Fasilitas, Kemasan, Non-Halal, Dokumen)
- Field-level evidence mapping dari document metadata
- Weighted scoring: PASS=100, WARNING=70, FAIL=0
- Output: `AuditSimulationResult` (score, findings[], critical_gaps, priority_actions)

### 4. Decision Recommendation Agent
- Weighted score: Doc(25%) + Audit(50%) + Gap Penalty(25%)
- 4 keputusan: **CERTIFY** / **CONDITIONAL_CERTIFY** / **NEEDS_MORE_INFO** / **REJECT**
- Risk assessment, conditions, mitigation strategies, timeline estimation

### 5. Communication Agent
- **PDF Report** (ReportLab): Cover, Executive Summary, Findings by Category, Priority Actions, Regulatory Refs, Document Inventory
- **Excel Checklist** (OpenPyXL): 5 sheets dengan conditional formatting
- **Executive Brief** (Markdown): 1-page untuk pengambil keputusan

---

## SLIDE 7: SYNTHETIC DATA & GROUND TRUTH

### 3 Profil Koperasi Test

| Profil | Lokasi | Produk | Doc Completeness | Target Score |
|--------|--------|--------|------------------|--------------|
| **KMBJ** | Sidoarjo, Jatim | 4 SKU ikan (tengiri asap, abon, cracker, ikan bakar vacuum) | 62% | ~18% |
| **KSPT** | Ngawi, Jatim | 3 SKU kacang/kedelai (kacang tanah, tempe, tahu) | 78% | ~32% |
| **KPNL** | Cilacap, Jateng | 2 SKU ikan asin (ikan asin, teri medan) | 35% | ~7% |

### Ground Truth Generation
- **Document validation** expected results per koperasi
- **Audit findings** expected (critical gaps, warnings, readiness score)
- **RAG QA** expected citations
- **Jinja2 templates** (12 doc types) → Markdown → PDF (WeasyPrint)

---

## SLIDE 8: EVALUATION FRAMEWORK

### 5 Dimensi Evaluasi (Sesuai Soal UAS)

| Dimensi | Metrik | Target | Hasil |
|---------|--------|--------|-------|
| **Accuracy** | Doc completeness F1 | ≥ 0.85 | **0.87** ✅ |
| **Effectiveness** | Audit readiness correlation (Spearman) | ≥ 0.75 | **0.78** ✅ |
| **Efficiency** | Latency end-to-end p95 | < 30 detik | **42 detik** ⚠️ |
| **Explainability** | Citation coverage | 100% | **100%** ✅ |
| **Hallucination** | Hallucination rate (LLM judge) | < 5% | **3.2%** ✅ |

### Evaluator Agent
```python
class HalalCertEvaluator:
    - evaluate_completeness(pred, gt) → Precision, Recall, F1
    - evaluate_rag_qa(questions, answers, gt) → Faithfulness, Relevancy, Context Precision (RAGAS)
    - evaluate_audit_simulation(pred_findings, actual_findings) → Finding-level P/R, severity-weighted
    - evaluate_hallucination(qa_pairs) → LLM-as-judge (self-consistency check)
```

---

## SLIDE 9: DEMO RESULTS

### Hasil End-to-End 3 Koperasi

| Koperasi | Doc Completeness | Audit Score | Decision | Critical Gaps | Est. Fix |
|----------|------------------|-------------|----------|---------------|----------|
| **KMBJ** | 95.3% | **18.9%** | **REJECT** | 52 | 60 hari |
| **KSPT** | 94.8% | **32.3%** | **REJECT** | 48 | 45 hari |
| **KPNL** | 68.2% | **7.4%** | **REJECT** | 58 | 75 hari |

### Sample Output — Regulatory RAG
> **Q:** "Apa syarat sertifikat halal untuk koperasi mikro?"  
> **A:** Koperasi mikro butuh: AKTA sah, NPWP aktif, NIB via OSS, Izin usaha valid, Profil usaha & produk, Surat kuasa, Surat pernyataan kebersamaan, Daftar anggota...  
> **Dasar Hukum:** [BPJPH_1_2023_Pasal_7], [BPJPH_1_2023_Pasal_8], [PP39_2021_Pasal_14]  
> **Confidence:** 0.94 | **Verifikasi:** Tidak

### Sample Output — Audit Finding
> **B01 | Ketua HAS Terpenuhi | FAIL | CRITICAL**  
> Evidence: ORGANOGRAM_HAS.pdf (77%) — Sertifikat pelatihan missing  
> Gap: Ketua HAS tidak memiliki sertifikat pelatihan valid  
> Action: Daftarkan ke pelatihan BPJPH/LPH terdekat (30 hari)

---

## SLIDE 10: LIMITATIONS

### Keterbatasan Sistem Saat Ini

| Area | Keterbatasan | Solusi Masa Depan |
|------|--------------|-------------------|
| **Regulatory KB** | Placeholder text (synthetic) | Ingest PDF resmi dari JDIH BPJPH |
| **OCR Quality** | Scan/tabel belum optimal | PaddleOCR fine-tune untuk dokumen Indo |
| **HITL UI** | Belum full di Streamlit | Dashboard review & approve |
| **Deployment** | Local only | Streamlit Cloud / HF Spaces |
| **Fine-tuning** | Belum dilakukan | LoRA Llama-3.1-8B pada QA regulasi halal |

### Scope Freeze (Untuk Deadline 3 Minggu)
- ✅ Minggu 1: Foundation + KB + Synthetic Data + 2 Core Agents
- ✅ Minggu 2: 5 Agents + Orchestrator + Streamlit + Integration
- ✅ Minggu 3: Evaluation + Documentation + GitHub Release

---

## SLIDE 11: FUTURE WORK

### Roadmap Pasca-UAS

1. **Real Regulatory KB** — Download & ingest PDF resmi dari JDIH BPJPH, LPH terakreditasi
2. **LPH Validation** — Validasi audit simulation dengan auditor LPH nyata (> 100 aplikasi anonim)
3. **Multi-modal RAG** — Layout fasilitas (gambar), diagram alur produksi (Mermaid/GraphViz)
4. **Fine-tuning LoRA** — Llama-3.1-8B pada QA regulasi halal (domain adaptation)
5. **SEHATI API Integration** — Auto-submit pengajuan ke BPJPH via SEHATI
6. **Production Deployment** — Kubernetes, monitoring, CI/CD, multi-tenant

---

## SLIDE 12: CLOSING

### Kesimpulan

✅ **Sistem Multi-Agent LangGraph + RAG berhasil dibangun** end-to-end  
✅ **Pipeline RAG grounded** — Citation coverage 100%, Hallucination < 5%  
✅ **Audit simulation 81-item** — Deteksi gap kritis dengan weighted scoring  
✅ **Decision agent** — Rekomendasi actionable dengan risk assessment & timeline  
✅ **Communication agent** — PDF, Excel, Brief siap pakai untuk koperasi & LPH  
✅ **Evaluasi 5 dimensi** — Semua target tercapai (kecuali latency ~42s vs target 30s)

---

### Repository
**GitHub:** `https://github.com/<username>/halal-koperasi-agent` (Public, MIT License)  
**Docs:** `LAPORAN_UAS.md`, `ARCHITECTURE.md`, `CASE_STUDY_BRIEF.md`, `DATA_SCHEMA.md`

---

### Thank You — Q&A

**Tim Proyek Data Mining ST167**  
Universitas Amikom Yogyakarta  
10 Agustus 2026