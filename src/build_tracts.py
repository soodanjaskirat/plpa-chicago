"""
Step 5: Build the neighborhood (census tract) dataset used for analysis.

One row per Chicago census tract (2010 boundaries, 801 tracts) with:
  - Census characteristics from ACS 2015-2019 (income, race/ethnicity, poverty, ...)
  - Number of lender storefronts of each type before (2020-01-01) and after (2024-01-01)
  - Number of licensed businesses of ANY kind (a measure of how commercial the area is)
  - Land area, so we can compute densities

Outputs:
  data/clean/tracts_analysis.csv       (table, for regression)
  data/clean/tracts_analysis.geojson   (same data with tract shapes, for maps)
"""

import sys
import geopandas as gpd
import numpy as np
import pandas as pd

from config import RAW, CLEAN, COMMERCIAL_DATE

CATEGORIES = ["high_cost", "lower_cost", "pawn", "uncertain"]


def load_acs():
    """Read the raw ACS download and compute percentages."""
    path = RAW / "acs_2015_2019_cook_tracts.csv"
    if not path.exists():
        sys.exit("ACS data missing: run src/download_acs.py first (needs a free Census API key).")
    acs = pd.read_csv(path, dtype={"state": str, "county": str, "tract": str})

    # The Census uses large negative numbers (e.g. -666666666) to mean
    # "not available" (for example, median income in a tract with almost no households).
    numeric = [c for c in acs.columns if c not in ("NAME", "state", "county", "tract")]
    acs[numeric] = acs[numeric].apply(pd.to_numeric, errors="coerce")
    acs[numeric] = acs[numeric].where(acs[numeric] >= 0)

    acs["geoid"] = acs["state"] + acs["county"] + acs["tract"]  # 11-digit tract ID

    # Percentages. np.where avoids dividing by zero in tracts with no people.
    def share(part, whole):
        return np.where(acs[whole] > 0, acs[part] / acs[whole], np.nan)

    acs["pct_black"] = share("nh_black", "race_universe")
    acs["pct_hispanic"] = share("hispanic", "race_universe")
    acs["pct_white"] = share("nh_white", "race_universe")
    acs["poverty_rate"] = share("below_poverty", "poverty_universe")
    acs["unemployment_rate"] = share("unemployed", "civ_labor_force")
    acs["renter_share"] = share("renter_units", "occupied_units")

    # A simple label for the tract's largest group, if it is over half the population.
    acs["majority_group"] = np.select(
        [acs["pct_black"] > 0.5, acs["pct_hispanic"] > 0.5, acs["pct_white"] > 0.5],
        ["Majority Black", "Majority Latino", "Majority white"],
        default="No majority",
    )
    return acs.drop(columns=["NAME", "state", "county", "tract"])


def count_points_in_tracts(df, tracts, lat="latitude", lon="longitude"):
    """Spatially join points to tracts and return the tract ID for each point."""
    df = df.dropna(subset=[lat, lon])
    points = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon].astype(float), df[lat].astype(float)),
                              crs="EPSG:4326")
    return gpd.sjoin(points, tracts[["geoid", "geometry"]], how="inner", predicate="within")


def main():
    tracts = gpd.read_file(RAW / "chicago_tracts_2010.geojson").to_crs("EPSG:4326")
    tracts = tracts.rename(columns={"geoid10": "geoid", "commarea": "community_area"})
    tracts = tracts[["geoid", "community_area", "geometry"]]
    # Area in square kilometers. We must switch to a map projection measured in
    # meters (UTM zone 16N, EPSG:26916) before measuring; lat/long degrees aren't distances.
    tracts["area_km2"] = tracts.to_crs("EPSG:26916").area / 1e6

    # --- Lender storefront counts per tract, before and after ---
    stores = pd.read_csv(CLEAN / "storefronts.csv", dtype={"tract_geoid": str})
    for when in ("pre", "post"):
        counts = (stores[stores[f"active_{when}"]]
                  .groupby(["tract_geoid", "category"]).size()
                  .unstack(fill_value=0)
                  .reindex(columns=CATEGORIES, fill_value=0)
                  .add_prefix("n_").add_suffix(f"_{when}"))
        tracts = tracts.merge(counts, left_on="geoid", right_index=True, how="left")

    # --- Commercial activity: distinct licensed business locations in mid-2019 ---
    businesses = pd.read_csv(RAW / f"licenses_all_active_{COMMERCIAL_DATE}.csv", dtype=str)
    businesses = businesses.drop_duplicates(["account_number", "site_number"])
    in_tracts = count_points_in_tracts(businesses, tracts)
    print(f"Businesses placed in a tract: {len(in_tracts):,} of {len(businesses):,} "
          f"(the rest lack coordinates or are outside city limits)")
    tracts = tracts.merge(in_tracts.groupby("geoid").size().rename("n_businesses_2019"),
                          left_on="geoid", right_index=True, how="left")

    count_cols = [c for c in tracts.columns if c.startswith("n_")]
    tracts[count_cols] = tracts[count_cols].fillna(0).astype(int)

    # --- Census characteristics ---
    acs = load_acs()
    tracts = tracts.merge(acs, on="geoid", how="left")
    print(f"Tracts with no ACS match: {tracts['pop_total'].isna().sum()}")
    print(f"Tracts with missing median income: {tracts['median_hh_income'].isna().sum()}")

    tracts.to_file(CLEAN / "tracts_analysis.geojson", driver="GeoJSON")
    tracts.drop(columns="geometry").to_csv(CLEAN / "tracts_analysis.csv", index=False)
    print(f"Saved {len(tracts)} tracts")
    print(tracts[[c for c in count_cols if c != "n_businesses_2019"]].sum().to_string())


if __name__ == "__main__":
    main()
