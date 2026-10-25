"""Convert raw fund unit-price / crediting-rate downloads (data/raw/unit_prices/) into the
standard format read by build_master.py: data/derived/unit_prices/<fund>.csv with columns
option_id, date, price, price_type.  Also fills data/derived/unit_price_mapping_template.csv
and writes data/derived/unit_price_coverage.csv.

Run:  python3 code/1_build/convert_unit_prices.py
"""
import os
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw', 'unit_prices')
OUT = os.path.join(ROOT, 'data', 'derived', 'unit_prices')
MAP = os.path.join(ROOT, 'data', 'derived', 'unit_price_mapping_template.csv')
DL_DATE = '2026-09-30'
TEAM_ABN = '16457520308'


def rd(f, **kw):
    return pd.read_csv(os.path.join(RAW, f), **kw)


def dmy(s):
    return pd.to_datetime(s, format='%d/%m/%Y')


def index_from_rates(dates, rates_pct):
    """Chain period returns (in %) into an index = 100 * prod(1 + r/100).
    The base value 100 is placed one day before the first period end."""
    s = pd.Series(np.asarray(rates_pct, float), index=pd.to_datetime(dates)).sort_index().dropna()
    if s.empty:
        return pd.Series(dtype=float)
    idx = 100 * (1 + s / 100).cumprod()
    base = pd.Series([100.0], index=[s.index[0] - pd.Timedelta(days=1)])
    return pd.concat([base, idx])


# ------------------------------------------------------------------ fund specs
# series: APRA option code (suffix after the ABN) -> key of the series in the raw file
SPECS = []


def add(fund, abn, file, price_type, basis, url, series, note=''):
    SPECS.append(dict(fund=fund, abn=abn, file=file, price_type=price_type, basis=basis,
                      url=url, series=series, note=note))


ART = 60905115063
add('ART', ART, 'ART_unit_prices_SOL.csv', 'unit_price',
    'Net of investment fees, costs and tax (Super Savings accumulation); sell price',
    'https://www.australianretirementtrust.com.au/investments/performance/unit-prices',
    {'BLF': 'BF', 'GRO': '11', 'CON': '35', 'RTF': '10', 'BLI': '13', 'HGI': '49',
     'SCB': '17', 'DVA': '48', 'DBI': '23'},
    'Website history capped at 10 years (from 2016-09-27).')
add('ART_QSuper', ART, 'ART_QSuper_unit_prices_accum.csv', 'unit_price',
    'Net of investment fees, costs and tax (QSuper accumulation)',
    'https://qsuper.qld.gov.au/investments/unit-prices',
    {'X6': 'lifetime6', 'X5': 'lifetime5', 'X4': 'lifetime4', 'X2': 'lifetime2',
     'X1': 'lifetime', 'X0': 'lifetime0', 'X8': 'lifetime8', 'X7': 'lifetime7',
     'X9': 'lifetime9', 'B1': 'balanced'},
    'QSuper Lifetime groups and Balanced Risk-Adjusted. Dates shifted back 2 business days '
    '(QSuper publishes with a 2-day lag); weekend rows before 2013 dropped.')
AW = 53226460365
add('Aware', AW, 'Aware_unit_prices_FUTURE_SAVER.csv', 'unit_price',
    'Net of investment fees, costs and tax (Future Saver accumulation)',
    'https://aware.com.au/member/investments/unit-prices',
    {'AWAREACCHGRO': 'High Growth', 'AWAREACCHGSC': 'High Growth Socially Conscious',
     'AWAREACCHGINDX': 'High Growth Indexed', 'AWAREACCGROW': 'Balanced',
     'VSACCSOCCN': 'Balanced Socially Conscious', 'AWAREACCBALINDX': 'Balanced Indexed',
     'AWAREACCBGRO': 'Conservative Balanced', 'VSACCCPSTB': 'Conservative',
     'AWAREACCCGRO': 'Defensive', 'AWAREACCBOND': 'Bonds'},
    'Website series from 2017 (First State Super Future Saver before the Dec 2020 VicSuper merger); '
    'VS-coded options may carry VicSuper history in APRA before that.')
HP = 68657495890
add('Hostplus', HP, 'Hostplus_super_unit_prices_current_options.csv', 'unit_price',
    'Net of investment fees, costs and tax (super accumulation)',
    'https://hostplus.com.au/members/our-performance/unit-prices',
    {c: c for c in ['HC00A', 'HC01A', 'HC02A', 'HC03A', 'HC04A', 'HC08A', 'HC20A', 'HC27A',
                    'HC32A', 'HC33A', 'HC34A', 'HC35A', 'HC36A', 'HC37A', 'HC38A', 'HC39A', 'HC40A']})
VS = 24496637884
vs_super = {'VTBGTO': 'Balanced growth', 'VTBGNO': 'Balanced growth', 'VTBCTO': 'Balanced',
            'VTBCNO': 'Balanced', 'VTFPTO': 'Conservative', 'VTFPNO': 'Conservative',
            'VTSPTO': 'Growth', 'VTSPNO': 'Growth', 'VTIBIO': 'Balanced low cost',
            'VTIBNO': 'Balanced low cost', 'VTJUTO': 'Just shares'}
vs_map = {k: ('Vision Super', 'Premixed super' if v != 'Just shares' else 'Single sector super', v)
          for k, v in vs_super.items()}
