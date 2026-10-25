import pandas as pd, numpy as np, time
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.utils.indexed_list import IndexedList
from openpyxl.comments import Comment

import os, sys
# run:  python3 code/2_data_checks/make_master_xlsx.py  (from any folder)
SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')) + '/'
sys.path.insert(0, os.path.join(SRC, 'code', '1_build'))
from build_master import bucket, BUCKET_ORDER
from openpyxl.workbook.properties import CalcProperties
OUTF = os.path.join(SRC, 'data', 'derived', 'option_quarter_master.xlsx')
t0 = time.time()
m = pd.read_csv(SRC + 'data/derived/option_quarter_master.csv', low_memory=False)
for c in ['saa_date', 'first_saa', 'last_saa', 'fy_end', 'wind_up_date', 'last_major_merger_fy']:
    m[c] = pd.to_datetime(m[c], errors='coerce')
m = m.sort_values(['saa_date', 'fund_name', 'option_id']).reset_index(drop=True)

# independent source total straight from the raw APRA file
raw = pd.read_csv(SRC + 'data/raw/apra/QSPS Historical SAA June 2026.csv', low_memory=False,
                  usecols=['investment_option_identifier', 'time_key', 'rse_name', 'investment_option_name',
                           'ConsolidatedSectorType', 'ConsolidatedListingType', 'ConsolidatedDomicileType',
                           'InvestmentBenchmarkAllocationPercent', 'InvestmentCurrencyHedgingRatioPercent'])
raw['saa_date'] = pd.to_datetime(raw['time_key'].astype(str), format='%Y%m%d')
rt = raw.groupby(['investment_option_identifier', 'saa_date'])['InvestmentBenchmarkAllocationPercent'].sum()
rt = rt.rename('apra_raw_total').reset_index().rename(columns={'investment_option_identifier': 'option_id'})
m = m.merge(rt, on=['option_id', 'saa_date'], how='left')
m['key'] = m['option_id'] + '|' + m['saa_date'].dt.strftime('%Y-%m-%d')
print('loaded', m.shape, round(time.time() - t0), 's')

# ----------------------------------------------------------------------------- styles
FONT = 'Arial'
f_norm = Font(name=FONT, size=10)
f_head = Font(name=FONT, size=10, bold=True)
f_title = Font(name=FONT, size=14, bold=True)
f_sub = Font(name=FONT, size=11, bold=True)
f_input = Font(name=FONT, size=10, color='0000FF')
f_link = Font(name=FONT, size=10, color='008000')
fill_head = PatternFill('solid', fgColor='D9D9D9')
fill_check = PatternFill('solid', fgColor='EDEDED')
fill_input = PatternFill('solid', fgColor='FFFF00')
thin = Side(style='thin', color='808080')
b_bottom = Border(bottom=thin)
wrap = Alignment(wrap_text=True, vertical='top')

wb = Workbook(write_only=True)
wb.calculation = CalcProperties(fullCalcOnLoad=True)   # Excel computes every check when the file is opened
wb._fonts = IndexedList()
wb._fonts.add(f_norm)                      # workbook default font -> Arial 10


def cell(ws, v, font=None, fmt=None, fill=None, align=None, border=None):
    c = WriteOnlyCell(ws, value=v)
    if font: c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if align: c.alignment = align
    if border: c.border = border
    return c


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.to_pydatetime()
    if v is pd.NaT:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v

# ----------------------------------------------------------------------------- column layout of Data
cols = list(m.columns)                                    # 78 master cols + apra_raw_total + key
col = {c: L(i + 1) for i, c in enumerate(cols)}
FB, LB = col['w_' + BUCKET_ORDER[0]], col['w_' + BUCKET_ORDER[-1]]
checks = ['sum_buckets', 'chk_total', 'chk_source', 'sum_ex_fx', 'chk_near1', 'chk_prop_u', 'chk_unlisted_core',
          'chk_unlisted_all', 'chk_listed_growth', 'chk_ns_real', 'chk_hedge', 'n_negative', 'all_ok']
n0 = len(cols)
for j, c in enumerate(checks):
    col[c] = L(n0 + j + 1)
NROW = len(m) + 1
TOL1, TOL2 = 'Checks!$C$5', 'Checks!$C$6'     # sum tolerance, rounding tolerance


def W(name, r):
    return f"{col['w_' + name]}{r}"


def check_formulas(r):
    c = lambda k: f'{col[k]}{r}'
    return {
        'sum_buckets': f'=SUM({FB}{r}:{LB}{r})',
        'chk_total': f"=ABS({c('sum_buckets')}-{c('w_total')})<={TOL2}",
        'chk_source': f"=IF({c('filled_gap')},TRUE,ABS({c('sum_buckets')}-{c('apra_raw_total')})<={TOL2})",
        'sum_ex_fx': f"={c('sum_buckets')}-{W('FX_OVERLAY', r)}",
        'chk_near1': f"=ABS({c('sum_ex_fx')}-1)<={TOL1}",
        'chk_prop_u': f"=ABS({c('w_prop_u')}-({W('PROP_U_AU', r)}+{W('PROP_U_INT', r)}+{W('PROP_U_NSDOM', r)}))<={TOL2}",
        'chk_unlisted_core': (f"=ABS({c('w_unlisted_core')}-({W('PE_U', r)}+{W('PROP_U_AU', r)}+{W('PROP_U_INT', r)}"
                              f"+{W('PROP_U_NSDOM', r)}+{W('INFRA_U', r)}+{W('CREDIT_U', r)}))<={TOL2}"),
        'chk_unlisted_all': f"=ABS({c('w_unlisted_all')}-({c('w_unlisted_core')}+{W('ALT_U', r)}))<={TOL2}",
        'chk_listed_growth': (f"=ABS({c('w_listed_growth')}-({W('EQ_AU_L', r)}+{W('EQ_INT_L', r)}+{W('PROP_AU_L', r)}"
                              f"+{W('PROP_INT_L', r)}+{W('INFRA_L', r)}))<={TOL2}"),
        'chk_ns_real': f"=ABS({c('w_notspecified_real')}-({W('PROP_NS', r)}+{W('INFRA_NS', r)}))<={TOL2}",
        'chk_hedge': f"=IF({c('hedge_ratio_intl')}=\"\",TRUE,AND({c('hedge_ratio_intl')}>=0,{c('hedge_ratio_intl')}<=1))",
        'n_negative': f'=COUNTIF({FB}{r}:{LB}{r},"<0")',
        'all_ok': (f"=AND({c('chk_total')},{c('chk_source')},{c('chk_near1')},{c('chk_prop_u')},{c('chk_unlisted_core')},"
                   f"{c('chk_unlisted_all')},{c('chk_listed_growth')},{c('chk_ns_real')},{c('chk_hedge')})"),
    }

