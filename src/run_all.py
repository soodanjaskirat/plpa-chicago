"""
Rebuild the whole project from scratch, in the right order:
data -> analysis tables (results/) -> figures (figures/).

    python src/run_all.py            # reuse raw files already downloaded
    python src/run_all.py --refresh  # download everything again first

Why reuse raw files by default? The city's license data changes every day.
Keeping the exact files we downloaded means anyone re-running the cleaning
steps gets exactly our numbers. Use --refresh only when you want newer data
(and expect small differences).
"""

import argparse

import analysis_descriptive
import analysis_models
import analysis_substitution
import build_storefronts
import build_tracts
import download_acs
import download_boundaries
import download_licenses
import make_figures
import review_candidates
import validate_coverage_2011
from config import RAW, COMMERCIAL_DATE, census_api_key

ACS_FILE = RAW / "acs_2015_2019_cook_tracts.csv"


def download(step, marker, refresh):
    """Run a download step unless its raw file already exists."""
    if marker.exists() and not refresh:
        print(f"[skip] {step.__name__}: {marker.name} already downloaded")
    else:
        print(f"[run]  {step.__name__}")
        step.main()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-download all raw data")
    args = parser.parse_args()

    # 1. City data: licenses and boundaries (no key needed).
    download(download_licenses, RAW / f"licenses_all_active_{COMMERCIAL_DATE}.csv", args.refresh)
    download(download_boundaries, RAW / "chicago_tracts_2010.geojson", args.refresh)

    # 2. Lender storefronts and the 2011 coverage check.
    for step in (review_candidates, build_storefronts, validate_coverage_2011):
        print(f"[run]  {step.__name__}")
        step.main()

    # 3. Census data (needs a free key), then the tract-level dataset.
    if not ACS_FILE.exists() and not census_api_key():
        print("[stop] No Census API key. Get one at https://api.census.gov/data/key_signup.html,\n"
              "       save it in a file named .census_key in the project folder, and run again.")
        return
    download(download_acs, ACS_FILE, args.refresh)
    print("[run]  build_tracts")
    build_tracts.main()

    # 4. Analysis and figures.
    for step in (analysis_descriptive, analysis_models, analysis_substitution, make_figures):
        print(f"[run]  {step.__name__}")
        step.main()
    print("Done. Data in data/clean/, tables in results/, figures in figures/")


if __name__ == "__main__":
    main()
