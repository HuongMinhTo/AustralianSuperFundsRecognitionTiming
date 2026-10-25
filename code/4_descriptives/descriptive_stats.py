"""Descriptive statistics and graphs for the weekly option returns, the market proxies and the exposure-weighted
news variables used in the distributed-lag model (estimation sample of code/3_lag_model, equal-weighted case).
Output: output/descriptives/Descriptive_statistics_returns_and_proxies.docx / .xlsx and PNG figures.
Run: python3 code/4_descriptives/descriptive_stats.py   (after code/3_lag_model/run_lag_model.sh)"""
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
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(R, 'output', 'descriptives')
os.makedirs(OUT, exist_ok=True)
S = pd.read_pickle(os.path.join(R, 'output', 'estimates', 'lag_model', 'equal', 'S.pkl')).sort_values(['option_id', 'week'])
S['ret_pct'] = 100 * S['ret']
S['w_fic'] = S['w_FI'].fillna(0) + S['w_CASH'].fillna(0)
S['w_oth'] = (1 - S['w_listed_growth'].fillna(0) - S['w_unlisted_core'].fillna(0) - S['w_fic']).clip(lower=0)
S['XT'] = S['XU'] + S['XL'] + S['XD'] + S['XO']
W0, W1 = S['week'].min(), S['week'].max()
FUNDNAME = {'CONSTRUCTION AND BUILDING UNIONS SUPERANNUATION FUND': 'Cbus', 'HOSTPLUS Superannuation Fund': 'Hostplus',
            'Colonial First State FirstChoice Superannuation Trust': 'CFS FirstChoice'}


def stats(x):
    x = pd.Series(x).dropna()
    return dict(N=len(x), Mean=x.mean(), SD=x.std(), Min=x.min(), P25=x.quantile(.25), Median=x.median(),
                P75=x.quantile(.75), Max=x.max(), Skewness=x.skew(), Kurtosis=x.kurt())


# option-level first-order autocorrelation of weekly returns (needs consecutive weeks)
def ac1(g):
    g = g.set_index('week')['ret']
    g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq='W-WED'))   # complete calendar; gaps stay missing
    return g.corr(g.shift(1)) if g.notna().sum() > 30 else np.nan


oac = S.groupby('option_id').apply(ac1)
S['opt_ac1'] = S['option_id'].map(oac)

# ------------------------------------------------------------------ Table 1: weekly option returns (panel)
S['unl_bin'] = pd.cut(S['w_unlisted_core'], [-0.001, 0.05, 0.15, 0.25, 1.0],
                      labels=['Unlisted share 0-5%', 'Unlisted share 5-15%', 'Unlisted share 15-25%', 'Unlisted share above 25%'])
PT = {'unit_price': 'Unit-price series', 'crediting_rate': 'Crediting-rate series', 'cumulative_index': 'Crediting-index series (UniSuper)'}
groups = [('All option-weeks', S)]
groups += [(f'{t} funds' if t != 'Public Sector' else 'Public-sector funds', S[S.fund_type_fixed == t])
           for t in ['Industry', 'Public Sector', 'Retail']]
groups += [('MySuper options', S[S.is_mysuper_option == True]), ('Choice options', S[S.is_mysuper_option != True])]
groups += [(PT[p], S[S.price_type == p]) for p in ['unit_price', 'crediting_rate', 'cumulative_index']]
groups += [(str(b), S[S.unl_bin == b]) for b in S['unl_bin'].cat.categories]
rows = []
for lab, d in groups:
    st = stats(d['ret_pct'])
    rows.append(dict(Group=lab, Funds=d.abn.nunique(), Options=d.option_id.nunique(), **st,
                     **{'AC(1), median option': d.drop_duplicates('option_id')['opt_ac1'].median(),
                        'Annualised mean (%)': 52 * st['Mean'], 'Annualised volatility (%)': np.sqrt(52) * st['SD']}))
T1 = pd.DataFrame(rows).rename(columns={'N': 'Option-weeks', 'Kurtosis': 'Kurt.', 'Skewness': 'Skew.', 'AC(1), median option': 'AC(1)',
                                        'Annualised mean (%)': 'Ann. mean (%)', 'Annualised volatility (%)': 'Ann. vol. (%)'})

