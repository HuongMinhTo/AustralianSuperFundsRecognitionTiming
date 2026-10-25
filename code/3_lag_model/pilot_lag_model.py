"""Estimation of the exposure-weighted distributed-lag model on the weekly unit-price panel.

r_{i,t} = a_i (+ d_t) + sum_g bU_g * XU_{i,g,t} + sum_g bL_g * XL_{i,g,t}
          + sum_{k=0,1} (cD_k XD_{i,t-k} + cO_k XO_{i,t-k}) + e_{i,t}

X^U_{i,t} = sum_{b in unlisted buckets} w_{i,b,q(t)} R^proxy_{b,t}   (start-of-quarter weights)
X^L_{i,t} = same over listed growth buckets; X^D defensive (FI, cash); X^O other/not-specified.
Lag groups g: {0},{1},{2-4},{5-8},{9-13},{14-26}; XU_{g,t} = sum_{k in g} X^U_{i,t-k}
(so b_g is the average per-lag coefficient in group g).
Summed delayed response D^U = sum_{g>=1} n_g bU_g; recognition curve C(h) = cumulative share.
"""
import os
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
U = _ROOT + '/'
OUTD = os.path.join(_ROOT, 'output', 'estimates', 'lag_model', os.environ.get('OUTSUB', ''))
os.makedirs(OUTD, exist_ok=True)
# Sample: 'main' = all priced core options except platform funds priced from unit-trust exit prices
# (trust prices drop on distribution dates; quarterly match with APRA is weak); 'trusts' = include them;
# 'tierA' = the 18 Tier A funds of the first estimation.
SAMPLE = os.environ.get('SAMPLE', 'main')
# WEIGHT: 'equal' = every option-week counts equally; 'aum' = option-weeks weighted by the option's member assets
# at June 2026 (APRA QSPS Product Structure Table 1b, all investment pathways), normalised to mean 1.
WEIGHT = os.environ.get('WEIGHT', 'equal')
# Options added although another option with identical (bucketed) strategic weights represents their allocation:
# AustralianSuper Socially Aware has its own crediting rates and holdings (tracking error 1.4% a year vs Balanced).
ADD_OPTIONS = ['65714394898-ARSB']
TRUST_ABNS = [70815369818, 81154851339, 82004832237, 57526653420, 61808189263]
TIERA_ABNS = [23053121564, 24496637884, 28342064803, 33813823017, 53226460365, 60346078879, 60905115063,
              62653671394, 64971749321, 65127917725, 65714394898, 68657495890, 73549180515, 74559365913,
              75493363262, 76641658449, 85571332201, 91385943850]
GROUPS = [(0, 0), (1, 1), (2, 4), (5, 8), (9, 13), (14, 26)]
GNAME = ['0', '1', '2-4', '5-8', '9-13', '14-26']
NG = np.array([b - a + 1 for a, b in GROUPS])

# ------------------------------------------------------------------ proxies
# Market news is measured over the SAME window as each option's return: from the previous price date to
# the current price date (price_date in master_weekly). This matters for series whose weekly periods end
# on a Tuesday (AMIST, HESTA before 2021) or a Friday (NGS before 2021). Set PROXY_ALIGN=wed to use plain
# Wednesday-to-Wednesday proxy returns instead (the original pilot).
ALIGN = os.environ.get('PROXY_ALIGN', 'own')
p = pd.read_csv(U + 'data/raw/proxies/proxy_etf_prices_yahoo.csv', parse_dates=['date'])
px = p.pivot_table(index='date', columns='ticker', values='adjclose').sort_index()
days = pd.bdate_range('2009-01-01', '2026-09-30')
Rd = np.log(px.reindex(px.index.union(days)).ffill(limit=5).loc[days]).diff()


def fb(a, b):                      # daily log return of a, with fallback b before a starts
    return Rd[a].fillna(Rd[b]) if b is not None else Rd[a]


