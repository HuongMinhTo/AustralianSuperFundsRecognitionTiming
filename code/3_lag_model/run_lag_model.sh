#!/bin/bash
# Distributed-lag model, equal-weighted and AUM-weighted: estimation, robustness and the combined report.
# Can be run from any folder. Needs data/derived/master_weekly.csv.gz (code/1_build/build_master.py weekly).
# Model objects -> output/estimates/lag_model/{equal,aum}/...   logs -> output/logs/lag_model/   report -> output/lag_model/
set -e
export PYTHONDONTWRITEBYTECODE=1                    # no __pycache__ folders
cd "$(dirname "$0")"
LOG=../../output/logs/lag_model; mkdir -p "$LOG"
python3 ../1_build/build_option_aum.py              # AUM weights -> data/derived/option_aum_june2026_all.csv
for C in equal aum; do
  WEIGHT=$C OUTSUB=$C python3 pilot_lag_model.py > $LOG/log_${C}_main.txt 2>&1
  WEIGHT=$C OUTSUB=$C/wed PROXY_ALIGN=wed python3 pilot_lag_model.py > $LOG/log_${C}_wed.txt 2>&1
  WEIGHT=$C OUTSUB=$C/trusts SAMPLE=trusts python3 pilot_lag_model.py > $LOG/log_${C}_trusts.txt 2>&1
  WEIGHT=$C OUTSUB=$C/tierA SAMPLE=tierA python3 pilot_lag_model.py > $LOG/log_${C}_tierA.txt 2>&1
  CASE=$C python3 robust.py > $LOG/log_${C}_robust.txt 2>&1
done
python3 ../5_sample_checks/option_aum.py            # sample AUM vs APRA totals (read by the report)
python3 report_weighting.py > $LOG/log_report.txt 2>&1   # -> output/lag_model/