# ------------------------------------------------------------------ Table 2: cross-section of options
opt = S.groupby('option_id').agg(fund=('fund_name', 'first'), weeks=('ret', 'size'), mean=('ret', 'mean'), sd=('ret', 'std'),
                                 wU=('w_unlisted_core', 'mean'), wLG=('w_listed_growth', 'mean'), wFC=('w_fic', 'mean'),
                                 aum=('aum_k', 'first'))
opt['ann_ret'] = 100 * 52 * opt['mean']
opt['ann_vol'] = 100 * np.sqrt(52) * opt['sd']
opt['ac1'] = oac.reindex(opt.index)
opt['aum_bn'] = opt['aum'] / 1e6
cs_vars = [('Weeks with a return', 'weeks', 1), ('Annualised mean return (%)', 'ann_ret', 1),
           ('Annualised volatility (%)', 'ann_vol', 1), ('First-order autocorrelation, AC(1)', 'ac1', 1),
           ('Listed growth share (%)', 'wLG', 100), ('Unlisted share (%)', 'wU', 100),
           ('Fixed income and cash share (%)', 'wFC', 100), ('Member assets, June 2026 ($bn)', 'aum_bn', 1)]
T2 = pd.DataFrame([dict(Variable=lab, Options=int(opt[c].notna().sum()), Mean=(opt[c] * k).mean(), SD=(opt[c] * k).std(),
                        P10=(opt[c] * k).quantile(.1), P25=(opt[c] * k).quantile(.25), Median=(opt[c] * k).median(),
                        P75=(opt[c] * k).quantile(.75), P90=(opt[c] * k).quantile(.9))
                   for lab, c, k in cs_vars])

# ------------------------------------------------------------------ Table 3: market proxies (Wednesday to Wednesday)
p = pd.read_csv(os.path.join(R, 'data', 'raw', 'proxies', 'proxy_etf_prices_yahoo.csv'), parse_dates=['date'])
px = p.pivot_table(index='date', columns='ticker', values='adjclose').sort_index()
first_px = p.dropna(subset=['adjclose']).groupby('ticker')['date'].min()
wed = pd.date_range(W0 - pd.Timedelta(days=7), W1, freq='W-WED')
lv = np.log(px.reindex(px.index.union(wed)).ffill(limit=5).loc[wed])
rw = 100 * lv.diff().iloc[1:]
PROX = [('VAS.AX', 'Vanguard Australian Shares (S&P/ASX 300)', 'Listed Australian equity'),
        ('VGS.AX', 'Vanguard MSCI Index International Shares', 'Listed international equity, unhedged'),
        ('VGAD.AX', 'Vanguard MSCI International Shares (Hedged)', 'Listed international equity, hedged'),
        ('VSO.AX', 'Vanguard MSCI Australian Small Companies', 'Unlisted (private) equity'),
        ('VAP.AX', 'Vanguard Australian Property Securities', 'Listed and unlisted Australian property'),
        ('DJRE.AX', 'SPDR Dow Jones Global Real Estate', 'Listed and unlisted international property'),
        ('IFRA.AX', 'VanEck FTSE Global Infrastructure (Hedged)', 'Listed and unlisted infrastructure'),
        ('VAF.AX', 'Vanguard Australian Fixed Interest', 'Australian fixed income; private credit'),
        ('VIF.AX', 'Vanguard International Fixed Interest (Hedged)', 'International fixed income'),
        ('BILL.AX', 'iShares Core Cash ETF', 'Cash'),
        ('WXOZ.AX', 'SPDR S&P World ex Australia', 'Back-fill for VGS/VGAD before they start'),
        ('^AXJO', 'S&P/ASX 200 index', 'Reference only')]
rows = []
for t, name, use in PROX:
    if t not in rw:
        continue
    x = rw[t]
    st = stats(x)
    rows.append(dict(Ticker=t.replace('.AX', ''), Proxy=name, **{'Used for': use},
                     **{'First price': first_px.get(t, pd.NaT)}, Weeks=st['N'], Mean=st['Mean'], SD=st['SD'],
                     Min=st['Min'], Max=st['Max'], Skewness=st['Skewness'], **{'Excess kurtosis': st['Kurtosis']},
                     **{'AC(1)': x.dropna().autocorr(1), 'Annualised mean (%)': 52 * st['Mean'],
                        'Annualised volatility (%)': np.sqrt(52) * st['SD']}))
