"""
build_master.py -- builds the master dataset for the stale-valuation study.

Run from the PhD_Topic3_Data folder:
    python3 code/1_build/build_master.py saa        # option-quarter allocations from QSPS Historical SAA
    python3 code/1_build/build_master.py fund       # fund-year variables from APRA annual fund-level statistics
    python3 code/1_build/build_master.py perf       # option-quarter APRA return / volatility measures
    python3 code/1_build/build_master.py merge      # option-quarter master + unit-price mapping template
    python3 code/1_build/build_master.py weekly     # weekly master, once unit prices are in data/derived/unit_prices/
    python3 code/1_build/build_master.py all        # every step in order

Outputs go to data/derived/. See data/derived/README.md for the variable list.

Timing conventions (so every right-hand-side variable is known in advance):
  * Allocations reported at quarter end q are the "start-of-quarter" weights for quarter q+1.
  * Fund-year variables are those of the latest 30 June on or before the observation date.
"""
from __future__ import annotations
import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'data', 'derived')
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, 'unit_prices'), exist_ok=True)

F_SAA = ROOT + '/data/raw/apra/QSPS Historical SAA June 2026.csv'
F_PERF = ROOT + '/data/raw/apra/QSPS Historical performance June 2026.csv'
F_FUND = ROOT + '/data/raw/apra/Annual fund-level superannuation statistics back series June 2004 to June 2025 (1).xlsx'
F_UNIVERSE = ROOT + '/data/raw/apra/fund_universe_june2026.csv'
F_CHECKLIST = ROOT + '/data/raw/unit_prices/Fund_website_download_checklist.xlsx'

MERGER_SHARE = 0.25        # successor-fund transfers in >= 25% of opening net assets = major merger
JUMP = 0.10                # quarter-to-quarter change in w_unlisted_core treated as a large jump
SUM_TOL = 0.02             # weights (excl. currency overlay) must be within 2 pp of 100%
SPECIALIST = 0.40          # one non-equity asset class >= 40% of the option = specialist option
BAD_FUND_SHARE = 0.02      # fund flagged if more than 2% of its option-quarters fail the sum check

# ----------------------------------------------------------------------------- 1. allocations

BUCKET_ORDER = ['EQ_AU_L', 'EQ_INT_L', 'EQ_OTHER', 'PE_U',
                'PROP_AU_L', 'PROP_INT_L', 'PROP_U_AU', 'PROP_U_INT', 'PROP_U_NSDOM', 'PROP_NS', 'PROP_OTHER',
                'INFRA_L', 'INFRA_U', 'INFRA_NS', 'INFRA_OTHER',
                'CREDIT_U', 'CREDIT_OTHER', 'FI', 'CASH', 'ALT_U', 'ALT_OTHER', 'FX_OVERLAY', 'OTHER']


def bucket(sector: str, listing: str, dom: str) -> str:
    au = dom == 'Australian Domicile'
    intl = dom == 'International Domicile'
    if sector == 'Equity':
        if listing == 'Unlisted':
            return 'PE_U'
        if listing == 'Listed':
            return 'EQ_AU_L' if au else 'EQ_INT_L'
        return 'EQ_OTHER'
    if sector == 'Property':
        if listing == 'Listed':
            return 'PROP_AU_L' if au else 'PROP_INT_L'
        if listing == 'Unlisted':
            return 'PROP_U_AU' if au else ('PROP_U_INT' if intl else 'PROP_U_NSDOM')
        return 'PROP_NS' if listing == 'Not Specified' else 'PROP_OTHER'
    if sector == 'Infrastructure':
        if listing == 'Listed':
            return 'INFRA_L'
        if listing == 'Unlisted':
            return 'INFRA_U'
        return 'INFRA_NS' if listing == 'Not Specified' else 'INFRA_OTHER'
    if sector == 'Credit':
        return 'CREDIT_U' if listing == 'Unlisted' else 'CREDIT_OTHER'
    if sector in ('Fixed Income', 'Fixed Income Excluding Credit'):
        return 'FI'
    if sector == 'Cash':
        return 'CASH'
    if sector in ('Alternatives', 'Growth Alternatives', 'Defensive Alternatives'):
        return 'ALT_U' if listing == 'Unlisted' else 'ALT_OTHER'
    if sector == 'Currency Exposure':
        return 'FX_OVERLAY'
    return 'OTHER'


