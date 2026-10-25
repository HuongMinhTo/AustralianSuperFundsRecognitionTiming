"""AUM (member assets, June 2026) of the investment options studied, from APRA QSPS Product Structure Table 1b
('Investment Option Member Assets (All investment pathways)', $'000). Output: output/sample_checks/option_aum_june2026.xlsx"""
import os
import numpy as np
import pandas as pd
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
P = lambda *a: os.path.join(R, *a)
t = pd.read_excel(P('data', 'raw', 'apra', 'QSPS Product Structure June 2026.xlsx'), sheet_name='Table 1b', header=3).iloc[3:]
t.columns = [str(c).strip() for c in t.columns]
co = [c for c in t.columns if c.startswith('Investment Option Member Assets')][0]
cp = [c for c in t.columns if c.startswith('Investment Pathway Member Assets')][0]
ca = [c for c in t.columns if c.startswith('Investment Option Member Accounts')][0]
for c in (co, cp, ca):
    t[c] = pd.to_numeric(t[c], errors='coerce')
t['abn'] = pd.to_numeric(t['RSE ABN'], errors='coerce').astype('Int64')
opt = t.groupby('Investment Option Identifier').agg(abn=('abn', 'first'), assets_opt=(co, 'max'), assets_path=(cp, 'sum'),
                                                   accounts=(ca, 'max'))
opt['assets_k'] = opt['assets_opt'].fillna(opt['assets_path'].where(opt['assets_path'] > 0))
opt['source'] = np.where(opt['assets_opt'].notna(), 'option total', np.where(opt['assets_k'].notna(), 'sum of pathways', 'not reported'))

qs = pd.read_excel(P('data', 'raw', 'apra', 'Quarterly Superannuation Fund Statistics June 2026.xlsx'), sheet_name='Table 1', header=5).iloc[2:]
qs.columns = [str(c).strip() for c in qs.columns]
qs = qs[pd.to_datetime(qs['Period'], errors='coerce') == '2026-06-30']
qs['abn'] = pd.to_numeric(qs['ABN'], errors='coerce').astype('Int64')
cb = [c for c in qs.columns if c.startswith("Total members' benefits")][0]
fundben = qs.set_index('abn')[cb].astype(float)

S = pd.read_pickle(P('output', 'estimates', 'lag_model', 'equal', 'S.pkl'))
St = pd.read_pickle(P('output', 'estimates', 'lag_model', 'equal', 'trusts', 'S.pkl'))
oq = pd.read_csv(P('data', 'derived', 'option_quarter_master.csv'), parse_dates=['saa_date'], low_memory=False)
fn = oq.groupby('abn')['fund_name'].last()
ftype = oq.groupby('abn')['fund_type_fixed'].last()

so = S.groupby('option_id').agg(abn=('abn', 'first'), option=('option_name', 'last'), last_week=('week', 'max'),
                                mysuper=('is_mysuper_option', 'max'), wU=('w_unlisted_core', 'mean'))
so = so.join(opt[['assets_k', 'accounts', 'source']], how='left')
so['active_2026'] = so['last_week'] >= '2026-07-01'

# identical allocations represented by a sample option in the June 2026 quarter (e.g. lifecycle stages, product copies)
j = oq[(oq.saa_date == oq.saa_date.max()) & oq.core_sample.astype(bool)][['option_id', 'abn', 'alloc_group']]
rep_groups = set(S.loc[S.saa_date == S.saa_date.max(), 'alloc_group'].dropna())
j = j[j.alloc_group.isin(rep_groups)].set_index('option_id').join(opt[['assets_k']], how='left')