# VTBCNO matches the untaxed pension Balanced series exactly (APRA quarterly returns), not the super series
vs_map['VTBCNO'] = ('Vision Super', 'Premixed pensions', 'Balanced')
vs_map.update({
    'ASMSLGBAC1': ('Active Super', 'Premixed super - Lifestage', 'Lifestage Appreciator'),
    'ASMSLGDIC1': ('Active Super', 'Premixed super - Lifestage', 'Lifestage Accumulator'),
    'ASMSLGHGC1': ('Active Super', 'Premixed super - Lifestage', 'Lifestage Accelerator'),
    'LGBAC1': ('Active Super', 'Premixed super - Choice', 'Conservative Balanced'),
    'LGDIC1': ('Active Super', 'Premixed super - Choice', 'Balanced'),
    'LGHGC1': ('Active Super', 'Premixed super - Choice', 'High Growth'),
    'LGCGC1': ('Active Super', 'Premixed super - Choice', 'Conservative')})
add('VisionSuper', VS, 'VisionSuper_unit_prices_all.csv', 'unit_price',
    'Net of tax, reserving margin, investment fees and costs (SUPER/NCAP accounts)',
    'https://www.visionsuper.com.au/investment/performance/unit-prices', vs_map,
    'Two APRA codes (..TO/..NO) per Vision option with identical allocations; both mapped to the '
    'SUPER series, except VTBCNO which matches the PENSION (untaxed) Balanced series. Active Super options priced only from 2025-03-03 (merger).')
BR = 23053121564
add('BrighterSuper', BR, 'BrighterSuper_unit_prices_accum.csv', 'unit_price',
    'Net of investment fees, costs and tax; admin-fee basis changes 31 May 2024 for '
    'MySuper, Indexed Balanced, Secure, Aus Shares, Property, Fixed Interest, Cash',
    'https://www.brightersuper.com.au/investments/latest-performance/historical-daily-unit-prices',
    {'LG40C1': 'MS1', '40000202': 'OPTMMGROWTH', '40000204': 'OPTMMHIGROWTH',
     '40000222': 'OPTMMBAL', '40000225': 'OPTMMCONSERVE', 'ELINBX': 'IB', 'LG26C1': 'DF',
     'LG06C1': 'PR', 'LG09C1': 'FI', 'ENERCAPGU': 'CAPGRNT', 'ENERSRTRNU': 'SMOOTHRET'},
    'Energy Super multi-manager options (4000xxxx) monthly prices until mid-2023. '
    'LG26C1 (DEF_ACC) matched to Secure by allocation (63% FI, 21% cash).')
US = 91385943850
add('UniSuper', US, 'UniSuper_daily_cumulative_crediting_index.csv', 'cumulative_index',
    'Accumulation, after fund tax and investment costs, before account fees; interim daily crediting rates',
    'https://www.unisuper.com.au/investments/investment-performance',
    {'BalancedMySuper': 4, 'Conserv': 2, 'ConservBal': 3, 'Growth': 6, 'SBalanced': 5,
     'HighGrowth': 8, 'SHiGrowth': 7, 'ListedProp': 10},
    'Calendar-daily index built by the fund from interim crediting rates.')
EQ = 33813823017
add('Equip', EQ, 'Equip_unit_prices_all.csv', 'unit_price',
    'Net of investment fees, costs and tax (Accumulation/TTR); mid price',
    'https://www.equipsuper.com.au/your-investments/unit-prices',
    {'1110': 'MySuper', '1040': 'Capital Stable', '1010': 'Balanced', '1070': 'Growth Plus',
     '1060': 'Growth', '1200': 'Index Diversified', '1020': 'Balanced Growth',
     '1050': 'Diversified Fixed Interest'})
AS = 65714394898
add('AustralianSuper', AS, 'AustralianSuper_daily_crediting_rates_Super_2008_2026.csv', 'crediting_rate',
    'Daily crediting rates, net of investment fees, costs and tax (Super)',
    'https://www.australiansuper.com/why-choose-us/investment-performance',
    {'ARBA': 'Balanced', 'ARYO': 'Conservative Balanced', 'ARHG': 'High Growth', 'ARST': 'Stable',
     'ARDO': 'Indexed Diversified', 'ARSB': 'Socially Aware', 'ARDI': 'Diversified Fixed Interest'},
    'Rates in % to 4 decimals, chained into an index (base 100).')
CB = 75493363262
add('Cbus', CB, 'Cbus_crediting_rates_Super_2014_2026.csv', 'crediting_rate',
    'Crediting rates, net of investment fees, costs and tax (Super)',
    'https://www.cbussuper.com.au/super/my-investment-options/super-crediting-rates',
    {'0001': 'Growth (MySuper)', '0018': 'Growth (MySuper)', '0003': 'Conservative',
     '0019': 'Growth Plus', '0010': 'Conservative Growth', '0002': 'High Growth',
     '0020': 'Indexed Diversified', '0024': 'Diversified Fixed Interest', '0023': 'Property'},
    'Rates in % to 2 decimals only; weekly (Thu-Wed) to 2018-10-03, daily from 2018-10-04; '
    '0.00 before an option starts is treated as missing. 0018 shares the Growth (MySuper) series.')

# ------------------------------------------------------------------ Tier A, batch 2 (downloaded 30 Sep 2026)
RE = 62653671394
add('Rest', RE, 'Rest_unit_prices_super.csv', 'unit_price',
    'Net of investment fees, costs and tax (Rest Super accumulation); sell price',
    'https://rest.com.au/investments/unit-prices',
    {'RE7C': 'CoreStrategy', 'RB7C': 'Balanced', 'RJ7C': 'CapitalStable', 'RH7C': 'HighGrowth',
     'RV7C': 'SustainableGrowth', 'RJ7K': 'BalancedIndexed'},
    'API field validFromDate is 2 business days after valuation; dates shifted back 2 business days.')