T3 = pd.DataFrame(rows).rename(columns={'Skewness': 'Skew.', 'Excess kurtosis': 'Kurt.', 'Annualised mean (%)': 'Ann. mean (%)',
                                       'Annualised volatility (%)': 'Ann. vol. (%)'})
T3['First price'] = pd.to_datetime(T3['First price']).dt.strftime('%b %Y')
order = [t for t, _, _ in PROX if t in rw and t != 'WXOZ.AX']
T4 = rw[order].corr().round(2)
T4.index = T4.columns = [t.replace('.AX', '') for t in order]
T4 = T4.reset_index().rename(columns={'index': ''})

# ------------------------------------------------------------------ Table 5: exposure-weighted news and weights
nv = [('Unlisted news X^U (%)', S['XU'] * 100), ('Listed growth news X^L (%)', S['XL'] * 100),
      ('Defensive news X^D (%)', S['XD'] * 100), ('Other/unspecified news X^O (%)', S['XO'] * 100),
      ('Total news X (%)', S['XT'] * 100), ('Option return r (%)', S['ret_pct']),
      ('Unlisted share w^U (%)', S['w_unlisted_core'] * 100), ('Listed growth share (%)', S['w_listed_growth'] * 100),
      ('Fixed income and cash share (%)', S['w_fic'] * 100), ('Other and unspecified share (%)', S['w_oth'] * 100)]
T5 = pd.DataFrame([dict(Variable=lab, **{k: v for k, v in stats(x).items() if k not in ('Skewness', 'Kurtosis')})
                   for lab, x in nv]).rename(columns={'N': 'Option-weeks'})
# correlation of option returns with current and lagged news (pooled, within option)
g = S.groupby('option_id')
cors = {}
for lab, v in [('X^U', 'XU'), ('X^L', 'XL'), ('X', 'XT')]:
    # news of calendar week t-k (missing if that week is not in the sample), never the previous retained row
    src = S[['option_id', 'week', v]]
    cors[lab] = [S['ret'].corr(pd.Series(S[['option_id', 'week']].merge(
        src.assign(week=src['week'] + pd.Timedelta(weeks=k)), on=['option_id', 'week'], how='left')[v].values,
        index=S.index)) for k in range(0, 5)]
T6 = pd.DataFrame(cors, index=[f'Lag {k}' for k in range(5)]).T.round(3).reset_index().rename(columns={'index': 'News variable'})

# ------------------------------------------------------------------ figures (black and white)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],
                     'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '0.3',
                     'axes.grid': True, 'axes.axisbelow': True, 'grid.color': '0.9', 'legend.frameon': False,
                     'savefig.dpi': 300, 'savefig.bbox': 'tight'})
figs = []
LS = [dict(color='0.0', ls='-'), dict(color='0.0', ls='--'), dict(color='0.5', ls='-'), dict(color='0.5', ls=':')]

# Figure 1: growth of $1 in the proxies
wl = lv.loc[lv.index >= W0]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=False)
for ax, (tit, tk) in zip(axs, [('(a) Equity and property proxies', ['VAS.AX', 'VGS.AX', 'VSO.AX', 'VAP.AX']),
                               ('(b) Infrastructure, bond and cash proxies', ['IFRA.AX', 'VAF.AX', 'VIF.AX', 'BILL.AX'])]):
    for t, st in zip(tk, LS):
        s = wl[t].dropna()
        ax.plot(s.index, np.exp(s - s.iloc[0]), lw=1.3, label=t.replace('.AX', '') + (f' (from {s.index[0]:%b %Y})' if s.index[0] > W0 + pd.Timedelta(days=30) else ''), **st)
    ax.axhline(1, color='0.3', lw=0.6)
    ax.set_title(tit, fontsize=10, loc='left'); ax.set_ylabel('Value of $1 invested (adjusted close)')
    ax.legend(loc='upper left', fontsize=8.5)
p_ = os.path.join(OUT, 'fig1_proxy_growth.png'); fig.savefig(p_); plt.close(fig)
figs.append(('Figure 1', 'Market proxies: growth of $1, July 2015 to August 2026', p_,
             'Weekly (Wednesday) adjusted closing prices of the ASX-listed ETFs used as proxies (dividends reinvested). '
             'Series that start after July 2015 are shown from their first price; in the model they are back-filled '
             '(WXOZ for VGS/VGAD, VAP for DJRE, VAF for VIF, a REIT/equity blend for IFRA, zero for BILL).'))