# ----------------------------------------------------------------------------- glossary content
G = {  # name: (description, source, unit / type)
 'option_id': ('APRA investment option identifier: <fund ABN>-<option code>. Unique key of an option.', 'QSPS Historical SAA', 'text'),
 'saa_date': ('Quarter end at which the strategic asset allocation is reported. In the weekly file these weights apply to the following quarter (start-of-quarter weights).', 'QSPS Historical SAA (time_key)', 'date'),
 'w_EQ_AU_L': ('Listed equity, Australian domicile.', 'SAA: Equity / Listed / Australian', 'weight (share of option)'),
 'w_EQ_INT_L': ('Listed equity, international or unspecified domicile.', 'SAA: Equity / Listed / other domicile', 'weight'),
 'w_EQ_OTHER': ('Equity with listing type Not Applicable or Not Specified (e.g. overlays, unclassified).', 'SAA: Equity / NA or NS', 'weight'),
 'w_PE_U': ('Unlisted equity (private equity).', 'SAA: Equity / Unlisted', 'weight'),
 'w_PROP_AU_L': ('Listed property, Australian domicile.', 'SAA: Property / Listed / Australian', 'weight'),
 'w_PROP_INT_L': ('Listed property, international or unspecified domicile.', 'SAA: Property / Listed / other', 'weight'),
 'w_PROP_U_AU': ('Unlisted property, Australian domicile.', 'SAA: Property / Unlisted / Australian', 'weight'),
 'w_PROP_U_INT': ('Unlisted property, international domicile.', 'SAA: Property / Unlisted / International', 'weight'),
 'w_PROP_U_NSDOM': ('Unlisted property, domicile Not Specified or Not Applicable.', 'SAA: Property / Unlisted / NS or NA', 'weight'),
 'w_PROP_NS': ('Property with listing type Not Specified.', 'SAA: Property / Not Specified', 'weight'),
 'w_PROP_OTHER': ('Property with listing type Not Applicable.', 'SAA: Property / Not Applicable', 'weight'),
 'w_INFRA_L': ('Listed infrastructure.', 'SAA: Infrastructure / Listed', 'weight'),
 'w_INFRA_U': ('Unlisted infrastructure.', 'SAA: Infrastructure / Unlisted', 'weight'),
 'w_INFRA_NS': ('Infrastructure with listing type Not Specified.', 'SAA: Infrastructure / Not Specified', 'weight'),
 'w_INFRA_OTHER': ('Infrastructure with listing type Not Applicable.', 'SAA: Infrastructure / Not Applicable', 'weight'),
 'w_CREDIT_U': ('Unlisted credit (private credit).', 'SAA: Credit / Unlisted', 'weight'),
 'w_CREDIT_OTHER': ('Credit that is listed, Not Specified or Not Applicable (can include negative overlay positions).', 'SAA: Credit / other', 'weight'),
 'w_FI': ('Fixed income, including "Fixed Income Excluding Credit", any listing type.', 'SAA: Fixed Income', 'weight'),
 'w_CASH': ('Cash.', 'SAA: Cash', 'weight'),
 'w_ALT_U': ('Alternatives (incl. growth and defensive alternatives), unlisted.', 'SAA: Alternatives / Unlisted', 'weight'),
 'w_ALT_OTHER': ('Alternatives with other listing types.', 'SAA: Alternatives / other', 'weight'),
 'w_FX_OVERLAY': ('Currency exposure overlay. Not a physical asset, so it is excluded when checking that weights sum to 1.', 'SAA: Currency Exposure', 'weight'),
 'w_OTHER': ('Any sector not listed above.', 'SAA: residual', 'weight'),
 'w_intl': ('Share of the option in international-domicile assets (all sectors).', 'Derived from SAA', 'weight'),
 'hedge_ratio_intl': ('Allocation-weighted currency hedging ratio of international assets. Blank if no international assets.', 'SAA: InvestmentCurrencyHedgingRatioPercent', 'ratio 0-1'),
 'w_prop_u': ('All unlisted property = PROP_U_AU + PROP_U_INT + PROP_U_NSDOM.', 'Derived', 'weight'),
 'w_unlisted_core': ('Main unlisted exposure = PE_U + all unlisted property + INFRA_U + CREDIT_U.', 'Derived', 'weight'),
 'w_unlisted_all': ('w_unlisted_core + ALT_U.', 'Derived', 'weight'),
 'w_notspecified_real': ('Property and infrastructure with listing type Not Specified = PROP_NS + INFRA_NS.', 'Derived', 'weight'),
 'w_listed_growth': ('Listed equity, property and infrastructure = EQ_AU_L + EQ_INT_L + PROP_AU_L + PROP_INT_L + INFRA_L.', 'Derived', 'weight'),
 'w_total': ('Sum of all 23 bucket weights, as computed by build_master.py.', 'Derived', 'weight'),
 'w_total_ex_fx': ('w_total minus w_FX_OVERLAY.', 'Derived', 'weight'),
 'abn': ('Fund (RSE) ABN. Links options to fund-level data.', 'QSPS Historical SAA', 'number'),
 'option_name': ('Latest reported option name.', 'QSPS Historical SAA', 'text'),
 'option_type': ('Multi Manager, Single Manager - Unlisted, Separately Managed Account, etc.', 'QSPS Historical SAA', 'text'),
 'option_category': ('Multi Sector or Single Sector.', 'QSPS Historical SAA', 'text'),
 'fund_name': ('Latest reported fund (RSE) name.', 'QSPS Historical SAA', 'text'),
 'trustee': ('RSE licensee.', 'QSPS Historical SAA', 'text'),
 'public_offer': ('Public offer status of the fund.', 'QSPS Historical SAA', 'text'),
 'first_saa': ('First quarter the option appears in the SAA file.', 'Derived', 'date'),
 'last_saa': ('Last quarter the option appears in the SAA file.', 'Derived', 'date'),
 'apra_return_measure': ('APRA field return_measurement_comparison_percent (definition to be confirmed in APRA notes before use).', 'QSPS Historical performance', 'decimal'),
 'apra_vol_5y': ('APRA five-year return volatility measure.', 'QSPS Historical performance', 'decimal'),
 'apra_vol_10y': ('APRA ten-year return volatility measure.', 'QSPS Historical performance', 'decimal'),
 'is_mysuper_option': ('TRUE if the option is offered through a MySuper product.', 'QSPS Historical performance (product_type)', 'TRUE/FALSE'),
 'fy_end': ('Balance date of the fund-year record attached (latest on or before saa_date).', 'APRA annual fund-level statistics', 'date'),
 'fund_type': ('Industry, Retail, Public Sector, Corporate, Retail - ERF.', 'APRA annual fund-level statistics, Table 2a/2b', 'text'),
 'rse_class': ('RSE regulatory classification.', 'Table 2a/2b', 'text'),
 'profit_status': ('RSE licensee profit status.', 'Table 2a/2b', 'text'),
 'wind_up_date': ('RSE wind-up date, if any.', 'Table 2a/2b', 'date'),
 'total_assets_k': ('Total assets of the fund.', 'Table 2a/2b', "$'000"),
 'n_options': ('Number of investment options.', 'Table 2a/2b', 'count'),
 'n_mysuper': ('Number of MySuper products authorised.', 'Table 2a/2b', 'count'),
 'outflow_ratio': ("Net members' benefits outflow ratio.", 'Table 2a/2b', 'ratio'),
 'inv_exp_ratio': ('Investment expenses ratio.', 'Table 2a/2b', 'ratio'),
 'op_exp_ratio': ('Operating expense ratio.', 'Table 2a/2b', 'ratio'),
 'ret_1y_fund': ('Fund one-year rate of return.', 'Table 2a/2b', 'decimal'),
 'member_accounts': ('Total number of member accounts.', 'Table 2a/2b', 'count'),
 'avg_balance_k': ('Average member account balance.', 'Table 2a/2b', "$'000"),
 'net_assets_bop_k': ('Net assets at beginning of period.', 'Table 3a/3b', "$'000"),
 'contrib_employer_k': ('Employer contributions.', 'Table 3a/3b', "$'000"),
 'contrib_member_k': ('Member contributions.', 'Table 3a/3b', "$'000"),
 'flows_in_k': ("Total members' benefit flows in.", 'Table 3a/3b', "$'000"),
 'rollover_in_k': ('Inward rollovers.', 'Table 3a/3b', "$'000"),
 'sft_in_k': ('Inward successor fund transfers (part of inward rollovers).', 'Table 3a/3b', "$'000"),
 'rollover_out_k': ('Outward rollovers.', 'Table 3a/3b', "$'000"),
 'sft_out_k': ('Outward successor fund transfers (part of outward rollovers).', 'Table 3a/3b', "$'000"),
 'benefits_k': ('Total benefit payments.', 'Table 3a/3b', "$'000"),
 'flows_out_k': ("Total members' benefit flows out.", 'Table 3a/3b', "$'000"),
 'net_flows_k': ("Net members' benefits flows.", 'Table 3a/3b', "$'000"),
 'inv_income_k': ('Investment income and gains/losses.', 'Table 3a/3b', "$'000"),
 'log_assets': ('Natural log of total_assets_k.', 'Derived', 'log'),
 'net_flow_ratio': ('net_flows_k / net_assets_bop_k (blank if opening assets are zero).', 'Derived', 'ratio'),
 'gross_flow_ratio': ('(|flows_in_k| + |flows_out_k|) / net_assets_bop_k.', 'Derived', 'ratio'),
 'fund_type_2026': ('Fund type in the June 2026 fund universe file.', 'fund_universe_june2026.csv', 'text'),
 'in_download_checklist': ('TRUE if the fund is one of the 41 funds on the unit-price download checklist.', 'Fund_website_download_checklist.xlsx', 'TRUE/FALSE'),
 'filled_gap': ('TRUE if APRA reported no allocation for this quarter inside the option history; the previous quarter is carried forward.', 'Derived', 'TRUE/FALSE'),
 'phases': ('Product phases through which the option is offered (Accumulation, Retirement, or both).', 'QSPS Historical performance (product_phase)', 'text'),
 'is_lifecycle': ('TRUE if the option is a lifecycle (age-based) stage.', 'QSPS Historical performance (investment_menu_type = Lifecycle Option)', 'TRUE/FALSE'),
 'on_platform': ('TRUE if the option is offered only through platform menus.', 'QSPS Historical performance (investment_menu_type = Platform)', 'TRUE/FALSE'),
 'net_flows_ex_sft_k': ('Net member flows excluding successor fund transfers in and out (mergers).', 'Derived from Table 3a/3b', "$'000"),
 'net_flow_ratio_ex_sft': ('net_flows_ex_sft_k / net_assets_bop_k.', 'Derived', 'ratio'),
 'net_flow_ratio_w': ('net_flow_ratio winsorised at the 1st and 99th percentiles of the fund-year panel.', 'Derived', 'ratio'),
 'net_flow_ratio_ex_sft_w': ('net_flow_ratio_ex_sft winsorised at the 1st and 99th percentiles. Preferred flow measure.', 'Derived', 'ratio'),
 'gross_flow_ratio_w': ('gross_flow_ratio winsorised at the 1st and 99th percentiles.', 'Derived', 'ratio'),
 'sft_in_share': ('Successor fund transfers in / opening net assets for the fund-year attached.', 'Derived', 'ratio'),
 'major_merger_year': ('TRUE if the attached fund-year had successor fund transfers in of at least 25% of opening net assets.', 'Derived', 'TRUE/FALSE'),
 'fund_type_fixed': ('Fund type used in analysis: the June 2026 classification for every quarter (historical type if not in the 2026 list). Avoids type changes caused by mergers (e.g. ART shown as Public Sector before 2022).', 'fund_universe_june2026.csv', 'text'),
 'last_major_merger_fy': ("Balance date of the fund's latest major-merger year, if any.", 'Derived', 'date'),
 'pre_merger': ("TRUE for quarters up to the end of the fund's latest major-merger year. Fund-level variables then describe the fund before the merger, while the option history is back-filled under today's fund.", 'Derived', 'TRUE/FALSE'),
 'fund_type_changed': ('TRUE if the historical fund type differs from fund_type_fixed.', 'Derived', 'TRUE/FALSE'),
 'fund_vars_reliable': ('TRUE if fund-level variables exist, are not pre-merger and the fund type did not change. Use fund-level variables only where TRUE.', 'Derived', 'TRUE/FALSE'),
 'weights_incomplete': ('TRUE if weights excluding the currency overlay are more than 2 pp from 100%.', 'Derived', 'TRUE/FALSE'),
 'bad_weight_fund': ('TRUE for funds where more than 2% of option-quarters have incomplete weights (Avanteos, Netwealth, Wealth Personal).', 'Derived', 'TRUE/FALSE'),
 'd_unlisted_core': ('Change in w_unlisted_core from the previous quarter.', 'Derived', 'weight'),
 'large_jump': ('TRUE if |d_unlisted_core| > 10 pp.', 'Derived', 'TRUE/FALSE'),
 'reclass_jump': ('TRUE if a large jump is at least half offset by opposite moves in the not-specified or other buckets: likely a reporting reclassification, not a real reallocation.', 'Derived', 'TRUE/FALSE'),
 'is_pension': ('TRUE if the option is offered only in the retirement phase, or its name indicates a pension / retirement income option. Excluded from the core sample (different tax, duplicate of accumulation option).', 'Derived', 'TRUE/FALSE'),
 'alloc_group': ('Group id: options with identical bucket weights in the same quarter.', 'Derived', 'id'),
 'alloc_group_size': ('Number of options in the allocation group.', 'Derived', 'count'),
 'alloc_group_rep': ('Representative option of the group (accumulation first, then MySuper, then multi-manager, then lowest id).', 'Derived', 'text'),
 'is_group_rep': ('TRUE if this option is its group representative.', 'Derived', 'TRUE/FALSE'),
 'specialist_q': ('TRUE in a quarter if the option looks like a specialist option: capital-guaranteed or life product by name; property, infrastructure, credit or alternatives >= 40%; cash or fixed income >= 80%; or no listed growth assets with unlisted >= 50%.', 'Derived', 'TRUE/FALSE'),
 'specialist_option': ('TRUE if specialist_q holds in at least half of the option\'s quarters (e.g. HESTA Property and Infrastructure, ART Unlisted Assets, capital-guaranteed options). Excluded from the core sample. Diversified options with high unlisted shares are not flagged.', 'Derived', 'TRUE/FALSE'),
 'core_sample': ('TRUE for the main sample: multi-sector, multi-manager, not pension, weights complete, not a bad-weight fund, not a specialist option.', 'Derived', 'TRUE/FALSE'),
 'core_sample_dedup': ('core_sample and group representative: one option per identical allocation in each quarter.', 'Derived', 'TRUE/FALSE'),
 'apra_raw_total': ('Independent control total: sum of every raw allocation row for this option and quarter, taken directly from the APRA file (not from build_master.py).', 'QSPS Historical SAA, summed in Python', 'weight'),
 'key': ('Lookup key = option_id|saa_date (yyyy-mm-dd). Used by the Audit sheet.', 'Derived', 'text'),
 'sum_buckets': ('FORMULA. Sum of the 23 bucket weights in this row.', 'Check formula', 'weight'),
 'chk_total': ('FORMULA. TRUE if sum_buckets equals w_total within the rounding tolerance.', 'Check formula', 'TRUE/FALSE'),
 'chk_source': ('FORMULA. TRUE if sum_buckets equals apra_raw_total (the raw APRA rows) within the rounding tolerance: no allocation row was lost or double-counted when grouping into buckets. Carried-forward quarters (filled_gap) have no raw rows and pass by definition.', 'Check formula', 'TRUE/FALSE'),
 'sum_ex_fx': ('FORMULA. sum_buckets minus the currency overlay.', 'Check formula', 'weight'),
 'chk_near1': ('FORMULA. TRUE if sum_ex_fx is within the sum tolerance of 1 (100%). FALSE rows are reported this way by APRA and should be reviewed, not necessarily corrected.', 'Check formula', 'TRUE/FALSE'),
 'chk_prop_u': ('FORMULA. TRUE if w_prop_u equals its three components.', 'Check formula', 'TRUE/FALSE'),
 'chk_unlisted_core': ('FORMULA. TRUE if w_unlisted_core equals its six components.', 'Check formula', 'TRUE/FALSE'),
 'chk_unlisted_all': ('FORMULA. TRUE if w_unlisted_all = w_unlisted_core + w_ALT_U.', 'Check formula', 'TRUE/FALSE'),
 'chk_listed_growth': ('FORMULA. TRUE if w_listed_growth equals its five components.', 'Check formula', 'TRUE/FALSE'),
 'chk_ns_real': ('FORMULA. TRUE if w_notspecified_real = w_PROP_NS + w_INFRA_NS.', 'Check formula', 'TRUE/FALSE'),
 'chk_hedge': ('FORMULA. TRUE if hedge_ratio_intl is blank or between 0 and 1.', 'Check formula', 'TRUE/FALSE'),
 'n_negative': ('FORMULA. Number of negative bucket weights (overlays or short positions reported by APRA). Informational.', 'Check formula', 'count'),
 'all_ok': ('FORMULA. TRUE if every TRUE/FALSE check in the row passes.', 'Check formula', 'TRUE/FALSE'),
}
missing = [c for c in cols + checks if c not in G]
assert not missing, missing