HE = 64971749321
add('HESTA', HE, 'HESTA_historicaldata_super.csv', 'unit_price',
    'Net of investment fees, costs and tax (super); unit prices, back-cast before first published price with period returns',
    'https://www.hesta.com.au/members/investments/super-performance',
    {'HE46': ('Core Pool', 'Balanced Growth'), 'HE47': ('Shares Plus', 'High Growth'),
     'HE51': ('Conservative Pool', 'Conservative'), 'HE52': ('Eco Pool', 'Sustainable Growth'),
     'HEBN': ('Indexed Balanced Growth',), 'HE48': ('Property', 'Property and Infrastructure')},
    'Dated by Period End Date (valuation date). Weekly (Wed-Tue) periods to 20 Oct 2021, daily after. '
    'Old pool names spliced to new names (Core Pool -> Balanced Growth etc.).')
CS = 74559365913
add('CareSuper', CS, 'CareSuper_unit_prices_super_by_option.txt', 'unit_price',
    'Net of investment fees, costs and tax (super); Spirit Super history before 1 Nov 2024 spliced',
    'https://www.caresuper.com.au/members/investments/investment-performance/unit-prices',
    {'MTBLSO': ('Balanced-TB', 'Balanced-Superannuation'), 'MTGRSO': ('Growth-TG', 'Growth-Superannuation'),
     'MTMSIO': ('Conservative-Balanced-TM', 'Moderate-Superannuation'),
     'MTCNSO': ('Capital-Stable-TS', 'Conservative-Superannuation'),
     'MTSSIO': ('Sustainable-Balanced-TD', 'Sustainable-Superannuation'),
     'CSIOS2A': ('Alternative-Growth-TA', None)},
    'APRA RSE is the former Spirit Super (MTAA codes). Before 1 Nov 2024 the Spirit Super series '
    '(unit-price-history.xlsx) is used; from 1 Nov 2024 the CareSuper series, chained at the splice date. '
    'Dates corrected (see DATE_SHIFT): weekly labels to 21 Apr 2017 moved 4 business days later, daily '
    'dates 22 Apr 2017 - Mar 2021 moved 2 business days earlier.')
CSC1 = 65127917725
add('CSC_PSSap', CSC1, 'CSC_PSSap_ADFSuper_unit_prices.csv', 'unit_price',
    'Net of investment fees, costs and tax; sell price',
    'https://www.csc.gov.au/Members/Investment/Performance/Historical-unit-price-and-earning-rates/pssap/',
    {'OPT06': ('PSSap', 'MySuper Balanced (default)'), 'OPT07': ('PSSap', 'Balanced (Ancillary Members)'),
     'OPT08': ('PSSap', 'Aggressive'), 'OPT09': ('PSSap', 'Income Focused')})
CSC2 = 90302247344
add('CSC_ADFSuper', CSC2, 'CSC_PSSap_ADFSuper_unit_prices.csv', 'unit_price',
    'Net of investment fees, costs and tax; sell price',
    'https://www.csc.gov.au/Members/Investment/Performance/Historical-unit-price-and-earning-rates/adf-super/',
    {'OPT43': ('ADFSuper', 'tab_2be0913e-27dc-4267-b306-2345b6acfc71'),
     'OPT44': ('ADFSuper', 'tab_e0e9e123-0005-4a84-af59-e6e4fc6277a8'),
     'OPT45': ('ADFSuper', 'tab_cbe3ec36-0cec-4c20-92a8-9c82a2d488d2')},
    'ADF Super tabs: 2be0913e = MySuper Balanced, e0e9e123 = Aggressive, cbe3ec36 = Income Focused.')
NG = 73549180515
add('NGS', NG, 'NGS_unit_prices_all.csv', 'unit_price',
    'Net of investment fees and tax (and of the asset-based admin fee before 1 Nov 2025)',
    'https://www.ngssuper.com.au/investments/unit-prices',
    {'MYSUPER': 'SDNA', 'NGSHIGRO': 'SDNM', 'NGSBAL': 'SDNN', 'NGSDEF': 'SDNB', 'NGSIGRW': 'SDN8'},
    'Accumulation codes SDNx from /api/chart/unitpricehistory. Fee basis change 1 Nov 2025 (admin fee no longer in price).')
BQ = 85571332201
add('BUSSQ', BQ, 'BUSSQ_unit_prices_powerbi.csv', 'unit_price',
    'Net of investment fees, costs and tax (Super/TTR)',
    'https://www.bussq.com.au/investments/investing-with-bussq/performance/unit-prices',
    {'BQBGRS': 'Balanced Growth'},
    'Power BI report; weekly (Wednesday) prices in early years. 30 June special statement prices dropped.')

# ------------------------------------------------------------------ Tier A, batch 3 (downloaded 30 Sep 2026)
RS = 76641658449
add('ReiSuper', RS, 'ReiSuper_unit_prices_super.csv', 'unit_price',
    'Weekly (Wednesday) sell prices, net of investment fees, costs and tax (super)',
    'https://www.reisuper.com.au/publications-and-forms/unit-prices',
    {'RFBALS': 'balanced', 'RFGRWS': 'growth', 'RFSTBS': 'stable', 'RFGRPS': 'growth_plus'},
    'Parsed from annual PDFs (code/utilities/parse_reisuper_pdfs.py); FY2025 OCR from scanned PDF; the FY2024 PDF '
    'stops at 24 Jan 2024, so Feb-Jun 2024 is missing. Weekly Wednesday prices plus month-end prices in FY2021-22.')
