"""Date-convention check for low-frequency (weekly) price series, which check_date_alignment.py skips.
For every pair of consecutive prices 5-8 calendar days apart, the option's log return is correlated with
the listed-market composite return over the same window moved k business days earlier (k = 0..4).
The best k should be 0 (or 1 for series whose period ends on a Tuesday); a clearly larger best k means the
labels run late. Market composite = 0.5 ASX 200 + 0.5 world ex-Australia (WXOZ/VGS), log returns.
Run: python3 code/2_data_checks/check_weekly_alignment.py -> data/derived/unit_price_weekly_alignment.csv"""
import glob, os
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
p = pd.read_csv(os.path.join(ROOT, 'data', 'raw', 'proxies', 'proxy_etf_prices_yahoo.csv'), parse_dates=['date'])
px = p.pivot_table(index='date', columns='ticker', values='adjclose').ffill()
lvl = 0.5 * np.log(px['^AXJO']) + 0.5 * np.log(px['VGS.AX'].fillna(px['WXOZ.AX'] * px['VGS.AX'].dropna().iloc[0]
                                                                          / px['WXOZ.AX'].loc[px['VGS.AX'].dropna().index[0]]))
lvl = lvl.dropna()


def at(dates):
    return lvl.reindex(lvl.index.union(dates)).ffill().loc[dates].values


rows = []
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'derived', 'unit_prices', '*.csv'))):
    d = pd.read_csv(f, parse_dates=['date'])
    for oid, g in d.groupby('option_id'):
        s = g.set_index('date')['price'].sort_index()
        s = s[s.index >= '2010-01-01']
        gap = s.index.to_series().diff().dt.days
        wk = gap.between(5, 8)
        if wk.sum() < 52:
            continue
        end = s.index[wk.values]
        start = s.index[np.where(wk.values)[0] - 1]
        r = np.log(s.values[wk.values]) - np.log(s.values[np.where(wk.values)[0] - 1])
        out = {}
        for k in range(0, 5):
            m = at(end - BDay(k)) - at(start - BDay(k))
            ok = ~np.isnan(m) & ~np.isnan(r)
            out[k] = np.corrcoef(r[ok], m[ok])[0, 1] if ok.sum() > 30 else np.nan
        best = max(out, key=lambda k: out[k] if pd.notna(out[k]) else -9)
        rows.append(dict(file=os.path.basename(f), option_id=oid, n_weekly=int(wk.sum()),
                         first=end.min().date(), last=end.max().date(), best_shift=best,
                         **{f'corr_{k}': round(v, 3) for k, v in out.items()}))
res = pd.DataFrame(rows)
res.to_csv(os.path.join(ROOT, 'data', 'derived', 'unit_price_weekly_alignment.csv'), index=False)
pd.set_option('display.width', 250)
print(res.groupby('file').agg(options=('option_id', 'size'), weeks=('n_weekly', 'median'),
                              best=('best_shift', lambda s: s.value_counts().to_dict()),
                              c0=('corr_0', 'median'), c1=('corr_1', 'median'), c2=('corr_2', 'median'),
                              c3=('corr_3', 'median')).to_string())
