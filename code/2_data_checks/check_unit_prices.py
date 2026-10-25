"""Quality checks on the standardised unit prices (data/derived/unit_prices/) and the weekly panel.

1. Coverage per option: first/last price, weeks with returns, share of stale weeks.
2. Outliers: weekly log returns beyond +/-8% and daily jumps beyond +/-5% (possible splices, resets).
3. Validation: quarterly return from our prices vs APRA's quarterly return measure
   (apra_return_measure in option_quarter_master).

Outputs: data/derived/unit_price_checks.xlsx (sheets Coverage, Outliers_weekly, Outliers_daily,
Quarterly_vs_APRA, By_fund) and a printed summary.
Run:  python3 code/2_data_checks/check_unit_prices.py
"""
import glob
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
M = os.path.join(ROOT, 'data', 'derived')

px = pd.concat([pd.read_csv(f, parse_dates=['date']).assign(file=os.path.basename(f))
                for f in sorted(glob.glob(os.path.join(M, 'unit_prices', '*.csv')))
                if not os.path.basename(f).startswith('_')], ignore_index=True)
px = px.sort_values(['option_id', 'date'])
wk = pd.read_csv(os.path.join(M, 'master_weekly.csv.gz'), parse_dates=['week', 'saa_date'], low_memory=False)
oq = pd.read_csv(os.path.join(M, 'option_quarter_master.csv'), parse_dates=['saa_date'], low_memory=False)
names = oq.drop_duplicates('option_id', keep='last').set_index('option_id')[['fund_name', 'option_name']]

# 1. coverage ---------------------------------------------------------------
cov = px.groupby('option_id').agg(file=('file', 'first'), first_price=('date', 'min'),
                                  last_price=('date', 'max'), n_prices=('price', 'size'))
w = wk.groupby('option_id').agg(weeks_in_panel=('week', 'size'), weeks_with_ret=('ret', lambda r: r.notna().sum()),
                                first_week_ret=('week', lambda s: s[wk.loc[s.index, 'ret'].notna()].min()),
                                stale_share=('stale_days', lambda s: (s > 5).mean()),
                                core=('core_sample', 'max'), rep_priced=('is_group_rep_priced', 'max'))
cov = names.join(cov, how='right').join(w)
cov['first_saa'] = oq.groupby('option_id')['saa_date'].min()

# 2. outliers -----------------------------------------------------------------
ow = wk.loc[wk['ret'].abs() > 0.08, ['option_id', 'week', 'price', 'ret', 'price_type']].merge(
    names, left_on='option_id', right_index=True)
px['dret'] = px.groupby('option_id')['price'].transform(lambda p: np.log(p).diff())
od = px.loc[px['dret'].abs() > 0.05, ['option_id', 'date', 'price', 'dret', 'file']].merge(
    names, left_on='option_id', right_index=True)

# 3. quarterly return from prices vs APRA --------------------------------------
def q_end_price(g):
    g = g.set_index('date')['price']
    qe = pd.date_range(g.index.min(), g.index.max() + pd.offsets.QuarterEnd(0), freq='QE')
    s = g.reindex(g.index.union(qe)).ffill()
    last = pd.Series(g.index, index=g.index).reindex(g.index.union(qe)).ffill()
    out = pd.DataFrame({'p_qe': s.loc[qe], 'last_obs': last.loc[qe]})
    out = out[(out.index - out['last_obs']).dt.days <= 7]          # price within a week of quarter end
    return out['p_qe']

qp = (px.groupby('option_id')[['date', 'price']].apply(q_end_price)
      .rename('p_qe').reset_index().rename(columns={'level_1': 'saa_date'}))
qp['saa_date'] = pd.to_datetime(qp['saa_date']).dt.normalize()
qp = qp.sort_values(['option_id', 'saa_date'])
qp['ret_q_price'] = qp.groupby('option_id')['p_qe'].pct_change() * 100
gap = qp.groupby('option_id')['saa_date'].diff().dt.days
qp.loc[gap > 95, 'ret_q_price'] = np.nan
cmp_ = qp.merge(oq[['option_id', 'saa_date', 'fund_name', 'option_name', 'apra_return_measure', 'core_sample']],
                on=['option_id', 'saa_date'], how='inner').dropna(subset=['ret_q_price', 'apra_return_measure'])
cmp_['apra_ret_pct'] = cmp_['apra_return_measure'] * 100      # APRA reports decimals (0.0307 = 3.07%)
cmp_['diff_pp'] = cmp_['ret_q_price'] - cmp_['apra_ret_pct']

by_opt = cmp_.groupby('option_id').agg(fund=('fund_name', 'first'), option=('option_name', 'first'),
                                       quarters=('diff_pp', 'size'),
                                       corr=('diff_pp', lambda d: np.corrcoef(cmp_.loc[d.index, 'ret_q_price'],
                                                                              cmp_.loc[d.index, 'apra_ret_pct'])[0, 1]
                                             if len(d) > 2 else np.nan),
                                       mean_diff_pp=('diff_pp', 'mean'),
                                       mad_pp=('diff_pp', lambda d: d.abs().median()),
                                       max_abs_pp=('diff_pp', lambda d: d.abs().max()))
by_fund = cmp_.groupby('fund_name').agg(options=('option_id', 'nunique'), quarters=('diff_pp', 'size'),
                                        corr=('diff_pp', lambda d: np.corrcoef(cmp_.loc[d.index, 'ret_q_price'],
                                                                               cmp_.loc[d.index, 'apra_ret_pct'])[0, 1]),
                                        mean_diff_pp=('diff_pp', 'mean'),
                                        median_abs_diff_pp=('diff_pp', lambda d: d.abs().median()),
                                        share_within_0_25pp=('diff_pp', lambda d: (d.abs() <= 0.25).mean()))
cov = cov.join(by_opt[['quarters', 'corr', 'mean_diff_pp', 'mad_pp', 'max_abs_pp']])

out = os.path.join(M, 'unit_price_checks.xlsx')
with pd.ExcelWriter(out) as xw:
    by_fund.round(4).to_excel(xw, sheet_name='By_fund')
    cov.round(4).to_excel(xw, sheet_name='Coverage')
    cmp_.round(4).to_excel(xw, sheet_name='Quarterly_vs_APRA', index=False)
    ow.round(5).to_excel(xw, sheet_name='Outliers_weekly', index=False)
    od.round(5).to_excel(xw, sheet_name='Outliers_daily', index=False)

pd.set_option('display.width', 250)
print(by_fund.round(3).to_string())
print('\nweekly outliers |ret|>8%:', len(ow), '| daily jumps |ret|>5%:', len(od))
print(od.groupby('option_id').size().sort_values(ascending=False).head(10).to_string())
bad = by_opt[(by_opt['mad_pp'] > 0.1) | (by_opt['corr'] < 0.95)]
print('\noptions with weak match (median |diff| > 0.1pp or corr < 0.95):')
print(bad.round(3).to_string())
print('saved', out)