AM = 28342064803
add('AMIST', AM, 'AMIST_weekly_crediting_rates_super.csv', 'crediting_rate',
    'Weekly crediting rates (Wednesday-Tuesday), net of investment fees, costs and tax (super/TTR)',
    'https://www.ausfoodsuper.com.au/super-weekly-crediting-rates/',
    {'AMSTBAL': 'mysuperdefault', 'AMSTBAC': 'balanced', 'AMSTGRO': 'growth', 'AMSTSTA': 'capitalstable'},
    'AMIST Super is now Australian Food Super. Rates in % to 2 decimals, chained into an index dated at the '
    'period end (Tuesday), so weekly returns run Wednesday-Tuesday, one day earlier than the Wednesday proxies.')
LS = 60346078879
add('legalsuper', LS, 'legalsuper_unit_prices_super.csv', 'unit_price',
    'Daily sell prices, net of tax and fees except the weekly $0.99 administration fee (super)',
    'https://www.legalsuper.com.au/investments/performance/accumulation',
    {'LEGLMYA': 'MySuper Balanced', 'LEGLAGU': 'High Growth', 'LEGLARU': 'Growth',
     'LEGLBAU': 'Conservative Balanced', 'LEGLCOU': 'Conservative', 'LEGLMOU': 'Balanced'},
    'CSV from /api/InvestmentReturn/download-performance-data-csv (from 1 Jul 2016).')

# ------------------------------------------------------------------ retail funds (downloaded 30 Sep 2026)
MLCS = 70732426024
_mlc = {'AP7': 'MLC Aggressive', 'BP4': 'MLC Balanced', 'CBL': 'MLC Conservative Balanced',
        'GP5': 'MLC Growth', 'IPB': 'MLC Low Cost Balanced', 'IPC': 'MLC Low Cost Conservative Balanced',
        'IPG': 'MLC Low Cost Growth', 'SP6': 'MLC High Growth', 'SRG': 'MLC Socially Responsible Growth',
        'STA': 'MLC Stable'}
mlc_map = {f'MKBSS{k}': ('MasterKey Business Super', v) for k, v in _mlc.items()}
mlc_map.update({f'MKSFS{k}': ('MasterKey Super Fundamentals', v) for k, v in _mlc.items()})
mlc_map.update({'MYSU55': ('MasterKey Business Super', 'MySuper Growth Portfolio'),
                'MYS65O': ('MasterKey Business Super', 'MySuper Conservative Balanced Portfolio')})
add('MLC', MLCS, 'MLC_MasterKey_unit_prices.csv', 'unit_price',
    'Net of investment fees, costs and tax (MasterKey super); mid of the two published prices',
    'https://www.mlc.com.au/masterkeyWeb/execute/FramesetUnitPrices', mlc_map,
    'MasterKey Business Super (MKBSS) and Super Fundamentals (MKSFS) multi-sector options, calendar-daily. '
    'MySuper lifecycle: Under 55 = MySuper Growth Portfolio, 65 and over = MySuper Conservative Balanced '
    'Portfolio (ages 55-64 are blends without their own price).')
CFS = 26458298557
cfs_codes = ['AIL0309AU', 'AIL0844AU', 'AIL1420AU', 'AIL1577AU', 'AIL1822AU', 'AIL1887AU', 'AIL2165AU',
             'AIL2179AU', 'AIL2263AU', 'AIL2410AU', 'AIL2475AU', 'AIL2671AU', 'AIL2910AU', 'AIL3112AU',
             'AIL3408AU', 'AIL3499AU', 'AIL3674AU', 'AIL4280AU', 'AIL4383AU', 'AIL4388AU', 'AIL5660AU',
             'AIL5950AU', 'AIL6728AU', 'AIL7032AU', 'AIL7120AU', 'AIL7749AU', 'AIL9999AU', 'FSF0598AU',
             'FSF0599AU', 'FSF0605AU', 'FSF0606AU', 'FSF0607AU', 'FSF0613AU', 'FSF0614AU', 'FSF0632AU',
             'FSF0633AU', 'FSF0634AU', 'FSF0637AU', 'FSF0639AU', 'FSF0836AU', 'FSF0956AU', 'FSF1041AU',
             'FSF1333AU', 'FSF1334AU', 'FSF1335AU', 'FSF1336AU', 'FSF1337AU', 'FSF1338AU', 'FSF1345AU',
             'FSF1346AU', 'FSF1347AU', 'FSF1379AU', 'FSF1380AU', 'FSF1381AU', 'FSF1382AU', 'FSF1383AU',
             'FSF1384AU', 'FSF1385AU', 'FSF1386AU', 'FSF1387AU', 'FSF1388AU', 'FSF1389AU', 'FSF1617AU',
             'FSF1703AU', 'FSF1704AU', 'FSF1733AU', 'FSF1734AU', 'FSF1783AU', 'FSF1823AU', 'FSF1824AU',
             'FSF1825AU', 'FSF2329AU', 'FSF2964AU', 'FSF3348AU', 'FSF3368AU', 'FSF4073AU', 'FSF4191AU',
             'FSF5102AU', 'FSF5132AU', 'FSF8505AU', 'FSF9318AU']
add('CFS', CFS, 'CFS_FirstChoice_unit_prices.csv', 'unit_price',
    'Net of investment fees, costs and tax (FirstChoice super); exit price',
    'https://www.colonialfirststate.com.au/Price_Performance/', {c: c for c in cfs_codes},
    'APRA option codes are the APIR codes; history from the CFS price download (from 2010).')