def step_saa():
    cols = ['investment_option_identifier', 'time_key', 'investment_option_name', 'investment_option_type',
            'investment_option_category', 'rse_name', 'rse_abn', 'rsl_name', 'Public_Offer_Status',
            'ConsolidatedSectorType', 'ConsolidatedListingType', 'ConsolidatedDomicileType',
            'InvestmentBenchmarkAllocationPercent', 'InvestmentCurrencyHedgingRatioPercent']
    df = pd.read_csv(F_SAA, usecols=cols, low_memory=False)
    df = df.rename(columns={'investment_option_identifier': 'option_id', 'rse_abn': 'abn',
                            'InvestmentBenchmarkAllocationPercent': 'w',
                            'InvestmentCurrencyHedgingRatioPercent': 'hedge'})
    df['saa_date'] = pd.to_datetime(df['time_key'].astype(str), format='%Y%m%d')
    keys = ['ConsolidatedSectorType', 'ConsolidatedListingType', 'ConsolidatedDomicileType']
    combos = df[keys].drop_duplicates()
    combos['bucket'] = [bucket(*r) for r in combos[keys].itertuples(index=False)]
    df = df.merge(combos, on=keys, how='left')

    wide = df.pivot_table(index=['option_id', 'saa_date'], columns='bucket', values='w', aggfunc='sum', fill_value=0.0)
    wide = wide.reindex(columns=BUCKET_ORDER, fill_value=0.0)
    wide.columns = ['w_' + c for c in wide.columns]
    wide = wide.reset_index()

    # hedge ratio of international assets, weighted by allocation
    intl = df[df['ConsolidatedDomicileType'] == 'International Domicile'].copy()
    intl['wh'] = intl['w'] * intl['hedge']
    h = intl.groupby(['option_id', 'saa_date']).agg(w_intl=('w', 'sum'), wh=('wh', 'sum')).reset_index()
    h['hedge_ratio_intl'] = np.where(h['w_intl'] > 0, h['wh'] / h['w_intl'], np.nan)
    wide = wide.merge(h[['option_id', 'saa_date', 'w_intl', 'hedge_ratio_intl']], on=['option_id', 'saa_date'], how='left')

    W = lambda *c: wide[['w_' + x for x in c]].sum(axis=1)
    wide['w_prop_u'] = W('PROP_U_AU', 'PROP_U_INT', 'PROP_U_NSDOM')
    wide['w_unlisted_core'] = W('PE_U', 'PROP_U_AU', 'PROP_U_INT', 'PROP_U_NSDOM', 'INFRA_U', 'CREDIT_U')
    wide['w_unlisted_all'] = wide['w_unlisted_core'] + wide['w_ALT_U']
    wide['w_notspecified_real'] = W('PROP_NS', 'INFRA_NS')
    wide['w_listed_growth'] = W('EQ_AU_L', 'EQ_INT_L', 'PROP_AU_L', 'PROP_INT_L', 'INFRA_L')
    wide['w_total'] = wide[['w_' + c for c in BUCKET_ORDER]].sum(axis=1)
    wide['w_total_ex_fx'] = wide['w_total'] - wide['w_FX_OVERLAY']      # currency overlays are not physical assets

    attrs = (df.sort_values('saa_date')
               .groupby('option_id')
               .agg(option_name=('investment_option_name', 'last'), option_type=('investment_option_type', 'last'),
                    option_category=('investment_option_category', 'last'), fund_name=('rse_name', 'last'),
                    abn=('abn', 'last'), trustee=('rsl_name', 'last'), public_offer=('Public_Offer_Status', 'last'),
                    first_saa=('saa_date', 'min'), last_saa=('saa_date', 'max'))
               .reset_index())
    wide = wide.merge(attrs[['option_id', 'abn']], on='option_id', how='left')
    wide.to_csv(os.path.join(OUT, 'option_quarter_saa.csv'), index=False)
    attrs.to_csv(os.path.join(OUT, 'option_attributes.csv'), index=False)
    print('saa:', wide.shape, 'options', attrs.shape[0], 'quarters', wide['saa_date'].nunique(),
          '| weight sums: median', round(wide['w_total'].median(), 4),
          'share within 0.98-1.02:', round(wide['w_total'].between(0.98, 1.02).mean(), 3))