comp = pd.DataFrame({'eq_au': Rd['VAS.AX'], 'eq_int_u': fb('VGS.AX', 'WXOZ.AX'), 'eq_int_h': fb('VGAD.AX', 'WXOZ.AX'),
                     'small': Rd['VSO.AX'], 'reit_au': Rd['VAP.AX'], 'reit_gl': fb('DJRE.AX', 'VAP.AX'),
                     'fi_au': Rd['VAF.AX'], 'fi_gl': fb('VIF.AX', 'VAF.AX'), 'cash': Rd['BILL.AX'].fillna(0.0)})
comp['infra'] = Rd['IFRA.AX'].fillna(0.5 * comp['eq_int_h'] + 0.5 * comp['reit_gl'])
LEV = comp.fillna(0).cumsum()                     # cumulative log-return index per component
PCOLS = list(LEV.columns)

w = pd.read_csv(U + 'data/derived/master_weekly.csv.gz', parse_dates=['week', 'saa_date', 'price_date'], low_memory=False)
w = w.sort_values(['option_id', 'week'])
if ALIGN == 'wed':
    ref = w['week']
else:
    ref = w['price_date'].fillna(w['week'])
ud = pd.DatetimeIndex(ref.unique()).sort_values()
lev_at = LEV.reindex(LEV.index.union(ud)).ffill().loc[ud]
L = lev_at.reindex(ref.values).set_axis(w.index)
for c in PCOLS:
    w[c] = L[c].groupby(w['option_id']).diff()
print('proxy alignment:', ALIGN, '| sample:', SAMPLE)
W = lambda c: w[c].fillna(0)
h = w['hedge_ratio_intl'].clip(0, 1).fillna(0.5)
eq_int = h * w['eq_int_h'] + (1 - h) * w['eq_int_u']
eq_bl = 0.5 * w['eq_au'] + 0.5 * eq_int
reit_bl = 0.5 * w['reit_au'] + 0.5 * w['reit_gl']

w['XL'] = (W('w_EQ_AU_L') * w['eq_au'] + W('w_EQ_INT_L') * eq_int + W('w_PROP_AU_L') * w['reit_au']
           + W('w_PROP_INT_L') * w['reit_gl'] + W('w_INFRA_L') * w['infra'])
w['XU'] = (W('w_PE_U') * w['small'] + W('w_PROP_U_AU') * w['reit_au'] + W('w_PROP_U_INT') * w['reit_gl']
           + W('w_PROP_U_NSDOM') * reit_bl + W('w_INFRA_U') * w['infra'] + W('w_CREDIT_U') * w['fi_au'])
w['XD'] = W('w_FI') * (0.5 * w['fi_au'] + 0.5 * w['fi_gl']) + W('w_CASH') * w['cash'] + W('w_CREDIT_OTHER') * w['fi_au']
w['XO'] = ((W('w_EQ_OTHER') + W('w_ALT_U') + W('w_ALT_OTHER') + W('w_OTHER')) * eq_bl
           + (W('w_PROP_NS') + W('w_PROP_OTHER')) * reit_bl + (W('w_INFRA_NS') + W('w_INFRA_OTHER')) * w['infra'])

w = w.sort_values(['option_id', 'week'])
g = w.groupby('option_id')
for v in ['XU', 'XL']:
    lags = {k: g[v].shift(k) for k in range(0, 27)}
    for (a, b), nm in zip(GROUPS, GNAME):
        w[f'{v}_{nm}'] = sum(lags[k] for k in range(a, b + 1))
    w[f'{v}_lead'] = sum(g[v].shift(-k) for k in range(1, 5))
for v in ['XD', 'XO']:
    w[f'{v}_0'] = w[v]
    w[f'{v}_1'] = g[v].shift(1)

UL = [f'XU_{n}' for n in GNAME]
LL = [f'XL_{n}' for n in GNAME]
CTRL = ['XD_0', 'XD_1', 'XO_0', 'XO_1']
keep = w['core_sample_dedup_priced'].astype(bool) | (w['option_id'].isin(ADD_OPTIONS) & w['core_sample'].astype(bool)
                                                   & ~w['is_pension'].astype(bool))
if SAMPLE == 'main':
    keep &= ~w['abn'].isin(TRUST_ABNS)
