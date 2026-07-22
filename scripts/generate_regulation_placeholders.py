#!/usr/bin/env python3
"""Generate placeholder regulation PDFs from text files using PyMuPDF."""

import argparse
from pathlib import Path
import fitz

BASE_DIR = Path(__file__).parent.parent
CONTENT_DIR = BASE_DIR / "data" / "regulation_texts"
SOURCES = {
    "UU_33_2014":   "UU No. 33 Tahun 2014",
    "PP_39_2021":   "PP No. 39 Tahun 2021",
    "BPJPH_1_2023": "BPJPH No. 1 Tahun 2023",
    "BPJPH_2_2023": "BPJPH No. 2 Tahun 2023",
    "MUI_FATWA":    "Fatwa MUI",
    "LPH_PANDUAN":  "Panduan LPH",
    "SNI_HALAL":    "SNI 99001 (HAS)",
    "KOMINFO_9_2023": "Kominfo No. 9",
}
LINE_PER_PAGE = 55
CHARS_PER_LINE = 80


def create_pdf_from_text(txt_path: Path, pdf_path: Path) -> Path:
    text = txt_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    
    pages = []
    current = []
    lc = 0
    
    for line in lines:
        wraps = max(1, (len(line) // CHARS_PER_LINE) + 1)
        current.append(line)
        lc += wraps
        if lc >= LINE_PER_PAGE:
            pages.append("\n".join(current))
            current = []
            lc = 0
    
    if current:
        pages.append("\n".join(current))
    
    doc = fitz.open()
    for chunk in pages:
        page = doc.new_page()
        rect = fitz.Rect(50, 50, 545, 792)
        page.insert_textbox(rect, chunk, fontname="helv", fontsize=10, align=0)
    
    doc.save(str(pdf_path))
    doc.close()
    return True


def main():
    p = argparse.ArgumentParser(description="Generate placeholder regulation PDFs")
    p.add_argument("--output", "-o", default="data/downloads")
    p.add_argument("--force", "-f", action="store_true")
    p.add_argument("--list", "-l", action="store_true")
    args = p.parse_args()
    
    if args.list:
        for src, desc in SOURCES.items():
            tf = CONTENT_DIR / f"{src}.txt"
            print(f"{'✅' if tf.exists() else '❌'} {src}: {desc}")
        return
    
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    
    ok = 0
    for src, desc in SOURCES.items():
        tf = CONTENT_DIR / f"{src}.txt"
        pf = out / f"{src}.pdf"
        
        if not tf.exists():
            print(f"❌ {src}: no text file")
            continue
        if pf.exists() and not args.force:
            print(f"⏭️ {src}: exists")
            ok += 1
            continue
        
        try:
            create_pdf_from_text(tf, pf)
            size = pf.stat().st_size
            print(f"✅ {src}: {size:,} B")
            ok += 1
        except Exception as e:
            print(f"❌ {src}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{ok}/{len(SOURCES)} PDFs generated to {out.absolute()}")


if __name__ == "__main__":
    main()