# ----------------------------------------------------------------------------- 2. fund-year

def read_apra_table(path, sheet):
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = next(i for i in range(15) if str(raw.iat[i, 0]).strip() == 'Period')
    cols, seen = [], {}
    for c in raw.iloc[hdr]:
        name = ' '.join(str(c).split())
        seen[name] = seen.get(name, 0) + 1
        cols.append(name if seen[name] == 1 else f'{name} ({seen[name]})')
    d = raw.iloc[hdr + 1:].copy()
    d.columns = cols
    d['Period'] = pd.to_datetime(d['Period'], errors='coerce')
    return d.dropna(subset=['Period'])


def step_fund():
    # 'a' tables: funds with a 30 June balance date; 'b' tables: other balance dates (e.g. ANZ Staff)
    t2 = pd.concat([read_apra_table(F_FUND, 'Table 2a'), read_apra_table(F_FUND, 'Table 2b')], ignore_index=True)
    t3 = pd.concat([read_apra_table(F_FUND, 'Table 3a'), read_apra_table(F_FUND, 'Table 3b')], ignore_index=True)
    keep2 = {'Period': 'fy_end', 'ABN': 'abn', 'Fund name': 'fund_name_apra', 'Fund type': 'fund_type',
             'RSE Regulatory classification': 'rse_class', 'RSE licensee profit status': 'profit_status',
             'RSE Wind up date': 'wind_up_date', 'Total assets': 'total_assets_k',
             'Number of investment options*': 'n_options', 'Number of MySuper products authorised*': 'n_mysuper',
             "Net members' benefits outflow ratio": 'outflow_ratio', 'Investment expenses ratio': 'inv_exp_ratio',
             'Operating expense ratio': 'op_exp_ratio', 'One-year rate of return': 'ret_1y_fund',
             'Total number of member accounts': 'member_accounts', 'Average member account balance': 'avg_balance_k'}
    keep3 = {'Period': 'fy_end', 'ABN': 'abn', 'Net assets at beginning of period': 'net_assets_bop_k',
             'Employer contributions': 'contrib_employer_k', 'Member contributions': 'contrib_member_k',
             "Total Members' benefit flows in": 'flows_in_k', 'Inward rollovers': 'rollover_in_k',
             'of which: Successor fund transfers': 'sft_in_k', 'Outward rollover': 'rollover_out_k',
             'of which: Successor fund transfers (2)': 'sft_out_k', 'Total benefit payments': 'benefits_k',
             "Total Members' benefit flows out": 'flows_out_k', "Net members' benefits flows": 'net_flows_k',
             'Investment income and gains / losses': 'inv_income_k'}
    miss = [k for k in list(keep2) + list(keep3) if k not in t2.columns and k not in t3.columns]
    if miss:
        print('fund: columns not found (check names):', miss)
    a = t2[[c for c in keep2 if c in t2.columns]].rename(columns=keep2)
    b = t3[[c for c in keep3 if c in t3.columns]].rename(columns=keep3)
    fy = a.merge(b, on=['fy_end', 'abn'], how='left')
    fy['abn'] = pd.to_numeric(fy['abn'], errors='coerce').astype('Int64')
    for c in fy.columns:
        if c.endswith('_k') or c in ('outflow_ratio', 'inv_exp_ratio', 'op_exp_ratio', 'ret_1y_fund',
                                     'member_accounts', 'n_options', 'n_mysuper'):
            fy[c] = pd.to_numeric(fy[c], errors='coerce')
    fy = fy.dropna(subset=['abn']).sort_values(['abn', 'fy_end']).drop_duplicates(['abn', 'fy_end'], keep='last')
    fy['log_assets'] = np.log(fy['total_assets_k'].where(fy['total_assets_k'] > 0))
    bop = fy['net_assets_bop_k'].where(fy['net_assets_bop_k'] > 0)
    fy['net_flow_ratio'] = fy['net_flows_k'] / bop
    fy['gross_flow_ratio'] = (fy['flows_in_k'].abs() + fy['flows_out_k'].abs()) / bop
    # flows excluding successor fund transfers (mergers), and winsorised versions (1st/99th percentile)
    fy['net_flows_ex_sft_k'] = fy['net_flows_k'] - fy['sft_in_k'].fillna(0) + fy['sft_out_k'].fillna(0)
    fy['net_flow_ratio_ex_sft'] = fy['net_flows_ex_sft_k'] / bop
    for c in ['net_flow_ratio', 'net_flow_ratio_ex_sft', 'gross_flow_ratio']:
        lo, hi = fy[c].quantile([0.01, 0.99])
        fy[c + '_w'] = fy[c].clip(lo, hi)
    # a major merger: successor fund transfers in of at least 25% of opening net assets
    fy['sft_in_share'] = fy['sft_in_k'] / bop
    fy['major_merger_year'] = fy['sft_in_share'] >= MERGER_SHARE
    fy.to_csv(os.path.join(OUT, 'fund_year.csv'), index=False)
    print('fund:', fy.shape, 'funds', fy['abn'].nunique(), 'years', fy['fy_end'].dt.year.min(), '-', fy['fy_end'].dt.year.max())