MER = 19905422981
mer_map = {'CSDHG': 'HIGH_GROW', 'CSDSG': 'SELCT_GROW', 'CSDDG': 'GROWTH', 'CSDFF': 'MOD_GROW',
           'CSDCS': 'STABLE', 'CSDSRCG': 'SR_CGROW', 'CSDSRHG': 'SR_HGROW', 'ICSIPP': 'IND_STAB',
           'IDGIPP': 'IND_GROW', 'CSDFS': 'FAIRFAX', 'CSDMMSBG': 'MGSP_MSBG', 'SP190029': 'SP190028'}
mer_map.update({c: c for c in ['SP192933', 'SP193438', 'SP193943', 'SP194448', 'SP194953', 'SP195458',
                               'SP195963', 'SP196468', 'SP196973', 'SP197478', 'SP197983', 'SP198488',
                               'SP198993', 'SP199498', 'SP199903', 'SP200408', 'SP200913', 'SP201418']})
add('Mercer', MER, 'Mercer_CSD_unit_prices_weekly.csv', 'unit_price',
    'Net of investment fees, costs and tax (Corporate Super Division); exit price',
    'https://www.mercersuper.com.au/investments/unit-prices/', mer_map,
    'Public API queried for every Wednesday from 5 Jul 2017; dated by the effective date the API returns. '
    'Lutheran (CSDLMSBG) and Virgin (RD*) options are not published.')
ES = 56601925435
es_map = {'FSF1370AU': '33-31', 'FSF1372AU': '33-1', 'FSF1373AU': '33-2', 'FSF1374AU': '33-3',
          'FSF1375AU': '33-4', 'FSF1376AU': '33-5', 'FSF1377AU': '33-6', 'FSF1931AU': '33-53',
          'FSF2935AU': '33-8', 'FSF5146AU': '33-56', 'FSF6523AU': '33-55', 'FSF7626AU': '33-54',
          'FSF8112AU': '33-52', 'FSF9814AU': '33-7', 'AIL2388AU': '33-35', 'AIL4820AU': '33-33',
          'AIL5931AU': '33-34'}
add('EssentialSuper', ES, 'EssentialSuper_unit_prices.csv', 'unit_price',
    'Net of investment fees, costs and tax (Essential Super); exit price',
    'https://super.commbank.com.au/Public/UnitPrices.aspx', es_map,
    'CSV from the Historical page (from May 2013). Options matched to APRA codes by name.')
# Platform (wrap) super funds whose options are unit trusts: trust exit prices from the IOOF price API.
IO = 70815369818
io_map = {c: c for c in ['IOF0090AU', 'IOF0093AU', 'IOF0094AU', 'IOF0095AU', 'IOF0097AU', 'IOF0232AU',
                         'IOF0253AU', 'IOF0254AU', 'IOF0255AU', 'MLC0260AU', 'MLC0265AU', 'MLC0397AU',
                         'MLC0398AU', 'MLC0449AU', 'MLC0670AU', 'MLC7387AU', 'MLC7849AU', 'MLC9748AU',
                         'UFM0051AU']}
io_map['70815369818036'] = 'IOF0232AU'
TRUST_BASIS = 'Unit trust exit price, net of management costs; distributions added back (see note); tax at member level'
TRUST_URL = 'https://www.ioof.com.au/performance/unit-prices'
TRUST_NOTE = ('Platform option = unit trust; exit price from the IOOF unit-price API. Trust prices fall on '
              'ex-distribution dates: in the first 8 days of Jan/Apr/Jul/Oct, a daily return more than 0.6% below '
              'the median of all trusts in the file is treated as a distribution and replaced by that median.')
add('IOOF', IO, 'IOOF_MLC_trusts_unit_prices.csv', 'unit_price', TRUST_BASIS, TRUST_URL, io_map,
    TRUST_NOTE + ' 70815369818036 (IOOF Balanced Growth, MySuper) uses the IOF0232AU trust.')
RPS = 61808189263
add('RPS', RPS, 'IOOF_MLC_trusts_unit_prices.csv', 'unit_price', TRUST_BASIS, TRUST_URL,
    {c: c for c in ['IOF0090AU', 'IOF0093AU', 'IOF0097AU', 'IOF0253AU', 'IOF0254AU', 'IOF0255AU',
                    'MLC0397AU', 'MLC0449AU', 'UFM0051AU']},
    TRUST_NOTE + ' ANZ Smart Choice options (ASC*) have no public price history.')
OA = 81154851339
add('Oasis', OA, 'IOOF_MLC_trusts_unit_prices.csv', 'unit_price', TRUST_BASIS, TRUST_URL,
    {c: c for c in ['IOF0090AU', 'IOF0093AU', 'IOF0095AU', 'IOF0253AU', 'IOF0254AU', 'IOF0255AU',
                    'MLC0397AU', 'MLC0449AU', 'UFM0051AU']}, TRUST_NOTE)
AV = 82004832237
add('AvWrap', AV, 'IOOF_MLC_trusts_unit_prices.csv', 'unit_price', TRUST_BASIS, TRUST_URL,
    {'HUB' + c: c for c in ['IOF0090AU', 'IOF0093AU', 'IOF0097AU', 'IOF0253AU', 'IOF0254AU', 'IOF0255AU',
                            'MLC0265AU']}, TRUST_NOTE)
BE = 57526653420
be_map = {c + 'BSP': c for c in ['STL0012AU', 'STL0013AU', 'STL0029AU', 'STL0031AU', 'STL0032AU',
                                 'STL0033AU', 'STL0034AU', 'STL0035AU']}