# ----------------------------------------------------------------------------- 1. README
ws = wb.create_sheet('README')
ws.column_dimensions['A'].width = 3; ws.column_dimensions['B'].width = 120
lines = [
    ('Option-quarter master dataset: allocations with weight checks', f_title),
    ('Source: option_quarter_master.csv (built by code/1_build/build_master.py from APRA QSPS Historical SAA, QSPS Historical performance and APRA annual fund-level statistics). 43,482 option-quarters, 1,357 options, 52 funds, June 2014 to June 2026.', f_norm),
    ('', f_norm),
    ('Sheets', f_sub),
    ('Checks  - summary of every weight check, tolerances (the only cells to edit), sample and quality flags, and results by quarter.', f_norm),
    ('Data  - the full dataset (values) followed by grey check columns (formulas). Filter any check column on FALSE to see the rows that fail.', f_norm),
    ('Audit_Jun2026  - rebuilds the key buckets for June 2026 directly from the raw APRA rows with SUMIFS and compares them with the Data sheet.', f_norm),
    ('Raw_Jun2026  - the 14,998 raw APRA allocation rows for June 2026; the bucket of each row is assigned by formula from Bucket_map.', f_norm),
    ('Bucket_map  - the rule that assigns each APRA sector / listing type / domicile combination to a bucket.', f_norm),
    ('Glossary  - definition, source and unit of every column.', f_norm),
    ('', f_norm),
    ('What the checks test', f_sub),
    ('1. Aggregation: the buckets add up to w_total (chk_total) and to the raw APRA rows (chk_source), so nothing was lost or double-counted.', f_norm),
    ('2. Completeness: excluding the currency overlay, weights sum to 100% within the tolerance (chk_near1).', f_norm),
    ('3. Derived variables: w_prop_u, w_unlisted_core, w_unlisted_all, w_listed_growth and w_notspecified_real equal the sum of their components.', f_norm),
    ('4. Ranges: hedging ratios lie between 0 and 1; negative bucket weights are counted (n_negative) for information.', f_norm),
    ('5. Bucket rule: Audit_Jun2026 recomputes the unlisted, listed-growth and overlay totals from raw APRA rows for every option in June 2026.', f_norm),
    ('', f_norm),
    ('Colour legend', f_sub),
    ('Blue text on yellow = input you may change (tolerances on the Checks sheet). Black = formula or data. Green = formula pulling values from another sheet. Grey header = check column.', f_norm),
    ('Weights are shares of the option (0.25 = 25%). Values are strategic benchmark weights, not actual holdings.', f_norm),
]
for txt, fnt in lines:
    ws.append([None, cell(ws, txt, fnt, align=Alignment(wrap_text=True, vertical='top'))])

