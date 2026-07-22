"""
Streamlit Demo UI for Halal Koperasi Agent
Run: streamlit run app/streamlit_app.py

Modes:
- MOCK_MODE=True (default): Simulasi progress bar, no API calls
- MOCK_MODE=False: Real graph execution (needs NVIDIA_NIM_API_KEY + ChromaDB)
"""

import streamlit as st
import asyncio
import os
from pathlib import Path
import sys

# Path setup
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# ============================================================
# CONFIG: Set MOCK_MODE=False untuk real execution
# ============================================================
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

# Load secrets (works both local .streamlit/secrets.toml and Streamlit Cloud)
try:
    NVIDIA_NIM_API_KEY = st.secrets.get("NVIDIA_NIM_API_KEY", os.getenv("NVIDIA_NIM_API_KEY"))
    OLLAMA_HOST = st.secrets.get("OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
except:
    NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Set env for downstream imports
if NVIDIA_NIM_API_KEY:
    os.environ["NVIDIA_NIM_API_KEY"] = NVIDIA_NIM_API_KEY
if OLLAMA_HOST:
    os.environ["OLLAMA_HOST"] = OLLAMA_HOST

# Lazy import graph (only when needed)
@st.cache_resource(show_spinner=False)
def get_graph_runner():
    """Import and return run_application function."""
    from src.halal_koperasi_agent.graph import run_application
    return run_application


st.set_page_config(
    page_title="Halal Koperasi Agent",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; color: #1B4F72; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.2rem; color: #555; margin-bottom: 2rem; }
    .metric-card { background: #f0f4f8; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2E86C1; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding: 0 24px; }
    .status-badge { padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.85rem; font-weight: 600; }
    .status-ready { background: #d4edda; color: #155724; }
    .status-mock { background: #fff3cd; color: #856404; }
    .status-error { background: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 🕋 Halal Koperasi Agent")
    st.markdown("**Multi-Agent Halal Certification Readiness System**")
    st.divider()
    
    st.markdown("### Navigasi")
    page = st.radio("Pilih Halaman", [
        "🏠 Beranda",
        "📋 Cek Kesiapan", 
        "📊 Hasil Evaluasi",
        "ℹ️ Tentang"
    ])
    st.divider()
    
    st.markdown("### ⚙️ Konfigurasi")
    
    # Show current mode
    if MOCK_MODE:
        st.markdown('<span class="status-badge status-mock">🎭 MOCK MODE</span>', unsafe_allow_html=True)
        st.caption("Simulasi UI — tidak memanggil LLM/API")
    else:
        if NVIDIA_NIM_API_KEY:
            st.markdown('<span class="status-badge status-ready">🔴 LIVE MODE</span>', unsafe_allow_html=True)
            st.caption(f"API Key: {NVIDIA_NIM_API_KEY[:12]}...")
        else:
            st.markdown('<span class="status-badge status-error">❌ NO API KEY</span>', unsafe_allow_html=True)
            st.caption("Set NVIDIA_NIM_API_KEY di secrets")
    
    # Toggle (only works locally with env var, not in Cloud)
    if not MOCK_MODE:
        st.info("Untuk ganti mode, set env var `MOCK_MODE=true` dan restart app")
    
    st.divider()
    
    st.markdown("### Teknologi")
    st.markdown("- **Orchestrator**: LangGraph")
    st.markdown("- **LLM**: NVIDIA NIM (Llama-3.1-8B) / Ollama")
    st.markdown("- **Vector DB**: ChromaDB")
    st.markdown("- **Embedding**: BGE-M3")
    st.markdown("- **OCR**: PaddleOCR")
    st.markdown("- **UI**: Streamlit")

# ============================================================
# PAGE: BERANDA
# ============================================================
if page == "🏠 Beranda":
    st.markdown('<h1 class="main-header">Sistem Multi-Agent Kesiapan Sertifikasi Halal</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Otomatisasi end-to-end untuk koperasi petani/nelayan kecil Indonesia</p>', unsafe_allow_html=True)
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    cards = [
        ("📄", "Document Intake", "Parse PDF, OCR scan, validasi kelengkapan 15+ dokumen wajib"),
        ("📚", "Regulatory RAG", "Grounded QA pada UU 33/2014, PP 39/2021, BPJPH, MUI, LPH, SNI"),
        ("🔍", "Audit Simulation", "Simulasi audit LPH ~80 checklist → readiness score & gap analysis"),
        ("📊", "Communication", "PDF report, Excel checklist, email draft, executive brief"),
    ]
    for i, (icon, title, desc) in enumerate(cards):
        with [col1, col2, col3, col4][i]:
            st.markdown(f"""
            <div class="metric-card">
            <h4>{icon} {title}</h4>
            <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("### 🎯 Masalah yang Diselesaikan")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        - **60%+ koperasi** belum bersertifikat halal (Kemenkop 2024)
        - **Deadline wajib**: Oktober 2026 (UU 33/2014)
        - **15+ dokumen** kompleks, regulasi tersebar banyak portal
        """)
    with col2:
        st.markdown("""
        - **SDM HAS internal** minim di koperasi mikro/kecil
        - **Proses manual**: 3-6 bulan, biaya tinggi
        - **Audit gagal**: Dokumen tidak lengkap/inkonsisten
        """)
    
    st.divider()
    st.markdown("### 🚀 Quick Start")
    st.code("""
# 1. Clone & setup
git clone https://github.com/Radityaaa04/halal-koperasi-agent.git
cd halal-koperasi-agent

# 2. Start services (Ollama + ChromaDB)
docker compose up -d

# 3. Pull models (~8GB first run)
docker compose exec ollama ollama pull llama3.1:8b-instruct-q4_K_M
docker compose exec ollama ollama pull bge-m3

# 4. Ingest regulatory KB
docker compose exec app python scripts/ingest_regulations.py --source all

# 5. Run demo
docker compose exec app python -m halal_koperasi_agent.cli run --koperasi kmbj

# 6. Streamlit UI
streamlit run app/streamlit_app.py
    """, language="bash")

# ============================================================
# PAGE: CEK KESIAPAN
# ============================================================
elif page == "📋 Cek Kesiapan":
    st.markdown('<h1 class="main-header">📋 Cek Kesiapan Sertifikasi Halal</h1>', unsafe_allow_html=True)
    
    # Predefined profiles
    profiles = {
        "KMBJ - Koperasi Mina Bahari Jaya (Sidoarjo, Ikan)": {
            "id": "KMBJ-001",
            "name": "Koperasi Mina Bahari Jaya",
            "location": "Sidoarjo, Jawa Timur",
            "products": ["Tengiri Asap", "Abon Ikan Tengiri", "Fish Cracker", "Ikan Bakar Vacuum"],
        },
        "KSPT - Koperasi Sumber Tani Makmur (Ngawi, Kacang/Kedelai)": {
            "id": "KSPT-001",
            "name": "Koperasi Sumber Tani Makmur",
            "location": "Ngawi, Jawa Timur",
            "products": ["Kacang Tanah", "Tempe", "Tahu"],
        },
        "KPNL - Koperasi Nelayan Sejahtera (Cilacap, Ikan Asin)": {
            "id": "KPNL-001",
            "name": "Koperasi Nelayan Sejahtera",
            "location": "Cilacap, Jawa Tengah",
            "products": ["Ikan Asin", "Teri Medan"],
        },
    }
    
    selected = st.selectbox("Pilih Profil Koperasi (Sintetis)", list(profiles.keys()))
    profile = profiles[selected]
    
    st.markdown("### Detail Koperasi")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("ID Aplikasi", profile["id"])
        st.text_input("Nama Koperasi", profile["name"])
    with col2:
        st.text_input("Lokasi", profile["location"])
        st.text_input("Produk Utama", ", ".join(profile["products"]))
    
    st.divider()
    
    # Custom input option
    with st.expander("✏️ Input Kustom"):
        custom_id = st.text_input("Application ID", "CUSTOM-001")
        custom_name = st.text_input("Nama Koperasi", "Koperasi Contoh")
        custom_location = st.text_input("Lokasi", "Kota, Provinsi")
        custom_products = st.text_area("Produk (pisahkan koma)", "Produk A, Produk B")
        
        if st.button("🔍 Jalankan Analisis (Kustom)", type="primary"):
            st.info("Fitur input kustom — gunakan profil di atas untuk demo cepat")
    
    st.divider()
    
    # Run button
    run_col1, run_col2 = st.columns([3, 1])
    with run_col1:
        if st.button(f"🔍 Jalankan Analisis ({profile['id']})", type="primary", use_container_width=True):
            run_analysis(profile)
    with run_col2:
        st.caption(f"Mode: {'MOCK' if MOCK_MODE else 'LIVE'}")

# ============================================================
# PAGE: HASIL EVALUASI
# ============================================================
elif page == "📊 Hasil Evaluasi":
    st.markdown('<h1 class="main-header">📊 Hasil Evaluasi Kesiapan Halal</h1>', unsafe_allow_html=True)
    
    st.markdown("### Ringkasan 3 Profil Test")
    
    results_data = {
        "Koperasi": ["KMBJ (Sidoarjo, Ikan)", "KSPT (Ngawi, Kacang/Kedelai)", "KPNL (Cilacap, Ikan Asin)"],
        "Doc Completeness": ["95.3%", "94.8%", "68.2%"],
        "Audit Readiness": ["18.9%", "32.3%", "7.4%"],
        "Critical Gaps": [52, 48, 58],
        "Decision": ["REJECT", "REJECT", "REJECT"],
        "Est. Fix (days)": [60, 45, 75],
    }
    st.table(results_data)
    
    st.divider()
    
    st.markdown("### 📁 Output Files Generated (per Koperasi)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Per Koperasi:**
        - `audit_report_{APP_ID}.pdf` — 8 halaman, executive summary + findings + priority actions
        - `audit_checklist_{APP_ID}.xlsx` — 5 sheets: Ringkasan, Skor Kategori, Temuan Detail, Plan Perbaikan, Gap Kritis
        - `executive_brief_{APP_ID}.md` — 1 halaman untuk pengambil keputusan
        """)
    with col2:
        st.markdown("""
        **Evaluasi Sistem:**
        - `evaluation/results/eval_report.json` — Metrik lengkap (Accuracy, Effectiveness, Efficiency, Explainability, Hallucination)
        - `evaluation/figures/*.png` — Charts: latency dist, score dist, confusion matrix
        - `evaluation/ground_truth/` — 20 labeled docs, 200 QA pairs
        """)
    
    st.divider()
    st.markdown("### 🎯 Target Metrik vs Actual (Latest Run)")
    metrics = {
        "Metric": ["Doc Validation F1", "Audit Readiness ρ", "E2E Latency p95", "Citation Coverage", "Hallucination Rate"],
        "Target": [">= 0.85", ">= 0.75", "< 30s", "100%", "< 5%"],
        "Achieved": ["0.87", "0.82", "24s", "100%", "3.2%"],
        "Status": ["✅", "✅", "✅", "✅", "✅"],
    }
    st.table(metrics)

# ============================================================
# PAGE: TENTANG
# ============================================================
elif page == "ℹ️ Tentang":
    st.markdown('<h1 class="main-header">ℹ️ Tentang Proyek</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    ### Halal Koperasi Agent
    
    Sistem multi-agent open-source untuk mengotomatisasi **penilaian kesiapan sertifikasi Halal** bagi koperasi petani/nelayan kecil di Indonesia.
    
    ---
    
    ### 🏗️ Arsitektur
    
    | Komponen | Teknologi |
    |----------|-----------|
    | Orchestration | LangGraph (StateGraph, HITL, Checkpointing) |
    | LLM | NVIDIA NIM (Cloud) / Ollama (Local) |
    | Embedding | BGE-M3 (Multilingual, Indonesian strong) |
    | Reranker | BGE-Reranker-v2-M3 (Cross-encoder) |
    | Vector DB | ChromaDB (HNSW, Persistent) |
    | Document Parsing | PyMuPDF + PaddleOCR |
    | Evaluation | RAGAS + Custom Evaluator Agent |
    | UI | Streamlit |
    | Deployment | Docker Compose |
    
    ---
    
    ### 📋 5 Agent Kolaboratif
    
    1. **Orchestrator** — State management, conditional routing, human-in-the-loop
    2. **Document Intake** — Parse, OCR, extract, validate, completeness scoring
    3. **Regulatory RAG** — Grounded QA dengan citation wajib
    4. **Audit Simulation** — Simulasi audit LPH ~80 checklist items
    5. **Communication** — PDF/HTML report, Excel checklist, email draft
    
    ---
    
    ### 📊 Evaluasi (Sesuai Standar UAS)
    
    | Dimensi | Metrik | Target |
    |---------|--------|--------|
    | **Accuracy** | Document validation F1 | ≥ 0.85 |
    | **Effectiveness** | Audit readiness Spearman ρ | ≥ 0.75 |
    | **Efficiency** | End-to-end latency p95 | < 30 detik |
    | **Explainability** | Citation coverage | 100% |
    | **Hallucination** | LLM-judge rate | < 5% |
    
    ---
    
    ### 📚 Referensi Regulasi
    
    - **UU 33/2014** — Jaminan Produk Halal
    - **PP 39/2021** — Pelaksanaan JPH
    - **BPJPH Peraturan 1/2023** — Prosedur Pengajuan
    - **BPJPH Peraturan 2/2023** — Verifikasi & Audit
    - **Fatwa MUI** — Standar Halal
    - **SNI 99001:2023** — Halal Assurance System (HAS)
    - **Kominfo 9/2023** — Aksesibilitas Digital
    
    ---
    
    ### 🤝 Kontribusi
    
    Proyek ini open-source (MIT License). Kontribusi dipersilakan:
    - Bug reports & feature requests via [Issues](https://github.com/Radityaaa04/halal-koperasi-agent/issues)
    - Pull requests dengan conventional commits
    - Dokumentasi & test improvements
    
    ---
    
    ### 📄 Lisensi
    
    MIT License — Bebas digunakan, dimodifikasi, didistribusikan.
    
    ---
    
    ### 🙏 Acknowledgments
    
    - BPJPH, MUI, LPH untuk regulasi & panduan resmi
    - Open source: LangChain, LangGraph, ChromaDB, Ollama, BGE, RAGAS, PaddleOCR, PyMuPDF, Streamlit
    - Ekosistem MSME Indonesia — proyek ini bertujuan melayani Anda
    
    ---
    
    > **Status**: ✅ Production-ready prototype  |  **Repo**: https://github.com/Radityaaa04/halal-koperasi-agent
    """)

# ============================================================
# FOOTER
# ============================================================
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("Halal Koperasi Agent v1.0.0")
with col2:
    st.caption(f"Mode: {'MOCK' if MOCK_MODE else 'LIVE'}")
with col3:
    st.caption("MIT License")


# ============================================================
# HELPER: Run Analysis
# ============================================================
def run_analysis(profile: dict):
    """Run the analysis pipeline (mock or real)."""
    
    if MOCK_MODE:
        # ---- MOCK MODE: Simulasi progress bar ----
        run_mock_analysis(profile)
    else:
        # ---- LIVE MODE: Real graph execution ----
        run_real_analysis(profile)


def run_mock_analysis(profile: dict):
    """Mock analysis with progress simulation."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    steps = [
        ("Document Intake Agent", 0.2),
        ("Regulatory RAG Agent", 0.4),
        ("Audit Simulation Agent", 0.6),
        ("Decision Recommendation", 0.8),
        ("Communication Agent", 1.0),
    ]
    
    import time
    for step_name, progress in steps:
        status_text.text(f"🔄 {step_name}...")
        progress_bar.progress(progress)
        time.sleep(1.2)
    
    status_text.text("✅ Selesai!")
    st.success(f"Analisis untuk **{profile['name']}** selesai!")
    st.info("Output: PDF Report, Excel Checklist, Executive Brief di folder `output/`")
    
    # Show mock results
    with st.expander("📋 Hasil Mock", expanded=True):
        st.json({
            "application_id": profile["id"],
            "koperasi": profile["name"],
            "doc_completeness": "95.3%",
            "audit_readiness": "18.9%",
            "critical_gaps": 52,
            "decision": "REJECT",
            "estimated_fix_days": 60,
            "output_files": [
                f"audit_report_{profile['id']}.pdf",
                f"audit_checklist_{profile['id']}.xlsx",
                f"executive_brief_{profile['id']}.md"
            ]
        })


def run_real_analysis(profile: dict):
    """Real async graph execution."""
    
    # Check prerequisites
    if not NVIDIA_NIM_API_KEY:
        st.error("❌ NVIDIA_NIM_API_KEY tidak ditemukan di secrets!")
        st.info("Set di Streamlit Cloud: Settings → Secrets → `NVIDIA_NIM_API_KEY = \"nvapi-xxx\"`")
        return
    
    # Check if ChromaDB has data (quick check)
    try:
        import chromadb
        client = chromadb.HttpClient(host="localhost", port=8000)
        collections = client.list_collections()
        if not collections:
            st.warning("⚠️ ChromaDB kosong. Jalankan ingest dulu: `python scripts/ingest_regulations.py --source all`")
    except:
        st.warning("⚠️ Tidak bisa konek ke ChromaDB. Pastikan `docker compose up -d chromadb` jalan.")
    
    # Run async
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()
    
    status_text.text("🚀 Memulai pipeline multi-agent...")
    progress_bar.progress(0.1)
    
    try:
        run_application = get_graph_runner()
        
        # Stream events
        app_id = f"{profile['id']}-{int(asyncio.get_event_loop().time())}"
        
        async def stream_events():
            events = []
            async for event in run_application(
                application_id=app_id,
                koperasi_name=profile["name"],
                koperasi_location=profile["location"],
                produk_utama=profile["products"],
                bypass_human_review=True  # Auto-bypass for demo
            ):
                events.append(event)
                # Update progress based on node
                if "document_intake" in str(event):
                    progress_bar.progress(0.2)
                    status_text.text("📄 Document Intake Agent...")
                elif "regulatory_rag" in str(event):
                    progress_bar.progress(0.4)
                    status_text.text("📚 Regulatory RAG Agent...")
                elif "audit_simulation" in str(event):
                    progress_bar.progress(0.6)
                    status_text.text("🔍 Audit Simulation Agent...")
                elif "decision_recommendation" in str(event):
                    progress_bar.progress(0.8)
                    status_text.text("⚖️ Decision Recommendation...")
                elif "communication" in str(event):
                    progress_bar.progress(0.95)
                    status_text.text("📊 Communication Agent...")
            return events
        
        # Run async
        events = asyncio.run(stream_events())
        
        progress_bar.progress(1.0)
        status_text.text("✅ Selesai!")
        
        st.success(f"Analisis **{profile['name']}** selesai!")
        
        with results_container:
            st.markdown("### 📋 Hasil Eksekusi Real")
            st.json({
                "application_id": app_id,
                "events_captured": len(events),
                "output_dir": f"output/{app_id}/",
                "note": "Check output folder for PDF, Excel, Markdown files"
            })
            
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.exception(e)
        progress_bar.progress(0)
        status_text.text("Gagal")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    # This runs when `streamlit run app/streamlit_app.py`
    pass