elif SAMPLE == 'tierA':
    keep &= w['abn'].isin(TIERA_ABNS)
w['in_sample'] = keep
S = w[w['in_sample'] & w['ret'].notna() & (w['week'] >= '2015-07-01')].copy()
S = S.dropna(subset=UL + LL + CTRL + ['XU_lead'])
AUM = pd.read_csv(U + 'data/derived/option_aum_june2026_all.csv', index_col='option_id')['assets_k']
S['aum_k'] = S['option_id'].map(AUM)
if WEIGHT == 'aum':
    S = S[S['aum_k'] > 0].copy()
    S['wt'] = S['aum_k'] / S['aum_k'].mean()
else:
    S['wt'] = 1.0
print('weights:', WEIGHT)
S['fund_id'] = pd.factorize(S['abn'])[0]
print('sample:', len(S), 'option-weeks |', S.option_id.nunique(), 'options |', S.fund_name.nunique(), 'funds |',
      S.week.min().date(), '-', S.week.max().date())


def fit(df, cols, time_fe, cov='kernel'):
    d = df.set_index(['option_id', 'week'])
    mod = PanelOLS(d['ret'], d[cols], entity_effects=True, time_effects=time_fe, drop_absorbed=True,
                   weights=d['wt'] if WEIGHT == 'aum' else None)
    if cov == 'kernel':
        return mod.fit(cov_type='kernel', kernel='bartlett', bandwidth=8, low_memory=time_fe)
    return mod.fit(cov_type='clustered', clusters=d[['fund_id']] if cov == 'fund' else None,
                   cluster_entity=False)


def summarise(res, pref):
    b = res.params[[f'{pref}_{n}' for n in GNAME]].values
    V = res.cov.loc[[f'{pref}_{n}' for n in GNAME], [f'{pref}_{n}' for n in GNAME]].values
    a = np.r_[0, NG[1:]]
    D = a @ b
    seD = np.sqrt(a @ V @ a)
    tot = NG @ b
    cum = np.cumsum(NG * b)
    return dict(b0=b[0], se0=np.sqrt(V[0, 0]), D=D, seD=seD, total=tot, seTot=np.sqrt(NG @ V @ NG),
                share_delayed=D / tot if tot != 0 else np.nan, cum=cum, b=b, se=np.sqrt(np.diag(V)))


results = {}
for label, tfe, cols in [('A_optionFE', False, UL + LL + CTRL),
                         ('B_option_weekFE', True, UL + LL + CTRL),
                         ('C_lead_placebo_optionFE', False, UL + LL + CTRL + ['XU_lead', 'XL_lead'])]:
    res = fit(S, cols, tfe)
    results[label] = res
    su, sl = summarise(res, 'XU'), summarise(res, 'XL')
    print(f'\n=== {label}  (N={res.nobs}, R2 within={res.rsquared_within:.3f}) Driscoll-Kraay SE')
    print(pd.DataFrame({'bU': su['b'], 'seU': su['se'], 'bL': sl['b'], 'seL': sl['se']}, index=GNAME).round(3).to_string())
    for nm, s_ in [('Unlisted', su), ('Listed', sl)]:
        print(f"{nm}: b0={s_['b0']:.3f} ({s_['se0']:.3f})  D={s_['D']:.3f} ({s_['seD']:.3f})  total={s_['total']:.3f} "
              f"({s_['seTot']:.3f})  share delayed={s_['share_delayed']:.2f}")
    if 'XU_lead' in cols:
        print('leads: XU_lead', round(res.params['XU_lead'], 3), '(', round(res.std_errors['XU_lead'], 3), ')',
              ' XL_lead', round(res.params['XL_lead'], 3), '(', round(res.std_errors['XL_lead'], 3), ')')

# fund-clustered SE for model A (few clusters: indicative)
resF = fit(S, UL + LL + CTRL, False, cov='fund')
suF = summarise(resF, 'XU')
print('\nModel A with fund-clustered SE (%d clusters): D^U =' % S.fund_id.nunique(), round(suF['D'], 3), '(', round(suF['seD'], 3), ')',
      ' b0U =', round(suF['b0'], 3), '(', round(suF['se0'], 3), ')')

