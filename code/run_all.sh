#!/bin/bash
# Full pipeline, in order. Run from anywhere:   bash code/run_all.sh            (every stage)
#                                              bash code/run_all.sh 3 4 5      (selected stages)
# Stage 1  build the data (data/raw -> data/derived)     Stage 2  check the data
# Stage 3  distributed-lag model (slow)                   Stage 4  descriptive statistics
# Stage 5  sample checks against APRA                     Stage 6  asymmetric recognition
# Not included (one-off data collection): code/utilities/grab_download.sh, code/utilities/parse_reisuper_pdfs.py
set -e
export PYTHONDONTWRITEBYTECODE=1                    # no __pycache__ folders
cd "$(dirname "$0")/.."                             # project folder
STAGES="${*:-1 2 3 4 5 6}"
run() { echo ">> $*"; "$@"; }
for s in $STAGES; do
  case $s in
    1) run python3 code/1_build/build_master.py saa
       run python3 code/1_build/build_master.py fund
       run python3 code/1_build/build_master.py perf
       run python3 code/1_build/build_master.py merge          # option-quarter master + unit-price mapping template
       run python3 code/1_build/convert_unit_prices.py         # data/raw/unit_prices -> data/derived/unit_prices
       run python3 code/1_build/build_master.py weekly         # weekly panel data/derived/master_weekly.csv.gz
       run python3 code/1_build/build_option_aum.py ;;         # AUM weights data/derived/option_aum_june2026_all.csv
    2) run python3 code/2_data_checks/check_unit_prices.py     # data/derived/unit_price_checks.xlsx
       run python3 code/2_data_checks/check_date_alignment.py
       run python3 code/2_data_checks/check_weekly_alignment.py
       run python3 code/2_data_checks/make_master_xlsx.py      # Excel version of the master (browsing only)
       run python3 code/2_data_checks/summarise_master.py ;;   # output/data_summary/
    3) run bash code/3_lag_model/run_lag_model.sh ;;            # output/lag_model/, output/estimates/lag_model/
    4) run python3 code/4_descriptives/descriptive_stats.py    # output/descriptives/
       run python3 code/4_descriptives/fig4_aum.py ;;          # Figure A4, equal- vs AUM-weighted allocation
    5) run python3 code/5_sample_checks/option_aum.py          # output/sample_checks/option_aum_june2026.xlsx
       run python3 code/5_sample_checks/check_apra_consistency.py ;;   # output/sample_checks/apra_consistency_check.xlsx
    6) run python3 code/6_asymmetry/asymmetry_model.py         # positive vs negative news -> output/estimates/asymmetry/
       run python3 code/6_asymmetry/report_asymmetry.py ;;     # output/asymmetry/
    *) echo "unknown stage $s"; exit 1 ;;
  esac
done
