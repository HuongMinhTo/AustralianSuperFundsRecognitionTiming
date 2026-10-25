"""Reconcile the funds and options in the estimation sample with the APRA source files.
Sources: QSPS Historical SAA June 2026 (raw csv), QSPS Product Structure June 2026 (Table 1b),
Quarterly Superannuation Fund Statistics June 2026 (Table 1), data/derived/option_quarter_master.csv,
output/estimates/lag_model/equal/S.pkl (main estimation sample). Output: output/sample_checks/apra_consistency_check.xlsx
Run: python3 code/5_sample_checks/check_apra_consistency.py"""
import os
import numpy as np
import pandas as pd

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
P = lambda *a: os.path.join(R, *a)
out = {}

# ---------------------------------------------------------------- sources
saa = pd.read_csv(P('data', 'raw', 'apra', 'QSPS Historical SAA June 2026.csv'), low_memory=False,
                  usecols=['investment_option_identifier', 'time_key', 'investment_option_name', 'investment_option_type',
                           'investment_option_category', 'rse_name', 'rse_abn', 'InvestmentBenchmarkAllocationPercent'])
saa['saa_date'] = pd.to_datetime(saa['time_key'].astype(str), format='%Y%m%d')
t1b = pd.read_excel(P('data', 'raw', 'apra', 'QSPS Product Structure June 2026.xlsx'), sheet_name='Table 1b', header=3).iloc[3:]
t1b.columns = [str(c).strip() for c in t1b.columns]
t1b['abn'] = pd.to_numeric(t1b['RSE ABN'], errors='coerce').astype('Int64')
qs = pd.read_excel(P('data', 'raw', 'apra', 'Quarterly Superannuation Fund Statistics June 2026.xlsx'), sheet_name='Table 1', header=5).iloc[2:]
qs.columns = [str(c).strip() for c in qs.columns]
qs = qs[pd.to_datetime(qs['Period'], errors='coerce') == '2026-06-30']
qs['abn'] = pd.to_numeric(qs['ABN'], errors='coerce').astype('Int64')
oq = pd.read_csv(P('data', 'derived', 'option_quarter_master.csv'), parse_dates=['saa_date'], low_memory=False)
S = pd.read_pickle(P('output', 'estimates', 'lag_model', 'equal', 'S.pkl'))
St = pd.read_pickle(P('output', 'estimates', 'lag_model', 'equal', 'trusts', 'S.pkl'))

# ---------------------------------------------------------------- 1. universe
u = pd.DataFrame([
    ['APRA-regulated funds in Quarterly Superannuation Fund Statistics (June 2026)', qs['abn'].nunique(), np.nan],
    ['Funds / investment options in QSPS Product Structure, Table 1b (June 2026)', t1b['abn'].nunique(),
     t1b['Investment Option Identifier'].nunique()],
    ['Funds / options in QSPS Historical SAA file (raw csv, all quarters)', saa['rse_abn'].nunique(),
     saa['investment_option_identifier'].nunique()],
    ['  of which reported in June 2026', saa.loc[saa.time_key == 20260630, 'rse_abn'].nunique(),
     saa.loc[saa.time_key == 20260630, 'investment_option_identifier'].nunique()],
    ['Funds / options in option_quarter_master.csv', oq['abn'].nunique(), oq['option_id'].nunique()],
    ['SAA options also listed in Table 1b (June 2026)', np.nan,
     len(set(saa['investment_option_identifier']) & set(t1b['Investment Option Identifier'].astype(str)))],
], columns=['Item', 'Funds', 'Options'])
u['Quarters'] = [np.nan, 1, saa['saa_date'].nunique(), 1, oq['saa_date'].nunique(), np.nan]
out['1 Universe'] = u

# funds regulated by APRA but absent from the SAA file
miss = qs[~qs['abn'].isin(saa['rse_abn'].unique())][['Fund name', 'abn', 'Fund type', 'RSE Regulatory classification']]
miss = miss.merge(t1b.groupby('abn').agg(options_1b=('Investment Option Identifier', 'nunique'),
                                         multi_sector_1b=('Investment Option Category Type',
                                                          lambda s: (s == 'Multi Sector').sum())).reset_index(),
                  on='abn', how='left')
