import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'output', 'estimates', 'lag_model', os.environ.get('CASE', 'equal')))
import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from linearmodels.panel import PanelOLS
S=pd.read_pickle('S.pkl')
GN=['0','1','2-4','5-8','9-13','14-26']; NG=np.array([1,1,3,4,5,13])
UL=[f'XU_{n}' for n in GN]; LL=[f'XL_{n}' for n in GN]; CT=['XD_0','XD_1','XO_0','XO_1']
def run(df, lab):
    d=df.set_index(['option_id','week'])
    cols=[c for c in UL+LL+CT if d[c].abs().sum()>0]   # a fund may report no 'other' assets: drop all-zero controls
    r=PanelOLS(d['ret'],d[cols],entity_effects=True,drop_absorbed=True,weights=(d['wt'] if d['wt'].nunique()>1 else None)).fit(cov_type='kernel',kernel='bartlett',bandwidth=8)
    out={}
    for p in ['XU','XL']:
        b=r.params[[f'{p}_{n}' for n in GN]].values; V=r.cov.loc[[f'{p}_{n}' for n in GN],[f'{p}_{n}' for n in GN]].values
        a=np.r_[0,NG[1:]]; out[p+'_b0']=b[0]; out[p+'_D']=a@b; out[p+'_seD']=np.sqrt(a@V@a); out[p+'_tot']=NG@b
    out['N']=r.nobs; out['options']=df.option_id.nunique(); out['label']=lab; out['aum_bn']=df.groupby('option_id').aum_k.first().sum()/1e6
    return out
rows=[run(S,'Baseline')]
covid=(S.week>='2020-02-15')&(S.week<='2020-06-30')
rows.append(run(S[~covid],'Excl. Feb-Jun 2020'))
rows.append(run(S[S.price_type=='unit_price'],'Unit-price funds only'))
rows.append(run(S[S.price_type!='unit_price'],'Crediting-rate funds only'))
rows.append(run(S[S.week<'2020-01-01'],'2015-2019'))
rows.append(run(S[S.week>='2020-01-01'],'2020-2026'))
rows.append(run(S[S.is_mysuper_option==True],'MySuper options'))
rows.append(run(S[S.fund_name!='AustralianSuper'],'Excluding AustralianSuper'))
rows.append(run(S[S.option_id!='65714394898-ARSB'],'Without AustralianSuper Socially Aware'))
rows.append(run(S[S.fund_type_fixed!='Retail'],'Industry and public-sector funds'))
rows.append(run(S[S.fund_type_fixed=='Retail'],'Retail funds'))
if os.path.exists('tierA/S.pkl'):
    rows.append(run(pd.read_pickle('tierA/S.pkl'),'Tier A funds only (first estimation)'))
if os.path.exists('trusts/S.pkl'):
    rows.append(run(pd.read_pickle('trusts/S.pkl'),'Incl. platform funds priced from trust exit prices'))
if os.path.exists('wed/S.pkl'):
    rows.append(run(pd.read_pickle('wed/S.pkl'),'Wednesday proxy windows'))
R=pd.DataFrame(rows).set_index('label'); print(R.round(3).to_string())
F=[]
for f,d in S.groupby('fund_name'):
    if d.option_id.nunique()<3: continue
    try: o=run(d,f); F.append(o)
    except Exception as e: print(f,e)
F=pd.DataFrame(F).set_index('label'); F['mean_wU']=S.groupby('fund_name').w_unlisted_core.mean()
print(F[['options','N','mean_wU','XU_b0','XU_D','XU_seD','XU_tot','XL_b0','XL_D']].round(3).to_string())
R.to_csv('robust.csv'); F.to_csv('by_fund.csv')
