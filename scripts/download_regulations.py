#!/usr/bin/env python3
"""
Playwright-based PDF Downloader for Indonesian Halal Regulations
Downloads regulatory PDFs from government portals using browser automation.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from halal_koperasi_agent.config import settings

# Regulation sources with download strategies
REGULATION_SOURCES = {
    "UU_33_2014": {
        "name": "UU No. 33 Tahun 2014 - Jaminan Produk Halal",
        "url": "https://bpjph.halal.go.id/regulasi/uu",
        "filename": "UU_33_2014.pdf",
        "strategy": "bpjph_direct",
    },
    "PP_39_2021": {
        "name": "PP No. 39 Tahun 2021 - Pelaksanaan JPH",
        "url": "https://bpjph.halal.go.id/regulasi/pp",
        "filename": "PP_39_2021.pdf",
        "strategy": "bpjph_direct",
    },
    "BPJPH_1_2023": {
        "name": "Peraturan BPJPH No. 1 Tahun 2023 - Prosedur Pengajuan",
        "url": "https://bpjph.halal.go.id/regulasi/peraturan-bpjph",
        "filename": "BPJPH_1_2023.pdf",
        "strategy": "bpjph_direct",
    },
    "BPJPH_2_2023": {
        "name": "Peraturan BPJPH No. 2 Tahun 2023 - Prosedur Verifikasi & Audit",
        "url": "https://bpjph.halal.go.id/regulasi/peraturan-bpjph",
        "filename": "BPJPH_2_2023.pdf",
        "strategy": "bpjph_direct",
    },
    "MUI_FATWA": {
        "name": "Fatwa MUI Tentang Halal (Kompilasi)",
        "url": "https://mui.or.id/fatwa/",
        "filename": "MUI_FATWA.pdf",
        "strategy": "mui_fatwa",
    },
    "LPH_PANDUAN": {
        "name": "Panduan Audit LPH (Kompilasi)",
        "url": "internal",
        "filename": "LPH_PANDUAN.pdf",
        "strategy": "manual",
    },
    "SNI_HALAL": {
        "name": "SNI 99001:2023 - HAS & SNI 3932 - Makanan Halal",
        "url": "https://www.bsn.go.id/",
        "filename": "SNI_HALAL.pdf",
        "strategy": "bsn",
    },
    "KOMINFO_9_2023": {
        "name": "Permenkominfo No. 9 Tahun 2023 - Aksesibilitas Digital",
        "url": "https://jdih.kominfo.go.id/",
        "filename": "KOMINFO_9_2023.pdf",
        "strategy": "kominfo",
    },
}


class RegulationDownloader:
    def __init__(self, download_dir: Path, headless: bool = True):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.results = {}

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context = await self.browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def download_bpjph_direct(self, source_id: str, config: dict) -> bool:
        """Download from BPJPH regulation pages - look for direct PDF links."""
        page = await self.context.new_page()
        try:
            logger.info(f"Navigating to {config['url']}")
            await self._safe_goto(page, config["url"])
            
            # Wait for content to load
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)  # Extra wait for JS rendering
            
            # Strategy: Find all links containing .pdf or "download"
            pdf_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links
                        .map(a => ({href: a.href, text: a.innerText.trim()}))
                        .filter(l => l.href.toLowerCase().includes('.pdf') || 
                                     l.text.toLowerCase().includes('download') ||
                                     l.text.toLowerCase().includes('pdf'));
                }
            """)
            
            logger.info(f"Found {len(pdf_links)} potential PDF links")
            
            # Filter for relevant PDF
            target_link = None
            for link in pdf_links:
                href = link['href'].lower()
                text = link['text'].lower()
                if any(keyword in href or keyword in text for keyword in [
                    source_id.lower().replace('_', ''),
                    config['filename'].replace('.pdf', '').lower().replace('_', ''),
                ]):
                    target_link = link
                    break
            
            # If not found by keyword, try first PDF link
            if not target_link and pdf_links:
                target_link = pdf_links[0]
            
            if not target_link:
                logger.warning(f"No PDF link found for {source_id}")
                return await self._try_fallback_download(source_id, config)
            
            logger.info(f"Downloading from: {target_link['href']}")
            return await self._download_via_link(page, target_link['href'], config['filename'])
            
        except Exception as e:
            logger.error(f"Error downloading {source_id}: {e}")
            return False
        finally:
            await page.close()

    async def download_mui_fatwa(self, source_id: str, config: dict) -> bool:
        """Download MUI Fatwa compilation page."""
        page = await self.context.new_page()
        try:
            logger.info(f"Navigating to {config['url']}")
            await self._safe_goto(page, config["url"])
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # MUI fatwa page - look for fatwa links
            fatwa_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links
                        .map(a => ({href: a.href, text: a.innerText.trim()}))
                        .filter(l => l.href.toLowerCase().includes('.pdf') &&
                                     (l.text.toLowerCase().includes('halal') ||
                                      l.text.toLowerCase().includes('fatwa')));
                }
            """)
            
            if not fatwa_links:
                logger.warning("No fatwa PDF links found on MUI page")
                return False
            
            # For compilation, we'd need to download multiple and merge
            # For now, download first one as sample
            first_link = fatwa_links[0]
            logger.info(f"Downloading MUI fatwa from: {first_link['href']}")
            return await self._download_via_link(page, first_link['href'], config['filename'])
            
        except Exception as e:
            logger.error(f"Error downloading MUI fatwa: {e}")
            return False
        finally:
            await page.close()

    async def download_kominfo(self, source_id: str, config: dict) -> bool:
        """Download from Kominfo JDih."""
        page = await self.context.new_page()
        try:
            await self._safe_goto(page, config["url"])
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Search for Permenkominfo 9/2023
            pdf_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links
                        .map(a => ({href: a.href, text: a.innerText.trim()}))
                        .filter(l => l.href.toLowerCase().includes('.pdf') &&
                                     (l.text.toLowerCase().includes('9') ||
                                      l.text.toLowerCase().includes('2023') ||
                                      l.text.toLowerCase().includes('aksesibilitas')));
                }
            """)
            
            if not pdf_links:
                logger.warning("No matching PDF links found on Kominfo page")
                return False
            
            return await self._download_via_link(page, pdf_links[0]['href'], config['filename'])
            
        except Exception as e:
            logger.error(f"Error downloading Kominfo: {e}")
            return False
        finally:
            await page.close()

    async def download_bsn(self, source_id: str, config: dict) -> bool:
        """Download from BSN - SNI standards typically require purchase."""
        logger.warning("SNI standards typically require purchase from BSN.")
        logger.info("Creating placeholder file. Please replace with actual purchased standard.")
        
        placeholder_path = self.download_dir / config['filename']
        placeholder_content = f"""# Placeholder for {config['name']}

This is a placeholder file. SNI standards (SNI 99001:2023, SNI 3932) 
are copyrighted standards sold by Badan Standardisasi Nasional (BSN).

To obtain the actual standards:
1. Visit https://www.bsn.go.id/
2. Purchase SNI 99001:2023 (Sistem Jaminan Halal) 
3. Purchase SNI 3932 (Makanan Halal)
4. Replace this file with the purchased PDFs.

For development/testing purposes, you can create a minimal version
with the key clauses needed for your RAG system.
"""
        (self.download_dir / config['filename']).write_text(placeholder_content, encoding='utf-8')
        return True

    async def download_manual(self, source_id: str, config: dict) -> bool:
        """Manual download placeholder."""
        logger.warning(f"{config['name']} requires manual download.")
        logger.info(f"Please obtain {config['filename']} manually and place in {self.download_dir}")
        return True

    # ============================================================
    # Helper Methods
    # ============================================================
    
    async def _safe_goto(self, page: Page, url: str, timeout: int = 60000):
        """Navigate with retry logic."""
        for attempt in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                return
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Navigation attempt {attempt+1} failed: {e}, retrying...")
                await asyncio.sleep(2)

    async def _download_via_link(self, page: Page, url: str, filename: str) -> bool:
        """Click link and wait for download."""
        try:
            # Navigate directly to PDF URL to trigger download
            async with page.expect_download(timeout=60000) as download_info:
                await page.goto(url, wait_until="networkidle", timeout=60000)
            download = await download_info.value
            
            # Save with our desired filename
            save_path = self.download_dir / filename
            await download.save_as(str(placeholder_path))
            
            # Verify file size
            file_size = placeholder_path.stat().st_size
            if file_size < 1000:  # Less than 1KB is suspicious
                logger.warning(f"Downloaded file very small ({file_size} bytes)")
                return False
            
            logger.success(f"Downloaded {filename} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    async def _try_fallback_download(self, source_id: str, config: dict) -> bool:
        """Try alternative download strategies."""
        logger.info(f"Trying fallback for {source_id}...")
        
        # Try direct PDF URL patterns
        fallback_urls = [
            config['url'].rstrip('/') + f"/{config['filename']}",
            config['url'].rstrip('/') + f"/download/{config['filename']}",
            f"https://bpjph.halal.go.id/assets/files/{config['filename']}",
        ]
        
        for url in fallback_urls:
            try:
                logger.info(f"Trying fallback URL: {url}")
                page = await self.context.new_page()
                async with page.expect_download(timeout=30000) as download_info:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                download = await download_info.value
                save_path = self.download_dir / config['filename']
                await download.save_as(str(save_path))
                
                if save_path.stat().st_size > 1000:
                    logger.success(f"Fallback download succeeded: {config['filename']}")
                    await page.close()
                    return True
                await page.close()
            except Exception as e:
                logger.debug(f"Fallback {url} failed: {e}")
        
        return False

    # ============================================================
    # Main orchestration
    # ============================================================
    
    async def run(self, sources: list[str] = None, force: bool = False) -> dict:
        """Run downloads for specified sources."""
        if sources is None:
            sources = list(REGULATION_SOURCES.keys())
        
        strategy_map = {
            "bpjph_direct": self.download_bpjph_direct,
            "mui_fatwa": self.download_mui_fatwa,
            "kominfo": self.download_kominfo,
            "bsn": self.download_bsn,
            "manual": self.download_manual,
        }
        
        results = {}
        for source_id in sources:
            if source_id not in REGULATION_SOURCES:
                logger.warning(f"Unknown source: {source_id}")
                results[source_id] = {"status": "unknown"}
                continue
            
            config = REGULATION_SOURCES[source_id]
            strategy = config.get("strategy", "manual")
            
            # Skip if already exists and not forced
            file_path = self.download_dir / config['filename']
            if file_path.exists() and not force:
                logger.info(f"{source_id}: Already exists, skipping (use --force to re-download)")
                results[source_id] = {"status": "skipped", "file": config['filename']}
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Downloading: {config['name']}")
            logger.info(f"Strategy: {strategy}")
            logger.info(f"{'='*60}")
            
            try:
                downloader = strategy_map.get(strategy, self.download_manual)
                success = await downloader(source_id, config)
                
                file_path = self.download_dir / config['filename']
                if file_path.exists() and file_path.stat().st_size > 1000:
                    results[source_id] = {
                        "status": "success",
                        "file": config['filename'],
                        "size": file_path.stat().st_size
                    }
                else:
                    results[source_id] = {"status": "failed", "error": "File not created or too small"}
                    
            except Exception as e:
                logger.error(f"Failed {source_id}: {e}")
                results[source_id] = {"status": "error", "error": str(e)}
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Indonesian Halal Regulations PDFs")
    parser.add_argument("--source", "-s", action="append", help="Specific source(s) to download")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-download existing files")
    parser.add_argument("--list", "-l", action="store_true", help="List available sources")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
    parser.add_argument("--output", "-o", default="data/downloads", help="Output directory")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available regulation sources:")
        for sid, config in REGULATION_SOURCES.items():
            print(f"  {sid}: {config['name']} -> {config['filename']} (strategy: {config['strategy']})")
        return
    
    download_dir = Path(args.output)
    download_dir.mkdir(parents=True, exist_ok=True)
    
    async def run():
        async with RegulationDownloader(download_dir, headless=args.headless) as downloader:
            results = await downloader.run(sources=args.source, force=args.force)
            
            print("\n" + "="*60)
            print("DOWNLOAD SUMMARY")
            print("="*60)
            for source_id, result in results.items():
                status = result.get('status', 'unknown')
                icon = {"success": "✅", "skipped": "⏭️", "failed": "❌", "error": "💥"}.get(status, "❓")
                print(f"  {icon} {source_id}: {status}")
                if result.get('file'):
                    print(f"    File: {result['file']} ({result.get('size', 0):,} bytes)")
                if result.get('error'):
                    print(f"    Error: {result['error']}")
    
    asyncio.run(run())


if __name__ == "__main__":
    main()