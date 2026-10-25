"""Asymmetric recognition: is market news relevant to unlisted assets recognised more slowly when it is negative
than when it is positive?

The weekly exposure-weighted news of each option is split into a positive and a negative part,
    X^{U+}_{i,t} = X^U_{i,t} 1[state_t = up],   X^{U-}_{i,t} = X^U_{i,t} 1[state_t = down]   (same for listed news X^L),
and the grouped distributed-lag model of code/3_lag_model/pilot_lag_model.py is estimated with separate lag
coefficients for each part. Speed is compared with the delayed share D/Total (scale-free), and listed news is the
placebo: (asymmetry in unlisted) - (asymmetry in listed).

States ('variants'):
  own    sign of the option's own news (X^U for unlisted news, X^L for listed news)        - main
  mkt    sign of the listed equity market over the same window (0.5 ASX 300 + 0.5 world ex-Australia)
  large  bottom 10% vs top 10% of weekly market returns (the middle 80% is a third, separate part)
Specifications: Model A (option fixed effects) for every variant; Model B (option and week fixed effects) and
'excluding February-June 2020' for the main variant. Equal weights and June-2026 AUM weights.

The panel is built by running the data-construction part of code/3_lag_model/pilot_lag_model.py, so the sample,
news variables and controls are exactly those of the main model.
Output: code/6_asymmetry/out/asym_results.pkl (read by report_asymmetry.py)
Run from anywhere:  python3 code/6_asymmetry/asymmetry_model.py
"""
import os
import warnings
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'output', 'estimates', 'asymmetry')
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ panel of the main model
os.environ.update(WEIGHT='equal', SAMPLE='main', PROXY_ALIGN='own', OUTSUB='')
MAIN = os.path.join(ROOT, 'code', '3_lag_model', 'pilot_lag_model.py')
src = open(MAIN).read()
src = src[:src.index('\n\ndef fit(')]
ns = {'__file__': MAIN, '__name__': 'panel'}
exec(compile(src, MAIN, 'exec'), ns)
w, S0 = ns['w'], ns['S']
GROUPS, GNAME, NG, CTRL = ns['GROUPS'], ns['GNAME'], ns['NG'], ns['CTRL']
K = GROUPS[-1][1]

mkt = 0.5 * w['eq_au'] + 0.5 * ns['eq_int']                 # listed equity market over the option's window
wk_mkt = mkt.groupby(w['week']).median()                       # one value per week for the decile cut-offs
wk_in = wk_mkt[wk_mkt.index.isin(S0['week'].unique())]
P10, P90 = wk_in.quantile(0.10), wk_in.quantile(0.90)

STATES = {
    'own': {'XU': {'p': w['XU'] > 0, 'n': w['XU'] <= 0}, 'XL': {'p': w['XL'] > 0, 'n': w['XL'] <= 0}},
    'mkt': {v: {'p': mkt > 0, 'n': mkt <= 0} for v in ('XU', 'XL')},
    'large': {v: {'p': mkt >= P90, 'n': mkt <= P10, 'm': (mkt > P10) & (mkt < P90)} for v in ('XU', 'XL')},
}


def split_cols(var):
    """Add grouped-lag sums of each state part of XU and XL to w; return {(v, part): [column names]}."""
    out = {}
    for v, parts in STATES[var].items():
        for part, cond in parts.items():
            s = w[v] * cond.astype(float)                       # NaN news stays NaN
            gg = s.groupby(w['option_id'])
            lags = {k: gg.shift(k) for k in range(K + 1)}
            names = []
            for (a, b), nm in zip(GROUPS, GNAME):
                c = f'{v}{part}_{var}_{nm}'
                w[c] = sum(lags[k] for k in range(a, b + 1))
                names.append(c)
            out[(v, part)] = names
    return out


COLS = {var: split_cols(var) for var in STATES}


def sample(weight, excl_covid=False):
    S = S0.copy()
    if weight == 'aum':
        S = S[S['aum_k'] > 0].copy()
        S['wt'] = S['aum_k'] / S['aum_k'].mean()
    else:
        S['wt'] = 1.0
    if excl_covid:
        S = S[(S['week'] < '2020-02-01') | (S['week'] > '2020-06-30')]
    return S


def fit(S, cols, time_fe, weight):
    d = S.join(w[[c for c in cols if c not in S.columns]]).dropna(subset=cols).set_index(['option_id', 'week'])
    mod = PanelOLS(d['ret'], d[cols], entity_effects=True, time_effects=time_fe, drop_absorbed=True,
                   weights=d['wt'] if weight == 'aum' else None)
    r = mod.fit(cov_type='kernel', kernel='bartlett', bandwidth=8, low_memory=time_fe)
    return r, len(d), d.index.get_level_values(0).nunique()


A_D = np.r_[0, NG[1:]].astype(float)            # weights giving the delayed response D = sum_{k>=1} beta_k
GRID = [0, 1, 4, 8, 13, 26]


def lagidx(h):
    """weights on the group coefficients giving the cumulative response C(h) = sum_{k<=h} beta_k"""
    return np.array([max(0, min(b, h) - a + 1) for a, b in GROUPS], dtype=float)


def measures(b):
    D, T = A_D @ b, NG @ b
    m = dict(b0=b[0], D=D, T=T, share=D / T)
    for h in GRID:
        m[f'R{h}'] = (lagidx(h) @ b) / T
    return m