# Figure 2: average option vs a listed 70/30 portfolio
ew = S.groupby('week')['ret'].mean()
aw = S.dropna(subset=['aum_k']).groupby('week').apply(lambda d: np.average(d['ret'], weights=d['aum_k']))
bench = (0.35 * rw['VAS.AX'] + 0.35 * rw['VGS.AX'].fillna(rw['WXOZ.AX']) + 0.30 * rw['VAF.AX']) / 100
bench = bench.reindex(ew.index)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
ax = axs[0]
for s_, lab, st in [(ew, 'Options, equal-weighted average', LS[0]), (aw, 'Options, AUM-weighted average', LS[1]),
                    (bench, 'Listed 70/30 portfolio (35% VAS, 35% VGS, 30% VAF)', LS[2])]:
    ax.plot(s_.index, 100 * np.exp(s_.fillna(0).cumsum()), lw=1.3, label=lab, **st)
ax.set_title('(a) Cumulative return, index July 2015 = 100', fontsize=10, loc='left')
ax = axs[1]
for s_, lab, st in [(ew, 'Options, equal-weighted average', LS[0]), (aw, 'Options, AUM-weighted average', LS[1]),
                    (bench, 'Listed 70/30 portfolio', LS[2])]:
    ax.plot(s_.index, 100 * np.sqrt(52) * s_.rolling(52).std(), lw=1.3, label=lab, **st)
ax.set_title('(b) Rolling 52-week volatility (% a year)', fontsize=10, loc='left')
h_, l_ = axs[0].get_legend_handles_labels()
fig.legend(h_, l_, loc='lower center', ncol=3, fontsize=8.5, bbox_to_anchor=(0.5, -0.06))
p_ = os.path.join(OUT, 'fig2_options_vs_listed.png'); fig.savefig(p_); plt.close(fig)
figs.append(('Figure 2', 'Average option return compared with a listed 70/30 portfolio', p_,
             'Weekly log returns of the sample options averaged each week (equal-weighted, or weighted by June 2026 member '
             'assets), compared with a listed portfolio of 35% Australian shares, 35% international shares and 30% Australian '
             'bonds. Option returns are net of fees and taxes; the listed portfolio is gross.'))

# Figure 3: volatility and autocorrelation against unlisted share (option level)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
ax = axs[0]
bins = [0, .05, .15, .25, 1]
labs = ['0-5%', '5-15%', '15-25%', '>25%']
opt['ubin'] = pd.cut(opt['wU'], bins, labels=labs, include_lowest=True)
opt['vol_per_growth'] = opt['ann_vol'] / (100 * (opt['wLG'] + opt['wU'])).replace(0, np.nan) * 100
data = [opt.loc[opt.ubin == b, 'ann_vol'].dropna() for b in labs]
ax.boxplot(data, labels=[f'{b}\n(n={len(d)})' for b, d in zip(labs, data)], widths=0.5, patch_artist=True,
           boxprops=dict(facecolor='0.9', color='0.2'), medianprops=dict(color='0.0', lw=1.5),
           whiskerprops=dict(color='0.2'), capprops=dict(color='0.2'), flierprops=dict(marker='o', ms=3, mec='0.3'))
ax.set_xlabel('Mean unlisted share of option'); ax.set_ylabel('Annualised volatility of weekly returns (%)')
ax.set_title('(a) Volatility by unlisted share', fontsize=10, loc='left')
ax = axs[1]
ax.scatter(100 * opt['wU'], opt['ac1'], s=14, facecolor='none', edgecolor='0.2', lw=0.6)
o2 = opt.dropna(subset=['ac1', 'wU'])
b_ = np.polyfit(100 * o2['wU'], o2['ac1'], 1)
xx = np.linspace(0, 100 * o2['wU'].max(), 20)
ax.plot(xx, np.polyval(b_, xx), color='0.0', lw=1.3, label=f'Linear fit: {10 * b_[0]:+.3f} per 10 percentage points')
ax.axhline(0, color='0.3', lw=0.6)
ax.set_xlabel('Mean unlisted share of option (%)'); ax.set_ylabel('First-order autocorrelation of weekly returns')
ax.set_title('(b) Return autocorrelation and unlisted share', fontsize=10, loc='left'); ax.legend(loc='upper left', fontsize=8.5)
p_ = os.path.join(OUT, 'fig3_volatility_autocorrelation.png'); fig.savefig(p_); plt.close(fig)
figs.append(('Figure 3', 'Return volatility and autocorrelation by unlisted share', p_,
             'One observation per option. Panel (a): boxes show the interquartile range and median, whiskers 1.5 times the '
             'interquartile range. Panel (b): first-order autocorrelation of each option\'s weekly returns; positive '
             'autocorrelation is the classic sign of smoothed (stale) prices.'))

