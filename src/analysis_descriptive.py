"""
Phase 2, part 1: descriptive statistics (no models yet, just careful counting).

Answers, in plain numbers:
  1. How many high-cost lenders and pawnshops existed each year?
  2. How do tracts WITH a high-cost store differ from tracts without one?
  3. Who lived near these stores? Compare each group's share of Chicago's
     population with its share of the stores ("exposure").
  4. How did each chain's licenses end after the law?

Tables are saved to results/.
"""

import pandas as pd

from analysis_data import load_tracts, load_stores
from config import CLEAN, RAW, RESULTS, LAW_DATE

TRACT_VARS = {
    "median_hh_income": "Median household income ($)",
    "pct_black": "Share Black",
    "pct_hispanic": "Share Latino",
    "pct_white": "Share white (non-Hispanic)",
    "poverty_rate": "Poverty rate",
    "unemployment_rate": "Unemployment rate",
    "renter_share": "Renter share",
    "n_businesses_2019": "Licensed businesses (2019)",
    "pop_total": "Population",
}


def store_counts_by_year():
    """Counts of open storefronts on Jan 1 of each year, plus the citywide background."""
    panel = pd.read_csv(CLEAN / "storefront_year_panel.csv")
    counts = panel[panel["active"]].groupby(["year", "category"]).size().unstack(fill_value=0)
    counts = counts[["high_cost", "pawn"]]
    citywide = pd.read_csv(RAW / "citywide_limited_license_counts.csv").set_index("year")
    counts = counts.join(citywide)
    counts.to_csv(RESULTS / "store_counts_by_year.csv")
    return counts


def tract_comparison(tracts):
    """Average characteristics of tracts with vs. without a high-cost store in 2020."""
    has = tracts["any_high_cost_pre"] == 1
    table = pd.DataFrame({
        "Tracts with a store": tracts.loc[has, list(TRACT_VARS)].mean(),
        "Tracts without": tracts.loc[~has, list(TRACT_VARS)].mean(),
        "All tracts": tracts[list(TRACT_VARS)].mean(),
    }).rename(index=TRACT_VARS)
    table.loc["Number of tracts"] = [has.sum(), (~has).sum(), len(tracts)]
    table.to_csv(RESULTS / "tract_comparison.csv")
    return table


def exposure(tracts, group_col):
    """For each group of tracts: share of Chicago's residents vs. share of the stores.

    If a group holds 27% of residents but 40% of the stores, stores are
    over-concentrated there. We also report stores per 100,000 residents and
    the share of residents living within a mile of at least one store."""
    g = tracts.groupby(group_col, observed=True)
    out = pd.DataFrame({
        "tracts": g.size(),
        "residents": g["pop_total"].sum(),
        "stores_2020": g["n_high_cost_pre"].sum(),
    })
    out["share_of_residents"] = out["residents"] / out["residents"].sum()
    out["share_of_stores"] = out["stores_2020"] / out["stores_2020"].sum()
    out["stores_per_100k"] = out["stores_2020"] / out["residents"] * 1e5
    near = tracts.assign(near_pop=tracts["pop_total"] * (tracts["high_cost_within_1mi"] > 0))
    out["share_living_within_1mi"] = near.groupby(group_col, observed=True)["near_pop"].sum() / out["residents"]
    return out


def closures_by_brand():
    """How each chain's licenses ended, for stores licensed on the day the law passed."""
    stores = load_stores()
    at_law = stores[(stores["category"] == "high_cost") & stores["active_law"]]
    table = (at_law.groupby("brand")
             .agg(stores_at_law_date=("storefront_id", "size"),
                  cancelled_early=("license_ended", lambda s: (s == "cancelled_early").sum()),
                  expired=("license_ended", lambda s: (s == "expired").sum()),
                  still_active=("license_ended", lambda s: (s == "still_active").sum()),
                  last_license_ended=("last_licensed", "max"))
             .sort_values("stores_at_law_date", ascending=False))
    # How long after the law did the last license end? (in months)
    table["months_after_law"] = ((table["last_license_ended"] - pd.Timestamp(LAW_DATE)).dt.days / 30.4).round(0)
    table.to_csv(RESULTS / "closures_by_brand.csv")
    return table


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    tracts = load_tracts()

    print("== 1. Open storefronts on Jan 1 of each year ==")
    print(store_counts_by_year().to_string())

    print("\n== 2. Tracts with vs. without a high-cost store (2020) ==")
    print(tract_comparison(tracts).to_string())

    print("\n== 3a. Exposure by neighborhood majority group ==")
    by_group = exposure(tracts, "majority_group")
    by_group.to_csv(RESULTS / "exposure_by_majority_group.csv")
    print(by_group.to_string())

    print("\n== 3b. Exposure by tract income quintile ==")
    by_income = exposure(tracts, "income_quintile")
    by_income.to_csv(RESULTS / "exposure_by_income_quintile.csv")
    print(by_income.to_string())

    print("\n== 4. How licenses ended after the law ==")
    print(closures_by_brand().to_string())


if __name__ == "__main__":
    main()