# ----------------------------------------------------------------------------- 2. Checks (summary)
ws = wb.create_sheet('Checks')
for c_, w_ in zip('ABCDEFGHIJ', [4, 30, 16, 16, 60, 14, 14, 14, 14, 14]):
    ws.column_dimensions[c_].width = w_
ws.append([None, cell(ws, 'Weight checks: summary', f_title)])
ws.append([None, cell(ws, 'Counts update automatically from the Data sheet. Change a tolerance in column C to re-run every check.', f_norm)])
ws.append([])
ws.append([None, cell(ws, 'Tolerances', f_sub)])
ws.append([None, cell(ws, 'Sum tolerance (chk_near1)', f_norm), cell(ws, 0.02, f_input, '0.00%', fill_input),
           None, cell(ws, 'Assumption: weights (excluding the currency overlay) may differ from 100% by up to 2 percentage points before a row is flagged for review.', f_norm, align=wrap)])
ws.append([None, cell(ws, 'Rounding tolerance (other checks)', f_norm), cell(ws, 0.000001, f_input, '0.000000', fill_input),
           None, cell(ws, 'Assumption: differences below 0.0001 percentage points are rounding.', f_norm, align=wrap)])
ws.append([])
ws.append([None, cell(ws, 'Check', f_head, fill=fill_head), cell(ws, 'Rows failing', f_head, fill=fill_head),
           cell(ws, 'Share of rows', f_head, fill=fill_head), cell(ws, 'What it means', f_head, fill=fill_head)])
