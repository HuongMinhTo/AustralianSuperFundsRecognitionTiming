# Derived datasets (`data/derived/`)

Built by the scripts in `code/1_build/` from the raw files in `data/raw/`. Nothing in this folder is edited by hand. Rebuild everything with (from the project folder):

```
bash code/run_all.sh 1 2
```

## Files

| File | Level | Content |
|---|---|---|
| `option_quarter_master.csv` | option × quarter, Jun 2014 – Jun 2026 | Allocations + option attributes + APRA return measures + fund-year variables + quality flags. **Main option-level file.** |
| `option_quarter_master.xlsx` | same | Excel version with glossary, weight-check formulas and an audit against raw APRA rows (`code/2_data_checks/make_master_xlsx.py`; rebuilt by stage 2) |
| `master_weekly.csv.gz` | option × week | Weekly unit-price returns + start-of-quarter weights + option and fund variables (weeks inside the APRA SAA period only). |
| `unit_price_coverage.csv` | option | First/last price date, number of prices and largest gap for each converted series |
| `unit_price_checks.xlsx` | | Validation: quarterly returns from our prices vs APRA, coverage, outliers (`code/2_data_checks/check_unit_prices.py`) |
| `option_quarter_saa.csv` | option × quarter | Allocation buckets only (from QSPS Historical SAA) |
| `option_attributes.csv` | option | Name, type, category, fund, first and last quarter in the SAA file |
| `option_quarter_perf.csv` | option × quarter | APRA return and volatility measures (QSPS Historical performance) |
| `option_mysuper_flag.csv` | option | Whether the option is offered through a MySuper product |
| `fund_year.csv` | fund × financial year, 2014–2025 | Fund type, size, flows, ratios (APRA annual fund-level statistics, Tables 2a/2b and 3a/3b) |
| `unit_price_mapping_template.csv` | option | One row per option of the 41 checklist funds, to record which price series belongs to which APRA option |
| `unit_prices/` | | Standardised price files, one per fund (`code/1_build/convert_unit_prices.py` from `data/raw/unit_prices/`) |

## Keys and timing

- `option_id` = APRA investment option identifier (`<fund ABN>-<option code>`), identical in the SAA, performance and product files.
- `abn` = fund (RSE) ABN, links options to fund-year data.
- `saa_date` = quarter end at which the allocation is reported.
- In `master_weekly`, each week uses the allocation reported at the **end of the previous quarter** (start-of-quarter weights), so weights are known before the returns they explain.
- Fund-year variables are those of the latest balance date on or before the observation date (`fy_end`).

## Allocation buckets (`w_*`, decimals of the option)

| Variable | Definition (APRA ConsolidatedSectorType / ListingType / DomicileType) | Proxy |
|---|---|---|
| `w_EQ_AU_L`, `w_EQ_INT_L` | Listed equity, Australian / international | ASX 300; MSCI ACWI ex Aus |
| `w_PE_U` | Unlisted equity | Small-cap index |
| `w_PROP_AU_L`, `w_PROP_INT_L` | Listed property | A-REIT; global REIT |
| `w_PROP_U_AU`, `w_PROP_U_INT`, `w_PROP_U_NSDOM` | Unlisted property by domicile (NSDOM = domicile not specified) | A-REIT; global REIT |
| `w_INFRA_L`, `w_INFRA_U` | Listed / unlisted infrastructure | Global listed infrastructure |
| `w_CREDIT_U` | Unlisted credit (private credit) | Credit / high-yield |
| `w_FI`, `w_CASH` | Fixed income (incl. "excluding credit"), cash | AusBond, Global Agg; bank bill |
| `w_ALT_U`, `w_ALT_OTHER` | Alternatives, unlisted / other | — |
| `w_PROP_NS`, `w_INFRA_NS` | Property / infrastructure with listing type "Not Specified" | Treated both ways in robustness |
| `w_EQ_OTHER`, `w_PROP_OTHER`, `w_INFRA_OTHER`, `w_CREDIT_OTHER`, `w_OTHER` | Listing "Not Applicable"/"Not Specified" and residual items | — |
| `w_FX_OVERLAY` | Currency exposure overlay (not a physical asset) | — |
| `w_unlisted_core` | PE_U + all PROP_U + INFRA_U + CREDIT_U | **main unlisted exposure** |
| `w_unlisted_all` | `w_unlisted_core` + ALT_U | |
| `w_listed_growth` | Listed equity, property and infrastructure | |
| `w_intl`, `hedge_ratio_intl` | International share, and its allocation-weighted hedging ratio | Combines hedged/unhedged proxies |
| `w_total`, `w_total_ex_fx` | Sum of buckets; `w_total_ex_fx` ≈ 1 for 99% of option-quarters | Data check |