def delta(f, p, V):
    """value and delta-method standard error of a scalar function f of the parameter vector p"""
    v = f(p)
    g = np.zeros(len(p))
    for j in range(len(p)):
        e = np.zeros(len(p)); e[j] = 1e-6 * max(1.0, abs(p[j]))
        g[j] = (f(p + e) - f(p - e)) / (2 * e[j])
    return v, float(np.sqrt(g @ V @ g))


def analyse(res, cols_by_part, names):
    p, V = res.params[names].values, res.cov.loc[names, names].values
    ix = {key: [names.index(c) for c in cs] for key, cs in cols_by_part.items()}
    sel = lambda key: (lambda q: q[ix[key]])
    out = {'parts': {}, 'tests': {}}
    for key in cols_by_part:
        m = {}
        for k_ in ['b0', 'D', 'T', 'share'] + [f'R{h}' for h in GRID]:
            m[k_] = delta(lambda q, k_=k_, key=key: measures(sel(key)(q))[k_], p, V)
        m['b'] = sel(key)(p)
        out['parts'][key] = m
    for v in ('XU', 'XL'):
        dshare = lambda q, v=v: measures(sel((v, 'n'))(q))['share'] - measures(sel((v, 'p'))(q))['share']
        dD = lambda q, v=v: measures(sel((v, 'n'))(q))['D'] - measures(sel((v, 'p'))(q))['D']
        dR1 = lambda q, v=v: measures(sel((v, 'n'))(q))['R1'] - measures(sel((v, 'p'))(q))['R1']
        dR4 = lambda q, v=v: measures(sel((v, 'n'))(q))['R4'] - measures(sel((v, 'p'))(q))['R4']
        out['tests'][f'{v}_dshare'] = delta(dshare, p, V)
        out['tests'][f'{v}_dD'] = delta(dD, p, V)
        out['tests'][f'{v}_dR1'] = delta(dR1, p, V)
        out['tests'][f'{v}_dR4'] = delta(dR4, p, V)
        # joint Wald test: the same lag profile for positive and negative news
        R = np.zeros((len(GNAME), len(p)))
        for j in range(len(GNAME)):
            R[j, ix[(v, 'n')][j]] = 1; R[j, ix[(v, 'p')][j]] = -1
        rb = R @ p
        out['tests'][f'{v}_wald'] = float(rb @ np.linalg.solve(R @ V @ R.T, rb))
    did = lambda q: ((measures(sel(('XU', 'n'))(q))['share'] - measures(sel(('XU', 'p'))(q))['share'])
                     - (measures(sel(('XL', 'n'))(q))['share'] - measures(sel(('XL', 'p'))(q))['share']))
    out['tests']['did_share'] = delta(did, p, V)
    return out


CASES = [('own', 'A', False), ('own', 'B', False), ('own', 'A', True), ('mkt', 'A', False), ('large', 'A', False)]
RES = {'P10': P10, 'P90': P90, 'GRID': GRID, 'GNAME': GNAME, 'NG': NG}
for weight in ('equal', 'aum'):
    S = sample(weight)
    # pooled model (no split): must reproduce the main estimate
    r, n, no = fit(S, ns['UL'] + ns['LL'] + CTRL, False, weight)
    RES[(weight, 'pooled')] = dict(D=A_D @ r.params[ns['UL']].values, n=n, options=no)
    print(weight, 'pooled D^U =', round(RES[(weight, 'pooled')]['D'], 3), '| N', n, '| options', no, flush=True)
    for var, model, excl in CASES:
        Sx = sample(weight, excl)
        cbp = COLS[var]
        names = [c for key in cbp for c in cbp[key]]
        r, n, no = fit(Sx, names + CTRL, model == 'B', weight)
        a = analyse(r, cbp, names)
        # how much news falls in each state (estimation sample, same-week news)
        d = Sx.join(w[[cbp[(v, pt)][0] for (v, pt) in cbp]])
        cnt = {}
        for (v, pt), cs in cbp.items():
            nz = d[cs[0]].fillna(0) != 0
            cnt[(v, pt)] = dict(option_weeks=int(nz.sum()), weeks=int(d.loc[nz, 'week'].nunique()),
                                mean_news=float(d.loc[nz, cs[0]].mean()), sd_news=float(d.loc[nz, cs[0]].std()))
        a.update(n=n, options=no, counts=cnt, r2=float(r.rsquared_within))
        RES[(weight, var, model, excl)] = a
        t = a['tests']
        print(f"{weight:5s} {var:5s} {model} exclCOVID={excl}: dshare U {t['XU_dshare'][0]:+.3f} ({t['XU_dshare'][1]:.3f})"
              f"  L {t['XL_dshare'][0]:+.3f} ({t['XL_dshare'][1]:.3f})  DiD {t['did_share'][0]:+.3f} ({t['did_share'][1]:.3f})"
              f"  | share U+ {a['parts'][('XU','p')]['share'][0]:.2f} U- {a['parts'][('XU','n')]['share'][0]:.2f}"
              f"  T U+ {a['parts'][('XU','p')]['T'][0]:.2f} U- {a['parts'][('XU','n')]['T'][0]:.2f}", flush=True)
pd.to_pickle(RES, os.path.join(OUT, 'asym_results.pkl'))
print('saved', os.path.join(OUT, 'asym_results.pkl'))
