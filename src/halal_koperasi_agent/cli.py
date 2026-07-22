#!/usr/bin/env python3
"""
CLI for HALAL Koperasi Multi-Agent System
"""

import asyncio
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import settings
from .state import create_initial_state
from .graph import graph

app = typer.Typer(name="halal-koperasi", help="Multi-Agent Halal Certification System for Indonesian Cooperatives")
console = Console()


@app.command()
def run(
    koperasi: str = typer.Argument(..., help="Koperasi profile: kmbj, kspt, kpnl"),
    application_id: str = typer.Option(None, "--app-id", "-a", help="Application ID (auto-generated if not provided)"),
    thread_id: str = typer.Option(None, "--thread-id", "-t", help="Thread ID for checkpointing"),
    output_dir: str = typer.Option("output/week1", "--output", "-o", help="Output directory for reports"),
):
    """Run the full multi-agent workflow for a koperasi"""
    
    profiles = {
        "kmbj": {
            "id": "KMBJ-001",
            "name": "Koperasi Mina Bahari Jaya",
            "location": "Sidoarjo, Jawa Timur",
            "products": ["Tengiri Asap", "Abon Ikan Tengiri", "Fish Cracker", "Ikan Bakar Vacuum"]
        },
        "kspt": {
            "id": "KSPT-002",
            "name": "Koperasi Sumber Tani Makmur",
            "location": "Ngawi, Jawa Timur",
            "products": ["Kacang Tanah", "Tempe", "Tahu"]
        },
        "kpnl": {
            "id": "KPNL-003",
            "name": "Koperasi Nelayan Sejahtera",
            "location": "Cilacap, Jawa Tengah",
            "products": ["Ikan Asin", "Teri Medan"]
        }
    }
    
    if koperasi not in profiles:
        console.print(f"[red]Unknown koperasi: {koperasi}. Available: {list(profiles.keys())}[/red]")
        raise typer.Exit(1)
    
    profile = profiles[koperasi]
    app_id = application_id or f"{profile['id']}-2025-001"
    tid = thread_id or app_id
    
    console.print(Panel.fit(
        f"[bold]HALAL Koperasi Agent - Multi-Agent Workflow[/bold]\n"
        f"Koperasi: {profile['name']} ({profile['id']})\n"
        f"Application ID: {app_id}\n"
        f"Thread ID: {tid}\n"
        f"Produk: {', '.join(profile['products'])}",
        title="🚀 Starting Workflow",
        border_style="green"
    ))
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Run the workflow
    initial_state = create_initial_state(
        application_id=app_id,
        koperasi_name=profile["name"],
        koperasi_location=profile["location"],
        produk_utama=profile["products"]
    )
    
    config = {"configurable": {"thread_id": tid}}
    
    console.print("[yellow]Running workflow...[/yellow]")
    
    # Run synchronously (for CLI)
    final_state = graph.invoke(initial_state, config=config)
    
    # Display results
    _display_results(final_state)
    
    console.print(f"[green]✅ Workflow completed! Check {output_dir}/ for reports.[/green]")


def _display_results(state: dict):
    """Display workflow results"""
    console.print(Panel.fit(
        f"[bold]Workflow Results[/bold]\n"
        f"Application ID: {state.get('application_id', 'N/A')}\n"
        f"Status: {state.get('status', 'N/A')}\n"
        f"Progress: {state.get('progress_percentage', 0):.1f}%\n"
        f"Document Completeness: {state.get('document_completeness_score', 0):.1%}\n"
        f"Missing Docs: {len(state.get('missing_required_docs', []))}",
        title="📋 Summary",
        border_style="green"
    ))


@app.command()
def ingest(
    source: str = typer.Option("all", "--source", "-s", help="Regulatory source to ingest (all, uu33, pp39, bpjph1, bpjph2, mui, lph, sni)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-ingestion"),
):
    """Ingest regulatory documents into ChromaDB vector store"""
    console.print(Panel.fit(
        f"[bold]Regulatory Knowledge Base Ingestion[/bold]\n"
        f"Source: {source}\n"
        f"Force: {force}",
        title="📚 Ingesting Regulations",
        border_style="blue"
    ))
    
    # TODO: Implement actual ingestion
    console.print("[yellow]Ingestion not yet implemented. Run scripts/ingest_regulations.py[/yellow]")


@app.command()
def generate(
    profiles: int = typer.Option(20, "--count", "-c", help="Number of synthetic koperasi profiles to generate"),
    output: str = typer.Option("data/koperasi_profiles", "--output", "-o", help="Output directory"),
):
    """Generate synthetic koperasi profiles and documents"""
    console.print(Panel.fit(
        f"[bold]Synthetic Data Generation[/bold]\n"
        f"Profiles: {profiles}\n"
        f"Output: {output}",
        title="🏭 Generating Data",
        border_style="magenta"
    ))
    
    # TODO: Implement actual generation
    console.print("[yellow]Generation not yet implemented. Run scripts/generate_synthetic_docs.py[/yellow]")


@app.command()
def eval(
    test_set: str = typer.Option("all", "--test-set", "-t", help="Test set to run (all, doc_validation, rag_qa, e2e)"),
    output: str = typer.Option("evaluation/results", "--output", "-o", help="Output directory for results"),
):
    """Run evaluation suite"""
    console.print(Panel.fit(
        f"[bold]Evaluation Suite[/bold]\n"
        f"Test Set: {test_set}\n"
        f"Output: {output}",
        title="📊 Running Evaluation",
        border_style="cyan"
    ))
    
    # TODO: Implement actual evaluation
    console.print("[yellow]Evaluation not yet implemented. Run scripts/run_eval.py[/yellow]")


@app.command()
def serve(
    port: int = typer.Option(8501, "--port", "-p", help="Streamlit port"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Streamlit host"),
):
    """Launch Streamlit UI"""
    console.print(Panel.fit(
        f"[bold]Starting Streamlit UI[/bold]\n"
        f"URL: http://{host}:{port}",
        title="🌐 Web Interface",
        border_style="green"
    ))
    
    import subprocess
    subprocess.run(["streamlit", "run", "app/streamlit_app.py", "--server.port", str(port), "--server.address", host])


@app.command()
def status():
    """Show system status and configuration"""
    table = Table(title="⚙️ System Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("App Name", settings.APP_NAME)
    table.add_row("Version", settings.APP_VERSION)
    table.add_row("Debug Mode", str(settings.DEBUG))
    table.add_row("Log Level", settings.LOG_LEVEL)
    table.add_row("Data Directory", str(settings.DATA_DIR))
    table.add_row("LLM Model", settings.LLM_MODEL)
    table.add_row("Embedding Model", settings.EMBEDDING_MODEL)
    table.add_row("Reranker Model", settings.RERANKER_MODEL)
    table.add_row("ChromaDB Host", settings.CHROMA_HOST)
    table.add_row("Chunk Size", str(settings.CHUNK_SIZE))
    table.add_row("Top-K Retrieval", str(settings.TOP_K_RETRIEVAL))
    table.add_row("Top-K Rerank", str(settings.TOP_K_RERANK))
    table.add_row("Human Review Threshold", f"{settings.HUMAN_REVIEW_THRESHOLD}%")
    
    console.print(table)


if __name__ == "__main__":
    app()