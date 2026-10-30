"""
Helper step: list license accounts that MIGHT be lenders, for a human to review.

This is how data/reference/lender_entities.csv was built. The keyword download
catches thousands of non-lenders ("Advance Auto Parts", "Mesirow Financial"...),
so a person has to read the names and decide which are storefront lenders.

Output: data/reference/candidate_accounts_for_review.csv
  One row per business owner account that was licensed at some point between
  2014 and the law date, with its names and number of locations, plus the
  category it was given in lender_entities.csv (blank = judged not a lender).
"""

import pandas as pd

from config import RAW, REFERENCE, LAW_DATE, PANEL_YEARS

# Names containing these words are probably lenders worth a look...
LENDER_WORDS = r"LOAN|LEND|PAYDAY|PAY DAY|TITLE|CASH ADV|CASH STORE|QUIK|FINANC|CREDIT|MONEY|CASH|CHECK ?.?N.? ?GO|CHECK INTO"
# ...unless they also contain one of these (clearly a different kind of business).
NOT_LENDER_WORDS = (r"ADVANCE AUTO|CAR ?WASH|MORTGAGE|INSURANCE|TAX|RESTAURANT|FOOD|BEAUTY|SALON|"
                    r"CASH (?:&|AND) CARRY|CREDIT UNION|REALTY|REAL ESTATE|AUTO SALES|MOTORS|CARS")


def main():
    lic = pd.read_csv(RAW / "licenses_lender_candidates.csv", dtype=str)
    lic["start"] = pd.to_datetime(lic["license_start_date"], errors="coerce")
    lic["end"] = pd.to_datetime(lic["expiration_date"], errors="coerce")

    # Keep licenses that overlap the start of our study window .. law date.
    lic = lic[(lic["start"] <= LAW_DATE) & (lic["end"] >= f"{PANEL_YEARS[0]}-01-01")]
    # Storefront lenders hold the city's general "Limited Business License".
    lic = lic[lic["license_description"] == "Limited Business License"]

    names = (lic["legal_name"].fillna("") + " " + lic["doing_business_as_name"].fillna("")).str.upper()
    lic = lic[names.str.contains(LENDER_WORDS) & ~names.str.contains(NOT_LENDER_WORDS)]

    review = (lic.groupby("account_number")
                 .agg(legal_name=("legal_name", "last"),
                      dba_names=("doing_business_as_name", lambda s: "; ".join(sorted(set(s.dropna())))[:120]),
                      n_locations=("site_number", "nunique"))
                 .reset_index())

    entities = pd.read_csv(REFERENCE / "lender_entities.csv", dtype=str)
    review = review.merge(entities[["account_number", "category"]], on="account_number", how="left")
    review = review.sort_values(["category", "n_locations"], ascending=[True, False])
    review.to_csv(REFERENCE / "candidate_accounts_for_review.csv", index=False)
    print(f"Wrote {len(review)} accounts for review "
          f"({review['category'].notna().sum()} classified in lender_entities.csv)")


if __name__ == "__main__":
    main()