## Other variables

- Option: `option_name`, `option_type`, `option_category`, `fund_name`, `trustee`, `public_offer`, `first_saa`, `last_saa`, `is_mysuper_option`.
- APRA measures: `apra_return_measure`, `apra_vol_5y`, `apra_vol_10y` (from `return_measurement_comparison_percent` and the volatility fields of the Historical performance file; confirm APRA's definitions before use).
- Fund-year (`$'000` where `_k`): `fund_type`, `rse_class`, `profit_status`, `total_assets_k`, `log_assets`, `n_options`, `n_mysuper`, contributions, `flows_in_k`, `flows_out_k`, `rollover_in_k`, `rollover_out_k`, `sft_in_k`/`sft_out_k` (successor fund transfers), `benefits_k`, `net_flows_k`, `net_flow_ratio`, `gross_flow_ratio`, `outflow_ratio`, `inv_exp_ratio`, `op_exp_ratio`, `ret_1y_fund`, `member_accounts`, `avg_balance_k`, `wind_up_date`.
- `fund_type_2026` (from `fund_universe_june2026.csv`), `in_download_checklist`.
- Weekly file only: `week` (Wednesday), `price`, `price_date` (last price on or before that Wednesday), `stale_days`, `ret` (log return, Wednesday to Wednesday; missing if the last price is more than 5 days old), `price_type` (`unit_price`, `cumulative_index` or `crediting_rate`), `fy_end_dummy` (17 June – 14 July).
- Weekly file only: `ret_coverage_q` (share of the quarter's weeks with a return), `priced_q` (≥ 50%), `alloc_group_rep_priced`, `is_group_rep_priced` and **`core_sample_dedup_priced`**: one priced option per identical allocation per quarter. Lifecycle stages have no published price; when a stage has the same allocation as a priced option (e.g. Aware Grow = High Growth, ART Less than 50 = High Growth), the priced option represents the group. **Main weekly sample.**

## Quality flags and sample indicators (added 29 Sep 2026)

| Variable | Meaning | Rows TRUE |
|---|---|---|
| `core_sample` | Multi-sector, multi-manager, not pension, weights within 2 pp of 100%, not a bad-weight fund, not a specialist option. **Main sample.** | 624 options in Jun 2026, 41 funds |
| `core_sample_dedup` | `core_sample` and `is_group_rep`: one option per identical allocation per quarter | 412 options in Jun 2026 |
| `specialist_option`, `specialist_q` | Specialist options labelled multi-sector: capital-guaranteed or life products; property, infrastructure, credit or alternatives ≥ 40%; cash or fixed income ≥ 80%; or unlisted-only (no listed growth, unlisted ≥ 50%). Option-level flag if true in at least half of its quarters. 16 options pass every other core filter, e.g. HESTA Property and Infrastructure, ART Unlisted Assets, Prime Super Alternatives, Cbus Property, Cbus Diversified Fixed Interest, Brighter Super capital-guaranteed options | |
| `is_pension` | Offered only in the retirement phase, or name indicates pension / retirement income | 11,730 |
| `is_lifecycle` | Lifecycle (age-based) stage | 8,974 |
| `on_platform` | Offered only through platform menus | |
| `weights_incomplete` | Weights excluding the currency overlay more than 2 pp from 100% | 437 |
| `bad_weight_fund` | Fund with more than 2% incomplete rows: Avanteos, Netwealth, Wealth Personal | 3,455 |
| `pre_merger`, `last_major_merger_fy` | Quarters up to the fund's latest major merger (successor fund transfers in ≥ 25% of opening assets) | 10,009 |
| `fund_type_fixed` | June 2026 fund type used for every quarter (e.g. ART is Industry throughout) | |
| `fund_type_changed` | Historical fund type differs from `fund_type_fixed` | |
| `fund_vars_reliable` | Fund-level variables exist, not pre-merger, type unchanged. **Use fund-level variables only where TRUE.** | 32,974 |
| `d_unlisted_core`, `large_jump` | Change in unlisted share; jump > 10 pp | 157 |
| `reclass_jump` | Large jump at least half offset by the not-specified / other buckets (likely reclassification) | 76 |
| `alloc_group`, `alloc_group_size`, `alloc_group_rep`, `is_group_rep` | Options with identical bucket weights in the same quarter, and the representative (accumulation, then MySuper, then multi-manager, then lowest id) | |
| `filled_gap` | Quarter missing inside an option's history, allocation carried forward (7 Centric Super options) | 16 |
| `phases` | Accumulation / Retirement phases the option is offered in | |

Flow measures: `net_flows_ex_sft_k` and `net_flow_ratio_ex_sft` exclude successor fund transfers; `*_w` versions are winsorised at the 1st/99th percentiles. Use `net_flow_ratio_ex_sft_w`. `sft_in_share` and `major_merger_year` describe the attached fund-year.

`apra_return_measure` is the option's quarterly net return **in decimals** (0.0307 = 3.07%) for the quarter ending `saa_date`. Confirmed: quarterly returns computed from fund unit prices match it to within 0.25 pp for 85–100% of quarters (Equip, AustralianSuper, Hostplus, Vision Super, Aware).

Thresholds are set at the top of `code/1_build/build_master.py` (`MERGER_SHARE`, `JUMP`, `SUM_TOL`, `SPECIALIST`, `BAD_FUND_SHARE`).

## Unit prices (pilot: 10 funds, downloaded 30 Sep 2026)

Raw downloads are in `data/raw/unit_prices/` (`download_log.csv` lists source, coverage and caveats). Convert and rebuild with:

```
python3 code/1_build/convert_unit_prices.py   # raw -> data/derived/unit_prices/<fund>.csv + fills unit_price_mapping_template.csv
python3 code/1_build/build_master.py weekly   # -> master_weekly.csv.gz
python3 code/2_data_checks/check_unit_prices.py     # -> unit_price_checks.xlsx
```

Standard format of `unit_prices/*.csv`: `option_id, date (yyyy-mm-dd), price, price_type`. Crediting rates are chained into an index (base 100): price = 100 × cumulative product of (1 + rate).

| Fund | Series | Priced options (core, one per allocation) | Weekly returns from | Median abs. gap vs APRA quarterly return |
|---|---|---|---|---|
| ART (Super Savings + QSuper) | Unit prices | 17 | Jul 2014 (QSuper); Sep 2016 (Super Savings) | 0.06 pp |
| AustralianSuper | Daily crediting rates | 5 | Jul 2014 | 0.00 pp |
| Aware Super | Unit prices | 9 | Jan 2017 | 0.03 pp |
| Brighter Super | Unit prices | 8 | Jul 2017 | 0.05 pp |
| Cbus | Crediting rates (2 decimals; weekly to Oct 2018) | 6 | Jul 2014 | 0.13 pp |
| Hostplus | Unit prices | 15 | Nov 2017 | 0.00 pp |
| Vision Super | Unit prices | 9 | Jul 2014 | 0.00 pp |
| UniSuper | Cumulative crediting index (interim rates) | 7 | Jul 2014 | 0.22 pp (ours ≈ 0.13 pp per quarter lower, correlation 1.00) |
| Equip | Unit prices | 7 | Jul 2014 | 0.00 pp |
| Team Super | none published (latest week only) | 0 | — | request from fund |

Total: 83 priced options, 33,669 option-weeks with returns. In June 2026, 77 of the 110 core allocation groups in these funds have a priced representative; the rest are lifecycle stages that blend pools (ART ages 50–65, Aware Manage 56–64 except 60), Team Super, and Brighter's OnePath Managed Growth.

Data fixes applied in `convert_unit_prices.py`:
- QSuper dates are shifted back 2 business days (QSuper publishes with a 2-day lag; verified against the same option in ART's Super Savings file, correlation of daily returns 0.96 at lag 2, and against APRA quarterly returns: median gap falls from 0.35 pp to 0.05 pp).
- Vision Super: each option has two APRA codes with identical allocations; both are mapped to the SUPER series except VTBCNO, which matches the untaxed PENSION Balanced series exactly.
- Cbus: 0.00 before an option's start is treated as missing.
- Large moves (> 5% daily) are all in the GFC or March 2020, not data errors.

Caveats to model: Brighter fee-basis break on 31 May 2024 (admin fees no longer deducted in the unit price for MySuper and six other options); UniSuper series is built from interim crediting rates; Cbus rates are rounded to 0.01%; ART Super Savings history starts in Sep 2016 (website cap).

## Known limitations

- Allocations are strategic benchmark weights, not actual holdings; option-level holdings are not available.
- The Historical SAA file covers only options that still exist in June 2026 (52 funds), so it is a survivor sample.
- Some options appear in the SAA file before their fund's ABN appears in the fund-level statistics (e.g. MLC Super Fund 2014–2017), consistent with back-filled history from predecessor funds; their fund-year variables are missing for those quarters.
- The fund-level back series in this folder starts in FY2014 for the tables used.