# Figure 4: average strategic allocation over time
qalloc = S.groupby('saa_date')[['w_listed_growth', 'w_unlisted_core', 'w_fic', 'w_oth']].mean() * 100
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.stackplot(qalloc.index, qalloc.T.values, colors=['0.25', '0.55', '0.8', '0.95'], edgecolor='white', lw=0.8,
             labels=['Listed growth (equity, property, infrastructure)', 'Unlisted (equity, property, infrastructure, credit)',
                     'Fixed income and cash', 'Other and not specified'])
ax.set_ylim(0, 100); ax.set_ylabel('Mean strategic weight (%)')
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8.5)
p_ = os.path.join(OUT, 'fig4_mean_allocation.png'); fig.savefig(p_); plt.close(fig)
figs.append(('Figure 4', 'Mean strategic asset allocation of the sample options', p_,
             'Equal-weighted mean of the APRA strategic weights across the options in the sample at the end of each quarter '
             '(the weights applied in the following quarter). The sample composition changes over time as options enter.'))

# Figure 5: unlisted news vs listed news, weekly cross-option mean
mx = S.groupby('week')[['XU', 'XL']].mean() * 100
fig, ax = plt.subplots(figsize=(10, 3.4))
ax.plot(mx.index, mx['XL'], color='0.6', lw=0.8, label=r'Listed growth news $X^L$')
ax.plot(mx.index, mx['XU'], color='0.0', lw=0.8, label=r'Unlisted news $X^U$')
ax.axhline(0, color='0.3', lw=0.6); ax.set_ylabel('Weekly news, mean across options (%)')
ax.legend(loc='lower left', fontsize=8.5)
p_ = os.path.join(OUT, 'fig5_news_series.png'); fig.savefig(p_); plt.close(fig)
figs.append(('Figure 5', 'Exposure-weighted market news over time', p_,
             'Weekly exposure-weighted news, X^U and X^L in equation (2) of the results report: proxy returns multiplied by '
             'each option\'s strategic weights, averaged across options each week.'))

# ------------------------------------------------------------------ Word (landscape, Times New Roman, black and white)
doc = Document()
sec = doc.sections[0]
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = Cm(29.7), Cm(21)
for a in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, a, Cm(2.0))
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
for nm in ('Title', 'Heading 1', 'Heading 2'):
    s_ = doc.styles[nm]
    s_.font.color.rgb = RGBColor(0, 0, 0)
    ppr = s_.element.find(qn('w:pPr'))
    if ppr is not None:
        for b in ppr.findall(qn('w:pBdr')):
            ppr.remove(b)
doc.styles['Normal'].font.size = Pt(11)


def border(c, edge, sz):
    tcPr = c._tc.get_or_add_tcPr()
    b = tcPr.find(qn('w:tcBorders'))
    if b is None:
        b = OxmlElement('w:tcBorders'); tcPr.append(b)
    e = OxmlElement(f'w:{edge}'); e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), str(sz)); e.set(qn('w:color'), '000000')
    b.append(e)


def fmt(v, d):
    if isinstance(v, str):
        return v
    if pd.isna(v):
        return ''
    if isinstance(v, (int, np.integer)) or (isinstance(v, float) and float(v).is_integer() and abs(v) >= 100):
        return f'{int(v):,}'
    return f'{v:,.{d}f}'


