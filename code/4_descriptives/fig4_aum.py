"""Figure A4 with an AUM-weighted panel: mean strategic asset allocation of the sample options over time,
(a) equal-weighted (as in descriptive_stats.py) and (b) weighted by June 2026 member assets (aum_k).
Output: output/descriptives/fig4_mean_allocation_equal_vs_aum.png and fig4_mean_allocation_aum.png"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(R, 'output', 'descriptives')
S = pd.read_pickle(os.path.join(R, 'output', 'estimates', 'lag_model', 'equal', 'S.pkl'))
S['w_fic'] = S['w_FI'].fillna(0) + S['w_CASH'].fillna(0)
S['w_oth'] = (1 - S['w_listed_growth'].fillna(0) - S['w_unlisted_core'].fillna(0) - S['w_fic']).clip(lower=0)
COLS = ['w_listed_growth', 'w_unlisted_core', 'w_fic', 'w_oth']
LABELS = ['Listed growth (equity, property, infrastructure)', 'Unlisted (equity, property, infrastructure, credit)',
          'Fixed income and cash', 'Other and not specified']
GREYS = ['0.25', '0.55', '0.8', '0.95']

eq = S.groupby('saa_date')[COLS].mean() * 100
A = S.dropna(subset=['aum_k'])
aw = A.groupby('saa_date').apply(lambda d: pd.Series(np.average(d[COLS].fillna(0), axis=0, weights=d['aum_k']), index=COLS)) * 100

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],
                     'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '0.3',
                     'savefig.dpi': 300, 'savefig.bbox': 'tight'})

def panel(ax, q, title):
    ax.stackplot(q.index, q.T.values, colors=GREYS, edgecolor='white', lw=0.8, labels=LABELS)
    ax.set_ylim(0, 100); ax.set_ylabel('Mean strategic weight (%)')
    ax.set_title(title, fontsize=10, loc='left')

fig, axs = plt.subplots(1, 2, figsize=(12, 4.0), sharey=True)
panel(axs[0], eq, '(a) Equal-weighted')
panel(axs[1], aw, '(b) AUM-weighted (June 2026 member assets)')
axs[1].set_ylabel('')
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, loc='lower center', bbox_to_anchor=(0.5, -0.08), ncol=4, fontsize=8.5, frameon=False)
fig.savefig(os.path.join(OUT, 'fig4_mean_allocation_equal_vs_aum.png')); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 3.6))
panel(ax, aw, '')
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8.5)
fig.savefig(os.path.join(OUT, 'fig4_mean_allocation_aum.png')); plt.close(fig)

pd.concat({'equal_weighted': eq, 'aum_weighted': aw}, axis=1).round(2).to_csv(os.path.join(OUT, 'fig4_mean_allocation_equal_vs_aum.csv'))
for name, q in (('equal', eq), ('aum', aw)):
    print(name, 'first', q.index[0].date(), q.iloc[0].round(1).to_dict())
    print(name, 'last ', q.index[-1].date(), q.iloc[-1].round(1).to_dict())
    print(name, 'mean over quarters', q.mean().round(1).to_dict())
print('options with assets:', A.option_id.nunique(), 'of', S.option_id.nunique())