# ----------------------------------------------------------------------------- 3. APRA option-level return measures

def step_perf():
    flag = pd.read_csv(F_PERF, usecols=['abn_investment_option_identifier', 'product_type'], low_memory=False)
    ph = pd.read_csv(F_PERF, usecols=['abn_investment_option_identifier', 'product_phase', 'investment_menu_type'],
                     low_memory=False)
    flag['product_phase'] = ph['product_phase']; flag['investment_menu_type'] = ph['investment_menu_type']
    g = flag.groupby('abn_investment_option_identifier')
    flag = pd.DataFrame({
        'is_mysuper_option': g['product_type'].apply(lambda x: x.eq('MySuper Product').any()),
        'phases': g['product_phase'].apply(lambda x: '|'.join(sorted(set(x.dropna())))),
        'is_lifecycle': g['investment_menu_type'].apply(lambda x: x.eq('Lifecycle Option').any()),
        'on_platform': g['investment_menu_type'].apply(lambda x: x.eq('Platform').any() and not x.ne('Platform').any()),
    }).rename_axis('option_id').reset_index()
    flag.to_csv(os.path.join(OUT, 'option_mysuper_flag.csv'), index=False)
    cols = ['abn_investment_option_identifier', 'period_end_date', 'return_measurement_comparison_percent',
            'return_investment_five_year_volatility_comparison_percent',
            'return_investment_ten_year_volatility_comparison_percent']
    p = pd.read_csv(F_PERF, usecols=cols, low_memory=False)
    p = p.rename(columns={'abn_investment_option_identifier': 'option_id', 'period_end_date': 'saa_date',
                          'return_measurement_comparison_percent': 'apra_return_measure',
                          'return_investment_five_year_volatility_comparison_percent': 'apra_vol_5y',
                          'return_investment_ten_year_volatility_comparison_percent': 'apra_vol_10y'})
    p['saa_date'] = pd.to_datetime(p['saa_date'])
    p = p.groupby(['option_id', 'saa_date'], as_index=False).mean(numeric_only=True)
    p.to_csv(os.path.join(OUT, 'option_quarter_perf.csv'), index=False)
    print('perf:', p.shape, 'options', p['option_id'].nunique())

# ----------------------------------------------------------------------------- 4. option-quarter master

def asof_fund(df, date_col):
    fy = pd.read_csv(os.path.join(OUT, 'fund_year.csv'), parse_dates=['fy_end'])
    fy = fy.drop(columns=['fund_name_apra'], errors='ignore')
    fy['abn'] = fy['abn'].astype('int64')
    left = df.copy()
    left['abn'] = left['abn'].astype('int64')
    left = left.sort_values(date_col)
    fy = fy.sort_values('fy_end')
    return pd.merge_asof(left, fy, left_on=date_col, right_on='fy_end', by='abn', direction='backward')


def checklist_funds():
    cl = pd.read_excel(F_CHECKLIST, sheet_name='Unit prices', header=1)
    cl = cl.rename(columns={c: ' '.join(str(c).split()) for c in cl.columns})
    uni = pd.read_csv(F_UNIVERSE)
    cl = cl.merge(uni[['Fund name', 'ABN']], left_on='Fund (APRA name)', right_on='Fund name', how='left')
    return cl


TYPE_MAP = {'INDUSTRY': 'Industry', 'RETAIL': 'Retail', 'PUBLIC_SECTOR': 'Public Sector', 'CORPORATE': 'Corporate'}
BUCKETS = ['w_' + b for b in BUCKET_ORDER]


