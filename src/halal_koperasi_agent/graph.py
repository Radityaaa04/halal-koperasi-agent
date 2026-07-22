#!/usr/bin/env python3
"""
LangGraph StateGraph for HALAL Koperasi Multi-Agent System
5-Agent Pipeline: Document Intake -> Regulatory RAG -> Audit Simulation -> Decision Recommendation -> Communication
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from .state import ApplicationState, create_initial_state, update_progress, add_message, log_htl
from .schemas.documents import DocumentType
from .config import settings

# Import real agents
from .agents.document_intake import DocumentIntakeAgent
from .agents.regulatory_rag import RegulatoryRAGAgent
from .agents.audit_simulation import AuditSimulationAgent
from .agents.decision_recommendation import DecisionRecommendationAgent
from .agents.communication import CommunicationAgent


# Initialize agents (singleton pattern)
_document_intake_agent = None
_regulatory_rag_agent = None
_audit_simulation_agent = None
_decision_recommendation_agent = None
_communication_agent = None

def get_document_intake_agent() -> DocumentIntakeAgent:
    global _document_intake_agent
    if _document_intake_agent is None:
        _document_intake_agent = DocumentIntakeAgent()
    return _document_intake_agent

def get_regulatory_rag_agent() -> RegulatoryRAGAgent:
    global _regulatory_rag_agent
    if _regulatory_rag_agent is None:
        _regulatory_rag_agent = RegulatoryRAGAgent()
    return _regulatory_rag_agent

def get_audit_simulation_agent() -> AuditSimulationAgent:
    global _audit_simulation_agent
    if _audit_simulation_agent is None:
        _audit_simulation_agent = AuditSimulationAgent()
    return _audit_simulation_agent

def get_decision_recommendation_agent() -> DecisionRecommendationAgent:
    global _decision_recommendation_agent
    if _decision_recommendation_agent is None:
        _decision_recommendation_agent = DecisionRecommendationAgent()
    return _decision_recommendation_agent

def get_communication_agent() -> CommunicationAgent:
    global _communication_agent
    if _communication_agent is None:
        _communication_agent = CommunicationAgent()
    return _communication_agent


# ============================================================
# NODE 1: Document Intake Agent
# ============================================================

async def document_intake_node(state: ApplicationState) -> ApplicationState:
    """Document Intake Agent: Parse, validate, score all uploaded documents"""
    state = update_progress(state, "document_intake", 15.0)
    state = add_message(state, "assistant", "📄 Document Intake Agent: Processing uploaded documents...")
    
    agent = get_document_intake_agent()
    
    # For now, process synthetic documents from data/synthetic_docs/{koperasi_id}/
    # In production, this would process uploaded files from state["documents"]
    koperasi_id = state["application_id"].split("-")[0].lower()  # e.g., "kmbj"
    synthetic_dir = Path("data/synthetic_docs") / koperasi_id
    
    documents = {}
    doc_types = [
        DocumentType.NPWP,
        DocumentType.AKTA_PENDIRIAN,
        DocumentType.NIB,
        DocumentType.IZIN_USAHA,
        DocumentType.SOP_PRODUKSI,
        DocumentType.DAFTAR_BAHAN_BAKU,
        DocumentType.RUTE_PRODUKSI,
        DocumentType.SERTIFIKAT_HALAL_BAHAN,
        DocumentType.LAYOUT_FASILITAS,
        DocumentType.ORGANOGRAM_HAS,
        DocumentType.BUKTI_PELATIHAN_HAS,
    ]
    
    for doc_type in doc_types:
        pdf_path = synthetic_dir / f"{doc_type.value}.pdf"
        if pdf_path.exists():
            try:
                metadata = await agent.process_document(pdf_path, doc_type)
                documents[doc_type] = metadata
            except Exception as e:
                state = add_message(state, "assistant", f"⚠️ Failed to process {doc_type.value}: {e}")
    
    # Calculate overall completeness
    if documents:
        completeness_scores = [d.completeness_score for d in documents.values()]
        state["document_completeness_score"] = sum(completeness_scores) / len(completeness_scores)
    else:
        state["document_completeness_score"] = 0.0
    
    # Find missing required documents
    required_types = [dt for dt in DocumentType if dt != DocumentType.ANGGARAN_DASAR]
    missing = [dt for dt in required_types if dt not in documents]
    state["missing_required_docs"] = missing
    
    # Store documents for downstream agents
    state["documents"] = documents
    
    state = add_message(
        state, 
        "assistant", 
        f"✅ Document Intake complete: {len(documents)} docs processed, "
        f"completeness={state['document_completeness_score']:.0%}, "
        f"missing={len(missing)} required docs"
    )
    
    return state


# ============================================================
# NODE 2: Regulatory RAG Agent
# ============================================================

async def regulatory_rag_node(state: ApplicationState) -> ApplicationState:
    """Regulatory RAG Agent: Answer regulatory questions grounded in KB"""
    state = update_progress(state, "regulatory_review", 35.0)
    state = add_message(state, "assistant", "📚 Regulatory RAG Agent: Retrieving relevant regulations...")
    
    agent = get_regulatory_rag_agent()
    await agent.initialize()
    
    # Generate auto-questions based on missing documents & products
    auto_questions = await agent.generate_auto_questions({
        "missing_required_docs": state.get("missing_required_docs", []),
        "produk_utama": state.get("produk_utama", []),
    })
    
    # Also answer specific questions
    questions = auto_questions + [
        "Apa syarat sertifikat halal untuk koperasi mikro/kecil?",
        "Bagaimana prosedur segregasi area halal dan non-halal di fasilitas produksi ikan?",
        "Apa sanksi jika Ketua HAS tidak memiliki sertifikat pelatihan valid?",
    ]
    
    rag_answers = []
    for q in questions[:5]:  # Limit to 5 questions for speed
        try:
            ans = await agent.answer_question(q)
            rag_answers.append(ans)
        except Exception as e:
            state = add_message(state, "assistant", f"⚠️ RAG error for '{q[:50]}...': {e}")
    
    state["regulatory_questions"] = questions
    state["rag_answers"] = rag_answers
    
    state = add_message(
        state, 
        "assistant", 
        f"✅ Regulatory RAG complete: {len(rag_answers)} questions answered, "
        f"avg confidence={sum(a.confidence for a in rag_answers)/len(rag_answers):.0%}" if rag_answers else "No answers"
    )
    
    return state


# ============================================================
# NODE 3: Audit Simulation Agent
# ============================================================

async def audit_simulation_node(state: ApplicationState) -> ApplicationState:
    """Audit Simulation Agent: Run 81-item LPH audit checklist, find gaps, score readiness"""
    state = update_progress(state, "audit_simulation", 60.0)
    state = add_message(state, "assistant", "🔍 Audit Simulation Agent: Running LPH audit checklist...")
    
    agent = get_audit_simulation_agent()
    await agent.initialize()
    
    # Run audit with processed documents
    documents = state.get("documents", {})
    result = await agent.run_audit(
        application_id=state["application_id"],
        koperasi_nama=state["koperasi_name"],
        documents=documents,
    )
    
    state["audit_result"] = result
    
    state = add_message(
        state, 
        "assistant", 
        f"✅ Audit Simulation complete: Score={result.overall_readiness_score:.1f}%, "
        f"Recommendation={result.submission_recommendation}, "
        f"Critical gaps={len(result.critical_gaps)}, High priority={len(result.high_priority_gaps)}"
    )
    
    return state


# ============================================================
# NODE 4: Decision Recommendation Agent (NEW - 5th agent)
# ============================================================

async def decision_recommendation_node(state: ApplicationState) -> ApplicationState:
    """Decision Recommendation Agent: Synthesize all outputs, make final certification decision"""
    state = update_progress(state, "decision_recommendation", 80.0)
    state = add_message(state, "assistant", "⚖️ Decision Recommendation Agent: Synthesizing all findings...")
    
    agent = get_decision_recommendation_agent()
    await agent.initialize()
    
    documents = state.get("documents", {})
    missing_required_docs = state.get("missing_required_docs", [])
    audit_result = state.get("audit_result")
    rag_answers = state.get("rag_answers", [])
    
    if not audit_result:
        state = add_message(state, "assistant", "⚠️ No audit result available, skipping decision")
        return state
    
    # Make final recommendation
    decision = agent.make_recommendation(
        application_id=state["application_id"],
        koperasi_nama=state["koperasi_name"],
        document_completeness=state.get("document_completeness_score", 0.0),
        missing_docs=missing_required_docs,
        audit_result=audit_result,
        rag_answers=rag_answers,
        documents=documents,
    )
    
    state["decision"] = decision
    
    # Update status based on recommendation
    rec = decision["recommendation"]
    if rec == "CERTIFY":
        state["status"] = "READY_FOR_SUBMISSION"
    elif rec == "CONDITIONAL_CERTIFY":
        state["status"] = "CONDITIONAL_APPROVAL"
    elif rec == "NEEDS_MORE_INFO":
        state["status"] = "DOCUMENT_INTAKE"  # Loop back
    else:  # REJECT
        state["status"] = "REJECTED"
    
    state = add_message(
        state, 
        "assistant", 
        f"✅ Decision: {decision['recommendation']} (Confidence: {decision['confidence']:.0%}, "
        f"Risk: {decision['risk_level']}, Score: {decision['weighted_score']:.1f})"
    )
    
    return state


# ============================================================
# NODE 5: Communication Agent
# ============================================================

async def communication_node(state: ApplicationState) -> ApplicationState:
    """Communication Agent: Generate PDF report, Excel checklist, Executive brief"""
    state = update_progress(state, "communication", 95.0)
    state = add_message(state, "assistant", "📝 Communication Agent: Generating final reports...")
    
    agent = get_communication_agent()
    
    documents = state.get("documents", {})
    audit_result = state.get("audit_result")
    rag_answers = state.get("rag_answers", [])
    decision = state.get("decision", {})
    
    if not audit_result:
        state = add_message(state, "assistant", "⚠️ No audit result, skipping report generation")
        return state
    
    output_dir = Path(f"output/{state['application_id']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate all reports
    reports = agent.generate_all_reports(
        result=audit_result,
        documents=documents,
        rag_answers=rag_answers,
        output_dir=output_dir,
    )
    
    # Also generate executive brief if decision exists
    if decision:
        brief_path = output_dir / f"executive_brief_{state['application_id']}.md"
        decision_agent = get_decision_recommendation_agent()
        await decision_agent.generate_executive_brief(decision, brief_path)
        reports["executive_brief"] = brief_path
    
    state["communication_output"] = reports
    
    state = add_message(
        state, 
        "assistant", 
        f"✅ Communication complete: PDF={reports.get('pdf', 'N/A')}, "
        f"Excel={reports.get('excel', 'N/A')}, Brief={reports.get('executive_brief', 'N/A')}"
    )
    
    return state


# ============================================================
# HUMAN REVIEW NODE (Conditional)
# ============================================================

async def human_review_node(state: ApplicationState) -> ApplicationState:
    """Human-in-the-loop checkpoint for low readiness or critical gaps"""
    audit = state.get("audit_result")
    decision = state.get("decision")
    
    needs_review = (
        audit and (
            audit.overall_readiness_score < settings.HUMAN_REVIEW_THRESHOLD or
            len(audit.critical_gaps) > settings.CRITICAL_GAPS_THRESHOLD
        )
    )
    
    if decision:
        # Also trigger if decision recommends conditional or needs more info
        needs_review = needs_review or decision.get("recommendation") in [
            "CONDITIONAL_CERTIFY", "NEEDS_MORE_INFO"
        ]
    
    # Bypass human review interrupt for automated runs (config flag)
    bypass_review = state.get("bypass_human_review", False)
    
    if needs_review and not bypass_review:
        state["pending_human_review"] = True
        state["human_review_checkpoint"] = "post_audit"
        
        audit_summary = {
            "readiness_score": audit.overall_readiness_score if audit else 0,
            "critical_gaps": audit.critical_gaps if audit else [],
            "recommendation": audit.submission_recommendation if audit else "UNKNOWN",
            "decision_recommendation": decision.get("recommendation") if decision else "UNKNOWN",
            "decision_risk": decision.get("risk_level") if decision else "UNKNOWN",
        }
        
        state = add_message(
            state, 
            "assistant", 
            f"⚠️ Human review required: {audit_summary['recommendation']} (score: {audit_summary['readiness_score']:.1f}%)"
        )
        
        # Interrupt for human input
        human_input = interrupt({
            "message": (
                f"Audit Score: {audit_summary['readiness_score']:.1f}%\n"
                f"Decision: {audit_summary['decision_recommendation']}\n"
                f"Risk Level: {audit_summary['decision_risk']}\n"
                f"Critical Gaps: {len(audit_summary['critical_gaps'])}\n\n"
                "Provide action: APPROVE / REQUEST_FIXES / REJECT"
            ),
            "audit_summary": audit_summary,
        })
        
        # Log human action
        state = log_htl(
            state,
            step="human_review_post_audit",
            agent="human_reviewer",
            input_summary=f"Audit score: {audit_summary['readiness_score']:.1f}%",
            output_summary=f"Human action: {human_input.get('action', 'UNKNOWN')}",
            confidence=1.0,
            human_action=human_input.get("action"),
            human_feedback=human_input.get("feedback"),
        )
        
        action = human_input.get("action", "REQUEST_FIXES")
        if action == "APPROVE":
            state["status"] = "READY_FOR_SUBMISSION"
        elif action == "REJECT":
            state["status"] = "REJECTED"
        else:  # REQUEST_FIXES
            state["status"] = "DOCUMENT_INTAKE"
            state["current_step"] = "document_intake"
    else:
        state["pending_human_review"] = False
        if state.get("status") != "REJECTED":
            state["status"] = "READY_FOR_SUBMISSION"
    
    return state


def should_continue_to_human_review(state: ApplicationState) -> str:
    """Conditional edge: route to human review if needed"""
    audit = state.get("audit_result")
    decision = state.get("decision")
    
    needs_review = False
    if audit:
        needs_review = (
            audit.overall_readiness_score < settings.HUMAN_REVIEW_THRESHOLD or
            len(audit.critical_gaps) > settings.CRITICAL_GAPS_THRESHOLD
        )
    if decision:
        needs_review = needs_review or decision.get("recommendation") in [
            "CONDITIONAL_CERTIFY", "NEEDS_MORE_INFO"
        ]
    
    return "human_review" if needs_review else "communication"


def should_loop_back(state: ApplicationState) -> str:
    """After human review: loop to document intake if fixes requested, else communication for reports, then end"""
    return "document_intake" if state.get("status") == "DOCUMENT_INTAKE" else "communication"


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph():
    """Construct the LangGraph StateGraph with 5 agents"""
    workflow = StateGraph(ApplicationState)
    
    # Add all 5 agent nodes + human review
    workflow.add_node("document_intake", document_intake_node)
    workflow.add_node("regulatory_rag", regulatory_rag_node)
    workflow.add_node("audit_simulation", audit_simulation_node)
    workflow.add_node("decision_recommendation", decision_recommendation_node)
    workflow.add_node("communication", communication_node)
    workflow.add_node("human_review", human_review_node)
    
    # Entry point
    workflow.set_entry_point("document_intake")
    
    # Linear pipeline
    workflow.add_edge("document_intake", "regulatory_rag")
    workflow.add_edge("regulatory_rag", "audit_simulation")
    workflow.add_edge("audit_simulation", "decision_recommendation")
    
    # Conditional: human review or communication
    workflow.add_conditional_edges(
        "decision_recommendation",
        should_continue_to_human_review,
        {
            "human_review": "human_review",
            "communication": "communication"
        }
    )
    
    # Human review: loop back or end
    workflow.add_conditional_edges(
        "human_review",
        should_loop_back,
        {
            "document_intake": "document_intake",
            "communication": "communication",
        }
    )
    
    # Communication ends
    workflow.add_edge("communication", END)
    
    # Compile with checkpointer
    checkpointer = InMemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app


# Create the compiled graph
graph = build_graph()


# ============================================================
# RUN HELPER
# ============================================================

async def run_application(
    application_id: str,
    koperasi_name: str,
    koperasi_location: str,
    produk_utama: list,
    thread_id: str = None,
    bypass_human_review: bool = True  # For automated test runs
):
    """Run the full application workflow"""
    if thread_id is None:
        thread_id = application_id
    
    initial_state = create_initial_state(
        application_id=application_id,
        koperasi_name=koperasi_name,
        koperasi_location=koperasi_location,
        produk_utama=produk_utama
    )
    
    # Add bypass flag for automated runs
    initial_state["bypass_human_review"] = bypass_human_review
    
    config = {"configurable": {"thread_id": thread_id}}
    
    async for event in graph.astream(initial_state, config=config):
        yield event


if __name__ == "__main__":
    print("Graph nodes:", list(graph.nodes.keys()))
    print("Graph compiled successfully!")