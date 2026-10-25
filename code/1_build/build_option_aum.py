"""Member assets (AUM, $'000) and member accounts of every APRA investment option at June 2026, from APRA QSPS
Product Structure June 2026, Table 1b. Assets are 'Investment Option Member Assets (All investment pathways)';
where that is not reported, the sum of the option's 'Investment Pathway Member Assets' is used.
Used as the regression weights in the AUM-weighted distributed-lag model (code/3_lag_model/pilot_lag_model.py).
Output: data/derived/option_aum_june2026_all.csv (option_id, assets_k, accounts)
Run from the PhD_Topic3_Data folder:  python3 code/1_build/build_option_aum.py  [output path, optional]"""
import os, sys
import pandas as pd

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(R, 'data', 'derived', 'option_aum_june2026_all.csv')
t = pd.read_excel(os.path.join(R, 'data', 'raw', 'apra', 'QSPS Product Structure June 2026.xlsx'),
                  sheet_name='Table 1b', header=3).iloc[3:]
t.columns = [str(c).strip() for c in t.columns]
co = [c for c in t.columns if c.startswith('Investment Option Member Assets')][0]
cp = [c for c in t.columns if c.startswith('Investment Pathway Member Assets')][0]
ca = [c for c in t.columns if c.startswith('Investment Option Member Accounts')][0]
for c in (co, cp, ca):
    t[c] = pd.to_numeric(t[c], errors='coerce')
opt = t.groupby('Investment Option Identifier').agg(assets_opt=(co, 'max'), assets_path=(cp, 'sum'), accounts=(ca, 'max'))
opt['assets_k'] = opt['assets_opt'].fillna(opt['assets_path'].where(opt['assets_path'] > 0))
out = opt[['assets_k', 'accounts']].rename_axis('option_id').reset_index()
out.to_csv(OUT, index=False)
print(f'{len(out):,} options, total assets {out.assets_k.sum() / 1e6:,.1f} billion dollars -> {OUT}')