def add_flags(m):
    """Data-quality flags and sample indicators (see data/derived/README.md)."""
    uni = pd.read_csv(F_UNIVERSE)[['ABN', 'Fund type']].rename(columns={'ABN': 'abn', 'Fund type': 'fund_type_2026'})
    m = m.merge(uni, on='abn', how='left')
    m['fund_type_fixed'] = m['fund_type_2026'].map(TYPE_MAP).fillna(m['fund_type'])

    # mergers: quarters up to the end of the fund's latest major-merger year
    fy = pd.read_csv(os.path.join(OUT, 'fund_year.csv'), parse_dates=['fy_end'])
    last_merger = fy[fy['major_merger_year']].groupby('abn')['fy_end'].max().rename('last_major_merger_fy')
    m = m.merge(last_merger, left_on='abn', right_index=True, how='left')
    m['pre_merger'] = m['last_major_merger_fy'].notna() & (m['saa_date'] <= m['last_major_merger_fy'])
    m['fund_type_changed'] = m['fund_type'].notna() & (m['fund_type'] != m['fund_type_fixed'])
    m['fund_vars_reliable'] = m['fy_end'].notna() & ~m['pre_merger'] & ~m['fund_type_changed']

    # weights that do not add to 100% (excluding the currency overlay), and funds where this is common
    m['weights_incomplete'] = (m['w_total_ex_fx'] - 1).abs() > SUM_TOL
    share_bad = m.groupby('abn')['weights_incomplete'].transform('mean')
    m['bad_weight_fund'] = share_bad > BAD_FUND_SHARE

    # large quarter-to-quarter jumps in the unlisted share, and those that look like reclassification
    m = m.sort_values(['option_id', 'saa_date'])
    d = m.groupby('option_id')[['w_unlisted_core', 'w_notspecified_real', 'w_ALT_OTHER', 'w_OTHER', 'w_EQ_OTHER',
                                'w_CREDIT_OTHER', 'w_PROP_OTHER', 'w_INFRA_OTHER']].diff()
    m['d_unlisted_core'] = d['w_unlisted_core']
    resid = d.drop(columns='w_unlisted_core').sum(axis=1)
    m['large_jump'] = m['d_unlisted_core'].abs() > JUMP
    m['reclass_jump'] = m['large_jump'] & (resid.abs() >= 0.5 * m['d_unlisted_core'].abs()) & \
                        (np.sign(resid) == -np.sign(m['d_unlisted_core']))

    # pension (retirement-phase only) options
    pens = m['option_name'].fillna('').str.contains(
        r'pension|\(pen\)|retirement income|income stream|account[- ]based|\bttr\b|transition to retirement', case=False)
    m['is_pension'] = m['phases'].eq('Retirement') | pens

    # options with identical allocations in the same quarter
    sig = m[BUCKETS].round(6).astype(str).agg('|'.join, axis=1)
    m['alloc_group'] = pd.factorize(m['saa_date'].astype(str) + '#' + sig)[0]
    m['alloc_group_size'] = m.groupby('alloc_group')['option_id'].transform('size')
    pri = (m.assign(_p1=m['is_pension'], _p2=~m['is_mysuper_option'], _p3=m['option_type'] != 'Multi Manager')
             .sort_values(['alloc_group', '_p1', '_p2', '_p3', 'option_id']))
    rep = pri.groupby('alloc_group')['option_id'].first().rename('alloc_group_rep')
    m = m.merge(rep, left_on='alloc_group', right_index=True, how='left')
    m['is_group_rep'] = m['option_id'] == m['alloc_group_rep']

    # specialist options labelled multi-sector: capital-guaranteed / life products, options concentrated in one
    # non-equity asset class (property, infrastructure, credit or alternatives >= 40%; cash or fixed income >= 80%),
    # and unlisted-only options (no listed growth assets, unlisted >= 50%). Diversified options with high unlisted
    # shares (e.g. AMIST MySuper, ~40-55% unlisted) are NOT flagged. Option level: true in >= half of its quarters.
    prop_all = m[['w_PROP_AU_L', 'w_PROP_INT_L', 'w_PROP_U_AU', 'w_PROP_U_INT', 'w_PROP_U_NSDOM', 'w_PROP_NS',
                  'w_PROP_OTHER']].sum(axis=1)
    infra_all = m[['w_INFRA_L', 'w_INFRA_U', 'w_INFRA_NS', 'w_INFRA_OTHER']].sum(axis=1)
    credit_all = m['w_CREDIT_U'] + m['w_CREDIT_OTHER']
    alt_all = m['w_ALT_U'] + m['w_ALT_OTHER']
    name_spec = m['option_name'].fillna('').str.contains(r'guarant|life pack', case=False)
    conc = ((prop_all >= SPECIALIST) | (infra_all >= SPECIALIST) | (credit_all >= SPECIALIST) |
            (alt_all >= SPECIALIST) | (m['w_CASH'] >= 0.8) | (m['w_FI'] >= 0.8) |
            ((m['w_listed_growth'] + m['w_EQ_OTHER'] < 0.01) & (m['w_unlisted_core'] >= 0.5)))   # unlisted-only options
    m['specialist_q'] = name_spec | conc
    m['specialist_option'] = m.groupby('option_id')['specialist_q'].transform('mean') >= 0.5

    # sample indicators
    m['core_sample'] = (m['option_category'].eq('Multi Sector') & m['option_type'].eq('Multi Manager') &
                        ~m['is_pension'] & ~m['weights_incomplete'] & ~m['bad_weight_fund'] & ~m['specialist_option'])
    m['core_sample_dedup'] = m['core_sample'] & m['is_group_rep']
    return m


