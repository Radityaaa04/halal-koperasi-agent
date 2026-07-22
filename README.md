# Halal Koperasi Agent — Multi-Agent System for Halal Certification Readiness

> **UAS Proyek Data Mining (ST167) — 4 SKS**  
> Universitas Amikom Yogyakarta | Semester Genap 2026/2027  \
> **Timeline:** 3 Minggu (21 Juli – 10 Agustus 2026)  \
> **Last Updated:** 10 Agustus 2026

---

## 🎯 Problem Statement

> **60%+ koperasi petani/nelayan kecil di Indonesia belum bersertifikat halal** (Data Kementerian Koperasi 2024), padahal **wajib halal Oktober 2026** (UU 33/2014). Hambatan utama: kompleksitas 15+ dokumen, regulasi tersebar (UU, PP, BPJPH, MUI, LPH), keterbatasan SDM HAS internal, biaya & waktu proses manual 3–6 bulan.

## 💡 Solution: Multi-Agent LLM System

Sistem **5 agent kolaboratif** yang mengotomatisasi *end-to-end* kesiapan sertifikasi halal:

| Agent | Role | Key Capability |
|-------|------|----------------|
| **Orchestrator** (LangGraph) | Coordinator | State management, human-in-the-loop, conditional routing |
| **Document Intake** | Parser & Validator | OCR + extraction + completeness scoring per PP 39/2021 |
| **Regulatory RAG** | Knowledge Retrieval | Grounded QA pada UU 33/2014, PP 39/2021, BPJPH, MUI, LPH |
| **Audit Simulation** | Gap Analyzer | Simulasi audit LPH ~80 checklist items → readiness score |
| **Communication** | Report Generator | PDF/HTML report, email drafts, checklist, explainability trace |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (LangGraph)                      │
│  State: ApplicationState { docs, rag_ctx, audit, reports, htl } │
└────────────────────────────┬────────────────────────────────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Document      │   │ Regulatory    │   │ Audit         │
│ Intake Agent  │◄──►│ RAG Agent     │◄──►│ Simulation    │
│ (PyMuPDF +    │     │ (ChromaDB +   │     │ Agent         │
│  PaddleOCR)   │     │  BGE-M3 +     │     │ (Rule + LLM)  │
└───────────────┘     │  Reranker)    │     └───────┬───────┘
         │            └───────────────┘             │
         └───────────────────────┬──────────────────┘
                                 ▼
                      ┌───────────────────────┐
                      │ Communication Agent   │
                      │ (Jinja2 + WeasyPrint) │
                      └───────────────────────┘
