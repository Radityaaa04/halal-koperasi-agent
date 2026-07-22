#!/usr/bin/env python3
"""
Decision Recommendation Agent for HALAL Koperasi Multi-Agent System
Synthesizes all agent outputs and provides final certification recommendation.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from halal_koperasi_agent.config import settings
from halal_koperasi_agent.schemas.audit import (
    AuditCategory,
    AuditFinding,
    AuditSimulationResult,
    PriorityAction,
)
from halal_koperasi_agent.schemas.documents import DocumentMetadata, DocumentType, DocumentStatus
from halal_koperasi_agent.schemas.regulatory import RAGAnswer
from halal_koperasi_agent.schemas.application import ApplicationStatus
from halal_koperasi_agent.llm_providers import chat_completion, ChatMessage


class DecisionRecommendationAgent:
    """
    Agent responsible for:
    1. Synthesizing outputs from Document Intake, Regulatory RAG, Audit Simulation
    2. Making final certification recommendation with confidence
    3. Generating executive decision brief
    4. Providing risk assessment and mitigation strategies
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing Decision Recommendation Agent...")
        self._initialized = True
        logger.success("Decision Recommendation Agent initialized")

    def make_recommendation(
        self,
        application_id: str,
        koperasi_nama: str,
        document_completeness: float,
        missing_docs: List[DocumentType],
        audit_result: AuditSimulationResult,
        rag_answers: List[RAGAnswer],
        documents: Dict[DocumentType, DocumentMetadata],
    ) -> Dict[str, Any]:
        """
        Make final certification recommendation based on all agent outputs.
        
        Returns comprehensive decision object with:
        - recommendation: CERTIFY / CONDITIONAL_CERTIFY / REJECT / NEEDS_MORE_INFO
        - confidence: 0.0 - 1.0
        - risk_level: LOW / MEDIUM / HIGH / CRITICAL
        - conditions: List of conditions if conditional
        - rationale: Detailed reasoning
        """
        
        # Factor 1: Document completeness (weight: 25%)
        doc_score = document_completeness * 100
        
        # Factor 2: Audit readiness (weight: 50%)
        audit_score = audit_result.overall_readiness_score
        
        # Factor 3: Critical gaps (weight: 25% - negative impact)
        critical_gap_count = len(audit_result.critical_gaps)
        high_priority_gap_count = len(audit_result.high_priority_gaps)
        
        # Calculate weighted score
        weighted_score = (
            doc_score * 0.25 +
            audit_score * 0.50 +
            max(0, 100 - (critical_gap_count * 15) - (high_priority_gap_count * 8)) * 0.25
        )
        
        # Determine recommendation
        if weighted_score >= 85 and critical_gap_count == 0:
            recommendation = "CERTIFY"
            confidence = min(0.95, 0.7 + (weighted_score - 85) / 100)
            risk_level = "LOW"
        elif weighted_score >= 70 and critical_gap_count <= 1:
            recommendation = "CONDITIONAL_CERTIFY"
            confidence = min(0.85, 0.6 + (weighted_score - 70) / 100)
            risk_level = "MEDIUM"
        elif weighted_score >= 50 and critical_gap_count <= 3:
            recommendation = "NEEDS_MORE_INFO"
            confidence = 0.6
            risk_level = "HIGH"
        else:
            recommendation = "REJECT"
            confidence = min(0.9, 0.5 + (50 - weighted_score) / 100)
            risk_level = "CRITICAL"
        
        # Override for specific critical conditions
        critical_overrides = self._check_critical_overrides(audit_result, missing_docs)
        if critical_overrides:
            recommendation = critical_overrides["recommendation"]
            confidence = critical_overrides["confidence"]
            risk_level = critical_overrides["risk_level"]
        
        # Generate conditions for conditional certification
        conditions = self._generate_conditions(
            recommendation, audit_result, missing_docs, documents
        )
        
        # Generate rationale
        rationale = self._generate_rationale(
            recommendation, weighted_score, doc_score, audit_score,
            critical_gap_count, high_priority_gap_count, audit_result, missing_docs
        )
        
        # Risk mitigation strategies
        mitigations = self._generate_mitigations(audit_result, risk_level)
        
        # Timeline estimation
        timeline = self._estimate_timeline(recommendation, audit_result)
        
        decision = {
            "application_id": application_id,
            "koperasi_nama": koperasi_nama,
            "decision_timestamp": datetime.now().isoformat(),
            "agent_version": "1.0",
            
            # Core decision
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
            "risk_level": risk_level,
            "weighted_score": round(weighted_score, 1),
            
            # Score breakdown
            "score_breakdown": {
                "document_completeness": round(doc_score, 1),
                "audit_readiness": round(audit_score, 1),
                "gap_penalty": round(max(0, 100 - (critical_gap_count * 15) - (high_priority_gap_count * 8)), 1),
                "weighted_total": round(weighted_score, 1),
            },
            
            # Conditions & requirements
            "conditions": conditions,
            "mandatory_requirements_met": self._check_mandatory_requirements(audit_result, missing_docs),
            
            # Rationale & analysis
            "rationale": rationale,
            "risk_mitigations": mitigations,
            
            # Timeline & next steps
            "timeline": timeline,
            "next_steps": self._generate_next_steps(recommendation, audit_result, conditions),
            
            # Supporting evidence
            "supporting_evidence": {
                "total_documents": len(documents),
                "validated_documents": sum(1 for d in documents.values() if d.status == DocumentStatus.VALIDATED),
                "total_findings": len(audit_result.findings),
                "passed_findings": audit_result.passed,
                "failed_findings": audit_result.failed,
                "warning_findings": audit_result.warnings,
                "critical_gaps": critical_gap_count,
                "high_priority_gaps": high_priority_gap_count,
                "regulatory_questions_answered": len(rag_answers),
            },
        }
        
        logger.success(
            f"Decision: {recommendation} (confidence: {confidence:.0%}, "
            f"risk: {risk_level}, score: {weighted_score:.1f})"
        )
        
        return decision

    def _check_critical_overrides(
        self,
        audit_result: AuditSimulationResult,
        missing_docs: List[DocumentType],
    ) -> Optional[Dict[str, Any]]:
        """Check for conditions that force specific recommendations"""
        
        # Mandatory docs missing
        mandatory_missing = [
            d for d in missing_docs 
            if d in [DocumentType.AKTA_PENDIRIAN, DocumentType.NPWP, DocumentType.NIB]
        ]
        if mandatory_missing:
            return {
                "recommendation": "REJECT",
                "confidence": 0.95,
                "risk_level": "CRITICAL",
                "reason": f"Mandatory documents missing: {[d.value for d in mandatory_missing]}",
            }
        
        # Critical HAS failure
        has_failures = [
            f for f in audit_result.findings
            if f.category == AuditCategory.HAS and f.status == "FAIL" and f.severity == "CRITICAL"
        ]
        if len(has_failures) >= 2:
            return {
                "recommendation": "REJECT",
                "confidence": 0.9,
                "risk_level": "CRITICAL",
                "reason": f"Multiple critical HAS failures: {len(has_failures)}",
            }
        
        # No HAS structure at all
        has_passed = [
            f for f in audit_result.findings
            if f.category == AuditCategory.HAS and f.status == "PASS"
        ]
        if len(has_passed) == 0 and audit_result.total_checks > 0:
            return {
                "recommendation": "NEEDS_MORE_INFO",
                "confidence": 0.8,
                "risk_level": "HIGH",
                "reason": "HAS structure not established",
            }
        
        # Expired halal certificates for raw materials
        expired_certs = [
            f for f in audit_result.findings
            if f.category == AuditCategory.BAHAN_BAKU 
            and f.status == "FAIL" 
            and "expired" in f.gap_description.lower()
        ]
        if len(expired_certs) >= 3:
            return {
                "recommendation": "NEEDS_MORE_INFO",
                "confidence": 0.75,
                "risk_level": "HIGH",
                "reason": f"{len(expired_certs)} bahan baku dengan sertifikat halal expired",
            }
        
        return None

    def _generate_conditions(
        self,
        recommendation: str,
        audit_result: AuditSimulationResult,
        missing_docs: List[DocumentType],
        documents: Dict[DocumentType, DocumentMetadata],
    ) -> List[Dict[str, Any]]:
        """Generate conditions for conditional certification or pre-requisites"""
        conditions = []
        
        # Always include critical gaps as conditions
        for gap in audit_result.critical_gaps[:10]:
            conditions.append({
                "type": "CRITICAL_GAP",
                "description": gap,
                "priority": "CRITICAL",
                "deadline_days": 14,
                "verification": "Dokumen pendukung + verifikasi LPH",
            })
        
        # High priority gaps
        for gap in audit_result.high_priority_gaps[:5]:
            conditions.append({
                "type": "HIGH_PRIORITY",
                "description": gap,
                "priority": "HIGH",
                "deadline_days": 30,
                "verification": "Review dokumen + audit internal",
            })
        
        # Missing mandatory documents
        for doc in missing_docs:
            if doc in [DocumentType.AKTA_PENDIRIAN, DocumentType.NPWP, DocumentType.NIB]:
                conditions.append({
                    "type": "MANDATORY_DOCUMENT",
                    "description": f"Dokumen wajib hilang: {doc.value}",
                    "priority": "CRITICAL",
                    "deadline_days": 7,
                    "verification": "Submit dokumen asli + fotokopi legalisir",
                })
        
        # Warning findings that need attention
        warning_findings = [
            f for f in audit_result.findings
            if f.status == "WARNING" and f.severity in ["MEDIUM", "HIGH"]
        ][:5]
        for wf in warning_findings:
            conditions.append({
                "type": "WARNING_RESOLUTION",
                "description": f"{wf.checklist_item}: {wf.gap_description}",
                "priority": "MEDIUM",
                "deadline_days": 21,
                "verification": "Perbaikan dokumen + verifikasi ulang",
            })
        
        # Recommendation-specific conditions
        if recommendation == "CONDITIONAL_CERTIFY":
            conditions.append({
                "type": "POST_CERTIFICATION",
                "description": "Audit surveillance 6 bulan pasca sertifikasi",
                "priority": "HIGH",
                "deadline_days": 180,
                "verification": "LPH melakukan audit surveillance",
            })
            conditions.append({
                "type": "POST_CERTIFICATION",
                "description": "Laporan progress perbaikan bulanan",
                "priority": "MEDIUM",
                "deadline_days": 30,
                "verification": "Submit ke BPJPH melalui SEHATI",
            })
        
        return conditions

    def _generate_rationale(
        self,
        recommendation: str,
        weighted_score: float,
        doc_score: float,
        audit_score: float,
        critical_gaps: int,
        high_priority_gaps: int,
        audit_result: AuditSimulationResult,
        missing_docs: List[DocumentType],
    ) -> str:
        """Generate detailed rationale for the decision"""
        
        rationale_parts = []
        
        rationale_parts.append(
            f"KEPUTUSAN: {recommendation} dengan confidence {weighted_score:.1f}/100."
        )
        
        rationale_parts.append(
            f"ANALISIS SKOR: "
            f"Kelengkapan dokumen {doc_score:.0f}% (bobot 25%), "
            f"Kesiapan audit {audit_score:.1f}% (bobot 50%), "
            f"Penalti gap {max(0, 100 - critical_gaps * 15 - high_priority_gaps * 8):.0f}% (bobot 25%). "
            f"Total tertimbang: {weighted_score:.1f}%."
        )
        
        if missing_docs:
            rationale_parts.append(
                f"DOKUMEN HILANG: {len(missing_docs)} dokumen tidak disediakan: "
                f"{', '.join([d.value for d in missing_docs])}."
            )
        
        if critical_gaps > 0:
            rationale_parts.append(
                f"GAP KRITIS: {critical_gaps} item checklist gagal dengan severity CRITICAL. "
                f"Ini termasuk: {', '.join(audit_result.critical_gaps[:3])}."
            )
        
        if audit_result.passed > 0:
            rationale_parts.append(
                f"KEKUATAN: {audit_result.passed} item checklist LULUS, "
                f"termasuk kategori Administrasi ({audit_result.category_scores.get('A. Persyaratan Administrasi', 0):.0f}%)."
            )
        
        if audit_result.category_scores:
            weakest = min(audit_result.category_scores.items(), key=lambda x: x[1])
            rationale_parts.append(
                f"KELEMAHAN UTAMA: Kategori '{weakest[0]}' skor terendah ({weakest[1]:.0f}%)."
            )
        
        # Recommendation-specific rationale
        if recommendation == "CERTIFY":
            rationale_parts.append(
                "REKOMENDASI: Koperasi memenuhi syarat sertifikasi halal. "
                "Direkomendasikan untuk proses sertifikasi penuh via SEHATI BPJPH."
            )
        elif recommendation == "CONDITIONAL_CERTIFY":
            rationale_parts.append(
                "REKOMENDASI: Sertifikasi bersyarat. Koperasi memenuhi mayoritas syarat "
                "namun perlu menyelesaikan kondisi dalam jangka waktu ditentukan. "
                "Audit surveillance 6 bulan wajib."
            )
        elif recommendation == "NEEDS_MORE_INFO":
            rationale_parts.append(
                "REKOMENDASI: Belum siap sertifikasi. Perlu melengkapi dokumen & perbaikan gap "
                "sebelum mengajukan ulang. Estimasi perbaikan: 30-60 hari."
            )
        else:
            rationale_parts.append(
                "REKOMENDASI: Ditolak. Gap fundamental terlalu besar. "
                "Perlukan restrukturisasi HAS & lengkapi dokumen fundamental sebelum re-apply."
            )
        
        return " ".join(rationale_parts)

    def _generate_mitigations(
        self,
        audit_result: AuditSimulationResult,
        risk_level: str,
    ) -> List[Dict[str, Any]]:
        """Generate risk mitigation strategies"""
        mitigations = []
        
        # Per category
        for cat in AuditCategory:
            cat_findings = [f for f in audit_result.findings if f.category == cat]
            failed = [f for f in cat_findings if f.status == "FAIL"]
            if failed:
                mitigations.append({
                    "category": cat.value,
                    "risk": f"{len(failed)} item gagal dalam kategori ini",
                    "mitigation": f"Prioritaskan perbaikan: {', '.join([f.checklist_item for f in failed[:2]])}",
                    "timeline": "14-30 hari",
                    "owner": "Manajemen HAS / Ketua Koperasi",
                })
        
        # General mitigations based on risk level
        if risk_level in ["HIGH", "CRITICAL"]:
            mitigations.extend([
                {
                    "category": "STRATEGIC",
                    "risk": "Tidak lolos sertifikasi → kerugian pasar & reputasi",
                    "mitigation": "Bentuk tim task force sertifikasi halal dengan timeline ketat",
                    "timeline": "7 hari",
                    "owner": "Ketua Koperasi",
                },
                {
                    "category": "STRATEGIC", 
                    "risk": "Ketua HAS tidak bersertifikat → audit gagal",
                    "mitigation": "Daftarkan Ketua HAS ke program pelatihan BPJPH/LPH terdekat",
                    "timeline": "30 hari",
                    "owner": "Ketua Koperasi / Manajemen SDM",
                },
            ])
        
        return mitigations

    def _estimate_timeline(
        self,
        recommendation: str,
        audit_result: AuditSimulationResult,
    ) -> Dict[str, Any]:
        """Estimate timeline to certification"""
        
        if recommendation == "CERTIFY":
            return {
                "to_application": "1-2 minggu",
                "to_audit": "2-4 minggu",
                "to_certificate": "8-12 minggu",
                "total_estimate_weeks": 10,
            }
        elif recommendation == "CONDITIONAL_CERTIFY":
            return {
                "to_pre_conditions": "2-4 minggu",
                "to_application": "1-2 minggu",
                "to_conditional_audit": "4-6 minggu",
                "to_certificate": "12-16 minggu",
                "surveillance_due": "6 bulan pasca sertifikat",
                "total_estimate_weeks": 14,
            }
        elif recommendation == "NEEDS_MORE_INFO":
            return {
                "gap_resolution": f"{audit_result.estimated_time_to_fix_days} hari",
                "re_application": "2 minggu setelah gap terpenuhi",
                "to_certificate": "12-16 minggu dari re-apply",
                "total_estimate_weeks": max(16, audit_result.estimated_time_to_fix_days // 7 + 12),
            }
        else:  # REJECT
            return {
                "restructuring_required": "8-12 minggu",
                "gap_resolution": f"{max(60, audit_result.estimated_time_to_fix_days)} hari",
                "re_application": "Setelah restructuring selesai",
                "total_estimate_weeks": 24,
            }

    def _check_mandatory_requirements(
        self,
        audit_result: AuditSimulationResult,
        missing_docs: List[DocumentType],
    ) -> Dict[str, bool]:
        """Check which mandatory requirements are met"""
        mandatory_checks = {
            "akta_pendirian": DocumentType.AKTA_PENDIRIAN not in missing_docs,
            "npwp": DocumentType.NPWP not in missing_docs,
            "nib": DocumentType.NIB not in missing_docs,
            "has_structure": any(
                f.status == "PASS" for f in audit_result.findings 
                if f.category == AuditCategory.HAS
            ),
            "bahan_baku_halal": any(
                f.status == "PASS" for f in audit_result.findings
                if f.category == AuditCategory.BAHAN_BAKU
            ),
            "segregation_fasilitas": any(
                f.status == "PASS" for f in audit_result.findings
                if f.category == AuditCategory.FASILITAS
            ),
            "labeling_compliance": any(
                f.status == "PASS" for f in audit_result.findings
                if f.category == AuditCategory.KEMASAN
            ),
        }
        return mandatory_checks

    def _generate_next_steps(
        self,
        recommendation: str,
        audit_result: AuditSimulationResult,
        conditions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate actionable next steps"""
        
        steps = []
        
        if recommendation == "CERTIFY":
            steps = [
                {"step": 1, "action": "Ajukan sertifikasi via SEHATI BPJPH", "owner": "Ketua Koperasi", "deadline": "1 minggu"},
                {"step": 2, "action": "Persiapkan dokumen untuk audit LPH", "owner": "Tim HAS", "deadline": "2 minggu"},
                {"step": 3, "action": "Koordinasi jadwal audit dengan LPH", "owner": "Ketua HAS", "deadline": "3 minggu"},
                {"step": 4, "action": "Lakukan audit LPH", "owner": "LPH", "deadline": "8-12 minggu"},
                {"step": 5, "action": "Terima sertifikat halal", "owner": "Koperasi", "deadline": "12 minggu"},
            ]
        elif recommendation == "CONDITIONAL_CERTIFY":
            steps = [
                {"step": 1, "action": "Selesaikan semua kondisi CRITICAL", "owner": "Tim HAS", "deadline": "14 hari"},
                {"step": 2, "action": "Dokumentasikan bukti perbaikan", "owner": "Ketua HAS", "deadline": "21 hari"},
                {"step": 3, "action": "Ajukan sertifikasi bersyarat via SEHATI", "owner": "Ketua Koperasi", "deadline": "1 bulan"},
                {"step": 4, "action": "Audit LPH dengan catatan kondisi", "owner": "LPH", "deadline": "2-3 bulan"},
                {"step": 5, "action": "Terima sertifikat bersyarat", "owner": "Koperasi", "deadline": "3-4 bulan"},
                {"step": 6, "action": "Audit surveillance 6 bulan", "owner": "LPH", "deadline": "6 bulan pasca sertifikat"},
            ]
        elif recommendation == "NEEDS_MORE_INFO":
            steps = [
                {"step": 1, "action": "Fokus perbaikan GAP KRITIS", "owner": "Tim HAS", "deadline": "14 hari"},
                {"step": 2, "action": "Lengkapi dokumen wajib yang hilang", "owner": "Manajemen Admin", "deadline": "7 hari"},
                {"step": 3, "action": "Perbaiki GAP HIGH PRIORITY", "owner": "Tim Teknis", "deadline": "30 hari"},
                {"step": 4, "action": "Internal audit verifikasi perbaikan", "owner": "Ketua HAS", "deadline": "45 hari"},
                {"step": 5, "action": "Re-apply sertifikasi", "owner": "Ketua Koperasi", "deadline": "60 hari"},
            ]
        else:  # REJECT
            steps = [
                {"step": 1, "action": "Evaluasi ulang struktur HAS & SDM", "owner": "Ketua Koperasi", "deadline": "2 minggu"},
                {"step": 2, "action": "Rekrut/pelatihi Ketua HAS baru", "owner": "Manajemen SDM", "deadline": "30 hari"},
                {"step": 3, "action": "Bangun sistem HAS dari nol", "owner": "Tim HAS", "deadline": "60 hari"},
                {"step": 4, "action": "Lengkapi semua dokumen fundamental", "owner": "Admin", "deadline": "14 hari"},
                {"step": 5, "action": "Internal audit menyeluruh", "owner": "Audit Internal", "deadline": "75 hari"},
                {"step": 6, "action": "Re-apply setelah restructuring", "owner": "Ketua Koperasi", "deadline": "90 hari"},
            ]
        
        return steps

    async def generate_executive_brief(
        self,
        decision: Dict[str, Any],
        output_path: Path,
    ) -> Path:
        """Generate 1-page executive brief for decision makers"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        brief = f"""# EXECUTIVE BRIEF: REKOMENDASI SERTIFIKASI HALAL
**{decision['koperasi_nama']}** | Application ID: {decision['application_id']}  
**Tanggal:** {datetime.now().strftime('%d %B %Y')} | **Versi Agent:** {decision['agent_version']}

---

## 🎯 KEPUTUSAN UTAMA
**{decision['recommendation']}** (Confidence: {decision['confidence']:.0%} | Risk: {decision['risk_level']} | Score: {decision['weighted_score']:.1f}/100)

---

## 📊 SCORE BREAKDOWN
| Komponen | Skor | Bobot | Kontribusi |
|----------|------|-------|------------|
| Kelengkapan Dokumen | {decision['score_breakdown']['document_completeness']:.0f}% | 25% | {decision['score_breakdown']['document_completeness']*0.25:.1f} |
| Kesiapan Audit | {decision['score_breakdown']['audit_readiness']:.1f}% | 50% | {decision['score_breakdown']['audit_readiness']*0.5:.1f} |
| Penalti Gap | {decision['score_breakdown']['gap_penalty']:.0f}% | 25% | {decision['score_breakdown']['gap_penalty']*0.25:.1f} |
| **TOTAL** | | | **{decision['weighted_score']:.1f}** |

---

## ✅ SYARAT WAJIB TERPENUHI
{self._format_mandatory(decision['mandatory_requirements_met'])}

---

## ⚠️ GAP KRITIS ({len(decision['conditions']) if decision['conditions'] else 0} item)
{self._format_conditions(decision['conditions'][:5])}

---

## 📋 NEXT STEPS PRIORITAS
{self._format_next_steps(decision['next_steps'][:5])}

---

## 💰 ESTIMASI BIAYA & WAKTU
- **Timeline:** {decision['timeline'].get('to_certificate', decision['timeline'].get('total_estimate_weeks', 'N/A'))} minggu
- **Biaya perbaikan:** {decision['conditions'][0].get('estimated_cost', 'Rp 0 - Rp 50 Juta') if decision['conditions'] else 'TBD'}
- **Audit surveillance:** {'Ya (6 bln)' if decision['recommendation'] == 'CONDITIONAL_CERTIFY' else 'Tidak'}

---

## 📝 RATIONALE
{decision['rationale']}

---
*Generated by HALAL Koperasi Multi-Agent System v{decision['agent_version']}*
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(brief)
        
        logger.success(f"Executive brief generated: {output_path}")
        return output_path

    def _format_mandatory(self, mandatory: Dict[str, bool]) -> str:
        lines = []
        for key, met in mandatory.items():
            status = "✅" if met else "❌"
            lines.append(f"- {status} {key.replace('_', ' ').title()}")
        return "\n".join(lines) if lines else "- Tidak ada data"

    def _format_conditions(self, conditions: List[Dict[str, Any]]) -> str:
        if not conditions:
            return "- Tidak ada gap kritis"
        lines = []
        for c in conditions:
            lines.append(f"- **{c['priority']}**: {c['description']} (deadline: {c['deadline_days']} hari)")
        return "\n".join(lines)

    def _format_next_steps(self, steps: List[Dict[str, Any]]) -> str:
        if not steps:
            return "- Tidak ada next steps"
        lines = []
        for s in steps:
            lines.append(f"{s['step']}. {s['action']} — *{s['owner']}* ({s['deadline']})")
        return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    import sys
    from halal_koperasi_agent.schemas.audit import AuditCategory, AuditSimulationResult
    from halal_koperasi_agent.schemas.documents import DocumentType, DocumentStatus
    from halal_koperasi_agent.schemas.audit import AuditFinding, PriorityAction
    
    async def test():
        agent = DecisionRecommendationAgent()
        await agent.initialize()
        
        # Mock audit result
        mock_audit = AuditSimulationResult(
            application_id="TEST-001",
            koperasi_nama="Koperasi Test",
            overall_readiness_score=65.0,
            total_checks=81,
            passed=30,
            failed=20,
            warnings=15,
            not_applicable=16,
            pending=0,
            findings=[
                AuditFinding(
                    checklist_item_id="B01",
                    checklist_item="Ketua HAS Terpenuhi",
                    category=AuditCategory.HAS,
                    requirement_source="BPJPH Peraturan 1/2023",
                    status="FAIL",
                    evidence_found="ORGANOGRAM_HAS.pdf (77%)",
                    evidence_expected="Sertifikat pelatihan",
                    gap_description="Ketua HAS tidak memiliki sertifikat pelatihan valid",
                    recommended_action="Daftarkan ke pelatihan BPJPH",
                    severity="CRITICAL",
                    auto_fixable=False,
                    estimated_fix_days=30,
                    responsible_party="Ketua Koperasi",
                    regulatory_citations=[],
                    agent_reasoning="Mandatory",
                ),
            ],
            critical_gaps=["Ketua HAS tidak memiliki sertifikat pelatihan valid"],
            high_priority_gaps=[],
            category_scores={"A. Persyaratan Administrasi": 85.0, "B. Halal Assurance System (HAS)": 20.0},
            submission_recommendation="NEEDS_MAJOR_WORK",
            estimated_time_to_fix_days=60,
            priority_actions=[],
        )
        
        decision = agent.make_recommendation(
            application_id="TEST-001",
            koperasi_nama="Koperasi Test",
            document_completeness=0.75,
            missing_docs=[DocumentType.SERTIFIKAT_HALAL_BAHAN],
            audit_result=mock_audit,
            rag_answers=[],
            documents={},
        )
        
        print(f"Recommendation: {decision['recommendation']}")
        print(f"Confidence: {decision['confidence']}")
        print(f"Risk Level: {decision['risk_level']}")
        print(f"Weighted Score: {decision['weighted_score']}")
        print(f"Conditions: {len(decision['conditions'])}")
        print(f"Next Steps: {len(decision['next_steps'])}")
        
        await agent.generate_executive_brief(decision, Path("output/executive_brief.md"))
        print("Executive brief generated!")
    
    asyncio.run(test())