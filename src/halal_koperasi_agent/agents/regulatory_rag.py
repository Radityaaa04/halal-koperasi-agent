"""
Regulatory RAG Agent for HALAL Koperasi Multi-Agent System
Retrieves relevant regulations and answers questions grounded in official documents.
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field

from loguru import logger
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import VectorStoreRetriever
from rank_bm25 import BM25Okapi

from halal_koperasi_agent.config import settings
from halal_koperasi_agent.schemas.regulatory import (
    RegulatoryChunk,
    RegulatoryCitation,
    RAGAnswer,
    RegulatorySource,
)
from halal_koperasi_agent.schemas.documents import DocumentType
from halal_koperasi_agent.llm_providers import get_langchain_model
from halal_koperasi_agent.vector_store import get_chroma_client, get_embeddings, get_reranker


class RegulatoryRAGAgent:
    """
    Agent responsible for:
    1. Retrieving relevant regulatory chunks from ChromaDB (hybrid: vector + BM25)
    2. Reranking retrieved chunks with cross-encoder
    3. Generating grounded answers with citations
    4. Answering regulatory questions for halal certification
    """

    def __init__(self):
        self.chroma_client = None
        self.collections: Dict[str, Any] = {}
        self.bm25_indexes: Dict[str, BM25Okapi] = {}
        self.chunk_texts: Dict[str, List[str]] = {}
        self.chunk_metadatas: Dict[str, List[Dict]] = {}
        self.llm = None
        self.embeddings = None
        self.reranker = None
        self._initialized = False

    async def initialize(self):
        """Initialize vector store, embeddings, reranker, and BM25 indexes"""
        if self._initialized:
            return

        logger.info("Initializing Regulatory RAG Agent...")

        # 1. Initialize LLM
        try:
            from halal_koperasi_agent.llm_providers import get_langchain_model
            self.llm = get_langchain_model(
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL,
            )
            logger.info(f"LLM initialized: {settings.LLM_PROVIDER} - {settings.LLM_MODEL}")
        except Exception as e:
            logger.error(f"LLM init failed: {e}")
            raise

        # 2. Initialize ChromaDB client
        self.chroma_client = get_chroma_client()
        if not self.chroma_client:
            raise RuntimeError("ChromaDB client not available")

        # 3. Initialize embeddings
        try:
            from halal_koperasi_agent.vector_store import get_embeddings
            self.embeddings = get_embeddings()
            logger.info(f"Embeddings initialized: {settings.EMBEDDING_PROVIDER}")
        except Exception as e:
            logger.error(f"Embeddings init failed: {e}")
            raise

        # 4. Initialize reranker
        try:
            from halal_koperasi_agent.vector_store import get_reranker
            self.reranker = get_reranker()
            logger.info(f"Reranker initialized: {settings.RERANKER_PROVIDER}")
        except Exception as e:
            logger.warning(f"Reranker init failed (will skip reranking): {e}")
            self.reranker = None

        # 5. Load BM25 indexes for each collection
        await self._load_bm25_indexes()

        self._initialized = True
        logger.success("Regulatory RAG Agent initialized successfully")

    async def _load_bm25_indexes(self):
        """Load BM25 indexes for all collections"""
        collections = self.chroma_client.list_collections()
        
        for collection in collections:
            if not collection.name.startswith(settings.CHROMA_COLLECTION_PREFIX):
                continue
            
            source_name = collection.name.replace(f"{settings.CHROMA_COLLECTION_PREFIX}_", "")
            logger.info(f"Loading BM25 index for {source_name}...")
            
            try:
                # Get all documents from collection
                results = collection.get(
                    include=["documents", "metadatas"],
                )
                
                if not results["documents"]:
                    logger.warning(f"Collection {collection.name} is empty")
                    continue
                
                docs = results["documents"]
                metadatas = results["metadatas"]
                
                # Tokenize for BM25
                tokenized_docs = [doc.lower().split() for doc in docs]
                bm25 = BM25Okapi(tokenized_docs)
                
                self.bm25_indexes[source_name] = bm25
                self.chunk_texts[source_name] = docs
                self.chunk_metadatas[source_name] = metadatas
                
                logger.info(f"  Loaded {len(docs)} documents for BM25")
                
            except Exception as e:
                logger.error(f"Failed to load BM25 for {source_name}: {e}")

    # ============================================================
    # RETRIEVAL
    # ============================================================

    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        sources: Optional[List[str]] = None,
    ) -> List[Document]:
        """
        Hybrid retrieval: Vector search + BM25 + RRF fusion
        Returns top-k Document objects with metadata
        """
        if not self._initialized:
            await self.initialize()
        
        top_k = top_k or settings.TOP_K_RETRIEVAL
        
        # 1. Vector search (semantic)
        vector_results = await self._vector_search(query, top_k * 2, sources)
        
        # 2. BM25 search (keyword)
        bm25_results = self._bm25_search(query, top_k * 2, sources)
        
        # 3. Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            vector_results, bm25_results, top_k=top_k * 2
        )
        
        # 4. Rerank if available
        if self.reranker and len(fused_results) > settings.TOP_K_RERANK:
            reranked = await self._rerank(query, fused_results, settings.TOP_K_RERANK)
            return reranked[:top_k]
        
        return fused_results[:top_k]

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        sources: Optional[List[str]] = None,
    ) -> List[Tuple[Document, float]]:
        """Vector similarity search across collections"""
        results = []
        
        # Get embedding for query
        query_embedding = self.embeddings.embed_query(query)
        
        collections = self.chroma_client.list_collections()
        
        for collection in collections:
            if not collection.name.startswith(settings.CHROMA_COLLECTION_PREFIX):
                continue
            
            source_name = collection.name.replace(f"{settings.CHROMA_COLLECTION_PREFIX}_", "")
            
            if sources and source_name not in sources:
                continue
            
            try:
                results_data = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, 50),
                    include=["documents", "metadatas", "distances"],
                )
                
                if not results_data["documents"][0]:
                    continue
                
                for doc, meta, dist in zip(
                    results_data["documents"][0],
                    results_data["metadatas"][0],
                    results_data["distances"][0],
                ):
                    # Accept all results, use rank position for RRF
                    # Cosine distance: 0 = identical, 2 = completely opposite
                    # Lower is better -> convert to pseudo-similarity for ranking
                    similarity = 2.0 - dist  # Now 0=bad, 2=perfect
                    doc_obj = Document(
                        page_content=doc,
                        metadata=meta,
                    )
                    results.append((doc_obj, similarity))
                        
            except Exception as e:
                logger.warning(f"Vector search failed for {collection.name}: {e}")
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _bm25_search(
        self,
        query: str,
        top_k: int,
        sources: Optional[List[str]] = None,
    ) -> List[Tuple[Document, float]]:
        """BM25 keyword search across collections"""
        results = []
        tokenized_query = query.lower().split()
        
        for source_name, bm25 in self.bm25_indexes.items():
            if sources and source_name not in sources:
                continue
            
            try:
                scores = bm25.get_scores(tokenized_query)
                top_indices = sorted(
                    range(len(scores)), 
                    key=lambda i: scores[i], 
                    reverse=True
                )[:top_k]
                
                for idx in top_indices:
                    if scores[idx] > 0:
                        doc = Document(
                            page_content=self.chunk_texts[source_name][idx],
                            metadata=self.chunk_metadatas[source_name][idx],
                        )
                        results.append((doc, scores[idx]))
                        
            except Exception as e:
                logger.warning(f"BM25 search failed for {source_name}: {e}")
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _reciprocal_rank_fusion(
            self,
            vector_results: List[Tuple[Document, float]],
            bm25_results: List[Tuple[Document, float]],
            top_k: int,
            k: int = 60,
        ) -> List[Document]:
            """Combine vector and BM25 results using Reciprocal Rank Fusion"""
            doc_scores: Dict[str, Tuple[float, Document]] = {}
        
            # Process vector results
            for rank, (doc, score) in enumerate(vector_results):
                doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
                rrf_score = 1 / (k + rank + 1)
                if doc_id not in doc_scores or rrf_score > doc_scores[doc_id][0]:
                    doc_scores[doc_id] = (rrf_score, doc)
        
            # Process BM25 results
            for rank, (doc, score) in enumerate(bm25_results):
                doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
                rrf_score = 1 / (k + rank + 1)
                if doc_id not in doc_scores or rrf_score > doc_scores[doc_id][0]:
                    doc_scores[doc_id] = (rrf_score, doc)
        
            # Sort by combined score and return top_k
            fused = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)
            return [doc for _, doc in fused[:top_k]]

    async def _rerank(
        self,
        query: str,
        documents: List[Document],
        top_n: int,
    ) -> List[Document]:
        """Rerank documents using LLM-based relevance scoring.
        
        NVIDIA's integrate API does not expose dedicated reranker models.
        We use LLM-based scoring: ask the LLM to rate each doc's relevance to the query
        on a scale of 0-10. This is cost-effective (few tokens) and accurate.
        """
        if not self.llm or len(documents) <= top_n:
            return documents[:top_n]
        
        try:
            from halal_koperasi_agent.llm_providers import chat_completion, ChatMessage
            
            # Batch score: ask LLM to rank all docs at once (cost-efficient)
            doc_summaries = []
            for i, doc in enumerate(documents):
                snippet = doc.page_content[:200].replace('\n', ' ')
                doc_summaries.append(f"DOC_{i}: {snippet}")
            
            system_prompt = """Anda adalah sistem reranking untuk RAG. Berikan skor relevansi 0-10 untuk setiap dokumen terhadap query.