be_map.update({'QUE0179AU': 'STL0033AU', 'QUE0180AU': 'STL0032AU', 'QUE0183AU': 'STL0034AU'})
add('Bendigo', BE, 'IOOF_MLC_trusts_unit_prices.csv', 'unit_price', TRUST_BASIS,
    'https://www.betashares.com.au/advisers/bendigo-funds/', be_map,
    TRUST_NOTE + ' Bendigo SmartStart MySuper options (QUE*) invest in the Balanced/Conservative/Growth Index '
    'funds and are proxied by those trusts (STL0033AU/STL0032AU/STL0034AU).')
FS = 68964712340
add('FutureSuper', FS, 'FutureSuper_unit_prices_accum.csv', 'unit_price',
    'Net of investment fees, costs and tax (Future Super accumulation); mid of buy and sell prices',
    'https://www.futuresuper.com.au/unit-prices',
    {'S-FS-MOD': 'M1', 'S-FS-GROW': 'M2', 'S-FS-BAL-GROW': 'M3', 'S-FS-HIGR': 'M4', 'S-FS-ALTGROW': 'M5',
     'S-FS-BAL': 'M6'},
    'Registry CSV (api.futuresuper.com.au/api/metrics/registry-unit-prices/<code>) starts 23 May 2025, when '
    'the options were re-based at 1.00; earlier history not published. smartMonday options (same RSE) '
    'publish monthly returns only.')
TRUST_FILE = 'IOOF_MLC_trusts_unit_prices.csv'


def trust_prices():
    """Distribution-adjusted trust price index for every APIR in the IOOF file."""
    if 'trusts' not in CACHE:
        d = rd(TRUST_FILE)
        d['date'] = pd.to_datetime(d['date'], format='%d %b %Y')
        p = d.pivot_table(index='date', columns='apir', values='exit').sort_index()
        # each trust's return between its own consecutive prices
        r = pd.DataFrame({c: np.log(p[c].dropna()).diff() for c in p.columns}).reindex(p.index)
        med = r.median(axis=1)
        ex = r.sub(med, axis=0)
        win = (r.index.month.isin([1, 4, 7, 10])) & (r.index.day <= 8)
        dist = ex.lt(-0.006) & np.repeat(win[:, None], r.shape[1], 1)
        r = r.mask(dist, pd.DataFrame(np.repeat(med.values[:, None], r.shape[1], 1), index=r.index,
                                      columns=r.columns))
        print('trust distribution days replaced:', int(dist.values.sum()))
        # rebuild levels from the first price of each trust
        lvl = {}
        for c in p.columns:
            s = p[c].dropna()
            rr = r[c].reindex(s.index).fillna(0)
            rr.iloc[0] = 0
            lvl[c] = s.iloc[0] * np.exp(rr.cumsum())
        CACHE['trusts'] = lvl
    return CACHE['trusts']

# business-day shift applied to a fund's dates (negative = move earlier); set after checking
DATE_SHIFT = {
    # Rest's API date (validFromDate) is 2 business days after the valuation date (all years; checked
    # against same-day ASX ETF returns: correlation 0.66 at +2, -0.03 at 0)
    'Rest': -2,
    # Spirit Super history: weekly Wednesday labels up to 21 Apr 2017 are the START of the pricing week -
    # the price reflects the valuation 4 business days later (weekly-return correlation with the market
    # 0.89-0.90 at +4 vs 0.13-0.22 as dated); daily prices from 22 Apr 2017 to Mar 2021 are dated 2 business
    # days late (Australian Shares correlates 0.87 with VAS at +2, -0.07 at 0); correct from April 2021
    'CareSuper': [('1900-01-01', '2017-04-22', 4), ('2017-04-22', '2021-04-01', -2)],
    # NGS weekly prices 2010-2020 are labelled Saturday and reflect Friday's valuation (weekly correlation
    # 0.93 at -1 vs 0.80 as dated); daily prices from 2021 are correctly dated
    'NGS': 'weekend_to_friday',
    # BUSSQ (Power BI): weekly Wednesday labels before April 2021 reflect the previous Friday's valuation
    # (weekly-return correlation with the market 0.84-0.90 at -3 business days vs 0.46-0.49 as dated).
    # Daily labels are 2 business days after valuation from April 2021 to 5 Aug 2024 and again from
    # 1 Oct 2025 (monthly correlation checks, e.g. 0.72-0.83 at -2 vs about 0 as dated); correctly dated
    # 7 Aug 2024 to 26 Sep 2025 (the 6 Aug 2024 price spans the switch and is left as dated).
    'BUSSQ': [('1900-01-01', '2021-04-01', -3), ('2021-04-01', '2024-08-06', -2),
              ('2025-10-01', '2100-01-01', -2)],
}

CACHE = {}


def load(f, **kw):
    if f not in CACHE:
        CACHE[f] = rd(f, **kw)
    return CACHE[f]


