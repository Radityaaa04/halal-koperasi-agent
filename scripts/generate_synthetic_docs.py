#!/usr/bin/env python3
"""
Synthetic Document Generator for Halal Certification System
Generates realistic PDF documents for koperasi test cases based on YAML profiles and Jinja2 templates.
Uses reportlab (pure Python, no GTK required).
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Frame, PageTemplate, BaseDocTemplate
)
from reportlab.lib import colors

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from halal_koperasi_agent.utils import create_jinja_env, format_currency, _strftime

# Document type to template mapping
DOC_TEMPLATES = {
    "AKTA_PENDIRIAN": "akta_pendirian.md.j2",
    "ANGGARAN_DASAR": "anggaran_dasar.md.j2",
    "NPWP": "npwp.md.j2",
    "NIB": "nib.md.j2",
    "IZIN_USAHA": "izin_usaha.md.j2",
    "SOP_PRODUKSI": "sop_produksi.md.j2",
    "DAFTAR_BAHAN_BAKU": "daftar_bahan_baku.md.j2",
    "RUTE_PRODUKSI": "rute_produksi.md.j2",
    "SERTIFIKAT_HALAL_BAHAN": "sertifikat_halal_bahan.md.j2",
    "LAYOUT_FASILITAS": "layout_fasilitas.md.j2",
    "ORGANOGRAM_HAS": "organogram_has.md.j2",
    "BUKTI_PELATIHAN_HAS": "bukti_pelatihan_has.md.j2",
}

# Required documents per PP 39/2021 & BPJPH Peraturan 1/2023
REQUIRED_DOCS = [
    "AKTA_PENDIRIAN", "ANGGARAN_DASAR", "NPWP", "NIB", "IZIN_USAHA",
    "SOP_PRODUKSI", "DAFTAR_BAHAN_BAKU", "RUTE_PRODUKSI",
    "SERTIFIKAT_HALAL_BAHAN", "LAYOUT_FASILITAS", "ORGANOGRAM_HAS", "BUKTI_PELATIHAN_HAS",
]


class ReportLabPDFBuilder:
    """Build PDFs from markdown-like content using reportlab."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            'CustomTitle', parent=self.styles['Title'],
            fontSize=18, textColor=HexColor('#1a3a5c'), spaceAfter=12,
            borderWidth=0, borderPadding=0,
        ))
        self.styles.add(ParagraphStyle(
            'CustomHeading1', parent=self.styles['Heading1'],
            fontSize=14, textColor=HexColor('#2c5f8a'), spaceBefore=18, spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            'CustomHeading2', parent=self.styles['Heading2'],
            fontSize=12, textColor=HexColor('#3a7ab5'), spaceBefore=12, spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            'CustomBody', parent=self.styles['Normal'],
            fontSize=10, leading=14, textColor=HexColor('#333333'),
            alignment=TA_JUSTIFY, spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            'CustomCenter', parent=self.styles['Normal'],
            fontSize=10, leading=14, alignment=TA_CENTER, textColor=HexColor('#666666'),
        ))
        self.styles.add(ParagraphStyle(
            'TableHeader', parent=self.styles['Normal'],
            fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            'TableCell', parent=self.styles['Normal'],
            fontSize=8, leading=10, textColor=HexColor('#333333'), alignment=TA_LEFT,
        ))
        self.styles.add(ParagraphStyle(
            'Footer', parent=self.styles['Normal'],
            fontSize=8, leading=10, alignment=TA_CENTER, textColor=HexColor('#666666'),
        ))
    
    def markdown_to_elements(self, markdown: str) -> list:
        """Convert simple markdown to reportlab flowables."""
        elements = []
        lines = markdown.split('\n')
        in_table = False
        table_rows = []
        
        for line in lines:
            line = line.rstrip()
            
            # Skip empty
            if not line.strip():
                if in_table and table_rows:
                    elements.append(self._build_table(table_rows))
                    table_rows = []
                    in_table = False
                elements.append(Spacer(1, 6))
                continue
            
            # Table detection
            if '|' in line and line.count('|') >= 2:
                if not in_table:
                    in_table = True
                    table_rows = []
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                table_rows.append(cells)
                continue
            
            # If was in table, flush it
            if in_table:
                if table_rows:
                    elements.append(self._build_table(table_rows))
                    table_rows = []
                in_table = False
            
            # Headings
            if line.startswith('### '):
                elements.append(Paragraph(line[4:].strip(), self.styles['CustomHeading2']))
            elif line.startswith('## '):
                elements.append(Paragraph(line[3:].strip(), self.styles['CustomHeading1']))
            elif line.startswith('# '):
                elements.append(Paragraph(line[2:].strip(), self.styles['CustomTitle']))
            # Horizontal rule
            elif line.startswith('---') or line.startswith('==='):
                elements.append(Spacer(1, 12))
            # Bold/italic in body (simple inline)
            else:
                # Convert markdown inline: **bold** -> <b>text</b>, *italic* -> <i>text</i>
                text = line
                import re
                # Replace **text** with <b>text</b> (non-greedy)
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                # Replace *text* with <i>text</i> (non-greedy, but not inside <b>)
                text = re.sub(r'(?<!<b>)\*(.+?)\*(?!</b>)', r'<i>\1</i>', text)
                elements.append(Paragraph(text, self.styles['CustomBody']))
        
        # Flush remaining table
        if table_rows:
            elements.append(self._build_table(table_rows))
        
        return elements
    
    def _build_table(self, rows: list) -> Table:
        """Build a styled table from rows of cells."""
        if not rows:
            return Spacer(1, 6)
        
        # Convert to Paragraphs
        data = []
        for row in rows:
            data.append([Paragraph(cell, self.styles['TableCell']) for cell in row])
        
        # Style: header row different
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]
        # Alternate row colors
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle(style_cmds))
        return table
    
    def build_pdf(self, elements: list, output_path: Path, title: str = ""):
        """Build PDF from flowables."""
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(HexColor('#666666'))
            page_num = doc.page
            canvas.drawCentredString(A4[0]/2, 15*mm, f"{page_num}")
            canvas.restoreState()
        
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        
        # Add title page info if provided
        if title:
            elements.insert(0, Paragraph(title, self.styles['CustomTitle']))
            elements.insert(1, Spacer(1, 20))
        
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)