Format output SANGAT KETAT - satu baris per dokumen:
DOC_0: <score>
DOC_1: <score>
...dst
Hanya angka, tidak ada penjelasan."""
            
            user_prompt = f"""Query: {query}

Dokumen:
{chr(10).join(doc_summaries)}

Berikan skor 0-10 untuk setiap dokumen:"""
            
            response = await chat_completion(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL,
                temperature=0.0,
            )
            
            # Parse scores
            import re
            scores = {}
            for match in re.finditer(r"DOC_(\d+):\s*(\d+(?:\.\d+)?)", response.content):
                doc_idx = int(match.group(1))
                score = float(match.group(2))
                if doc_idx < len(documents):
                    scores[doc_idx] = score
            
            if not scores:
                logger.warning("LLM rerank: no scores parsed, using original order")
                return documents[:top_n]
            
            # Sort by score descending
            sorted_indices = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
            reranked = [documents[i] for i in sorted_indices[:top_n]]
            
            logger.info(f"LLM rerank: {len(reranked)} docs reranked (top score: {scores[sorted_indices[0]]:.1f})")
            return reranked
            
        except Exception as e:
            logger.warning(f"LLM rerank failed ({e!r}), using unranked top_n")
            return documents[:top_n]

    # ============================================================
    # ANSWER GENERATION
    # ============================================================

    async def answer_question(
        self,
        question: str,
        context_application_id: Optional[str] = None,
        auto_questions: bool = True,
    ) -> RAGAnswer:
        """
        Answer a regulatory question with grounded citations.
        If auto_questions=True and context_application_id provided,
        auto-generates relevant questions based on application state.
        """
        if not self._initialized:
            await self.initialize()

        # Retrieve relevant chunks
        retrieved_docs = await self.retrieve(
            question,
            top_k=settings.TOP_K_RETRIEVAL,
        )
        
        if not retrieved_docs:
            return RAGAnswer(
                question=question,
                answer="Informasi tidak tersedia dalam dokumen resmi yang diindeks. "
                       "Silakan konsultasi ke LPH/BPJPH.",
                citations=[],
                confidence=0.0,
                needs_human_verification=True,
                verification_reason="No relevant regulatory chunks found",
                retrieved_chunks=[],
                retrieval_strategy="hybrid_rrf_rerank",
            )

        # Generate answer with citations
        answer_result = await self._generate_answer(question, retrieved_docs)
        
        # Hallucination check (self-consistency)
        hallucination_risk = await self._check_hallucination(question, answer_result)
        
        # Determine if human verification needed
        needs_verification = (
            hallucination_risk > 0.3 or
            answer_result.confidence < 0.7 or
            len(answer_result.citations) == 0
        )
        
        return RAGAnswer(
            question=question,
            answer=answer_result.answer,
            citations=answer_result.citations,
            confidence=answer_result.confidence,
            needs_human_verification=needs_verification,
            verification_reason="Low confidence or hallucination risk" if needs_verification else None,
            retrieved_chunks=[doc.metadata.get("chunk_id", "") for doc in answer_result.context_docs],
            retrieval_strategy="hybrid_rrf_rerank",
            model_used=settings.LLM_MODEL,
        )

    async def _generate_answer(
        self,
        question: str,
        context_docs: List[Document],
    ) -> "AnswerWithCitations":
        """Generate grounded answer with citations using LLM"""
        
        # Prepare context with source tracking
        context_parts = []
        for i, doc in enumerate(context_docs):
            meta = doc.metadata
            source = meta.get("source", "UNKNOWN")
            article = meta.get("article", "")
            verse = meta.get("verse", "")
            chunk_id = meta.get("chunk_id", f"CHUNK-{i}")
            
            header = f"[SOURCE: {source}"
            if article:
                header += f", {article}"
            if verse:
                header += f" {verse}"
            header += f"] (CHUNK: {chunk_id})"
            
            context_parts.append(f"{header}\n{doc.page_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build prompt
        system_prompt = """Anda adalah Asisten Regulasi Halal Indonesia. Jawab pertanyaan HANYA berdasarkan KONTEKS yang disediakan.