rows = []
for a, g in so.groupby('abn'):
    rows.append(dict(abn=a, Fund=fn.get(a), Type=ftype.get(a), options=len(g),
                     options_with_aum=int(g.assets_k.notna().sum()),
                     aum_sample_bn=g.assets_k.sum() / 1e6,
                     aum_active_bn=g.loc[g.active_2026, 'assets_k'].sum() / 1e6,
                     aum_incl_identical_bn=j.loc[j.abn == a, 'assets_k'].sum() / 1e6,
                     fund_benefits_bn=fundben.get(a, np.nan) / 1e6,
                     wU_assetweighted=np.average(g.wU, weights=g.assets_k.fillna(0)) if g.assets_k.fillna(0).sum() > 0 else np.nan))
F = pd.DataFrame(rows)
F['share_of_fund'] = F['aum_incl_identical_bn'] / F['fund_benefits_bn']
F = F.sort_values('aum_sample_bn', ascending=False)
tot = dict(abn='', Fund='TOTAL (main sample)', Type='', options=F.options.sum(), options_with_aum=F.options_with_aum.sum(),
           aum_sample_bn=F.aum_sample_bn.sum(), aum_active_bn=F.aum_active_bn.sum(),
           aum_incl_identical_bn=F.aum_incl_identical_bn.sum(), fund_benefits_bn=F.fund_benefits_bn.sum(),
           wU_assetweighted=np.average(so.wU, weights=so.assets_k.fillna(0)))
tot['share_of_fund'] = tot['aum_incl_identical_bn'] / tot['fund_benefits_bn']
F = pd.concat([F, pd.DataFrame([tot])], ignore_index=True)

sys_ = pd.DataFrame([
    ['All APRA-regulated funds (Quarterly Fund Statistics, total members\' benefits)', fundben.sum() / 1e6],
    ['All investment options in Product Structure Table 1b (option member assets)', opt.assets_k.sum() / 1e6],
    [f'Options in the APRA allocation (SAA) file, {oq.abn.nunique()} funds', opt.loc[opt.index.isin(oq.option_id.unique()), 'assets_k'].sum() / 1e6],
    ['Core-sample options, June 2026', opt.loc[opt.index.isin(oq.loc[(oq.saa_date == oq.saa_date.max()) & oq.core_sample.astype(bool), 'option_id']), 'assets_k'].sum() / 1e6],
    [f'Main sample: the {len(so)} options studied', so.assets_k.sum() / 1e6],
    ['Main sample: options priced in Jul-Aug 2026 only', so.loc[so.active_2026, 'assets_k'].sum() / 1e6],
    ['Main sample incl. identically allocated options represented (June 2026)', j.assets_k.sum() / 1e6],
    ['Trust-inclusive sample (adds IOOF, RPS, AvWrap, Bendigo options)', opt.loc[opt.index.isin(St.option_id.unique()), 'assets_k'].sum() / 1e6],
], columns=['Aggregate (June 2026)', 'Assets ($bn)'])
sys_['Share of APRA-regulated total'] = sys_['Assets ($bn)'] / sys_.iloc[0, 1]

fnm = P('output', 'sample_checks', 'option_aum_june2026.xlsx')
os.makedirs(os.path.dirname(fnm), exist_ok=True)
with pd.ExcelWriter(fnm, engine='openpyxl') as xw:
    sys_.to_excel(xw, sheet_name='Totals', index=False)
    F.to_excel(xw, sheet_name='By fund', index=False)
    so.reset_index().assign(assets_bn=lambda d: d.assets_k / 1e6).sort_values('assets_k', ascending=False).to_excel(xw, sheet_name='By option', index=False)
pd.set_option('display.width', 250)
print(sys_.round(3).to_string(index=False))
print(F.drop(columns='abn').round(3).to_string(index=False))
print('sample options without AUM:', so[so.assets_k.isna()][['option']].to_string())
print('by source:', so.source.value_counts().to_dict())
print('top 10 options:'); print(so.sort_values('assets_k', ascending=False).head(10)[['option', 'assets_k', 'mysuper']].assign(bn=lambda d: d.assets_k / 1e6).round(2).to_string())
print('MySuper share of sample AUM:', so.loc[so.mysuper == True, 'assets_k'].sum() / so.assets_k.sum())
