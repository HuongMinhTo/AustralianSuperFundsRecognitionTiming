"""Word and Excel report comparing equal-weighted and AUM-weighted estimates of the distributed-lag model
(run after pilot_lag_model.py and robust.py for WEIGHT=equal and WEIGHT=aum; see run_all.sh)."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.section import WD_ORIENT, WD_SECTION
import copy, subprocess, tempfile

D = os.path.dirname(os.path.abspath(__file__))
_dev = os.path.join(D, '..', '..')
OUT = os.path.join(_dev, 'output', 'lag_model')
os.makedirs(OUT, exist_ok=True)
GN = ['0', '1', '2-4', '5-8', '9-13', '14-26']
NG = np.array([1, 1, 3, 4, 5, 13])
CASES = {'equal': 'equal-weighted', 'aum': 'AUM-weighted'}


def _load(c):
    d = os.path.join(_dev, 'output', 'estimates', 'lag_model', c)
    return dict(res=pd.read_pickle(os.path.join(d, 'results.pkl')), cs=pd.read_pickle(os.path.join(d, 'cs.pkl')),
                S=pd.read_pickle(os.path.join(d, 'S.pkl')), O=pd.read_csv(os.path.join(d, 'option_dimson.csv')),
                R=pd.read_csv(os.path.join(d, 'robust.csv')), F=pd.read_csv(os.path.join(d, 'by_fund.csv')))


K = {c: _load(c) for c in CASES}
S = K['equal']['S']
SW = K['aum']['S']
O = K['equal']['O']
_ROOT = os.path.abspath(os.path.join(D, '..', '..'))
DATA = _ROOT
FUNDNAME = {'CONSTRUCTION AND BUILDING UNIONS SUPERANNUATION FUND': 'Cbus', 'HOSTPLUS Superannuation Fund': 'Hostplus',
            'Australian Meat Industry Superannuation Trust': 'AMIST', 'Retail Employees Superannuation Trust': 'Rest',
            'Public Sector Superannuation Accumulation Plan': 'CSC PSSap', 'Australian Defence Force Superannuation Scheme': 'CSC ADF Super',
            'Building Unions Superannuation Scheme (Queensland)': 'BUSSQ', 'NGS Super': 'NGS Super', 'Rei Super': 'Rei Super',
            'Local Authorities Superannuation Fund': 'Vision Super', 'equipsuper': 'Equip', 'Unisuper': 'UniSuper',
            'Brighter Super Fund': 'Brighter Super', 'Australian Retirement Trust': 'ART', 'HESTA': 'HESTA',
            'CareSuper': 'CareSuper', 'legalsuper': 'legalsuper', 'Aware Super': 'Aware Super', 'AustralianSuper': 'AustralianSuper',
            'Team Superannuation Fund': 'Team Super', 'First Super': 'First Super', 'Prime Super': 'Prime Super',
            'ANZ Australian Staff Superannuation Scheme': 'ANZ Staff Super', 'NESS Super': 'NESS Super',
            'Fire and Emergency Services Superannuation Fund': 'Fire and Emergency Services Super',
            'Colonial First State FirstChoice Superannuation Trust': 'CFS FirstChoice', 'Mercer Super Trust': 'Mercer Super Trust',
            'MLC Super Fund': 'MLC Super Fund', 'Essential Super': 'Essential Super',
            'Smart Future Trust': 'Smart Future Trust (Future Super)', 'Russell Investments Master Trust': 'Russell iQ Super',
            'AMP Super Fund': 'AMP Super Fund', 'IOOF Portfolio Service Superannuation Fund': 'IOOF Portfolio Service',
            'Retirement Portfolio Service': 'Retirement Portfolio Service (OnePath)',
            'Oasis Superannuation Master Trust': 'Oasis', 'AvWrap Retirement Service': 'AvWrap',
            'The Bendigo Superannuation Plan': 'Bendigo Super Plan'}


def cell(b, se, d=3):
    return f'{b:.{d}f} ({se:.{d}f})'


def summ(res, key, p):
    par, se, cov, n, r2 = res[key]
    names = [f'{p}_{g}' for g in GN]
    b = par[names].values
    V = cov.loc[names, names].values
    a = np.r_[0, NG[1:]]
    return dict(b=b, se=se[names].values, b0=b[0], se0=np.sqrt(V[0, 0]), D=a @ b, seD=np.sqrt(a @ V @ a),
                T=NG @ b, seT=np.sqrt(NG @ V @ NG), V=V, n=n, r2=r2)


def pct_(x):
    return f'{100 * x:.0f}%'


M = {}
for c in CASES:
    res = K[c]['res']
    M[c] = {m: {p: summ(res, key, p) for p in ('XU', 'XL')}
            for m, key in [('A', 'A_optionFE'), ('B', 'B_option_weekFE'), ('C', 'C_lead_placebo_optionFE'), ('AF', 'A_fundSE')]}
    M[c]['lead'] = (res['C_lead_placebo_optionFE'][0], res['C_lead_placebo_optionFE'][1])
E_, W_ = M['equal'], M['aum']
LAGLAB = ['0 (same week)', '1', '2 to 4', '5 to 8', '9 to 13', '14 to 26']
tables = {}


def lagtab(m):
    return pd.DataFrame({'Lag (weeks)': LAGLAB,
                         'Unlisted: equal-weighted': [cell(b, s) for b, s in zip(E_[m]['XU']['b'], E_[m]['XU']['se'])],
                         'Unlisted: AUM-weighted': [cell(b, s) for b, s in zip(W_[m]['XU']['b'], W_[m]['XU']['se'])],
                         'Listed: equal-weighted': [cell(b, s) for b, s in zip(E_[m]['XL']['b'], E_[m]['XL']['se'])],
                         'Listed: AUM-weighted': [cell(b, s) for b, s in zip(W_[m]['XL']['b'], W_[m]['XL']['se'])]})


_lagnote = ('Coefficients per week of lag with Driscoll-Kraay standard errors (Bartlett kernel, 8 weeks) in parentheses. '
            'Within a lag group the response is assumed equal in each week, so the group total is the coefficient times the '
            'number of weeks. Equal-weighted: every option-week counts equally (OLS). AUM-weighted: weighted least squares '
            'with each option weighted by its June 2026 member assets (equation 6). Controls: same-week and one-week-lagged '
            'news on defensive and other/unspecified exposures.')
tables['Table 1'] = ('Response to market news by lag, Model A (option fixed effects)', lagtab('A'), _lagnote)
tables['Table 2'] = ('Response to market news by lag, Model B (option and week fixed effects)', lagtab('B'), _lagnote)


def col(Mc, m, S_):
    U, L = Mc[m]['XU'], Mc[m]['XL']
    lead = ['', '']
    if m == 'C':
        par, se = Mc['lead']
        lead = [cell(par['XU_lead'], se['XU_lead']), cell(par['XL_lead'], se['XL_lead'])]
    fund = cell(Mc['AF']['XU']['D'], Mc['AF']['XU']['seD']) if m == 'A' else ''
    return ([cell(U['b0'], U['se0']), cell(U['D'], U['seD']), cell(U['T'], U['seT']), pct_(U['D'] / U['T']),
             cell(L['b0'], L['se0']), cell(L['D'], L['seD'])] + lead
            + [fund, f'{S_.option_id.nunique()}', f'{U["n"]:,}', f'{U["r2"]:.3f}'])


t3 = pd.DataFrame({'Statistic': ['Unlisted: same-week response', 'Unlisted: delayed response (weeks 1-26)',
                                 'Unlisted: total response', 'Unlisted: share of total that is delayed',
                                 'Listed: same-week response', 'Listed: delayed response (weeks 1-26)',
                                 'Lead placebo, unlisted (t+1 to t+4)', 'Lead placebo, listed (t+1 to t+4)',
                                 'Unlisted delayed response, SE clustered by fund', 'Options', 'Option-weeks',
                                 'Within R-squared']})
for m in ('A', 'B', 'C'):
    t3[f'{m}: equal'] = col(E_, m, S)
    t3[f'{m}: AUM'] = col(W_, m, SW)
tables['Table 3'] = ('Same-week, delayed and total response to market news', t3,
                     'Model A: option fixed effects; Model B: option and week fixed effects; Model C: Model A plus leads of '
                     'unlisted and listed news (placebo). Driscoll-Kraay standard errors in parentheses, except the row '
                     f'clustered by fund ({S["abn"].nunique()} clusters, indicative). Definitions in equation (4). The '
                     'AUM-weighted sample drops one option without reported assets (Mercer SmartPath, born before 1929).')

lag_of = np.repeat(np.arange(6), NG)


def curve(s):
    per = s['b'][lag_of]
    cum = np.cumsum(per)
    out = []
    for h in range(27):
        cnt = np.array([np.sum(lag_of[:h + 1] == g) for g in range(6)])
        out.append((cum[h], np.sqrt(cnt @ s['V'] @ cnt)))
    return np.array(out)


cu, cl = curve(E_['A']['XU']), curve(E_['A']['XL'])
cuw, clw = curve(W_['A']['XU']), curve(W_['A']['XL'])
hs = [0, 1, 2, 4, 8, 13, 26]
t4 = pd.DataFrame({'Weeks after the news': [str(h) for h in hs],
                   'Unlisted, equal: cumulative': [cell(*cu[h]) for h in hs],
                   'Unlisted, equal: share': [pct_(cu[h, 0] / cu[26, 0]) for h in hs],
                   'Unlisted, AUM: cumulative': [cell(*cuw[h]) for h in hs],
                   'Unlisted, AUM: share': [pct_(cuw[h, 0] / cuw[26, 0]) for h in hs],
                   'Listed, equal: cumulative': [cell(*cl[h]) for h in hs],
                   'Listed, AUM: cumulative': [cell(*clw[h]) for h in hs]})
tables['Table 4'] = ('Recognition curve: how fast news is reflected in unit prices', t4,
                     'Model A. Cumulative response = sum of per-week coefficients from week 0 to week h (standard errors by '
                     'the delta method). Share = C(h) in equation (4), the share of the 26-week total recognised by week h.')

lab = {'Baseline': 'Baseline (Model A)', 'Excl. Feb-Jun 2020': 'Excluding February to June 2020',
       'Unit-price funds only': 'Unit-price funds only',
       'Crediting-rate funds only': 'Crediting-rate and crediting-index funds only',
       '2015-2019': 'July 2015 to December 2019', '2020-2026': 'January 2020 to August 2026',
       'MySuper options': 'MySuper options only', 'Excluding AustralianSuper': 'Excluding AustralianSuper',
       'Without AustralianSuper Socially Aware': 'Without AustralianSuper Socially Aware (previous sample)',
       'Industry and public-sector funds': 'Industry and public-sector funds only', 'Retail funds': 'Retail funds only',
       'Tier A funds only (first estimation)': 'Tier A funds only (18 funds)',
       'Incl. platform funds priced from trust exit prices': 'Adding platform funds priced from unit-trust exit prices',
       'Wednesday proxy windows': 'News over Wednesday-to-Wednesday windows'}
Re, Rw = K['equal']['R'].set_index('label'), K['aum']['R'].set_index('label')
t5 = pd.DataFrame({'Sample': [lab[x] for x in Re.index], 'Options': Re['options'].astype(int).values,
                   'AUM ($bn)': [f'{v:,.0f}' for v in Re['aum_bn']],
                   'Equal: delayed': [cell(a, b) for a, b in zip(Re['XU_D'], Re['XU_seD'])],
                   'Equal: total': Re['XU_tot'].round(3).values,
                   'AUM: delayed': [cell(a, b) for a, b in zip(Rw.loc[Re.index, 'XU_D'], Rw.loc[Re.index, 'XU_seD'])],
                   'AUM: total': Rw.loc[Re.index, 'XU_tot'].round(3).values})
tables['Table 5'] = ('Robustness of the unlisted response', t5,
                     'Model A re-estimated on sub-samples, unlisted exposure (same-week responses are in the Excel file, sheets '
                     '"Robustness raw"); Driscoll-Kraay standard errors in parentheses. '
                     'Options and AUM (June 2026 member assets of the options) refer to the equal-weighted sample. Platform '
                     'funds priced from trust exit prices: IOOF Portfolio Service, Retirement Portfolio Service, AvWrap and '
                     'Bendigo.')

Fe, Fw = K['equal']['F'].set_index('label'), K['aum']['F'].set_index('label')
faum = S.groupby(['fund_name', 'option_id'])['aum_k'].first().groupby('fund_name').sum() / 1e6
keep = Fe[(Fe['N'] >= 500) & (Fe['mean_wU'] >= 0.01)].index
keep = sorted(keep, key=lambda f: FUNDNAME.get(f, f))
t6 = pd.DataFrame({'Fund': [FUNDNAME.get(f, f) for f in keep], 'Options': Fe.loc[keep, 'options'].astype(int).values,
                   'AUM ($bn)': [f'{faum.get(f, np.nan):,.1f}' for f in keep],
                   'Mean unlisted share': [pct_(x) for x in Fe.loc[keep, 'mean_wU']],
                   'Equal: delayed': [cell(a, b) for a, b in zip(Fe.loc[keep, 'XU_D'], Fe.loc[keep, 'XU_seD'])],
                   'Equal: total': Fe.loc[keep, 'XU_tot'].round(3).values,
                   'AUM: delayed': [cell(a, b) for a, b in zip(Fw.reindex(keep)['XU_D'], Fw.reindex(keep)['XU_seD'])],
                   'AUM: total': Fw.reindex(keep)['XU_tot'].round(3).values})
tables['Table 6'] = ('Delayed response of unlisted exposure by fund', t6,
                     'Model A estimated separately for each fund with at least three priced options, 500 option-weeks and a '
                     'mean unlisted share of at least 1%; AUM-weighted estimates weight a fund\'s options by their June 2026 '
                     'assets. Always-zero controls are dropped for funds that report no other or unspecified assets. '
                     'Fund-level estimates are noisy and descriptive.')

(pc, bc, r2c), (p0, b0_), (pa, ba) = K['equal']['cs']['cs'], K['equal']['cs']['cs0'], K['equal']['cs']['ca']
(pcw, bcw, r2w), (p0w, b0w), (paw, baw) = K['aum']['cs']['cs'], K['aum']['cs']['cs0'], K['aum']['cs']['ca']
t7 = pd.DataFrame({'Dependent variable (one row per option)': ['Summed lagged beta (weeks 1-13)', 'Same-week beta',
                                                               'First-order autocorrelation of weekly returns'],
                   'Equal: constant': [f'{pc["Intercept"]:.3f}', f'{p0["Intercept"]:.3f}', f'{pa["Intercept"]:.3f}'],
                   'Equal: unlisted share': [cell(pc['w_unlisted'], bc['w_unlisted']),
                                             cell(p0['w_unlisted'], b0_['w_unlisted']),
                                             cell(pa['w_unlisted'], ba['w_unlisted'])],
                   'AUM: constant': [f'{pcw["Intercept"]:.3f}', f'{p0w["Intercept"]:.3f}', f'{paw["Intercept"]:.3f}'],
                   'AUM: unlisted share': [cell(pcw['w_unlisted'], bcw['w_unlisted']),
                                           cell(p0w['w_unlisted'], b0w['w_unlisted']),
                                           cell(paw['w_unlisted'], baw['w_unlisted'])],
                   'Options (equal / AUM)': [f'{len(O)} / {len(K["aum"]["O"])}'] * 3})
tables['Table 7'] = ('Option-level check: Dimson betas and unlisted exposure', t7,
                     'For each option with at least two years of data, weekly returns are regressed on the option\'s own total '
                     'exposure-weighted news in weeks 0 to 13 (Dimson, 1979; Newey-West standard errors). The betas are then '
                     'regressed on the option\'s mean unlisted share by OLS (equal) or by WLS with June 2026 assets as weights '
                     '(AUM); standard errors clustered by fund.')

# ------------------------------------------------------------------ figures (black and white)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],
                     'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '0.3',
                     'axes.grid': True, 'axes.axisbelow': True, 'grid.color': '0.9', 'legend.frameon': False,
                     'savefig.dpi': 300, 'savefig.bbox': 'tight'})
figs = {}
fig, ax = plt.subplots(figsize=(7.2, 3.8))
x = np.arange(27)
mk = [0, 1, 2, 4, 8, 13, 26]
ax.fill_between(x, cu[:, 0] - 1.96 * cu[:, 1], cu[:, 0] + 1.96 * cu[:, 1], facecolor='0.88', edgecolor='none')
ax.plot(x, cuw[:, 0] - 1.96 * cuw[:, 1], color='0.45', lw=0.6, ls=':')
ax.plot(x, cuw[:, 0] + 1.96 * cuw[:, 1], color='0.45', lw=0.6, ls=':')
ax.plot(x, cu[:, 0], color='0.0', lw=1.6, marker='o', markersize=3.5, markevery=mk, label='Unlisted, equal-weighted')
ax.plot(x, cuw[:, 0], color='0.0', lw=1.6, ls='--', marker='s', markersize=3.5, markevery=mk, label='Unlisted, AUM-weighted')
ax.plot(x, cl[:, 0], color='0.55', lw=1.3, marker='o', markersize=3, markevery=mk, label='Listed, equal-weighted')
ax.plot(x, clw[:, 0], color='0.55', lw=1.3, ls='--', marker='s', markersize=3, markevery=mk, label='Listed, AUM-weighted')
ax.axhline(0, color='0.3', lw=0.6)
ax.set_xlabel('Weeks after the market news'); ax.set_ylabel('Cumulative response of unit price')
ax.set_xticks(mk); ax.legend(loc='lower right', fontsize=8.5, ncol=2)
p = os.path.join(OUT, 'fig1_recognition_curves_equal_vs_aum.png'); fig.savefig(p); plt.close(fig)
figs['Figure 1'] = ('Recognition curves, equal-weighted and AUM-weighted', p,
                    'Cumulative response of weekly option returns to a unit of exposure-weighted market news (Model A). '
                    'Shaded: 95% band for the equal-weighted unlisted curve; dotted lines: 95% band for the AUM-weighted '
                    'unlisted curve.')

fig, ax = plt.subplots(figsize=(7.2, 3.8))
Ow = K['aum']['O']
sz = 8 + 400 * np.sqrt(Ow['aum_k'] / Ow['aum_k'].max())
ax.scatter(Ow['w_unlisted'] * 100, Ow['beta_lag'], s=sz, facecolor='none', edgecolor='0.2', lw=0.6)
xx = np.linspace(0, O['w_unlisted'].max(), 50)
ax.plot(xx * 100, pc['Intercept'] + pc['w_unlisted'] * xx, color='0.0', lw=1.3,
        label=f'OLS (equal-weighted), slope {pc["w_unlisted"]:.2f}')
ax.plot(xx * 100, pcw['Intercept'] + pcw['w_unlisted'] * xx, color='0.0', lw=1.3, ls='--',
        label=f'WLS (AUM-weighted), slope {pcw["w_unlisted"]:.2f}')
ax.axhline(0, color='0.3', lw=0.6)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
ax.set_xlabel('Mean unlisted share of option'); ax.set_ylabel('Summed lagged beta (weeks 1-13)')
ax.legend(loc='upper left', fontsize=8.5)
p = os.path.join(OUT, 'fig2_lagged_beta_vs_unlisted_equal_vs_aum.png'); fig.savefig(p); plt.close(fig)
figs['Figure 2'] = ('Lagged market sensitivity and unlisted exposure', p,
                    f'Each circle is an option ({len(Ow)} options); circle area is proportional to June 2026 assets. Lines '
                    'are the fitted regressions in Table 7.')

# ------------------------------------------------------------------ appendices: data
OQ = pd.read_csv(os.path.join(DATA, 'data', 'derived', 'option_quarter_master.csv'), parse_dates=['saa_date'], low_memory=False)
FYR = pd.read_csv(os.path.join(DATA, 'data', 'derived', 'fund_year.csv'), parse_dates=['fy_end'])
MPT = pd.read_csv(os.path.join(DATA, 'data', 'derived', 'unit_price_mapping_template.csv'))
LASTQ = OQ['saa_date'].max()
sname = lambda n: FUNDNAME.get(n, n)
assets = FYR.sort_values('fy_end').groupby('abn')['total_assets_k'].last() / 1e6
ftype = OQ.groupby('abn')['fund_type_fixed'].last()
fname = OQ.groupby('abn')['fund_name'].last()
ADF = 90302247344
META = {  # abn: (price series, frequency, date correction)
    60905115063: ('Unit prices: Super Savings (from Sep 2016) and QSuper Lifetime/Balanced Risk-Adjusted (from 2005)', 'Daily',
                  'QSuper dates moved 2 business days earlier'),
    65714394898: ('Daily crediting rates (4 decimals), chained into an index', 'Daily', 'None'),
    53226460365: ('Unit prices (Future Saver)', 'Daily', 'None'),
    23053121564: ('Unit prices', 'Daily; Energy Super options monthly until mid-2023', 'None; admin-fee basis change 31 May 2024'),
    85571332201: ('Unit prices (Power BI report)', 'Weekly to Mar 2021, daily after',
                  '-3 business days before Apr 2021; -2 Apr 2021 to 5 Aug 2024 and from 1 Oct 2025'),
    75493363262: ('Crediting rates (2 decimals), chained into an index', 'Weekly (Thu-Wed) to Oct 2018, daily after', 'None'),
    74559365913: ('Unit prices; Spirit Super history before Nov 2024', 'Weekly to Apr 2017, daily after',
                  'Weekly labels +4 business days (start of pricing week); daily Apr 2017 to Mar 2021 -2'),
    65127917725: ('Unit prices (sell)', 'Daily', 'None'),
    ADF: ('Unit prices (sell)', 'Daily', 'None; allocations identical to PSSap, so represented by the PSSap options'),
    33813823017: ('Unit prices (mid)', 'Daily', 'None'),
    64971749321: ('Unit prices; period returns before first published price', 'Weekly (Wed-Tue) to Oct 2021, daily after',
                  'None (dated by period end)'),
    68657495890: ('Unit prices', 'Daily', 'None'),
    60346078879: ('Unit prices (sell)', 'Daily', 'None'),
    73549180515: ('Unit prices', 'Weekly (Saturday labels) to 2020, daily after', 'Saturday labels moved to Friday'),
    76641658449: ('Unit prices (sell) from annual PDFs', 'Weekly (Wednesday)', 'None; Feb-Jun 2024 missing'),
    62653671394: ('Unit prices (sell)', 'Daily', 'Dates moved 2 business days earlier'),
    91385943850: ('Cumulative crediting index (interim daily rates)', 'Daily (calendar days)', 'None'),
    24496637884: ('Unit prices', 'Daily', 'None; one code matched to the untaxed pension series'),
    28342064803: ('Weekly crediting rates (2 decimals), chained into an index', 'Weekly (Wed-Tue)',
                  'None (news measured over the same Wed-Tue window)'),
    26458298557: ('Exit prices (FirstChoice; APRA codes are APIR codes)', 'Daily', 'None'),
    19905422981: ('Exit prices (Corporate Super Division), API queried for each Wednesday', 'Weekly (Wednesday)', 'None'),
    70732426024: ('Mid of the two published prices (MasterKey Business Super, Super Fundamentals)', 'Daily (calendar days)', 'None'),
    56601925435: ('Exit prices (historical CSV)', 'Daily', 'None'),
    68964712340: ('Mid of buy and sell prices; Future Super options only, from May 2025', 'Daily', 'None'),
}
pct0 = lambda x: '' if pd.isna(x) else f'{100 * x:.0f}%'
# option AUM, June 2026 (APRA QSPS Product Structure Table 1b; data/derived/option_aum_june2026_all.csv)
_ao = S.groupby('option_id').agg(abn=('abn', 'first'), assets_k=('aum_k', 'first'), mysuper=('is_mysuper_option', 'max'),
                                 fund=('fund_name', 'first')).reset_index()
_old = os.path.join(_dev, 'output', 'sample_checks', 'option_aum_june2026.xlsx')
_at = pd.read_excel(_old, sheet_name='Totals').set_index('Aggregate (June 2026)')['Assets ($bn)']
OPT_AUM = _ao.groupby('abn')['assets_k'].sum() / 1e6
_tot = _ao['assets_k'].sum()
AUMT = dict(sample=_tot / 1e6, apra=_at.iloc[0], rep=_at.iloc[6], share=_tot / 1e6 / _at.iloc[0],
            share_rep=_at.iloc[6] / _at.iloc[0], mysuper=_ao.loc[_ao['mysuper'] == True, 'assets_k'].sum() / _tot,
            ind=_ao.loc[_ao['abn'].map(ftype) != 'Retail', 'assets_k'].sum() / _tot)
AUM_ARSB = _ao.loc[_ao.option_id == '65714394898-ARSB', 'assets_k'].sum() / 1e6
_sw = SW.groupby('option_id')['aum_k'].first().sort_values(ascending=False)
_ew = SW.groupby('option_id')['wt'].sum().sort_values(ascending=False) / SW['wt'].sum()   # effective WLS weight (assets x weeks)
TOP1, TOP10 = _ew.iloc[0], _ew.iloc[:10].sum()
CFS_SHARE_EQ = (S['abn'] == 26458298557).mean()
CFS_SHARE_AUM = _ao.loc[_ao['abn'] == 26458298557, 'assets_k'].sum() / _tot

# Appendix A: funds in the study
SA = S.copy()
SA['fi_cash'] = SA['w_FI'].fillna(0) + SA['w_CASH'].fillna(0)
fa = SA.groupby('abn').agg(options=('option_id', 'nunique'), weeks=('ret', 'size'), first=('week', 'min'),
                           last=('week', 'max'), unl=('w_unlisted_core', 'mean')).reset_index()
fa = pd.concat([fa, pd.DataFrame([dict(abn=ADF, options=0, weeks=0, first=pd.NaT, last=pd.NaT,
                                        unl=OQ.loc[(OQ.abn == ADF) & OQ.core_sample, 'w_unlisted_core'].mean())])])
fa['Fund'] = fa['abn'].map(fname).map(sname)
fa = fa.sort_values('Fund')
appA = pd.DataFrame({
    'Fund': fa['Fund'], 'Type': fa['abn'].map(ftype).values,
    'Fund assets ($bn)': [f'{v:.0f}' if pd.notna(v) else '' for v in fa['abn'].map(assets)],
    'Options studied: AUM ($bn)': [f'{v:.1f}' if pd.notna(v) and v > 0 else '' for v in fa['abn'].map(OPT_AUM)],
    'Options': fa['options'].astype(int).values, 'Option-weeks': fa['weeks'].astype(int).values,
    'Sample period': [f'{a:%b %Y} - {b:%b %Y}' if pd.notna(a) else '-' for a, b in zip(fa['first'], fa['last'])],
    'Mean unlisted share': [pct0(v) for v in fa['unl']],
    'Price series': [META[a][0] for a in fa['abn']], 'Frequency': [META[a][1] for a in fa['abn']],
    'Date correction': [META[a][2] for a in fa['abn']]})
appA_note = (f'Estimation sample (weekly returns July 2015 to {S["week"].max():%B %Y}, core_sample_dedup_priced plus AustralianSuper Socially Aware). Fund assets are '
             'total assets at the latest financial year in the APRA fund-level statistics. Options studied: AUM is the June 2026 '
             'member assets of the fund\'s options in the estimation sample (all investment pathways; APRA QSPS Product Structure, '
             f'Table 1b); total {AUMT["sample"]:,.0f} billion dollars. Type is the June 2026 APRA fund type. '
             'Mean unlisted share is the average strategic weight in unlisted equity, property, infrastructure and credit over '
             'the option-weeks used. Date corrections align each price with its valuation date (checked against same-day market '
             'returns; Section 2).')

# Appendix B: options in the study
ob = SA.sort_values('week').groupby('option_id').agg(
    abn=('abn', 'first'), option=('option_name', 'last'), mysuper=('is_mysuper_option', 'max'),
    lifecycle=('is_lifecycle', 'max'), weeks=('ret', 'size'), first=('week', 'min'), last=('week', 'max'),
    lg=('w_listed_growth', 'mean'), unl=('w_unlisted_core', 'mean'), fic=('fi_cash', 'mean'),
    ptype=('price_type', 'last')).reset_index()
ob['Fund'] = ob['abn'].map(fname).map(sname)
ob = ob.sort_values(['Fund', 'option'])
PT = {'unit_price': 'Unit price', 'crediting_rate': 'Crediting rate', 'cumulative_index': 'Crediting index'}
yn = lambda v: 'Yes' if bool(v) else ''
appB = pd.DataFrame({
    'Fund': ob['Fund'].values, 'Investment option': ob['option'].values,
    'APRA code': ob['option_id'].str.split('-', n=1).str[1].values,
    'MySuper': [yn(v) for v in ob['mysuper']], 'Lifecycle': [yn(v) for v in ob['lifecycle']],
    'First week': ob['first'].dt.strftime('%b %Y').values, 'Last week': ob['last'].dt.strftime('%b %Y').values,
    'Weeks': ob['weeks'].astype(int).values, 'Listed growth': [pct0(v) for v in ob['lg']],
    'Unlisted': [pct0(v) for v in ob['unl']], 'Fixed income and cash': [pct0(v) for v in ob['fic']],
    'AUM ($m)': [f'{v / 1e3:,.0f}' if pd.notna(v) else '' for v in ob['option_id'].map(_ao.set_index('option_id')['assets_k'])],
    'AUM weight': [f'{100 * v:.2f}%' if pd.notna(v) else '' for v in ob['option_id'].map(_ew)],
    'Price type': ob['ptype'].map(PT).values})
appB_note = ('One priced option per identical allocation per quarter. First and last week are the first and last weeks with a '
             'return in the estimation sample; weeks counts weekly returns. Asset shares are mean APRA strategic weights over '
             'those weeks: listed growth = listed equity, property and infrastructure; unlisted = unlisted equity, property, '
             'infrastructure and credit; the remainder is alternatives, other and not-specified assets. Lifecycle stages '
             'without their own price are represented by the identically allocated priced option in the same quarter. '
             'AustralianSuper Socially Aware is added although its bucketed weights equal another option\'s (own crediting '
             'rates). AUM: June 2026 member assets (APRA QSPS Product Structure, Table 1b). AUM weight: the option\'s share of '
             'the total weight in the AUM-weighted regressions (assets times weeks in the sample).')

# Appendix C: funds still missing
inS = set(S['abn']) | {ADF}
cj = OQ[(OQ.saa_date == LASTQ) & OQ.core_sample]
fc = pd.DataFrame({'abn': sorted(set(OQ['abn']) - inS)})
fc['Fund'] = fc['abn'].map(fname).map(sname)
fc['core'] = fc['abn'].map(cj.groupby('abn')['option_id'].nunique()).fillna(0).astype(int)
fc['dedup'] = fc['abn'].map(OQ[(OQ.saa_date == LASTQ) & OQ.core_sample_dedup].groupby('abn')['option_id'].nunique()).fillna(0).astype(int)
fc['unl'] = fc['abn'].map(cj.groupby('abn')['w_unlisted_core'].mean())
fc['prio'] = fc['abn'].map(MPT.groupby('abn')['fund_priority'].first())
fc['bad'] = fc['abn'].map(OQ.groupby('abn')['bad_weight_fund'].max())
NOPUB = {16457520308: 'Publishes only the latest week of unit prices; request history from the fund',
         56286625181: 'Only monthly returns public (weekly crediting rates behind member login); request from the fund',
         60562335823: 'Weekly returns public only for FY2026-FY2027 (too short); request history from the fund',
         83810127567: 'No public price history (corporate fund); request from the fund',
         72229227691: 'Only financial-year-to-date returns public; request from the fund',
         43198502058: 'No public weekly series; options are smoothed and hold little unlisted; request if needed',
         89384753567: 'Only monthly period returns public (iQ Super performance pages); history behind member login',
         78421957449: 'Public unit-price service returns no data; North/MyNorth history behind member login',
         91593544166: 'No public unit-price history found (options from Dec 2022, 0-4% unlisted)',
         43905581638: 'No public unit-price history found (Spaceship, Professional Super; options from 2024, no unlisted)',
         22599554834: 'Only monthly period returns public (GuildSuper, now on the Smart Future Trust platform)',
         30099320583: 'No public unit-price history found (website not reachable); options hold no unlisted'}
TRUSTF = {70815369818, 81154851339, 82004832237, 57526653420, 61808189263}


def status(r):
    if r.abn in NOPUB and r.type != 'Retail':
        return 1, 'A. Industry and public-sector funds without usable public prices', NOPUB[r.abn]
    if r.abn in NOPUB:
        return 2, 'B. Retail funds without usable public prices', NOPUB[r.abn]
    if r.abn in TRUSTF:
        return 3, 'C. Platform funds priced from unit-trust exit prices', (
            'Downloaded (trust exit prices); excluded from the main sample because distributions are not in the price '
            '(quarterly match with APRA returns weak); included in the robustness check (Table 5)')
    if r.core > 0:
        extra = '; all allocations identical to options of other funds' if r.dedup == 0 else ''
        return 4, 'D. Funds excluded by the sample rules', f'No public price history searched yet{extra}'
    if r.bad:
        return 4, 'D. Funds excluded by the sample rules', 'Platform: strategic weights incomplete for more than 2% of option-quarters'
    return 4, 'D. Funds excluded by the sample rules', 'Only single-manager or separately managed options (no multi-manager, multi-sector option)'


fc['type'] = fc['abn'].map(ftype)
st_ = fc.apply(status, axis=1, result_type='expand')
fc['grp_n'], fc['grp'], fc['status'] = st_[0], st_[1], st_[2]
fc = fc.sort_values(['grp_n', 'core', 'Fund'], ascending=[True, False, True])
appC = pd.DataFrame({'Group': fc['grp'].str[:1].values, 'Fund': fc['Fund'].values, 'Type': fc['type'].values,
                     f'Core options ({LASTQ:%b %Y})': fc['core'].values,
                     'Distinct allocations': fc['dedup'].values,
                     'Mean unlisted share': [pct0(v) for v in fc['unl']], 'Status': fc['status'].values})
appC_note = ('All funds in the APRA Historical SAA file (June 2026) that are not in the main estimation sample. Group A: '
             'industry and public-sector funds whose unit-price or crediting-rate history is not published; group B: retail '
             'funds whose price history is not published; group C: platform funds downloaded but priced from unit-trust exit '
             'prices (robustness only); group D: funds excluded by the sample rules. Core options and distinct allocations are '
             'counted in June 2026; mean unlisted share is the average over their core options. Within included funds, some '
             'options are still unpriced: smartMonday options of the Smart Future Trust (monthly returns only; 41 lifecycle '
             'ages and 4 diversified options), MLC MySuper ages 55 to 64 (blends of two pools), Mercer Lutheran and Virgin '
             'LifeStage options, ART ages 50 to 65 and Aware Manage 56 to 64 (blended stages); Rei Super misses February to '
             'June 2024.')

# ------------------------------------------------------------------ Word
doc = Document()
for s in doc.sections:
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    for a in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(s, a, Cm(2.3))
for st in doc.styles:
    try:
        st.font.name = 'Times New Roman'; st.font.color.rgb = RGBColor(0, 0, 0)
        rpr = st.element.get_or_add_rPr(); rf = rpr.find(qn('w:rFonts'))
        if rf is None:
            rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
        for a_ in list(rf.attrib):
            del rf.attrib[a_]
        for a_ in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
            rf.set(qn(a_), 'Times New Roman')
    except Exception:
        pass


def style(name):
    for s_ in doc.styles:
        if s_.name == name:
            return s_
    return None


for el in doc.styles.element.iter(qn('w:color')):
    for a_ in ('w:themeColor', 'w:themeTint', 'w:themeShade'):
        if el.get(qn(a_)) is not None:
            del el.attrib[qn(a_)]
    el.set(qn('w:val'), '000000')
for el in list(doc.styles.element.iter(qn('w:pBdr'))):      # coloured rule under Title
    el.getparent().remove(el)
style('Normal').font.size = Pt(11)
for h_, sz in (('Title', 16), ('Heading 1', 13), ('Heading 2', 11.5)):
    s_ = style(h_)
    if s_ is not None:
        s_.font.size = Pt(sz); s_.font.bold = True


def border(c, edge, sz):
    tcPr = c._tc.get_or_add_tcPr(); b = tcPr.find(qn('w:tcBorders'))
    if b is None:
        b = OxmlElement('w:tcBorders'); tcPr.append(b)
    e = OxmlElement(f'w:{edge}'); e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), str(sz)); e.set(qn('w:color'), '000000')
    b.append(e)


def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, np.integer)):
        return f'{int(v):,}'
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ''
    return f'{v:.3f}'


FIRSTW = {'Table 1': 2.8, 'Table 2': 2.8, 'Table 3': 4.0, 'Table 4': 1.9, 'Table 5': 4.6, 'Table 6': 2.4, 'Table 7': 4.2}
FS = {'Table 3': 7.5, 'Table 4': 8.5, 'Table 5': 8, 'Table 6': 8, 'Table 7': 8.5}


def add_table(num, title, t, note):
    p_ = doc.add_paragraph(); r_ = p_.add_run(f'{num}. {title}'); r_.bold = True
    p_.paragraph_format.space_before = Pt(12); p_.paragraph_format.keep_with_next = True
    tb = doc.add_table(rows=len(t) + 1, cols=t.shape[1]); tb.alignment = WD_TABLE_ALIGNMENT.CENTER; tb.autofit = False
    first = FIRSTW.get(num, 3.0); other = (16.4 - first) / max(t.shape[1] - 1, 1)
    widths = [first] + [other] * (t.shape[1] - 1)
    for gc, w_ in zip(tb._tbl.tblGrid.findall(qn('w:gridCol')), widths):
        gc.set(qn('w:w'), str(int(w_ * 567)))
    lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); tb._tbl.tblPr.append(lay)
    for j, w_ in enumerate(widths):
        for c in tb.columns[j].cells:
            c.width = Cm(w_)
    for j, c in enumerate(t.columns):
        tb.cell(0, j).text = str(c)
    for i, row in enumerate(t.itertuples(index=False)):
        for j, v in enumerate(row):
            tb.cell(i + 1, j).text = fmt(v)
    n = len(t) + 1
    for i in range(n):
        for j in range(t.shape[1]):
            c = tb.cell(i, j)
            if i == 0:
                border(c, 'top', 12); border(c, 'bottom', 6)
            if i == n - 1:
                border(c, 'bottom', 12)
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(1); pp.paragraph_format.space_before = Pt(1)
                pp.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT
                pp.paragraph_format.keep_with_next = i < n - 1
                for rr in pp.runs:
                    rr.font.size = Pt(FS.get(num, 9)); rr.font.bold = (i == 0)
    q = doc.add_paragraph(); rn = q.add_run('Note: ' + note); rn.font.size = Pt(9)


def add_figure(num, title, path, note):
    p_ = doc.add_paragraph(); r_ = p_.add_run(f'{num}. {title}'); r_.bold = True
    p_.paragraph_format.space_before = Pt(12); p_.paragraph_format.keep_with_next = True
    doc.add_picture(path, width=Cm(16)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    q = doc.add_paragraph(); rn = q.add_run('Note: ' + note); rn.font.size = Pt(9)


def para(text):
    doc.add_paragraph(text)


def md_block(md):
    """Convert markdown with LaTeX maths to Word via pandoc (maths become native equation-editor objects,
    OMML) and append the resulting paragraphs to the document."""
    with tempfile.TemporaryDirectory() as td:
        src, dst = os.path.join(td, 'x.md'), os.path.join(td, 'x.docx')
        open(src, 'w').write(md)
        subprocess.run(['pandoc', src, '-f', 'markdown', '-t', 'docx', '-o', dst], check=True)
        body = Document(dst).element.body
        for el in list(body):
            if el.tag == qn('w:sectPr'):
                continue
            el = copy.deepcopy(el)
            for ps in el.iter(qn('w:pStyle')):
                ps.getparent().remove(ps)
            for pp in ([el] if el.tag == qn('w:p') else []):
                ppr = pp.find(qn('w:pPr'))
                if ppr is None:
                    ppr = OxmlElement('w:pPr'); pp.insert(0, ppr)
                sp = OxmlElement('w:spacing'); sp.set(qn('w:after'), '120'); ppr.append(sp)
            doc.element.body.insert(len(doc.element.body) - 1, el)


MD = r"""
**Returns.** For option $i$ with published unit price (or chained crediting-rate index) $P_i$, the weekly return is