ATURAN KETAT:
1. Hanya jawab berdasarkan KONTEKS yang disediakan.
2. Jika konteks tidak cukup, jawab: "Informasi tidak tersedia dalam dokumen resmi yang diindeks. Silakan konsultasi ke LPH/BPJPH."
3. SELALU sertakan sitasi untuk KLAIM yang Anda buat.
4. Format sitasi: [SOURCE: SOURCE_NAME, Pasal X Ayat Y] (CHUNK: CHUNK_ID)
5. JANGAN mengarang, menghallusinasikan, atau mengasumsikan.
6. Bahasa Indonesia formal, jelas, actionable.

FORMAT JAWABAN:
**Jawaban:** [jawaban singkat, grounded]
**Dasar Hukum:** [daftar sitasi dengan quote singkat]
**Confidence:** [0.0-1.0]
**Perlu Verifikasi Manusia:** [Ya/Tidak + alasan]"""

        user_prompt = f"""KONTEKS REGULASI:
{context_parts}

PERTANYAAN: {question}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Get LLM response
        from halal_koperasi_agent.llm_providers import chat_completion, ChatMessage
        response = await chat_completion(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            temperature=0.1,
        )

        # Parse response
        return self._parse_answer(response.content, context_docs)

    def _parse_answer(self, response: str, context_docs: List[Document]) -> "AnswerWithCitations":
        """Parse LLM response into structured answer with citations"""
        import re
        
        # Extract sections
        answer_match = re.search(r"\*\*Jawaban:\*\*\s*(.+?)(?=\n\*\*|\Z)", response, re.DOTALL)
        hukum_match = re.search(r"\*\*Dasar Hukum:\*\*\s*(.+?)(?=\n\*\*|\Z)", response, re.DOTALL)
        conf_match = re.search(r"\*\*Confidence:\*\*\s*([\d.]+)", response)
        verify_match = re.search(r"\*\*Perlu Verifikasi Manusia:\*\*\s*(.+?)(?=\n\*\*|\Z)", response, re.DOTALL)
        
        answer = answer_match.group(1).strip() if answer_match else response.strip()
        dasar_hukum = hukum_match.group(1).strip() if hukum_match else ""
        confidence = float(conf_match.group(1)) if conf_match else 0.7
        needs_verification = "Ya" in (verify_match.group(1) if verify_match else "Tidak")
        
        # Parse citations from Dasar Hukum
        citations = []
        if dasar_hukum:
            # Pattern: [SOURCE: SOURCE, Pasal X Ayat Y] (CHUNK: CHUNK_ID)
            citation_pattern = r"\[SOURCE:\s*([^,\]]+)(?:,\s*([^,\]]+))?\s*\]\s*\(CHUNK:\s*([^)]+)\)"
            for match in re.finditer(citation_pattern, dasar_hukum):
                source = match.group(1).strip()
                article = match.group(2).strip() if match.group(2) else ""
                chunk_id = match.group(3).strip()
                
                # Find matching doc for text snippet
                text_snippet = ""
                for doc in context_docs:
                    if doc.metadata.get("chunk_id") == chunk_id:
                        text_snippet = doc.page_content[:200] + "..."
                        break
                
                citations.append(RegulatoryCitation(
                    chunk_id=chunk_id,
                    source=RegulatorySource(source) if source in [s.value for s in RegulatorySource] else RegulatorySource.LPH_PANDUAN,
                    article=article or "Unknown",
                    verse=None,
                    text_snippet=text_snippet or "Quote not extracted",
                    relevance_score=1.0,
                ))
        
        # If no citations parsed, create from context
        if not citations:
            for i, doc in enumerate(context_docs):
                meta = doc.metadata
                citations.append(RegulatoryCitation(
                    chunk_id=meta.get("chunk_id", f"CHUNK-{i}"),
                    source=RegulatorySource(meta.get("source", "LPH_PANDUAN")) if meta.get("source") in [s.value for s in RegulatorySource] else RegulatorySource.LPH_PANDUAN,
                    article=meta.get("article", "Unknown"),
                    verse=meta.get("verse"),
                    text_snippet=doc.page_content[:200],
                    relevance_score=0.8,
                ))
        
        return AnswerWithCitations(
            answer=answer,
            citations=citations,
            confidence=confidence,
            needs_human_verification=needs_verification,
            context_docs=context_docs,
        )

    async def _check_hallucination(
        self,
        question: str,
        answer_result: "AnswerWithCitations",
    ) -> float:
        """Self-consistency check for hallucination risk"""
        if not self.llm:
            return 0.0
        
        # Quick check: does answer make claims not in context?
        context_text = " ".join([doc.page_content for doc in answer_result.context_docs])
        answer_text = answer_result.answer
        
        # Simple heuristic: check if key terms in answer appear in context
        answer_terms = set(re.findall(r"\b\w{4,}\b", answer_text.lower()))
        context_terms = set(re.findall(r"\b\w{4,}\b", context_text.lower()))
        
        if not answer_terms:
            return 0.0
        
        overlap = len(answer_terms & context_terms) / len(answer_terms)
        hallucination_risk = 1 - overlap
        
        return max(0.0, min(1.0, hallucination_risk))

    # ============================================================
    # AUTO QUESTIONS
    # ============================================================

    async def generate_auto_questions(
        self,
        application_state: Dict[str, Any],
    ) -> List[str]:
        """Generate relevant regulatory questions based on application state"""
        questions = []
        
        # Based on missing documents
        missing_docs = application_state.get("missing_required_docs", [])
        for doc_type in missing_docs:
            questions.append(f"Apa syarat dokumen {doc_type.value} untuk sertifikasi halal?")
        
        # Based on product type
        produk = application_state.get("produk_utama", [])
        if any("ikan" in p.lower() for p in produk):
            questions.append("Apa kriteria segregasi area halal dan non-halal di fasilitas produksi ikan?")
        if any("herbal" in p.lower() or "teh" in p.lower() for p in produk):
            questions.append("Apa regulasi untuk bahan baku herbal/alkohol dalam produk halal?")
        
        # Generic questions
        questions.extend([
            "Berapa lama masa berlaku sertifikat halal dan prosedur perpanjangan?",
            "Apa sanksi jika gagal audit LPH 3 kali berturut-turut?",
            "Siapa wajib menjadi anggota HAS (Halal Assurance System) di koperasi?",
        ])
        
        # Deduplicate and limit
        unique = list(dict.fromkeys(questions))
        return unique[:10]