def add_table(num, title, t, note, widths, fs=8.5, d=3):
    p_ = doc.add_paragraph(); r_ = p_.add_run(f'{num}. {title}'); r_.bold = True
    p_.paragraph_format.space_before = Pt(10); p_.paragraph_format.keep_with_next = True
    tb = doc.add_table(rows=len(t) + 1, cols=t.shape[1]); tb.alignment = WD_TABLE_ALIGNMENT.CENTER; tb.autofit = False
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
            tb.cell(i + 1, j).text = fmt(v, d)
    n = len(t) + 1
    for i in range(n):
        for j in range(t.shape[1]):
            c = tb.cell(i, j)
            if i == 0:
                border(c, 'top', 12); border(c, 'bottom', 6)
            if i == n - 1:
                border(c, 'bottom', 12)
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.space_before = Pt(0)
                pp.paragraph_format.keep_with_next = i < n - 1
                isnum = pd.api.types.is_numeric_dtype(t.dtypes.iloc[j]) or t.columns[j].startswith('Lag')
                pp.alignment = WD_ALIGN_PARAGRAPH.RIGHT if (isnum and j > 0) else WD_ALIGN_PARAGRAPH.LEFT
                for rr in pp.runs:
                    rr.font.size = Pt(fs); rr.font.bold = (i == 0)
    q = doc.add_paragraph(); rn = q.add_run('Note: ' + note); rn.font.size = Pt(9)


doc.add_heading('Descriptive statistics: weekly option returns and market proxies', level=0)
doc.add_paragraph(f'Minh Huong · estimation sample of the distributed-lag model: {S.fund_name.nunique()} funds, '
                  f'{S.option_id.nunique()} options, {len(S):,} option-weeks, weekly returns {W0:%B %Y} to {W1:%B %Y}. '
                  'Returns are weekly log returns in per cent (Wednesday to Wednesday, measured between the valuation dates '
                  'of the last prices on or before each Wednesday).')
doc.add_heading('Summary', level=1)
a, l = T1.iloc[0], T3.set_index('Ticker')
for txt in [
    f'The average option earned {a["Ann. mean (%)"]:.1f}% a year (log return, net of fees and taxes) with annualised '
    f'volatility of {a["Ann. vol. (%)"]:.1f}%, against {l.loc["VAS", "Ann. vol. (%)"]:.1f}% for '
    f'Australian shares (VAS) and {l.loc["VGS", "Ann. vol. (%)"]:.1f}% for international shares (VGS).',
    f'Volatility falls as the unlisted share rises: options with more than 25% unlisted have annualised volatility of '
    f'{T1.set_index("Group").loc["Unlisted share above 25%", "Ann. vol. (%)"]:.1f}%, against '
    f'{T1.set_index("Group").loc["Unlisted share 0-5%", "Ann. vol. (%)"]:.1f}% for options with less than 5% '
    '(Table 1, Figure 3), although high-unlisted options are mostly growth-oriented.',
    f'Weekly option returns are only mildly autocorrelated on average (median option AC(1) {a["AC(1)"]:.2f}, '
    f'similar to listed shares: VAS {l.loc["VAS", "AC(1)"]:.2f}, VGS {l.loc["VGS", "AC(1)"]:.2f}), but the autocorrelation '
    f'rises with the unlisted share, from {T1.set_index("Group").loc["Unlisted share 0-5%", "AC(1)"]:.2f} for '
    f'options with less than 5% unlisted to {T1.set_index("Group").loc["Unlisted share above 25%", "AC(1)"]:.2f} '
    'for options with more than 25% (Table 1, Figure 3b), as expected if unlisted assets are revalued with a lag.',
    f'Same-week market news explains most of the weekly variation in option returns (correlation with total news '
    f'{T6.iloc[2]["Lag 0"]:.2f}); correlations with news one to four weeks earlier are small (at most '
    f'{T6[["Lag 1", "Lag 2", "Lag 3", "Lag 4"]].abs().values.max():.2f}, Table 6). Delayed recognition is therefore a small '
    'part of weekly variance, which is why it is measured with the summed lag coefficients of the regression model rather '
    'than with simple correlations.',
    f'The market proxies cover the sample period except IFRA (from {T3.set_index("Ticker").loc["IFRA", "First price"]}), VIF '
    f'and BILL (back-filled in the model). Listed property (VAP) is the most volatile proxy '
    f'({l.loc["VAP", "Ann. vol. (%)"]:.1f}% a year) and cash (BILL) is the only strongly autocorrelated one '
    f'(AC(1) {l.loc["BILL", "AC(1)"]:.2f}).']:
    doc.add_paragraph(txt, style='List Bullet')