def series_for(spec, key):
    f, fund = spec['file'], spec['fund']
    if fund == 'ART':
        d = load(f, dtype={'fund_code': str}, parse_dates=['date'])
        return d[d.fund_code == key].set_index('date')['sell_price']
    if fund == 'ART_QSuper':
        # QSuper's published dates run 2 business days after the valuation date (checked against the
        # same option in ART's Super Savings file and against APRA quarterly returns), so shift back.
        d = load(f, parse_dates=['date'])
        x = d[(d.option_code == key) & (d.date.dt.dayofweek < 5)]
        return pd.Series(x['unit_price'].values, index=x['date'] - BDay(2))
    if fund == 'Aware':
        d = load(f)
        return pd.Series(d[key].values, index=dmy(d['Date']))
    if fund == 'Hostplus':
        d = load(f, parse_dates=['date'])
        return d[d.option_code == key].set_index('date')['unit_price']
    if fund == 'VisionSuper':
        d = load(f, parse_dates=['date'])
        g, t, n = key
        x = d[(d.group == g) & (d.option_type == t) & (d.option_name == n)]
        return x.set_index('date')['buy_price']
    if fund == 'BrighterSuper':
        d = load(f, parse_dates=['date'])
        return d[d.option_code == key].set_index('date')['unit_price']
    if fund == 'UniSuper':
        d = load(f, parse_dates=['date'])
        x = d[(d.option_id_site == key) & (d.basis == 'accumulation_after_tax')]
        return x.set_index('date')['cum_index'] * 100
    if fund == 'Equip':
        d = load(f)
        x = d[(d['Option Type'] == 'Accumulation/TTR') & (d['Option Name'] == key)]
        return pd.Series(x['Mid Price'].values, index=dmy(x['Date']))
    if fund == 'AustralianSuper':
        d = load(f, parse_dates=['Rate Date'])
        return index_from_rates(d['Rate Date'], d[key])
    if fund == 'Cbus':
        d = load(f, parse_dates=['period_start', 'period_end']).sort_values('period_start')
        nz = d.loc[d[key].fillna(0) != 0, 'period_start']
        x = d[d.period_start >= nz.min()]
        return index_from_rates(x['period_end'], x[key])
    if fund == 'Rest':
        d = load(f, parse_dates=['date'])
        return d[d.option_code == key].set_index('date')['sell']
    if fund == 'HESTA':
        d = load(f)
        d = d.assign(end=pd.to_datetime(d['Period End Date'], format='%d/%m/%Y'))
        x = d[d['Investment Option'].isin(key)].sort_values('end').drop_duplicates('end', keep='last')
        r = pd.to_numeric(x['Result'], errors='coerce').values / 100
        up = pd.to_numeric(x['Unit Price'], errors='coerce').values
        idx = x['end'].values
        # back-cast before the first published unit price using the period returns
        first = np.where(~np.isnan(up))[0]
        if len(first) == 0:
            return index_from_rates(idx, r * 100)
        p = up.copy(); i0 = first[0]
        for i in range(i0 - 1, -1, -1):
            p[i] = p[i + 1] / (1 + r[i + 1])
        return pd.Series(p, index=pd.to_datetime(idx))
    if fund == 'CareSuper':
        if 'CareSuper_parsed' not in CACHE:
            parts, cur = {}, None
            for line in open(os.path.join(RAW, f)).read().splitlines():
                if line.startswith('# '):
                    cur = line[2:].split('-2026')[0].replace('Superannuation-', ''); parts[cur] = []
                elif line and not line.startswith('SellPrice'):
                    a = line.split(',')
                    parts[cur].append((a[1], float(a[0])))
            CACHE['CareSuper_parsed'] = {k: pd.Series([v for _, v in l], index=pd.to_datetime([d for d, _ in l]))
                                         for k, l in parts.items()}
            sp = pd.read_excel(os.path.join(RAW, 'CareSuper_SpiritSuper_unit_price_history_pre_Nov2024.xlsx'))
            CACHE['Spirit'] = sp.set_index(pd.to_datetime(sp['PriceDate'])).drop(columns='PriceDate')
        cur_key, sp_key = key
        new = CACHE['CareSuper_parsed'][cur_key].sort_index()
        new = new[new.index >= '2024-11-01']
        if sp_key is None:
            return new
        old = pd.to_numeric(CACHE['Spirit'][sp_key], errors='coerce').dropna().sort_index()
        old = old[old.index < '2024-11-01']
        if new.empty or old.empty:
            return pd.concat([old, new])
        # chain: scale the new series so that its first value continues the old series' last return
        return pd.concat([old, new * old.iloc[-1] / new.iloc[0]])
    if fund in ('CSC_PSSap', 'CSC_ADFSuper'):
        d = load(f, parse_dates=['date'])
        prod, nm = key
        return d[(d['product'] == prod) & (d['option_name'] == nm)].set_index('date')['sell']
    if fund == 'NGS':
        d = load(f, parse_dates=['date'])
        return d[d.code == key].set_index('date')['unit_price']
    if fund == 'BUSSQ':
        d = load(f, parse_dates=['date'])
        x = d[(d.product_type == 'Super / TTR') & (d.option_name == key)]
        x = x[~((x.date.dt.month == 6) & (x.date.dt.day == 30) & (x.date.dt.dayofweek != 2))]
        return x.set_index('date')['unit_price']
    if fund == 'ReiSuper':
        d = load(f, parse_dates=['date'])
        return d[d.option == key].set_index('date')['price']
    if fund == 'AMIST':
        d = load(f, parse_dates=['period_end'])
        d = d.assign(opt=d['option'].str.replace(r'[^A-Za-z]', '', regex=True).str.lower())
        x = d[d.opt == key].sort_values('period_end').drop_duplicates('period_end', keep='first')
        # the website has occasional typos such as '0..01'
        r = pd.to_numeric(x['rate_pct'].astype(str).str.replace('..', '.', regex=False)
                          .str.replace('\u2212', '-', regex=False), errors='coerce')
        return index_from_rates(x['period_end'], r)
    if fund == 'FutureSuper':
        d = load(f)
        x = d[d['Investment Option Id'] == key]
        return pd.Series(((x['Buy Price'] + x['Sell Price']) / 2).values,
                         index=pd.to_datetime(x['Effective Date']))
    if fund == 'MLC':
        d = load(f, parse_dates=['date'])
        prod, nm = key
        x = d[(d['product'] == prod) & (d['fund'] == nm)]
        return pd.Series(((x['buy'] + x['sell']) / 2).values, index=x['date'])
    if fund == 'CFS':
        d = load(f, parse_dates=['date'])
        return d[d.apir == key].set_index('date')['exit']
    if fund == 'Mercer':
        d = load(f, parse_dates=['effective_date'])
        return d[d.code == key].drop_duplicates('effective_date').set_index('effective_date')['exit']
    if fund == 'EssentialSuper':
        d = load(f)
        x = d[d.fund_code == key]
        return pd.Series(x['exit'].values, index=dmy(x['date']))
    if fund in ('IOOF', 'RPS', 'Oasis', 'AvWrap', 'Bendigo'):
        return trust_prices()[key]
    if fund == 'legalsuper':
        d = load(f, skiprows=3)
        return pd.Series(pd.to_numeric(d[f'{key} (Sell Price)'], errors='coerce').values, index=dmy(d['Date']))
    raise ValueError(fund)