# ------------------------------------------------------------------ option-level Dimson betas
# market news = option's own total exposure-weighted news; sum of lagged betas vs unlisted share
S['XT'] = S['XU'] + S['XL'] + S['XD'] + S['XO']
rows = []
# lags are built on each option's complete weekly calendar (w has one row per week) BEFORE the estimation rows
# are selected, so a lag is always the news of the calendar week t-k and never bridges weeks outside the sample
w['XT'] = w['XU'] + w['XL'] + w['XD'] + w['XO']
_gt = w.groupby('option_id')['XT']
for k in range(0, 14):
    w[f'XT_L{k}'] = _gt.shift(k)
for oid, d in w[w['in_sample'] & (w['week'] >= '2015-07-01') & w['option_id'].isin(S['option_id'].unique())].groupby('option_id'):
    d = d.sort_values('week').copy()
    X = pd.concat({f'L{k}': d[f'XT_L{k}'] for k in range(0, 5)}, axis=1)
    X['L5_13'] = sum(d[f'XT_L{k}'] for k in range(5, 14))
    Z = pd.concat([d['ret'], X], axis=1).dropna()
    if len(Z) < 104:
        continue
    import statsmodels.api as sm
    m = sm.OLS(Z['ret'], sm.add_constant(Z.drop(columns='ret'))).fit(cov_type='HAC', cov_kwds={'maxlags': 4})
    b = m.params
    rows.append(dict(option_id=oid, fund=d['fund_name'].iloc[0], option=d['option_name'].iloc[-1], weeks=len(Z),
                     w_unlisted=d['w_unlisted_core'].mean(), beta0=b['L0'],
                     beta_lag=b[['L1', 'L2', 'L3', 'L4']].sum() + 9 * b['L5_13'],
                     ac1=Z['ret'].autocorr(1), price_type=d['price_type'].iloc[-1], aum_k=AUM.get(oid, np.nan)))
O = pd.DataFrame(rows)
O['beta_sum'] = O['beta0'] + O['beta_lag']
import statsmodels.formula.api as smf
O['cs_wt'] = (O['aum_k'] / O['aum_k'].mean()) if WEIGHT == 'aum' else 1.0
O = O[O['cs_wt'] > 0].copy()
_cl = dict(cov_type='cluster', cov_kwds={'groups': pd.factorize(O['fund'])[0]})
cs = smf.wls('beta_lag ~ w_unlisted', data=O, weights=O['cs_wt']).fit(**_cl)
cs0 = smf.wls('beta0 ~ w_unlisted', data=O, weights=O['cs_wt']).fit(**_cl)
ca = smf.wls('ac1 ~ w_unlisted', data=O, weights=O['cs_wt']).fit(**_cl)
print('\nOption-level (N=%d): beta_lag = %.3f + %.3f*w_unlisted (se %.3f); beta0 slope %.3f (se %.3f); AC1 slope %.3f (se %.3f)'
      % (len(O), cs.params['Intercept'], cs.params['w_unlisted'], cs.bse['w_unlisted'],
         cs0.params['w_unlisted'], cs0.bse['w_unlisted'], ca.params['w_unlisted'], ca.bse['w_unlisted']))

# save for the report
S.to_pickle(os.path.join(OUTD, 'S.pkl'))
O.to_csv(os.path.join(OUTD, 'option_dimson.csv'), index=False)
pd.to_pickle({k: (v.params, v.std_errors, v.cov, v.nobs, v.rsquared_within) for k, v in results.items()} |
             {'A_fundSE': (resF.params, resF.std_errors, resF.cov, resF.nobs, resF.rsquared_within)},
             os.path.join(OUTD, 'results.pkl'))
pd.to_pickle(dict(cs=(cs.params, cs.bse, cs.rsquared), cs0=(cs0.params, cs0.bse), ca=(ca.params, ca.bse)),
             os.path.join(OUTD, 'cs.pkl'))
