# Contributing to Halal Koperasi Agent

Terima kasih atas minat Anda berkontribusi! Proyek ini bertujuan membantu koperasi MSME Indonesia memperoleh sertifikasi Halal secara efisien.

## 🛠️ Cara Kontribusi

### 1. Setup Development Environment
```bash
# Fork & clone
git clone https://github.com/your-fork/halal-koperasi-agent.git
cd halal-koperasi-agent

# Install dev dependencies
pip install -r requirements-dev.txt
pre-commit install

# Start services
docker compose up -d
```

### 2. Coding Standards
- **Python 3.11+** with type hints (mypy strict)
- **Formatting**: `black` (line length 100)
- **Linting**: `ruff` (replaces flake8, isort)
- **Type checking**: `mypy --strict src/ tests/`
- **Docstrings**: Google style for public APIs

```bash
# Run all checks
ruff check src/ tests/
black src/ tests/
mypy src/ tests/
pytest tests/ -v
```

### 3. Commit Convention
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add PDF table extraction for Bahan Baku
fix: handle missing NPWP in validator
docs: update ARCHITECTURE.md with new RAG flow
test: add e2e test for KMBJ profile
refactor: extract base agent class
```

### 4. Pull Request Process
1. Buat branch dari `main`: `feature/xxx`, `fix/xxx`, `docs/xxx`
2. Pastikan semua test pass (`pytest tests/`)
3. Update dokumentasi terkait (README, docs/, docstrings)
4. Tambahkan changelog entry di `CHANGELOG.md` (jika ada)
5. Request review — minimal 1 approval

---

## 🏗️ Arsitektur Singkat

| Komponen | File Utama |
|----------|------------|
| State Schema | `src/halal_koperasi_agent/state.py` |
| Graph Definition | `src/halal_koperasi_agent/graph.py` |
| Base Agent | `src/halal_koperasi_agent/agents/base.py` |
| Document Intake | `src/halal_koperasi_agent/agents/document_intake.py` |
| Regulatory RAG | `src/halal_koperasi_agent/agents/regulatory_rag.py` |
| Audit Simulation | `src/halal_koperasi_agent/agents/audit_simulation.py` |
| Communication | `src/halal_koperasi_agent/agents/communication.py` |
| Evaluator | `src/halal_koperasi_agent/agents/evaluator.py` |

---

## 🧪 Menambah Test

- **Unit**: `tests/unit/test_<module>.py` — test fungsi/kelas isolasi
- **Integration**: `tests/integration/test_<flow>.py` — multi-agent flow
- **E2E**: `tests/e2e/test_<scenario>.py` — full pipeline dengan data sintetis

Gunakan `pytest-mock` untuk mock LLM/ChromaDB di unit test.

---

## 📝 Dokumentasi

Semua dokumentasi teknis di folder `docs/`:
- `ARCHITECTURE.md` — diagram alur data, state machine
- `DATA_SCHEMA.md` — Pydantic models, synthetic data design
- `EVALUATION.md` — metrik, metodologi, ground truth
- `DEPLOYMENT.md` — Docker, Ollama, production hardening
- `CASE_STUDY.md` — walkthrough end-to-end

---

## 🐛 Melaporkan Bug

Gunakan [GitHub Issues](https://github.com/your-org/halal-koperasi-agent/issues) dengan template:
- **Bug Report**: steps to reproduce, expected vs actual, logs
- **Feature Request**: use case, proposed API, priority

---

## 💬 Diskusi

- **GitHub Discussions** untuk pertanyaan umum, ide, showcase
- **Issues** untuk bug & feature tracking

---

## 📜 Code of Conduct

Proyek ini mengikuti [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Dengan berpartisipasi, Anda setuju menjaga lingkungan yang inklusif & hormat.

---

**Pertanyaan?** Buka [Discussion](https://github.com/your-org/halal-koperasi-agent/discussions) atau email maintainer.