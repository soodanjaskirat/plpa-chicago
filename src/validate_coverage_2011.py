"""
Validation: do City of Chicago business licenses actually capture state-licensed lenders?

Our whole project uses CITY licenses to locate lenders. A fair critic would ask:
"How do you know the city data includes the lenders the STATE licensed?"

We can test this for one date. The Wayback Machine saved IDFPR's official
"Consumer Credit Licensee List" current to April 5, 2011, with every branch
address. We take every Chicago branch on that state list and check whether
the city had an active business license at the same street address on that date.

The share of state-listed branches that we find in the city data is the
"coverage rate". High coverage means the city data is a trustworthy record of
lender storefronts (at least in 2011).

Outputs:
  data/raw/idfpr_consumer_credit_licensees_2011-04-05.pdf   (archived state list)
  data/raw/licenses_all_active_2011-04-05.csv               (city licenses on that date)
  data/clean/validation_2011_coverage.csv                   (one row per state-listed Chicago branch)
"""

import re
import pandas as pd
import requests
from pypdf import PdfReader

from config import RAW, CLEAN, LICENSES_URL
from addresses import address_key as _address_key
from download_licenses import fetch_all

SNAPSHOT_DATE = "2011-04-05"
# Wayback Machine copy of the IDFPR PDF. The "id_" flag returns the original file.
IDFPR_2011_URL = ("http://web.archive.org/web/20210302072041id_/"
                  "https://www.idfpr.com/DFI/CCD/licensees/ConsumerInstallmentLicensees.pdf")

# Words that mean "this IDFPR licensee is a payday, title, or cash-advance type lender".
HIGH_COST_NAME_WORDS = r"PAYDAY|PAY DAY|CASH ADVANCE|TITLE LOAN|AMERICASH|CHECK INTO CASH|GREAT LAKES SPECIALTY|QC FINANCIAL|ILLINOIS LENDING|DEVON FINANCIAL|AMERICA'S FINANCIAL CHOICE|BUCKEYE|TITLE LENDERS|MOTION FUNDING|SUN CASH|GENESIS FINANCIAL"

def address_key(address):
    """Standardize an address, IGNORING direction (N/S/E/W), because the state
    list sometimes leaves out "West", "North", etc. See addresses.py."""
    return _address_key(address, keep_direction=False)


def parse_idfpr_pdf(path):
    """Pull every Chicago branch (name + street address) out of the IDFPR PDF.

    Each entry in the PDF ends with a line like '1857 773-493-5616'
    (license number + phone). We split the text into entries at those lines."""
    lines = []
    for page in PdfReader(path).pages:
        lines += [line.strip() for line in page.extract_text().splitlines()]

    entries, current = [], []
    for line in lines:
        current.append(line)
        if re.fullmatch(r"\d+ \d{3}-\d{3}-\d{2,4}", line):  # end of one licensee entry
            entries.append(current)
            current = []

    branches = []
    for entry in entries:
        city_idx = next((i for i, l in enumerate(entry) if re.search(r"\bIL\s+\d{5}", l)), None)
        if city_idx is None or not re.match(r"^CHICAGO\s+IL\b", entry[city_idx].upper()):
            continue  # keep only Chicago addresses (not Chicago Heights, etc.)
        # Name = first real line of the entry (skip headers, blanks, a stray "H"
        # head-office marker and d/b/a lines that spill over from the previous entry).
        skip = re.compile(r"^(D/B/A|CONSUMER CREDIT|LICENSEE|NAME & ADDRESS|\(TO|H$|$)", re.I)
        name = next(l for l in entry if not skip.match(l))
        # Street = the closest line above the city line that starts with a house
        # number (this skips "Suite 4", "#111" and building-name lines).
        above = [l for l in entry[:city_idx] if re.match(r"^\d+", l) and l != name
                 and not re.match(r"^\d+(ST|ND|RD|TH) FLOOR", l, re.I)]
        street = above[-1] if above else None
        is_head_office = any(l.startswith("CIN") for l in entry[city_idx:])
        branches.append({"idfpr_name": name, "street": street, "head_office": is_head_office})
    return pd.DataFrame(branches)


def main():
    pdf_path = RAW / "idfpr_consumer_credit_licensees_2011-04-05.pdf"
    if not pdf_path.exists():
        pdf_path.write_bytes(requests.get(IDFPR_2011_URL, timeout=300).content)

    city_path = RAW / f"licenses_all_active_{SNAPSHOT_DATE}.csv"
    if not city_path.exists():
        city = fetch_all({
            "$select": "account_number, site_number, legal_name, doing_business_as_name, address, license_description",
            "$where": f"license_start_date <= '{SNAPSHOT_DATE}' AND expiration_date >= '{SNAPSHOT_DATE}'",
        })
        city.to_csv(city_path, index=False)
    city = pd.read_csv(city_path, dtype=str)

    state = parse_idfpr_pdf(pdf_path)
    state["key"] = state["street"].map(address_key)
    city["key"] = city["address"].map(address_key)
    city_keys = set(city["key"].dropna())

    state["found_in_city_licenses"] = state["key"].isin(city_keys)
    state["high_cost_type"] = state["idfpr_name"].str.upper().str.contains(HIGH_COST_NAME_WORDS)
    state.to_csv(CLEAN / "validation_2011_coverage.csv", index=False)

    branches = state[~state["head_office"]]  # storefront branches, not head offices
    print(f"IDFPR 2011 list: {len(state)} Chicago entries ({len(branches)} branches, "
          f"{state['head_office'].sum()} head offices)")
    for label, subset in [("All branches", branches),
                          ("Payday/title/cash-advance branches", branches[branches["high_cost_type"]])]:
        print(f"  {label}: {subset['found_in_city_licenses'].mean():.0%} found in city licenses "
              f"({subset['found_in_city_licenses'].sum()} of {len(subset)})")


if __name__ == "__main__":
    main()
