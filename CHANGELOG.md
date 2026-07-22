# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-agent architecture with LangGraph StateGraph orchestration
- Document Intake Agent: PDF parsing, OCR, validation, completeness scoring
- Regulatory RAG Agent: ChromaDB + BGE-M3 + BGE-Reranker, grounded citations
- Audit Simulation Agent: 80-item LPH checklist, gap analysis, readiness scoring
- Communication Agent: PDF reports, Excel checklists, email drafts
- Synthetic data generation: 20 cooperative profiles, 300 documents
- Evaluation framework: RAGAS + custom metrics (Accuracy, Effectiveness, Efficiency, Explainability, Hallucination)
- Docker Compose deployment with Ollama, ChromaDB, Streamlit UI

### Changed
- N/A

### Fixed
- N/A

## [1.0.0] - 2026-08-10

### Added
- Initial release: Complete 5-agent system for Halal certification readiness
- Local LLM inference via Ollama (Llama-3.1-8B, BGE-M3, BGE-Reranker)
- ChromaDB persistent vector storage with HNSW indexing
- Human-in-the-loop checkpoints with SQLite checkpointing
- Streamlit prototype UI for stakeholder demos
- Comprehensive evaluation suite with synthetic ground truth
- Full documentation: ARCHITECTURE.md, DATA_SCHEMA.md, EVALUATION.md, DEPLOYMENT.md

---

## Versioning Policy

- **Major (X.0.0)**: Breaking changes to agent interfaces, state schema, or API
- **Minor (X.Y.0)**: New agents, new evaluation metrics, new regulatory sources
- **Patch (X.Y.Z)**: Bug fixes, documentation, performance improvements

## Release Process

1. Update `CHANGELOG.md` with version & date
2. Tag release: `git tag -a v1.0.0 -m "Release v1.0.0"`
3. Push tags: `git push origin --tags`
4. GitHub Actions builds Docker images & publishes to GHCR
5. Create GitHub Release with changelog excerpt