N = len(m)
meaning = {
    'chk_total': 'Bucket columns add up to w_total. Any failure = a coding error in the bucket variables.',
    'chk_source': 'Bucket columns add up to the raw APRA rows. Any failure = rows lost or double-counted.',
    'chk_near1': 'Weights excluding the overlay are not 100% +/- tolerance. Mostly APRA reporting (e.g. leverage, residual items); review before use.',
    'chk_prop_u': 'Unlisted property total does not equal its components.',
    'chk_unlisted_core': 'Main unlisted exposure does not equal its components.',
    'chk_unlisted_all': 'Unlisted incl. alternatives does not equal its components.',
    'chk_listed_growth': 'Listed growth total does not equal its components.',
    'chk_ns_real': 'Not-specified property/infrastructure total does not equal its components.',
    'chk_hedge': 'Hedging ratio outside 0-1.',
    'all_ok': 'Rows failing at least one check.',
}
first_tbl = 9
for k in ['chk_total', 'chk_source', 'chk_near1', 'chk_prop_u', 'chk_unlisted_core', 'chk_unlisted_all',
          'chk_listed_growth', 'chk_ns_real', 'chk_hedge', 'all_ok']:
    r = first_tbl + ['chk_total', 'chk_source', 'chk_near1', 'chk_prop_u', 'chk_unlisted_core', 'chk_unlisted_all',
                     'chk_listed_growth', 'chk_ns_real', 'chk_hedge', 'all_ok'].index(k)
    rng = f"Data!${col[k]}$2:${col[k]}${NROW}"
    ws.append([None, cell(ws, k, f_norm), cell(ws, f'=COUNTIF({rng},FALSE)', f_link, '#,##0'),
               cell(ws, f'=C{r}/COUNTA(Data!$A$2:$A${NROW})', f_norm, '0.00%'), cell(ws, meaning[k], f_norm, align=wrap)])
