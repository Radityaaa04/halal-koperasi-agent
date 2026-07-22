#!/usr/bin/env python3
"""
Regulatory Knowledge Base Ingestion Script (NVIDIA NIM API Version)
Downloads, parses, chunks, and indexes Indonesian Halal regulations into ChromaDB.
Uses NVIDIA NIM API for embeddings (not local model download).
"""

import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
import fitz  # PyMuPDF
import httpx
import yaml
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

# Load .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from halal_koperasi_agent.config import settings
from halal_koperasi_agent.schemas.regulatory import RegulatoryChunk, RegulatorySource

# Configuration
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
BATCH_SIZE = 100

# Source configuration
REGULATORY_SOURCES = {
    "UU_33_2014": {
        "name": "UU No. 33 Tahun 2014 - Jaminan Produk Halal",
        "source_enum": "UU_33_2014",
        "category": "persyaratan_umum",
        "url": "https://bpjph.halal.go.id/regulasi/uu",
        "priority_pages": None,
    },
    "PP_39_2021": {
        "name": "PP No. 39 Tahun 2021 - Pelaksanaan Jaminan Produk Halal",
        "source_enum": "PP_39_2021",
        "category": "prosedur_pengajuan",
        "url": "https://bpjph.halal.go.id/regulasi/pp",
        "priority_pages": None,
    },
    "BPJPH_1_2023": {
        "name": "Peraturan BPJPH No. 1 Tahun 2023 - Prosedur Pengajuan",
        "source_enum": "BPJPH_1_2023",
        "category": "prosedur_pengajuan",
        "url": "https://bpjph.halal.go.id/regulasi/peraturan-bpjph",
        "priority_pages": None,
    },
    "BPJPH_2_2023": {
        "name": "Peraturan BPJPH No. 2 Tahun 2023 - Prosedur Verifikasi & Audit",
        "source_enum": "BPJPH_2_2023",
        "category": "audit_lapangan",
        "url": "https://bpjph.halal.go.id/regulasi/peraturan-bpjph",
        "priority_pages": None,
    },
    "MUI_FATWA": {
        "name": "Fatwa MUI Tentang Halal (Kompilasi)",
        "source_enum": "MUI_FATWA",
        "category": "fatwa_mui",
        "url": "https://mui.or.id/fatwa/",
        "priority_pages": None,
    },
    "LPH_PANDUAN": {
        "name": "Panduan Audit LPH (Kompilasi)",
        "source_enum": "LPH_PANDUAN",
        "category": "audit_lapangan",
        "url": "internal",
        "priority_pages": None,
    },
    "SNI_HALAL": {
        "name": "SNI 99001:2023 - HAS & SNI 3932 - Makanan Halal",
        "source_enum": "SNI_HALAL",
        "category": "standar_teknis",
        "url": "https://www.bsn.go.id/",
        "priority_pages": None,
    },
    "KOMINFO_9_2023": {
        "name": "Permenkominfo No. 9 Tahun 2023 - Aksesibilitas Digital",
        "source_enum": "KOMINFO_9_2023",
        "category": "aksesibilitas",
        "url": "https://jdih.kominfo.go.id/",
        "priority_pages": None,
    },
}

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
BATCH_SIZE = 100


