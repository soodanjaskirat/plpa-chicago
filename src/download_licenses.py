"""
Step 1: Download business license records from the Chicago Data Portal.

We download three raw files:

1. licenses_lender_candidates.csv
   Every license record whose business name contains a lending-related word
   (LOAN, CASH, TITLE, PAYDAY, ...) plus every Pawnbroker license. This is a
   deliberately WIDE net: it contains many non-lenders (e.g. "Advance Auto Parts").
   We narrow it down later using the hand-checked list in
   data/reference/lender_entities.csv.

2. licenses_all_active_2019-07-01.csv
   Every business (of any kind) with a license active on July 1, 2019.
   We use it to measure how commercial each neighborhood is, because lenders
   open where there are shops. Without that control, we might just "discover"
   that lenders are located on busy shopping streets.

3. citywide_limited_license_counts.csv
   How many ordinary storefront businesses were licensed each year, citywide.
   This is the background trend to compare lender closures against.

The portal updates daily, so we record the download time in a small text file.
"""

from datetime import datetime, timezone
import pandas as pd
import requests

from config import RAW, LICENSES_URL, COMMERCIAL_DATE, PANEL_YEARS

# Words that commonly appear in names of payday, title, installment lenders and pawnshops.
KEYWORDS = ["LOAN", "LEND", "CASH", "TITLE", "PAYDAY", "PAY DAY", "CREDIT", "FINANC",
            "ADVANCE", "CHECK", "MONEY", "PAWN", "QUIK", "QUICK"]

PAGE_SIZE = 50000  # the portal returns at most this many rows per request


def fetch_all(params):
    """Download every row matching a query, one page at a time.

    The portal won't send millions of rows at once, so we ask for page 1,
    then page 2 (using $offset), and so on until a page comes back short."""
    rows, offset = [], 0
    while True:
        page_params = dict(params, **{"$limit": PAGE_SIZE, "$offset": offset, "$order": "id"})
        response = requests.get(LICENSES_URL, params=page_params, timeout=300)
        response.raise_for_status()  # stop with an error if the download failed
        page = response.json()
        rows.extend(page)
        offset += len(page)
        print(f"  downloaded {offset:,} rows so far")
        if len(page) < PAGE_SIZE:
            return pd.DataFrame(rows)


def main():
    # --- 1. Wide net of possible lenders --------------------------------------
    # Build a SoQL (the portal's SQL-like query language) WHERE clause like:
    #   upper(legal_name) like '%LOAN%' OR upper(doing_business_as_name) like '%LOAN%' OR ...
    name_conditions = " OR ".join(
        f"upper(legal_name) like '%{word}%' OR upper(doing_business_as_name) like '%{word}%'"
        for word in KEYWORDS
    )
    where = f"({name_conditions}) OR license_description = 'Pawnbroker'"
    print("Downloading lender candidate licenses...")
    candidates = fetch_all({"$where": where})
    candidates.drop(columns=["location"], errors="ignore").to_csv(
        RAW / "licenses_lender_candidates.csv", index=False)
    print(f"Saved {len(candidates):,} candidate license records")

    # --- 2. All businesses active on one date (for the commercial-activity control) ---
    print(f"Downloading all businesses licensed on {COMMERCIAL_DATE}...")
    all_active = fetch_all({
        "$select": "id, account_number, site_number, license_description, latitude, longitude",
        "$where": f"license_start_date <= '{COMMERCIAL_DATE}' AND expiration_date >= '{COMMERCIAL_DATE}'",
    })
    all_active.to_csv(RAW / f"licenses_all_active_{COMMERCIAL_DATE}.csv", index=False)
    print(f"Saved {len(all_active):,} active license records")

    # --- 3. Citywide count of ordinary storefront businesses each year ---
    # This is the "background" trend: how many Limited Business License locations
    # existed each Jan 1. Lenders closing faster than this suggests something
    # beyond normal business turnover (or COVID) was going on.
    print("Counting citywide Limited Business License locations by year...")
    yearly = []
    for year in PANEL_YEARS:
        day = f"{year}-01-01"
        response = requests.get(LICENSES_URL, timeout=300, params={
            "$select": "count(distinct account_number || '-' || site_number) as n",
            "$where": (f"license_description = 'Limited Business License' AND "
                       f"license_start_date <= '{day}' AND expiration_date >= '{day}'"),
        })
        response.raise_for_status()
        yearly.append({"year": year, "limited_license_locations": int(response.json()[0]["n"])})
    pd.DataFrame(yearly).to_csv(RAW / "citywide_limited_license_counts.csv", index=False)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (RAW / "licenses_download_time.txt").write_text(
        f"Chicago Business Licenses (r5kz-chrr) downloaded {stamp}\n")


if __name__ == "__main__":
    main()