class SyntheticDocGenerator:
    def __init__(self, profiles_dir: Path, templates_dir: Path, output_dir: Path):
        self.profiles_dir = profiles_dir
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.env = create_jinja_env(templates_dir)
        self.pdf_builder = ReportLabPDFBuilder()
    
    def load_profile(self, profile_name: str) -> dict:
        profile_path = self.profiles_dir / f"{profile_name}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")
        with open(profile_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def prepare_context(self, profile: dict, doc_type: str) -> dict:
        k = profile['koperasi']
        err = profile.get('error_injection', {})
        
        # Base context
        ctx = {
            'nama_koperasi': k['nama'],
            'kode_koperasi': k['id'].replace('-', ''),
            'versi': '01/Rev-0',
            'tanggal_berlaku': datetime.now().strftime('%Y-%m-%d'),
            'tanggal': datetime.now().strftime('%Y-%m-%d'),
            'format_currency': format_currency,
            'strftime': _strftime,
            'datetime': datetime,
        }
        
        # Add profile-specific data
        ctx.update({
            'nama_pimpinan': k['nama_pimpinan'],
            'nik_pimpinan': k['nik_pimpinan'],
            'alamat_kedudukan': f"{k['alamat']['desa_kelurahan']}, {k['alamat']['kecamatan']}, {k['alamat']['kabupaten_kota']}",
            'rt_rw': k['alamat'].get('rincian', '').split('RT ')[-1] if 'RT' in k['alamat'].get('rincian', '') else '01/01',
            'kelurahan': k['alamat']['desa_kelurahan'],
            'kecamatan': k['alamat']['kecamatan'],
            'kabupaten_kota': k['alamat']['kabupaten_kota'],
            'provinsi': k['alamat']['provinsi'],
            'kode_pos': k['alamat']['kode_pos'],
            'telepon': k['kontak'].get('telepon', ''),
            'email': k['kontak'].get('email', ''),
            'website': k['kontak'].get('website', ''),
            'jenis_koperasi': 'Produsen' if 'perikanan' in k['profil_usaha']['bidang_usaha'].lower() else 'Koperasi Produsen',
            'maksud_tujuan': 'Meningkatkan kesejahteraan anggota melalui usaha bersama di bidang ' + k['profil_usaha']['bidang_usaha'].lower(),
            'kegiatan_usaha': '\n'.join([f'{i+1}. {p["nama"]}' for i, p in enumerate(k['profil_usaha']['produk_utama'])]),
            'modal_dasar': k['profil_usaha'].get('modal_dasar', 0),
            'modal_wajib': k['profil_usaha'].get('modal_wajib', 50000000),
            'modal_sukarela': k['profil_usaha'].get('modal_sukarela', 100000000),
            'simpanan_pokok_min': 100000,
            'simpanan_wajib_min': 50000,
            'masa_jabatan': '5 tahun',
            'max_anggota_pengurus': 5,
            'jumlah_pengawas': 3,
            'masa_jabatan_tahun': 5,
        })
        
        # Pengurus for AKTA
        ctx['pengurus'] = k.get('pengurus', [
            {'nama': k['nama_pimpinan'], 'nik': k['nik_pimpinan'], 'jabatan': 'Ketua', 'alamat': k['alamat']['desa_kelurahan'], 'pekerjaan': 'Pengusaha'},
            {'nama': k['kontak'].get('cp_nama', 'Sekretaris'), 'nik': '3578012345678902', 'jabatan': 'Sekretaris', 'alamat': k['alamat']['desa_kelurahan'], 'pekerjaan': 'Karyawan'},
            {'nama': 'Bendahara', 'nik': '3578012345678903', 'jabatan': 'Bendahara', 'alamat': k['alamat']['desa_kelurahan'], 'pekerjaan': 'Karyawan'},
        ])
        ctx['pengurus_list'] = ctx['pengurus']
        ctx['pengawas_list'] = [
            {'jabatan': 'Ketua Pengawas', 'nama': 'Pengawas Utama', 'nik': '3578012345678904', 'alamat': k['alamat']['desa_kelurahan']},
        ]
        ctx['tempat_akta'] = k['alamat']['kabupaten_kota']
        ctx['saksi1_nama'] = 'Saksi Satu'; ctx['saksi1_nik'] = '3578012345678905'
        ctx['saksi2_nama'] = 'Saksi Dua'; ctx['saksi2_nik'] = '3578012345678906'
        ctx['nomor_pendaftaran'] = f"{k['id']}/K/{datetime.now().year}"
        ctx['tanggal_pendaftaran'] = datetime.now().strftime('%Y-%m-%d')
        ctx['instansi_pendaftaran'] = f"Dinas Koperasi {k['alamat']['kabupaten_kota']}"
        ctx['tanggal_pengesahan'] = datetime.now().strftime('%Y-%m-%d')
        ctx['nama_pemerintah_daerah'] = f"Kepala Dinas Koperasi {k['alamat']['kabupaten_kota']}"
        ctx['nama_ketua'] = k['nama_pimpinan']
        ctx['nama_sekretaris'] = k['kontak'].get('cp_nama', 'Sekretaris')
        ctx['nama_bendahara'] = 'Bendahara'
        
        # NPWP
        ctx['npwp_number'] = f"{k['id'][-4:]}.{k['id'][-4:]}.{k['id'][-4:]}.{k['id'][-3:]}"
        ctx['nama_wp'] = k['nama']
        ctx['alamat_wp'] = ctx['alamat_kedudukan']
        ctx['kpp'] = f"KPP {k['alamat']['kabupaten_kota']}"
        ctx['status_wp'] = 'aktif'
        ctx['tanggal_daftar'] = '2020-01-15'
        ctx['tanggal_terbit_kartu'] = '2020-01-20'
        ctx['cara_daftar'] = 'Online (DJP Online)'
        ctx['klu_list'] = [k['profil_usaha']['kbli_utama']]
        ctx['fasilitas_perpajakan'] = 'Belum memanfaatkan'
        ctx['npwp_pusat'] = ''; ctx['npwp_cabang'] = ''
        ctx['tanggal_cetak'] = datetime.now().strftime('%Y-%m-%d')
        ctx['kode_verifikasi'] = f"NPWP-{k['id']}-{datetime.now().strftime('%Y%m%d')}"
        
        # NIB
        ctx['nib_number'] = f"9120{k['id'][-6:]}"
        ctx['nama_usaha'] = k['nama']
        ctx['alamat_usaha'] = ctx['alamat_kedudukan']
        ctx['kbli_utama'] = k['profil_usaha']['kbli_utama']
        ctx['kbli_list'] = [{'kode': c, 'nama': 'Pengolahan Hasil Perikanan', 'status': 'Utama' if c == k['profil_usaha']['kbli_utama'] else 'Tambahan'} for c in k['profil_usaha']['kbli_detail']]
        ctx['status_nib'] = 'Aktif'
        ctx['tanggal_terbit'] = '2020-01-15'
        ctx['tanggal_berlaku'] = '2025-01-15'
        ctx['nama_pemilik'] = k['nama_pimpinan']
        ctx['nik_pemilik'] = k['nik_pimpinan']
        ctx['jk_pemilik'] = 'Laki-laki'
        ctx['tempat_lahir_pemilik'] = k['alamat']['kabupaten_kota']
        ctx['tgl_lahir_pemilik'] = '1970-01-01'
        ctx['kewarganegaraan_pemilik'] = 'WNI'
        ctx['alamat_ktp_pemilik'] = ctx['alamat_kedudukan']
        ctx['modal_disetor'] = k['profil_usaha'].get('modal_dasar', 0)
        ctx['nilai_investasi'] = k['profil_usaha'].get('modal_dasar', 0)
        ctx['tenaga_kerja'] = k['profil_usaha'].get('jumlah_karyawan', 0)
        ctx['tk_laki'] = k['profil_usaha'].get('jumlah_karyawan', 0) // 2
        ctx['tk_perempuan'] = k['profil_usaha'].get('jumlah_karyawan', 0) // 2
        ctx['luas_tanah'] = k['fasilitas_produksi'].get('unit_pengolahan_m2', 100)
        ctx['luas_bangunan'] = k['fasilitas_produksi'].get('unit_pengolahan_m2', 100)
        ctx['sku_nomor'] = f"SKU-{k['id']}"
        ctx['sku_tgl_terbit'] = '2020-01-15'
        ctx['sku_tgl_berlaku'] = '2025-01-15'
        ctx['sku_status'] = 'Aktif'
        ctx['bpom_nomor'] = k['fasilitas_produksi'].get('sertifikat_lain', [''])[0] if k['fasilitas_produksi'].get('sertifikat_lain') else 'Belum ada'
        ctx['bpom_tgl_terbit'] = '2020-02-01'
        ctx['bpom_tgl_berlaku'] = '2025-02-01'
        ctx['bpom_status'] = 'Aktif'
        ctx['halal_nomor'] = 'Belum bersertifikat'
        ctx['halal_tgl_terbit'] = ''
        ctx['halal_tgl_berlaku'] = ''
        ctx['halal_status'] = 'Belum mengajukan'
        ctx['tdup_nomor'] = f"TDUP-{k['id']}"
        ctx['tdup_tgl_terbit'] = '2020-01-15'
        ctx['tdup_tgl_berlaku'] = '2025-01-15'
        ctx['tdup_status'] = 'Aktif'
        ctx['zonasi'] = 'Industri Ringan'
        ctx['hak_tanah'] = 'Hak Milik'
        ctx['jarak_permukiman'] = 1.5
        ctx['akses_jalan'] = 'Jalan Kolektor'
        ctx['amdal_nomor'] = 'Tidak memerlukan AMDAL'
        ctx['amdal_tanggal'] = ''
        ctx['amdal_status'] = 'Tidak wajib'
        ctx['ukl_upl_nomor'] = f"UKL-{k['id']}"
        ctx['ukl_upl_tanggal'] = '2020-01-15'
        ctx['ukl_upl_status'] = 'Disetujui'
        ctx['sppl_nomor'] = ''
        ctx['sppl_tanggal'] = ''
        ctx['sppl_status'] = ''
        ctx['verifikasi_oss'] = 'Terverifikasi'
        ctx['pembaruan_terakhir'] = datetime.now().strftime('%Y-%m-%d')
        ctx['kode_verifikasi'] = f"NIB-{k['id']}-{datetime.now().strftime('%Y%m%d')}"
        
        # Izin Usaha
        ctx['izin_nomor'] = f"IU-{k['id']}-{datetime.now().year}"
        ctx['izin_jenis'] = 'SKTU'
        ctx['izin_status'] = 'Aktif'
        ctx['izin_tgl_terbit'] = datetime.now().strftime('%Y-%m-%d')
        ctx['izin_tgl_berlaku'] = (datetime.now().replace(year=datetime.now().year+5)).strftime('%Y-%m-%d')
        ctx['izin_instansi'] = f"Dinas Koperasi {k['alamat']['kabupaten_kota']}"
        ctx['dasar_hukum'] = 'UU No. 25/2008 jo UU No. 7/2014'
        ctx['zonasi_status'] = 'Sesuai RTRW'
        ctx['zonasi_keterangan'] = 'Kawasan industri ringan'
        ctx['k3_status'] = 'Memenuhi'
        ctx['k3_keterangan'] = 'APAR, jalur evakuasi, P3K tersedia'
        ctx['amdal_status'] = 'Tidak wajib AMDAL (UKL-UPL)'
        ctx['amdal_keterangan'] = 'UKL-UPL disetujui'
        ctx['kesehatan_status'] = 'Lolos pemeriksaan'
        ctx['kesehatan_keterangan'] = 'Dinas Kesehatan'
        ctx['masa_berlaku_tahun'] = 5
        
        # Products
        ctx['produk_list'] = k['profil_usaha']['produk_utama']
        
        # SOP Produksi
        produk = ctx['produk_list'][0] if ctx['produk_list'] else {}
        ctx['kode_produk'] = produk.get('sku', 'PRD001')
        ctx['total_halaman'] = 8
        ctx['tgl_revisi'] = datetime.now().strftime('%Y-%m-%d')
        ctx['deskripsi_revisi'] = 'Versi awal untuk persiapan sertifikasi halal'
        ctx['tgl_persetujuan'] = datetime.now().strftime('%Y-%m-%d')
        ctx['nama_pimpinan'] = k['nama_pimpinan']
        ctx['nama_ketua_has'] = k['kontak'].get('cp_nama', 'Koordinator HAS')
        ctx['nama_produk'] = produk.get('nama', 'Produk Utama')
        ctx['nama_unit'] = k['nama']
        ctx['alamat_unit'] = ctx['alamat_kedudukan']
        cap_key = list(k['profil_usaha']['kapasitas_produksi_bulan'].keys())[0] if k['profil_usaha']['kapasitas_produksi_bulan'] else ''
        ctx['kapasitas_bulan'] = k['profil_usaha']['kapasitas_produksi_bulan'].get(cap_key, 500) if cap_key else 500
        
        # Production steps for SOP
        if 'Ikan' in k['profil_usaha']['bidang_usaha'] or 'perikanan' in k['profil_usaha']['bidang_usaha'].lower():
            ctx['langkah_produksi'] = [
                {"urutan": 1, "nama_tahap": "Penerimaan Bahan Baku Ikan", "deskripsi": "Penerimaan ikan segar dari nelayan/pelelangan", "peralatan": ["Timbangan digital", "Keranjang plastik", "Es kristal"], "parameter_kontrol": ["Suhu < 10°C", "Organoleptik (bau, warna, tekstur)"], "is_ccp": False, "pic": "Koordinator Gudang"},
                {"urutan": 2, "nama_tahap": "Pencucian & Pembuangan Isi Perut", "deskripsi": "Pencucian ikan dengan air bersih, pembuangan isi perut dan insang", "peralatan": ["Meja kerja stainless", "Air bersih bertekanan", "Pisau fillet"], "parameter_kontrol": ["Air jernih, bebas bau", "Suhu air < 15°C"], "is_ccp": True, "ccp_number": "1", "batas_kritis": "Air bersih, suhu < 15°C", "pemantauan": "Visual & termometer setiap batch", "frekuensi": "Setiap batch", "pic": "Operator Produksi"},
                {"urutan": 3, "nama_tahap": "Pengasapan/Penggorengan", "deskripsi": "Pengasapan ikan dengan kayu nangka / penggorengan", "peralatan": ["Asap oven / fryer", "Termometer inti", "Rak asap"], "parameter_kontrol": ["Suhu inti ikan > 70°C", "Waktu asap/goreng memadai"], "is_ccp": True, "ccp_number": "2", "batas_kritis": "Suhu inti > 70°C minimal 2 menit", "pemantauan": "Termometer inti setiap batch", "frekuensi": "Setiap batch", "pic": "Koordinator Produksi"},
                {"urutan": 4, "nama_tahap": "Pendinginan", "deskripsi": "Pendinginan cepat produk hingga suhu ruang", "peralatan": ["Rak pendingin", "Kipas pendingin"], "parameter_kontrol": ["Suhu ruang dalam 2 jam"], "is_ccp": False, "pic": "Operator Produksi"},
                {"urutan": 5, "nama_tahap": "Kemasan & Pelabelan", "deskripsi": "Kemasan vacuum, pelabelan produk", "peralatan": ["Mesin vacuum sealer", "Label printer", "Box karton"], "parameter_kontrol": ["Integritas kemasan", "Label halal benar", "Kode batch tertera"], "is_ccp": True, "ccp_number": "3", "batas_kritis": "Kemasan utuh, label benar", "pemantauan": "Visual setiap kemasan", "frekuensi": "Setiap kemasan", "pic": "Koordinator QC"},
                {"urutan": 6, "nama_tahap": "Penyimpanan & Distribusi", "deskripsi": "Penyimpanan cold storage & pengiriman", "peralatan": ["Cold storage -18°C", "Kendaraan distribusi"], "parameter_kontrol": ["Suhu cold storage -18°C", "Cold chain maintained"], "is_ccp": False, "pic": "Koordinator Gudang"},
            ]
            ctx['ccp_points'] = [
                {"ccp_id": "CCP-1", "nama": "Pencucian & Pembuangan Isi Perut", "hazards": "Kontaminasi mikroba (Salmonella, E. coli)", "batas_kritis": "Air bersih, suhu < 15°C", "pemantauan": "Visual air + termometer", "tindakan_koreksi": "Ganti air, cuci ulang", "verifikasi": "Lab mikroba harian", "pencatatan": "Form CCP-01"},
                {"ccp_id": "CCP-2", "nama": "Pengasapan/Penggorengan", "hazards": "Bakteri patogen sopravvive", "batas_kritis": "Suhu inti > 70°C minimal 2 menit", "pemantauan": "Termometer inti", "tindakan_koreksi": "Tambah waktu/ suhu", "verifikasi": "Lab mikroba produk jadi", "pencatatan": "Form CCP-02"},
                {"ccp_id": "CCP-3", "nama": "Kemasan & Pelabelan", "hazards": "Kontaminasi silang, label salah", "batas_kritis": "Kemasan utuh, label halal benar", "pemantauan": "Visual 100%", "tindakan_koreksi": "Kemasan ulang / label ulang", "verifikasi": "Audit internal mingguan", "pencatatan": "Form CCP-03"},
            ]
        else:
            ctx['langkah_produksi'] = [
                {"urutan": 1, "nama_tahap": "Penerimaan", "deskripsi": "Penerimaan bahan baku", "peralatan": ["Timbangan"], "parameter_kontrol": ["Kualitas"], "is_ccp": False, "pic": "Gudang"},
                {"urutan": 2, "nama_tahap": "Pengolahan", "deskripsi": "Proses produksi", "peralatan": ["Peralatan produksi"], "parameter_kontrol": ["Proses standar"], "is_ccp": True, "ccp_number": "1", "batas_kritis": "Sesuai SOP", "pemantauan": "Visual setiap batch", "frekuensi": "Setiap batch", "pic": "Koordinator Produksi"},
                {"urutan": 3, "nama_tahap": "Kemasan", "deskripsi": "Kemasan produk jadi", "peralatan": ["Mesin kemasan"], "parameter_kontrol": ["Integritas kemasan", "Label benar"], "is_ccp": True, "ccp_number": "2", "batas_kritis": "Kemasan utuh, label benar", "pemantauan": "Visual", "frekuensi": "Setiap kemasan", "pic": "Koordinator QC"},
            ]
            ctx['ccp_points'] = [
                {"ccp_id": "CCP-1", "nama": "Pengolahan", "hazards": "Kontaminasi proses", "batas_kritis": "Sesuai SOP", "pemantauan": "Visual", "tindakan_koreksi": "Ulangi proses", "verifikasi": "Audit internal", "pencatatan": "Form CCP-01"},
                {"ccp_id": "CCP-2", "nama": "Kemasan", "hazards": "Kontaminasi silang", "batas_kritis": "Kemasan utuh, label benar", "pemantauan": "Visual 100%", "tindakan_koreksi": "Kemasan ulang", "verifikasi": "Audit mingguan", "pencatatan": "Form CCP-02"},
            ]
        
        # Daftar Bahan Baku
        ctx['bahan_baku_list'] = []
        for p in k['profil_usaha']['produk_utama']:
            for bb in p.get('bahan_baku', []):
                ctx['bahan_baku_list'].append({
                    'nama': bb,
                    'sumber': 'Supplier terdaftar',
                    'kategori': 'Risiko Sedang' if 'ikan' in bb.lower() else 'Risiko Rendah',
                    'sertifikat_halal': 'Ada' if 'ikan' not in bb.lower() else 'Mengajukan',
                    'jumlah_bulan': 100,
                    'satuan': 'kg',
                    'catatan': '',
                })
        
        # Rute Produksi
        ctx['rute_produksi'] = k.get('rute_produksi', ctx['langkah_produksi'])
        
        # Sertifikat Halal Bahan
        ctx['sertifikat_halal_list'] = []
        for p in k['profil_usaha']['produk_utama']:
            for bb in p.get('bahan_baku', []):
                ctx['sertifikat_halal_list'].append({
                    'bahan': bb,
                    'supplier': 'Supplier terdaftar',
                    'nomor_sertifikat': f'HALAL-{bb[:3].upper()}-2024',
                    'tgl_terbit': '2024-01-15',
                    'tgl_berlaku': '2026-01-15',
                    'penerbit': 'LPH/MUI',
                    'status': 'Aktif',
                })
        
        # Layout Fasilitas
        ctx['layout_zones'] = [
            {"zona": "Zona Kotor", "ruang": "Penerimaan & Pencucian", "luas_m2": 30, "aktivitas": "Penerimaan ikan, pencucian, pembuangan isi perut", "peralatan": "Timbangan, spray washer, meja kerja", "akses": "Dari luar langsung"},
            {"zona": "Zona Bersih", "ruang": "Pengolahan (Asap/Goreng)", "luas_m2": 40, "aktivitas": "Pengasapan, penggorengan, pendinginan", "peralatan": "Asap oven, fryer, rak pendingin", "akses": "Dari zona kotor via air lock"},
            {"zona": "Zona Steril", "ruang": "Kemasan & QC", "luas_m2": 25, "aktivitas": "Kemasan vacuum, pelabelan, pemeriksaan QC", "peralatan": "Vacuum sealer, label printer, mikroskop", "akses": "Dari zona bersih via air lock"},
            {"zona": "Zona Penunjang", "ruang": "Gudang Bahan Baku & Produk Jadi", "luas_m2": 35, "aktivitas": "Penyimpanan bahan baku & produk jadi -18°C", "peralatan": "Cold storage, rak gondola", "akses": "Dari luar & zona bersih"},
        ]
        
        # Organogram HAS
        ctx['ketua_has'] = {
            'nama': k['kontak'].get('cp_nama', 'Koordinator HAS'),
            'jabatan': 'Ketua Tim HAS',
            'nik': '3578012345678910',
            'pendidikan': 'S1 Teknologi Pangan',
            'sertifikat': 'HAS-INT-001',
            'masa_berlaku': '2026-06-15',
        }
        ctx['anggota_has'] = [
            {'nama': 'Operator QC 1', 'jabatan_has': 'Anggota QC', 'nik': '3578012345678911', 'pendidikan': 'D3 Kimia', 'sertifikat': 'HAS-INT-002', 'masa_berlaku': '2026-06-15'},
            {'nama': 'Koordinator Gudang', 'jabatan_has': 'Anggota Gudang', 'nik': '3578012345678912', 'pendidikan': 'SMA', 'sertifikat': 'HAS-INT-003', 'masa_berlaku': '2026-06-15'},
            {'nama': 'Koordinator Produksi', 'jabatan_has': 'Anggota Produksi', 'nik': '3578012345678913', 'pendidikan': 'S1 Teknologi Pangan', 'sertifikat': 'HAS-INT-004', 'masa_berlaku': '2026-06-15'},
        ]
        ctx['training_plan'] = {
            'tahun': datetime.now().year,
            'pelatihan': [
                {'topik': 'Sistem Jaminan Halal (SJH)', 'tanggal': f'{datetime.now().year}-02-15', 'peserta': 'Semua tim HAS', 'penyelenggara': 'LPH MUI'},
                {'topik': 'HACCP & CCP Management', 'tanggal': f'{datetime.now().year}-05-20', 'peserta': 'Koordinator Produksi & QC', 'penyelenggara': 'BSI'},
                {'topik': 'Internal Auditor Halal', 'tanggal': f'{datetime.now().year}-08-10', 'peserta': 'Ketua HAS & Koordinator QC', 'penyelenggara': 'LPH MUI'},
            ]
        }
        
        # Bukti Pelatihan HAS
        ctx['pelatihan_list'] = ctx['training_plan']['pelatihan']
        
        return ctx
    
    def render_and_save(self, profile_name: str, doc_type: str, ctx: dict) -> bool:
        """Render template and save as PDF + MD + JSON."""
        if ctx is None:
            logger.warning(f"Skipping {doc_type} for {profile_name} (error injection: missing doc)")
            return False
        
        tpl_name = DOC_TEMPLATES.get(doc_type)
        if not tpl_name:
            logger.warning(f"No template for {doc_type}")
            return False
        
        try:
            template = self.env.get_template(tpl_name)
            markdown = template.render(**ctx)
            
            # Create output directory
            out_dir = self.output_dir / profile_name
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # Save markdown
            md_path = out_dir / f"{doc_type}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            # Build PDF from markdown
            elements = self.pdf_builder.markdown_to_elements(markdown)
            pdf_path = out_dir / f"{doc_type}.pdf"
            self.pdf_builder.build_pdf(elements, pdf_path, title=doc_type.replace('_', ' '))
            
            # Save metadata JSON
            meta_path = out_dir / f"{doc_type}.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'profile': profile_name,
                    'doc_type': doc_type,
                    'generated_at': datetime.now().isoformat(),
                    'template': tpl_name,
                    'completeness_estimate': 0.8,
                    'pages': max(1, len(markdown) // 3000),
                }, f, indent=2, ensure_ascii=False)
            
            logger.success(f"Generated {profile_name}/{doc_type}.pdf ({len(markdown)} chars)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate {profile_name}/{doc_type}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_all_for_profile(self, profile_name: str) -> dict:
        profile = self.load_profile(profile_name)
        
        results = {'profile': profile_name, 'documents': {}}
        missing = profile.get('error_injection', {}).get('missing_docs', [])
        
        for doc_type in REQUIRED_DOCS:
            if doc_type in missing:
                results['documents'][doc_type] = 'MISSING (intentional)'
                continue
            
            ctx = self.prepare_context(profile, doc_type)
            success = self.render_and_save(profile_name, doc_type, ctx)
            results['documents'][doc_type] = 'OK' if success else 'FAILED'
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic koperasi documents")
    parser.add_argument('--profiles', type=str, default=None, help='Comma-separated profile names (default: all)')
    parser.add_argument('--output', type=str, default='data/synthetic_docs', help='Output directory')
    parser.add_argument('--profiles-dir', type=str, default='data/koperasi_profiles', help='Profiles directory')
    parser.add_argument('--templates-dir', type=str, default='data/templates', help='Templates directory')
    parser.add_argument('--clean', action='store_true', help='Clean output directory first')
    args = parser.parse_args()
    
    base = Path(__file__).parent.parent
    profiles_dir = base / args.profiles_dir
    templates_dir = base / args.templates_dir
    output_dir = base / args.output
    
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)
        logger.info(f"Cleaned output directory: {output_dir}")
    
    if args.profiles:
        profiles = [p.strip() for p in args.profiles.split(',')]
    else:
        profiles = [f.stem for f in profiles_dir.glob('*.yaml') if f.stem != 'index']
    
    logger.info(f"Generating documents for profiles: {profiles}")
    
    generator = SyntheticDocGenerator(profiles_dir, templates_dir, output_dir)
    
    all_results = []
    for profile in profiles:
        try:
            result = generator.generate_all_for_profile(profile)
            all_results.append(result)
        except Exception as e:
            logger.error(f"Failed to process profile {profile}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save summary
    summary_path = output_dir / "generation_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'profiles': all_results,
            'total_profiles': len(all_results),
        }, f, indent=2, ensure_ascii=False)
    
    logger.success(f"Generation complete. Summary: {summary_path}")
    
    for r in all_results:
        ok = sum(1 for v in r['documents'].values() if v == 'OK')
        fail = sum(1 for v in r['documents'].values() if v == 'FAILED')
        missing = sum(1 for v in r['documents'].values() if v.startswith('MISSING'))
        print(f"  {r['profile']}: OK={ok}, FAILED={fail}, MISSING={missing}")


if __name__ == '__main__':
    main()