"""Export exactly the 40 instructor-supplied crypto rows from a batch CSV."""
import csv
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]) if len(sys.argv)>1 else root/'40_Results'/'one_year_assets.csv'
output=Path(sys.argv[2]) if len(sys.argv)>2 else root/'40_Results'/'one_year_crypto.csv'
with source.open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f); fields=reader.fieldnames
    rows=[r for r in reader if r['asset']!='SP500']
if len(rows)!=40 or len({r['asset'] for r in rows})!=40 or any(r['status']!='completed' for r in rows):
    raise ValueError('Expected 40 distinct completed crypto assets')
with output.open('x',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print(f'Saved {len(rows)} crypto rows to {output}')