class RegulationIngester:
    def __init__(self):
        self.http_client: httpx.AsyncClient | None = None
        self.chroma_client = None
        self.collections = {}

    async def initialize(self):
        """Initialize HTTP client and ChromaDB connection."""
        logger.info("Initializing HTTP client for NVIDIA NIM API...")
        self.http_client = httpx.AsyncClient(
            base_url=settings.NVIDIA_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

        logger.info("Connecting to ChromaDB...")
        self.chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST.replace("http://", "").split(":")[0],
            port=int(settings.CHROMA_HOST.split(":")[-1]) if ":" in settings.CHROMA_HOST else 8000,
        )

        # Create/get collections for each source
        for source_id, config in REGULATORY_SOURCES.items():
            collection_name = f"{settings.CHROMA_COLLECTION_PREFIX}_{source_id.lower()}"
            self.collections[source_id] = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"source": source_id, "description": config["name"]},
            )
            logger.info(f"Collection ready: {collection_name}")

    async def close(self):
        if self.http_client:
            await self.http_client.aclose()

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from NVIDIA NIM API."""
        if not texts:
            return []

        payload = {
            "model": settings.EMBEDDING_MODEL,
            "input": texts,
            "input_type": "passage",
            "modality": "text",
            "truncate": "END",
        }

        # Debug: print request details (mask key)
        logger.debug(f"POST /embeddings | model={settings.EMBEDDING_MODEL} | key={'set' if settings.NVIDIA_API_KEY else 'EMPTY'} | base={settings.NVIDIA_BASE_URL}")
        
        response = await self.http_client.post(
            "/embeddings",
            json=payload,
        )
        
        if response.status_code != 200:
            logger.error(f"API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()

        # NVIDIA NIM returns OpenAI-compatible format
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    def extract_text_from_pdf(self, pdf_path: Path) -> list[dict]:
        """Extract text from PDF with page numbers."""
        doc = fitz.open(pdf_path)
        pages = []

        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            blocks = page.get_text("dict")["blocks"]
            structured_text = ""
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            structured_text += span["text"] + " "
                        structured_text += "\n"
                    structured_text += "\n"

            pages.append({
                "page_number": page_num,
                "text": text,
                "structured_text": structured_text,
                "char_count": len(text),
            })

        doc.close()
        return pages

    def detect_article_verse(self, text: str) -> tuple[str | None, str | None]:
        """Detect Pasal and Ayat from Indonesian legal text."""
        pasal_match = re.search(r"Pasal\s+(\d+[A-Z]?)", text, re.IGNORECASE)
        ayat_match = re.search(r"Ayat\s*\(?(\d+)\)?", text, re.IGNORECASE)

        article = f"Pasal {pasal_match.group(1)}" if pasal_match else None
        verse = f"Ayat ({ayat_match.group(1)})" if ayat_match else None

        return article, verse

    def detect_chapter(self, text: str) -> str | None:
        bab_match = re.search(r"BAB\s+[IVX]+\s+(.+?)(?:\n|$)", text, re.IGNORECASE)
        return bab_match.group(0).strip() if bab_match else None

    def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        legal_terms = [
            "halal", "haram", "sertifikat", "produk", "jaminan", "bpjph",
            "lph", "mui", "audit", "verifikasi", "pengajuan", "persyaratan",
            "bahan baku", "fasilitas", "proses", "produksi", "segregasi",
            "kontaminasi", "ccp", "haccp", "has", "organogram", "pelatihan",
            "sanksi", "denda", "pembatalan", "perpanjangan", "mutasi",
            "impor", "ekspor", "label", "logo", "nomor registrasi",
        ]

        found = []
        text_lower = text.lower()
        for term in legal_terms:
            if term in text_lower:
                found.append(term)

        words = re.findall(r"\b[a-zA-Z]{4,}\b", text_lower)
        from collections import Counter
        freq = Counter(words)
        for word, count in freq.most_common(5):
            if word not in found and count > 2:
                found.append(word)

        return found[:max_keywords]

    def chunk_text(self, text: str, source_id: str, page_num: int, metadata: dict) -> list:
        chunks = []
        words = text.split()

        for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk_words = words[i:i + CHUNK_SIZE]
            chunk_text = " ".join(chunk_words)

            if len(chunk_text.strip()) < 50:
                continue

            chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()[:12]
            chunk_id = f"{source_id}_{page_num}_{chunk_hash}"

            article, verse = self.detect_article_verse(chunk_text)
            chapter = self.detect_chapter(chunk_text)

            chunk = {
                "chunk_id": chunk_id,
                "source": source_id,
                "document_title": metadata["document_title"],
                "chapter": chapter,
                "article": article,
                "verse": verse,
                "text": chunk_text,
                "keywords": self.extract_keywords(chunk_text),
                "effective_date": metadata.get("effective_date"),
                "category": metadata["category"],
                "language": "id",
                "embedding_model": settings.EMBEDDING_MODEL,
                "page_number": page_num,
                "char_start": i * 5,
                "char_end": (i + len(chunk_words)) * 5,
            }
            chunks.append(chunk)

        return chunks

    async def process_source(self, source_id: str, pdf_path: Path, force: bool = False) -> dict:
        config = REGULATORY_SOURCES[source_id]
        collection = self.collections[source_id]

        if not force:
            existing = collection.count()
            if existing > 0:
                logger.info(f"{source_id}: Already has {existing} chunks, skipping (use --force to re-ingest)")
                return {"source": source_id, "status": "skipped", "chunks": existing}

        logger.info(f"Processing {source_id}: {config['name']}")

        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return {"source": source_id, "status": "error", "error": "PDF not found"}

        pages = self.extract_text_from_pdf(pdf_path)
        logger.info(f"Extracted {len(pages)} pages from {pdf_path.name}")

        all_chunks = []
        for page in pages:
            if page["char_count"] < 100:
                continue

            chunks = self.chunk_text(
                page["text"],
                source_id,
                page["page_number"],
                {
                    "source_enum": config["source_enum"],
                    "document_title": config["name"],
                    "category": config["category"],
                    "effective_date": None,
                }
            )
            all_chunks.extend(chunks)

        logger.info(f"Generated {len(all_chunks)} chunks")

        if len(all_chunks) == 0:
            logger.warning(f"{source_id}: No chunks generated, skipping")
            return {"source": source_id, "status": "skipped", "chunks": 0, "pages": len(pages)}

        # Embed in batches
        texts = [chunk["text"] for chunk in all_chunks]
        embeddings = []

        for i in tqdm(range(0, len(texts), BATCH_SIZE), desc=f"Embedding {source_id}"):
            batch_texts = texts[i:i + BATCH_SIZE]
            batch_embeddings = await self.get_embeddings(batch_texts)
            embeddings.extend(batch_embeddings)

        # Prepare for ChromaDB
        ids = [chunk["chunk_id"] for chunk in all_chunks]
        metadatas = []
        documents = []

        for chunk, embedding in zip(all_chunks, embeddings):
            metadatas.append({
                "source": chunk["source"],
                "document_title": chunk["document_title"],
                "chapter": chunk["chapter"] or "",
                "article": chunk["article"] or "",
                "verse": chunk["verse"] or "",
                "category": chunk["category"],
                "page_number": chunk["page_number"],
                "keywords": ",".join(chunk["keywords"]),
                "effective_date": chunk["effective_date"].isoformat() if chunk["effective_date"] else "",
            })
            documents.append(chunk["text"])

        # Upsert to ChromaDB
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

        logger.success(f"{source_id}: Ingested {len(all_chunks)} chunks successfully")

        return {
            "source": source_id,
            "status": "success",
            "chunks": len(all_chunks),
            "pages": len(pages),
        }

    async def run_ingestion(self, sources: list[str] = None, force: bool = False):
        # Handle "all" keyword or None
        if sources is None or sources == ["all"] or sources == "all":
            sources = list(REGULATORY_SOURCES.keys())
        
        # Filter out "all" if mixed with specific sources
        sources = [s for s in sources if s != "all"] if isinstance(sources, list) else [sources]
        if not sources:
            sources = list(REGULATORY_SOURCES.keys())

        results = []
        downloads_dir = settings.DATA_DIR / "downloads"

        for source_id in sources:
            if source_id not in REGULATORY_SOURCES:
                logger.warning(f"Unknown source: {source_id}")
                continue

            pdf_path = downloads_dir / f"{source_id}.pdf"
            result = await self.process_source(source_id, pdf_path, force)
            results.append(result)

        logger.info("\n" + "=" * 60)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 60)
        total_chunks = 0
        for r in results:
            status_icon = "✅" if r["status"] == "success" else "⏭️" if r["status"] == "skipped" else "❌"
            chunks = r.get("chunks", 0)
            total_chunks += chunks if isinstance(chunks, int) else 0
            logger.info(f"{status_icon} {r['source']}: {r['status']} ({chunks} chunks)")

        logger.info(f"Total chunks ingested: {total_chunks}")

        return results

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Indonesian Halal Regulations into ChromaDB via NVIDIA NIM API")
    parser.add_argument("--source", "-s", action="append", help="Specific source(s) to ingest (default: all)")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-ingestion even if data exists")
    parser.add_argument("--list", "-l", action="store_true", help="List available sources")

    args = parser.parse_args()

    if args.list:
        print("Available regulatory sources:")
        for sid, config in REGULATORY_SOURCES.items():
            print(f"  {sid}: {config['name']} ({config['category']})")
        return

    async with RegulationIngester() as ingester:
        await ingester.run_ingestion(sources=args.source, force=args.force)


if __name__ == "__main__":
    asyncio.run(main())