"""
Shared loaders for the analysis scripts.

Puts the clean data into the exact shape the models need, in one place, so
every table and figure uses the same definitions.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from config import CLEAN, RAW, COMMERCIAL_DATE

LOOP_COMMUNITY_AREA = 32       # downtown; an outlier with thousands of businesses
ACCESS_RADIUS_M = 1609         # 1 mile, in meters
METRIC_CRS = "EPSG:26916"      # UTM zone 16N: a map projection measured in meters


def load_tracts():
    """Tract table, restricted to tracts where people live, with model-ready variables.

    Variables are rescaled so regression results read naturally:
      income_10k     median household income in $10,000s
      black_10pp     percent Black, in 10-percentage-point steps (0.0 to 10.0)
      latino_10pp    percent Latino, in 10-percentage-point steps
      log_businesses log(1 + number of licensed businesses in 2019)
    """
    tracts = gpd.read_file(CLEAN / "tracts_analysis.geojson")
    tracts = tracts[(tracts["pop_total"] > 0) & tracts["median_hh_income"].notna()].copy()

    tracts["any_high_cost_pre"] = (tracts["n_high_cost_pre"] > 0).astype(int)
    tracts["income_10k"] = tracts["median_hh_income"] / 10_000
    tracts["black_10pp"] = tracts["pct_black"] * 10
    tracts["latino_10pp"] = tracts["pct_hispanic"] * 10
    tracts["poverty_10pp"] = tracts["poverty_rate"] * 10
    tracts["log_businesses"] = np.log1p(tracts["n_businesses_2019"])
    tracts["log_pop"] = np.log(tracts["pop_total"])
    tracts["income_quintile"] = pd.qcut(tracts["median_hh_income"], 5,
                                        labels=["Lowest", "Low", "Middle", "High", "Highest"])
    tracts["community_area"] = tracts["community_area"].astype(int)

    tracts = add_access_counts(tracts)
    return tracts


def load_stores():
    """All lender storefronts as map points."""
    stores = pd.read_csv(CLEAN / "storefronts.csv", dtype={"tract_geoid": str},
                         parse_dates=["first_licensed", "last_licensed"])
    return gpd.GeoDataFrame(stores, geometry=gpd.points_from_xy(stores["longitude"], stores["latitude"]),
                            crs="EPSG:4326")


def count_within(points, centers, radius):
    """For each center point, count how many points lie within `radius` meters."""
    circles = gpd.GeoDataFrame(geometry=centers.buffer(radius), crs=METRIC_CRS)
    joined = gpd.sjoin(circles, points[["geometry"]].to_crs(METRIC_CRS), how="left", predicate="contains")
    return joined.groupby(level=0)["index_right"].count().reindex(circles.index, fill_value=0)


def add_access_counts(tracts):
    """Count high-cost stores (and all businesses) within 1 mile of each tract's center.

    A store serves people from surrounding blocks, not only its own tract, so
    "is there a store within a mile?" is a second, fairer measure of access.
    We count all businesses within the same mile as the commercial-activity control."""
    stores = load_stores()
    pre = stores[(stores["category"] == "high_cost") & stores["active_pre"]]
    centers = tracts.to_crs(METRIC_CRS).geometry.centroid
    tracts["high_cost_within_1mi"] = count_within(pre, centers, ACCESS_RADIUS_M).values

    businesses = pd.read_csv(RAW / f"licenses_all_active_{COMMERCIAL_DATE}.csv", dtype=str)
    businesses = businesses.drop_duplicates(["account_number", "site_number"]).dropna(subset=["latitude"])
    business_points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(
        businesses["longitude"].astype(float), businesses["latitude"].astype(float)), crs="EPSG:4326")
    tracts["businesses_within_1mi"] = count_within(business_points, centers, ACCESS_RADIUS_M).values
    tracts["log_businesses_1mi"] = np.log1p(tracts["businesses_within_1mi"])
    return tracts


def load_panel():
    """Storefront-year panel turned into 'did this store close during the year?'.

    For every store open on Jan 1 of year t, exit = 1 if it is no longer
    licensed on Jan 1 of year t+1. 'post' marks years starting in 2021 or
    later: the law took effect in March 2021, so closures between Jan 2021
    and Jan 2022 are mostly after it."""
    panel = pd.read_csv(CLEAN / "storefront_year_panel.csv")
    panel = panel[panel["category"].isin(["high_cost", "pawn"])].sort_values(["storefront_id", "year"])
    panel["active_next_year"] = panel.groupby("storefront_id")["active"].shift(-1)
    at_risk = panel[panel["active"] & panel["active_next_year"].notna()].copy()
    at_risk["exit"] = (~at_risk["active_next_year"].astype(bool)).astype(int)
    at_risk["high_cost"] = (at_risk["category"] == "high_cost").astype(int)
    at_risk["post"] = (at_risk["year"] >= 2021).astype(int)
    return at_risk