def step_merge():
    saa = pd.read_csv(os.path.join(OUT, 'option_quarter_saa.csv'), parse_dates=['saa_date'])
    attrs = pd.read_csv(os.path.join(OUT, 'option_attributes.csv'), parse_dates=['first_saa', 'last_saa'])
    perf = pd.read_csv(os.path.join(OUT, 'option_quarter_perf.csv'), parse_dates=['saa_date'])
    # fill quarters missing inside an option's history by carrying the previous allocation forward
    qs = pd.DatetimeIndex(sorted(saa['saa_date'].unique()))
    full = []
    for oid, g in saa.groupby('option_id'):
        idx = qs[(qs >= g['saa_date'].min()) & (qs <= g['saa_date'].max())]
        g = g.set_index('saa_date').reindex(idx)
        g['filled_gap'] = g['option_id'].isna()
        g = g.ffill()
        full.append(g.rename_axis('saa_date').reset_index())
    saa = pd.concat(full, ignore_index=True)
    m = saa.merge(attrs.drop(columns=['abn']), on='option_id', how='left')
    m = m.merge(perf, on=['option_id', 'saa_date'], how='left')
    flag = pd.read_csv(os.path.join(OUT, 'option_mysuper_flag.csv'))
    m = m.merge(flag, on='option_id', how='left')
    for c in ['is_mysuper_option', 'is_lifecycle', 'on_platform']:
        m[c] = m[c].astype('boolean').fillna(False).astype(bool)
    m = asof_fund(m, 'saa_date')
    m['major_merger_year'] = m['major_merger_year'].astype('boolean').fillna(False).astype(bool)
    m = add_flags(m)
    cl = checklist_funds()
    m['in_download_checklist'] = m['abn'].isin(cl['ABN'].dropna().astype('int64'))
    m = m.sort_values(['option_id', 'saa_date'])
    m = m[['option_id', 'saa_date'] + [c for c in m.columns if c not in ('option_id', 'saa_date')]]
    m.to_csv(os.path.join(OUT, 'option_quarter_master.csv'), index=False)
    print('merge:', m.shape, '| options', m['option_id'].nunique(), '| funds', m['abn'].nunique(),
          '| rows with fund-year data', round(m['fy_end'].notna().mean(), 3),
          '| rows in download-checklist funds', round(m['in_download_checklist'].mean(), 3))
    last = m[m['saa_date'] == m['saa_date'].max()]
    print('flags (all rows): filled_gap', int(m['filled_gap'].sum()), '| pre_merger', int(m['pre_merger'].sum()),
          '| weights_incomplete', int(m['weights_incomplete'].sum()), '| bad_weight_fund', int(m['bad_weight_fund'].sum()),
          '| large_jump', int(m['large_jump'].sum()), '| reclass_jump', int(m['reclass_jump'].sum()),
          '| is_pension', int(m['is_pension'].sum()), '| is_lifecycle', int(m['is_lifecycle'].sum()),
          '| specialist_option', int(m['specialist_option'].sum()))
    print('June 2026: options', len(last), '| core_sample', int(last['core_sample'].sum()),
          '| core_sample_dedup', int(last['core_sample_dedup'].sum()), '| funds in core', last.loc[last['core_sample'], 'abn'].nunique())

    # mapping template: one row per option of the checklist funds (latest quarter), to link price series
    last = m[m['saa_date'] == m['saa_date'].max()]
    t = last[last['in_download_checklist']][['abn', 'fund_name', 'option_id', 'option_name', 'option_category',
                                             'option_type', 'is_mysuper_option', 'is_pension', 'is_lifecycle',
                                             'core_sample', 'core_sample_dedup', 'w_unlisted_core', 'first_saa']].copy()
    pr = cl[['ABN', 'Priority']].dropna().rename(columns={'ABN': 'abn', 'Priority': 'fund_priority'})
    pr['abn'] = pr['abn'].astype('int64')
    t = t.merge(pr, on='abn', how='left')
    for c in ['price_file', 'price_series_name', 'price_type', 'source_url', 'download_date', 'fee_tax_basis',
              'first_price_date', 'notes']:
        t[c] = ''
    t = t.sort_values(['fund_priority', 'fund_name', 'core_sample_dedup', 'is_mysuper_option', 'w_unlisted_core'],
                      ascending=[True, True, False, False, False])
    path = os.path.join(OUT, 'unit_price_mapping_template.csv')
    if os.path.exists(path):
        old = pd.read_csv(path, dtype=str)
        filled = [c for c in ('price_file', 'price_series_name', 'source_url') if c in old.columns and old[c].notna().any()]
        if filled:   # never overwrite a template that has been filled in
            path = os.path.join(OUT, 'unit_price_mapping_template_NEW.csv')
    t.to_csv(path, index=False)
    print('mapping template:', t.shape, '->', os.path.basename(path))