add_table('Table 1', 'Weekly option returns (%), pooled option-weeks', T1, (
    'Weekly log returns in per cent. Groups by fund type (APRA, June 2026), MySuper status, type of published series and the '
    'option-week unlisted share (start-of-quarter strategic weight). AC(1) is the median across options of each option\'s '
    'first-order autocorrelation. Annualised mean = 52 x weekly mean; annualised volatility = square root of 52 x weekly '
    'standard deviation.'), [3.8, 1.1, 1.3, 1.6] + [1.35] * 9 + [1.2, 1.5, 1.5], fs=7.5)
add_table('Table 2', 'Cross-section of options', T2, (
    'One observation per option. Asset shares are the mean APRA strategic weights over the option\'s weeks in the sample; '
    'member assets are from APRA QSPS Product Structure, Table 1b (all investment pathways).'),
    [6.0, 1.6] + [2.2] * 7, fs=8.5, d=2)
add_table('Table 3', 'Market proxies: weekly returns (%), Wednesday to Wednesday', T3, (
    f'Weekly log returns of adjusted closing prices (Yahoo Finance), {W0:%B %Y} to {W1:%B %Y}, from each ETF\'s first price. '
    'In the model, missing early weeks are back-filled: WXOZ for VGS and VGAD, VAP for DJRE, VAF for VIF, a 50/50 blend '
    'of hedged international equity and global REITs for IFRA, and zero for BILL. The S&P/ASX 200 index is shown for '
    'reference only.'), [1.3, 4.6, 4.4, 1.5, 1.3, 1.1, 1.1, 1.3, 1.2, 1.1, 1.2, 1.1, 1.5, 1.5], fs=7.5)
add_table('Table 4', 'Correlations of weekly proxy returns', T4, 'Pearson correlations of weekly log returns over common weeks.',
          [1.6] + [1.6] * (T4.shape[1] - 1), fs=8.5, d=2)
add_table('Table 5', 'Exposure-weighted news, option returns and strategic weights (pooled option-weeks)', T5, (
    'News variables as in equation (2) of the results report: weekly proxy returns weighted by the option\'s start-of-quarter '
    'strategic weights; X = X^U + X^L + X^D + X^O. Weights in per cent of the option; a listed growth share above 100% '
    'belongs to geared options (CFS Geared Growth Plus).'),
    [6.0, 2.1] + [1.9] * 7, fs=8.5)
add_table('Table 6', 'Correlation of weekly option returns with current and lagged news', T6, (
    'Pooled correlation between the option return in week t and the option\'s news in week t-k (k = 0 to 4).'),
    [5.0] + [2.2] * 5, fs=9)
for num, title, path, note in figs:
    p_ = doc.add_paragraph(); r_ = p_.add_run(f'{num}. {title}'); r_.bold = True; p_.paragraph_format.keep_with_next = True
    doc.add_picture(path, width=Cm(23)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    q = doc.add_paragraph(); rn = q.add_run('Note: ' + note); rn.font.size = Pt(9)
fn = os.path.join(OUT, 'Descriptive_statistics_returns_and_proxies.docx')
doc.save(fn)

with pd.ExcelWriter(os.path.join(OUT, 'Descriptive_statistics_returns_and_proxies.xlsx'), engine='openpyxl') as xw:
    for k, t in [('Table 1 Option returns', T1), ('Table 2 Cross-section', T2), ('Table 3 Proxies', T3),
                 ('Table 4 Proxy correlations', T4), ('Table 5 News and weights', T5), ('Table 6 Return-news corr', T6)]:
        t.to_excel(xw, sheet_name=k, index=False)
    opt.drop(columns=['mean', 'sd']).reset_index().to_excel(xw, sheet_name='Option-level data', index=False)
    rw.loc[rw.index >= W0].to_excel(xw, sheet_name='Proxy weekly returns (%)')
    pd.DataFrame({'Equal-weighted options': ew, 'AUM-weighted options': aw, 'Listed 70/30': bench}).to_excel(
        xw, sheet_name='Average option returns')
    qalloc.to_excel(xw, sheet_name='Mean allocation by quarter')
print('saved', fn)
pd.set_option('display.width', 250)
print(T1.round(3).to_string()); print(T2.round(2).to_string()); print(T3.round(3).to_string()); print(T6.to_string())
