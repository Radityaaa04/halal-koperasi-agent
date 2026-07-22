#!/usr/bin/env python3
"""
Evaluation Suite for HALAL Koperasi Multi-Agent System
Metrics: Accuracy, Effectiveness, Efficiency, Explainability, Hallucination Rate
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from halal_koperasi_agent.graph import run_application
from halal_koperasi_agent.state import create_initial_state
from halal_koperasi_agent.agents.regulatory_rag import RegulatoryRAGAgent
from halal_koperasi_agent.agents.document_intake import DocumentIntakeAgent
from halal_koperasi_agent.schemas.documents import DocumentType, DocumentStatus


# ============================================================
# GROUND TRUTH DATA
# ============================================================

GROUND_TRUTH = {
    "kmbj": {
        "expected_audit_score_range": (10, 25),  # 62% doc completeness
        "expected_recommendation": "REJECT",
        "expected_critical_gaps_min": 50,
    },
    "kspt": {
        "expected_audit_score_range": (15, 30),  # 78% doc completeness
        "expected_recommendation": "REJECT",
        "expected_critical_gaps_min": 50,
    },
    "kpnl": {
        "expected_audit_score_range": (5, 20),  # 35% doc completeness
        "expected_recommendation": "REJECT",
        "expected_critical_gaps_min": 60,
    },
}

REGULATORY_QA_GROUND_TRUTH = [
    {
        "question": "Apa syarat sertifikat halal untuk koperasi?",
        "must_contain": ["PP 39/2021", "BPJPH", "dokumen", "wajib"],
        "must_not_contain": [],
        "expected_sources": ["PP_39_2021", "BPJPH_1_2023"],
    },
    {
        "question": "Berapa lama masa berlaku sertifikat halal?",
        "must_contain": ["4 tahun", "perpanjangan", "masa berlaku"],
        "must_not_contain": ["selamanya", "tidak ada batas"],
        "expected_sources": ["UU_33_2014", "PP_39_2021"],
    },
    {
        "question": "Apa kriteria segregasi area halal dan non-halal?",
        "must_contain": ["pisah", "dedicated", "peralatan", "zonasi"],
        "must_not_contain": ["campur", "bersama"],
        "expected_sources": ["SNI_HALAL", "PP_39_2021"],
    },
    {
        "question": "Apa sanksi jika tidak memiliki sertifikat halal?",
        "must_contain": ["sanksi", "administratif", "denda", "PP 39/2021"],
        "must_not_contain": ["tidak ada sanksi", "bebas"],
        "expected_sources": ["UU_33_2014", "PP_39_2021"],
    },
    {
        "question": "Siapa wajib menjadi anggota HAS di koperasi?",
        "must_contain": ["Ketua HAS", "pelatihan", "sertifikat", "minimal"],
        "must_not_contain": ["tidak perlu", "opsional"],
        "expected_sources": ["BPJPH_1_2023", "SNI_HALAL"],
    },
]


# ============================================================
# EVALUATION CLASS
# ============================================================

class EvaluationSuite:
    def __init__(self):
        self.results = {}

    async def run_full_evaluation(self) -> Dict[str, Any]:
        """Run all evaluation metrics"""
        logger.info("Starting full evaluation suite...")
        start_time = time.time()
        
        # 1. RAG Accuracy
        rag_results = await self.evaluate_rag_accuracy()
        
        # 2. Pipeline Effectiveness
        pipeline_results = await self.evaluate_pipeline_effectiveness()
        
        # 3. Efficiency (Latency)
        efficiency_results = await self.evaluate_efficiency()
        
        # 4. Explainability
        explainability_results = await self.evaluate_explainability()
        
        # 5. Hallucination Rate
        hallucination_results = await self.evaluate_hallucination_rate()
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(
            rag_results, pipeline_results, efficiency_results,
            explainability_results, hallucination_results
        )
        
        total_time = time.time() - start_time
        
        report = {
            "evaluation_timestamp": datetime.now().isoformat(),
            "total_evaluation_time_seconds": round(total_time, 1),
            "overall_score": overall_score,
            "metrics": {
                "accuracy": rag_results,
                "effectiveness": pipeline_results,
                "efficiency": efficiency_results,
                "explainability": explainability_results,
                "hallucination": hallucination_results,
            },
        }
        
        # Save report
        output_dir = Path("evaluation/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.success(f"Evaluation complete. Overall score: {overall_score:.1f}/100. Report: {report_path}")
        return report

    # ============================================================
    # 1. RAG ACCURACY
    # ============================================================

    async def evaluate_rag_accuracy(self) -> Dict[str, Any]:
        """Evaluate Regulatory RAG Agent accuracy against ground truth Q&A questions"""
        logger.info("Evaluating RAG accuracy...")
        
        agent = RegulatoryRAGAgent()
        await agent.initialize()
        
        correct = 0
        total = len(REGULATORY_QA_GROUND_TRUTH)
        details = []
        
        for gt in REGULATORY_QA_GROUND_TRUTH:
            q = gt["question"]
            ans = await agent.answer_question(q)
            
            answer_text = ans.answer.lower()
            
            # Check must_contain
            has_all = all(term.lower() in answer_text for term in gt["must_contain"])
            has_none = all(term.lower() not in answer_text for term in gt["must_not_contain"])
            sources_ok = any(s in str(ans.citations) for s in gt["expected_sources"])
            
            is_correct = has_all and has_none
            if is_correct:
                correct += 1
            
            details.append({
                "question": q,
                "correct": is_correct,
                "answer": ans.answer[:200],
                "confidence": ans.confidence,
                "citations_count": len(ans.citations),
                "has_required_terms": has_all,
                "has_no_forbidden_terms": has_none,
                "expected_sources_found": sources_ok,
            })
        
        accuracy = correct / total if total > 0 else 0
        
        logger.info(f"RAG Accuracy: {accuracy:.1%} ({correct}/{total})")
        
        return {
            "total_questions": total,
            "correct": correct,
            "accuracy": round(accuracy, 3),
            "details": details,
        }

    # ============================================================
    # 2. PIPELINE EFFECTIVENESS
    # ============================================================

    async def evaluate_pipeline_effectiveness(self) -> Dict[str, Any]:
        """Test 3 koperasi profiles through full pipeline"""
        logger.info("Evaluating pipeline effectiveness...")
        
        results = {}
        
        for pid, gt in GROUND_TRUTH.items():
            profile_config = {
                "kmbj": ("KMBJ-001-2025-001", "Koperasi Mina Bahari Jaya", "Sidoarjo", 
                         ["Tengiri Asap", "Abon Ikan Tengiri", "Fish Cracker", "Ikan Bakar Vacuum"]),
                "kspt": ("KSPT-002-2025-001", "Koperasi Sumber Tani Makmur", "Ngawi",
                         ["Kacang Tanah", "Tempe", "Tahu"]),
                "kpnl": ("KPNL-003-2025-001", "Koperasi Nelayan Sejahtera", "Cilacap",
                         ["Ikan Asin", "Teri Medan"]),
            }
            
            app_id, name, loc, prods = profile_config[pid]
            
            logger.info(f"Testing profile: {pid} ({name})")
            
            # Run full pipeline
            final_state = {}
            async for event in run_application(
                application_id=app_id,
                koperasi_name=name,
                koperasi_location=loc,
                produk_utama=prods,
                thread_id=f"eval-{pid}"
            ):
                final_state = event
            
            audit = final_state.get("audit_result")
            decision = final_state.get("decision")
            
            # Check score range
            score_in_range = False
            if audit:
                score_in_range = gt["expected_audit_score_range"][0] <= audit.overall_readiness_score <= gt["expected_audit_score_range"][1]
            
            # Check recommendation
            rec_match = False
            if decision:
                rec_match = decision.get("recommendation") == gt["expected_recommendation"]
            
            # Check critical gaps
            gaps_ok = False
            if audit:
                gaps_ok = len(audit.critical_gaps) >= gt["expected_critical_gaps_min"]
            
            results[pid] = {
                "audit_score": audit.overall_readiness_score if audit else 0,
                "expected_range": gt["expected_audit_score_range"],
                "score_in_range": score_in_range,
                "recommendation": decision.get("recommendation") if decision else "UNKNOWN",
                "expected_recommendation": gt["expected_recommendation"],
                "rec_match": rec_match,
                "critical_gaps": len(audit.critical_gaps) if audit else 0,
                "expected_critical_gaps_min": gt["expected_critical_gaps_min"],
                "gaps_ok": gaps_ok,
                "decision_confidence": decision.get("confidence", 0) if decision else 0,
                "risk_level": decision.get("risk_level", "UNKNOWN") if decision else "UNKNOWN",
            }
        
        # Calculate effectiveness metrics
        total = len(results)
        score_in_range_count = sum(1 for r in results.values() if r["score_in_range"])
        rec_match_count = sum(1 for r in results.values() if r["rec_match"])
        gaps_ok_count = sum(1 for r in results.values() if r["gaps_ok"])
        
        return {
            "profiles_tested": total,
            "score_range_accuracy": round(score_in_range_count / total, 3),
            "recommendation_accuracy": round(rec_match_count / total, 3),
            "critical_gaps_detection": round(gaps_ok_count / total, 3),
            "details": results,
        }

    # ============================================================
    # 3. EFFICIENCY (LATENCY)
    # ============================================================

    async def evaluate_efficiency(self) -> Dict[str, Any]:
            """Measure latency of full pipeline"""
            logger.info("Evaluating efficiency (latency)...")

            # Warm up
            _ = await self._run_full_pipeline("EFF-WARMUP", "Efficiency Test", "Jakarta", ["Test Product"])

            # Measure 3 runs
            latencies = []
            for i in range(3):
                test_id = f"EFF-{i+1}"
                start = time.time()
                final = await self._run_full_pipeline(test_id, "Efficiency Test", "Jakarta", ["Test Product"])
                elapsed = time.time() - start
                latencies.append(elapsed)
                logger.info(f"  Run {i+1}: {elapsed:.1f}s")

            avg_latency = sum(latencies) / len(latencies)
            p95_latency = sorted(latencies)[int(0.95 * len(latencies))]

            # SLA: < 120 seconds for full pipeline
            meets_sla = avg_latency < 120

            return {
                "runs": len(latencies),
                "latencies_seconds": latencies,
                "average_latency_seconds": round(avg_latency, 1),
                "p95_latency_seconds": round(p95_latency, 1),
                "meets_sla": meets_sla,
                "sla_threshold_seconds": 120,
            }

    async def _run_full_pipeline(self, app_id: str, name: str, loc: str, prods: list) -> Dict[str, Any]:
        """Helper to run full pipeline and return final state"""
        final_state = {}
        async for event in run_application(
            application_id=app_id,
            koperasi_name=name,
            koperasi_location=loc,
            produk_utama=prods,
            thread_id=app_id
        ):
            final_state = event
        return final_state

    # ============================================================
    # 4. EXPLAINABILITY
    # ============================================================

    async def evaluate_explainability(self) -> Dict[str, Any]:
            """Evaluate if outputs have proper citations and reasoning"""
            logger.info("Evaluating explainability...")

            agent = RegulatoryRAGAgent()
            await agent.initialize()

            # Test 5 questions
            test_questions = [gt["question"] for gt in REGULATORY_QA_GROUND_TRUTH]

            scores = []
            details = []

            for q in test_questions:
                ans = await agent.answer_question(q)

                # Check criteria
                has_citations = len(ans.citations) > 0
                has_confidence = ans.confidence > 0
                has_verification_flag = ans.needs_human_verification is not None
                has_sources = ans.retrieved_chunks is not None and len(ans.retrieved_chunks) > 0

                criteria_met = sum([
                    has_citations,
                    has_confidence,
                    has_verification_flag,
                    has_sources,
                ])

                score = criteria_met / 4
                scores.append(score)

                details.append({
                    "question": q,
                    "has_citations": has_citations,
                    "citations_count": len(ans.citations),
                    "has_confidence": has_confidence,
                    "has_verification_flag": has_verification_flag,
                    "has_sources": has_sources,
                    "score": score,
                })

            avg_score = sum(scores) / len(scores) if scores else 0

            return {
                "explainability_score": round(avg_score, 3),
                "questions_evaluated": len(test_questions),
                "details": details,
            }

    # ============================================================
    # 5. HALLUCINATION RATE
    # ============================================================

    async def evaluate_hallucination_rate(self) -> Dict[str, Any]:
        """Evaluate hallucination using self-consistency check"""
        logger.info("Evaluating hallucination rate...")
        
        agent = RegulatoryRAGAgent()
        await agent.initialize()
        
        test_questions = [gt["question"] for gt in REGULATORY_QA_GROUND_TRUTH[:3]]
        
        hallucination_count = 0
        total_checks = 0
        details = []
        
        for q in test_questions:
            # Get 3 answers for same question (self-consistency)
            answers = []
            for _ in range(3):
                ans = await agent.answer_question(q)
                answers.append(ans.answer.lower())
            
            # Compare pairwise
            for i in range(len(answers)):
                for j in range(i+1, len(answers)):
                    total_checks += 1
                    
                    # Check key terms consistency
                    terms_i = set(answers[i].split())
                    terms_j = set(answers[j].split())
                    
                    # Focus on factual terms (numbers, dates, specific regulations)
                    factual_terms_i = {t for t in terms_i if any(c.isdigit() for c in t) or any(kw in t for kw in ["pasal", "ayat", "tahun", "pp", "uu", "bpjph", "mui", "lph", "sni"])}
                    factual_terms_j = {t for t in terms_j if any(c.isdigit() for c in t) or any(kw in t for kw in ["pasal", "ayat", "tahun", "pp", "uu", "bpjph", "mui", "lph", "sni"])}
                    
                    if factual_terms_i and factual_terms_j:
                        overlap = len(factual_terms_i & factual_terms_j) / len(factual_terms_i | factual_terms_j)
                        if overlap < 0.3:  # Low overlap on factual terms
                            hallucination_count += 1
            
            details.append({
                "question": q,
                "answers_generated": len(answers),
                "pairwise_checks": 3,
            })
        
        hallucination_rate = hallucination_count / total_checks if total_checks > 0 else 0
        threshold_met = hallucination_rate < 0.1  # < 10% hallucination rate
        
        return {
            "hallucination_rate": round(hallucination_rate, 3),
            "threshold": 0.1,
            "threshold_met": threshold_met,
            "total_checks": total_checks,
            "hallucinations_detected": hallucination_count,
            "details": details,
        }

    # ============================================================
    # OVERALL SCORE CALCULATION
    # ============================================================

    def _calculate_overall_score(
        self,
        rag: Dict[str, Any],
        pipeline: Dict[str, Any],
        efficiency: Dict[str, Any],
        explainability: Dict[str, Any],
        hallucination: Dict[str, Any],
    ) -> float:
        """Calculate weighted overall score"""
        
        weights = {
            "accuracy": 0.30,
            "effectiveness": 0.30,
            "efficiency": 0.15,
            "explainability": 0.15,
            "hallucination": 0.10,
        }
        
        scores = {
            "accuracy": rag.get("accuracy", 0) * 100,
            "effectiveness": (
                pipeline.get("score_range_accuracy", 0) * 0.4 +
                pipeline.get("recommendation_accuracy", 0) * 0.4 +
                pipeline.get("critical_gaps_detection", 0) * 0.2
            ) * 100,
            "efficiency": 100 if efficiency.get("meets_sla", False) else 50,
            "explainability": explainability.get("explainability_score", 0) * 100,
            "hallucination": (1 - hallucination.get("hallucination_rate", 0)) * 100,
        }
        
        overall = sum(scores[k] * weights[k] for k in weights)
        return round(overall, 1)


async def main():
    suite = EvaluationSuite()
    report = await suite.run_full_evaluation()
    
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Overall Score: {report['overall_score']:.1f}/100")
    print(f"Total Time: {report['total_evaluation_time_seconds']:.1f}s")
    print()
    for metric, data in report["metrics"].items():
        if metric == "accuracy":
            print(f"  Accuracy: {data['accuracy']:.1%} ({data['correct']}/{data['total_questions']})")
        elif metric == "effectiveness":
            print(f"  Effectiveness: Score Range {data['score_range_accuracy']:.0%}, "
                  f"Recommendation {data['recommendation_accuracy']:.0%}, "
                  f"Gap Detection {data['critical_gaps_detection']:.0%}")
        elif metric == "efficiency":
            print(f"  Efficiency: Avg {data['average_latency_seconds']:.1f}s, "
                  f"P95 {data['p95_latency_seconds']:.1f}s, SLA {'✓' if data['meets_sla'] else '✗'}")
        elif metric == "explainability":
            print(f"  Explainability: {data['explainability_score']:.0%}")
        elif metric == "hallucination":
            print(f"  Hallucination Rate: {data['hallucination_rate']:.1%} "
                  f"({'✓' if data['threshold_met'] else '✗'})")


if __name__ == "__main__":
    asyncio.run(main())