# ----------------------------------------------------------------------------- 5. weekly master (needs unit prices)

def load_unit_prices():
    """Standard format: data/derived/unit_prices/*.csv with columns option_id, date, price
    (optional: price_type = 'unit_price' or 'crediting_rate'). For crediting-rate series, 'price'
    must be the chained index (100 * cumulative product of 1 + daily rate)."""
    files = sorted(glob.glob(os.path.join(OUT, 'unit_prices', '*.csv')))
    if not files:
        return None
    parts = []
    for f in files:
        d = pd.read_csv(f)
        need = {'option_id', 'date', 'price'}
        if not need.issubset(d.columns):
            print('skipped (needs option_id, date, price):', os.path.basename(f))
            continue
        raw_date = d['date'].astype(str).str.strip()
        iso = pd.to_datetime(raw_date, format='ISO8601', errors='coerce')             # yyyy-mm-dd
        dmy = pd.to_datetime(raw_date, format='%d/%m/%Y', errors='coerce')            # dd/mm/yyyy (Australian)
        d['date'] = iso.fillna(dmy)
        if d['date'].isna().any():
            print('unparsed dates in', os.path.basename(f), ':', raw_date[d['date'].isna()].head(3).tolist())
        d['price'] = pd.to_numeric(d['price'], errors='coerce')
        if 'price_type' not in d.columns:
            d['price_type'] = 'unit_price'
        d['source_file'] = os.path.basename(f)
        parts.append(d.dropna(subset=['date', 'price'])[['option_id', 'date', 'price', 'price_type', 'source_file']])
    return pd.concat(parts, ignore_index=True) if parts else None


def weekly_returns(px: pd.DataFrame, max_gap_days: int = 5) -> pd.DataFrame:
    out = []
    for oid, g in px.sort_values('date').groupby('option_id'):
        g = g.drop_duplicates('date', keep='last').set_index('date')
        weds = pd.date_range(g.index.min(), g.index.max(), freq='W-WED')
        s = g['price'].reindex(g.index.union(weds)).ffill()
        last_obs = pd.Series(g.index, index=g.index).reindex(g.index.union(weds)).ffill()
        w = pd.DataFrame({'price': s.loc[weds], 'price_date': last_obs.loc[weds]})
        w['stale_days'] = (w.index - w['price_date']).dt.days
        w.loc[w['stale_days'] > max_gap_days, 'price'] = np.nan
        w['ret'] = np.log(w['price']).diff()
        w['option_id'] = oid
        w['price_type'] = g['price_type'].iloc[-1]
        out.append(w.reset_index(names='week'))
    return pd.concat(out, ignore_index=True)


