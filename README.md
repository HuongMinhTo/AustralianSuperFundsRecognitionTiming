# The Timing of Market Information Recognition in Australian Superannuation Unit Prices

PhD Topic 3 · Minh Huong To · Deakin University · folder structure revised 11 October 2026

This folder holds the data, code and outputs for the study. Its layout follows the conventions of finance and economics replication packages (AEA Data Editor template; Journal of Finance code-sharing policy): raw data are kept unchanged, every derived dataset and result is produced by code, and one script runs the whole analysis in order.

The GitHub repository (github.com/HuongMinhTo/AustralianSuperFundsRecognitionTiming) holds the code and documentation only. The data and outputs are not shared, because the fund-website and Bloomberg terms do not allow redistribution; the APRA files can be downloaded from apra.gov.au.

## Folder structure

```
PhD_Topic3_Data/
├── README.md             this file
├── code/                 all scripts, one folder per stage
│   ├── run_all.sh        runs the full analysis in order
│   ├── 1_build/          raw data -> analysis datasets
│   ├── 2_data_checks/    coverage, outliers, date alignment, data summary
│   ├── 3_lag_model/      distributed-lag model (equal- and AUM-weighted), robustness, report
│   ├── 4_descriptives/   returns, proxies and news variables of the estimation sample
│   ├── 5_sample_checks/  sample against APRA totals
│   ├── 6_asymmetry/      positive vs negative news
│   └── utilities/        one-off data-collection helpers (not part of the pipeline)
├── data/
│   ├── raw/              original downloads, never edited: apra/, unit_prices/, bloomberg/
│   └── derived/          datasets built by code/1_build (variables in data/derived/README.md)
├── output/               everything produced by the code
│   ├── estimates/        model objects (.pkl) and option-level estimates
│   ├── logs/             run logs
│   ├── lag_model/        main results: Word report, Excel tables, figures
│   ├── descriptives/     descriptive statistics and figures (incl. Figure A4)
│   ├── data_summary/     summary of APRA allocations
│   ├── sample_checks/    sample AUM and reconciliation with APRA files
│   ├── asymmetry/        asymmetric recognition results
│   └── hypothesis_tests/ hypothesis-test summary used in the proposal (computed from output/estimates, not by run_all.sh)
├── proposal/             research proposal, current version only (v5 tracked and clean)
├── docs/                 data report: data used, data missing, Bloomberg list, strengths and limitations
├── literature/           key papers
└── _old/                 superseded files, kept for the record (see _old/README.md)
```

## Rules for this folder

1. `data/raw/` is read-only. New downloads are added there and logged in `data/raw/unit_prices/download_log.csv`.
2. Nothing in `data/derived/` or `output/` is edited by hand; it is rebuilt by the code. The one exception is `output/hypothesis_tests/`.
3. Scripts use paths relative to the project folder, so they run from any folder and on any computer.
4. Only the current version of each document stays in its folder. Earlier versions go to `_old/`; nothing is deleted.

## Data sources

| Data | Location | Source and access | Licence |
| --- | --- | --- | --- |
| APRA Quarterly Superannuation Product Statistics, June 2026 (Historical SAA, Historical performance, Product Structure, Performance) | `data/raw/apra/` | apra.gov.au, public; downloaded 28 Sep 2026 | CC BY 4.0 |
| APRA Quarterly Superannuation Fund Statistics June 2026; Annual fund-level statistics back series 2004-2025; Quarterly MySuper statistics | `data/raw/apra/` | apra.gov.au, public; downloaded 28 Sep 2026 | CC BY 4.0 |
| Fund universe, June 2026 | `data/raw/apra/fund_universe_june2026.csv` | Compiled from APRA lists | - |
| Unit prices and crediting rates by fund | `data/raw/unit_prices/` | Public fund websites, downloaded 28-30 Sep 2026; source, coverage and caveats for each file in `download_log.csv` | Fund website terms; not for redistribution |
| Market index and ASX-listed ETF prices (daily closes, PX_LAST) | `data/raw/bloomberg/` | Bloomberg Terminal, downloaded 20-22 Oct 2026; combined into `data/derived/bloomberg_daily.csv` by `code/9_bloomberg/build_bloomberg_daily.py`; series list in `docs/Bloomberg_data_collection_list.docx` | Bloomberg terms; not for redistribution |