r_after = first_tbl + 10
ws.append([None, cell(ws, 'Rows with a negative bucket', f_norm),
           cell(ws, f'=COUNTIF(Data!${col["n_negative"]}$2:${col["n_negative"]}${NROW},">0")', f_link, '#,##0'),
           cell(ws, f'=C{r_after}/COUNTA(Data!$A$2:$A${NROW})', f_norm, '0.00%'),
           cell(ws, 'Informational: APRA reports some negative weights (overlays, short credit positions).', f_norm, align=wrap)])
ws.append([None, cell(ws, 'Total option-quarters', f_norm), cell(ws, f'=COUNTA(Data!$A$2:$A${NROW})', f_link, '#,##0')])
ws.append([None, cell(ws, 'Audit June 2026: options failing', f_norm),
           cell(ws, "=COUNTIF(Audit_Jun2026!$N$2:$N$5000,FALSE)", f_link, '#,##0'), None,
           cell(ws, 'Options whose Data values differ from the raw APRA rows rebuilt with SUMIFS (see Audit_Jun2026).', f_norm, align=wrap)])
ws.append([])
ws.append([None, cell(ws, 'Sample and quality flags', f_sub)])
ws.append([None, cell(ws, 'Flag', f_head, fill=fill_head), cell(ws, 'Rows TRUE', f_head, fill=fill_head),
           cell(ws, 'Share of rows', f_head, fill=fill_head), cell(ws, 'Use', f_head, fill=fill_head)])
flag_use = [
    ('core_sample', 'Main sample: multi-sector, multi-manager, accumulation, weights complete, not specialist.'),
    ('core_sample_dedup', 'Main sample with one option per identical allocation.'),
    ('is_pension', 'Excluded from the core sample.'),
    ('is_lifecycle', 'Kept; lifecycle stages share assets, so cluster by fund.'),
    ('weights_incomplete', 'Excluded from the core sample.'),
    ('bad_weight_fund', 'Excluded from the core sample.'),
    ('specialist_option', 'Excluded from the core sample; can be analysed separately.'),
    ('pre_merger', 'Do not use fund-level variables in these rows.'),
    ('fund_vars_reliable', 'Use fund-level variables only where TRUE.'),
    ('large_jump', 'Robustness: exclude or winsorise.'),
    ('reclass_jump', 'Likely reclassification; robustness: exclude.'),
    ('filled_gap', 'Allocation carried forward from the previous quarter.'),
]
fr0 = r_after + 6
for i, (k, use) in enumerate(flag_use):
    r = fr0 + i
    rng = f"Data!${col[k]}$2:${col[k]}${NROW}"
    ws.append([None, cell(ws, k, f_norm), cell(ws, f'=COUNTIF({rng},TRUE)', f_link, '#,##0'),
               cell(ws, f'=C{r}/COUNTA(Data!$A$2:$A${NROW})', f_norm, '0.00%'), cell(ws, use, f_norm, align=wrap)])
ws.append([])
ws.append([None, cell(ws, 'Results by quarter', f_sub)])
hdr_r = fr0 + len(flag_use) + 2
ws.append([None] + [cell(ws, h, f_head, fill=fill_head, align=Alignment(wrap_text=True)) for h in
                    ['Quarter (saa_date)', 'Options', 'Rows failing chk_near1', 'Rows failing any check',
                     'Average w_unlisted_core', 'Average sum_ex_fx', 'Minimum sum_ex_fx', 'Core sample options',
                     'Core sample, de-duplicated']])