$$r_{i,t}=\ln P_i(\tau_{i,t})-\ln P_i(\tau_{i,t-1}) \qquad (1)$$

where $\tau_{i,t}$ is the valuation date of the last price on or before the Wednesday of week $t$ (at most five days old; otherwise the return is missing). The sample keeps one priced option per identical allocation per quarter (Appendix B), plus AustralianSuper Socially Aware, and starts in July 2015, so that 26 weeks of lagged news are available. Every price series was checked for its date convention against same-day market returns; late-dated series were corrected (QSuper, Rest, BUSSQ, CareSuper and NGS; Appendix A). The main sample leaves out five platform funds whose options are priced from unit-trust exit prices, because those prices fall on distribution dates and match APRA quarterly returns poorly; they are added back as a robustness check (Table 5).

**Exposure-weighted news.** Let $I_b$ be the price index of the listed proxy for asset bucket $b$ and $R_{b,i,t}=\ln I_b(\tau_{i,t})-\ln I_b(\tau_{i,t-1})$ its return over exactly the same window as the option return. With $w_{i,b,q(t)-1}$ the APRA strategic weight of bucket $b$ at the end of the quarter before week $t$,

$$X^{U}_{i,t}=\sum_{b\in\mathcal{U}} w_{i,b,q(t)-1}\,R_{b,i,t},\qquad X^{L}_{i,t}=\sum_{b\in\mathcal{L}} w_{i,b,q(t)-1}\,R_{b,i,t} \qquad (2)$$