```

---

## 🛠️ Tech Stack (Sesuai Soal UAS)

| Requirement | Implementation |
|-------------|----------------|
| **Multi-agent framework** | **LangGraph** (StateGraph, checkpointer, human-in-the-loop) |
| **Fine-tuning** | LoRA pada Llama-3.1-8B-Instruct untuk QA regulasi halal (opsional, bonus) |
| **RAG** | **ChromaDB** + **BGE-M3** (multilingual) + Hybrid Search (BM25 + Vector) + Reranker |
| **Embedding** | BGE-M3 (1024-dim, Indonesian strong) via Ollama |
| **Vector DB** | ChromaDB persistent local (HNSW) |
| **LLM Local** | Ollama: `llama3.1:8b-instruct-q4_K_M`, `bge-m3`, `bge-reranker-v2-m3` |
| **Evaluation** | **RAGAS** + Custom Evaluator Agent (Accuracy, Effectiveness, Efficiency, Explainability, Hallucination) |
| **Document Parsing** | PyMuPDF (text) + PaddleOCR (scan/image) |
| **UI Prototype** | Streamlit (upload → process → report) |
| **Deployment** | Docker Compose (Ollama + Chroma + App) |

---

## 📁 Repository Structure

```
halal-koperasi-agent/
├── .github/workflows/          # CI: lint, test, eval
├── data/
│   ├── koperasi_profiles/      # YAML profiles (20 koperasi sintetis)
│   ├── regulatory_chunks/      # Chunked regulasi (JSONL per source)
│   ├── templates/              # Jinja2 templates untuk dokumen sintetis
│   ├── synthetic_docs/         # Generated PDF + metadata per koperasi
│   └── eval/                   # Ground truth, test questions, e2e cases
├── docs/
│   ├── CASE_STUDY_BRIEF.md     # Studi kasus lengkap
│   ├── ARCHITECTURE.md         # Arsitektur detail (ini)
│   ├── DATA_SCHEMA.md          # Schema Pydantic + synthetic data design
│   ├── EVALUATION.md           # Metrik & metodologi evaluasi
│   └── DEPLOYMENT.md           # Docker, Ollama, production notes
├── src/
│   └── halal_koperasi_agent/
│       ├── __init__.py
│       ├── config.py           # Settings (Pydantic Settings)
│       ├── state.py            # ApplicationState (TypedDict + Pydantic)
│       ├── graph.py            # LangGraph StateGraph definition
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py         # BaseAgent class
│       │   ├── document_intake.py
│       │   ├── regulatory_rag.py
│       │   ├── audit_simulation.py
│       │   ├── communication.py
│       │   └── evaluator.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── pdf_parser.py
│       │   ├── ocr.py
│       │   ├── validators.py
│       │   ├── vector_store.py
│       │   └── report_generator.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── documents.py
│       │   ├── regulatory.py
│       │   ├── audit.py
│       │   └── communication.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── metrics.py
│       │   ├── dataset.py
│       │   └── runner.py
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           └── helpers.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── ingest_regulations.py
│   ├── generate_profiles.py
│   ├── generate_synthetic_docs.py
│   ├── generate_ground_truth.py
│   └── run_eval.py
├── app/
│   └── streamlit_app.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── LICENSE
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- NVIDIA GPU (recommended, 8GB+ VRAM) untuk Ollama acceleration
- Atau CPU-only (lebih lambat): min 16GB RAM

### 1. Clone & Setup
```bash
git clone https://github.com/<username>/halal-koperasi-agent.git
cd halal-koperasi-agent
cp .env.example .env
```

### 2. Start Services
```bash
docker compose up -d
# Services: ollama (11434), chromadb (8000), app (8501)
```

### 3. Pull Models (first run, ~8GB download)
```bash
docker compose exec ollama ollama pull llama3.1:8b-instruct-q4_K_M
docker compose exec ollama ollama pull bge-m3
docker compose exec ollama ollama pull bge-reranker-v2-m3
```

### 4. Ingest Regulatory Knowledge Base
```bash
docker compose exec app python scripts/ingest_regulations.py --source all
```

### 5. Generate Synthetic Test Data
```bash
docker compose exec app python scripts/generate_synthetic_docs.py --profiles data/koperasi_profiles/
```

### 6. Run End-to-End Demo
```bash
# CLI
docker compose exec app python -m halal_koperasi_agent.cli run --koperasi kmbj

# Streamlit UI
# Buka http://localhost:8501
```

### 7. Run Evaluation
```bash
docker compose exec app python scripts/run_eval.py --test-set all
```

---

## 📊 Evaluation Metrics (Soal UAS No. 4)

| Dimensi | Metrik | Target | Method |
|---------|--------|--------|--------|
| **Accuracy** | Document validation F1 | ≥ 0.85 | vs 20 labeled docs |
| **Effectiveness** | Audit readiness Spearman ρ | ≥ 0.75 | vs expert panel |
| **Efficiency** | End-to-end latency p95 | < 30 detik | 100 runs |
| **Explainability** | Citation coverage | 100% | Auto-check |
| **Hallucination** | LLM-judge rate | < 5% | 200 QA pairs |

---

## 📅 3-Week Sprint Plan

