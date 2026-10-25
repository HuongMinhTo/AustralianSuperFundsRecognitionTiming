"""Parse REI Super annual unit-price PDFs (weekly Wednesday sell prices) into one long CSV.
Text PDFs are read with pdftotext -layout; FY2025 is a scanned table, OCR'd separately into
ReiSuper_pdf/ReiSuper_super_unit_prices_2024_25_ocr.csv (checked against the page images).
The FY2024 PDF on the website stops at 24 Jan 2024 (last page blank), so Feb-Jun 2024 is missing.
Output: data/raw/unit_prices/ReiSuper_unit_prices_super.csv (option, date, price)
Run: python3 code/utilities/parse_reisuper_pdfs.py
"""
import os, re, subprocess
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
PDF = os.path.join(ROOT, 'data', 'raw', 'unit_prices', 'ReiSuper_pdf')
# 1-based position of each option among the numbers that follow the date on a row
COLS = {'old': {'growth': 1, 'balanced': 2, 'stable': 3},                       # FY2014-FY2020
        'alpha1': {'balanced': 3, 'growth': 6, 'stable': 10},                   # FY2021-FY2023
        'alpha2': {'balanced': 3, 'growth': 8, 'stable': 10},                   # FY2024
        'new': {'growth_plus': 1, 'growth': 2, 'balanced': 3, 'stable': 4}}     # FY2026
LAYOUT = {'2013_14': 'old', '2014_15': 'old', '2015_16': 'old', '2016_17': 'old', '2017_18': 'old',
          '2018_19': 'old', '2019_20': 'old', '2020_21': 'alpha1', '2021_22': 'alpha1', '2022_23': 'alpha1',
          '2023_24': 'alpha2', '2025_26': 'new'}
NEED = {'old': 3, 'alpha1': 10, 'alpha2': 10, 'new': 4}
DATE = re.compile(r'^\s*(\d{1,2}[/-](?:\d{2}|[A-Za-z]{3})[/-]\d{2,4})\s+(.*)$')

rows = []
for fy, lay in LAYOUT.items():
    f = os.path.join(PDF, f'ReiSuper_super_unit_prices_{fy}.pdf')
    txt = subprocess.run(['pdftotext', '-layout', f, '-'], capture_output=True, text=True).stdout
    n_ok = n_bad = 0
    for line in txt.splitlines():
        m = DATE.match(line)
        if not m:
            continue
        nums = re.findall(r'\d+\.\d+', m.group(2))
        if len(nums) < NEED[lay]:
            n_bad += 1
            continue
        d = pd.to_datetime(m.group(1), dayfirst=True, format='mixed')
        for opt, pos in COLS[lay].items():
            rows.append((opt, d, float(nums[pos - 1]), fy))
        n_ok += 1
    print(fy, lay, 'rows', n_ok, 'skipped', n_bad)
ocr = pd.read_csv(os.path.join(PDF, 'ReiSuper_super_unit_prices_2024_25_ocr.csv'))
for _, r in ocr.iterrows():
    d = pd.to_datetime(r['date'], dayfirst=True)
    for opt in ['growth_plus', 'growth', 'balanced', 'stable']:
        rows.append((opt, d, float(r[opt]), '2024_25'))
out = pd.DataFrame(rows, columns=['option', 'date', 'price', 'fy']).sort_values(['option', 'date'])
out = out.drop_duplicates(['option', 'date'], keep='last')
# sanity: weekly returns, including across financial-year boundaries
out['ret'] = out.groupby('option')['price'].pct_change()
big = out[out['ret'].abs() > 0.06]
print('weekly moves > 6%:'); print(big.to_string())
out.drop(columns='ret').to_csv(os.path.join(ROOT, 'data', 'raw', 'unit_prices', 'ReiSuper_unit_prices_super.csv'), index=False)
print(out.groupby('option')['date'].agg(['min', 'max', 'count']))