out['2 APRA funds not in SAA'] = miss.sort_values('Fund name')

# ---------------------------------------------------------------- 3. waterfall (option ever satisfies flag, 2015-2026)
win = oq[oq.saa_date >= '2015-06-30']
ever = win.groupby('option_id').agg(abn=('abn', 'first'), multi=('option_category', lambda s: (s == 'Multi Sector').any()),
                                    core=('core_sample', 'max'), dedup=('core_sample_dedup', 'max'),
                                    specialist=('specialist_option', 'max'))
pr = pd.read_csv(P('data', 'derived', 'master_weekly.csv.gz'), usecols=['option_id', 'core_sample_dedup_priced', 'ret'], low_memory=False)
pr = pr[pr.core_sample_dedup_priced.astype(bool) & pr.ret.notna()].groupby('option_id').size()
ever['priced'] = ever.index.isin(pr.index)
ever['in_trusts'] = ever.index.isin(St.option_id.unique())
ever['in_main'] = ever.index.isin(S.option_id.unique())
steps = [('All options in SAA file (reported June 2014-June 2026)', oq),
         ('Reported from June 2015 (estimation window)', win)]
wf = [[a, d.abn.nunique(), d.option_id.nunique()] for a, d in steps]
for lab, m in [('Multi-sector options', ever.multi), ('Core sample (multi-manager/multi-sector, weights complete, not specialist)', ever.core),
               ('Core sample, one option per identical allocation (dedup)', ever.dedup),
               ('Priced representative of a distinct allocation (a priced identical option replaces an unpriced one)', ever.priced),
               ('... in estimation sample incl. platform trust-priced funds', ever.in_trusts),
               ('... in MAIN estimation sample (26 lags available, trust-priced funds excluded)', ever.in_main)]:
    wf.append([lab, ever[m.astype(bool)].abn.nunique(), int(m.astype(bool).sum())])
wf = pd.DataFrame(wf, columns=['Step', 'Funds', 'Options'])
out['3 Waterfall'] = wf

# ---------------------------------------------------------------- 4. per fund
fn = saa.sort_values('saa_date').groupby('rse_abn')['rse_name'].last()
ft = oq.groupby('abn')['fund_type_fixed'].last()
jun = saa[saa.time_key == 20260630]
pf = pd.DataFrame({'abn': sorted(saa['rse_abn'].unique())})
pf['Fund (APRA name)'] = pf.abn.map(fn)
pf['Type'] = pf.abn.map(ft)
pf['SAA options (June 2026)'] = pf.abn.map(jun.groupby('rse_abn')['investment_option_identifier'].nunique()).fillna(0).astype(int)
pf['Multi-sector (June 2026)'] = pf.abn.map(jun[jun.investment_option_category == 'Multi Sector'].groupby('rse_abn')['investment_option_identifier'].nunique()).fillna(0).astype(int)
for c, m in [('Core (ever)', ever.core), ('Dedup (ever)', ever.dedup), ('Priced representative', ever.priced),
             ('In main sample', ever.in_main), ('In trust-inclusive sample', ever.in_trusts)]:
    pf[c] = pf.abn.map(ever[m.astype(bool)].groupby('abn').size()).fillna(0).astype(int)
pf['Option-weeks (main)'] = pf.abn.map(S.groupby('abn').size()).fillna(0).astype(int)
pf['Status'] = np.where(pf['In main sample'] > 0, 'Main sample',
                np.where(pf['In trust-inclusive sample'] > 0, 'Robustness only (trust prices)',
                np.where(pf['Dedup (ever)'] == 0, 'No distinct core option', 'Not priced (no public history)')))
pf.loc[pf.abn == 90302247344, 'Status'] = 'Represented by PSSap (identical allocations)'
pf.loc[pf.abn == 81154851339, 'Status'] = 'Prices downloaded (trust); no option is a priced distinct-allocation representative'
pf = pf.sort_values(['Status', 'Fund (APRA name)'])
out['4 By fund'] = pf