D = f"Data!${col['saa_date']}$2:${col['saa_date']}${NROW}"
for i, q in enumerate(sorted(m['saa_date'].unique())):
    r = hdr_r + 1 + i
    q = pd.Timestamp(q).to_pydatetime()
    ws.append([None, cell(ws, q, f_norm, 'dd-mmm-yyyy'),
               cell(ws, f'=COUNTIF({D},B{r})', f_link, '#,##0'),
               cell(ws, f"=COUNTIFS({D},B{r},Data!${col['chk_near1']}$2:${col['chk_near1']}${NROW},FALSE)", f_link, '#,##0'),
               cell(ws, f"=COUNTIFS({D},B{r},Data!${col['all_ok']}$2:${col['all_ok']}${NROW},FALSE)", f_link, '#,##0'),
               cell(ws, f"=AVERAGEIFS(Data!${col['w_unlisted_core']}$2:${col['w_unlisted_core']}${NROW},{D},B{r})", f_link, '0.0%'),
               cell(ws, f"=AVERAGEIFS(Data!${col['sum_ex_fx']}$2:${col['sum_ex_fx']}${NROW},{D},B{r})", f_link, '0.00%'),
               cell(ws, f"=_xlfn.MINIFS(Data!${col['sum_ex_fx']}$2:${col['sum_ex_fx']}${NROW},{D},B{r})", f_link, '0.00%'),
               cell(ws, f"=COUNTIFS({D},B{r},Data!${col['core_sample']}$2:${col['core_sample']}${NROW},TRUE)", f_link, '#,##0'),
               cell(ws, f"=COUNTIFS({D},B{r},Data!${col['core_sample_dedup']}$2:${col['core_sample_dedup']}${NROW},TRUE)", f_link, '#,##0')])

# ----------------------------------------------------------------------------- 3. Data
ws = wb.create_sheet('Data')
ws.freeze_panes = 'C2'
for c_ in cols + checks:
    ws.column_dimensions[col[c_]].width = 14
ws.column_dimensions[col['option_id']].width = 22
ws.column_dimensions[col['option_name']].width = 34
ws.column_dimensions[col['fund_name']].width = 30
ws.column_dimensions[col['key']].width = 32
hdr = []
for c_ in cols + checks:
    h = cell(ws, c_, f_head, fill=(fill_check if c_ in checks else fill_head), align=Alignment(wrap_text=True))
    hdr.append(h)
ws.append(hdr)
date_cols = {'saa_date', 'first_saa', 'last_saa', 'fy_end', 'wind_up_date', 'last_major_merger_fy'}
pct_cols = {c for c in cols if c.startswith('w_')} | {'hedge_ratio_intl', 'apra_raw_total'}
money = {c for c in cols if c.endswith('_k')}
vals = m[cols].astype(object).values
for i in range(len(m)):
    r = i + 2
    row = []
    for j, c_ in enumerate(cols):
        v = clean(vals[i, j])
        if c_ in date_cols:
            row.append(cell(ws, v, fmt='dd-mmm-yyyy'))
        elif c_ in pct_cols:
            row.append(cell(ws, v, fmt='0.00%'))
        elif c_ in money:
            row.append(cell(ws, v, fmt='#,##0'))
        else:
            row.append(v)
    f = check_formulas(r)
    for c_ in checks:
        row.append(cell(ws, f[c_], fmt=('0.00%' if c_ in ('sum_buckets', 'sum_ex_fx') else None)))
    ws.append(row)
print('data written', round(time.time() - t0), 's')

# ----------------------------------------------------------------------------- 4. Bucket_map
combos = raw[['ConsolidatedSectorType', 'ConsolidatedListingType', 'ConsolidatedDomicileType']].drop_duplicates()
combos = combos.sort_values(list(combos.columns)).reset_index(drop=True)
combos['bucket'] = ['w_' + bucket(*r) for r in combos.itertuples(index=False)]
grp = {}
for b in BUCKET_ORDER:
    grp['w_' + b] = ('unlisted_core' if b in ('PE_U', 'PROP_U_AU', 'PROP_U_INT', 'PROP_U_NSDOM', 'INFRA_U', 'CREDIT_U')
                     else 'listed_growth' if b in ('EQ_AU_L', 'EQ_INT_L', 'PROP_AU_L', 'PROP_INT_L', 'INFRA_L')
                     else 'fx_overlay' if b == 'FX_OVERLAY' else 'other')
combos['group'] = combos['bucket'].map(grp)
ws = wb.create_sheet('Bucket_map')
for c_, w_ in zip('ABCDEF', [30, 18, 26, 60, 18, 16]):
    ws.column_dimensions[c_].width = w_
ws.append([cell(ws, h, f_head, fill=fill_head) for h in
           ['ConsolidatedSectorType', 'ConsolidatedListingType', 'ConsolidatedDomicileType', 'Lookup key', 'Bucket', 'Group']])
for i, rr in enumerate(combos.itertuples(index=False)):
    r = i + 2
    ws.append([rr[0], rr[1], rr[2], f'=A{r}&"|"&B{r}&"|"&C{r}', rr[3], rr[4]])
NMAP = len(combos) + 1
ws.append([])
ws.append([cell(ws, 'Rule (build_master.py, function bucket): equity, property and infrastructure are split by listing type; listed equity and listed property by Australian vs other domicile; unlisted property by domicile; credit and alternatives into unlisted vs other; all fixed income together; currency exposure is an overlay. Group: unlisted_core = buckets in w_unlisted_core; listed_growth = buckets in w_listed_growth.', f_norm)])