def step_weekly():
    px = load_unit_prices()
    if px is None:
        print('weekly: no unit-price files in data/derived/unit_prices/ yet -- nothing to do.')
        return
    wk = weekly_returns(px)
    # start-of-quarter weights: allocation reported at the end of the previous quarter
    wk['saa_date'] = (wk['week'].dt.to_period('Q') - 1).dt.to_timestamp(how='end').dt.normalize()
    # everything option-level (weights, attributes, flags) from the option-quarter master;
    # fund-year variables are re-attached as of each week below
    oq = pd.read_csv(os.path.join(OUT, 'option_quarter_master.csv'), parse_dates=['saa_date'], low_memory=False)
    fy_cols = [c for c in pd.read_csv(os.path.join(OUT, 'fund_year.csv'), nrows=1).columns if c != 'abn']
    oq = oq.drop(columns=[c for c in fy_cols if c in oq.columns])
    missing = sorted(set(wk['option_id']) - set(oq['option_id']))
    if missing:
        print('weekly: option_ids not found in APRA data:', missing[:20])
    # keep weeks whose start-of-quarter allocation exists in the APRA SAA file
    m = wk.merge(oq, on=['option_id', 'saa_date'], how='inner')
    # priced representative of each allocation group: lifecycle stages and other options without a
    # published series are replaced by an identically allocated option that has prices that quarter
    # coverage = weeks with a return / all Wednesdays of the quarter (not / rows present, which overstates
    # coverage in the first and last quarter of a price history)
    q = (m.assign(_q=m['week'].dt.to_period('Q')).groupby(['option_id', 'saa_date'])
         .agg(_valid=('ret', lambda r: r.notna().sum()), _q=('_q', 'first')).reset_index())
    q['ret_coverage_q'] = q['_valid'] / q['_q'].map(lambda p: len(pd.date_range(p.start_time, p.end_time, freq='W-WED')))
    q = q[['option_id', 'saa_date', 'ret_coverage_q']]
    oq = oq.merge(q, on=['option_id', 'saa_date'], how='left')
    oq['priced_q'] = oq['ret_coverage_q'].fillna(0) >= 0.5
    cand = oq[oq['core_sample'] & oq['priced_q']].sort_values(
        ['alloc_group', 'is_group_rep', 'option_id'], ascending=[True, False, True])
    rep_p = cand.groupby('alloc_group')['option_id'].first().rename('alloc_group_rep_priced')
    m = m.merge(rep_p, left_on='alloc_group', right_index=True, how='left')
    m = m.merge(oq[['option_id', 'saa_date', 'ret_coverage_q', 'priced_q']], on=['option_id', 'saa_date'], how='left')
    m['is_group_rep_priced'] = m['option_id'] == m['alloc_group_rep_priced']
    m['core_sample_dedup_priced'] = m['core_sample'] & m['is_group_rep_priced']
    m = asof_fund(m, 'week')
    m['fy_end_dummy'] = ((m['week'].dt.month == 6) & (m['week'].dt.day >= 17)) | \
                        ((m['week'].dt.month == 7) & (m['week'].dt.day <= 14))
    m = m.sort_values(['option_id', 'week'])
    m.to_csv(os.path.join(OUT, 'master_weekly.csv.gz'), index=False, compression='gzip')
    print('weekly: core_sample_dedup_priced options', m.loc[m['core_sample_dedup_priced'], 'option_id'].nunique(),
          '| option-weeks with returns', int(m.loc[m['core_sample_dedup_priced'], 'ret'].notna().sum()))
    print('weekly:', m.shape, '| options', m['option_id'].nunique(),
          '| weeks', m['week'].min().date(), 'to', m['week'].max().date(),
          '| rows with weights', round(m['w_total'].notna().mean(), 3))


STEPS = {'saa': step_saa, 'fund': step_fund, 'perf': step_perf, 'merge': step_merge, 'weekly': step_weekly}

if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'all'
    for name in (STEPS if arg == 'all' else [arg]):
        STEPS[name]()