Some raw files are kept but not used by the code (for example closed or discontinued options, the short Prime Super history, the APRA MySuper statistics). They are documented in `download_log.csv` and may be useful later, for example for survivorship checks.

## Computational requirements

- Python 3 with pandas, numpy, statsmodels, linearmodels, matplotlib (version below 3.10, because `code/4_descriptives/descriptive_stats.py` uses `boxplot(labels=...)`), openpyxl and python-docx.
- pandoc, used to write equations into the Word reports.
- Last full test on 11 October 2026: Python 3.13, pandas 3.0, numpy 2.5, statsmodels 0.15, linearmodels 7.0, matplotlib 3.9, pandoc 3.1. The results reproduced the stored estimates to within 1e-11.
- Run time on a standard computer is about 20 minutes: stages 1-2 about 4 minutes, stage 3 about 13 minutes, stages 4-6 about 2 minutes. `output/estimates/` needs about 600 MB of disk space.

## How to run

From a terminal, in any folder:

```
bash code/run_all.sh            # every stage, 1 to 6
bash code/run_all.sh 3 4        # selected stages only
```

Each stage needs the outputs of the stages before it. Stages 4 to 6 need `output/estimates/lag_model/` from stage 3.

## Scripts and outputs

| Stage | Scripts (in `code/`) | What they do | Main outputs |
| --- | --- | --- | --- |
| 1 Build | `1_build/build_master.py` (saa, fund, perf, merge, weekly); `1_build/convert_unit_prices.py`; `1_build/build_option_aum.py` | Strategic allocations, fund-year variables, APRA returns, option-quarter master; standardised unit prices; weekly panel with start-of-quarter weights; June 2026 member assets (AUM weights) | `data/derived/` |
| 2 Data checks | `2_data_checks/check_unit_prices.py`, `check_date_alignment.py`, `check_weekly_alignment.py`, `make_master_xlsx.py`, `summarise_master.py` | Coverage, outliers, returns vs APRA, price-date alignment; Excel version of the master; allocation summary | `data/derived/unit_price_checks.xlsx`, `output/data_summary/` |
| 3 Lag model | `3_lag_model/run_lag_model.sh` runs `pilot_lag_model.py` (Models A-C, equal and AUM weights, robustness samples), `robust.py`, `report_weighting.py` | Distributed-lag model of weekly option returns on exposure-weighted listed and unlisted news | `output/estimates/lag_model/`, `output/lag_model/`, `output/logs/lag_model/` |
| 4 Descriptives | `4_descriptives/descriptive_stats.py`, `fig4_aum.py` | Returns, proxies and news variables; Figure A4 (equal- vs AUM-weighted mean allocation) | `output/descriptives/` |
| 5 Sample checks | `5_sample_checks/option_aum.py`, `check_apra_consistency.py` | Sample AUM against APRA totals; reconciliation with the APRA files | `output/sample_checks/` |
| 6 Asymmetry | `6_asymmetry/asymmetry_model.py`, `report_asymmetry.py` | Is negative news recognised more slowly than positive news? | `output/estimates/asymmetry/`, `output/asymmetry/` |

One-off data collection, not in the pipeline: `utilities/grab_download.sh` copies a downloaded price file from the Downloads folder into `data/raw/unit_prices/`; `utilities/parse_reisuper_pdfs.py` converts the REI Super PDF price lists to csv.

## History

- 2 October 2026: folder reorganised; superseded files moved to `_old/`.
- 11 October 2026: outdated files moved to `_old/superseded_2026-10-11/`. Folders renamed to the replication-package layout: `data_raw` -> `data/raw`, `master` -> `data/derived`, `results` -> `output`. Model objects and logs moved out of `code/` into `output/estimates/` and `output/logs/`. Scripts grouped into one folder per stage, with paths updated. The previous code is kept in `_old/superseded_2026-10-11/code_before_restructure/`.