# ----------------------------------------------------------------------------- 5. Raw_Jun2026
rj = raw[raw['saa_date'] == '2026-06-30'].sort_values(['investment_option_identifier']).reset_index(drop=True)
ws = wb.create_sheet('Raw_Jun2026')
for c_, w_ in zip('ABCDEFGHIJK', [22, 30, 34, 22, 16, 22, 12, 12, 56, 18, 14]):
    ws.column_dimensions[c_].width = w_
ws.freeze_panes = 'A2'
ws.append([cell(ws, h, f_head, fill=fill_head) for h in
           ['option_id', 'fund_name', 'option_name', 'Sector', 'Listing type', 'Domicile', 'Weight', 'Hedge ratio',
            'Lookup key (formula)', 'Bucket (formula)', 'Group (formula)']])
for i, rr in enumerate(rj.itertuples(index=False)):
    r = i + 2
    ws.append([rr.investment_option_identifier, rr.rse_name, rr.investment_option_name, rr.ConsolidatedSectorType,
               rr.ConsolidatedListingType, rr.ConsolidatedDomicileType,
               cell(ws, float(rr.InvestmentBenchmarkAllocationPercent), fmt='0.00%'),
               cell(ws, clean(rr.InvestmentCurrencyHedgingRatioPercent), fmt='0.00%'),
               f'=D{r}&"|"&E{r}&"|"&F{r}',
               cell(ws, f'=INDEX(Bucket_map!$E$2:$E${NMAP},MATCH(I{r},Bucket_map!$D$2:$D${NMAP},0))', f_link),
               cell(ws, f'=INDEX(Bucket_map!$F$2:$F${NMAP},MATCH(I{r},Bucket_map!$D$2:$D${NMAP},0))', f_link)])
NRAW = len(rj) + 1

# ----------------------------------------------------------------------------- 6. Audit_Jun2026
opts = rj.drop_duplicates('investment_option_identifier')[['investment_option_identifier', 'rse_name']]
ws = wb.create_sheet('Audit_Jun2026')
for c_, w_ in zip('ABCDEFGHIJKLMN', [22, 30, 9, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 10]):
    ws.column_dimensions[c_].width = w_
ws.freeze_panes = 'C2'
ws.append([cell(ws, h, f_head, fill=fill_head, align=Alignment(wrap_text=True)) for h in
           ['option_id', 'fund_name', 'Row in Data', 'Raw total (SUMIFS)', 'Data sum_buckets', 'Raw unlisted core',
            'Data w_unlisted_core', 'Raw listed growth', 'Data w_listed_growth', 'Raw FX overlay', 'Data w_FX_OVERLAY',
            'Max abs difference', 'Tolerance', 'All match']])
RA = f'Raw_Jun2026!$A$2:$A${NRAW}'; RG = f'Raw_Jun2026!$G$2:$G${NRAW}'; RK = f'Raw_Jun2026!$K$2:$K${NRAW}'
KEY = f"Data!${col['key']}$2:${col['key']}${NROW}"
dcol = lambda c_: f"Data!${col[c_]}$2:${col[c_]}${NROW}"
for i, rr in enumerate(opts.itertuples(index=False)):
    r = i + 2
    ws.append([rr[0], rr[1],
               f'=MATCH(A{r}&"|2026-06-30",{KEY},0)',
               cell(ws, f'=SUMIFS({RG},{RA},A{r})', f_link, '0.00%'),
               cell(ws, f"=INDEX({dcol('sum_buckets')},C{r})", f_link, '0.00%'),
               cell(ws, f'=SUMIFS({RG},{RA},A{r},{RK},"unlisted_core")', f_link, '0.00%'),
               cell(ws, f"=INDEX({dcol('w_unlisted_core')},C{r})", f_link, '0.00%'),
               cell(ws, f'=SUMIFS({RG},{RA},A{r},{RK},"listed_growth")', f_link, '0.00%'),
               cell(ws, f"=INDEX({dcol('w_listed_growth')},C{r})", f_link, '0.00%'),
               cell(ws, f'=SUMIFS({RG},{RA},A{r},{RK},"fx_overlay")', f_link, '0.00%'),
               cell(ws, f"=INDEX({dcol('w_FX_OVERLAY')},C{r})", f_link, '0.00%'),
               cell(ws, f'=MAX(ABS(D{r}-E{r}),ABS(F{r}-G{r}),ABS(H{r}-I{r}),ABS(J{r}-K{r}))', None, '0.0000%'),
               cell(ws, '=Checks!$C$6', f_link, '0.000000'),
               f'=L{r}<=M{r}'])

# ----------------------------------------------------------------------------- 7. Glossary
ws = wb.create_sheet('Glossary')
for c_, w_ in zip('ABCDE', [22, 12, 90, 40, 20]):
    ws.column_dimensions[c_].width = w_
ws.freeze_panes = 'A2'
ws.append([cell(ws, h, f_head, fill=fill_head) for h in ['Variable', 'Data column', 'Definition', 'Source', 'Unit / type']])
for c_ in cols + checks:
    d, s, u = G[c_]
    ws.append([c_, col[c_], cell(ws, d, align=wrap), cell(ws, s, align=wrap), u])
wb.save(OUTF)
print('saved', round(time.time() - t0), 's', 'raw rows', len(rj), 'audit options', len(opts), 'map', len(combos))
print('cols', {k: col[k] for k in ['saa_date', 'w_total', 'apra_raw_total', 'key', 'sum_buckets', 'all_ok']})
