#!/usr/bin/env python3
"""Render the saved technical report with its measured figures to PDF."""
import argparse
import html
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, Preformatted

ROOT = Path(__file__).resolve().parents[1]


def inline(text):
    text = html.escape(text.replace('—', '-').replace('–', '-'))
    text = re.sub(r'`([^`]+)`', r'<font name="DejaVuMono">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    def link(match):
        title, url = match.groups()
        return f'<link href="{url}" color="#236584">{title}</link>' if url.startswith('https://') else title
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fonts', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/pdf/Recalllens-Technical-Report.pdf')
    args = parser.parse_args()
    for name, filename in [('DejaVu', 'DejaVuSans.ttf'), ('DejaVuBold', 'DejaVuSans-Bold.ttf'), ('DejaVuMono', 'DejaVuSansMono.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(args.fonts / filename)))
    pdfmetrics.registerFontFamily('DejaVu', normal='DejaVu', bold='DejaVuBold', italic='DejaVu', boldItalic='DejaVuBold')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Body', fontName='DejaVu', fontSize=9.3, leading=14.1, spaceAfter=7, textColor=colors.HexColor('#213344')))
    styles.add(ParagraphStyle(name='TitleRL', fontName='DejaVuBold', fontSize=23, leading=29, spaceAfter=18, textColor=colors.HexColor('#13374c')))
    for name, size in [('H2RL', 14), ('H3RL', 11)]:
        styles.add(ParagraphStyle(name=name, fontName='DejaVuBold', fontSize=size, leading=size+5, spaceBefore=12, spaceAfter=7, keepWithNext=True, textColor=colors.HexColor('#16756a')))
    styles.add(ParagraphStyle(name='Cell', fontName='DejaVu', fontSize=8.2, leading=11.6))
    styles.add(ParagraphStyle(name='CodeRL', fontName='DejaVuMono', fontSize=7.6, leading=10, spaceAfter=10))
    docpath = ROOT / 'docs/TECHNICAL_REPORT.md'
    lines = docpath.read_text().splitlines()
    story, i = [], 0
    width = 487
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                block.append(lines[i])
                i += 1
            story.append(Preformatted('\n'.join(block), styles['CodeRL']))
        elif line.startswith('|'):
            data = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', c) for c in cells):
                    data.append([Paragraph(inline(c), styles['Cell']) for c in cells])
                i += 1
            table = Table(data, colWidths=[width/len(data[0])]*len(data[0]), repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f2f0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#16756a')),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d9e2e8'))]))
            story.extend([table, Spacer(1, 10)])
            continue
        elif line.startswith('!['):
            match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            path = docpath.parent / match.group(2)
            iw, ih = ImageReader(str(path)).getSize()
            height = width*ih/iw
            story.extend([Image(str(path), width=width, height=height), Paragraph(inline(match.group(1)), styles['Cell']), Spacer(1, 10)])
        elif line.startswith('# '):
            story.append(Paragraph(inline(line[2:]), styles['TitleRL']))
            story.append(Paragraph('OpenCV AI Competition 2026 | Evidence update: 26 October 2026', styles['Body']))
        elif line.startswith('## '):
            story.append(Paragraph(inline(line[3:]), styles['H2RL']))
        elif line.startswith('### '):
            story.append(Paragraph(inline(line[4:]), styles['H3RL']))
        else:
            text = line[2:] if line.startswith('- ') else line
            story.append(Paragraph(inline(text), styles['Body'], bulletText='-' if line.startswith('- ') else None))
        i += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def footer(canvas, doc):
        canvas.setFont('DejaVu', 8)
        canvas.setFillColor(colors.HexColor('#657886'))
        canvas.drawString(54, 30, 'Recalllens | Technical report')
        canvas.drawRightString(541, 30, str(doc.page))
    doc = SimpleDocTemplate(str(args.output), pagesize=(595, 842), leftMargin=54, rightMargin=54, topMargin=43, bottomMargin=49, title='Recalllens - Technical Report', author='Recalllens')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(args.output)


if __name__ == '__main__':
    main()
