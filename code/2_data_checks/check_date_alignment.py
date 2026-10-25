"""Check the date convention of each price series: correlate the option's daily log returns with a
same-day listed-market composite (ASX-listed ETFs: 0.4 VAS + 0.4 VGS + 0.2 VAF) shifted by k business
days. The shift with the highest correlation should be 0; +k means the published date is k business
days AFTER the market move (the series should be moved k business days earlier).
Run: python3 code/2_data_checks/check_date_alignment.py  -> data/derived/unit_price_date_alignment.csv"""
import glob, os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
p = pd.read_csv(os.path.join(ROOT, 'data', 'raw', 'proxies', 'proxy_etf_prices_yahoo.csv'), parse_dates=['date'])
px = p.pivot_table(index='date', columns='ticker', values='adjclose')
bd = pd.bdate_range('2015-01-01', px.index.max())
lr = np.log(px.reindex(bd).ffill(limit=3)).diff()
mkt = 0.4 * lr['VAS.AX'] + 0.4 * lr['VGS.AX'].fillna(lr['WXOZ.AX']) + 0.2 * lr['VAF.AX']
rows = []
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'derived', 'unit_prices', '*.csv'))):
    d = pd.read_csv(f, parse_dates=['date'])
    for oid, g in d.groupby('option_id'):
        s = g.set_index('date')['price'].sort_index()
        s = s[s.index.dayofweek < 5]
        daily = s.index.to_series().diff().dt.days.le(4)
        s = s[daily | daily.shift(-1, fill_value=False)]
        r = np.log(s).diff().reindex(bd)
        if r.notna().sum() < 250:
            continue
        cors = {k: r.corr(mkt.shift(k)) for k in range(-3, 4)}
        best = max(cors, key=lambda k: cors[k] if pd.notna(cors[k]) else -9)
        rows.append(dict(file=os.path.basename(f), option_id=oid, n_daily=int(r.notna().sum()), best_shift=best,
                         **{f'corr_{k}': round(v, 3) for k, v in cors.items()}))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(ROOT, 'data', 'derived', 'unit_price_date_alignment.csv'), index=False)
pd.set_option('display.width', 250)
print(out.groupby('file').agg(options=('option_id', 'size'), best_shift=('best_shift', lambda s: s.value_counts().to_dict()),
                              corr0=('corr_0', 'median'), corr1=('corr_1', 'median'), corr2=('corr_2', 'median')).to_string())
