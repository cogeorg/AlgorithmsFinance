"""Extract the local lab reference and render its relevant pages."""
import argparse
import json
from pathlib import Path
import sys
from pypdf import PdfReader

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
parser = argparse.ArgumentParser()
parser.add_argument('pdf', type=Path)
parser.add_argument('--render', action='store_true')
args = parser.parse_args()
reader = PdfReader(args.pdf)
selected = []
for number, page in enumerate(reader.pages, 1):
    text = page.extract_text() or ''
    if number in (29, 30, 31, 32, 36):
        selected.append((number, text))
        print(f'\n--- PDF page {number} ---\n{text}')
print(f'PDF: {args.pdf}; pages: {len(reader.pages)}; selected: {[n for n, _ in selected]}')
if args.render:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(args.pdf)
    out = Path(__file__).parent / 'slides'
    out.mkdir(exist_ok=True)
    for number, text in selected:
        (out / f'page_{number:02}.txt').write_text(text, encoding='utf-8')
        doc[number-1].render(scale=1.5).to_pil().save(out / f'page_{number:02}.png')