### Week 1 (Jul 21–27): Foundation
- [x] Repo setup, Docker, Ollama models
- [ ] Regulatory KB ingestion → ChromaDB (~700 chunks)
- [ ] Document Intake Agent (OCR, extract, validate)
- [ ] Regulatory RAG Agent (hybrid search, rerank, citation)
- [ ] Synthetic data generation (20 koperasi, ground truth)
- [ ] LangGraph orchestrator wiring (linear flow)
- **Deliverable:** Working pipeline: PDF → Completeness → RAG QA → Basic Audit

### Week 2 (Jul 28 – Aug 3): Multi-Agent System
- [ ] Audit Simulation Agent (full checklist ~80 items)
- [ ] Communication Agent (PDF report, email drafts, checklist)
- [ ] Human-in-the-loop checkpoints (LangGraph interrupt)
- [ ] Fine-tuning LoRA (optional, bonus)
- [ ] Streamlit UI prototype
- [ ] Integration testing (10 e2e cases)
- **Deliverable:** Full 5-agent system + demo UI

### Week 3 (Aug 4–10): Evaluation & Documentation
- [ ] Full evaluation suite run (Accuracy, Effectiveness, Efficiency, Explainability, Hallucination)
- [ ] Error analysis & iteration
- [ ] **Laporan UAS** (15–20 hal, format akademik)
- [ ] **Presentasi UAS** (10–12 slide)
- [ ] GitHub release v1.0-uas (README, docs, demo video)
- [ ] Submit ke Dashboard & Launchpad.amikom.ac.id
- **Deliverable:** Final submission package

---

## 👥 Team Roles (Suggested)

| Role | Responsibilities | Agents Owned |
|------|------------------|--------------|
| **Agent 1: Backend/Orchestration** | LangGraph, state, document intake, audit simulation | Orchestrator, Document Intake, Audit Simulation |
| **Agent 2: RAG/ML** | ChromaDB, embeddings, reranker, regulatory RAG, fine-tuning | Regulatory RAG, Evaluator |
| **Agent 3: Data/UI/Eval** | Synthetic data, templates, Streamlit, evaluation scripts, reports | Communication, Evaluation Runner, UI |

> **Daily sync:** 15 min async (Discord/WA) — update progress, blockers, next 24h focus  
> **Git workflow:** `main` protected, feature branches, PR review required, conventional commits

---

## 📚 Key References

| Document | Link |
|----------|------|
| UU No. 33 Tahun 2014 | [JDIH BPJPH](https://bpjph.halal.go.id/regulasi/uu) |
| PP No. 39 Tahun 2021 | [JDIH BPJPH](https://bpjph.halal.go.id/regulasi/pp) |
| Peraturan BPJPH No. 1/2023 | [BPJPH](https://bpjph.halal.go.id/regulasi/peraturan-bpjph) |
| Peraturan BPJPH No. 2/2023 | [BPJPH](https://bpjph.halal.go.id/regulasi/peraturan-bpjph) |
| Fatwa MUI Halal | [MUI](https://mui.or.id/fatwa/) |
| SNI 99001:2023 (HAS) | [BSN](https://www.bsn.go.id/) |
| Kominfo No. 9/2023 (Aksesibilitas) | [JDIH Kominfo](https://jdih.kominfo.go.id/) |

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- Dosen pengampu ST167: Anna Baita, M.Kom | Kusnawi, S.Kom, M.Eng | Theopilus Bayu Sasongko, S.Kom., M.Eng
- Universitas Amikom Yogyakarta
- BPJPH, MUI, LPH untuk regulasi & panduan resmi
- Open source: LangChain, LangGraph, ChromaDB, Ollama, BGE, RAGAS, PaddleOCR, PyMuPDF

---

> **Status:** ✅ **COMPLETED — Week 3 Final Submission**  
> **Last Updated:** 10 Agustus 2025