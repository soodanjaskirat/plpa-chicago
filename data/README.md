# Data

Everything in `clean/` is rebuilt from `raw/` and `reference/` by running:

```bash
python src/run_all.py            # uses the raw files already here
python src/run_all.py --refresh  # downloads fresh raw data first
```

The Census step needs a free API key (https://api.census.gov/data/key_signup.html)
saved in a file named `.census_key` in the project root. That file is git-ignored.

## raw/ — downloaded, never edited by hand

| File | Source | What it is |
|---|---|---|
| `licenses_lender_candidates.csv` | Chicago Data Portal, Business Licenses (`r5kz-chrr`) | Every license record whose legal or DBA name contains a lending word (LOAN, CASH, TITLE, PAYDAY, …), plus every Pawnbroker license. A deliberately wide net, with many non-lenders. |
| `licenses_all_active_2019-07-01.csv` | same | Every business licensed on July 1, 2019 (used to measure how commercial each tract is). |
| `citywide_limited_license_counts.csv` | same | Count of Limited Business License locations on Jan 1 of each year: the citywide background trend. |
| `licenses_download_time.txt` | — | When the license files were downloaded (the portal changes daily). |
| `licenses_all_active_2011-04-05.csv` | same | Every business licensed on April 5, 2011 (for the coverage check). |
| `idfpr_consumer_credit_licensees_2011-04-05.pdf` | IDFPR, via the Wayback Machine | The state's official list of consumer-credit licensees with branch addresses, current to April 5, 2011. IDFPR stopped updating this file after 2011. |
| `chicago_tracts_2010.geojson` | Chicago Data Portal (`74p9-q2aq`) | 801 census tract boundaries (2010 Census). |
| `chicago_community_areas.geojson` | Chicago Data Portal (`igwz-8jzy`) | 77 community area boundaries. |
| `acs_2015_2019_cook_tracts.csv` | Census Bureau API, ACS 5-year 2015–2019 | Tract characteristics for Cook County (needs API key). |
| `geocode_cache.csv` | Census Geocoder | Only created if some licenses lack coordinates. |

## reference/ — small hand-made tables

| File | What it is |
|---|---|
| `lender_entities.csv` | **The key judgment call in this project.** Each city license account we classified as a lender, its category, and the evidence. `check_status` / `check_note` record a cross-check done on Oct 31, 2026: whether the company's name or Chicago branch addresses appear on IDFPR's archived 2011 licensee list, or another source confirms it. All 28 high-cost accounts are confirmed (26 by matching branch addresses). NMLS Consumer Access was not used, because it requires accepting its terms of use for each search. |
| `candidate_accounts_for_review.csv` | Output of `src/review_candidates.py`: every possible lender account, with the category it was given (blank = judged not a lender). Lets anyone audit our choices. |

Categories:
- `high_cost`: payday, auto-title and high-APR installment lenders (the law's target).
- `lower_cost`: OneMain (≤36% APR). **Unusable as a comparison group:** its Chicago licenses stop in 2019 even though its branches stayed open.
- `pawn`: pawnshops, identified by the city's Pawnbroker license type (no name matching needed).
- `uncertain`: small-loan companies whose prices we could not verify; excluded from main results, used in sensitivity checks.
- `exclude_office`: online lenders' head offices (not storefronts).

## clean/ — produced by scripts

### `storefronts.csv` — one row per lender storefront
A storefront = a lender category + a standardized street address, merged across license renewals and ownership changes.

| Column | Meaning |
|---|---|
| `storefront_id` | `category|address key`, e.g. `high_cost|5638 W FULLERTON` |
| `category`, `brand` | From `lender_entities.csv` (pawn brand = city DBA name) |
| `accounts` | Every city account number ever licensed at this storefront |
| `address`, `zip_code`, `latitude`, `longitude` | From the most recent license |
| `first_licensed`, `last_licensed` | First license start / last license end |
| `license_ended` | `cancelled_early` (license cancelled before expiry: strong sign of closure), `expired` (not renewed), or `still_active` |
| `active_pre`, `active_law`, `active_post` | Licensed on 2020-01-01, 2021-03-23 (law date), 2024-01-01 |
| `geocoded_by` | `city` (coordinates from the license data) or `census_geocoder` |
| `tract_geoid`, `community_area` | 2010 census tract and community area the store is in |

### `storefront_year_panel.csv` — storefront × year
`active` = licensed on January 1 of that year (2014–2026).

### `tracts_analysis.csv` / `.geojson` — one row per census tract (801)
- `n_<category>_pre`, `n_<category>_post`: storefronts licensed on 2020-01-01 / 2024-01-01
- `n_businesses_2019`: distinct licensed business locations on 2019-07-01 (commercial activity)
- `area_km2`: land area
- ACS 2015–2019: `pop_total`, `median_hh_income` (+ `_moe`, the margin of error), `pct_black`, `pct_hispanic`, `pct_white` (non-Hispanic), `poverty_rate`, `unemployment_rate`, `renter_share`, `majority_group`

### `validation_2011_coverage.csv`
Each Chicago branch on IDFPR's 2011 list, and whether the city had a business license at that address on the same date.

## Known limitations of the data

1. **A license is not proof a store is open.** Stores can close before a license expires. This is why "after" is measured on 2024-01-01, well past the 2-year life of any license bought before the law.
2. **Coverage is high but not complete.** In 2011, 95% of the payday/title/cash-advance branches on the state list (80 of 84) had a city license at the same address, and 90% of all consumer-credit branches did. We can't run this check for 2019–2020 because no state list with addresses from those years is public.
3. **OneMain's city licenses stop in 2019 while its branches stayed open.** So for at least one company, a lapsed license did *not* mean a closure. For high-cost lenders, the evidence points the other way. They kept renewing in 2019–2020. Then 40 of the 65 stores licensed on the law date had licenses **cancelled before expiry**, mostly within months of the law. The state's own count also fell from 407 payday licenses to 10 (Woodstock Institute, from IDFPR data).
4. **Lender identification relies on a hand-built list.** Lenders whose city license names contain none of our keywords would be missed.
5. **Gaps under one year** between licenses at the same address are treated as continuous (16 cases, e.g. Check 'n Go re-registering under a new company in 2018).
6. **About 10% of all 2019 business licenses** lack coordinates or sit outside city limits, so `n_businesses_2019` slightly undercounts.
7. **ACS tract estimates have margins of error**, sometimes large. For median household income, the typical (median) tract's margin of error is about 19% of the estimate, so tract income is an estimate, not an exact number.
8. **4 tracts have no median income.** Three have zero residents (the O'Hare and Midway airport tracts, plus one non-residential tract). The fourth is a Hyde Park tract (community area 41) where the Census withheld the estimate. All 801 tracts otherwise matched the Census data, for a total population of 2,731,881.
9. **Downtown is an outlier.** One Loop tract (17031839100) had 7 high-cost stores but also 2,400 licensed businesses. This is why the analysis must control for commercial activity.