def main():
    os.makedirs(OUT, exist_ok=True)
    mp = pd.read_csv(MAP, dtype=str)
    for c in ['price_file', 'price_series_name', 'price_type', 'source_url', 'download_date',
              'fee_tax_basis', 'first_price_date', 'notes']:
        mp[c] = mp[c].astype(object)
    cov, per_fund = [], {}
    for spec in SPECS:
        if not os.path.exists(os.path.join(RAW, spec['file'])):
            print('missing raw file, skipped:', spec['file'])
            continue
        for code, key in spec['series'].items():
            oid = f"{spec['abn']}-{code}"
            s = pd.to_numeric(series_for(spec, key), errors='coerce')
            sh = DATE_SHIFT.get(spec['fund'])
            if isinstance(sh, int):
                s.index = s.index + BDay(sh)
            elif isinstance(sh, tuple):
                cut, k = pd.Timestamp(sh[0]), sh[1]
                s.index = pd.DatetimeIndex([d + BDay(k) if d < cut else d for d in s.index])
            elif sh == 'weekend_to_friday':
                s.index = pd.DatetimeIndex([d - BDay(1) if d.dayofweek >= 5 else d for d in s.index])
            elif isinstance(sh, list):
                segs = [(pd.Timestamp(a), pd.Timestamp(b), k) for a, b, k in sh]
                s.index = pd.DatetimeIndex([next((d + BDay(k) for a, b, k in segs if a <= d < b), d)
                                            for d in s.index])
            s = s[s > 0].dropna()
            s = s[~s.index.duplicated(keep='last')].sort_index()
            if s.empty:
                print('EMPTY', oid, key)
                continue
            per_fund.setdefault(spec['fund'], []).append(pd.DataFrame(
                {'option_id': oid, 'date': s.index.strftime('%Y-%m-%d'),
                 'price': s.values.round(8), 'price_type': spec['price_type']}))
            gaps = s.index.to_series().diff().dt.days
            cov.append(dict(fund=spec['fund'], option_id=oid, series=str(key), n=len(s),
                            first=s.index.min().date(), last=s.index.max().date(),
                            max_gap_days=int(gaps.max()) if len(s) > 1 else None,
                            in_apra=oid in set(mp.option_id)))
            row = mp.option_id == oid
            if row.any():
                mp.loc[row, 'price_file'] = f"unit_prices/{spec['fund']}.csv (raw: {spec['file']})"
                mp.loc[row, 'price_series_name'] = str(key)
                mp.loc[row, 'price_type'] = spec['price_type']
                mp.loc[row, 'source_url'] = spec['url']
                mp.loc[row, 'download_date'] = DL_DATE
                mp.loc[row, 'fee_tax_basis'] = spec['basis']
                mp.loc[row, 'first_price_date'] = str(s.index.min().date())
                mp.loc[row, 'notes'] = spec['note']
    for fund, parts in per_fund.items():
        pd.concat(parts).to_csv(os.path.join(OUT, f'{fund}.csv'), index=False)

    pilot_abns = {str(s['abn']) for s in SPECS} | {TEAM_ABN}
    nop = mp.abn.isin(pilot_abns) & mp.price_file.isna()
    mp.loc[nop & (mp.abn == TEAM_ABN), 'notes'] = (
        'Team Super publishes only the latest week of unit prices; history to be requested from the fund.')
    life = nop & (mp.is_lifecycle == 'True') & (mp.abn != TEAM_ABN)
    mp.loc[life, 'notes'] = (
        'Lifecycle stage without its own published price (members hold units in the underlying '
        'options/pools). In quarters where its allocation is identical to a priced option, that option '
        'represents the allocation group (is_group_rep_priced in master_weekly).')
    mp.to_csv(MAP, index=False)

    cv = pd.DataFrame(cov)
    cv.to_csv(os.path.join(ROOT, 'data', 'derived', 'unit_price_coverage.csv'), index=False)
    print(cv.groupby('fund').agg(options=('option_id', 'size'), first=('first', 'min'),
                                 in_apra=('in_apra', 'sum')).to_string())
    print('not in APRA:', cv.loc[~cv.in_apra, 'option_id'].tolist())
    print('mapped rows in template:', int(mp.price_file.notna().sum()))


if __name__ == '__main__':
    main()