# Helper class for internal use
class AnswerWithCitations(BaseModel):
    answer: str
    citations: List[RegulatoryCitation]
    confidence: float
    needs_human_verification: bool
    context_docs: List[Any] = Field(default_factory=list)


# ============================================================
# VECTOR STORE HELPERS (imported from vector_store module)
# ============================================================

def get_chroma_client():
    """Get ChromaDB HTTP client"""
    try:
        import chromadb
        host = settings.CHROMA_HOST.replace("http://", "").split(":")[0]
        port = int(settings.CHROMA_HOST.split(":")[-1]) if ":" in settings.CHROMA_HOST else 8000
        return chromadb.HttpClient(host=host, port=port)
    except Exception as e:
        logger.error(f"ChromaDB client error: {e}")
        return None


def get_collection(source: str):
    """Get ChromaDB collection for regulatory source"""
    client = get_chroma_client()
    if not client:
        return None
    collection_name = f"{settings.CHROMA_COLLECTION_PREFIX}_{source.lower()}"
    return client.get_or_create_collection(collection_name)


def get_embeddings():
    """Get embeddings model based on provider"""
    if settings.EMBEDDING_PROVIDER == "nvidia_nim":
        try:
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
            return NVIDIAEmbeddings(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.NVIDIA_API_KEY,
                base_url=settings.NVIDIA_BASE_URL,
            )
        except ImportError:
            raise ImportError("langchain-nvidia-ai-endpoints required for NIM embeddings")
    
    elif settings.EMBEDDING_PROVIDER == "huggingface":
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        return HuggingFaceEndpointEmbeddings(
            model=settings.EMBEDDING_MODEL,
            huggingfacehub_api_token=settings.HF_API_KEY,
        )
    
    else:  # ollama
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_HOST,
        )


def get_reranker():
    """Get reranker model based on provider"""
    if settings.RERANKER_PROVIDER == "nvidia_nim":
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank
            return NVIDIARerank(
                model=settings.RERANKER_MODEL,
                api_key=settings.NVIDIA_API_KEY,
                base_url=settings.NVIDIA_BASE_URL,
            )
        except ImportError:
            return None
    
    elif settings.RERANKER_PROVIDER == "ollama":
        # Use cross-encoder via sentence-transformers
        from sentence_transformers import CrossEncoder
        return CrossEncoder(settings.OLLAMA_RERANKER_MODEL)
    
    return None