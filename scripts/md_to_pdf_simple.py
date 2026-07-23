#!/usr/bin/env python
"""
Convert markdown to PDF using pure Python (fpdf2 + markdown2)
No external system dependencies needed.
Run: python scripts/md_to_pdf_simple.py
"""
import os
import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from fpdf import FPDF
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "fpdf2"], check=True)
    from fpdf import FPDF


class MarkdownPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128)
            self.cell(0, 5, "LAPORAN UAS PROYEK DATA MINING (ST167)", align="L")
            self.cell(0, 5, f"Halaman {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.line(10, 12, 200, 12)
            self.ln(5)

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Halaman {self.page_no()}/{{nb}}", align="C")

    def write_h1(self, text):
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 12, text)
        self.set_text_color(0)
        self.ln(4)

    def write_h2(self, text):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 10, text)
        self.set_text_color(0)
        self.ln(3)

    def write_h3(self, text):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 9, text)
        self.set_text_color(0)
        self.ln(2)

    def write_h4(self, text):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 8, text)
        self.set_text_color(0)
        self.ln(2)

    def write_body(self, text):
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def write_blockquote(self, text):
        self.set_font("Helvetica", "I", 11)
        self.set_text_color(80)
        self.multi_cell(0, 5.5, text)
        self.set_text_color(0)
        self.set_font("Helvetica", "", 11)
        self.ln(2)

    def write_list_item(self, text, indent=1):
        self.set_font("Helvetica", "", 11)
        prefix = "  " * indent
        self.cell(10 * indent)
        self.multi_cell(0, 5.5, f"{prefix}{text}")
        self.ln(1)

    def write_code_block(self, lines):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        for line in lines:
            self.cell(0, 4, "  " + cleanse(line), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)

    def write_table_row(self, cells, is_header=False):
        self.set_font("Helvetica", "B" if is_header else "", 10)
        num_cells = len(cells)
        if num_cells == 0:
            return
        cell_w = 190 // num_cells
        for j, cell in enumerate(cells):
            border = 1 if is_header else 0
            self.cell(cell_w, 6, cleanse(cell.strip()), border=border)
        self.ln()

    def write_hr(self):
        self.ln(2)
        self.set_draw_color(200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_draw_color(0)
        self.ln(4)

    def add_title_page(self):
        self.add_page()
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(0, 51, 102)
        self.ln(40)
        self.cell(0, 15, "LAPORAN UAS", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 15, "PROYEK DATA MINING (ST167)", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(51)
        self.multi_cell(0, 10,
            "Sistem Multi-Agent untuk Otomatisasi\n"
            "Penilaian Kesiapan Sertifikasi Halal Koperasi\n"
            "Petani/Nelayan Kecil di Indonesia",
            align="C"
        )
        self.ln(15)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(100)
        infos = [
            "Mata Kuliah: Proyek Data Mining (ST167) - 4 SKS",
            "Dosen: Anna Baita, M.Kom | Kusnawi, S.Kom, M.Eng",
            "        Theopilus Bayu Sasongko, S.Kom., M.Eng",
            "Tim: [Nama 1] | [Nama 2] | [Nama 3]",
            "Universitas Amikom Yogyakarta | Agustus 2026",
        ]
        for info in infos:
            self.cell(0, 8, info, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(12)
        self.set_font("Helvetica", "I", 10)
        self.cell(0, 6, "Repository: github.com/Radityaaa04/halal-koperasi-agent", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, "Demo: halal-koperasi-agent.streamlit.app", align="C", new_x="LMARGIN", new_y="NEXT")


def clean_markdown(text):
    """Remove complex blocks."""
    text = re.sub(r'```mermaid[\s\S]*?```', '', text)
    text = re.sub(r'<!--[\s\S]*?-->', '', text)
    return text


def cleanse(text):
    """Remove all non-Latin-1 characters from text."""
    charset = {
        '\u2014': '--', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...',
        '\u2192': '->', '\u00d7': 'x', '\u2265': '>=', '\u2264': '<=',
        '\u03c1': 'p', '\u2713': 'V', '\u2705': 'OK', '\u274c': 'NO',
        '\u250c': '+', '\u2500': '-', '\u2510': '+', '\u2502': '|',
        '\u2514': '+', '\u2518': '+', '\u251c': '+', '\u2524': '+',
        '\u252c': '+', '\u2534': '+', '\u253c': '+',
    }
    for uni, repl in charset.items():
        text = text.replace(uni, repl)
    # Aggressive: replace anything outside Latin-1
    return text.encode('latin-1', errors='replace').decode('latin-1')


def boldify(text):
    """Convert **bold** and _italic_ to plain text."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    return cleanse(text)


def parse_markdown_section(pdf, section):
    """Parse markdown lines and write to PDF."""
    lines = section.split('\n')
    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        line = lines[i]

        # Skip empty
        if not line.strip():
            i += 1
            continue

        stripped = line.strip()

        # Code fence
        if stripped.startswith('```'):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                if code_buf:
                    pdf.write_code_block(code_buf)
                in_code = False
                code_buf = []
            i += 1
            continue

        if in_code:
            code_buf.append(stripped)
            i += 1
            continue

        # Clean bold/italic
        text = boldify(stripped)

        # Headers
        if stripped.startswith('# '):
            pdf.write_h1(text[2:])
        elif stripped.startswith('## '):
            pdf.write_h2(text[3:])
        elif stripped.startswith('### '):
            pdf.write_h3(text[4:])
        elif stripped.startswith('#### '):
            pdf.write_h4(text[5:])

        # HR
        elif stripped == '---' or stripped == '---':
            pdf.write_hr()

        # Blockquote
        elif stripped.startswith('> '):
            pdf.write_blockquote(text[2:])

        # Table
        elif stripped.startswith('|'):
            # Skip separator like |---|---|
            if re.match(r'^\|[-:\s|]+\|$', stripped):
                pass
            else:
                row = [c.strip() for c in stripped.split('|')[1:-1]]
                is_header = (i + 1 < len(lines) and
                             lines[i + 1].strip().startswith('|') and
                             '---' in lines[i + 1])
                pdf.write_table_row(row, is_header)
        # List
        elif stripped.startswith('- ') or stripped.startswith('* '):
            pdf.write_list_item(text[2:])
        elif re.match(r'^\d+\.\s', stripped):
            pdf.write_list_item(text)
        else:
            pdf.write_body(text)
        i += 1

    # leftover code
    if in_code and code_buf:
        pdf.write_code_block(code_buf)


def markdown_to_pdf(md_path, pdf_path):
    print(f"📄 Reading {md_path}...")
    with open(md_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    raw = clean_markdown(raw)

    # Split on HR
    sections = re.split(r'\n---\n', raw)

    pdf = MarkdownPDF()
    pdf.alias_nb_pages()

    # Title page
    pdf.add_title_page()

    # Process each section
    for i, section in enumerate(sections):
        if i > 0:
            pdf.add_page()
        parse_markdown_section(pdf, section)

    pdf.output(pdf_path)
    size = os.path.getsize(pdf_path) / 1024
    print(f"\n✅ PDF generated!")
    print(f"   File: {pdf_path}")
    print(f"   Pages: {pdf.pages_count}")
    print(f"   Size: {size:.1f} KB")


if __name__ == "__main__":
    MD = PROJECT_ROOT / "docs" / "LAPORAN_UAS.md"
    PDF = PROJECT_ROOT / "docs" / "LAPORAN_UAS.pdf"
    if not MD.exists():
        print(f"❌ Not found: {MD}")
        sys.exit(1)
    markdown_to_pdf(MD, PDF)