# ---------------------------------------------------------------- 5. identity checks on sample options
ids = S.groupby('option_id').agg(abn=('abn', 'first'), fund=('fund_name', 'last'), option=('option_name', 'last'),
                                 first_week=('week', 'min'), last_week=('week', 'max'), weeks=('ret', 'size'),
                                 w_total=('w_total_ex_fx', 'mean'), w_min=('w_total_ex_fx', 'min'), w_max=('w_total_ex_fx', 'max'))
a = saa.sort_values('saa_date').groupby('investment_option_identifier').agg(
    apra_abn=('rse_abn', 'last'), apra_fund=('rse_name', 'last'), apra_option=('investment_option_name', 'last'),
    apra_cat=('investment_option_category', 'last'), apra_type=('investment_option_type', 'last'),
    apra_first=('saa_date', 'min'), apra_last=('saa_date', 'max'))
ids = ids.join(a, how='left')
ids['in_1b_June2026'] = ids.index.isin(set(t1b['Investment Option Identifier'].astype(str)))
ids['abn_match'] = ids['abn'] == ids['apra_abn']
ids['fund_name_match'] = ids['fund'] == ids['apra_fund']
ids['option_name_match'] = ids['option'] == ids['apra_option']
ids['multi_sector'] = ids['apra_cat'] == 'Multi Sector'
ids['weights_ok'] = ids['w_min'].between(0.97, 1.03) & ids['w_max'].between(0.97, 1.03)
ids['weeks_within_saa'] = (ids['first_week'] >= ids['apra_first']) & (ids['last_week'] <= ids['apra_last'] + pd.Timedelta(days=100))
out['5 Option checks'] = ids.reset_index()
chk = pd.DataFrame({f'Check ({S.option_id.nunique()} options in main sample)': [
    'Option identifier found in APRA SAA file', 'ABN equals APRA RSE ABN', 'Fund name equals APRA RSE name',
    'Option name equals APRA option name (latest)', 'APRA category is Multi Sector',
    'Strategic weights sum to 97-103% in every week used', 'Weeks used lie within the APRA reporting window',
    'Option still listed in Product Structure Table 1b (June 2026)'],
    'Pass': [int(ids.apra_abn.notna().sum()), int(ids.abn_match.sum()), int(ids.fund_name_match.sum()),
             int(ids.option_name_match.sum()), int(ids.multi_sector.sum()), int(ids.weights_ok.sum()),
             int(ids.weeks_within_saa.sum()), int(ids.in_1b_June2026.sum())]})
chk['Fail'] = len(ids) - chk['Pass']
out['0 Summary checks'] = chk

# ---------------------------------------------------------------- 6. returns vs APRA (from check_unit_prices)
try:
    bf = pd.read_excel(P('data', 'derived', 'unit_price_checks.xlsx'), sheet_name='By_fund')
    bf = bf[bf['fund_name'].isin(S['fund_name'].unique())]
    out['6 Returns vs APRA'] = bf
except Exception as e:
    print('returns check skipped:', e)

fnm = P('output', 'sample_checks', 'apra_consistency_check.xlsx')
os.makedirs(os.path.dirname(fnm), exist_ok=True)
with pd.ExcelWriter(fnm, engine='openpyxl') as xw:
    for k in sorted(out):
        out[k].to_excel(xw, sheet_name=k[:31], index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 90)
for k in ['0 Summary checks', '1 Universe', '3 Waterfall']:
    print('\n##', k); print(out[k].to_string(index=False))
print('\n## 2 APRA funds not in SAA:', len(miss)); print(miss.to_string(index=False))
print('\n## 4 By fund'); print(pf.drop(columns='abn').to_string(index=False))
print('\nfailures:'); print(ids.loc[~(ids.abn_match & ids.fund_name_match & ids.multi_sector & ids.weights_ok & ids.weeks_within_saa),
      ['fund', 'option', 'apra_option', 'apra_cat', 'w_min', 'w_max', 'first_week', 'apra_first', 'last_week', 'apra_last']].to_string())
print('\noption name differences:'); print(ids.loc[~ids.option_name_match, ['option', 'apra_option']].to_string())
if '6 Returns vs APRA' in out:
    print(out['6 Returns vs APRA'].round(3).to_string(index=False))
print('saved', fnm)