The unlisted buckets $\mathcal{U}$ use Australian small companies (VSO) for private equity, Australian and global REITs (VAP, DJRE) for unlisted property, global listed infrastructure (IFRA) for unlisted infrastructure and Australian bonds (VAF) for private credit. The listed buckets $\mathcal{L}$ use VAS, VGS/VGAD (combined with the option's hedge ratio), VAP, DJRE and IFRA. Defensive exposures (fixed income and cash) give $X^{D}_{i,t}$ and unspecified or other exposures give $X^{O}_{i,t}$. Proxy prices are daily adjusted closes of ASX-listed ETFs (Yahoo Finance).

**Model.** Lags are grouped into $K_1=\{0\}$, $K_2=\{1\}$, $K_3=\{2,\dots,4\}$, $K_4=\{5,\dots,8\}$, $K_5=\{9,\dots,13\}$ and $K_6=\{14,\dots,26\}$ weeks, with $n_g$ weeks in group $g$ and $X^{U}_{i,g,t}=\sum_{k\in K_g}X^{U}_{i,t-k}$ (likewise for $X^{L}$). The estimated model is

$$r_{i,t}=\alpha_i+\lambda_t+\sum_{g=1}^{6}\beta^{U}_{g}X^{U}_{i,g,t}+\sum_{g=1}^{6}\beta^{L}_{g}X^{L}_{i,g,t}+\sum_{k=0}^{1}\left(\gamma_k X^{D}_{i,t-k}+\delta_k X^{O}_{i,t-k}\right)+\varepsilon_{i,t} \qquad (3)$$

Model A sets the week effects $\lambda_t=0$; Model B estimates them; Model C adds the leads $\sum_{k=1}^{4}X^{U}_{i,t+k}$ and $\sum_{k=1}^{4}X^{L}_{i,t+k}$ as a placebo. Each $\beta_g$ is the response per week of lag within group $g$. The same-week, delayed and total responses and the recognition curve are

$$D^{U}=\sum_{g=2}^{6}n_g\,\beta^{U}_{g},\qquad T^{U}=\beta^{U}_{1}+D^{U},\qquad C^{U}(h)=\frac{1}{T^{U}}\sum_{k=0}^{h}\beta^{U}_{g(k)} \qquad (4)$$

where $g(k)$ is the group that contains lag $k$. This is a grouped form of the Dimson (1979) sum-of-betas approach applied to exposure-weighted news. Standard errors are Driscoll and Kraay (1998), robust to correlation across options in the same week and to autocorrelation up to eight weeks.

**Option-level check.** For each option with at least two years of data,

$$r_{i,t}=a_i+\sum_{k=0}^{4}b_{i,k}X_{i,t-k}+b_{i,5}\sum_{k=5}^{13}X_{i,t-k}+e_{i,t},\qquad X_{i,t}=X^{U}_{i,t}+X^{L}_{i,t}+X^{D}_{i,t}+X^{O}_{i,t} \qquad (5)$$

with Newey-West standard errors. The summed lagged beta $b^{lag}_i=\sum_{k=1}^{4}b_{i,k}+9\,b_{i,5}$ is then related to the option's mean unlisted share: $b^{lag}_i=c_0+c_1\bar{w}^{U}_i+u_i$.

**Weighting.** Equation (3) is estimated in two ways. *Equal-weighted*: ordinary least squares, so every option-week counts equally. *AUM-weighted*: weighted least squares,

$$\min_{\alpha,\lambda,\beta,\gamma,\delta}\;\sum_{i}\sum_{t}\omega_i\,\varepsilon_{i,t}^{2},\qquad \omega_i=\frac{A_i}{\bar{A}} \qquad (6)$$

where $A_i$ is option $i$'s member assets in June 2026 (all investment pathways; APRA QSPS Product Structure, Table 1b) and $\bar{A}$ is their mean in the sample. The option (and week) fixed effects become weighted means, the Driscoll and Kraay covariance is computed from the weighted scores, and the cross-sectional regression that follows equation (5) is estimated by weighted least squares with the same weights. The AUM-weighted estimates describe the average member dollar; the equal-weighted estimates describe the average option.
"""

nfund = S['fund_name'].nunique()
eA, wA = E_['A'], W_['A']
sh = lambda c, h: c[h, 0] / c[26, 0]
ReL, RwL = Re['XU_D'], Rw['XU_D']
doc.add_heading('Delayed recognition of market news in unlisted exposures: equal-weighted and AUM-weighted estimates',
                level=0)
ntyp = S.groupby('fund_type_fixed')['abn'].nunique()
para(f'Minh Huong · {nfund} funds ({ntyp.get("Industry", 0)} industry, {ntyp.get("Public Sector", 0)} public-sector, '
     f'{ntyp.get("Retail", 0)} retail), {S["option_id"].nunique()} options (including AustralianSuper Socially Aware), weekly '
     f'returns {S["week"].min():%B %Y} to {S["week"].max():%B %Y} · two weightings: (1) each option-week weighted equally, '
     '(2) each option weighted by its June 2026 assets · preliminary, not for citation.')

doc.add_heading('1. Key findings', level=1)
for txt in [
    f'Listed exposure is priced in the same week under both weightings: the same-week response is {eA["XL"]["b0"]:.2f} '
    f'(equal) and {wA["XL"]["b0"]:.2f} (AUM), with no significant delayed response ({eA["XL"]["D"]:.2f}, standard error '
    f'{eA["XL"]["seD"]:.2f}; {wA["XL"]["D"]:.2f}, standard error {wA["XL"]["seD"]:.2f}).',
    f'Unlisted exposure is recognised late under both weightings. Equal-weighted: same-week {eA["XU"]["b0"]:.2f}, delayed '
    f'{eA["XU"]["D"]:.2f} (standard error {eA["XU"]["seD"]:.2f}), {100 * eA["XU"]["D"] / eA["XU"]["T"]:.0f}% of the total '
    f'response is delayed. AUM-weighted: same-week {wA["XU"]["b0"]:.2f}, delayed {wA["XU"]["D"]:.2f} (standard error '
    f'{wA["XU"]["seD"]:.2f}), {100 * wA["XU"]["D"] / wA["XU"]["T"]:.0f}% delayed (Table 3).',
    f'Speed of recognition. Equal-weighted, {100 * sh(cu, 0):.0f}% of the eventual response appears in the same week, '
    f'{100 * sh(cu, 1):.0f}% by week 1, {100 * sh(cu, 4):.0f}% by week 4 and {100 * sh(cu, 8):.0f}% by week 8. AUM-weighted '
    f'the figures are {100 * sh(cuw, 0):.0f}%, {100 * sh(cuw, 1):.0f}%, {100 * sh(cuw, 4):.0f}% and {100 * sh(cuw, 8):.0f}% '
    '(Table 4, Figure 1): the assets that most members hold are revalued more slowly than the average option.',
    f'The AUM-weighted result is not driven by AustralianSuper alone: without AustralianSuper the AUM-weighted delayed response '
    f'is {RwL["Excluding AustralianSuper"]:.2f} (standard error {Rw.loc["Excluding AustralianSuper", "XU_seD"]:.2f}). It holds '
    f'with week fixed effects (Model B: {W_["B"]["XU"]["D"]:.2f}, equal {E_["B"]["XU"]["D"]:.2f}), without the COVID months '
    f'({RwL["Excl. Feb-Jun 2020"]:.2f}; equal {ReL["Excl. Feb-Jun 2020"]:.2f}) and in both sub-periods (Table 5). Leads are '
    'close to zero under both weightings.',
    f'Across options the lagged market beta rises with the unlisted share: slope {pc["w_unlisted"]:.2f} (standard error '
    f'{bc["w_unlisted"]:.2f}) equal-weighted and {pcw["w_unlisted"]:.2f} ({bcw["w_unlisted"]:.2f}) AUM-weighted (Table 7, '
    'Figure 2).',
    f'Adding AustralianSuper Socially Aware (one option, {S.loc[S.option_id == "65714394898-ARSB"].shape[0]} weeks, '
    f'{AUM_ARSB:.1f} billion dollars) leaves the estimates almost unchanged: the equal-weighted delayed response is '
    f'{ReL["Baseline"]:.3f} with it and {ReL["Without AustralianSuper Socially Aware"]:.3f} without it.',
    'Why the weightings differ. Under AUM weighting the ten largest options carry '
    f'{100 * TOP10:.0f}% of the weight (AustralianSuper Balanced alone {100 * TOP1:.0f}%), and these are large industry-fund '
    'options with high unlisted shares, whereas equal weighting gives much of the weight to the many small retail options with '
    f'little unlisted (CFS FirstChoice supplies {100 * CFS_SHARE_EQ:.0f}% of option-weeks but {100 * CFS_SHARE_AUM:.1f}% of the '
    'assets). The AUM-weighted estimates describe the experience of the average member dollar; the equal-weighted estimates '
    'describe the average option.']:
    doc.add_paragraph(txt, style=style('List Bullet'))

doc.add_heading('2. Data and model', level=1)
_r = lambda t_: doc.paragraphs[-1].add_run(t_)
para('')
_r('Sample coverage. ').bold = True
_r(f'The {S["option_id"].nunique()} options studied held {AUMT["sample"]:,.0f} billion dollars of member assets in June 2026, '
   f'{100 * AUMT["share"]:.0f}% of the {AUMT["apra"]:,.0f} billion dollars in all APRA-regulated funds '
   f'({100 * AUMT["share_rep"]:.0f}% when identically allocated options represented by a sample option, such as lifecycle stages '
   f'and product copies, are added). MySuper options account for {100 * AUMT["mysuper"]:.0f}% of the sample assets and '
   f'industry and public-sector funds for {100 * AUMT["ind"]:.0f}%. AustralianSuper Socially Aware is added to the sample of '
   'the earlier report: its strategic weights, grouped into our asset buckets, equal those of AustralianSuper Balanced (to June '
   '2025) and Indexed Diversified (from September 2025), so the one-option-per-allocation rule had left it out, but it has its own '
   'crediting rates and holdings (tracking error 1.4% a year against Balanced). Three other excluded socially responsible '
   'options (a second CFS Thrive+ code, Essential Super Thrive+ and MLC Socially Responsible Growth in Super Fundamentals) are '
   'product copies of included options (tracking error 0-0.14% a year) and are not added.')
md_block(MD)

doc.add_heading('3. Results', level=1)
for k, (title, t, note) in tables.items():
    add_table(k, title, t, note)
for k, (title, path, note) in figs.items():
    add_figure(k, title, path, note)

doc.add_heading('4. Caveats and next steps', level=1)
for txt in [
    'AUM weights are June 2026 member assets held fixed over 2015-2026; earlier option-level assets are not in our data. '
    'Options that grew fast (for example lifecycle cohorts and Hostplus) are over-weighted in early years, and options that '
    'shrank are under-weighted.',
    'AUM weighting concentrates the estimate on a few large options, so its standard errors are about twice as large as the '
    'equal-weighted ones and the fund-clustered standard errors rest on few effective clusters.',
    'Retail coverage is partial: AMP, Russell, smartMonday, Centric and OneSuper publish no price history (Appendix C, group B). '
    'Platform funds priced from unit-trust exit prices are used only as a robustness check.',
    'Proxies are ETFs rather than benchmark indices (Bloomberg), and private credit is proxied by Australian bonds, which is weak. '
    'Strategic weights, not actual holdings, are used, measured at the start of each quarter.',
    'Next: add a time-varying asset weight once earlier option-level assets are obtained (APRA quarterly releases), request '
    'missing price histories, and add the revaluation-calendar test and the wealth-transfer bound, where the AUM-weighted '
    'recognition curve is the relevant input.']:
    doc.add_paragraph(txt, style=style('List Bullet'))
para('References: Dimson, E. (1979), Risk measurement when shares are subject to infrequent trading, Journal of '
     'Financial Economics 7, 197-226. Driscoll, J. C. and Kraay, A. C. (1998), Consistent covariance matrix estimation '
     'with spatially dependent panel data, Review of Economics and Statistics 80, 549-560.')

# ------------------------------------------------------------------ appendices: landscape section
sec = doc.add_section(WD_SECTION.NEW_PAGE)
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = Cm(29.7), Cm(21)
for a_ in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, a_, Cm(2.0))


def add_wide_table(num, title, t, note, widths, fs=8):
    p_ = doc.add_paragraph(); r_ = p_.add_run(f'{num}. {title}'); r_.bold = True
    p_.paragraph_format.space_before = Pt(6); p_.paragraph_format.keep_with_next = True
    tb = doc.add_table(rows=len(t) + 1, cols=t.shape[1]); tb.alignment = WD_TABLE_ALIGNMENT.CENTER; tb.autofit = False
    for gc, w_ in zip(tb._tbl.tblGrid.findall(qn('w:gridCol')), widths):
        gc.set(qn('w:w'), str(int(w_ * 567)))
    lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); tb._tbl.tblPr.append(lay)
    for j, w_ in enumerate(widths):
        for c in tb.columns[j].cells:
            c.width = Cm(w_)
    for j, c in enumerate(t.columns):
        tb.cell(0, j).text = str(c)
    trpr = tb.rows[0]._tr.get_or_add_trPr(); th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'true'); trpr.append(th)
    for i, row in enumerate(t.itertuples(index=False)):
        for j, v in enumerate(row):
            tb.cell(i + 1, j).text = fmt(v)
    n = len(t) + 1
    for i in range(n):
        tr = tb.rows[i]._tr.get_or_add_trPr(); cs_ = OxmlElement('w:cantSplit'); cs_.set(qn('w:val'), 'true'); tr.append(cs_)
        for j in range(t.shape[1]):
            c = tb.cell(i, j)
            if i == 0:
                border(c, 'top', 12); border(c, 'bottom', 6)
            if i == n - 1:
                border(c, 'bottom', 12)
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.space_before = Pt(0)
                num_col = pd.api.types.is_numeric_dtype(t.dtypes.iloc[j]) or str(t.columns[j]).startswith(('Options', 'Option-weeks', 'Weeks', 'Core', 'Distinct', 'Assets', 'Fund assets', 'Mean', 'Listed', 'Unlisted', 'Fixed', 'AUM'))
                pp.alignment = WD_ALIGN_PARAGRAPH.RIGHT if (num_col and j > 0) else WD_ALIGN_PARAGRAPH.LEFT
                for rr in pp.runs:
                    rr.font.size = Pt(fs); rr.font.bold = (i == 0)
    q = doc.add_paragraph(); rn = q.add_run('Note: ' + note); rn.font.size = Pt(8.5)


doc.add_heading('Appendices', level=1)
add_wide_table('Appendix A', 'Funds in the study', appA, appA_note,
               [2.6, 1.8, 1.2, 1.5, 1.3, 1.4, 2.5, 1.4, 4.2, 3.5, 4.3])
doc.add_page_break()
add_wide_table('Appendix B', 'Investment options in the study, sample period and main characteristics', appB, appB_note,
               [2.2, 4.6, 2.4, 1.2, 1.2, 1.4, 1.4, 1.1, 1.3, 1.3, 1.4, 1.5, 1.5, 1.9], fs=7)
doc.add_page_break()
add_wide_table('Appendix C', 'Funds still missing from the study', appC, appC_note,
               [1.4, 5.4, 2.0, 2.0, 2.0, 1.8, 11.1])

fn = os.path.join(OUT, 'Lag_model_results_equal_vs_AUM_weighted.docx')
doc.save(fn)
with pd.ExcelWriter(os.path.join(OUT, 'lag_model_tables_equal_vs_AUM_weighted.xlsx'), engine='openpyxl') as xw:
    for k, (title, t, note) in tables.items():
        t.to_excel(xw, sheet_name=k, index=False, startrow=2)
        ws = xw.sheets[k]; ws['A1'] = f'{k}. {title}'; ws.cell(row=len(t) + 5, column=1, value='Note: ' + note)
    for c, nm in CASES.items():
        K[c]['R'].to_excel(xw, sheet_name=f'Robustness raw ({c})', index=False)
        K[c]['F'].to_excel(xw, sheet_name=f'By fund raw ({c})', index=False)
        K[c]['O'].to_excel(xw, sheet_name=f'Option betas ({c})', index=False)
    rc = pd.DataFrame({'Weeks after the news': np.arange(27), 'Unlisted equal': cu[:, 0], 'Unlisted equal SE': cu[:, 1],
                       'Unlisted AUM': cuw[:, 0], 'Unlisted AUM SE': cuw[:, 1], 'Listed equal': cl[:, 0],
                       'Listed equal SE': cl[:, 1], 'Listed AUM': clw[:, 0], 'Listed AUM SE': clw[:, 1]})
    rc.to_excel(xw, sheet_name='Recognition curves (all lags)', index=False)
    for k, t, note in [('Appendix A', appA, appA_note), ('Appendix B', appB, appB_note), ('Appendix C', appC, appC_note)]:
        t.to_excel(xw, sheet_name=k, index=False, startrow=2)
        ws = xw.sheets[k]; ws['A1'] = k; ws.cell(row=len(t) + 5, column=1, value='Note: ' + note)
print('saved', fn)
print(t3.to_string())
print(t5.to_string())
